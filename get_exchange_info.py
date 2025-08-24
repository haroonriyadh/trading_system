from binance.client import Client
import math
import pandas as pd
import ast
from decimal import Decimal
from Database import mongo_client,db,db_OB,db_Orders


'''
for symbol in db_OB.list_collection_names():
    db_OB[symbol].drop_indexes()
    db_OB[symbol].create_index([('Distance', 1)])

    print(f'Done Create Index for {symbol}')
'''
#print(db_Orders['Open_Orders'].count_documents({'status':'FILLED'}))
'''
rules = {}
api_key = "MiQ3oXj2nqX2vZcOE3QO7ZsM3qLYIVtR1IYMl6TExUX88glGNCIjuwETUHKNE6Vy"
api_secret = "25IpcykYfndlVvmIaVPtGEq4fLSelVJSb6bFRl9JI9nHMY4UT0GT1fL7EerwNrhT"
client = Client(api_key=api_key,api_secret=api_secret)
exchange = client.futures_exchange_info()
for symbol in exchange['symbols']:
    if symbol['symbol'].endswith('USDT') and (symbol['underlyingSubType'] == ['Meme'] or symbol['symbol'].startswith('1000')) and\
       symbol['status'] == 'TRADING':
        tickSize = float(symbol['filters'][0]['tickSize'])
        minQty =   float(symbol['filters'][2]['minQty'])
        stepSize = float(symbol['filters'][2]['stepSize'])
        minNotional = float(symbol['filters'][5]['notional'])
        ticksize = float(symbol['filters'][0]['tickSize'])
        rules[symbol['symbol']] = [tickSize, minQty, stepSize, minNotional,ticksize]
        print(rules[symbol['symbol']])
    
with open('d:/trading_system/ticker_rules.py', 'w') as f:
    f.write('# 0 -- tickSize \n# 1 -- minQty \n# 2 -- stepSize \n# 3 -- minNotional \n# 4 -- ticksize \nrules = '+str(rules))

with open('d:/trading_system/symbols.py', 'w') as f:
    f.write('symbols = '+str(list(rules.keys())))
'''

