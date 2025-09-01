from Database import db_candle,Redis
from pybit.unified_trading import WebSocket
from time import sleep
from symbols import symbols
import json

ws = WebSocket(
    testnet=True,
    channel_type="linear",
)
def handle_message(data):
    candle = data['data'][0]
    # استخراج اسم الرمز من topic
    symbol = data['topic'].split(".")[-1]
    candle_obj = {
        "open_time": candle["start"],
        "open": float(candle["open"]),
        "high": float(candle["high"]),
        "low": float(candle["low"]),
        "close": float(candle["close"]),
        "volume": float(candle["volume"]),
    }
    # تحديث Redis
    Redis.set(symbol, json.dumps(candle_obj))

    # حفظ الشمعة المكتملة في Mongo
    if candle["confirm"]:
        db_candle[symbol].insert_one(candle_obj)

    print(f"{symbol}: {candle_obj}")


ws.kline_stream(
    interval=1,
    symbol=symbols,
    callback=handle_message
)
while True:
    sleep(5)