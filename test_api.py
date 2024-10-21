import requests
import dotenv
from datetime import datetime, timedelta

def get_last_market_day(date: datetime) -> datetime:
    """
    Returns the most recent date when the market was open (i.e., not a weekend).
    
    Parameters:
        date (datetime): The current date.

    Returns:
        datetime: The last market day (previous Friday if today is Saturday/Sunday).
    """
    # If today is Saturday (5) or Sunday (6), return the previous Friday
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


if __name__ == "__main__":
    api_key = dotenv.dotenv_values()['ALPHA_VANTAGE_API_KEY']
    symbol = 'IBM'
    interval = '15min' 
    high, low = get_opening_range_high_low(symbol, interval, api_key)
    print(f"Opening range high: {high}, low: {low}")
