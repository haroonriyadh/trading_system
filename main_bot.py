import requests
from binance.client  import Client
from Database import mongo_client,db,db_OB,db_Orders
from datetime import datetime,timedelta
from concurrent.futures import ThreadPoolExecutor
import time
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo
#import psutil
from ticker_rules import rules
from numba import njit

# إعداد مفاتيح Binance API وTelegram
api_key = "MiQ3oXj2nqX2vZcOE3QO7ZsM3qLYIVtR1IYMl6TExUX88glGNCIjuwETUHKNE6Vy"
api_secret = "25IpcykYfndlVvmIaVPtGEq4fLSelVJSb6bFRl9JI9nHMY4UT0GT1fL7EerwNrhT"

client = Client(api_key=api_key,api_secret=api_secret)

symbols = list(rules.keys())

# إعداد مفاتيح Binance API وTelegram
TELEGRAM_TOKEN = '7540566988:AAE-RRfOVWraT-co87saoHTfMJujxDQEjaA'
TELEGRAM_CHAT_ID = '6061081574'

Risk_in_Position = 10

fees = 0.07

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

def get_next_15_min():
    now = datetime.now()
    minutes_to_next_15 = 15 - (now.minute % 15)
    next_time = now + timedelta(minutes=minutes_to_next_15)
    return next_time.replace(second=0,microsecond=0)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    
    try:
        response = requests.post(url=url, json=payload)
        if response.status_code == 200:
            print("رسالة Telegram تم إرسالها بنجاح")
        else:
            print(f"Failed to send message, status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def count_dicimal_places(step):
    return len(format(step,'f').split('.')[1]) if '.' in format(step,'f')  else 0

def format_price(symbol,price):
    return round(price - (price % rules[symbol][0]),count_dicimal_places(rules[symbol][0]))

def format_qty(symbol,qty):
    return  int(qty) if rules[symbol][1] == 1  else round(qty - (qty % rules[symbol][1]),count_dicimal_places(rules[symbol][1]))

def Open_Order(Client, Symbol:str, Side:str ,PositionSide:str ,Type:str ,Qty,Price ,Stop_price):
    return Client.futures_create_order(symbol = Symbol,
                                        side = Side,
                                        positionSide = PositionSide,
                                        type = Type,
                                        timeInForce='GTD',
                                        quantity = Qty,
                                        price = Price,
                                        stopPrice = Stop_price,
                                        goodTillDate = int((datetime.now() + timedelta(minutes=15)).timestamp()*1000),
                                        recvWindow = 5000,
                                        timestamp = int(time.time()*1000))

def Take_profit_order(Client, Symbol:str ,Side:str ,PositionSide:str ,Type:str, Take_Profit_price):
    return Client.futures_create_order(symbol = Symbol,
                                        side = Side,
                                        positionSide = PositionSide,
                                        type = Type,
                                        stopPrice = Take_Profit_price,
                                        closePosition = True,
                                        recvWindow = 5000,
                                        timestamp = int(time.time()*1000))

def Stop_loss_order(Client, Symbol:str ,Side:str ,PositionSide:str ,Type:str ,Stop_Loss_price):
    return Client.futures_create_order(symbol = Symbol,
                                        side = Side,
                                        positionSide = PositionSide,
                                        type = Type,
                                        stopPrice = Stop_Loss_price,
                                        closePosition = True,
                                        recvWindow = 5000,
                                        timestamp = int(time.time()*1000))

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

def fetch_and_store_candle(symbol):
    try:
        data = client.futures_klines(symbol=symbol,interval='1m',limit=2,recvWindow = 5000,timestamp = int(time.time()*1000))
        candle_record = {"Open_time": datetime.fromtimestamp(data[0][0] / 1000),
                         "Open": float(data[0][1]),
                         "High": float(data[0][2]),
                         "Low": float(data[0][3]),
                         "Close": float(data[0][4]),
                         "Volume": float(data[0][7]),
                         "Close_time": datetime.fromtimestamp(data[0][6] / 1000)}
        
        db[symbol+'_1m'].insert_one(candle_record)
    
    except Exception as e:
        print(e)
        
    if symbol+'_1m' in db.list_collection_names() and symbol in db_OB.list_collection_names():
      
        db_OB[symbol].update_many({},[{'$set':{'Distance':{'$abs':{'$subtract':[candle_record['Close'],'$Activation_price']}}}}])
        
        OB_collection = db_OB[symbol].aggregate([{'$sort':{'Distance':1}},{'$limit':4}])
        
        for OB in OB_collection:
            # Delete Order Block if Closing price is not respected ...
            if candle_record['Open_time'].minute % 15 == 14 and\
                ((OB['Side'] == 'Bullish' and candle_record['Close'] <= OB['Activation_price']) or\
                 (OB['Side'] == 'Bearish' and candle_record['Close'] >= OB['Activation_price'])):
                
                db_OB[symbol].delete_one(OB)
                continue
            
            
            elif  OB['In_Trade'] == False and\
                candle_record['Low'] <= OB['Activation_price'] and OB['Side'] == 'Bullish':
                entry_price = format_price(symbol,OB['Entry_price'])
                qty = format_qty(symbol,Amount_To_Risk(float(client.futures_account_balance(recvWindow = 5000,timestamp = int(time.time()*1000))[5]['balance']),Risk_in_Position,entry_price,format_price(symbol,OB['Stop_loss']),fees))
                if qty*entry_price >= rules[symbol][3]:
                    try:
                        order =  Open_Order(Client=client,
                                            Symbol=symbol,
                                            Side='BUY',
                                            PositionSide='LONG',
                                            Type='STOP',
                                            Qty=qty,
                                            Price=entry_price,
                                            Stop_price=format_price(symbol,entry_price+rules[symbol][4]))
                                            
                        db_OB[symbol].update_one(OB,{'$set':{'In_Trade':True}})
                        
                        db_Orders['Open_Orders'].insert_one({'symbol':order['symbol'],
                                                             'OrderId':order['orderId'],
                                                             'status': order['status'],
                                                             'side':order['side'],
                                                             'positionSide': order['positionSide'],
                                                             'Quantity':qty,
                                                             'Entry_price': entry_price,
                                                             'Take_profit':TP_long(entry_price,OB['Stop_loss'],fees,Risk_Reward),
                                                             'Stop_loss':OB['Stop_loss'],
                                                             'Take_Profit_id':0,
                                                             'Stop_Loss_id':0,
                                                             'Time_Update':get_next_15_min(),
                                                             'OB_Id':OB['_id']})
                    except Exception as e:
                        print(e)
                        pass

                else:
                    print(f'Your Balance is Insufficient to Entry Position Long in {symbol} .')
                
                
            
            elif  OB['In_Trade'] == False and\
                candle_record['High'] >= OB['Activation_price'] and OB['Side'] == 'Bearish':
                entry_price = format_price(symbol,OB['Entry_price'])
                qty = format_qty(symbol,Amount_To_Risk(float(client.futures_account_balance(recvWindow = 5000,timestamp = int(time.time()*1000))[5]['balance']),Risk_in_Position,entry_price,format_price(symbol,OB['Stop_loss']),fees))
                if qty*entry_price >= rules[symbol][3]:
                    try:
                        order =  Open_Order(Client=client,
                                            Symbol=symbol,
                                            Side='SELL',
                                            PositionSide='SHORT',
                                            Type='STOP',
                                            Qty=qty,
                                            Price=entry_price,
                                            Stop_price=format_price(symbol,entry_price-rules[symbol][4]))
                                            
                        db_OB[symbol].update_one(OB,{'$set':{'In_Trade':True}})
                        
                        db_Orders['Open_Orders'].insert_one({'symbol':order['symbol'],
                                                             'OrderId':order['orderId'],
                                                             'status': order['status'],
                                                             'side':order['side'],
                                                             'positionSide': order['positionSide'],
                                                             'Quantity':qty,
                                                             'Entry_price' : entry_price,
                                                             'Take_profit':TP_short(entry_price,OB['Stop_loss'],fees,Risk_Reward),
                                                             'Stop_loss':OB['Stop_loss'],
                                                             'Take_Profit_id':0,
                                                             'Stop_Loss_id':0,
                                                             'Time_Update':get_next_15_min(),
                                                             'OB_Id':OB['_id']})
                    except Exception as e:
                        print(e)
                        pass


                else:
                    print(f'Your Balance is Insufficient to Entry Position Short in {symbol} .')
                
    if candle_record['Open_time'].minute % 15 == 0:

        if db.command('count',symbol+'_15m')['n'] >= 4:
            candles = db[symbol+'_15m'].aggregate([{'$sort':{'Open_time':-1}},{'$limit':4}]).to_list()
            
            #Get Bullish Order Block
            if candles[2]['Low'] <= candles[3]['Low'] and\
                candles[0]['Low'] > candles[2]['High']:
                db_OB[symbol].insert_one({'Start_time':candles[2]['Open_time'],
                                          'End_Time':candles[2]['Open_time'],
                                          'Side':'Bullish',
                                          'Entry_price':min(candles[2]['High'],candles[3]['High']),
                                          'Activation_price':candles[2]['Low'],
                                          'Stop_loss':candles[2]['Low'],
                                          'Distance':abs(candles[0]['Close']-candles[2]['Low']),
                                          'In_Trade':False})
                

            #Get Bearish Order Block   
            elif candles[2]['High'] >= candles[3]['High'] and\
                candles[0]['High'] < candles[2]['Low']:
                db_OB[symbol].insert_one({'Start_time':candles[2]['Open_time'],
                                          'End_Time':candles[2]['Open_time'],
                                          'Side':'Bearish',
                                          'Entry_price':max(candles[3]['Low'],candles[2]['Low']),
                                          'Activation_price':candles[2]['High'],
                                          'Stop_loss':candles[2]['High'],
                                          'Distance':abs(candles[0]['Close']-candles[2]['High']),
                                          'In_Trade':False})
                                            
                
        
        else:
            print(f'Length CandleStick Data for {symbol+"_15m"} Less than 4')
            candle_15m = client.futures_klines(symbol=symbol,interval='15m',limit=5,recvWindow = 5000,timestamp = int(time.time()*1000))
            if float(candle_15m[1][3]) <= float(candle_15m[0][3]) and\
                float(candle_15m[3][3]) > float(candle_15m[1][2]):
                db_OB[symbol].insert_one({'Start_time':datetime.fromtimestamp(candle_15m[1][0]/1000),
                                          'End_Time':datetime.fromtimestamp(candle_15m[1][0]/1000),
                                          'Side':'Bullish',
                                          'Entry_price':min(float(candle_15m[0][2]),float(candle_15m[1][2])),
                                          'Activation_price':float(candle_15m[1][3]),
                                          'Stop_loss':float(candle_15m[1][3]),
                                          'Distance':abs(float(candle_15m[3][4])-float(candle_15m[2][3])),
                                          'In_Trade':False})
                

            #Get Bearish Order Block   
            elif float(candle_15m[1][2]) >= float(candle_15m[0][2]) and\
                float(candle_15m[3][2]) < float(candle_15m[1][3]):
                db_OB[symbol].insert_one({'Start_time':datetime.fromtimestamp(candle_15m[1][0]/1000),
                                          'End_Time':datetime.fromtimestamp(candle_15m[1][0]/1000),
                                          'Side':'Bearish',
                                          'Entry_price':max(float(candle_15m[0][3]),float(candle_15m[1][3])),
                                          'Activation_price':float(candle_15m[1][2]),
                                          'Stop_loss':float(candle_15m[1][2]),
                                          'Distance':abs(float(candle_15m[4][4])-float(candle_15m[1][2])),
                                          'In_Trade':False})
                
        db[symbol+'_15m'].insert_one(candle_record)
    
    elif symbol+'_15m' in db.list_collection_names() and db[symbol+'_15m'].count_documents({}) > 0:
        last_candle_15m = db[symbol+'_15m'].aggregate([{'$sort':{'Open_time':-1}},{'$limit':1}]).to_list()
        db[symbol+'_15m'].update_one({'Open_time':last_candle_15m[0]['Open_time']},
                                        {'$set':{'High':candle_record['High'] if candle_record['High'] > last_candle_15m[0]['High'] else last_candle_15m[0]['High'],
                                                 'Low':candle_record['Low'] if candle_record['Low'] < last_candle_15m[0]['Low'] else last_candle_15m[0]['Low'],
                                                 'Close':candle_record['Close'],
                                                 'Volume':last_candle_15m[0]['Volume']+candle_record['Volume'],
                                                 'Close_time':candle_record['Close_time']}})

def Pull_data_for_miunte():
    with ThreadPoolExecutor() as executor:
        executor.map(fetch_and_store_candle,symbols)


''' 
for symbol in db.list_collection_names():
    db[symbol].delete_many({})

for symbol in db_OB.list_collection_names():
    db_OB[symbol].delete_many({})
'''


time_zone = ZoneInfo('Asia/Riyadh')

Scheduler = BackgroundScheduler(timezone=time_zone)

Scheduler.add_job(Pull_data_for_miunte,'cron',second=10)

Scheduler.add_job(Monitoring_open_Positions,'interval',seconds=10)

Scheduler.start()

try:
    
    while True:
        pass
        
except Exception as e:
    print(e)


       
    
