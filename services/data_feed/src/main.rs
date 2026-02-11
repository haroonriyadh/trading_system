use futures::{StreamExt, SinkExt};
use mongodb::{options::ClientOptions, Client, Collection, IndexModel, bson::{doc, DateTime}};
use redis::AsyncCommands;
use serde::{Deserialize, Deserializer};
use std::sync::Arc;
use tokio::sync::{broadcast, Semaphore};
use tokio::time::{interval, Duration};
use tokio_tungstenite::tungstenite::protocol::Message;
use tracing::{warn, error};

// =================================================================================
//  1. Data Structures
// =================================================================================

#[derive(Debug, Deserialize)]
struct BybitMsg<'a> {
    #[serde(borrow)]
    topic: &'a str,
    data: Vec<CandleRaw>,
}

#[derive(Debug, Deserialize)]
struct CandleRaw {
    #[serde(rename = "start")]
    start: i64,
    #[serde(rename = "end")]
    end: i64,
    #[serde(deserialize_with = "parse_f64_from_str")]
    open: f64,
    #[serde(deserialize_with = "parse_f64_from_str")]
    high: f64,
    #[serde(deserialize_with = "parse_f64_from_str")]
    low: f64,
    #[serde(deserialize_with = "parse_f64_from_str")]
    close: f64,
    #[serde(deserialize_with = "parse_f64_from_str")]
    volume: f64,
    confirm: bool,
    #[serde(rename = "timestamp")]
    _timestamp: i64,
}

fn parse_f64_from_str<'de, D>(deserializer: D) -> Result<f64, D::Error>
where
    D: Deserializer<'de>,
{
    let s: &str = Deserialize::deserialize(deserializer)?;
    s.parse::<f64>().map_err(serde::de::Error::custom)
}

#[derive(Debug, Clone)]
struct HLPoint {
    open_time: i64,
    price: f64,
    hl_type: i32
}

// =================================================================================
//  2. Main Entry Point
// =================================================================================

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter("warn") // فقط تحذيرات وإغلاق الشمعة
        .init();

    let mongo_host = std::env::var("MONGO_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let redis_host = std::env::var("REDIS_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());

    let mongo_url = format!("mongodb://{}:27017", mongo_host);
    let client_options = ClientOptions::parse(&mongo_url).await.unwrap();
    let mongo_client = Client::with_options(client_options).unwrap();
    let db_candle = mongo_client.database("CandleStick_data");
    let db_indicitors = mongo_client.database("Indicitors");

    let redis_url = format!("redis://{}:6379/", redis_host);
    let redis_client = redis::Client::open(redis_url).unwrap();
    let redis_conn = redis_client.get_multiplexed_async_connection().await.unwrap();

    let (tx, _) = broadcast::channel::<String>(10000);

    let symbols = load_symbols_from_json().await;
    if symbols.is_empty() {
        error!("❌ Failed to fetch symbols.");
        return;
    }

    // Historical Data Background
    let symbols_history = symbols.clone();
    let db_candle_hist = db_candle.clone();
    let db_indicitors_hist = db_indicitors.clone();
    tokio::spawn(async move {
        init_historical_data(&symbols_history, &db_candle_hist, &db_indicitors_hist).await;
    });

    // WebSocket واحد لكل الرموز
    let topics: Vec<String> = symbols.iter().map(|s| format!("kline.1.{}", s)).collect();
    let ws_url = "wss://stream.bybit.com/v5/public/linear";

    loop {
        match tokio_tungstenite::connect_async(ws_url).await {
            Ok((mut ws_stream, _)) => {
                // Subscribe لكل الرموز
                let subscribe_msg = serde_json::json!({"op":"subscribe","args":topics});
                if let Err(e) = ws_stream.send(Message::Text(subscribe_msg.to_string())).await {
                    error!("❌ Subscription failed: {:?}", e);
                    break;
                }

                let mut ping_interval = interval(Duration::from_secs(15));
                loop {
                    tokio::select! {
                        Some(msg) = ws_stream.next() => {
                            match msg {
                                Ok(Message::Text(txt)) => {
                                    handle_message(&txt, &tx, &db_candle, &redis_conn).await;
                                },
                                Ok(Message::Pong(_)) => {}, // Pong received
                                Ok(Message::Close(_)) => {
                                    warn!("⚠️ WebSocket closed by server, reconnecting...");
                                    break;
                                },
                                _ => {}
                            }
                        }
                        _ = ping_interval.tick() => {
                            // Ping to keep alive
                            if let Err(e) = ws_stream.send(Message::Ping(vec![])).await {
                                error!("❌ Ping failed: {:?}, reconnecting...", e);
                                break;
                            }
                        }
                        _ = tokio::time::sleep(Duration::from_secs(30)) => {
                            warn!("⚠️ No messages for 30s, reconnecting...");
                            break;
                        }
                    }
                }
            }
            Err(e) => {
                error!("❌ Connection Failed: {:?}. Retry in 5s...", e);
                tokio::time::sleep(Duration::from_secs(5)).await;
            }
       }
    }
}

// =================================================================================
//  Helpers and Handlers (unchanged logic, only removed info! printing)
// =================================================================================

async fn load_symbols_from_json() -> Vec<String> {
    let paths = vec!["shared/symbols.json","../shared/symbols.json","../../shared/symbols.json"];
    for p in paths {
        if let Ok(c) = std::fs::read_to_string(p) { return serde_json::from_str::<Vec<String>>(&c).unwrap_or(vec!["BTCUSDT".to_string()]); }
    }
    vec!["BTCUSDT".to_string()]
}

async fn ensure_index(collection: &Collection<mongodb::bson::Document>) {
    let model = IndexModel::builder().keys(doc! { "Open_time": -1 }).build();
    let _ = collection.create_index(model, None).await;
}

async fn handle_message(
    msg: &str,
    tx: &broadcast::Sender<String>,
    db: &mongodb::Database,
    redis_conn: &redis::aio::MultiplexedConnection
) {
    let parsed: BybitMsg = match serde_json::from_str(msg) { Ok(v) => v, Err(_) => return; };
    if parsed.data.is_empty() { return; }

    let symbol = parsed.topic.strip_prefix("kline.1.").unwrap_or(parsed.topic);

    for candle in parsed.data {
        let doc = doc! {
            "Open_time": DateTime::from_millis(candle.start),
            "Open": candle.open,
            "High": candle.high,
            "Low": candle.low,
            "Close": candle.close,
            "Volume": candle.volume,
            "Close_time": DateTime::from_millis(candle.end),
        };
        let json_str = serde_json::to_string(&doc).unwrap_or_default();
        let mut r_conn = redis_conn.clone();
        let r_symbol = symbol.to_string();
        let r_json = json_str.clone();
        let is_confirm = candle.confirm;

        let redis_task = async move {
            let _: redis::RedisResult<()> = r_conn.publish(format!("{}_RealTime", r_symbol), &r_json).await;
            if is_confirm {
                 let _: redis::RedisResult<()> = r_conn.publish(format!("{}_Close_Candle", r_symbol), &r_json).await;
                 warn!(symbol = %r_symbol, price = %candle.close, "🔥 Candle CLOSED");
            }
        };

        let mongo_task = async {
            if candle.confirm {
                let collection: Collection<mongodb::bson::Document> = db.collection(symbol);
                let _ = collection.insert_one(doc, None).await;
            }
        };

        let _ = tx.send(json_str);
        tokio::join!(redis_task, mongo_task);
    }
}

// =================================================================================
//  Historical Data (unchanged)
// =================================================================================

async fn init_historical_data(symbols: &[String], db_candle: &mongodb::Database, db_indicitors: &mongodb::Database) {
    let client = reqwest::Client::new();
    let semaphore = Arc::new(Semaphore::new(8));
    let mut handles = Vec::new();

    info!("📥 Fetching history and ensuring indexes for {} symbols...", symbols.len());

    for symbol in symbols {
        let symbol = symbol.clone();
        let db_candle = db_candle.clone();
        let db_indicitors = db_indicitors.clone();
        let client = client.clone();
        let sem = semaphore.clone();

        handles.push(tokio::spawn(async move {
            let _permit = sem.acquire().await.unwrap();
            let url = format!("https://api.bybit.com/v5/market/kline?category=linear&symbol={}&interval=1&limit=200", symbol);

            match client.get(&url).send().await {
                Ok(resp) => {
                    if let Ok(json) = resp.json::<serde_json::Value>().await {
                        if let Some(list) = json.get("result").and_then(|r| r.get("list")).and_then(|l| l.as_array()) {
                            let mut candle_docs = Vec::new();
                            let mut raw_candles = Vec::new();

                            for item in list {
                                if let Some(c) = item.as_array() {
                                    let start_ts = c[0].as_str().unwrap_or("0").parse::<i64>().unwrap_or(0);
                                    let open = c[1].as_str().unwrap_or("0").parse::<f64>().unwrap_or(0.0);
                                    let high = c[2].as_str().unwrap_or("0").parse::<f64>().unwrap_or(0.0);
                                    let low = c[3].as_str().unwrap_or("0").parse::<f64>().unwrap_or(0.0);
                                    let close = c[4].as_str().unwrap_or("0").parse::<f64>().unwrap_or(0.0);
                                    let volume = c[5].as_str().unwrap_or("0").parse::<f64>().unwrap_or(0.0);
                                    let end_ts = start_ts + 60000;

                                    let doc = doc! {
                                        "Open_time": DateTime::from_millis(start_ts),
                                        "Open": open,
                                        "High": high,
                                        "Low": low,
                                        "Close": close,
                                        "Volume": volume,
                                        "Close_time": DateTime::from_millis(end_ts),
                                    };
                                    candle_docs.push(doc);
                                    raw_candles.push((start_ts, open, high, low, close));
                                }
                            }

                            if !candle_docs.is_empty() {
                                candle_docs.reverse();
                                raw_candles.reverse();
                                
                                // ----------------------------------------------------
                                // 1. Handle Candle Collection (Clean, Index, Insert)
                                // ----------------------------------------------------
                                let col_candle: Collection<mongodb::bson::Document> = db_candle.collection(&symbol);
                                
                                // 🛠️ Ensure Index Exists!
                                ensure_index(&col_candle).await;

                                let _ = col_candle.delete_many(doc! {}, None).await;
                                let _ = col_candle.insert_many(candle_docs, None).await;

                                // ----------------------------------------------------
                                // 2. Handle Indicators Collection
                                // ----------------------------------------------------
                                let hl_points = detect_historical_hl(&raw_candles);
                                if !hl_points.is_empty() {
                                    let hl_docs: Vec<mongodb::bson::Document> = hl_points.into_iter().map(|p| {
                                        doc! {
                                            "Open_time": DateTime::from_millis(p.open_time),
                                            "Price": p.price,
                                            "Type": p.hl_type
                                        }
                                    }).collect();
                                    
                                    let col_ind: Collection<mongodb::bson::Document> = db_indicitors.collection(&symbol);
                                    
                                    // 🛠️ Ensure Index Exists!
                                    ensure_index(&col_ind).await;
                                    
                                    let _ = col_ind.delete_many(doc! {}, None).await;
                                    let _ = col_ind.insert_many(hl_docs, None).await;
                                }
                            }
                        }
                    }
                }
                Err(e) => error!(symbol = %symbol, error = ?e, "❌ Failed to fetch history"),
            }
        }));
    }

    futures::future::join_all(handles).await;
    info!("🏁 All historical data tasks finished (Indexes Verified).");
}

fn detect_historical_hl(candles: &[(i64, f64, f64, f64, f64)]) -> Vec<HLPoint> {
    let mut points = Vec::new();
    if candles.len() < 5 { return points; }

    for i in 2..candles.len() - 2 {
        let current = candles[i];
        let prev1 = candles[i-1];
        let prev2 = candles[i-2];
        let next1 = candles[i+1];
        let next2 = candles[i+2];

        if current.2 > prev1.2 && current.2 > prev2.2 && current.2 > next1.2 && current.2 > next2.2 {
            points.push(HLPoint {
                open_time: current.0,
                price: current.2,
                hl_type: 1
            });
        }
        if current.3 < prev1.3 && current.3 < prev2.3 && current.3 < next1.3 && current.3 < next2.3 {
            points.push(HLPoint {
                open_time: current.0,
                price: current.3,
                hl_type: 0
            });
        }
    }
    points
}
