use futures::{StreamExt, SinkExt};
use mongodb::{
    options::ClientOptions,
    Client,
    Collection,
    IndexModel,
    bson::{doc, DateTime, Document}
};
use redis::{AsyncCommands, Pipeline};
use serde::{Deserialize, Deserializer};
use std::{sync::Arc, time::Duration, collections::HashMap};
use tokio::sync::{mpsc, Semaphore};
use tokio::time::{interval, timeout};
use tokio_tungstenite::tungstenite::protocol::Message;
use tracing::{warn, error, info, debug};

// =================================================================================
//  1. Data Structures & Types
// =================================================================================

// استخدام Arc<str> لتقليل الـ Allocations للرموز المتكررة
type Symbol = Arc<str>;

#[derive(Debug, Deserialize)]
struct BybitMsg {
    topic: String,
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
}

// الهيكل الداخلي الذي يتم تمريره عبر القنوات (Channel)
#[derive(Debug, Clone)]
struct ProcessedCandle {
    symbol: Symbol,
    doc: Document,      // BSON Document for Mongo
    json: String,       // Pre-serialized JSON for Redis
    is_confirm: bool,
    close_price: f64,
}

#[derive(Debug, Clone)]
struct HLPoint {
    open_time: i64,
    price: f64,
    hl_type: i32 // 0: Low, 1: High
}

fn parse_f64_from_str<'de, D>(deserializer: D) -> Result<f64, D::Error>
where
    D: Deserializer<'de>,
{
    let s: &str = Deserialize::deserialize(deserializer)?;
    s.parse::<f64>().map_err(serde::de::Error::custom)
}

// =================================================================================
//  2. Main Entry Point
// =================================================================================

#[tokio::main]
async fn main() {
    // 1. Initialize High-Performance Logger
    tracing_subscriber::fmt()
        .with_env_filter("info")
        .with_thread_ids(true)
        .init();

    // 2. Configuration & Connections
    let mongo_host = std::env::var("MONGO_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let redis_host = std::env::var("REDIS_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());

    // Mongo Setup (Optimized Connection Pool)
    let mongo_url = format!("mongodb://{}:27017", mongo_host);
    let mut client_options = ClientOptions::parse(&mongo_url).await.unwrap();
    client_options.min_pool_size = Some(5);  // Keep connections warm
    client_options.max_pool_size = Some(50); // Handle bursts
    let mongo_client = Client::with_options(client_options).unwrap();
    
    let db_candle = mongo_client.database("CandleStick_data");
    let db_indicators = mongo_client.database("Indicitors");

    // Redis Setup
    let redis_url = format!("redis://{}:6379/", redis_host);
    let redis_client = redis::Client::open(redis_url).unwrap();
    let redis_conn = redis_client.get_multiplexed_async_connection().await.unwrap();

    // 3. Load Symbols
    let symbols = load_symbols_from_json().await;
    if symbols.is_empty() {
        error!("❌ No symbols found. Exiting.");
        return;
    }
    // Convert to Arc<str> for cheap cloning
    let arc_symbols: Vec<Symbol> = symbols.iter().map(|s| Arc::from(s.as_str())).collect();

    // 4. Background Task: Historical Data (The "Cold" Path)
    // Run this independently so it doesn't block the real-time feed startup
    let symbols_hist = symbols.clone();
    let db_c_hist = db_candle.clone();
    let db_i_hist = db_indicators.clone();
    
    tokio::spawn(async move {
        init_historical_data(symbols_hist, db_c_hist, db_i_hist).await;
    });

    // 5. Setup Channels (Actor Pattern)
    // Buffer size 50,000 ensures we can handle massive spikes without blocking WS
    let (tx_processing, rx_processing) = mpsc::channel::<ProcessedCandle>(50_000);

    // 6. Spawn Processor Task (The "Consumer")
    let db_candle_clone = db_candle.clone();
    let redis_conn_clone = redis_conn.clone();
    
    tokio::spawn(async move {
        data_processor_loop(rx_processing, db_candle_clone, redis_conn_clone).await;
    });

    // 7. WebSocket Loop (The "Producer" - Hot Path)
    let ws_url = "wss://stream.bybit.com/v5/public/linear";
    let sub_chunks: Vec<_> = arc_symbols.chunks(10).collect(); // Batch subscriptions

    info!("🚀 System initialized. Starting WebSocket loop...");

    loop {
        info!("🔌 Connecting to Bybit WS...");
        match tokio_tungstenite::connect_async(ws_url).await {
            Ok((mut ws_stream, _)) => {
                info!("✅ WS Connected.");

                // Send Subscriptions
                for chunk in &sub_chunks {
                    let topics: Vec<String> = chunk.iter().map(|s| format!("kline.1.{}", s)).collect();
                    let subscribe_msg = serde_json::json!({"op":"subscribe","args":topics});
                    if let Err(e) = ws_stream.send(Message::Text(subscribe_msg.to_string())).await {
                        error!("❌ Subscription error: {:?}", e);
                        break;
                    }
                }

                let mut ping_interval = interval(Duration::from_secs(20));

                loop {
                    tokio::select! {
                        msg_opt = ws_stream.next() => {
                            match msg_opt {
                                Some(Ok(Message::Text(txt))) => {
                                    // Parse and forward to processor channel immediately
                                    process_raw_msg(&txt, &tx_processing).await;
                                }
                                Some(Ok(Message::Pong(_))) => { /* Heartbeat */ }
                                Some(Ok(Message::Close(_))) => { warn!("⚠️ WS Close frame"); break; }
                                Some(Err(e)) => { error!("WS Error: {:?}", e); break; }
                                None => { warn!("⚠️ WS Stream ended"); break; }
                                _ => {}
                            }
                        }
                        _ = ping_interval.tick() => {
                            if let Err(_) = ws_stream.send(Message::Ping(vec![])).await {
                                break;
                            }
                        }
                    }
                }
            }
            Err(e) => {
                error!("❌ WS Connection failed: {:?}. Retry in 5s...", e);
                tokio::time::sleep(Duration::from_secs(5)).await;
            }
        }
    }
}

// =================================================================================
//  3. The "Hot Path" Parser
// =================================================================================

#[inline(always)]
async fn process_raw_msg(msg: &str, tx: &mpsc::Sender<ProcessedCandle>) {
    let parsed: Result<BybitMsg, _> = serde_json::from_str(msg);

    match parsed {
        Ok(parsed) => {
            if parsed.data.is_empty() { return; }

            // Efficient string slicing to get symbol
            let topic_str = parsed.topic.as_str();
            let symbol_str = if topic_str.starts_with("kline.1.") {
                &topic_str[8..]
            } else {
                topic_str
            };
            let symbol: Symbol = Arc::from(symbol_str);

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

                let p_candle = ProcessedCandle {
                    symbol: symbol.clone(),
                    doc,
                    json: json_str,
                    is_confirm: candle.confirm,
                    close_price: candle.close,
                };

                // Non-blocking send (wait only if buffer full)
                if let Err(_) = tx.send(p_candle).await {
                    error!("Processor channel closed!");
                    return;
                }
            }
        }
        Err(e) => {
             // Only log parse errors that are actual errors (not ping/pong text)
             if !msg.contains("success") && !msg.contains("op") {
                 debug!("Parse warning: {:?} | Msg: {}", e, msg);
             }
        }
    }
}

// =================================================================================
//  4. The "Worker" (Batching & Pipelining)
// =================================================================================

async fn data_processor_loop(
    mut rx: mpsc::Receiver<ProcessedCandle>,
    db: mongodb::Database,
    mut redis_conn: redis::aio::MultiplexedConnection
) {
    // Buffer for MongoDB Batch Insert: Map<Symbol, Vec<Document>>
    let mut mongo_buffer: HashMap<Symbol, Vec<Document>> = HashMap::new();
    
    // Flush interval allows batching inserts instead of 1-by-1
    let mut flush_interval = interval(Duration::from_millis(300)); 

    loop {
        tokio::select! {
            Some(candle) = rx.recv() => {
                // --- Redis Pipelining (Low Latency) ---
                let mut pipe = redis::pipe();
                let rt_channel = format!("{}_RealTime", candle.symbol);
                pipe.publish(&rt_channel, &candle.json);

                if candle.is_confirm {
                    let close_channel = format!("{}_Close_Candle", candle.symbol);
                    pipe.publish(&close_channel, &candle.json);
                    
                    // Add to Mongo Buffer ONLY if confirmed
                    mongo_buffer.entry(candle.symbol.clone())
                        .or_insert_with(Vec::new)
                        .push(candle.doc);
                        
                    // Log significant events
                    debug!("🔥 {} Closed: {}", candle.symbol, candle.close_price);
                }

                // Execute Redis Pipeline async
                let _: redis::RedisResult<()> = pipe.query_async(&mut redis_conn).await;
            }

            _ = flush_interval.tick() => {
                // --- Mongo Bulk Insert (Throughput) ---
                if !mongo_buffer.is_empty() {
                    for (symbol, docs) in mongo_buffer.drain() {
                        if docs.is_empty() { continue; }
                        
                        let collection = db.collection::<Document>(&symbol);
                        
                        // Spawn insert task to prevent blocking the Redis loop
                        tokio::spawn(async move {
                            if let Err(e) = collection.insert_many(docs, None).await {
                                error!("❌ Mongo flush failed for {}: {:?}", symbol, e);
                            }
                        });
                    }
                }
            }
        }
    }
}

// =================================================================================
//  5. Historical Data & Algorithms (The "Cold" Path)
// =================================================================================

async fn init_historical_data(
    symbols: Vec<String>, 
    db_candle: mongodb::Database, 
    db_indicators: mongodb::Database
) {
    info!("📚 Starting Historical Sync for {} symbols...", symbols.len());

    // Reuse HTTP Client for connection pooling
    let http_client = reqwest::Client::builder()
        .pool_idle_timeout(Duration::from_secs(15))
        .pool_max_idle_per_host(10)
        .build()
        .unwrap();

    // Limit concurrency to avoid Rate Limits (e.g., 10 concurrent requests)
    let semaphore = Arc::new(Semaphore::new(10));
    let mut handles = Vec::new();

    for symbol in symbols {
        let sem = semaphore.clone();
        let client = http_client.clone();
        let db_c = db_candle.clone();
        let db_i = db_indicators.clone();
        
        handles.push(tokio::spawn(async move {
            let _permit = sem.acquire().await.unwrap();
            
            // Ensure index exists first
            ensure_index(&db_c, &symbol).await;

            let url = format!(
                "https://api.bybit.com/v5/market/kline?category=linear&symbol={}&interval=1&limit=200",
                symbol
            );

            match client.get(&url).send().await {
                Ok(resp) => {
                    if let Ok(json) = resp.json::<serde_json::Value>().await {
                         process_history_json(&symbol, json, &db_c, &db_i).await;
                    }
                }
                Err(e) => error!("❌ History fetch failed for {}: {:?}", symbol, e),
            }
        }));
    }

    futures::future::join_all(handles).await;
    info!("✅ All Historical Data Synced.");
}

async fn ensure_index(db: &mongodb::Database, symbol: &str) {
    let model = IndexModel::builder().keys(doc! { "Open_time": -1 }).build();
    let col: Collection<Document> = db.collection(symbol);
    let _ = col.create_index(model, None).await;
}

async fn process_history_json(
    symbol: &str, 
    json: serde_json::Value, 
    db_c: &mongodb::Database, 
    db_i: &mongodb::Database
) {
    if let Some(list) = json.get("result").and_then(|r| r.get("list")).and_then(|l| l.as_array()) {
        let mut candle_docs = Vec::with_capacity(list.len());
        let mut raw_candles = Vec::with_capacity(list.len());

        for item in list {
            if let Some(c) = item.as_array() {
                // Safe parsing defaults
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

            // Bulk Insert Candles
            let col_c: Collection<Document> = db_c.collection(symbol);
            let _ = col_c.delete_many(doc! {}, None).await; // Clear old
            let _ = col_c.insert_many(candle_docs, None).await;

            // Detect & Insert HL
            let hl_points = detect_historical_hl(&raw_candles);
            if !hl_points.is_empty() {
                let hl_docs: Vec<Document> = hl_points.into_iter().map(|p| {
                    doc! {
                        "Open_time": DateTime::from_millis(p.open_time),
                        "Price": p.price,
                        "Type": p.hl_type
                    }
                }).collect();

                let col_i: Collection<Document> = db_i.collection(symbol);
                let _ = col_i.delete_many(doc! {}, None).await; // Clear old
                let _ = col_i.insert_many(hl_docs, None).await;
            }
        }
    }
}

// Pure function, zero copy on input
fn detect_historical_hl(candles: &[(i64, f64, f64, f64, f64)]) -> Vec<HLPoint> {
    let mut points = Vec::new();
    if candles.len() < 5 { return points; }

    for window in candles.windows(5) {
        let prev2 = window[0];
        let prev1 = window[1];
        let current = window[2];
        let next1 = window[3];
        let next2 = window[4];

        // Swing High
        if current.2 > prev1.2 && current.2 > prev2.2 && current.2 > next1.2 && current.2 > next2.2 {
            points.push(HLPoint { open_time: current.0, price: current.2, hl_type: 1 });
        }
        // Swing Low
        if current.3 < prev1.3 && current.3 < prev2.3 && current.3 < next1.3 && current.3 < next2.3 {
            points.push(HLPoint { open_time: current.0, price: current.3, hl_type: 0 });
        }
    }
    points
}

// =================================================================================
//  6. Utilities
// =================================================================================

async fn load_symbols_from_json() -> Vec<String> {
    let paths = vec![
        "shared/symbols.json",
        "../shared/symbols.json",
        "symbols.json"
    ];

    for p in paths {
        if let Ok(c) = tokio::fs::read_to_string(p).await {
            if let Ok(parsed) = serde_json::from_str::<Vec<String>>(&c) {
                return parsed;
            }
        }
    }
    // Fallback if file missing
    warn!("⚠️ Symbols file not found, defaulting to BTCUSDT");
    vec!["BTCUSDT".to_string()] 
}
