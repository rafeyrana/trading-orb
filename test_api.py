import requests
import dotenv
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from twilio.rest import Client

def send_email_alert(subject: str, message: str, email_addresses: list):
    """Send email alerts to specified email addresses"""
    env_vars = dotenv.dotenv_values()
    smtp_server = env_vars['SMTP_SERVER']
    smtp_port = int(env_vars['SMTP_PORT'])
    sender_email = env_vars['SENDER_EMAIL']
    email_password = env_vars['EMAIL_PASSWORD']
    
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(message, 'plain'))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, email_password)

            for email in email_addresses:
                msg['To'] = email
                server.send_message(msg)
                print(f"Alert email sent to {email}")
        return True
    except Exception as e:
        print(f"Error sending email alert: {e}")
        return False

def send_trade_alert(message: str, phone_numbers: list):
    """Send SMS alerts using Twilio"""
    env_vars = dotenv.dotenv_values()
    account_sid = env_vars['TWILIO_ACCOUNT_SID']
    auth_token = env_vars['TWILIO_AUTH_TOKEN']
    twilio_phone = env_vars['TWILIO_PHONE_NUMBER']
    
    try:
        client = Client(account_sid, auth_token)
        
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

def send_notification(message: str, notification_type: str, recipients: list):
    """Send notification based on specified type (email or sms)"""
    if notification_type.lower() == 'email':
        subject = "Stock Trading Alert"
        return send_email_alert(subject, message, recipients)
    elif notification_type.lower() == 'sms':
        return send_trade_alert(message, recipients)
    else:
        print(f"Invalid notification type: {notification_type}")
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

def monitor_price(symbol: str, high: float, low: float, api_key: str, notification_type: str, recipients: list):
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
                if send_notification(message, notification_type, recipients):
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
                if send_notification(message, notification_type, recipients):
                    alert_sent = True
                break
                
            else:
                print(f"No breakout for {symbol} yet. Waiting...")
            time.sleep(6)

        except Exception as e:
            print(f"Error occurred for {symbol}: {e}")
            break

def monitor_multiple_stocks(symbols: list, interval: str, api_key: str, notification_type: str, recipients: list):
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
            executor.submit(monitor_price, symbol, high, low, api_key, notification_type, recipients)

if __name__ == "__main__":
    env_vars = dotenv.dotenv_values()
    api_key = env_vars['ALPHA_VANTAGE_API_KEY']

    notification_type = 'email'  # Change this to 'sms' for text messages
    
    if notification_type == 'email':
        recipients = [
            'user1@example.com',
            'user2@example.com'
        ]
    else:
        recipients = [
            '+1234567890',
            '+0987654321'
        ]
    
    symbols = ['AAPL', "MSFT", "COIN", "NVDA", "TSLA"]
    interval = '15min'

    monitor_multiple_stocks(symbols, interval, api_key, notification_type, recipients)