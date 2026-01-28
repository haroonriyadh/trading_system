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
    """
    جلب بيانات الشموع بسرعة عالية جداً واستهلاك رام منخفض.
    يتم تحويل الوقت إلى timestamp لتكون المصفوفة كلها float64.
    """
    # استخدام find مع projection لتقليل البيانات المنقولة
    # الترتيب -1 يستفيد من الـ Index الموجود
    cursor = await db_candle[symbol].find(
        {}, 
        {"_id": 0, "Open_time": 1, "Open": 1, "High": 1, "Low": 1, "Close": 1}
    ).sort("Open_time", -1).to_list(length=limit)

    print(cursor)
    data = [
        [
            d["Open_time"], 
            d["Open"], 
            d["High"], 
            d["Low"], 
            d["Close"]
        ] 
        for d in cursor
    ][::-1]
    print(data)
    # استخدام float64 يوفر الذاكرة ويسرع العمليات الحسابية
    return np.array(data, dtype=object)

async def Get_HL_Points(symbol: str, limit: int) -> np.ndarray:
    """
    جلب نقاط High/Low.
    هنا نستخدم dtype=object لأن النوع Type عبارة عن نص (String).
    """
    cursor = await  db_indicitors[symbol].find(
        {}, 
        {"_id": 0, "Open_time": 1, "Price": 1, "Type": 1}
    ).sort("Open_time", -1).to_list(length=limit)

    print(cursor)
    # الترتيب الزمني: من الأقدم للأحدث
    return np.array([
        [d["Open_time"], d["Price"], d["Type"]] 
        for d in docs
    ], dtype=object)[::-1]

# -------------------
# JSON Helpers
# -------------------

def json_serialize(d):
    return {kk: (vv.isoformat() if isinstance(vv, datetime) else vv) for kk, vv in d.items()}

def json_deserialize(d):
    return {kk: (datetime.fromisoformat(vv) if kk in ['Start_Time','End_Time', 'Open_time','Close_time'] else vv) for kk, vv in d.items()}

