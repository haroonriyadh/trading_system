import math
import requests
import json as js

url = "https://api.bybit.com/v5/market/instruments-info"
params = {"category": "linear"}
resp = requests.get(url, params=params).json()

symbols_info = {item["symbol"]: item for item in resp["result"]["list"]}

def format_price(symbol: str, price: float) -> str:
    tick_size = float(symbols_info[symbol]["priceFilter"]["tickSize"])
    decimals = int(round(-math.log10(tick_size)))
    return f"{price:.{decimals}f}"

def format_qty(symbol: str, qty: float, price: float) -> str:
    f = symbols_info[symbol]["lotSizeFilter"]
    step = float(f["qtyStep"])
    min_q = float(f["minOrderQty"])
    max_q = float(f["maxOrderQty"])
    min_notional = float(f.get("minNotionalValue", 0))  # بعض الرموز قد لا تحتوي على هذا الحقل

    # ضبط الكمية ضمن الحدود المسموحة
    qty = max(min_q, min(max_q, math.ceil(qty / step) * step))

    # التأكد من أن القيمة الاسمية >= minNotionalValue
    if price > 0 and qty * price < min_notional:
        qty = math.ceil(min_notional / price / step) * step
        qty = min(qty, max_q)  # لا تتجاوز الحد الأقصى

    # حساب عدد الخانات العشرية
    decimals = max(0, int(-math.log10(step))) if step < 1 else 0

    return f"{qty:.{decimals}f}"


def min_qty(symbol: str) -> float:
    return float(symbols_info[symbol]["lotSizeFilter"]["minOrderQty"])

def min_notional(symbol: str) -> float:
    return float(symbols_info[symbol]["lotSizeFilter"]["minNotionalValue"])

# حفظ في ملف JSON
with open("exchange_info.json", "w", encoding="utf-8") as f:
    js.dump(symbols_info, f, indent=4, ensure_ascii=False)

print("تم حفظ البيانات في instruments_info.json ✅")
