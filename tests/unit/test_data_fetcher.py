from datetime import datetime
from unittest import mock

import pytest
import requests  # For requests.exceptions

import config  # Used by data_fetcher

# Assuming data_fetcher.py is in the project root or accessible via PYTHONPATH
from data_fetcher import DataFetcher

# --- Test Data ---
MOCK_API_KEY = "testkey123"

# Sample successful Alpha Vantage Intraday response for ORB
SAMPLE_AV_INTRADAY_RESPONSE = {
    f"Time Series ({config.ORB_INTERVAL})": {
        # Assuming default config values for market open for simplicity in mock
        f"{datetime.now().strftime('%Y-%m-%d')} 09:30:00": {
            "1. open": "150.00",
            "2. high": "152.50",
            "3. low": "149.50",
            "4. close": "151.00",
            "5. volume": "100000",
        },
        f"{datetime.now().strftime('%Y-%m-%d')} 09:45:00": {  # Another interval
            "1. open": "151.00",
            "2. high": "153.00",
            "3. low": "150.50",
            "4. close": "152.00",
            "5. volume": "120000",
        },
    },
    "Meta Data": {"2. Symbol": "TESTSYM", "4. Interval": config.ORB_INTERVAL},
}

# Sample successful Alpha Vantage Global Quote response
SAMPLE_AV_GLOBAL_QUOTE_RESPONSE = {
    "Global Quote": {
        "01. symbol": "TESTSYM",
        "05. price": "155.75",
        "09. change": "0.25",
        "10. change percent": "0.1608%",
    }
}

# Sample error response (e.g., invalid API key or symbol)
SAMPLE_AV_ERROR_RESPONSE = {
    "Error Message": "Invalid API call. Please check your API key and symbols."
}
SAMPLE_AV_INFO_RESPONSE_LIMIT = {  # API limit
    "Information": "Thank you for using Alpha Vantage! Our standard API call frequency is "
                   "5 calls per minute and 500 calls per day. (...)" # Truncated for test
}


@pytest.fixture
def fetcher() -> DataFetcher:
    """Fixture to create a DataFetcher instance with a mock API key."""
    # Temporarily set a dummy key in config for DataFetcher initialization if it reads from there
    # Or pass it directly if constructor takes it. Current DataFetcher takes it.
    return DataFetcher(api_key=MOCK_API_KEY)


@mock.patch("data_fetcher.requests.get")
def test_get_opening_range_high_low_success(mock_requests_get, fetcher):
    """Test get_opening_range_high_low successfully fetches and parses data."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_AV_INTRADAY_RESPONSE
    mock_requests_get.return_value = mock_response

    # Mock _get_last_market_day or ensure date in SAMPLE_AV_INTRADAY_RESPONSE matches.
    # Sample response uses today's date. A more robust test might mock _get_last_market_day.

    # To make the test deterministic with the sample data's date key:
    fixed_test_date = datetime.strptime(
        list(SAMPLE_AV_INTRADAY_RESPONSE[f"Time Series ({config.ORB_INTERVAL})"].keys())[0].split(
            " "
        )[0],
        "%Y-%m-%d",
    )

    with mock.patch.object(fetcher, "_get_last_market_day", return_value=fixed_test_date):
        high, low = fetcher.get_opening_range_high_low("TESTSYM")

    assert high == 152.50
    assert low == 149.50
    mock_requests_get.assert_called_once()


@mock.patch("data_fetcher.requests.get")
def test_get_opening_range_high_low_api_error(mock_requests_get, fetcher):
    """Test get_opening_range_high_low handles API error response."""
    mock_response = mock.Mock()
    mock_response.status_code = 200  # API might return 200 but with error in JSON
    mock_response.json.return_value = SAMPLE_AV_ERROR_RESPONSE
    mock_requests_get.return_value = mock_response

    high, low = fetcher.get_opening_range_high_low("TESTSYM_ERROR")
    assert high is None
    assert low is None


@mock.patch("data_fetcher.requests.get")
def test_get_opening_range_high_low_request_exception(mock_requests_get, fetcher):
    """Test get_opening_range_high_low handles requests.exceptions.RequestException."""
    mock_requests_get.side_effect = requests.exceptions.RequestException("Test network error")

    high, low = fetcher.get_opening_range_high_low("TESTSYM_NET_ERROR")
    assert high is None
    assert low is None


@mock.patch("data_fetcher.requests.get")
def test_get_opening_range_high_low_json_decode_error(mock_requests_get, fetcher):
    """Test get_opening_range_high_low handles JSONDecodeError."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError(
        "Test JSON decode error"
    )  # ValueError is base for JSONDecodeError
    mock_response.text = "Invalid JSON content"
    mock_requests_get.return_value = mock_response

    high, low = fetcher.get_opening_range_high_low("TESTSYM_JSON_ERROR")
    assert high is None
    assert low is None


@mock.patch("data_fetcher.requests.get")
def test_get_opening_range_high_low_missing_time_series_key(mock_requests_get, fetcher):
    """Test get_opening_range_high_low handles missing 'Time Series' key."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"Meta Data": {"Symbol": "TEST"}}  # Missing Time Series key
    mock_requests_get.return_value = mock_response

    high, low = fetcher.get_opening_range_high_low("TESTSYM_NO_TS_KEY")
    assert high is None
    assert low is None


@mock.patch("data_fetcher.requests.get")
def test_get_opening_range_high_low_missing_interval_data(mock_requests_get, fetcher):
    """Test get_opening_range_high_low handles missing specific interval data."""
    response_data = {
        f"Time Series ({config.ORB_INTERVAL})": {
            # Data for a different time, not the expected 09:30:00
            f"{datetime.now().strftime('%Y-%m-%d')} 10:00:00": {"2. high": "100", "3. low": "90"}
        }
    }
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_data
    mock_requests_get.return_value = mock_response

    fixed_test_date = datetime.strptime(
        list(response_data[f"Time Series ({config.ORB_INTERVAL})"].keys())[0].split(" ")[0],
        "%Y-%m-%d",
    )
    with mock.patch.object(fetcher, "_get_last_market_day", return_value=fixed_test_date):
        high, low = fetcher.get_opening_range_high_low("TESTSYM_NO_INTERVAL")
    # Fallback might find it if time is close. Test assumes strict match or true miss.
    assert high is None
    assert low is None  # For this test, we assume the fallback doesn't find a suitable key.


# --- Tests for get_current_price ---


@mock.patch("data_fetcher.requests.get")
def test_get_current_price_success(mock_requests_get, fetcher):
    """Test get_current_price successfully fetches and parses data."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_AV_GLOBAL_QUOTE_RESPONSE
    mock_requests_get.return_value = mock_response

    price = fetcher.get_current_price("TESTSYM")
    assert price == 155.75
    mock_requests_get.assert_called_once()


@mock.patch("data_fetcher.requests.get")
def test_get_current_price_api_error(mock_requests_get, fetcher):
    """Test get_current_price handles API error response (e.g. error message in JSON)."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_AV_ERROR_RESPONSE  # No "Global Quote"
    mock_requests_get.return_value = mock_response

    price = fetcher.get_current_price("TESTSYM_ERROR")
    assert price is None


@mock.patch("data_fetcher.requests.get")
def test_get_current_price_api_limit_info(mock_requests_get, fetcher):
    """Test get_current_price handles API limit info response."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_AV_INFO_RESPONSE_LIMIT  # No "Global Quote"
    mock_requests_get.return_value = mock_response

    price = fetcher.get_current_price("TESTSYM_LIMIT")
    assert price is None


@mock.patch("data_fetcher.requests.get")
def test_get_current_price_request_exception(mock_requests_get, fetcher):
    """Test get_current_price handles requests.exceptions.RequestException."""
    mock_requests_get.side_effect = requests.exceptions.RequestException("Test network error")

    price = fetcher.get_current_price("TESTSYM_NET_ERROR")
    assert price is None


@mock.patch("data_fetcher.requests.get")
def test_get_current_price_json_decode_error(mock_requests_get, fetcher):
    """Test get_current_price handles JSONDecodeError."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Test JSON decode error")
    mock_response.text = "Invalid JSON content"
    mock_requests_get.return_value = mock_response

    price = fetcher.get_current_price("TESTSYM_JSON_ERROR")
    assert price is None


@mock.patch("data_fetcher.requests.get")
def test_get_current_price_missing_global_quote(mock_requests_get, fetcher):
    """Test get_current_price handles missing 'Global Quote' key."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"SomeOtherKey": "SomeValue"}  # Missing Global Quote
    mock_requests_get.return_value = mock_response

    price = fetcher.get_current_price("TESTSYM_NO_GQ")
    assert price is None


@mock.patch("data_fetcher.requests.get")
def test_get_current_price_empty_global_quote(mock_requests_get, fetcher):
    """Test get_current_price handles 'Global Quote' key present but with empty dict value."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"Global Quote": {}}  # Empty Global Quote
    mock_requests_get.return_value = mock_response

    price = fetcher.get_current_price("TESTSYM_EMPTY_GQ")
    assert price is None


@mock.patch("data_fetcher.requests.get")
def test_get_current_price_missing_price_in_quote(mock_requests_get, fetcher):
    """Test get_current_price handles missing '05. price' in Global Quote."""
    response_data = {"Global Quote": {"01. symbol": "TESTSYM"}}  # Missing price
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_data
    mock_requests_get.return_value = mock_response

    price = fetcher.get_current_price("TESTSYM_NO_PRICE")
    assert price is None


@mock.patch("data_fetcher.requests.get")
def test_get_current_price_invalid_price_value(mock_requests_get, fetcher):
    """Test get_current_price handles non-float price value."""
    response_data = {"Global Quote": {"05. price": "not-a-float"}}
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_data
    mock_requests_get.return_value = mock_response

    price = fetcher.get_current_price("TESTSYM_BAD_PRICE_VAL")
    assert price is None


def test_data_fetcher_no_api_key():
    """Test DataFetcher raises ValueError if API key is None or empty."""
    with pytest.raises(ValueError, match="API key for Alpha Vantage must be provided."):
        DataFetcher(api_key=None)
    with pytest.raises(ValueError, match="API key for Alpha Vantage must be provided."):
        DataFetcher(api_key="")


# TODO: Add tests for _get_last_market_day if its logic becomes more complex (e.g. holidays)
# For now, its direct usage is implicitly tested via get_opening_range_high_low tests,
# especially when mocking it to control the date for ORB fetching.
