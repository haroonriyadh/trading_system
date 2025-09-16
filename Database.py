import os
from pymongo import MongoClient
import redis
from datetime import datetime


# MongoDB
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))

mongo_client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
db_candle = mongo_client['CandleStick_data']
db_OB = mongo_client['Order_Block']
db_Orders = mongo_client['Open_Orders']

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

Redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)



def Nearest_OB_Long(symbol: str, current_price: float) -> dict | None:
    # 1️⃣ إلغاء أي Order Block شرائي فوق السعر الحالي
    db_OB[symbol].update_many(
        {
            "Side": "Long",
            "Mitigated": 0,
            "Entry_Price": {"$gt": current_price}
        },
        {"$set": {"Mitigated": 1}}
    )

    # 2️⃣ إرجاع أقرب OB صالح (تحت السعر الحالي)
    results = db_OB[symbol].aggregate([
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


def Nearest_OB_Short(symbol: str, current_price: float) -> dict | None:
    # 1️⃣ إلغاء أي Order Block بيعي تحت السعر الحالي
    db_OB[symbol].update_many(
        {
            "Side": "Short",
            "Mitigated": 0,
            "Entry_Price": {"$lt": current_price}
        },
        {"$set": {"Mitigated": 1}}
    )

    # 2️⃣ إرجاع أقرب OB صالح (فوق السعر الحالي)
    results = db_OB[symbol].aggregate([
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
