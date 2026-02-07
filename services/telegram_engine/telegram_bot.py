import os
import asyncio
import json
import traceback
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# تأكد من أن هذه المسارات صحيحة في هيكل مشروعك
from shared.database import init_redis, Get_CandleStick, json_serialize
from shared.symbols_loader import symbols
from chart_generator import create_candlestick_chart

# تحميل المتغيرات
TELEGRAM_TOKEN = '8531837646:AAG7OJQ4BvPFrr_Kak9nFL5xQ0mYtD6tKRk'
TELEGRAM_CHAT_ID = '6061081574'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text("🚀 **Crypto Trading Bot is Online!**\nScanning for signals...", parse_mode='Markdown')


async def monitor_signals(application: Application):
    """مهمة خلفية لمراقبة Redis بحثاً عن إشارات جديدة"""
    print("📡 Signal Monitor Started...", flush=True)
    Redis = await init_redis()
    pubsub = Redis.pubsub()

    # الاشتراك في قنوات جميع العملات
    channels = [f"{sym}_Open_Trade" for sym in symbols]
    if not channels:
        print("⚠️ No symbols loaded to subscribe!", flush=True)
        # حتى لو لم توجد رموز، نستمر في الحلقة لعدم إيقاف التاسك
    else:
        await pubsub.subscribe(*channels)
        print(f"✅ Subscribed to {len(channels)} channels.", flush=True)

    while True:
        try:
            # انتظار رسالة (timeout قصير للسماح للحلقة بالعمل)
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            
            if message:
                data_str = message['data']
                if isinstance(data_str, bytes):
                    data_str = data_str.decode('utf-8')

                signal = json.loads(data_str)
                print(f"🔔 Signal Received: {signal}", flush=True)

                symbol = signal.get('symbol')
                if not symbol: continue

                # 1. جلب البيانات التاريخية لرسم الشارت
                candles = await Get_CandleStick(symbol, 300)

                if candles is None or len(candles) == 0:
                    print(f"⚠️ No candle data found for {symbol}")
                    continue

                # 2. إنشاء الصورة
                ts_key = str(int(datetime.now().timestamp()))
                chart_filename = f"chart_{symbol}_{ts_key}.png"
                chart_path = os.path.join("/tmp", chart_filename) 
                os.makedirs("/tmp", exist_ok=True)

                chart_created = create_candlestick_chart(symbol, candles, pattern_data=signal, save_path=chart_path)

                if chart_created:
                  
                    # 5. تنسيق الرسالة
                    side = signal.get('side', 'Unknown')
                    entry = signal.get('entry') or signal.get('Entry_Price')
                    stop = signal.get('stop_loss') or signal.get('Stop_Loss')
                    tp = signal.get('take_profit') or signal.get('Take_Profit')
                    pattern = signal.get('pattern', 'Signal')

                    caption = (
                        f"🚨 **New Open Trade**\n\n"
                        f"🪙 **Pair:** #{symbol}\n"
                        f"📊 **Pattern:** {pattern}\n"
                        f"↕️ **Side:** {side}\n"
                        f"💰 **Entry:** {entry}\n"
                        f"🛑 **Stop Loss:** {stop}\n"
                        f"🎯 **Target:** {tp}\n\n"
                    )

                    # 6. الإرسال
                    if TELEGRAM_CHAT_ID:
                        with open(chart_path, 'rb') as photo:
                            await application.bot.send_photo(
                                chat_id=TELEGRAM_CHAT_ID,
                                photo=photo,
                                caption=caption,
                                parse_mode='Markdown'
                            )
                        os.remove(chart_path)
                    else:
                        print("❌ TELEGRAM_CHAT_ID is not set.")

            await asyncio.sleep(0.1)

        except Exception as e:
            print(f"❌ Monitor Error: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)

async def post_init(application: Application):
    """يتم تشغيل هذه الدالة بمجرد أن يبدأ البوت"""
    # نقوم بإنشاء مهمة غير متزامنة (Task) للمراقب لتعمل في الخلفية
    asyncio.create_task(monitor_signals(application))

def main():
    """نقطة الدخول الرئيسية"""
    if not TELEGRAM_TOKEN:
        print("❌ Error: TELEGRAM_TOKEN environment variable not set.")
        return

    print("🤖 Initializing Bot...", flush=True)
    
    # بناء التطبيق مع إضافة post_init
    # post_init هو المكان الصحيح لتشغيل المهام الخلفية في الإصدارات الحديثة
    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))

    print("✅ Bot is running. Press Ctrl+C to stop.", flush=True)
    
    try:
        # تشغيل البوت بدون وسيط loop
        application.run_polling()
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user.")
    except Exception as e:
        print(f"❌ Fatal Error: {e}")

if __name__ == "__main__":
    main()

