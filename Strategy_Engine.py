from Database import db_candle,db_OB,db_Orders,Redis
from Order_Block import OrderBlock_Detector
from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor,as_completed
import time
from symbols import symbols
import numpy as np


def Get_CandelStick(symbol:str,limit:int) -> np.ndarray:

    data_candle:list[dict] = db_candle[symbol].aggregate([{"$project": {"_id": 0},'$sort':{'Open_time':-1}}]).to_list(limit)
    
    return np.array([candle.values() for  candle in data_candle],dtype=object)

last_ob_in_symbols = {symbol:{} for symbol in symbols}

def worker(symbol):
    while True:
        Redis.brpop(f"queue:{symbol}_Close_Candle", 0)
        OB = OrderBlock_Detector(Get_CandelStick(symbol,7))
        if isinstance(OB,dict) and OB != last_ob_in_symbols[symbol]:
            db_OB[symbol].insert_one(OB)
            print(f"System Find Order Block in {symbol} at {OB["Start_Time"]}")
            last_ob_in_symbols[symbol] = OB

        else:
            print(f"System Not Find Order Block in {symbol}")
        

if __name__ == "__main__":
    # ThreadPoolExecutor لتشغيل Workers بالتوازي
    with ThreadPoolExecutor(max_workers=len(symbols)) as executor:
        futures = [executor.submit(worker, sym) for sym in symbols]

        # نخلي البرنامج يشتغل باستمرار
        for f in futures:
            f.result()



