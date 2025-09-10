from Database import db_candle,db_OB
import requests
import pandas as pd
from symbols import symbols
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import numpy as np
from Order_Block import OrderBlock_Detector


def Get_order_block(df:pd.DataFrame):
    
    """
    This Function Take Candle_Data Greter Then 5 Previus Candle 
    """
    
    OB = []
    open_ob_index = set()
    for i in range(5,len(df)):
        
        #start = time.perf_counter()
        #Get Order Block 
        
        Ob = OrderBlock_Detector(df.iloc[i-5:i+1].values,"5m",1000)
        
        if Ob != False and Ob not in OB:
            #print(Ob)
            OB.append(Ob)
            open_ob_index.add(len(OB)-1)

        #print(time.perf_counter()-start)
        
        to_remove_ob = set()
        for ob in open_ob_index:
            if datetime.fromtimestamp(df.iat[i,0]/1000) >= OB[ob]["End_Time"]:
                to_remove_ob.add(ob)


            elif  OB[ob]["Side"] == "Long" and df.iat[i,3] <= OB[ob]["Entry_Price"]:           
                to_remove_ob.add(ob)
                

            elif OB[ob]["Side"] == "Short" and df.iat[i,2] >= OB[ob]["Entry_Price"]:
                to_remove_ob.add(ob)

        for f in to_remove_ob:
            open_ob_index.difference_update(to_remove_ob)

    
    return [OB[i] for i in open_ob_index]

def get_historical_candles(symbol,bar):
    url = "https://www.okx.com/api/v5/market/candles"
    params = {
        "instId": symbol,
        "bar": bar,   # شمعة دقيقة واحدة
        "limit": "300"
    }
    response = requests.get(url, params=params)
    data = response.json()

    if "data" in data:
        candles = []
        for item in data["data"]:
            candle = {
                "Open_Time": int(item[0]),
                "Open": float(item[1]),
                "High": float(item[2]),
                "Low": float(item[3]),
                "Close": float(item[4]),
                "Volume": float(item[5])
            }

            db_candle[symbol+bar].insert_one(
                {"Open_Time": candle["Open_Time"]},
                {"$set": candle}
            )
            candles.append(candle)


        print(f"✅ تم إدخال {len(candles)} شمعة تاريخية")
    else:
        print("⚠️ لم يتم العثور على بيانات من API")
    
    
    return  pd.DataFrame(reversed(candles))

symbols = ["WLD-USDT-SWAP","LPT-USDT-SWAP"]

for symbol in symbols:
    df = get_historical_candles(symbol=symbol,bar='5m')
    print(df)
    Order_Block = Get_order_block(df)
    for o in Order_Block:
        print(o)