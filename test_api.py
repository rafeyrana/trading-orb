import requests
import dotenv
from datetime import datetime

def get_opening_range_high_low(symbol: str, interval: str, api_key: str):
    """
    Fetches the high and low prices for the first interval of the day using Alpha Vantage API.

    Parameters:
        symbol (str): Stock symbol (e.g., "IBM")
        interval (str): Time interval (e.g., "1min", "5min", "15min", "30min", "60min")
        api_key (str): Your Alpha Vantage API key

    Returns:
        tuple: High and low prices for the first time interval (high, low)
    """
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={interval}&apikey={api_key}'
    response = requests.get(url)
    data = response.json()

    # Extract the time series data
    time_series_key = f"Time Series ({interval})"
    if time_series_key not in data:
        raise ValueError(f"Time series data not found for interval {interval}")
    
    time_series = data[time_series_key]

    # Get today's date in YYYY-MM-DD format
    today_date = datetime.now().strftime('%Y-%m-%d')

    # Build the key for the first time interval at 09:30
    first_interval_key = f"{today_date} 09:30:00"

    # Check if the key exists in the time series data
    if first_interval_key not in time_series:
        raise ValueError(f"No data found for the first time interval at {first_interval_key}")

    # Get the data for the 09:30 time slot
    first_interval = time_series[first_interval_key]

    # Extract the high and low prices from the first interval
    high_price = float(first_interval['2. high'])
    low_price = float(first_interval['3. low'])

    return high_price, low_price

# Example usage:
if __name__ == "__main__":
    api_key = dotenv.dotenv_values()['ALPHA_VANTAGE_API_KEY']
    symbol = 'IBM'
    interval = '15min'  # Example: fetching 15-minute interval data
    high, low = get_opening_range_high_low(symbol, interval, api_key)
    print(f"Opening range high: {high}, low: {low}")
