from Database import db_candle,db_OB
import requests
import pandas as pd
from symbols import symbols
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import numpy as np


def parse_timeframe(tf: str) -> int:
    """
    يحول الفريم النصي إلى عدد دقائق
    مثال:
    1m -> 1 دقيقة
    5m -> 5 دقائق
    1h -> 60 دقيقة
    4h -> 240 دقيقة
    1d -> 1440 دقيقة
    """
    unit = tf[-1]      # آخر حرف (m/h/d)
    value = int(tf[:-1])  # الرقم قبل الوحدة

    if unit == "m":  # دقائق
        return value
    elif unit == "h":  # ساعات
        return value * 60
    elif unit == "d":  # أيام
        return value * 1440
    else:
        raise ValueError("⚠️ فريم غير مدعوم، استخدم m/h/d فقط")

def next_candle_time(start_time, timeframe_str, n_candles):
    return start_time + timedelta(minutes=parse_timeframe(timeframe_str) * n_candles)

def get_order_block(df):
    
    """
    This Function Take Candle_Data Greter Then 5 Previus Candle 
    """
    
    OB = []
    open_ob_index = set()
    for i in range(len(df)):
        
        #Get Order Block Bullish    
        if i >= 6 and df.iat[i,3] > df.iat[i-2,2]:
            
            if  df.Low.iloc[i-2:i+1].min() == df.iat[i-1,3]:
                if (len(OB) > 0 and OB[-1][2] != df.iat[i-1,3]) or len(OB) == 0:
                    OB.append([1, df.iat[i-1,0], df.iat[i-1,3],df.High.iloc[i-2:i+1].min(),next_candle_time(df.iat[i-1,0],"5m",1000)])                      
                    open_ob_index.add(len(OB)-1)

            elif df.Low.iloc[i-3:i+1].min() == df.iat[i-2,3]:
                if (len(OB) > 0 and OB[-1][2] != df.iat[i-2,3]) or len(OB) == 0:
                    OB.append([1, df.iat[i-2,0], df.iat[i-2,3],df.High.iloc[i-3:i+1].min(),next_candle_time(df.iat[i-2,0],"5m",1000)]) 
                    open_ob_index.add(len(OB)-1)

            elif df.Low.iloc[i-4:i+1].min() == df.iat[i-3,3]:
                if (len(OB) > 0 and OB[-1][2] != df.iat[i-3,3]) or len(OB) == 0:
                    OB.append([1, df.iat[i-3,0], df.iat[i-3,3],df.High.iloc[i-4:i+1].min(),next_candle_time(df.iat[i-3,0],"5m",1000)])
                    open_ob_index.add(len(OB)-1)
            
            elif df.Low.iloc[i-5:i+1].min() == df.iat[i-4,3]:
                if (len(OB) > 0 and OB[-1][2] != df.iat[i-4,3]) or len(OB) == 0:
                    OB.append([1, df.iat[i-4,0], df.iat[i-4,3],df.High.iloc[i-5:i+1].min(),next_candle_time(df.iat[i-4,0],"5m",1000)])
                    open_ob_index.add(len(OB)-1)

        #Get Order Block Bearish    
        elif len(df) >= 6 and df.iat[i,2] < df.iat[i-2,3] :
            
            if  df.High.iloc[i-2:i+1].max() == df.iat[i-1,2]:
                if (len(OB) > 0 and OB[-1][2] != df.iat[i-1,2]) or len(OB) == 0:
                    OB.append([0, df.iat[i-1,0], df.iat[i-1,2],df.Low.iloc[i-2:i+1].max(),next_candle_time(df.iat[i-1,0],"5m",1000)])                      
                    open_ob_index.add(len(OB)-1)
            
            elif df.High.iloc[i-3:i+1].max() == df.iat[i-2,2]:
                if (len(OB) > 0 and OB[-1][2] != df.iat[i-2,2]) or len(OB) == 0:
                    OB.append([0, df.iat[i-2,0], df.iat[i-2,2],df.Low.iloc[i-3:i+1].max(),next_candle_time(df.iat[i-2,0],"5m",1000)]) 
                    open_ob_index.add(len(OB)-1)
            
            elif df.High.iloc[i-4:i+1].max() == df.iat[i-3,2]:
                if (len(OB) > 0 and OB[-1][2] != df.iat[i-3,2]) or len(OB) == 0:
                    OB.append([0, df.iat[i-3,0], df.iat[i-3,2],df.Low.iloc[i-4:i+1].max(),next_candle_time(df.iat[i-3,0],"5m",1000)])
                    open_ob_index.add(len(OB)-1)
            
            elif df.High.iloc[i-5:i+1].max() == df.iat[i-4,2]:
                if (len(OB) > 0 and OB[-1][2] != df.iat[i-4,2]) or len(OB) == 0:
                    OB.append([0, df.iat[i-4,0],df.iat[i-4,2],df.Low.iloc[i-5:i+1].max(),next_candle_time(df.iat[i-4,0],"5m",1000)])
                    open_ob_index.add(len(OB)-1)
        
        to_remove_ob = set()
        for ob in open_ob_index:
            if df.iat[i,0] >= OB[ob][4]:
                to_remove_ob.add(ob)


            elif  OB[ob][0] == 1 and df.iat[i,3] <= OB[ob][3]:           
                to_remove_ob.add(ob)
                

            elif OB[ob][0] == 0 and df.iat[i,2] >= OB[ob][3]:
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
                "timestamp": datetime.fromtimestamp(int(item[0]) / 1000),
                "Open": float(item[1]),
                "High": float(item[2]),
                "Low": float(item[3]),
                "Close": float(item[4]),
                "Volume": float(item[5])
            }

            db_candle[symbol+bar].update_one(
                {"timestamp": candle["timestamp"]},
                {"$set": candle},
                upsert=False
            )
            candles.append(candle)
        print(db_candle.command('count',symbol+bar))

        print(f"✅ تم إدخال {len(candles)} شمعة تاريخية")
    else:
        print("⚠️ لم يتم العثور على بيانات من API")
    
    
    return  pd.DataFrame(reversed(candles))

for symbol in symbols:
    statr = datetime.now()
    df = get_historical_candles(symbol=symbol,bar='5m')
    print(df)
    Order_Block = get_order_block(df)
    for o in Order_Block:
        print(o)
    end = datetime.now()
    print(end-statr)