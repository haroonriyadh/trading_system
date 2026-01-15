import asyncio
import numpy as np
import traceback
import json
from datetime import datetime
from symbols import symbols
from Database import (
    db_candle,
    db_indicitors,
    init_redis,
    json_serialize,
    json_deserialize
)

# Candle Columns
OPEN_TIME = 0
OPEN = 1
HIGH = 2
LOW = 3
CLOSE = 4
SOFT = CLOSE

def Trend_Regression(x:np.ndarray,y:np.ndarray):
    N = len(x)
    sx = x.sum()
    sy = y.sum()
    sxx = (x * x).sum()
    syy = (y * y).sum()
    sxy = (x * y).sum()

    m = (N*sxy - sx*sy) / (N*sxx - sx*sx)
    b = (sy - m*sx) / N
    r = (N*sxy - sx*sy) / (((N*sxx - sx*sx) * (N*syy - sy*sy)) ** 0.5 + 1e-9)

    mid_line = m*x + b
    sigma = (((y - mid_line)**2).sum() / N) ** 0.5

    upper_trendline = mid_line + (sigma * 2)
    lower_trendline = mid_line - (sigma * 2)

    return m, b, r, sigma, mid_line, upper_trendline, lower_trendline

def FlagPatternConditions(
        df:np.ndarray,
        i:int,
        HL_raw:np.ndarray,
        Flag_Range:int = 360,
        FlagRatioMin:float = 0.50,
        FlagRatioMax:float = 6
):
    Pattern = {
        "Side" : 0,
        "StartIndex" : 0,
        "EndIndex" : 0,
        "StopLoss" : 0,
        "HeadIndex" : 0,
        "UpperLine":[],
        "LowerLine":[],
        "MidLine":[],
        "FlagRatio":0,
        "correlation":0
    }

    if len(HL_raw) <= 5:
        return Pattern
    
    # Map timestamps to indices
    time_to_idx = {int(t): idx for idx, t in enumerate(df[:, OPEN_TIME])}
    
    HL_idx = []
    for h in HL_raw:
        t = int(h[0])
        if t in time_to_idx:
            HL_idx.append([time_to_idx[t], h[1], h[2]])
    
    if len(HL_idx) < 5:
        return Pattern
        
    HL = np.array(HL_idx)
    
    index = -5
    Range_Candle = i - HL[index,0]

    while Flag_Range > Range_Candle:
        if Range_Candle < 5:
            if abs(index - 1) < len(HL):
                index -= 1
                Range_Candle = i - HL[index,0]
                continue
            else:
                break
        
        HP = HL[index:, 1].max() # High Price
        LP = HL[index:, 1].min() # Low Price
        
        HI_pos = HL[index:, 1].argmax()
        LI_pos = HL[index:, 1].argmin()
        
        HI = int(HL[HI_pos + (index + len(HL)), 0]) # High Index
        LI = int(HL[LI_pos + (index + len(HL)), 0]) # Low Index
        
        Start_Price = HL[index, 1]  
        Start_Index = int(HL[index, 0])
        Start_Type = int(HL[index, 2])
        
        Last_Price = HL[-1, 1]
        Last_Type = int(HL[-1, 2])

        # Validate Bull Flag 
        if Start_Type == 0 and HP != Last_Price and LP == Start_Price and HI > Start_Index and \
           FlagRatioMin < ((i - HI) / (HI - Start_Index)) < FlagRatioMax and \
           Last_Type == 1 and LP < HL[HI_pos + (index + len(HL)):, 1].min() and \
           (i - (df[HI:i+1, LOW].argmin() + HI)) < ((df[HI:i+1, LOW].argmin() + HI) - HI):

            _, _, corr_long, _, mid_long, upper_long, lower_long = Trend_Regression(np.arange(HI, i+1), df[HI:i+1, SOFT])
            _, _, _, _, _, upper_long_shift_1, _ = Trend_Regression(np.arange(HI, i), df[HI:i, SOFT])
            
            if df[i, CLOSE] > upper_long[-1] and df[i-1, CLOSE] < upper_long_shift_1[-1]:
                Pattern["Side"] = "Bull"
                Pattern["StartIndex"] = Start_Index
                Pattern["EndIndex"] = i+1
                Pattern["TakeProfit"] = float(df[HI, HIGH])
                Pattern["StopLoss"] = float(df[HI:i+1, LOW].min())
                Pattern["HeadIndex"] = HI
                return Pattern

        # Validate Bear Flag 
        elif Start_Type == 1 and LP != Last_Price and HP == Start_Price and LI > Start_Index and \
             FlagRatioMin < ((i - LI) / (LI - Start_Index)) < FlagRatioMax and \
             Last_Type == 0 and HP > HL[LI_pos + (index + len(HL)):, 1].max() and \
             (i - (df[LI:i+1, HIGH].argmax() + LI)) < ((df[LI:i+1, HIGH].argmax() + LI) - LI):
            
            _, _, corr_short, _, mid_short, upper_short, lower_short = Trend_Regression(np.arange(LI, i+1), df[LI:i+1, SOFT]) 
            _, _, _, _, _, _, lower_short_shift_1 = Trend_Regression(np.arange(LI, i), df[LI:i, SOFT]) 
            
            if df[i, CLOSE] < lower_short[-1] and df[i-1, CLOSE] > lower_short_shift_1[-1]:
                Pattern["Side"] = "Bear"
                Pattern["StartIndex"] = Start_Index
                Pattern["EndIndex"] = i+1
                Pattern["TakeProfit"] = float(df[LI, LOW])
                Pattern["StopLoss"] = float(df[LI:i+1, HIGH].max())
                Pattern["HeadIndex"] = LI
                return Pattern

        if abs(index - 1) < len(HL):
            index -= 1
            Range_Candle = i - HL[index, 0]
        else:
            break

    return Pattern

async def Get_Candlestick(symbol: str, limit: int = 500) -> np.ndarray:
    try:
        cursor = await db_candle[symbol].find({}, {"_id": 0}).sort("Open_time", -1).limit(limit).to_list(limit)
        if not cursor:
            return np.array([])
        data = []
        for c in cursor:
            # Convert datetime to millisecond timestamp
            dt = c.get("Open_time")
            ts = int(dt.timestamp() * 1000)
            data.append([ts, float(c.get("Open")), float(c.get("High")), float(c.get("Low")), float(c.get("Close"))])
        return np.array(data)[::-1]
    except Exception as e:
        print(f"Error in Get_Candlestick for {symbol}: {e}")
        return np.array([])

async def Get_HL_Points(symbol: str, limit: int = 30) -> np.ndarray:
    try:
        results = await db_indicitors[symbol].find({}, {"_id": 0}).sort("Open_time", -1).limit(limit).to_list(limit)
        if not results:
            return np.array([])
        data = []
        for h in results:
            dt = h.get("Open_time")
            ts = int(dt.timestamp() * 1000)
            data.append([ts, float(h["Price"]), int(h["Type"])])
        return np.array(data)[::-1]
    except Exception as e:
        print(f"Error in Get_HL_Points for {symbol}: {e}")
        return np.array([])

async def Flag_Pattern_Worker(symbol: str):
    Redis = await init_redis()
    pubsub = Redis.pubsub()
    await pubsub.subscribe(f"{symbol}_HL_Updated")
    
    print(f"[{symbol}] Flag Pattern Worker started.")
    
    async for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                df = await Get_Candlestick(symbol)
                HL = await Get_HL_Points(symbol)
                
                if len(df) < 50 or len(HL) < 5:
                    continue
                    
                i = len(df) - 1
                pattern = FlagPatternConditions(df, i, HL)
                
                if pattern["Side"] != 0:
                    signal = {
                        "symbol": symbol,
                        "side": pattern["Side"],
                        "entry": float(df[i, CLOSE]),
                        "stop_loss": pattern["StopLoss"],
                        "take_profit": pattern["TakeProfit"],
                        "pattern": "Flag Pattern",
                        "timestamp": int(df[i, OPEN_TIME])
                    }
                    await Redis.publish(f"{symbol}_Trade_Signal", json.dumps(signal))
                    print(f"🔥 [{symbol}] FLAG PATTERN DETECTED: {pattern['Side']} | Entry: {signal['entry']}")
                    
            except Exception as e:
                print(f"Error in Flag_Pattern_Worker for {symbol}: {e}")
                traceback.print_exc()

async def main():
    await init_redis()
    tasks = []
    print(f"Starting Flag Pattern Strategy for {len(symbols)} symbols...")
    for sym in symbols:
        tasks.append(asyncio.create_task(Flag_Pattern_Worker(sym)))
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
