import os
import asyncio
from datetime import datetime
import redis.asyncio as redis
import numpy as np
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo

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

# -------------------
# 🛠️ دالة إصلاح الفهارس (جديدة)
# -------------------
async def ensure_indexes():
    """
    تقوم هذه الدالة بفحص جميع المجموعات (العملات) وإنشاء فهرس زمني لها.
    يجب استدعاء هذه الدالة مرة واحدة عند بدء تشغيل النظام.
    """
    print("⏳ Checking and creating indexes for CandleStick_data...")
    
    # 1. جلب أسماء كل المجموعات (رموز العملات)
    collection_names = await db_candle.list_collection_names()
    
    for symbol in collection_names:
        # إنشاء فهرس تنازلي لحقل الوقت لضمان سرعة الاستعلام والترتيب
        # background=True: يسمح بإنشاء الفهرس دون إيقاف قاعدة البيانات
        await db_candle[symbol].create_index([("Open_time", pymongo.DESCENDING)], background=True)
        
    print(f"✅ Indexes ensured for {len(collection_names)} symbols in CandleStick_data.")

    # 2. نطبق نفس الشيء على Indicitors لأنك تستخدم sort فيها أيضاً
    print("⏳ Checking and creating indexes for Indicitors...")
    indicitor_names = await db_indicitors.list_collection_names()
    for symbol in indicitor_names:
        await db_indicitors[symbol].create_index([("Open_time", pymongo.DESCENDING)], background=True)
    
    print(f"✅ Indexes ensured for {len(indicitor_names)} symbols in Indicitors.")


async def Get_CandleStick(symbol: str, limit: int) -> np.ndarray:
    # الاستعلام هنا سيصبح سريعاً جداً بعد إنشاء الفهرس
    cursor = db_candle[symbol].find(
        {},
        {"_id": 0, "Open_time": 1, "Open": 1, "High": 1, "Low": 1, "Close": 1}
    ).sort("Open_time", -1).limit(limit) # قمت بتعديل بسيط هنا لاستخدام limit داخل المونجو مباشرة إن أمكن
    
    # تحويل النتيجة لقائمة (Async)
    # ملاحظة: to_list يتطلب length، إذا كنت تريد عدداً محدداً استخدم limit في الـ find أفضل
    result_list = await cursor.to_list(length=limit)
    
    # عكس المصفوفة لتصبح من الأقدم للأحدث (حسب طلب الاستراتيجيات عادة)
    return np.array([[c.get(col) for col in ["Open_time", "Open", "High", "Low", "Close"]] for c in result_list], dtype=object)[::-1]


async def Get_HL_Points(symbol: str, limit: int) -> np.ndarray:
    cursor = db_indicitors[symbol].find(
        {},
        {"_id": 0, "Open_time": 1, "Price": 1, "Type": 1}
    ).sort("Open_time", -1).limit(limit)

    result_list = await cursor.to_list(length=limit)

    return np.array([[c.get(col) for col in ["Open_time", "Price", "Type"]] for c in result_list], dtype=object)[::-1]


# -------------------
# JSON Helpers
# -------------------
def json_serialize(d):
    return {kk: (vv.isoformat() if isinstance(vv, datetime) else vv) for kk, vv in d.items()}

def json_deserialize(d):
    return {kk: (datetime.fromisoformat(vv) if kk in ['Start_Time','End_Time', 'Open_time','Close_time'] else vv) for kk, vv in d.items()}

# -------------------
# مثال لطريقة التشغيل (Main)
# -------------------
# عند تشغيل ملفك الرئيسي، تأكد من استدعاء دالة الفهارس أولاً
async def main_example():
    await init_redis()
    
    # ⚠️ استدعاء هذه الدالة مرة واحدة عند البدء
    await ensure_indexes() 
    
    # ثم ابدأ عملك الطبيعي
    data = await Get_CandleStick("BTCUSDT", 100)
    print(f"Got {len(data)} candles for BTCUSDT")

# إذا كنت تريد تجربة الكود مباشرة، ألغِ تعليق السطرين التاليين:
# if __name__ == "__main__":
#     asyncio.run(main_example())
