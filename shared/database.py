import os
from datetime import datetime
import redis.asyncio as redis
import numpy as np
from motor.motor_asyncio import AsyncIOMotorClient

# -------------------
# MongoDB Async
# -------------------

MONGO_HOST = os.getenv("MONGO_HOST", "mongo")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))

mongo_client = AsyncIOMotorClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
db_candle = mongo_client['CandleStick_data']
db_OB = mongo_client['Order_Block']
db_Orders = mongo_client['Open_Orders']
db_indicitors = mongo_client['Indicitors']

# -------------------
# Redis Async
# -------------------

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

Redis = None

async def init_redis():
    global Redis
    if Redis is None:
        Redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return Redis

async def Get_CandleStick(symbol: str, limit: int) -> np.ndarray:
    # 1. طلب الحقول المحددة فقط + الترتيب العكسي لاستغلال الفهرس
    cursor = db_candle[symbol].find(
        {}, 
        {"_id": 0, "Open_time": 1, "Open": 1, "High": 1, "Low": 1, "Close": 1}
    ).sort("Open_time", -1).limit(limit).to_list()
    print(cursor)
    # 2. بناء القائمة يدوياً (أسرع من Loop) ثم قلب الترتيب
    return np.array([
        [c["Open_time"], c["Open"], c["High"], c["Low"], c["Close"]] 
        for c in await cursor
    ], dtype=object)[::-1]


async def Get_HL_Points(symbol: str, limit: int) -> np.ndarray:
    cursor = db_indicitors[symbol].find(
        {}, 
        {"_id": 0, "Open_time": 1, "Price": 1, "Type": 1}
    ).sort("Open_time", -1).limit(limit).to_list()
    print(cursor)
    return np.array([
        [c["Open_time"], c["Price"], c["Type"]] 
        for c in await cursor
    ], dtype=object)[::-1]


# -------------------
# JSON Helpers
# -------------------

def json_serialize(d):
    return {kk: (vv.isoformat() if isinstance(vv, datetime) else vv) for kk, vv in d.items()}

def json_deserialize(d):
    return {kk: (datetime.fromisoformat(vv) if kk in ['Start_Time','End_Time', 'Open_time','Close_time'] else vv) for kk, vv in d.items()}

