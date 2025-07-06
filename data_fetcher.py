# Module for fetching data from financial APIs

import requests
import config
from datetime import datetime, timedelta

class DataFetcher:
    def __init__(self, api_key):
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("API key for Alpha Vantage must be provided.")

    def _get_last_market_day(self, date: datetime) -> datetime:
        # Simple implementation, assumes US market days (Mon-Fri)
        # More robust implementation would use a market calendar library
        if date.weekday() == 5:  # Saturday
            return date - timedelta(days=1)
        elif date.weekday() == 6:  # Sunday
            return date - timedelta(days=2)
        # TODO: Handle market holidays
        return date

    def get_opening_range_high_low(self, symbol: str, interval: str = config.ORB_INTERVAL):
        """
        Fetches the opening range (high and low) for a given symbol and interval
        from the first candle of the last market day.
        """
        today = datetime.now() # Assumes running in EST for market time alignment initially
        # TODO: Convert to EST using pytz if server is not in EST
        last_market_day = self._get_last_market_day(today)
        last_market_day_str = last_market_day.strftime('%Y-%m-%d')

        # Alpha Vantage uses 09:30 for the start of the main session for many US stocks
        first_interval_key_time_str = f"{config.MARKET_OPEN_HOUR_EST:02}:{config.MARKET_OPEN_MINUTE_EST:02}:00"
        first_interval_key = f"{last_market_day_str} {first_interval_key_time_str}"

        url = (f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY'
               f'&symbol={symbol}&interval={interval}&extended_hours=false'
               f'&apikey={self.api_key}')

        print(f"Fetching ORB for {symbol} for {first_interval_key} using URL: {url}")

        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for {symbol} from Alpha Vantage: {e}")
            return None, None
        except ValueError as e: # Handles JSON decoding errors
            print(f"Error decoding JSON for {symbol}: {e}")
            print(f"Response content: {response.text}")
            return None, None


        time_series_key = f"Time Series ({interval})"
        if time_series_key not in data:
            print(f"'{time_series_key}' not found in API response for {symbol}.")
            print(f"API Response: {data.get('Information', data.get('Note', 'No additional info'))}")
            return None, None

        time_series = data[time_series_key]
        if first_interval_key not in time_series:
            print(f"No data found for the first market interval ({first_interval_key}) for {symbol}.")
            # Fallback: try to get the earliest available data for the day if exact match fails
            # This can happen if the API returns slightly different timestamps
            for timestamp_key in time_series.keys():
                if last_market_day_str in timestamp_key and \
                   f"{config.MARKET_OPEN_HOUR_EST:02}:{config.MARKET_OPEN_MINUTE_EST:02}" in timestamp_key:
                    print(f"Found a slightly different timestamp for market open: {timestamp_key}")
                    first_interval_key = timestamp_key
                    break
            else: # If no suitable key found after checking
                print(f"Still no data for {symbol} around market open on {last_market_day_str}.")
                return None, None


        first_interval_data = time_series[first_interval_key]
        high_price = float(first_interval_data['2. high'])
        low_price = float(first_interval_data['3. low'])

        return high_price, low_price

    def get_current_price(self, symbol: str) -> float | None:
        """
        Fetches the current price for a given symbol.
        """
        url = (f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE'
               f'&symbol={symbol}&apikey={self.api_key}')

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching current price for {symbol}: {e}")
            return None
        except ValueError as e: # Handles JSON decoding errors
            print(f"Error decoding JSON for current price of {symbol}: {e}")
            return None

        if "Global Quote" not in data or not data["Global Quote"]:
            print(f"No global quote data found for symbol {symbol}.")
            print(f"API Response: {data.get('Information', data.get('Note', 'No additional info'))}")
            return None

        current_price_str = data["Global Quote"].get("05. price")
        if current_price_str is None:
            print(f"'05. price' not found in Global Quote for {symbol}.")
            return None

        try:
            current_price = float(current_price_str)
            return current_price
        except ValueError:
            print(f"Could not convert current price '{current_price_str}' to float for {symbol}.")
            return None

if __name__ == '__main__':
    # Simple test
    if not config.ALPHA_VANTAGE_API_KEY:
        print("ALPHA_VANTAGE_API_KEY not set in .env file. Please set it to test DataFetcher.")
    else:
        fetcher = DataFetcher(api_key=config.ALPHA_VANTAGE_API_KEY)

        # Test ORB
        print("\nTesting ORB Fetching:")
        for symbol_test in ["AAPL", "MSFT"]: # Using common symbols for testing
            print(f"\nFetching ORB for {symbol_test}...")
            high, low = fetcher.get_opening_range_high_low(symbol_test)
            if high is not None and low is not None:
                print(f"ORB for {symbol_test}: High = ${high:.2f}, Low = ${low:.2f}")
            else:
                print(f"Could not fetch ORB for {symbol_test}.")

        # Test Current Price
        print("\nTesting Current Price Fetching:")
        for symbol_test in ["AAPL", "MSFT"]:
            print(f"\nFetching current price for {symbol_test}...")
            price = fetcher.get_current_price(symbol_test)
            if price is not None:
                print(f"Current price for {symbol_test}: ${price:.2f}")
            else:
                print(f"Could not fetch current price for {symbol_test}.")

        # Test with a potentially problematic symbol (e.g., one that might not exist or have delayed data)
        print("\nTesting with a non-standard symbol (e.g., 'INVALID'):")
        invalid_symbol = "INVALID_SYMBOL_XYZ"
        high, low = fetcher.get_opening_range_high_low(invalid_symbol)
        if high is None and low is None:
            print(f"Correctly failed to fetch ORB for {invalid_symbol}")
        price = fetcher.get_current_price(invalid_symbol)
        if price is None:
            print(f"Correctly failed to fetch current price for {invalid_symbol}")

        print("\nDataFetcher tests complete.")
