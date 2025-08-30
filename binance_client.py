from binance.client  import Client
from ticker_rules import rules
from datetime import datetime,timedelta
import time


api_key = "MiQ3oXj2nqX2vZcOE3QO7ZsM3qLYIVtR1IYMl6TExUX88glGNCIjuwETUHKNE6Vy"
api_secret = "25IpcykYfndlVvmIaVPtGEq4fLSelVJSb6bFRl9JI9nHMY4UT0GT1fL7EerwNrhT"
client = Client(api_key=api_key,api_secret=api_secret)


def count_dicimal_places(step):
    return len(format(step,'f').split('.')[1]) if '.' in format(step,'f')  else 0

def format_price(symbol,price):
    return round(price - (price % rules[symbol][0]),count_dicimal_places(rules[symbol][0]))

def format_qty(symbol,qty):
    return  int(qty) if rules[symbol][1] == 1  else round(qty - (qty % rules[symbol][1]),count_dicimal_places(rules[symbol][1]))

def Open_Order(Client:Client, Symbol:str, Side:str ,PositionSide:str ,Type:str ,Qty,Price ,Stop_price):
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

def Take_profit_order(Client:Client, Symbol:str ,Side:str ,PositionSide:str ,Type:str, Take_Profit_price):
    return Client.futures_create_order(symbol = Symbol,
                                        side = Side,
                                        positionSide = PositionSide,
                                        type = Type,
                                        stopPrice = Take_Profit_price,
                                        closePosition = True,
                                        recvWindow = 5000,
                                        timestamp = int(time.time()*1000))

def Stop_loss_order(Client:Client, Symbol:str ,Side:str ,PositionSide:str ,Type:str ,Stop_Loss_price):
    return Client.futures_create_order(symbol = Symbol,
                                        side = Side,
                                        positionSide = PositionSide,
                                        type = Type,
                                        stopPrice = Stop_Loss_price,
                                        closePosition = True,
                                        recvWindow = 5000,
                                        timestamp = int(time.time()*1000))
