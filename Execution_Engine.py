import json
from Database import db_Orders,Redis,json_deserialize,json_serialize
from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor
from symbols import symbols
from telegram_bot import send_telegram_message
from bybit_client import get_coin_balance,place_limit_order,set_take_profit,format_price,format_qty,min_qty,min_notional,get_order_status,modify_pending_order
from numba import njit

Risk_in_Position = 1

fees = 0.04

Risk_Reward = 2

max_open_positions = 4

@njit
def Amount_To_Risk(balance, max_loss, buy_price ,sl ,fees):
    return (balance*(max_loss/(((abs((buy_price/sl)-1)*100))+fees)))/buy_price

@njit
def TP_long(buy_price, sl, fees, RRR):
    return buy_price*(((((abs(((buy_price/sl)-1)*100)+fees)*RRR)+fees)/100)+1)

@njit
def TP_short(buy_price, sl, fees, RRR):
    return buy_price*((((((abs(((sl/buy_price)-1)*100)+fees)*RRR)+fees)*-1)/100)+1)

last_order_in_symbols = {symbol : {"Long" : {"Order_id" : None,"Price" : None} ,"Short" : {"Order_id" : None,"Price" : None}} for symbol in symbols}

async def worker(symbol):

    while True:
        # انتظار إكتشاف الاوردر بلوك الجديد
        last_order = Redis.brpop(f"queue:{symbol}_Last_Order_Block", 0)
        last_order = json_deserialize(json.loads(last_order[1]))

        if isinstance(last_order, dict):
            if  last_order["Side"] == "Long" and get_order_status(symbol,last_order_in_symbols[symbol]["Long"])["result"][0]["orderStatus"] == "New":

                if last_order_in_symbols[symbol]["Long"]["Price"] > last_order["Entry_Price"]:                
                    
                    #حساب المخاطره في الصفقة
                    Amount = Amount_To_Risk(float(get_coin_balance("USDT")["walletBalance"]),Risk_in_Position,last_order["Entry_Price"],last_order["Stop_Loss"],fees)
                    
                    #ارسال امر معلق للمنصه
                    order_modify = modify_pending_order(symbol = symbol,
                                                        order_id=last_order_in_symbols[symbol]["Long"]["Order_id"],
                                                        new_qty = format_qty(symbol,Amount,last_order_in_symbols[symbol]["Long"]["Price"]),
                                                        new_price = format_price(symbol,last_order["Entry_Price"]))

                    # حفظ الامر المعلق في قاعدة البيانات
                    db_Orders[symbol].insert_one(order_modify["result"])
                    print(f"System Modify Pending Order in {symbol} at {last_order['Entry_Price']}")

                    last_order_in_symbols[symbol][last_order["Side"]] = {"Order_id":order_modify["result"]["orderId"],"Price" : last_order["Entry_Price"]}
                    
                    #ارسال اشعار لفتح WebSocket Stream لمراقبة الاوامر المعلقة
                    #Redis.lpush(f"queue:{symbol}_Monitor_Order", "Order_id")
                
                elif last_order_in_symbols[symbol]["Long"]["Price"] == None:
                    #حساب المخاطره في الصفقة
                    Amount = Amount_To_Risk(float(get_coin_balance("USDT")["walletBalance"]),Risk_in_Position,last_order["Entry_Price"],last_order["Stop_Loss"],fees)
                    
                    #ارسال امر معلق للمنصه
                    order_limit = place_limit_order(symbol = symbol,
                                                    side = "Buy" if last_order["Side"] == "Long" else "Sell",
                                                    qty = format_qty(symbol,Amount,last_order_in_symbols[symbol]["Long"]["Price"]),
                                                    price = format_price(symbol,last_order["Entry_Price"]))

                    # حفظ الامر المعلق في قاعدة البيانات
                    db_Orders[symbol].insert_one(order_limit["result"])
                    print(f"✅ System Place Limit Order in {symbol} at {last_order['Entry_Price']}")

                    last_order_in_symbols[symbol][last_order["Side"]] = {"Order_id":order_limit["result"]["orderId"],"Price" : last_order["Entry_Price"]}
                    
                    #ارسال اشعار لفتح WebSocket Stream لمراقبة الاوامر المعلقة
                    #Redis.lpush(f"queue:{symbol}_Monitor_Order", "Order_id")

            elif last_order["Side"] == "Short" and get_order_status(symbol,last_order_in_symbols[symbol]["Long"])["result"][0]["orderStatus"] == "New" and\
                (last_order_in_symbols[symbol]["Long"]["Price"] < last_order["Entry_Price"] or last_order_in_symbols[symbol]["Long"]["Price"] == None):
                
            
                
                
                """
                # إرسال رسالة نصية لارسال الامر المعلق
                send_telegram_message(f"Order Block Detected!\n\nSymbol: {symbol}\n"+
                                    f"Side: {OB['Side']}\n"+
                                    f"Entry Price: {OB['Entry_Price']:.4f}\n"+
                                    f"Stop Loss: {OB['Stop_Loss']:.4f}\n"+
                                    f"Time: {OB['Start_Time']}")
                """

            

        

if __name__ == "__main__":
    # ThreadPoolExecutor لتشغيل Workers بالتوازي
    with ThreadPoolExecutor(max_workers=len(symbols)) as executor:
        futures = [executor.submit(worker, sym) for sym in symbols]

        # نخلي البرنامج يشتغل باستمرار
        for f in futures:
            f.result()
            



