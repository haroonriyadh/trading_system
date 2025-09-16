import redis
import pickle
import json
import timeit
from datetime import datetime, timedelta

# إعداد Redis
r = redis.Redis(host='localhost', port=6379, db=0)

# دالة لحساب نهاية الشمعة
def next_candle_time(ts, frame, limit_to_end):
    return ts + timedelta(minutes=frame)

# دالة إنشاء Order Block
def make_order_block(side, ts, entry, stop, frame=5, limit_to_end=True):
    return {
        "Side": side,
        "Start_Time": ts if isinstance(ts, datetime) else datetime.fromtimestamp(ts/1000),
        "Entry_Price": entry,
        "Stop_Loss": stop,
        "End_Time": next_candle_time(ts, frame, limit_to_end),
        "Mitigated": 0
    }

# إنشاء dict كبير 1000 order block
test_dict = {f'order{i}': make_order_block("buy", datetime.now(), 150+i, 149+i) for i in range(1)}

# تحويل dict للـ JSON (تحويل datetime إلى isoformat)
def json_serialize(d):
    return {kk: (vv.isoformat() if isinstance(vv, datetime) else vv) for kk, vv in d.items()}

def json_deserialize(d):
    return {kk: (datetime.fromisoformat(vv) if kk in ['Start_Time','End_Time'] else vv) for kk, vv in d.items()}

# عدد التكرارات
repeats = 1000

# دوال لكل طريقة
def set_get_pickle():
    r.set("test_pickle", pickle.dumps(test_dict))
    pickle.loads(r.get("test_pickle"))

def set_get_json():
    r.set("test_json", json.dumps(json_serialize(test_dict)))
    json_deserialize(json.loads(r.get("test_json")))

def set_get_hash():
    # تحويل كل value إلى JSON string
    mapping = {k: json.dumps(json_serialize({k:v})[k]) for k,v in test_dict.items()}
    r.hset("test_hash", mapping=mapping)

    raw_data = r.hgetall("test_hash")
    data = {}
    for k, v in raw_data.items():
        key = k.decode()
        # كل value هي JSON string تمثل dict مفرد
        value_dict = json.loads(v.decode())
        # إعادة تحويل datetime
        value_dict = {kk: (datetime.fromisoformat(vv) if kk in ['Start_Time','End_Time'] else vv) for kk, vv in value_dict.items()}
        data[key] = value_dict

# قياس الزمن
pickle_time = timeit.timeit(set_get_pickle, number=repeats)
json_time = timeit.timeit(set_get_json, number=repeats)
hash_time = timeit.timeit(set_get_hash, number=repeats)

# طباعة النتائج
print(f"Pickle: {pickle_time/repeats:.6f}s per operation")
print(f"JSON  : {json_time/repeats:.6f}s per operation")
print(f"Hash  : {hash_time/repeats:.6f}s per operation")

# حذف المفاتيح المستخدمة
r.delete("test_pickle")
r.delete("test_json")
r.delete("test_hash")
print("تم مسح البيانات من Redis.")
