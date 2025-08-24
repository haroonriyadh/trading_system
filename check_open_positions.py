from binance_client import client,Client
from Database import db_Orders
import time
from ticker_rules import format_price

TELEGRAM_TOKEN = '7540566988:AAE-RRfOVWraT-co87saoHTfMJujxDQEjaA'
TELEGRAM_CHAT_ID = '6061081574'

max_open_positions = 2

def Take_profit_order(Client:Client, Symbol:str ,Side:str ,PositionSide:str ,Type:str ,Take_Profit_Order:float):
    return Client.futures_create_order(symbol = Symbol,
                                        side = Side,
                                        positionSide=PositionSide,
                                        type=Type,
                                        stopPrice = Take_Profit_Order,
                                        ClosePosition = True,
                                        recvWindow = 5000,
                                        timestamp = int(time.time()*1000))

def Stop_loss_order(Client:Client, Symbol:str ,Side:str ,PositionSide:str ,Type:str ,Stop_Loss_Order:float):
    return Client.futures_create_order(symbol = Symbol,
                                        side = Side,
                                        positionSide=PositionSide,
                                        type=Type,
                                        stopPrice = Stop_Loss_Order,
                                        ClosePosition = True,
                                        recvWindow = 5000,
                                        timestamp = int(time.time()*1000))

def Monitoring_open_Positions(client:Client):
    if db_Orders.command('count','Open_Orders')['n'] > 0:
        if len(db_Orders['Open_Orders'].find({'status':'FILLED'}).to_list()) == max_open_positions:
            for order in db_Orders['Open_Orders'].find({'status':'NEW'}):
                client.futures_cancel_order(symbol=order['symbol'],orderId=order['OrderId'],recvWindow = 5000,timestamp = int(time.time()*1000))
                db_Orders['Open_Orders'].delete_one({'symbol':order['symbol'],'OrderId':order['OrderId']})
        
        for order in db_Orders['Open_Orders'].find({}):
            
            if order['status'] == 'NEW':
                Order = client.futures_get_order(symbol = order['symbol'],orderId = order['OrderId'])
                if Order['status'] == ('FILLED' or 'PARTIALLY_FILLED') and Order['type'] == 'LIMIT':
                    

                    tp_order = Take_profit_order(Client=client,
                                                  Symbol=order['symbol'],
                                                  Side='BUY' if order['side'] == 'SELL' else 'SELL',
                                                  PositionSide=order['positionSide'],
                                                  Type='TAKE_PROFIT_MARKET',
                                                  Take_Profit_Order=format_price(order['symbol'],order['Take_profit']))
                                    
                    sl_order = Stop_loss_order(Client=client,
                                               Symbol=order['symbol'],
                                               Side='BUY' if order['side'] == 'SELL' else 'SELL',
                                               PositionSide=order['positionSide'],
                                               Type='STOP_MARKET',
                                               Stop_Loss_Order=format_price(order['symbol'],order['Stop_loss']))
                    
                    db_Orders['Open_Orders'].update_one({'symbol':Order['symbol'],'orderId':Order['orderId']},
                                                        {'$set':{'status':Order['status'],
                                                                 'Take_Profit_id':tp_order['orderId'],
                                                                 'Stop_Loss_id':sl_order['orderId']}})
                    

                elif Order['status'] == 'CANCELED':
                    db_Orders['Open_Orders'].delete_one({'symbol':order['symbol'],'OrderId':order['OrderId']})


            elif order['status'] == ('FILLED' or 'PARTIALLY_FILLED'):
                Order_Take = client.futures_get_order(symbol = order['symbol'],orderId = order['Take_Profit_id'])
                Order_Stop = client.futures_get_order(symbol = order['symbol'],orderId = order['Stop_Loss_id'])
                if Order_Take['status'] == 'FILLED':
                    client.futures_cancel_order(symbol=Order_Stop['symbol'],orderId=Order_Stop['orderId'],recvWindow = 5000,timestamp = int(time.time()*1000))
                    db_Orders['Open_Orders'].delete_one({'symbol':Order_Take['symbol'],'Stop_Loss_id':order['Stop_Loss_id']})

                elif Order_Stop['status'] == 'FILLED':
                    client.futures_cancel_order(symbol=Order_Take['symbol'],orderId=Order_Take['orderId'],recvWindow = 5000,timestamp = int(time.time()*1000))
                    db_Orders['Open_Orders'].delete_one({'symbol':Order_Take['symbol'],'Take_Profit_id':order['Take_Profit_id']})


while True:
    Monitoring_open_Positions(client=client)
    time.sleep(5)
