from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import dotenv
import requests
import requests.exceptions

# concurrent.futures, smtplib, email.mime, twilio are no longer needed here
# as this file will not be the main executable and won't send alerts.

# The core data fetching functions (get_opening_range_high_low, get_current_price)
# have been moved to data_fetcher.py and are part of the DataFetcher class.
# The old notification functions (send_email_alert, send_trade_alert, send_notification)
# are removed as per the refactoring plan.
# The monitoring logic (monitor_price, monitor_multiple_stocks) is now part_of
# strategy.py and main.py.

# This file can be used for basic, isolated API connection tests or kept empty
# if all testing is done via the new module-specific test blocks or a dedicated test suite.


def get_last_market_day(date: datetime) -> datetime:
    """
    Helper function to determine the last market day.
    Note: This is simplified. A robust version is in DataFetcher or uses a market calendar.
    """
    if date.weekday() == 5:  # Saturday
        return date - timedelta(days=1)
    elif date.weekday() == 6:  # Sunday
        return date - timedelta(days=2)
    # Does not account for holidays
    return date


def test_alpha_vantage_connection(api_key: str, symbol: str = "IBM") -> None:
    """
    A simple test function to check connectivity and basic API response
    for Alpha Vantage TIME_SERIES_INTRADAY and GLOBAL_QUOTE.
    This is different from the DataFetcher class methods and is just for raw testing.
    """
    print(f"\n--- Testing Alpha Vantage Connection for {symbol} ---")

    # Test TIME_SERIES_INTRADAY (used for ORB)
    interval = "15min"
    # today variable was unused.
    # last_market_day_str = get_last_market_day(datetime.now()).strftime('%Y-%m-%d')
    # first_interval_key_part = f"{last_market_day_str} 09:30:00"
    # Example, not strictly used for this test

    url_intraday: str = (
        f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY"
        f"&symbol={symbol}&interval={interval}&extended_hours=false"
        f"&apikey={api_key}"
    )

    print(f"Testing Intraday URL: {url_intraday}")
    response_intraday: Optional[requests.Response] = None
    try:
        response_intraday = requests.get(url_intraday)
        response_intraday.raise_for_status()
        data_intraday: Dict[str, Any] = response_intraday.json()
        if f"Time Series ({interval})" in data_intraday:
            print(f"SUCCESS: Intraday data received for {symbol}.")
            # Sample data point:
            # print(f"{list(data_intraday[f'Time Series ({interval})'].items())[0]}")
        elif "Information" in data_intraday or "Note" in data_intraday:
            info_note: Optional[str] = data_intraday.get("Information", data_intraday.get("Note"))
            print(f"INFO: Intraday info/note for {symbol}: {info_note}")
        else:
            print(f"WARNING: Unexpected Intraday response structure for {symbol}: {data_intraday}")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed for Intraday for {symbol}: {e}")
    except ValueError as e:  # JSON decoding error
        print(f"ERROR: JSON decoding failed for Intraday for {symbol}: {e}")
        if response_intraday:
            print(f"Response text: {response_intraday.text[:200]}")
        else:
            print("No response received for Intraday request.")

    # Test GLOBAL_QUOTE (used for current price)
    url_quote: str = (
        f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
    )
    print(f"\nTesting Global Quote URL: {url_quote}")
    response_quote: Optional[requests.Response] = None
    try:
        response_quote = requests.get(url_quote)
        response_quote.raise_for_status()
        data_quote: Dict[str, Any] = response_quote.json()
        if "Global Quote" in data_quote and data_quote["Global Quote"]:
            price: Optional[str] = data_quote["Global Quote"].get("05. price")
            print(f"SUCCESS: Global Quote for {symbol}: Price {price}")
        elif "Information" in data_quote or "Note" in data_quote:
            info_note_quote: Optional[str] = data_quote.get(  # Renamed to avoid clash
                "Information", data_quote.get("Note")
            )
            print(f"INFO: Global Quote info/note for {symbol}: {info_note_quote}")
        else:
            print(f"WARNING: Unexpected Global Quote response structure for {symbol}: {data_quote}")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed for Global Quote for {symbol}: {e}")
    except ValueError as e:  # JSON decoding error
        print(f"ERROR: JSON decoding failed for Global Quote for {symbol}: {e}")
        if response_quote:
            print(f"Response text: {response_quote.text[:200]}")
        else:
            print("No response received for Global Quote request.")

    print(f"--- Alpha Vantage Connection Test for {symbol} Complete ---")


if __name__ == "__main__":
    print("Running basic API connection tests (not the full bot)...")
    # Load environment variables for the API key
    dotenv.load_dotenv()
    env_vars: Dict[str, Optional[str]] = dotenv.dotenv_values()
    api_key: Optional[str] = env_vars.get("ALPHA_VANTAGE_API_KEY")

    if not api_key:
        print("ALPHA_VANTAGE_API_KEY not found in environment variables or .env file.")
        print("Please ensure it's set to run the connection test.")
    else:
        masked_api_key: str = (
            ("*" * (len(api_key) - 4) + api_key[-4:]) if len(api_key) > 4 else "****"
        )
        print(f"Using API Key: {masked_api_key}")

        # Test with a common symbol
        test_alpha_vantage_connection(api_key, symbol="MSFT")

        # Test with a potentially problematic symbol
        # (e.g., one that might hit API limits or be invalid)
        # test_alpha_vantage_connection(api_key, symbol="NONEXISTENT_SYMBOL_XYZ")

        # You can add more test cases or specific checks here if needed.
        # For example, checking specific fields in the response.

    print("\nOld `test_api.py` script's main execution block finished.")
    print("The main bot logic is now in `main.py`.")
    print("This file (`test_api.py`) is now primarily for isolated API connection testing.")
