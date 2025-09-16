from Database import db_candle,Redis,json_serialize
from symbols import symbols
import json
import logging
from datetime import datetime
import websocket


logging.basicConfig(filename='logfile_multi_kline.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s %(message)s')

#Time Frames
intervals = [1]

# بناء قائمة المواضيع (topics) للاشتراك
topics = [f"kline.{interval}.{symbol}" for symbol in symbols for interval in intervals]


def on_message(ws,message):
    data = json.loads(message)
    
    candle_obj = {
        "Open_time": datetime.fromtimestamp(int(data["data"][0]["start"])/1000),
        "Open": float(data["data"][0]["open"]),
        "High": float(data["data"][0]["high"]),
        "Low": float(data["data"][0]["low"]),
        "Close": float(data["data"][0]["close"]),
        "Volume": float(data["data"][0]["volume"]),
        "Close_time": datetime.fromtimestamp(int(data["data"][0]["end"])/1000)
    }

    # تحديث Redis أولاً
    Redis.publish(f"{data['topic'].split(".")[-1]}_RealTime", json.dumps(json_serialize(candle_obj)))

    # حفظ الشمعة المكتملة في Mongo
    if data['data'][0]["confirm"]:
        db_candle[data['topic'].split(".")[-1]].insert_one(candle_obj)
        
        # إرسال إشعار إغلاق الشمعة
        Redis.lpush(f"{data['topic'].split(".")[-1]}_Close_Candle", "Closed")

    print(f"{data['topic'].split(".")[-1]} | Time: {datetime.fromtimestamp(int(data["data"][0]["timestamp"])/1000)} ,Open: {candle_obj["Open"]}, High: {candle_obj["High"]}, Low: {candle_obj["Low"]}, Close: {candle_obj["Close"]}, Volume: {candle_obj["Volume"]}")
    print("-" * 60)


def on_error(_ws, error):
    print('⚠️ WebSocket Error:', error)


def on_close(_ws, close_status_code, close_msg):
    print("### WebSocket Closed ###", close_status_code, close_msg)


def on_open(ws):
    print(f'✅ WebSocket Opened in {datetime.now()}')
    sub_msg = {"op": "subscribe", "args": topics}
    ws.send(json.dumps(sub_msg))
    print(f"Subscribed to: {topics}")


def on_pong(_ws, *data):
    print('pong received', datetime.now())


def on_ping(_ws, *data):
    print("ping received at", datetime.now())


def connWS():
    ws = websocket.WebSocketApp(
        "wss://stream.bybit.com/v5/public/linear",   # Spot
        # إذا أردت العقود (Linear): "wss://stream.bybit.com/v5/public/linear"
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_ping=on_ping,
        on_pong=on_pong,
        on_open=on_open
    )
    ws.run_forever(ping_interval=60, ping_timeout=10)


if __name__ == "__main__":
    websocket.enableTrace(False)  # اجعلها True لو تريد تتبع كل الأحداث
    connWS()
