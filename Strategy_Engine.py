import json
import time
import threading
from types import NoneType
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from Database import (
    db_candle, db_OB, db_Orders, Redis,
    Nearest_OB_Long, Nearest_OB_Short,
    json_deserialize, json_serialize
)
from Order_Block import OrderBlock_Detector
from symbols import symbols
from telegram_bot import send_telegram_message
import traceback


# حالة أخيرة لكل symbol لمنع التكرار
last_ob_in_symbols = {symbol: None for symbol in symbols}


def Get_CandelStick(symbol: str, limit: int) -> np.ndarray:
    cursor = db_candle[symbol].aggregate(
        [{"$project": {"_id": 0}}, {"$sort": {"Open_time": -1}}]
    ).to_list(limit)

    return np.array([[c.get(col) for col in ["Open_time", "Open", "High", "Low", "Close"]] for c in cursor], dtype=object)[::-1]


def detect_order_block(symbol):
    """Worker يستمع لإشعار إغلاق شمعة ويبحث عن Order Block."""
    while True:
        #try:
            # انتظار إشعار إغلاق شمعة (blocking)
            Redis.brpop(f"{symbol}_Close_Candle", 0)

            candles = Get_CandelStick(symbol, 7)
            if len(candles) < 6:
                print(f"[{symbol}] Not enough candles: {len(candles)}/6")
                continue

            OB = OrderBlock_Detector(candles, "1m", 1000)

            if isinstance(OB, dict) and OB["Open_time"] != last_ob_in_symbols[symbol]:
                print(f"✅ System Find Order Block in {symbol} at {OB['Open_time']}")
                last_ob_in_symbols[symbol] = OB["Open_time"]
                Redis.set(f"{symbol}_Nearest_Order_Block_{OB['Side']}",json.dumps(json_serialize(OB)))
                db_OB[symbol].insert_one(OB)

            else:
                print(f"❌ System Not Find Order Block in {symbol}")

        #except Exception as e:
            #print(f"[detect_order_block] Exception for {symbol}: {e}", flush=True)
            #time.sleep(1)  # تأخير قبل إعادة المحاولة


def Signals(symbol):
    """Worker يستمع لتيّار RealTime ويتعامل مع nearest OB."""
    pubsub = Redis.pubsub()
    pubsub.subscribe(f"{symbol}_RealTime")

    for msg in pubsub.listen():
        try:

            data = msg["data"]
            if isinstance(data, bytes):
                data = json_deserialize(json.loads(data))


                # جلب أقرب OB محفوظ في Redis
                NearestLong = Redis.get(f"{symbol}_Nearest_Order_Block_Long")
                NearestShort = Redis.get(f"{symbol}_Nearest_Order_Block_Short")

                if isinstance(NearestLong,bytes):
                    NearestLong = json_deserialize(json.loads(NearestLong))
                    if data["Close"] <= NearestLong["Entry_Price"]:
                        print(f"{symbol} Price has Mitigate Order Block Long at {NearestLong['Entry_Price']}")
                        # استخدم $set عند التحديث
                        db_OB[symbol].update_many(
                            {"Open_time": NearestLong["Open_time"]},
                            {"$set": {"Close_time": data["Open_time"], "Mitigated": 1}}
                        )
                        nearestlong = Nearest_OB_Long(symbol, data["Close"])
                        if isinstance(nearestlong,dict):
                            Redis.set(f"{symbol}_Nearest_Order_Block_Long", json.dumps(json_serialize(nearestlong)))
                            send_telegram_message(
                                f"Price {symbol} has Mitigate Order Block Long at {NearestLong['Entry_Price']}\n\n"
                                f"The Nearest Order Block Long is:\nTime : {nearestlong['Open_time']}\n"
                                f"Entry_Price : {nearestlong['Entry_Price']}\nStop_Loss : {nearestlong['Stop_Loss']}"
                            )


                        elif isinstance(nearestlong,NoneType):
                            Redis.delete(f"{symbol}_Nearest_Order_Block_Long")
                            send_telegram_message(
                                f"Price {symbol} has Mitigate Order Block Long at {NearestLong['Entry_Price']}\n\n"
                                f"There is no Order Block Long below the Current Price."
                            )



                if isinstance(NearestShort,bytes):
                    NearestShort = json_deserialize(json.loads(NearestShort))
                    if data["Close"] >= NearestShort["Entry_Price"]:                
                        print(f"[{symbol}] Price has Mitigate Order Block Short at {NearestShort['Entry_Price']}")
                        db_OB[symbol].update_many(
                            {"Open_time": NearestShort["Open_time"]},
                            {"$set": {"Close_time": data["Open_time"], "Mitigated": 1}}
                        )
                        
                        nearestshort = Nearest_OB_Short(symbol, data["Close"])
                        if isinstance(nearestshort,dict):
                            Redis.set(f"{symbol}_Nearest_Order_Block_Short", json.dumps(json_serialize(nearestshort)))
                            send_telegram_message(
                                f"Price {symbol} has Mitigate Order Block Short at {NearestShort['Entry_Price']}\n\n"
                                f"The Nearest Order Block Short is:\nTime : {nearestshort['Open_time']}\n"
                                f"Entry_Price : {nearestshort['Entry_Price']}\nStop_Loss : {nearestshort['Stop_Loss']}"
                            )
                        
                        elif isinstance(nearestshort,NoneType):
                            Redis.delete(f"{symbol}_Nearest_Order_Block_Short")
                            send_telegram_message(
                                f"Price {symbol} has Mitigate Order Block Short at {NearestShort['Entry_Price']}\n\n"
                                f"There is no Order Block Short above the Current Price."
                            )


        except Exception as e:
            print(f"[Signals] Exception for {symbol}: {e}", flush=True)
            print(traceback.format_exc())  # يطبع كل التفاصيل + السطر

            # لا نخرج من الحلقة؛ نكمل الاستماع
            continue


def worker_wrapper(fn, symbol):
    """يغلف الworker بحيث يعيد التشغيل عند وقوع أي استثناء (سجل الخطأ ثم أعد المحاولة)."""
    while True:
        try:
            fn(symbol)
        except Exception as e:
            print(f"[worker_wrapper] {fn.__name__}({symbol}) crashed: {e}", flush=True)
            time.sleep(1)


if __name__ == "__main__":
    max_workers = max(4, len(symbols) * 2)  # ضمان رقم معقول
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # أرسل وركرز لكل symbol (detect + signal)
        for sym in symbols:
            executor.submit(worker_wrapper, detect_order_block, sym)
            executor.submit(worker_wrapper, Signals, sym)

        # إبقاء البرنامج شغّال بدون استخدام as_completed (لأن الworkers لا تنتهي)
        threading.Event().wait()  # بديل بسيط وآمن
