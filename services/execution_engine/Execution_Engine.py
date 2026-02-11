import asyncio
import json
from shared.symbols_loader import symbols
import traceback
from shared.database import (
    db_Orders,
    init_redis,
    json_serialize,
    json_deserialize
)


from bybit_client import (
    get_coin_balance,
    place_market_order,
    set_take_profit,set_stop_loss,
    format_price,
    format_qty,
    min_qty,
    min_notional
)

Risk_in_Position = 0.1

fees = 0.10

Risk_Reward = 2

max_open_positions = 4


def  Amount_To_Risk(balance, max_loss, buy_price ,sl ,fees):
    return (balance*(max_loss/(((abs((buy_price/sl)-1)*100))+fees)))/buy_price

def TP_long(buy_price, sl, fees, RRR):
    return buy_price*(((((abs(((buy_price/sl)-1)*100)+fees)*RRR)+fees)/100)+1)

def TP_short(buy_price, sl, fees, RRR):
    return buy_price*((((((abs(((sl/buy_price)-1)*100)+fees)*RRR)+fees)*-1)/100)+1)

async def Execution_Order(symbol):
    """مهمة خلفية لمراقبة Redis بحثاً عن إشارات جديدة"""
    print("📡 Signal Monitor Started...", flush=True)
    Redis = await init_redis()
    pubsub = Redis.pubsub()

    # الاشتراك في قنوات جميع العملات
    channel = f"{symbol}_Trade_Signal"
    if not channel:
        print("⚠️ No symbols loaded to subscribe!", flush=True)
        # حتى لو لم توجد رموز، نستمر في الحلقة لعدم إيقاف التاسك
    else:
        await pubsub.subscribe(channel)
        print(f"✅ Subscribed to {symbol } channel")
    while True:
        try:
            # انتظار رسالة (timeout قصير للسماح للحلقة بالعمل)
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            
            if message:
                data_str = message['data']
                if isinstance(data_str, bytes):
                    data_str = data_str.decode('utf-8')

                Order = json.loads(data_str)
                Side = Order["side"]
                print(f"🔔 Signal Received: {Order}", flush=True)
            
                # Run synchronous API calls in a thread pool to avoid blocking the event loop
                balance_info = await asyncio.to_thread(get_coin_balance, "USDT")
                if not balance_info:
                    print(f"Error: Could not fetch balance for {symbol}")
                    continue

                # Calculate Risk In Position
                Amount = Amount_To_Risk(
                    float(balance_info["walletBalance"]),
                    Risk_in_Position, Order["entry"],
                    Order["stop_loss"],
                    fees
                )
                
                Tp_price = format_price(
                    symbol,
                    TP_long(
                        Order["entry"],
                        Order["stop_loss"],
                        fees,
                        Risk_Reward
                    )
                ) if Side == "Bull" else format_price(
                    symbol,
                    TP_short(
                        Order["entry"],
                        Order["stop_loss"],
                        fees,
                        Risk_Reward
                    )
                )
                
                # Check Amount Not Smaller Then Min Qty 
                if (
                    Amount >= min_qty(symbol) and
                    (Amount * Order["entry"]) >= min_notional(symbol)
                ):
                    # Run order placement in a thread pool
                    # pybit's HTTP methods are synchronous and use requests internally
                    Market_Order = await asyncio.to_thread(
                        place_market_order,
                        symbol=symbol,
                        side="Buy" if Side == "Bull" else "Sell",
                        qty=format_qty(
                            symbol,
                            Amount,
                            Order["entry"]
                        ),
                        take_profit=Tp_price,
                        stop_loss=Order["stop_loss"]
                    )
                    
                    if Market_Order.get("result"):
                        await Redis.publish(f"{symbol}_Open_Trade", json.dumps(json_serialize(Order)))
                        # Store Market Order In Database
                        await db_Orders[symbol].insert_one(Market_Order["result"])
                        print(f"System Placed Market Order in {symbol} at {Order['entry']}")
                    else:
                        print(f"Error placing order for {symbol}: {Market_Order.get('retMsg')}")
                        
        except Exception as e:
            print(f"Error in Execution_Order for {symbol}: {e}")
            await asyncio.sleep(1)



async def main():
    tasks = []
    for sym in symbols:
        tasks.append(asyncio.create_task(Execution_Order(sym)))
        
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())