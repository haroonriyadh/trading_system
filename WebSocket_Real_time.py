from Database import db_candle,Redis
from symbols import symbols
import json
import logging
from datetime import datetime
import websocket

logging.basicConfig(filename='logfile_multi_kline.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')

interval = 1
# بناء قائمة المواضيع (topics) للاشتراك
topics = [f"kline.{interval}.{symbol}" for symbol in symbols]

def on_message(ws,message):
    data = json.loads(message)
    candle = data['data'][0]
    # استخراج اسم الرمز من topic
    symbol = data['topic'].split(".")[-1]
    candle_obj = {
        "Open_time": datetime.fromtimestamp(int(candle['start'])/1000),
        "Open": float(candle["open"]),
        "High": float(candle["high"]),
        "Low": float(candle["low"]),
        "Close": float(candle["close"]),
        "Volume": float(candle["volume"]),
        "Close_time": datetime.fromtimestamp(int(candle['end'])/1000)

    }
    # تحديث Redis
    try:
        Redis.set(symbol, json.dumps(candle_obj,default=str))
    except Exception as e:
        print(e)
        pass

    # حفظ الشمعة المكتملة في Mongo
    if candle["confirm"]:
        try:
            db_candle[symbol].insert_one(candle_obj)
        except Exception as e:
            print(e)
            pass

    print(f"{symbol} | Time: {datetime.fromtimestamp(int(candle['timestamp'])/1000)} ,Open: {candle['open']}, High: {candle['high']}, Low: {candle['low']}, Close: {candle['close']}, Volume: {candle['volume']}")
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
