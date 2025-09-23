use tokio_tungstenite::tungstenite::protocol::Message;
use tokio::sync::broadcast;
use futures_util::{StreamExt, SinkExt};
use serde_json::Value;
use mongodb::{options::ClientOptions, Client, Collection, bson::{doc, DateTime}};
use redis::AsyncCommands;
use std::sync::Arc;

#[tokio::main]
async fn main() {
    // ------------------- MongoDB -------------------
    let client_options = ClientOptions::parse("mongodb://mongo:27017").await.unwrap();
    let mongo_client = Client::with_options(client_options).unwrap();
    let db_candle = Arc::new(mongo_client.database("CandleStick_data"));

    // ------------------- Redis -------------------
    let redis_client = redis::Client::open("redis://redis:6379/").unwrap();
    
    // تعريف Redis connection
    let redis_conn = redis_client.get_async_connection().await.unwrap();
    let redis_conn = Arc::new(tokio::sync::Mutex::new(redis_conn));

    // ------------------- Broadcast Channel -------------------
    let (tx, _) = broadcast::channel::<String>(100);

    // ------------------- Bybit WebSocket Client -------------------
    let symbols = vec!["BTCUSDT", "ETHUSDT"]; // يمكنك إضافة المزيد بسهولة
    let url = "wss://stream.bybit.com/v5/public/linear";

    tokio::spawn({
        let db_candle = db_candle.clone();
        let redis_conn = redis_conn.clone();
        let tx_bybit = tx.clone();
        let topics: Vec<String> = symbols.iter().map(|s| format!("kline.1.{}", s)).collect();

        async move {
            loop {
                match tokio_tungstenite::connect_async(url).await {
                    Ok((mut ws_stream, _)) => {
                        let subscribe_msg = serde_json::json!({
                            "op": "subscribe",
                            "args": topics
                        });
                        ws_stream.send(Message::Text(subscribe_msg.to_string())).await.unwrap();

                        while let Some(Ok(msg)) = ws_stream.next().await {
                            if let Message::Text(txt) = msg {
                                handle_message(&txt, &tx_bybit, &db_candle, &redis_conn).await;
                            }
                        }
                    }
                    Err(e) => {
                        eprintln!("WebSocket error: {:?}", e);
                        tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
                    }
                }
            }
        }
    }).await.unwrap();
}

// ------------------- Handle Bybit Message -------------------
async fn handle_message(msg: &str, tx: &broadcast::Sender<String>, db: &Arc<mongodb::Database>, redis_conn: &Arc<tokio::sync::Mutex<redis::aio::Connection>>) {
    let v: Value = match serde_json::from_str(msg) {
        Ok(val) => val,
        Err(e) => {
            eprintln!("JSON parse error: {:?}", e);
            return;
        }
    };

    if let Some(data_arr) = v.get("data").and_then(|d| d.as_array()) {
        if data_arr.is_empty() { return; }

        let symbol = v.get("topic")
            .and_then(Value::as_str)
            .map(|s| s.split('.').last().unwrap_or(s))
            .unwrap_or("");

        for candle in data_arr {
            let open = candle.get("open").and_then(|v| v.as_str()).unwrap_or("0").parse::<f32>().unwrap_or(0.0);
            let high = candle.get("high").and_then(|v| v.as_str()).unwrap_or("0").parse::<f32>().unwrap_or(0.0);
            let low = candle.get("low").and_then(|v| v.as_str()).unwrap_or("0").parse::<f32>().unwrap_or(0.0);
            let close = candle.get("close").and_then(|v| v.as_str()).unwrap_or("0").parse::<f32>().unwrap_or(0.0);
            let volume = candle.get("volume").and_then(|v| v.as_str()).unwrap_or("0").parse::<f32>().unwrap_or(0.0);
            let start_ts = candle.get("start").and_then(|v| v.as_i64()).unwrap_or(0);
            let end_ts = candle.get("end").and_then(|v| v.as_i64()).unwrap_or(0);
            let timestamp = candle.get("timestamp").and_then(|v| v.as_i64()).unwrap_or(0);
            let confirm = candle.get("confirm").and_then(|v| v.as_bool()).unwrap_or(false);

            let doc = doc! {
                "Open_time": DateTime::from_millis(start_ts),
                "Open": open,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": volume,
                "Close_time": DateTime::from_millis(end_ts),
            };

            if confirm {
                let collection: Collection<mongodb::bson::Document> = db.collection(symbol);
                let _ = collection.insert_one(doc.clone(), None).await;

                let mut conn = redis_conn.lock().await;
                let _: redis::RedisResult<i16> = conn.lpush(format!("{}_Close_Candle", symbol), "Closed").await;

            }

            let json_str = serde_json::to_string(&doc).unwrap();
            let _ = tx.send(json_str.clone());


            let mut conn = redis_conn.lock().await;
            let _: redis::RedisResult<i16> = conn.publish(format!("{}_RealTime", symbol), json_str).await;


            println!("{:?} | Time: {}, Open: {}, High: {}, Low: {}, Close: {}, Volume: {}", symbol, DateTime::from_millis(timestamp), open, high, low, close, volume);
        }
    }
}
