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
        df = pd.DataFrame(candles_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('datetime', inplace=True)

        # إعداد الألوان (Dark Theme)
        mc = mpf.make_marketcolors(
            up='#00ff00',      # أخضر للصعود
            down='#ff0000',    # أحمر للهبوط
            edge='inherit',
            wick={'up': '#00ff00', 'down': '#ff0000'},
            volume='in'
        )

        style = mpf.make_mpf_style(
            marketcolors=mc,
            gridstyle=':',
            gridcolor='#404040',
            y_on_right=True,
            facecolor='#1e1e1e',
            edgecolor='#404040',
            figcolor='#1e1e1e',
            axescolor='#404040',
            textcolor='white'
        )

        # عنوان المخطط
        pattern_name = pattern_data.get('pattern', 'Analysis') if pattern_data else 'Analysis'
        title = f'{symbol} - {pattern_name}'

        # إعداد المؤامرة (Plot)
        fig, axes = mpf.plot(
            df,
            type='candle',
            style=style,
            volume=True,
            figsize=(12, 8),
            returnfig=True,
            title=title,
            tight_layout=True,
            warn_too_much_data=1000
        )

        ax = axes[0] # المحور الرئيسي للسعر

        if pattern_data:
            # استخراج البيانات بمرونة (سواء كانت المفاتيح صغيرة أو كبيرة)
            entry = pattern_data.get('entry') or pattern_data.get('Entry_Price')
            stop = pattern_data.get('stop_loss') or pattern_data.get('Stop_Loss')
            tp = pattern_data.get('take_profit') or pattern_data.get('Take_Profit')
            side = pattern_data.get('side') or pattern_data.get('Side')

            # تحديد لون الخطوط بناءً على الاتجاه
            is_long = side in ['Bull', 'Long', 'BUY']
            line_color = '#00ff00' if is_long else '#ff0000'

            # رسم الخطوط الأفقية
            if entry:
                ax.axhline(y=float(entry), color='white', linestyle='--', alpha=0.9, linewidth=1.5, label='Entry')
            if stop:
                ax.axhline(y=float(stop), color='#ff4444', linestyle='-', alpha=0.8, linewidth=1.5, label='Stop Loss')
            if tp:
                ax.axhline(y=float(tp), color='#00ff00', linestyle='-', alpha=0.8, linewidth=1.5, label='Take Profit')

            # إضافة مربع معلومات (Text Box)
            info_text = f"Pattern: {pattern_name}\nSide: {side}\nEntry: {entry}"
            if stop: info_text += f"\nSL: {stop}"
            if tp: info_text += f"\nTP: {tp}"

            ax.text(0.02, 0.98, info_text,
                   transform=ax.transAxes, fontsize=11, verticalalignment='top', color='white',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='#333333', alpha=0.9, edgecolor='#555555'))

        # حفظ الصورة
        plt.savefig(save_path, dpi=100, bbox_inches='tight', facecolor='#1e1e1e')
        plt.close() # إغلاق لتحرير الذاكرة
        return True

    except Exception as e:
        print(f"❌ Error creating candlestick chart: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_simple_chart(symbol, candles_data, order_block=None, save_path="chart.png"):
    """
    مخطط بسيط بديل في حال فشل mplfinance أو للاستخدام السريع
    """
    try:
        timestamps = [ts if isinstance(ts, datetime) else datetime.fromtimestamp(ts/1000) for ts in candles_data[:, 0]]
        opens = candles_data[:, 1]
        highs = candles_data[:, 2]
        lows = candles_data[:, 3]
        closes = candles_data[:, 4]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
        fig.patch.set_facecolor('#1e1e1e')
        ax1.set_facecolor('#1e1e1e')
        ax2.set_facecolor('#1e1e1e')

        # رسم الشموع يدوياً
        for i, (o, h, l, c) in enumerate(zip(opens, highs, lows, closes)):
            color = '#00ff00' if c >= o else '#ff0000'
            ax1.plot([timestamps[i], timestamps[i]], [l, h], color=color, linewidth=1)
            ax1.plot([timestamps[i], timestamps[i]], [o, c], color=color, linewidth=4)

        if order_block:
            ob_entry = order_block.get('Entry_Price')
            ob_stop = order_block.get('Stop_Loss')
            side = order_block.get('Side')
            
            if ob_entry and ob_stop:
                color = 'green' if side == 'Long' else 'red'
                ax1.axhline(y=ob_entry, color=color, linestyle='--', alpha=0.7, label='Entry')
                ax1.axhline(y=ob_stop, color='red', linestyle='-', alpha=0.5, label='SL')

        ax1.set_title(f'{symbol} - Simple View', color='white')
        ax1.tick_params(axis='x', colors='white')
        ax1.tick_params(axis='y', colors='white')
        ax1.grid(True, alpha=0.1)

        # الحجم
        volumes = candles_data[:, 5]
        ax2.bar(timestamps, volumes, color='#0088ff', alpha=0.5)
        ax2.tick_params(axis='x', colors='white')
        ax2.tick_params(axis='y', colors='white')

        plt.tight_layout()
        plt.savefig(save_path, dpi=100, bbox_inches='tight', facecolor='#1e1e1e')
        plt.close()
        return True

    except Exception as e:
        print(f"❌ Error creating simple chart: {e}")
        return False

# كتلة الاختبار
if __name__ == "__main__":
    test_data = np.array([
        [1640995200000, 40000, 41000, 39500, 40500, 1000],
        [1640995260000, 40500, 40800, 40200, 40300, 1200],
        [1640995320000, 40300, 41500, 40200, 41200, 800],
        [1640995380000, 41200, 42000, 41100, 41800, 1500],
    ])

    test_pattern = {
        'pattern': 'Bull Flag',
        'side': 'Long',
        'entry': 41800,
        'stop_loss': 40300,
        'take_profit': 43000
    }

    print("Generating test chart...")
    create_candlestick_chart('BTCUSDT', test_data, test_pattern, 'test_chart.png')
    print("✅ Test chart created: test_chart.png")

