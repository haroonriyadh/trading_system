from binance_client import api_key,api_secret,client
from symbols import symbols


def change_leverage(client,symbol):
    try:
        max_leverage = client.futures_leverage_bracket(symbol=symbol)[0]['brackets'][0]['initialLeverage']
        change_leverage = client.futures_change_leverage(symbol=symbol,leverage=max_leverage)
    except Exception as e:
        print(e)
