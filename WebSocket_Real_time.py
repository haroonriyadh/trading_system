from pybit.unified_trading import WebSocket
from Database import db_candle,db_OB,Redis
from datetime import datetime
import json
from symbols import symbols 


INTERVAL = 1

def make_handler(symbol):
    def handle_kline(msg):
        candle_obj = {
            "open_time": msg['data'][0]["start"],
            "open": float(msg['data'][0]["open"]),
            "high": float(msg['data'][0]["high"]),
            "low": float(msg['data'][0]["low"]),
            "close": float(msg['data'][0]["close"]),
            "volume": float(msg['data'][0]["volume"]),
                            }
        
        # تحديث الكاش (Redis)
        Redis.set(symbol, json.dumps(candle_obj))
        print(f"Symbol : {symbol} " ,Redis.get(symbol))

        # إذا اكتملت الشمعة
        if msg['data'][0]["confirm"]:
            print("Closed")
            # خزّن في Mongo
            db_candle[symbol].insert_one(candle_obj)


    return handle_kline


# إنشاء WebSocket
ws = WebSocket(testnet=False, channel_type="linear")

for symbol in symbols:
    make_handle = make_handler(symbol)

    ws.kline_stream(
        interval=INTERVAL,
        symbol=symbol,
        callback=make_handle
        )

while True:
    pass