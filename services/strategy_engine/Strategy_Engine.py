import asyncio
import datetime
import json
import time
from types import NoneType
import numpy as np
from Order_Block import OrderBlock_Detector
from shared.symbols_loader import symbols
from telegram_bot import send_telegram_message
import traceback
from shared.database import (
    db_candle,
    db_OB, 
    db_Orders,
    init_redis,
    Get_Candlestick,
    Nearest_OB_Long,
    Nearest_OB_Short,
    json_deserialize,
    json_serialize
)




# حالة أخيرة لكل symbol لمنع التكرار
last_ob_in_symbols = {symbol: None for symbol in symbols}

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

        if isinstance(msg["data"], str):
            data = json_deserialize(json.loads(msg["data"]))

            # جلب أقرب OB محفوظ في Redis
            NearestLong = await Redis.get(f"{symbol}_Nearest_Order_Block_Long")
            NearestShort = await Redis.get(f"{symbol}_Nearest_Order_Block_Short")

            if isinstance(NearestLong,str):
                
                NearestLong = json_deserialize(json.loads(NearestLong))

                if data["Close"] <= NearestLong["Entry_Price"]:
                    await Redis.lpush(f"{symbol}_Open_Long_Position", json.dumps(json_serialize(NearestLong)))
                    print(f"{symbol} Price has Mitigate Bullish Order Block at {NearestLong['Entry_Price']}")
                    await db_OB[symbol].update_many(
                        {"Open_time": NearestLong["Open_time"]},
                        {"$set": {"Close_time": data["Open_time"], "Mitigated": 1}}
                    )

                    
                    nearestlong = await Nearest_OB_Long(symbol, data["Close"])
                    if isinstance(nearestlong,dict):
                        # استخدم $set عند التحديث
                        await Redis.set(f"{symbol}_Nearest_Order_Block_Long", json.dumps(json_serialize(nearestlong)))
                        await send_telegram_message(
                            f"Price {symbol} has Mitigate Bullish Order Block at {NearestLong['Entry_Price']}\n\n"
                            f"The Nearest Bullish Order Block is:\nTime : {nearestlong['Open_time']}\n"
                            f"Entry_Price : {nearestlong['Entry_Price']}\nStop_Loss : {nearestlong['Stop_Loss']}"
                        )


                    elif isinstance(nearestlong,NoneType):
                        await Redis.delete(f"{symbol}_Nearest_Order_Block_Long")
                        await send_telegram_message(
                            f"Price {symbol} has Mitigate Bullish Order Block at {NearestLong['Entry_Price']}\n\n"
                            f"There Is No Bullish Order Block Below The Current Price."
                        )



            if isinstance(NearestShort,str):
                
                NearestShort = json_deserialize(json.loads(NearestShort))
                
                if data["Close"] >= NearestShort["Entry_Price"]:   
                    await Redis.lpush(f"{symbol}_Open_Short_Position", json.dumps(json_serialize(NearestShort)))             
                    print(f"[{symbol}] Price has Mitigate Bearish Order Block at {NearestShort['Entry_Price']}")
                    await db_OB[symbol].update_many(
                        {"Open_time": NearestShort["Open_time"]},
                        {"$set": {"Close_time": data["Open_time"], "Mitigated": 1}}
                    )
                    
                    nearestshort = await Nearest_OB_Short(symbol, data["Close"])
                    if isinstance(nearestshort,dict):
                        await Redis.set(f"{symbol}_Nearest_Order_Block_Short", json.dumps(json_serialize(nearestshort)))
                        await send_telegram_message(
                            f"Price {symbol} has Mitigate Bearish Order Block at {NearestShort['Entry_Price']}\n\n"
                            f"The Nearest Bearish Order Block is:\nTime : {nearestshort['Open_time']}\n"
                            f"Entry_Price : {nearestshort['Entry_Price']}\nStop_Loss : {nearestshort['Stop_Loss']}"
                        )
                    
                    elif isinstance(nearestshort,NoneType):
                        await Redis.delete(f"{symbol}_Nearest_Order_Block_Short")
                        await send_telegram_message(
                            f"Price {symbol} has Mitigate Bearish Order Block at {NearestShort['Entry_Price']}\n\n"
                            f"There Is No Bearish Order Block Above The Current Price."
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
        tasks.append(
            asyncio.create_task(
                worker_wrapper(
                    detect_order_block,sym
                )
            )
        )

        tasks.append(
            asyncio.create_task(
                worker_wrapper(
                    Signals, sym
                )
            )
        )

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())