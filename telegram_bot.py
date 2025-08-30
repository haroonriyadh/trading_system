import requests


TELEGRAM_TOKEN = '7540566988:AAE-RRfOVWraT-co87saoHTfMJujxDQEjaA'
TELEGRAM_CHAT_ID = '6061081574'



def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    
    try:
        response = requests.post(url=url, json=payload)
        if response.status_code == 200:
            print("رسالة Telegram تم إرسالها بنجاح")
        else:
            print(f"Failed to send message, status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")