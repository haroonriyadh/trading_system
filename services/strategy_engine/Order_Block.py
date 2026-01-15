from datetime import datetime, timedelta
import numpy as np
from typing import Union

TS, OPEN, HIGH, LOW, CLOSE = 0, 1, 2, 3, 4

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
    return start_time if isinstance(start_time,datetime) else datetime.fromtimestamp(start_time/1000)+ timedelta(minutes=parse_timeframe(timeframe_str) * n_candles)

def make_order_block(side, ts, entry, stop, frame, limit_to_end):
    return {
        "Side": side,
        "Open_time": ts if isinstance(ts,datetime) else datetime.fromtimestamp(ts/1000),
        "Entry_Price": entry,
        "Stop_Loss": stop,
        "Close_time": next_candle_time(ts, frame, limit_to_end),
        "Mitigated" : 0
    }

def OrderBlock_Detector(df: np.ndarray, frame: str, limit_to_end: int) -> Union[dict, bool]:
    """    
    Return
    -------

                {
                "Side": side,
                "Open_time": ts ,
                "Entry_Price": entry,
                "Stop_Loss": stop,
                "Close_time": Time To End Order Block
            }
    """
    if len(df) < 6:
        return False
    
    # Bullish
    if df[-1, LOW] > df[-3, HIGH]:
        checks = [
            (-2, df[-3:, LOW].min() == df[-2, LOW], df[-3:, HIGH].min(), df[-2, LOW]),
            (-3, df[-4:, LOW].min() == df[-3, LOW], df[-4:, HIGH].min(), df[-3, LOW]),
            (-4, df[-5:, LOW].min() == df[-4, LOW], df[-5:, HIGH].min(), df[-4, LOW]),
            (-5, df[-6:, LOW].min() == df[-5, LOW], df[-6:, HIGH].min(), df[-5, LOW]),
        ]
        for idx, cond, entry, stop in checks:
            if cond:
                return make_order_block("Long", df[idx, TS], entry, stop, frame, limit_to_end)
    
    # Bearish
    elif df[-1, HIGH] < df[-3, LOW]:
        checks = [
            (-2, df[-3:, HIGH].max() == df[-2, HIGH], df[-3:, LOW].max(), df[-2, HIGH]),
            (-3, df[-4:, HIGH].max() == df[-3, HIGH], df[-4:, LOW].max(), df[-3, HIGH]),
            (-4, df[-5:, HIGH].max() == df[-4, HIGH], df[-5:, LOW].max(), df[-4, HIGH]),
            (-5, df[-6:, HIGH].max() == df[-5, HIGH], df[-6:, LOW].max(), df[-5, HIGH]),
        ]
        for idx, cond, entry, stop in checks:
            if cond:
                return make_order_block("Short", df[idx, TS], entry, stop, frame, limit_to_end)

    return False