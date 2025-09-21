from ast import Await
import asyncio
import datetime
import json
import time
import threading
from types import NoneType
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from Database import (
    db_candle, db_OB, db_Orders,init_redis,
    Nearest_OB_Long, Nearest_OB_Short,
    json_deserialize, json_serialize
)
from Order_Block import OrderBlock_Detector
from symbols import symbols
from telegram_bot import send_telegram_message
import traceback



# حالة أخيرة لكل symbol لمنع التكرار
last_ob_in_symbols = {symbol: None for symbol in symbols}


async def Get_CandelStick(symbol: str, limit: int) -> np.ndarray:
    cursor = await db_candle[symbol].aggregate(
        [{"$project": {"_id": 0}}, {"$sort": {"Open_time": -1}}]
    ).to_list(limit)

    return np.array([[c.get(col) for col in ["Open_time", "Open", "High", "Low", "Close"]] for c in cursor], dtype=object)[::-1]


async def detect_order_block(symbol):
    
    Redis = await init_redis()
    
    """Worker يستمع لإشعار إغلاق شمعة ويبحث عن Order Block."""
    while True:

        # انتظار إشعار إغلاق شمعة (blocking)
        await Redis.brpop(f"{symbol}_Close_Candle", 0)

        candles = await Get_CandelStick(symbol, 7)
        if len(candles) < 6:
            print(f"[{symbol}] Not enough candles: {len(candles)}/6")
            continue

        OB =  OrderBlock_Detector(candles, "1m", 1000)

        if isinstance(OB, dict) and OB["Open_time"] != last_ob_in_symbols[symbol]:
            print(f"{datetime.datetime.now()} | ✅ System Find Order Block in {symbol} at {OB['Open_time']}")
            last_ob_in_symbols[symbol] = OB["Open_time"]
            await Redis.set(f"{symbol}_Nearest_Order_Block_{OB['Side']}",json.dumps(json_serialize(OB)))
            await db_OB[symbol].insert_one(OB)

        else:
            print(f"{datetime.datetime.now()} | ❌ System Not Find Order Block in {symbol}")


async def Signals(symbol):
    """Worker يستمع لتيّار RealTime ويتعامل مع nearest OB."""
    Redis = await init_redis()
    pubsub = Redis.pubsub()
    await pubsub.subscribe(f"{symbol}_RealTime")

    async for msg in pubsub.listen():

            data =  msg["data"]
            if isinstance(data, bytes):
                data = json_deserialize(json.loads(data))


                # جلب أقرب OB محفوظ في Redis
                NearestLong = await Redis.get(f"{symbol}_Nearest_Order_Block_Long")
                NearestShort = await Redis.get(f"{symbol}_Nearest_Order_Block_Short")

                if isinstance(NearestLong,bytes):
                    NearestLong = json_deserialize(json.loads(NearestLong))
                    if data["Close"] <= NearestLong["Entry_Price"]:
                        print(f"{symbol} Price has Mitigate Order Block Long at {NearestLong['Entry_Price']}")
                        # استخدم $set عند التحديث
                        await db_OB[symbol].update_many(
                            {"Open_time": NearestLong["Open_time"]},
                            {"$set": {"Close_time": data["Open_time"], "Mitigated": 1}}
                        )
                        nearestlong = await Nearest_OB_Long(symbol, data["Close"])
                        if isinstance(nearestlong,dict):
                            await Redis.set(f"{symbol}_Nearest_Order_Block_Long", json.dumps(json_serialize(nearestlong)))
                            await send_telegram_message(
                                f"Price {symbol} has Mitigate Order Block Long at {NearestLong['Entry_Price']}\n\n"
                                f"The Nearest Order Block Long is:\nTime : {nearestlong['Open_time']}\n"
                                f"Entry_Price : {nearestlong['Entry_Price']}\nStop_Loss : {nearestlong['Stop_Loss']}"
                            )


                        elif isinstance(nearestlong,NoneType):
                            await Redis.delete(f"{symbol}_Nearest_Order_Block_Long")
                            await send_telegram_message(
                                f"Price {symbol} has Mitigate Order Block Long at {NearestLong['Entry_Price']}\n\n"
                                f"There is no Order Block Long below the Current Price."
                            )



                if isinstance(NearestShort,bytes):
                    NearestShort = json_deserialize(json.loads(NearestShort))
                    if data["Close"] >= NearestShort["Entry_Price"]:                
                        print(f"[{symbol}] Price has Mitigate Order Block Short at {NearestShort['Entry_Price']}")
                        await db_OB[symbol].update_many(
                            {"Open_time": NearestShort["Open_time"]},
                            {"$set": {"Close_time": data["Open_time"], "Mitigated": 1}}
                        )
                        
                        nearestshort = await Nearest_OB_Short(symbol, data["Close"])
                        if isinstance(nearestshort,dict):
                            await Redis.set(f"{symbol}_Nearest_Order_Block_Short", json.dumps(json_serialize(nearestshort)))
                            await send_telegram_message(
                                f"Price {symbol} has Mitigate Order Block Short at {NearestShort['Entry_Price']}\n\n"
                                f"The Nearest Order Block Short is:\nTime : {nearestshort['Open_time']}\n"
                                f"Entry_Price : {nearestshort['Entry_Price']}\nStop_Loss : {nearestshort['Stop_Loss']}"
                            )
                        
                        elif isinstance(nearestshort,NoneType):
                            await Redis.delete(f"{symbol}_Nearest_Order_Block_Short")
                            await send_telegram_message(
                                f"Price {symbol} has Mitigate Order Block Short at {NearestShort['Entry_Price']}\n\n"
                                f"There is no Order Block Short above the Current Price."
                            )





async def worker_wrapper(fn, symbol):
    """يغلف الworker بحيث يعيد التشغيل عند وقوع أي استثناء (سجل الخطأ ثم أعد المحاولة)."""
    while True:
        try:
           await fn(symbol)
        except Exception as e:
            print(traceback.format_exc())
            asyncio.sleep(5)


async def main():
    tasks = []
    for sym in symbols:
        tasks.append(asyncio.create_task(worker_wrapper(detect_order_block,sym)))
        tasks.append(asyncio.create_task(worker_wrapper(Signals, sym)))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())