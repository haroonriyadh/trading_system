from binance.client  import Client
from Database import db_candle,db_OB,db_Orders,rides
from datetime import datetime,timedelta
from concurrent.futures import ThreadPoolExecutor
import time
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo
from ticker_rules import rules
from binance_client import client,Open_Order,Stop_loss_order,Take_profit_order,count_dicimal_places,format_price,format_qty
from telegram_bot import send_telegram_message




def Monitoring_open_Positions():
    if db_Orders.command('count','Open_Orders')['n'] > 0:
        if db_Orders['Open_Orders'].count_documents({'status':'FILLED'}) == max_open_positions:
            for order in db_Orders['Open_Orders'].find({'status':'NEW'}):
                client.futures_cancel_order(symbol=order['symbol'],orderId=order['OrderId'],recvWindow = 5000,timestamp = int(time.time()*1000))
                db_OB[order['symbol']].update_one({'_id':order['OB_Id']},{'$set':{'In_Trade':False}})
                db_Orders['Open_Orders'].delete_one({'symbol':order['symbol'],'OrderId':order['OrderId']})
        
        for order in db_Orders['Open_Orders'].find({}):
            if order['status'] == 'NEW':
                Order = client.futures_get_order(symbol = order['symbol'],orderId = order['OrderId'],recvWindow = 5000,timestamp = int(time.time()*1000))
                if Order['status'] == ('FILLED' or 'PARTIALLY_FILLED') and Order['type'] == 'LIMIT' and order['Time_Update'] > datetime.now():
                    
                    tp_order = Take_profit_order(Client=client,
                                                Symbol=order['symbol'],
                                                Side='BUY' if order['side'] == 'SELL' else 'SELL',
                                                PositionSide=order['positionSide'],
                                                Type='TAKE_PROFIT_MARKET',
                                                Take_Profit_price=format_price(order['symbol'],order['Take_profit']))
                                    
                    sl_order = Stop_loss_order(Client=client,
                                            Symbol=order['symbol'],
                                            Side='BUY' if order['side'] == 'SELL' else 'SELL',
                                            PositionSide=order['positionSide'],
                                            Type='STOP_MARKET',
                                            Stop_Loss_price=format_price(order['symbol'],order['Stop_loss']))
                                            
                    send_telegram_message(f"New Position: \nSymbol: {order['symbol']}\nSide: {order['side']}\nEntryPrice: {Order['price']}\nTakeProfit: {tp_order['stopPrice']}\nStopLoss: {sl_order['stopPrice']}")

                    db_Orders['Open_Orders'].update_one(order,
                                                        {'$set':{'status':Order['status'],
                                                                 'Take_Profit_id':tp_order['orderId'],
                                                                 'Stop_Loss_id':sl_order['orderId']}})
                    


                elif order['Time_Update'] <= datetime.now():
                    client.futures_cancel_order(symbol=order['symbol'],orderId=order['OrderId'],recvWindow = 5000,timestamp = int(time.time()*1000))
                    db_OB[order['symbol']].update_one({'_id':order['OB_Id']},{'$set':{'In_Trade':False}})
                    db_Orders['Open_Orders'].delete_one(order)
                    
                    
            elif order['status'] == ('FILLED' or 'PARTIALLY_FILLED'):
                Order_Take = client.futures_get_order(symbol = order['symbol'],orderId = order['Take_Profit_id'],recvWindow = 5000,timestamp = int(time.time()*1000))
                Order_Stop = client.futures_get_order(symbol = order['symbol'],orderId = order['Stop_Loss_id'],recvWindow = 5000,timestamp = int(time.time()*1000))
                if Order_Take['status'] == 'FILLED':
                    client.futures_cancel_order(symbol=Order_Stop['symbol'],orderId=Order_Stop['orderId'],recvWindow = 5000,timestamp = int(time.time()*1000))
                    send_telegram_message(f"{Order_Take['symbol']} Alert: Take Profit Reached!\nClose your position to secure profit")
                    db_Orders['Open_Orders'].delete_one(order)
                    db_OB[order['symbol']].update_one({'_id':order['OB_Id']},{'$set':{'In_Trade':False}})

                elif Order_Stop['status'] == 'FILLED':
                    client.futures_cancel_order(symbol=Order_Take['symbol'],orderId=Order_Take['orderId'],recvWindow = 5000,timestamp = int(time.time()*1000))
                    send_telegram_message(f"{Order_Stop['symbol']} Alert: Stop Loss Triggered!\nExit the position to minimize loss")
                    db_Orders['Open_Orders'].delete_one(order)
                    db_OB[order['symbol']].update_one({'_id':order['OB_Id']},{'$set':{'In_Trade':False}})
