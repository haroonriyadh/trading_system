# إنشاء جلسة اتصال
from pybit.unified_trading import HTTP, TradeHTTP
from datetime import datetime
import json
import time


# =========================
# Load API credentials
# =========================
with open('authcreds.json') as f:
    creds = json.load(f)

# =========================
# Create session
# =========================
session = HTTP(api_key=creds['Bybit']['key'], api_secret=creds['Bybit']['secret'],demo=True)

# =========================
# Helper Functions
# =========================
def place_market_order(symbol: str, side: str, qty: float, category: str):
    return session.place_order(
        category=category,
        symbol=symbol,
        orderType='Market',
        side=side,
        qty=qty
    )

def place_limit_order(symbol: str, side: str, qty: float, price: float, category: str):
    return session.place_order(
        category=category,
        symbol=symbol,
        orderType='Limit',
        side=side,
        qty=qty,
        price=price,
        timeInForce='GTC'
    )

def set_take_profit(symbol: str, side: str, ordertype: str, tp_price: float, qty: float, category: str):
    return session.place_order(
        category=category,
        symbol=symbol,
        side=side,
        orderType=ordertype,
        price=tp_price,
        takeProfit=tp_price,
        qty=qty
    )

def set_stop_loss(symbol: str, side: str,ordertype: str, sl_price: float, qty: float, category: str):
    return session.place_order(
        category=category,
        symbol=symbol,
        side=side,
        orderType=ordertype,
        price=sl_price,
        stopLoss=sl_price,
        qty=qty
    )

def cancel_order(symbol: str, order_id: str, category: str):
    return session.cancel_order(
        category=category,
        symbol=symbol,
        orderId=order_id
    )

def modify_pending_order(symbol: str, order_id: str, new_price: float, new_qty: float, category: str):
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

    return session.replace_order(**params)

def get_active_orders(symbol: str, category: str):
    """
    Get all active orders for a symbol
    """
    return session.get_active_orders(category=category, symbol=symbol)

# =========================
# Example Workflow
# =========================
if __name__ == "__main__":
    SYMBOL = 'BTCUSDT'
    QTY = 0.001
    MARKET_SIDE = 'Buy'
    LIMIT_PRICE = 110000
    TP_PRICE = 112000
    SL_PRICE = 109000
    CATEGORY = 'linear' 
    start = time.perf_counter()
    market_order = place_market_order(SYMBOL, MARKET_SIDE, QTY, CATEGORY)
    print(f"=== Place Market Order === in {time.perf_counter()-start}")

    print(market_order)
    time.sleep(1)

    print("=== Place Pending Limit Order ===")
    limit_order = place_limit_order(SYMBOL, 'Buy', QTY, LIMIT_PRICE, CATEGORY)
    print(limit_order)
    time.sleep(1)

    print("=== Set Take Profit ===")
    tp_order = set_take_profit(SYMBOL, 'Sell', 'Limit',TP_PRICE, QTY, CATEGORY)
    print(tp_order)
    time.sleep(1)

    print("=== Set Stop Loss ===")
    sl_order = set_stop_loss(SYMBOL, 'Sell', 'Limit', SL_PRICE, QTY, CATEGORY)
    print(sl_order)
    time.sleep(1)

    print("=== Get Active Orders ===")
    active_orders = get_active_orders(SYMBOL, CATEGORY)
    print(active_orders)

    if active_orders['result']:
        first_order_id = active_orders['result'][0]['orderId']
        print("=== Modify First Pending Order ===")
        modified_order = modify_pending_order(SYMBOL, first_order_id, new_price=108500, new_qty=0.002, category=CATEGORY)
        print(modified_order)


