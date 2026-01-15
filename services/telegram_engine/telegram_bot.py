import requests
import os
from datetime import datetime
import aiohttp


async def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    print("رسالة Telegram تم إرسالها بنجاح")
                else:
                    print(f"Failed to send message, status code: {response.status}")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")


def send_telegram_photo(image_path, caption=""):
    """إرسال صورة إلى Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    try:
        with open(image_path, 'rb') as photo:
            files = {'photo': photo}
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'caption': caption
            }
            response = requests.post(url, files=files, data=data)
            
        if response.status_code == 200:
            print("صورة Telegram تم إرسالها بنجاح")
            # حذف الصورة بعد الإرسال
            os.remove(image_path)
        else:
            print(f"Failed to send photo, status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending Telegram photo: {e}")
        # حذف الصورة في حالة الخطأ
        if os.path.exists(image_path):
            os.remove(image_path)