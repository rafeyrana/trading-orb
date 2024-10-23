import requests
import dotenv
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from twilio.rest import Client

def send_trade_alert(message: str, phone_numbers: list):
  

    env_vars = dotenv.dotenv_values()
    account_sid = env_vars['TWILIO_ACCOUNT_SID']
    auth_token = env_vars['TWILIO_AUTH_TOKEN']
    twilio_phone = env_vars['TWILIO_PHONE_NUMBER']
    
    try:
        client = Client(account_sid, auth_token)
        
        # Send message to each phone number
        for phone_number in phone_numbers:
            message = client.messages.create(
                body=message,
                from_=twilio_phone,
                to=phone_number
            )
            print(f"Alert sent to {phone_number} - Message SID: {message.sid}")
        return True
    except Exception as e:
        print(f"Error sending trade alert: {e}")
        return False

def get_last_market_day(date: datetime) -> datetime:
    if date.weekday() == 5:  # Saturday
        return date - timedelta(days=1)
    elif date.weekday() == 6:  # Sunday
        return date - timedelta(days=2)
    else:
        return date

def get_opening_range_high_low(symbol: str, interval: str, api_key: str):
    today = datetime.now()
    last_market_day = get_last_market_day(today)
    last_market_day_str = last_market_day.strftime('%Y-%m-%d')
    first_interval_key = f"{last_market_day_str} 09:30:00"

    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={interval}&extended_hours=false&apikey={api_key}'
    response = requests.get(url)
    data = response.json()

    time_series_key = f"Time Series ({interval})"
    if time_series_key not in data:
        raise ValueError(f"Time series data not found for interval {interval}")
    
    time_series = data[time_series_key]
    if first_interval_key not in time_series:
        raise ValueError(f"No data found for the first time interval at {first_interval_key}")

    first_interval = time_series[first_interval_key]
    high_price = float(first_interval['2. high'])
    low_price = float(first_interval['3. low'])

    return high_price, low_price

def get_current_price(symbol: str, api_key: str) -> float:
    url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}'
    response = requests.get(url)
    data = response.json()
    
    if "Global Quote" not in data:
        raise ValueError(f"No global quote data found for symbol {symbol}")
    
    current_price = float(data["Global Quote"]["05. price"])
    return current_price

def monitor_price(symbol: str, high: float, low: float, api_key: str, phone_numbers: list):
   
    alert_sent = False

    while not alert_sent:
        try:
            current_price = get_current_price(symbol, api_key)
            print(f"Current price for {symbol}: ${current_price:.2f}")

            if current_price > high:
                message = (
                    f"🔔 TRADE ALERT: {symbol} Breakout!\n"
                    f"Action: BUY\n"
                    f"Price: ${current_price:.2f}\n"
                    f"Breakout Level: ${high:.2f}\n"
                    f"Time: {datetime.now().strftime('%H:%M:%S')}"
                )
                print(message)
                if send_trade_alert(message, phone_numbers):
                    alert_sent = True
                break
                
            elif current_price < low:
                message = (
                    f"🔔 TRADE ALERT: {symbol} Breakdown!\n"
                    f"Action: SELL\n"
                    f"Price: ${current_price:.2f}\n"
                    f"Breakdown Level: ${low:.2f}\n"
                    f"Time: {datetime.now().strftime('%H:%M:%S')}"
                )
                print(message)
                if send_trade_alert(message, phone_numbers):
                    alert_sent = True
                break
                
            else:
                print(f"No breakout for {symbol} yet. Waiting...")
            time.sleep(6)

        except Exception as e:
            print(f"Error occurred for {symbol}: {e}")
            break

def monitor_multiple_stocks(symbols: list, interval: str, api_key: str, phone_numbers: list):
    orb_ranges = {}
    for symbol in symbols:
        try:
            high, low = get_opening_range_high_low(symbol, interval, api_key)
            orb_ranges[symbol] = (high, low)
            print(f"Opening range for {symbol} - High: ${high:.2f}, Low: ${low:.2f}")
        except Exception as e:
            print(f"Error fetching ORB for {symbol}: {e}")

    with ThreadPoolExecutor(max_workers=len(symbols)) as executor:
        for symbol, (high, low) in orb_ranges.items():
            executor.submit(monitor_price, symbol, high, low, api_key, phone_numbers)

if __name__ == "__main__":

    env_vars = dotenv.dotenv_values()
    api_key = env_vars['ALPHA_VANTAGE_API_KEY']

    phone_numbers = [
        '+1234567890',  
        '+0987654321'
    ]
    
    symbols = ['AAPL', "MSFT", "COIN", "NVDA", "TSLA"]
    interval = '15min'

    monitor_multiple_stocks(symbols, interval, api_key, phone_numbers)