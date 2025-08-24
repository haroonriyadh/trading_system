from pymongo import MongoClient
 

mongo_client = MongoClient('mongodb://localhost:27017/')
db = mongo_client['CandleStick_data']  # اسم قاعدة البيانات
db_OB = mongo_client['Order_Block']
db_Orders = mongo_client['Open_Orders']
 
