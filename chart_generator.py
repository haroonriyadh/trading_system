import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import numpy as np
from datetime import datetime
import os


def create_candlestick_chart(symbol, candles_data, order_block=None, save_path="chart.png"):
    """
    إنشاء مخطط شموع يابانية مع تمييز Order Block
    
    Args:
        symbol: رمز العملة
        candles_data: بيانات الشموع (numpy array)
        order_block: بيانات Order Block (dict)
        save_path: مسار حفظ الصورة
    """
    try:
        # تحويل البيانات إلى DataFrame
        df = pd.DataFrame(candles_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('datetime', inplace=True)
        
        # إعداد الألوان والأنماط
        mc = mpf.make_marketcolors(
            up='#00ff00',      # أخضر للشموع الصاعدة
            down='#ff0000',    # أحمر للشموع الهابطة
            edge='inherit',
            wick={'up': '#00ff00', 'down': '#ff0000'},
            volume='in'
        )
        
        style = mpf.make_mpf_style(
            marketcolors=mc,
            gridstyle='-',
            gridcolor='#404040',
            y_on_right=True,
            facecolor='#1e1e1e',
            edgecolor='#404040',
            figcolor='#1e1e1e',
            axescolor='#404040',
            textcolor='white'
        )
        
        # إعداد المؤامرة
        fig, axes = mpf.plot(
            df,
            type='candle',
            style=style,
            volume=True,
            figsize=(12, 8),
            returnfig=True,
            title=f'{symbol} - Order Block Detection',
            tight_layout=True
        )
        
        # إضافة Order Block إذا كان موجوداً
        if order_block:
            ax = axes[0]
            
            # تحديد موقع Order Block
            ob_time = pd.to_datetime(order_block['Start_Time'], unit='ms')
            ob_entry = order_block['Entry_Price']
            ob_stop = order_block['Stop_Loss']
            
            # رسم خطوط Order Block
            if order_block['Side'] == 'Long':
                color = '#00ff00'
                alpha = 0.3
            else:
                color = '#ff0000'
                alpha = 0.3
            
            # رسم منطقة Order Block
            ax.axhline(y=ob_entry, color=color, linestyle='--', alpha=0.7, linewidth=2)
            ax.axhline(y=ob_stop, color=color, linestyle='-', alpha=0.5, linewidth=1)
            
            # إضافة نص
            ax.text(0.02, 0.98, f"Order Block: {order_block['Side']}\nEntry: {ob_entry:.4f}\nStop: {ob_stop:.4f}", 
                   transform=ax.transAxes, fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor=color, alpha=0.3))
        
        # حفظ الصورة
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='#1e1e1e')
        plt.close()
        
        return True
        
    except Exception as e:
        print(f"Error creating chart: {e}")
        return False


def create_simple_chart(symbol, candles_data, order_block=None, save_path="chart.png"):
    """
    إنشاء مخطط بسيط باستخدام matplotlib
    """
    try:
        # تحويل البيانات
        timestamps = [ts if isinstance(ts,datetime) else datetime.fromtimestamp(ts/1000) for ts in candles_data[:, 0]]
        opens = candles_data[:, 1]
        highs = candles_data[:, 2]
        lows = candles_data[:, 3]
        closes = candles_data[:, 4]
        
        # إنشاء المخطط
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), 
                                      gridspec_kw={'height_ratios': [3, 1]})
        
        # مخطط الشموع
        for i, (ts, o, h, l, c) in enumerate(zip(timestamps, opens, highs, lows, closes)):
            color = 'green' if c >= o else 'red'
            ax1.plot([i, i], [l, h], color='black', linewidth=1)
            ax1.plot([i, i], [o, c], color=color, linewidth=3)
        
        # إضافة Order Block
        if order_block:
            ob_entry = order_block['Entry_Price']
            ob_stop = order_block['Stop_Loss']
            color = 'green' if order_block['Side'] == 'Long' else 'red'
            
            ax1.axhline(y=ob_entry, color=color, linestyle='--', alpha=0.7, linewidth=2)
            ax1.axhline(y=ob_stop, color=color, linestyle='-', alpha=0.5, linewidth=1)
            
            ax1.text(0.02, 0.98, f"Order Block: {order_block['Side']}\nEntry: {ob_entry:.4f}\nStop: {ob_stop:.4f}", 
                    transform=ax1.transAxes, fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor=color, alpha=0.3))
        
        ax1.set_title(f'{symbol} - Order Block Detection')
        ax1.set_ylabel('Price')
        ax1.grid(True, alpha=0.3)
        
        # مخطط الحجم
        volumes = candles_data[:, 5]
        ax2.bar(range(len(volumes)), volumes, color='blue', alpha=0.7)
        ax2.set_ylabel('Volume')
        ax2.set_xlabel('Time')
        ax2.grid(True, alpha=0.3)
        
        # حفظ الصورة
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return True
        
    except Exception as e:
        print(f"Error creating simple chart: {e}")
        return False


if __name__ == "__main__":
    # اختبار المخطط
    test_data = np.array([
        [1640995200000, 100, 105, 95, 102, 1000],
        [1640995260000, 102, 108, 100, 106, 1200],
        [1640995320000, 106, 110, 104, 108, 800],
        [1640995380000, 108, 112, 106, 110, 1500],
        [1640995440000, 110, 115, 108, 113, 2000],
    ])
    
    test_ob = {
        'Side': 'Long',
        'Start_Time': 1640995320000,
        'Entry_Price': 110,
        'Stop_Loss': 108
    }
    
    create_simple_chart('BTCUSDT', test_data, test_ob, 'test_chart.png')
    print("Test chart created: test_chart.png")
