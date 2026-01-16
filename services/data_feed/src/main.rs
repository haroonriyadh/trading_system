use futures::{StreamExt, SinkExt};
use mongodb::{options::ClientOptions, Client, Collection, bson::{doc, DateTime}};
use redis::AsyncCommands;
use serde::{Deserialize, Deserializer};
use std::sync::Arc;
use tokio::sync::{broadcast, Semaphore};
use tokio_tungstenite::tungstenite::protocol::Message;
use tracing::{info, warn, error, debug};
use axum::{extract::{Path, State}, routing::get, Json, Router};
use tower_http::cors::CorsLayer;
use futures::TryStreamExt; // لإصلاح مشكلة الـ cursor
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
    hl_type: String,
    side: String,
}

// Structs for Dynamic Symbol Fetching
#[derive(Debug, Deserialize)]
struct TickerResponse {
    result: TickerResult,
}

#[derive(Debug, Deserialize)]
struct TickerResult {
    list: Vec<TickerItem>,
}

#[derive(Debug, Deserialize)]
struct TickerItem {
    symbol: String,
    #[serde(rename = "turnover24h")]
    turnover: String,
}

// =================================================================================
//  2. Main Entry Point
// =================================================================================

#[tokio::main]
async fn main() {
    // 1. Init Logger
    tracing_subscriber::fmt()
        .with_env_filter("info")
        .init();

    info!("🚀 System Initialization Started (Single Connection Mode)...");

    // 2. Connect DBs (Using 127.0.0.1 for Termux stability)
    let client_options = ClientOptions::parse("mongodb://127.0.0.1:27017").await.unwrap();
    let mongo_client = Client::with_options(client_options).unwrap();
    let db_candle = mongo_client.database("CandleStick_data");
    let db_indicitors = mongo_client.database("Indicitors");

    let redis_client = redis::Client::open("redis://127.0.0.1:6379/").unwrap();
    let redis_conn = redis_client.get_multiplexed_async_connection().await.unwrap();

    let (tx, _) = broadcast::channel::<String>(10000); 

    info!("🌍 Loading symbols from shared/symbols.json...");
    let symbols = load_symbols_from_json().await;
    
    if symbols.is_empty() {
        error!("❌ Failed to fetch symbols. Please check internet connection.");
        return;
    }
    // طباعة أول 3 أسماء للتأكد
    info!("✅ Loaded {} symbols. Examples: {}, {}, {}", symbols.len(), symbols[0], symbols[1], symbols[2]);

    let ws_url = "wss://stream.bybit.com/v5/public/linear";
    
    // --- Background Task: Historical Data ---
    let symbols_history = symbols.clone();
    let db_candle_hist = db_candle.clone();
    let db_indicitors_hist = db_indicitors.clone();
    tokio::spawn(async move {
        init_historical_data(&symbols_history, &db_candle_hist, &db_indicitors_hist).await;
    });

    // 1. تشغيل سيرفر الـ API في الخلفية (انقله هنا قبل الـ loop)
    let app = Router::new()
        .route("/api/history/:symbol", get(get_history))
        .layer(CorsLayer::permissive())
        .with_state(db_candle.clone());

    tokio::spawn(async move {
        info!("🌐 API Server running on http://0.0.0.0:3000");
        let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await.unwrap();
        axum::serve(listener, app).await.unwrap();
    });


    // --- Single WebSocket Connection Logic ---
    let topics: Vec<String> = symbols.iter().map(|s| format!("kline.1.{}", s)).collect();

    info!("📡 Attempting Single WebSocket Connection for {} symbols...", symbols.len());

    loop {
        match tokio_tungstenite::connect_async(ws_url).await {
            Ok((mut ws_stream, _)) => {
                info!("✅ WebSocket Connected.");

                // ملاحظة فنية:
                // رغم أننا نستخدم اتصالاً واحداً، إلا أن Bybit أحياناً ترفض رسالة الاشتراك
                // إذا كانت تحتوي على عدد ضخم جداً من الـ args في سطر واحد.
                // للأمان، سنرسل أوامر الاشتراك في دفعات (داخل نفس الاتصال)
                // هذا لا يفتح اتصالات جديدة، بل يرسل رسائل عبر نفس الأنبوب.
                for chunk in topics.chunks(10) {
                    let subscribe_msg = serde_json::json!({
                        "op": "subscribe",
                        "args": chunk
                    });

                    if let Err(e) = ws_stream.send(Message::Text(subscribe_msg.to_string())).await {
                        error!("❌ Subscription command failed: {:?}", e);
                        break; // نكسر الحلقة لإعادة الاتصال بالكامل
                    }
                }
                info!("📤 All subscription commands sent.");

                // حلقة الاستماع (Listening Loop)
                while let Some(Ok(msg)) = ws_stream.next().await {
                    if let Message::Text(txt) = msg {
                        handle_message(&txt, &tx, &db_candle, &redis_conn).await;
                    }
                }
                warn!("⚠️ WebSocket connection closed by server. Reconnecting...");
            }
            Err(e) => {
                error!("❌ Connection Failed: {:?}. Retry in 5s...", e);
                tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
            }
       }
    }
}

// =================================================================================
//  3. Dynamic Symbol Fetcher
// =================================================================================

async fn load_symbols_from_json() -> Vec<String> {
    let path = std::path::Path::new("shared/symbols.json");
    if !path.exists() {
        error!("❌ symbols.json not found at {:?}", path);
        return vec!["BTCUSDT".to_string()];
    }

    match std::fs::read_to_string(path) {
        Ok(content) => {
            match serde_json::from_str::<Vec<String>>(&content) {
                Ok(symbols) => symbols,
                Err(e) => {
                    error!("❌ Failed to parse symbols.json: {:?}", e);
                    vec!["BTCUSDT".to_string()]
                }
            }
        }
        Err(e) => {
            error!("❌ Failed to read symbols.json: {:?}", e);
            vec!["BTCUSDT".to_string()]
        }
    }
}

// =================================================================================
//  4. Real-Time Handler (مع تفعيل طباعة الـ Info لكل تحديث)
// =================================================================================

async fn handle_message(
    msg: &str, 
    tx: &broadcast::Sender<String>, 
    db: &mongodb::Database, 
    redis_conn: &redis::aio::MultiplexedConnection
) {
    let parsed: BybitMsg = match serde_json::from_str(msg) {
        Ok(val) => val,
        Err(_) => return, 
    };

    if parsed.data.is_empty() { return; }

    let symbol = match parsed.topic.strip_prefix("kline.1.") {
        Some(s) => s,
        None => parsed.topic,
    };

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
        
        // -------------------------------------------------------------
        //  التعديل هنا: تفعيل طباعة Info لكل عملة
        // -------------------------------------------------------------
        // نستخدم Structured Logging ليكون الأداء سريعاً حتى مع الطباعة الكثيرة
        info!(
            symbol = %symbol, 
            price = %candle.close, 
            vol = %candle.volume, 
            "⚡ Update"
        );
        // -------------------------------------------------------------

        let mut r_conn = redis_conn.clone();
        let r_symbol = symbol.to_string();
        let r_json = json_str.clone();
        let is_confirm = candle.confirm;
        
        let redis_task = async move {
            let _: redis::RedisResult<()> = r_conn.publish(format!("{}_RealTime", r_symbol), r_json).await;
            if is_confirm {
                 // تمييز الإغلاق بلون مختلف (Warn يظهر بالأصفر غالباً)
                 warn!(symbol = %r_symbol, price = %candle.close, "🔥 Candle CLOSED");
                 let _: redis::RedisResult<()> = r_conn.lpush(format!("{}_Close_Candle", r_symbol), "Closed").await;
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
//  5. Historical Data Logic
// =================================================================================

async fn init_historical_data(symbols: &[String], db_candle: &mongodb::Database, db_indicitors: &mongodb::Database) {
    let client = reqwest::Client::new();
    let semaphore = Arc::new(Semaphore::new(8)); 
    let mut handles = Vec::new();

    info!("📥 Fetching history for {} symbols...", symbols.len());

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
                                let col_candle: Collection<mongodb::bson::Document> = db_candle.collection(&symbol);
                                let _ = col_candle.delete_many(doc! {}, None).await; 
                                let _ = col_candle.insert_many(candle_docs, None).await;

                                let hl_points = detect_historical_hl(&raw_candles);
                                if !hl_points.is_empty() {
                                    let hl_docs: Vec<mongodb::bson::Document> = hl_points.into_iter().map(|p| {
                                        doc! {
                                            "Open_time": DateTime::from_millis(p.open_time),
                                            "Price": p.price,
                                            "Type": p.hl_type,
                                            "Side": p.side
                                        }
                                    }).collect();
                                    let col_ind: Collection<mongodb::bson::Document> = db_indicitors.collection(&symbol);
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
    info!("🏁 All historical data tasks finished.");
}

// =================================================================================
//  6. Algorithm
// =================================================================================

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
                hl_type: "High".to_string(),
                side: "Top".to_string(),
            });
        }
        if current.3 < prev1.3 && current.3 < prev2.3 && current.3 < next1.3 && current.3 < next2.3 {
            points.push(HLPoint {
                open_time: current.0,
                price: current.3,
                hl_type: "Low".to_string(),
                side: "Bottom".to_string(),
            });
        }
    }
    points
}

async fn get_history(Path(symbol): Path<String>, State(db): State<mongodb::Database>) -> Json<Vec<serde_json::Value>> {
    let collection = db.collection::<mongodb::bson::Document>(&symbol);
    // نأخذ 500 شمعة
    let options = mongodb::options::FindOptions::builder()
        .sort(mongodb::bson::doc! { "Open_time": -1 })
        .limit(500)
        .build();

    let mut cursor = collection.find(mongodb::bson::doc! {}, options).await.unwrap();
    let mut history = Vec::new();

    while let Ok(Some(doc)) = cursor.try_next().await {
        // تحويل التاريخ من BSON DateTime إلى Seconds (i64)
        let open_time = doc.get_datetime("Open_time").unwrap();
        let timestamp_seconds = open_time.timestamp_millis() / 1000;

        let candle = serde_json::json!({
            "time": timestamp_seconds as i64, // يجب أن يكون رقماً صحيحاً
            "open": doc.get_f64("Open").unwrap_or(0.0),
            "high": doc.get_f64("High").unwrap_or(0.0),
            "low": doc.get_f64("Low").unwrap_or(0.0),
            "close": doc.get_f64("Close").unwrap_or(0.0),
        });
        history.push(candle);
    }
    
    // هام جداً: الترتيب يجب أن يكون من الأقدم (أصغر رقم وقت) إلى الأحدث
    history.sort_by_key(|c| c["time"].as_i64().unwrap());
    
    Json(history)
}

