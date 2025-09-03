from Database import db_candle,Redis
from symbols import symbols
import json
import logging
from datetime import datetime
import websocket
import array
import struct



logging.basicConfig(filename='logfile_multi_kline.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s %(message)s')

interval = 1
# بناء قائمة المواضيع (topics) للاشتراك
topics = [f"kline.{interval}.{symbol}" for symbol in symbols]

def on_message(ws,message):
    data = json.loads(message)
    prices = array.array("f",[float(data['data'][0]["open"]),
                              float(data['data'][0]["high"]),
                              float(data['data'][0]["low"]),
                              float(data['data'][0]["close"]),
                              float(data['data'][0]["volume"])])
    
    time = array.array("q",[int(data['data'][0]["start"]),
                            int(data['data'][0]["end"])])
    
    candle_obj = {
        "Open_time": time[0],
        "Open": prices[0],
        "High": prices[1],
        "Low": prices[2],
        "Close": prices[3],
        "Volume": prices[4],
        "Close_time": time[1]
    }

    
    
    # تحديث Redis
    Redis.set(data['topic'].split(".")[-1], json.dumps(candle_obj,default=str))

    # حفظ الشمعة المكتملة في Mongo
    if data['data'][0]["confirm"]:
        db_candle[data['topic'].split(".")[-1]].insert_one(candle_obj)


    print(f"{data['topic'].split(".")[-1]} | Time: {datetime.fromtimestamp(time[0]/1000)} ,Open: {prices[0]}, High: {prices[1]}, Low: {prices[2]}, Close: {prices[3]}, Volume: {prices[4]}")
    print("-" * 60)

def on_error(ws, error):
    print('⚠️ WebSocket Error:', error)


def on_close(ws, close_status_code, close_msg):
    print("### WebSocket Closed ###", close_status_code, close_msg)


def on_open(ws):
    print('✅ WebSocket Opened')
    sub_msg = {"op": "subscribe", "args": topics}
    ws.send(json.dumps(sub_msg))
    print(f"Subscribed to: {topics}")


def on_pong(ws, *data):
    print('pong received')


def on_ping(ws, *data):
    now = datetime.now()
    print("ping received at", now.strftime("%H:%M:%S"))


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
    ws.run_forever(ping_interval=20, ping_timeout=10)


if __name__ == "__main__":
    websocket.enableTrace(False)  # اجعلها True لو تريد تتبع كل الأحداث
    connWS()
