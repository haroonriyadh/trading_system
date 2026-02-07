# إنشاء جلسة اتصال
from pybit.unified_trading import HTTP, TradeHTTP
from datetime import datetime
import json
import time
import math
import requests


url = "https://api.bybit.com/v5/market/instruments-info"
params = {"category": "linear","limit":"1000"}
resp = requests.get(url, params=params).json()

symbols_info = {item["symbol"]: item for item in resp["result"]["list"] if item["symbol"].endswith("USDT") and item["status"] == "Trading"}


# حفظ في ملف JSON
with open("exchange_info.json", "w", encoding="utf-8") as f:
    json.dump(symbols_info, f, indent=4, ensure_ascii=False)

print(f"تم حفظ البيانات في exchange_info.json ✅ for {len(symbols_info)} coin ")


# =========================
# Create session
# =========================
session = HTTP(
  api_key="Jxyfw9hxY3NLVznAJx",
  api_secret="Bl1XKTd3lh56rvhneJ4BS9RbmKTLFNgE4coe",
  demo=True
)

# =========================
# Helper Functions
# =========================
def format_price(symbol: str, price: float) -> float:
    tick_size = float(symbols_info[symbol]["priceFilter"]["tickSize"])
    decimals = int(round(-math.log10(tick_size)))
    return float(f"{price:.{decimals}f}")

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

    return float(f"{qty:.{decimals}f}")

def min_qty(symbol: str) -> float:
    return float(symbols_info[symbol]["lotSizeFilter"]["minOrderQty"])

def min_notional(symbol: str) -> float:
    return float(symbols_info[symbol]["lotSizeFilter"]["minNotionalValue"])

def place_market_order(symbol: str, side: str, qty: float, take_profit: float, stop_loss: float , category: str = "linear"):
    return session.place_order(
        category=category,
        symbol=symbol,
        orderType='Market',
        side=side,
        takeProfit=take_profit,    # أخذ الربح
        stopLoss=stop_loss,      # وقف الخسارة
        tpTriggerBy="LastPrice",
        slTriggerBy="LastPrice",
        qty=qty
    )

def place_limit_order(symbol: str, side: str, qty: float, price: float, category: str = "linear"):
    return session.place_order(
        category=category,
        symbol=symbol,
        orderType='Limit',
        side=side,
        qty=qty,
        price=price,
        timeInForce='GTC'
    )

def set_take_profit(symbol: str, side: str, ordertype: str, tp_price: float, qty: float, category: str = "linear"):
    return session.place_order(
        category=category,
        symbol=symbol,
        side=side,
        orderType=ordertype,
        price=tp_price,
        takeProfit=tp_price,
        qty=qty
    )

def set_stop_loss(symbol: str, side: str,ordertype: str, sl_price: float, qty: float, category: str = "linear"):
    return session.place_order(
        category=category,
        symbol=symbol,
        side=side,
        orderType=ordertype,
        price=sl_price,
        stopLoss=sl_price,
        qty=qty
    )

def cancel_order(symbol: str, order_id: str, category: str = "linear"):
    return session.cancel_order(
        category=category,
        symbol=symbol,
        orderId=order_id
    )

def modify_pending_order(symbol: str, order_id: str, new_price: float, new_qty: float, category: str = "linear"):
    """
    Modify an existing pending (Limit) order.
    """
    params = {
        "category": category,
        "symbol": symbol,
        "orderId": order_id,
    }
    if new_price is not None:
        params["price"] = new_price
    if new_qty is not None:
        params["qty"] = new_qty

    return session.amend_order(**params)

def get_active_orders(symbol: str, category: str = "linear"):
    """
    Get all active orders for a symbol
    """
    return session.get_open_orders(category=category, symbol=symbol)

def get_order_status(symbol: str, order_id: str, category: str = "linear"):
    return session.get_order_history(category=category, symbol=symbol, orderId=order_id)

def get_wallet_balance(category: str = 'linear'):
    """
    Get wallet balance for a specific category (spot, linear, option, etc.)
    """
    return session.get_wallet_balance(category=category, accountType="UNIFIED")

def get_account_info():
    """
    Get account information including balances for all categories
    """
    return session.get_account_info()

def get_coin_balance(coin: str, category: str = 'linear'):

    """
    Get balance for a specific coin in a specific category
    """
    balance_info = get_wallet_balance(category)
    
    if balance_info.get('result') and balance_info['result'].get('list'):
        for account in balance_info['result']['list']:
            # البحث في قائمة العملات داخل كل حساب
            if account.get('coin'):
                for coin_info in account.get('coin', []):
                    if coin_info.get('coin') == coin:
                        return coin_info
    return None

if __name__ == "__main__":
    start = time.perf_counter()
    print(get_coin_balance("USDT"))
    print(time.perf_counter()-start)

    Respone = {'availableToBorrow': '',
                'bonus': '0',
                'accruedInterest': '0', 
                'availableToWithdraw': '', 
                'totalOrderIM': '0', 
                'equity': '46708.96299647', 
                'totalPositionMM': '0', 
                'usdValue': '46751.09448109', 
                'unrealisedPnl': '0', 
                'collateralSwitch': True, 
                'spotHedgingQty': '0', 
                'borrowAmount': '0.000000000000000000',
                'totalPositionIM': '0', 
                'walletBalance': '46708.96299647', 
                'cumRealisedPnl': '-3291.03700353', 
                'locked': '0', 
                'marginCollateral': True, 'coin': 'USDT'}

