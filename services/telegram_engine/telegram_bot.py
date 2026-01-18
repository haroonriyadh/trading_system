import os
import asyncio
import json
import traceback
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from shared.database import init_redis, Get_CandleStick, json_serialize, json_deserialize
from shared.symbols_loader import symbols
from chart_generator import create_candlestick_chart

# Load environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("❌ Error: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not found in environment variables.")
    # For fail-safety in local dev without env vars, one might exit or warn. 
    # We'll just warn here.

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text("🚀 Crypto Trading Bot is Running!\nWaiting for signals...")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Interactive Buttons (Approve/Reject)"""
    query = update.callback_query
    await query.answer()

    data = query.data
    # data format: "ACTION|SYMBOL|SIDE|TIMESTAMP" (Simpified)
    # But to be safe and stateless, we might just encode indices or a unique ID.
    # For now, let's assume we serialized the minimal necessary info to execute.
    # Or better: Store pending signals in Redis and reference by ID.
    
    # Let's parse the JSON we put in callback_data if it fits, or use a split string
    try:
        action, symbol, side, timestamp_str = data.split("|")
        # timestamp is used to ensure uniqueness or verify expiry
        
        Redis = await init_redis()

        if action == "APPROVE":
            # Reconstruct the order/signal object to send to Execution Engine
            # We need to fetch the full signal details. Since callback_data limit is 64 bytes, 
            # we should have stored the full pending signal in Redis.
            
            signal_key = f"PENDING_SIGNAL:{symbol}:{timestamp_str}"
            signal_data_raw = await Redis.get(signal_key)
            
            if not signal_data_raw:
                await query.edit_message_caption(caption=f"⚠️ Signal Expired or Not Found for {symbol}.")
                return

            signal_data = json.loads(signal_data_raw)
            
            # Prepare payload for Execution Engine
            # Execution Engine expects specific fields like Entry_Price, Stop_Loss, etc.
            # Convert our signal format to what Execution Engine expects if needed.
            # Based on Execution_Engine.py, it expects: Entry_Price, Stop_Loss, Open_time
            
            execution_payload = {
                "symbol": signal_data["symbol"],
                "Side": signal_data["side"],  # Bull/Bear or Long/Short
                "Entry_Price": signal_data["entry"],
                "Stop_Loss": signal_data["stop_loss"],
                "Open_time": datetime.now().isoformat() # Time of approval
            }
            
            # Determine list key (Long/Short) based on side
            side_norm = "Long" if signal_data["side"] in ["Bull", "Long"] else "Short"
            queue_key = f"{symbol}_Open_{side_norm}_Position"
            
            # Push to Redis
            await Redis.lpush(queue_key, json.dumps(json_serialize(execution_payload)))
            
            await query.edit_message_caption(caption=f"✅ Approved & Executed!\nSymbol: {symbol}\nSide: {side_norm}\nEntry: {signal_data['entry']}")
            
            # Clean up pending
            await Redis.delete(signal_key)
            
        elif action == "REJECT":
            signal_key = f"PENDING_SIGNAL:{symbol}:{timestamp_str}"
            await Redis.delete(signal_key)
            await query.edit_message_caption(caption=f"❌ Signal Rejected for {symbol}.")

    except Exception as e:
        print(f"Callback error: {e}")
        traceback.print_exc()
        await query.edit_message_caption(caption=f"⚠️ Error processing request: {e}")


async def monitor_signals(application: Application):
    """Background task to listen for Redis signals"""
    print("📡 Starting Signal Monitor...", flush=True)
    Redis = await init_redis()
    pubsub = Redis.pubsub()
    
    # Subscribe to all symbol signal channels
    channels = [f"{sym}_Trade_Signal" for sym in symbols]
    await pubsub.subscribe(*channels)
    
    print(f"✅ Subscribed to {len(channels)} channels.", flush=True)

    while True:
        try:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                data_str = message['data']
                if isinstance(data_str, bytes):
                    data_str = data_str.decode('utf-8')
                
                signal = json.loads(data_str)
                print(f"🔔 Received Signal: {signal}", flush=True)
                
                # Generate Chart
                symbol = signal['symbol']
                # Fetch recent candles for context (e.g., last 100)
                candles = await Get_CandleStick(symbol, 310)
                
                chart_path = f"/tmp/{symbol}_{int(datetime.now().timestamp())}.png"
                success = create_candlestick_chart(symbol, candles, pattern_data=signal, save_path=chart_path)
                
                if success:
                    # Store signal content in Redis for callback retrieval (No Expiry)
                    # Use a unique ID based on timestamp
                    ts_key = str(int(datetime.now().timestamp()))
                    signal_key = f"PENDING_SIGNAL:{symbol}:{ts_key}"
                    await Redis.set(signal_key, json.dumps(signal))
                    
                    # Prepare Buttons
                    # side field might be "Bull" or "Bear"
                    side_short = "Long" if signal["side"] in ["Bull", "Long"] else "Short"
                    
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Approve", callback_data=f"APPROVE|{symbol}|{side_short}|{ts_key}"),
                            InlineKeyboardButton("❌ Reject", callback_data=f"REJECT|{symbol}|{side_short}|{ts_key}")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    caption = (
                        f"🚨 **New {signal.get('pattern', 'Signal')} Detected**\n\n"
                        f"🪙 **Symbol:** {symbol}\n"
                        f"📈 **Side:** {signal['side']}\n"
                        f"🚪 **Entry:** {signal['entry']}\n"
                        f"🛑 **Stop Loss:** {signal['stop_loss']}\n"
                        f"🎯 **Take Profit:** {signal['take_profit']}\n"
                        f"🕒 **Time:** {signal.get('timestamp')}\n\n"
                        f"Do you want to take this trade?"
                    )
                    
                    # Send to Telegram
                    await application.bot.send_photo(
                        chat_id=TELEGRAM_CHAT_ID,
                        photo=open(chart_path, 'rb'),
                        caption=caption,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                    
                    # Cleanup
                    os.remove(chart_path)
                else:
                    await application.bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=f"⚠️ Signal received for {symbol} but failed to generate chart.\nData: {signal}"
                    )
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            print(f"Error in signal monitor: {e}")
            traceback.print_exc()
            await asyncio.sleep(1)


def main():
    """Main Entry Point for the Bot"""
    if not TELEGRAM_TOKEN:
        return

    # Build Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Get the event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Schedule the background task
    loop.create_task(monitor_signals(application))
    
    # Run the bot (polling)
    print("🤖 Bot is starting polling...", flush=True)
    application.run_polling()

if __name__ == "__main__":
    main()
