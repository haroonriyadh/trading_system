import asyncio
import json
import logging
from datetime import datetime
import traceback
import websockets
from Database import db_candle, json_serialize, init_redis
from symbols import symbols

logging.basicConfig(
    filename='logfile_multi_kline_async.log',
    level=logging.ERROR,
    format='%(asctime)s %(levelname)s %(message)s'
)

connected_clients = set()

# Time Frames
intervals = [1]
topics = [f"kline.{interval}.{symbol}" for symbol in symbols for interval in intervals]

# -------------------------
# Handle incoming WebSocket messages
# -------------------------
async def handle_message(message, Redis, db_candle):
    try:
        data = json.loads(message)
        candle_obj = {
            "symbol": data['topic'].split('.')[-1],
            "Open_time": datetime.fromtimestamp(int(data["data"][0]["start"] / 1000)),
            "Open": float(data["data"][0]["open"]),
            "High": float(data["data"][0]["high"]),
            "Low": float(data["data"][0]["low"]),
            "Close": float(data["data"][0]["close"]),
            "Volume": float(data["data"][0]["volume"]),
            "Close_time": datetime.fromtimestamp(int(data["data"][0]["end"] / 1000))
        }

        # إرسال البيانات لجميع عملاء React المتصلين
        if connected_clients:
            await asyncio.gather(*(client.send(json.dumps(candle_obj)) for client in connected_clients))

        # نشر على Redis
        await Redis.publish(f"{data['topic'].split('.')[-1]}_RealTime", json.dumps(json_serialize(candle_obj)))

        # حفظ الشمعة المكتملة في MongoDB
        if data['data'][0]["confirm"]:
            await db_candle[data['topic'].split('.')[-1]].insert_one(candle_obj)
            await Redis.lpush(f"{data['topic'].split('.')[-1]}_Close_Candle", "Closed")

        # طباعة لمراقبة البيانات
        print(f"{data['topic'].split('.')[-1]}| Time: {datetime.fromtimestamp(data['data'][0]['timestamp']/1000)} ,Open: {candle_obj['Open']}, High: {candle_obj['High']}, Low: {candle_obj['Low']}, Close: {candle_obj['Close']}, Volume: {candle_obj['Volume']}")
        print("-" * 60)
    except Exception:
        print(traceback.format_exc())
        logging.error(traceback.format_exc())

# -------------------------
# WebSocket server لإرسال البيانات لواجهة React
# -------------------------
async def react_websocket_server(websocket, path):
    print(f"✅ React client connected: {websocket.remote_address}")
    connected_clients.add(websocket)
    try:
        async for _ in websocket:  # React قد ترسل رسائل لكن نحن نهملها
            pass
    finally:
        connected_clients.remove(websocket)
        print(f"❌ React client disconnected: {websocket.remote_address}")

# -------------------------
# Bybit WebSocket client باستخدام websockets
# -------------------------
async def bybit_websocket_client(Redis, db_candle):
    url = "wss://stream.bybit.com/v5/public/linear"
    retry_delay = 5

    while True:
        try:
            async with websockets.connect(url, ping_interval=30, ping_timeout=10) as ws:
                print(f"✅ WebSocket Opened to Bybit at {datetime.now()}")
                sub_msg = {"op": "subscribe", "args": topics}
                await ws.send(json.dumps(sub_msg))
                print(f"Subscribed to: {topics}")

                async for message in ws:
                    await handle_message(message, Redis, db_candle)

        except Exception as e:
            print("⚠️ Bybit WebSocket error:", e)
            traceback.print_exc()
            print(f"Retrying connection in {retry_delay}s...")
            await asyncio.sleep(retry_delay)

# -------------------------
# Main async function
# -------------------------
async def main():
    # تهيئة Redis async
    Redis = await init_redis()

    # تشغيل WebSocket server لواجهة React على port 9000
    server = await websockets.serve(react_websocket_server, "localhost", 9000)
    print("✅ React WebSocket Server running on ws://localhost:9000")

    # تشغيل Bybit WebSocket client و React server بشكل متزامن
    bybit_task = asyncio.create_task(bybit_websocket_client(Redis, db_candle))

    # يبقي السيرفر شغال
    await asyncio.gather(bybit_task, server.wait_closed())

if __name__ == "__main__":
    asyncio.run(main())
