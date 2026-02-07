import asyncio
import json
from shared.symbols_loader import symbols
import traceback
from shared.database import (
    db_Orders,
    init_redis,
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
    Redis = await init_redis()
    while True:
        try:
            # brpop returns (key, value) when it gets a message from any of the keys
            result = await Redis.brpop(f"{symbol}_Open_Position", 0)
            if not result:
                continue
                
            key, raw_order = result
            Order = json_deserialize(json.loads(raw_order))
            Side = Order["Side"]
            
            if isinstance(Order, dict):
                # Run synchronous API calls in a thread pool to avoid blocking the event loop
                balance_info = await asyncio.to_thread(get_coin_balance, "USDT")
                if not balance_info:
                    print(f"Error: Could not fetch balance for {symbol}")
                    continue

                # Calculate Risk In Position
                Amount = Amount_To_Risk(
                    float(balance_info["walletBalance"]),
                    Risk_in_Position, Order["Entry_Price"],
                    Order["Stop_Loss"],
                    fees
                )
                
                Tp_price = format_price(
                    symbol,
                    TP_long(
                        Order["Entry_Price"],
                        Order["Stop_Loss"],
                        fees,
                        Risk_Reward
                    )
                ) if Side == "Long" else format_price(
                    symbol,
                    TP_short(
                        Order["Entry_Price"],
                        Order["Stop_Loss"],
                        fees,
                        Risk_Reward
                    )
                )
                
                # Check Amount Not Smaller Then Min Qty 
                if (
                    Amount >= min_qty(symbol) and
                    (Amount * Order["Entry_Price"]) >= min_notional(symbol)
                ):
                    # Run order placement in a thread pool
                    # pybit's HTTP methods are synchronous and use requests internally
                    Market_Order = await asyncio.to_thread(
                        place_market_order,
                        symbol=symbol,
                        side="Buy" if Side == "Long" else "Sell",
                        qty=format_qty(
                            symbol,
                            Amount,
                            Order["Entry_Price"]
                        ),
                        take_profit=Tp_price,
                        stop_loss=Order["Stop_Loss"]
                    )
                    
                    if Market_Order.get("result"):
                        # Store Market Order In Database
                        await db_Orders[symbol].insert_one(Market_Order["result"])
                        print(f"System Placed Market Order in {symbol} at {Order['Entry_Price']}")
                    else:
                        print(f"Error placing order for {symbol}: {Market_Order.get('retMsg')}")
                        
        except Exception as e:
            print(f"Error in Execution_Order for {symbol}: {e}")
            await asyncio.sleep(1)

async def worker_wrapper(fn, symbol):
    while True:
        try:
           await fn(symbol)
        except Exception as e:
            print(traceback.format_exc())
            await asyncio.sleep(5)

async def main():
    tasks = []
    for sym in symbols:
        tasks.append(
            asyncio.create_task(
                worker_wrapper(
                    Execution_Order,sym
                )
            )
        )

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())


            

        

            



