import asyncio
import numpy as np
import traceback
import json
from symbols import symbols
from datetime import datetime
from Database import (
    db_candle,
    db_indicitors,
    init_redis,
    json_serialize,
    json_deserialize,
    Get_Candlestick
)

# Candle Columns
OPEN_TIME = 0
OPEN = 1
HIGH = 2
LOW = 3
CLOSE = 4

WINDOW = 5 # Window for High/Low detection


async def Get_Last_HL(symbol: str, limit: int = 2) -> list:
    results = await db_indicitors[symbol].find({}, {"_id": 0}).sort("Open_time", -1).limit(limit).to_list(limit)
    return results[::-1] # chronological order

async def Detect_Highs_Lows(symbol: str):
    Redis = await init_redis()
    
    while True:
        try:
            # Wait for signal that a new candle is closed
            await Redis.brpop(f"{symbol}_Close_Candle", 0)
            
            # Fetch data (we need at least WINDOW + 1 candles)
            df = await Get_Candlestick(symbol, 20)
            if len(df) < WINDOW + 1:
                continue
                
            # Current index to check is the last closed candle (len(df) - 1)
            i = len(df) - 1
            current_time = df[i, OPEN_TIME]
            
            # Get existing HL state from MongoDB
            last_hls = await Get_Last_HL(symbol)
            
            # Format: [{"Open_time": datetime, "Price": ..., "Type": ...}]
            new_hl = None
            
            # Check for a candle that has reached a high
            if df[i, HIGH] == df[i-WINDOW : i+1, HIGH].max():
                # If no previous or last was a low
                if not last_hls or last_hls[-1]["Type"] == 0:
                    new_hl = {
                        "Open_time": datetime.fromtimestamp(current_time/1000), 
                        "Price": float(df[i, HIGH]), 
                        "Type": 1, 
                        "Side": "High"
                    }
                # If last was a high and current high is higher, update it
                elif last_hls[-1]["Type"] == 1 and df[i, HIGH] > last_hls[-1]["Price"]:
                    await db_indicitors[symbol].update_one(
                        {"Open_time": last_hls[-1]["Open_time"]},
                        {"$set": {
                            "Open_time": datetime.fromtimestamp(current_time/1000), 
                            "Price": float(df[i, HIGH])
                        }}
                    )
                    await Redis.publish(f"{symbol}_HL_Updated", json.dumps({"symbol": symbol, "type": "update", "side": "High"}))
                    print(f"[{symbol}] Updated Higher High at {df[i, HIGH]}")

            # Check for a candle that has reached a low
            elif df[i, LOW] == df[i-WINDOW:i+1, LOW].min():
                # If no previous or last was a high
                if not last_hls or last_hls[-1]["Type"] == 1:
                    new_hl = {
                        "Open_time": datetime.fromtimestamp(current_time/1000), 
                        "Price": float(df[i, LOW]), 
                        "Type": 0, 
                        "Side": "Low"
                    }
                # If last was a low and current low is lower, update it
                elif last_hls[-1]["Type"] == 0 and df[i, LOW] < last_hls[-1]["Price"]:
                    await db_indicitors[symbol].update_one(
                        {"Open_time": last_hls[-1]["Open_time"]},
                        {"$set": {
                            "Open_time": datetime.fromtimestamp(current_time/1000), 
                            "Price": float(df[i, LOW])
                        }}
                    )
                    await Redis.publish(f"{symbol}_HL_Updated", json.dumps({"symbol": symbol, "type": "update", "side": "Low"}))
                    print(f"[{symbol}] Updated Lower Low at {df[i, LOW]}")

            if new_hl:
                await db_indicitors[symbol].insert_one(new_hl)
                await Redis.publish(f"{symbol}_HL_Updated", json.dumps({"symbol": symbol, "type": "new", "side": new_hl["Side"]}))
                print(f"[{symbol}] Detected New {new_hl['Side']} at {new_hl['Price']}")

        except Exception as e:
            print(f"Error in Detect_Highs_Lows for {symbol}: {e}")
            print(traceback.format_exc())
            await asyncio.sleep(1)

async def worker_wrapper(fn, symbol):
    while True:
        try:
           await fn(symbol)
        except Exception:
            print(traceback.format_exc())
            await asyncio.sleep(5)

async def main():
    tasks = []
    print(f"Starting Highs/Lows Indicator for {len(symbols)} symbols...")
    for sym in symbols:
        tasks.append(asyncio.create_task(worker_wrapper(Detect_Highs_Lows, sym)))
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())

