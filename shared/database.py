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
    cursor = db_candle[symbol].find(
        {}, 
        {"_id": 0, "Open_time": 1, "Open": 1, "High": 1, "Low": 1, "Close": 1}
    ).sort("Open_time", -1).limit(limit)

    docs = await cursor.to_list(length=limit)

    if not docs:
        return np.empty((0, 5))

    # التحسين الجوهري للرام:
    # 1. تحويل Open_time من object إلى timestamp (float)
    # 2. إنشاء القائمة بترتيب: [Time, Open, High, Low, Close]
    # 3. عكس القائمة [::-1] لتصبح (الأقدم -> الأحدث)
    data = [
        [
            d["Open_time"], 
            d["Open"], 
            d["High"], 
            d["Low"], 
            d["Close"]
        ] 
        for d in docs
    ][::-1]

    # استخدام float64 يوفر الذاكرة ويسرع العمليات الحسابية
    return np.array(data, dtype=objet)

async def Get_HL_Points(symbol: str, limit: int) -> np.ndarray:
    """
    جلب نقاط High/Low.
    هنا نستخدم dtype=object لأن النوع Type عبارة عن نص (String).
    """
    cursor = db_indicitors[symbol].find(
        {}, 
        {"_id": 0, "Open_time": 1, "Price": 1, "Type": 1}
    ).sort("Open_time", -1).limit(limit)

    docs = await cursor.to_list(length=limit)

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

