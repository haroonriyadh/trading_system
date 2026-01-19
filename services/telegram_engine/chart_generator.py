import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import numpy as np
from datetime import datetime
import os

def create_candlestick_chart(symbol, candles_data, pattern_data=None, save_path="chart.png"):
    """
    إنشاء مخطط شموع يابانية احترافي مع تمييز مستويات الدخول والأهداف.
    """
    try:
        # تحويل البيانات إلى DataFrame
        # الترتيب المتوقع: timestamp, open, high, low, close, volume
        df = pd.DataFrame(candles_data, columns=['open_time', 'open', 'high', 'low', 'close'])
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('open_time', inplace=True)
        df = df.dropna()
        print(df)

        # عنوان المخطط
        title = f'{symbol}'

        # إعداد المؤامرة (Plot)
        fig, axes = mpf.plot(
            df,
            type='candle',
            figsize=(12, 8),
            returnfig=True,
            title=title,
            tight_layout=True,
            warn_too_much_data=1000
        )

        ax = axes[0]
        # حفظ الصورة
        plt.savefig(save_path, dpi=100, bbox_inches='tight', facecolor='#1e1e1e')
        plt.close() # إغلاق لتحرير الذاكرة
        return True

    except Exception as e:
        print(f"❌ Error creating candlestick chart: {e}")
        import traceback
        traceback.print_exc()
        return False
