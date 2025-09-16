import math
import requests
import json as js

url = "https://api.bybit.com/v5/market/instruments-info"
params = {"category": "linear"}
resp = requests.get(url, params=params).json()

symbols_info = {item["symbol"]: item for item in resp["result"]["list"]}

# حفظ في ملف JSON
with open("exchange_info.json", "w", encoding="utf-8") as f:
    js.dump(symbols_info, f, indent=4, ensure_ascii=False)

print("تم حفظ البيانات في exchange_info.json ✅")
