import os
import asyncio
import json
import traceback
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# تأكد من أن هذه المسارات صحيحة في هيكل مشروعك
from shared.database import init_redis, Get_CandleStick, json_serialize,json_deserialize
from shared.symbols_loader import symbols
from chart_generator import create_candlestick_chart

# تحميل المتغيرات
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text("🚀 **Crypto Trading Bot is Online!**\nScanning for signals...", parse_mode='Markdown')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأزرار التفاعلية (موافقة/رفض)"""
    query = update.callback_query
    await query.answer() # لإيقاف أيقونة التحميل في تيليجرام

    try:
        # data format: "ACTION|SYMBOL|TIMESTAMP_KEY"
        parts = query.data.split("|")
        if len(parts) < 3:
            return

        action, symbol, ts_key = parts[0], parts[1], parts[2]
        
        Redis = await init_redis()
        signal_key = f"PENDING_SIGNAL:{symbol}:{ts_key}"
        
        # استرجاع بيانات الإشارة الأصلية
        signal_data_raw = await Redis.get(signal_key)

        if not signal_data_raw:
            await query.edit_message_caption(caption=f"⚠️ Signal Expired or Not Found for {symbol}.")
            return

        signal_data = json.loads(signal_data_raw)
        side = signal_data.get('side', 'Long')
        
        # توحيد صيغة Side (Long/Short)
        normalized_side = "Long" if side in ["Bull", "Long", "BUY"] else "Short"

        if action == "APPROVE":
            # إعداد حمولة التنفيذ (Payload) لمحرك التنفيذ
            execution_payload = {
                "symbol": symbol,
                "Side": normalized_side,
                "Entry_Price": signal_data.get('entry') or signal_data.get('Entry_Price'),
                "Stop_Loss": signal_data.get('stop_loss') or signal_data.get('Stop_Loss'),
                "Take_Profit": signal_data.get('take_profit') or signal_data.get('Take_Profit'),
                "Quantity": "USER_DEFINED", # يمكن تعديل هذا لاحقاً
                "Open_time": datetime.now().isoformat()
            }

            # إرسال إلى طابور التنفيذ
            queue_key = f"{symbol}_Open_{normalized_side}_Position"
            
            # نستخدم json_serialize لضمان توافق الأنواع (مثل datetime)
            await Redis.lpush(queue_key, json.dumps(json_serialize(execution_payload)))

            # تحديث الرسالة للمستخدم
            success_msg = (
                f"✅ **Order Approved & Sent!**\n"
                f"🪙 {symbol} ({normalized_side})\n"
                f"🚀 Entry: {execution_payload['Entry_Price']}"
            )
            await query.edit_message_caption(caption=success_msg, parse_mode='Markdown')

            # حذف الإشارة المعلقة لمنع التكرار
            await Redis.delete(signal_key)

        elif action == "REJECT":
            await Redis.delete(signal_key)
            await query.edit_message_caption(caption=f"❌ **Signal Rejected** for {symbol}.", parse_mode='Markdown')

    except Exception as e:
        print(f"Callback Error: {e}")
        traceback.print_exc()
        await query.edit_message_caption(caption=f"⚠️ Error processing request: {str(e)}")


async def monitor_signals(application: Application):
    """مهمة خلفية لمراقبة Redis بحثاً عن إشارات جديدة"""
    print("📡 Signal Monitor Started...", flush=True)
    Redis = await init_redis()
    pubsub = Redis.pubsub()

    # الاشتراك في قنوات جميع العملات
    channels = [f"{sym}_Trade_Signal" for sym in symbols]
    if not channels:
        print("⚠️ No symbols loaded to subscribe!", flush=True)
        return

    await pubsub.subscribe(*channels)
    print(f"✅ Subscribed to {len(channels)} channels.", flush=True)

    async for message in pubsub.listen():
        try:
            if message:
                data_str = message['data']
                if isinstance(data_str, bytes):
                    data_str = data_str.decode('utf-8')

                signal = json.loads(data_str)
                print(f"🔔 Signal Received: {signal}", flush=True)

                symbol = signal.get('symbol')
                if not symbol: continue

                # 1. جلب البيانات التاريخية لرسم الشارت
                # نفترض أن الدالة تعيد آخر 100-300 شمعة
                candles = await Get_CandleStick(symbol, 300)

                if candles is None or len(candles) == 0:
                    print(f"⚠️ No candle data found for {symbol}")
                    continue

                # 2. إنشاء الصورة
                ts_key = str(int(datetime.now().timestamp()))
                chart_filename = f"chart_{symbol}_{ts_key}.png"
                chart_path = os.path.join("/tmp", chart_filename) # يفضل استخدام مسار مؤقت
                
                # تأكد من وجود مجلد tmp
                os.makedirs("/tmp", exist_ok=True)

                chart_created = create_candlestick_chart(symbol, candles, pattern_data=signal, save_path=chart_path)

                if chart_created:
                    # 3. حفظ الإشارة في Redis لانتظار الموافقة (صلاحية 1 ساعة)
                    signal_key = f"PENDING_SIGNAL:{symbol}:{ts_key}"
                    await Redis.setex(signal_key, 3600, json.dumps(signal))

                    # 4. إعداد الأزرار
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Approve", callback_data=f"APPROVE|{symbol}|{ts_key}"),
                            InlineKeyboardButton("❌ Reject", callback_data=f"REJECT|{symbol}|{ts_key}")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    # 5. تنسيق الرسالة
                    side = signal.get('side', 'Unknown')
                    entry = signal.get('entry') or signal.get('Entry_Price')
                    stop = signal.get('stop_loss') or signal.get('Stop_Loss')
                    tp = signal.get('take_profit') or signal.get('Take_Profit')
                    pattern = signal.get('pattern', 'Signal')

                    caption = (
                        f"🚨 **New Opportunity Detected**\n\n"
                        f"🪙 **Pair:** #{symbol}\n"
                        f"📊 **Pattern:** {pattern}\n"
                        f"↕️ **Side:** {side}\n"
                        f"💰 **Entry:** {entry}\n"
                        f"🛑 **Stop Loss:** {stop}\n"
                        f"🎯 **Target:** {tp}\n\n"
                        f"⚡ *Action Required: Approve to Execute*"
                    )

                    # 6. الإرسال
                    if TELEGRAM_CHAT_ID:
                        with open(chart_path, 'rb') as photo:
                            await application.bot.send_photo(
                                chat_id=TELEGRAM_CHAT_ID,
                                photo=photo,
                                caption=caption,
                                parse_mode='Markdown',
                                reply_markup=reply_markup
                            )
                        
                        # حذف الصورة بعد الإرسال
                        os.remove(chart_path)
                    else:
                        print("❌ TELEGRAM_CHAT_ID is not set.")

            # انتظار قصير جداً لعدم استهلاك المعالج
            await asyncio.sleep(0.1)

        except Exception as e:
            print(f"❌ Monitor Error: {e}")
            traceback.print_exc()
            await asyncio.sleep(5) # انتظار أطول عند الخطأ

def main():
    """نقطة الدخول الرئيسية"""
    if not TELEGRAM_TOKEN:
        print("❌ Error: TELEGRAM_TOKEN environment variable not set.")
        return

    print("🤖 Initializing Bot...", flush=True)
    
    # بناء التطبيق
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # الحصول على حلقة الأحداث الحالية
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # جدولة مهمة المراقبة لتعمل بالتوازي مع البوت
    # ملاحظة: run_polling ستقوم بتشغيل الحلقة، لذا نضيف المهمة قبلها
    loop.create_task(monitor_signals(application))

    print("✅ Bot is running. Press Ctrl+C to stop.", flush=True)
    
    try:
        # تشغيل البوت (هذه الدالة حاجبة Blocking وستدير الحلقة)
        application.run_polling(loop=loop)
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user.")
    except Exception as e:
        print(f"❌ Fatal Error: {e}")

if __name__ == "__main__":
    main()

