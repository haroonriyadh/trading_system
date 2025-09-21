import os
from datetime import datetime
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient




# -------------------
# MongoDB Async
# -------------------
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))

mongo_client = AsyncIOMotorClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
db_candle = mongo_client['CandleStick_data']
db_OB = mongo_client['Order_Block']
db_Orders = mongo_client['Open_Orders']

# -------------------
# Redis Async
# -------------------
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

Redis = None

async def init_redis():
    global Redis
    if Redis is None:
        Redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return Redis



async def Nearest_OB_Long(symbol: str, current_price: float) -> dict | None:
    # 1️⃣ إلغاء أي Order Block شرائي فوق السعر الحالي
    await db_OB[symbol].update_many(
        {
            "Side": "Long",
            "Mitigated": 0,
            "Entry_Price": {"$gt": current_price}
        },
        {"$set": {"Mitigated": 1}}
    )

    # 2️⃣ إرجاع أقرب OB صالح (تحت السعر الحالي)
    results = await db_OB[symbol].aggregate([
        {"$project": {"_id": 0}},
        {"$match": {
            "Side": "Long",
            "Mitigated": 0,
            "Entry_Price": {"$lt": current_price}
        }},
        {"$addFields": {
            "diff": {"$abs": {"$subtract": ["$Entry_Price", current_price]}}
        }},
        {"$sort": {"diff": 1}},
        {"$limit": 1}
    ]).to_list()

    return results[0] if results else None


async def Nearest_OB_Short(symbol: str, current_price: float) -> dict | None:
    # 1️⃣ إلغاء أي Order Block بيعي تحت السعر الحالي
    await db_OB[symbol].update_many(
        {
            "Side": "Short",
            "Mitigated": 0,
            "Entry_Price": {"$lt": current_price}
        },
        {"$set": {"Mitigated": 1}}
    )

    # 2️⃣ إرجاع أقرب OB صالح (فوق السعر الحالي)
    results = await db_OB[symbol].aggregate([
        {"$project": {"_id": 0}},
        {"$match": {
            "Side": "Short",
            "Mitigated": 0,
            "Entry_Price": {"$gt": current_price}
        }},
        {"$addFields": {
            "diff": {"$abs": {"$subtract": ["$Entry_Price", current_price]}}
        }},
        {"$sort": {"diff": 1}},
        {"$limit": 1}
    ]).to_list()

    return results[0] if results else None



# تحويل dict للـ JSON (تحويل datetime إلى isoformat)
def json_serialize(d):
    return {kk: (vv.isoformat() if isinstance(vv, datetime) else vv) for kk, vv in d.items()}

def json_deserialize(d):
    return {kk: (datetime.fromisoformat(vv) if kk in ['Start_Time','End_Time'] else vv) for kk, vv in d.items()}
