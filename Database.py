from pymongo import MongoClient
import redis


mongo_client = MongoClient('mongodb://localhost:27017/')
db_candle = mongo_client['CandleStick_data']
db_OB = mongo_client['Order_Block']
db_Orders = mongo_client['Open_Orders']

Redis = redis.Redis(host='redis', port=6379, db=0)


