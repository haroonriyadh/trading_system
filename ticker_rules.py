from Database import db_candle,db_OB,db_Orders,Nearest_OB_Long,Nearest_OB_Short
from symbols import symbols
# 0 -- tickSize 
# 1 -- minQty 
# 2 -- stepSize 
# 3 -- minNotional 
# 4 -- ticksize 
rules = {'DOGEUSDT': [1e-05, 1.0, 1.0, 5.0, 1e-05], '1000SHIBUSDT': [1e-06, 1.0, 1.0, 5.0, 1e-06], '1000XECUSDT': [1e-05, 1.0, 1.0, 5.0, 1e-05], 'PEOPLEUSDT': [1e-05, 1.0, 1.0, 5.0, 1e-05], '1000LUNCUSDT': [1e-05, 1.0, 1.0, 5.0, 1e-05], '1000PEPEUSDT': [1e-07, 1.0, 1.0, 5.0, 1e-07], '1000FLOKIUSDT': [1e-05, 1.0, 1.0, 5.0, 1e-05], 'MEMEUSDT': [1e-06, 1.0, 1.0, 5.0, 1e-06], '1000BONKUSDT': [1e-06, 1.0, 1.0, 5.0, 1e-06], '1000SATSUSDT': [1e-07, 1.0, 1.0, 5.0, 1e-07], '1000RATSUSDT': [1e-05, 1.0, 1.0, 5.0, 1e-05], 'WIFUSDT': [0.0001, 0.1, 0.1, 5.0, 0.0001], 'MYROUSDT': [1e-05, 1.0, 1.0, 5.0, 1e-05], 'TURBOUSDT': [1e-07, 1.0, 1.0, 5.0, 1e-07], 'MEWUSDT': [1e-06, 1.0, 1.0, 5.0, 1e-06], 'BRETTUSDT': [1e-05, 1.0, 1.0, 5.0, 1e-05], 'POPCATUSDT': [0.0001, 1.0, 1.0, 5.0, 0.0001], 'NEIROETHUSDT': [1e-05, 1.0, 1.0, 5.0, 1e-05], '1MBABYDOGEUSDT': [1e-07, 1.0, 1.0, 5.0, 1e-07], 'NEIROUSDT': [1e-07, 1.0, 1.0, 5.0, 1e-07], '1000CATUSDT': [1e-05, 1.0, 1.0, 5.0, 1e-05], '1000000MOGUSDT': [0.0001, 0.1, 0.1, 5.0, 0.0001], '1000XUSDT': [1e-05, 1.0, 1.0, 5.0, 1e-05], '1000CHEEMSUSDT': [1e-07, 1.0, 1.0, 5.0, 1e-07], '1000WHYUSDT': [1e-07, 1.0, 1.0, 5.0, 1e-07]}


for symbol in symbols:
    #print(type(db_candle[symbol].find({}).to_list()[0]))
    db_candle[symbol].delete_many({})
    db_OB[symbol].delete_many({})

