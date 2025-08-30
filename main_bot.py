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


symbols = list(rules.keys())

Risk_in_Position = 1

fees = 0.04

Risk_Reward = 2

max_open_positions = 4

#@njit
def Amount_To_Risk(balance, max_loss, buy_price ,sl ,fees):
    return (balance*(max_loss/(((abs((buy_price/sl)-1)*100))+fees)))/buy_price

#@njit
def TP_long(buy_price, sl, fees, RRR):
    return buy_price*(((((abs(((buy_price/sl)-1)*100)+fees)*RRR)+fees)/100)+1)

#@njit
def TP_short(buy_price, sl, fees, RRR):
    return buy_price*((((((abs(((sl/buy_price)-1)*100)+fees)*RRR)+fees)*-1)/100)+1)

def get_next_15_min():
    now = datetime.now()
    minutes_to_next_15 = 15 - (now.minute % 15)
    next_time = now + timedelta(minutes=minutes_to_next_15)
    return next_time.replace(second=0,microsecond=0)





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
        
        db_candle[symbol+'_1m'].insert_one(candle_record)
    
    except Exception as e:
        print(e)
        
    if symbol+'_1m' in db_candle.list_collection_names() and symbol in db_OB.list_collection_names():
      
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

        if db_candle.command('count',symbol+'_15m')['n'] >= 4:
            candles = db_candle[symbol+'_15m'].aggregate([{'$sort':{'Open_time':-1}},{'$limit':4}]).to_list()
            
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
                
        db_candle[symbol+'_15m'].insert_one(candle_record)
    
    elif symbol+'_15m' in db_candle.list_collection_names() and db_candle[symbol+'_15m'].count_documents({}) > 0:
        last_candle_15m = db_candle[symbol+'_15m'].aggregate([{'$sort':{'Open_time':-1}},{'$limit':1}]).to_list()
        db_candle[symbol+'_15m'].update_one({'Open_time':last_candle_15m[0]['Open_time']},
                                        {'$set':{'High':candle_record['High'] if candle_record['High'] > last_candle_15m[0]['High'] else last_candle_15m[0]['High'],
                                                 'Low':candle_record['Low'] if candle_record['Low'] < last_candle_15m[0]['Low'] else last_candle_15m[0]['Low'],
                                                 'Close':candle_record['Close'],
                                                 'Volume':last_candle_15m[0]['Volume']+candle_record['Volume'],
                                                 'Close_time':candle_record['Close_time']}})

def Pull_data_for_miunte():
    with ThreadPoolExecutor() as executor:
        executor.map(fetch_and_store_candle,symbols)


''' 
for symbol in db_candle.list_collection_names():
    db_candle[symbol].delete_many({})

for symbol in db_OB.list_collection_names():
    db_OB[symbol].delete_many({})
'''


time_zone = ZoneInfo('Asia/Riyadh')

if __name__ == "__main__":

    Scheduler = BackgroundScheduler(timezone=time_zone)

    Scheduler.add_job(Pull_data_for_miunte,'cron',second=10)

    #Scheduler.add_job(Monitoring_open_Positions,'interval',seconds=10)

    Scheduler.start()

    try:
        
        while True:
            pass
            
    except Exception as e:
        print(e)


       
    
