import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import numpy as np
from datetime import datetime
import os


style = mpf.make_mpf_style(base_mpl_style = 'dark_background',
                            marketcolors  = {
                                'candle': {'up': '#0099ff', 'down': '#969696'},
                                'edge'  : {'up': '#0099ff', 'down': '#969696'},
                                'wick'  : {'up': '#0099ff', 'down': '#969696'},
                                'ohlc'  : {'up': '#0099ff', 'down': '#969696'},
                                'volume': {'up': '#4dc790', 'down': '#fd6b6c'},
                                'vcedge': {'up': '#1f77b4', 'down': '#1f77b4'},
                                'vcdopcod': True,
                                'alpha': 1
                            },
                            #gridstyle = None,
                            y_on_right = True
)

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

        df = df.astype({
          "open":"float64",
          "high":"float64",
          "low":"float64",
          "close":"float64"
        })
        df = df.loc[pattern_data["start_index"]:pattern_data["end_index"]]
        
        
        # عنوان المخطط
        title = f'{symbol}'

        # إعداد المؤامرة (Plot)
        fig, axes = mpf.plot(
            df,
           style=style,
            type='candle',
            figsize=(12, 8),
            returnfig=True,
            title=title,
            tight_layout=True,
            warn_too_much_data = len(df),
            scale_padding = 0.50,
            xrotation = 0
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
