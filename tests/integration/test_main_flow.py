import logging
from datetime import date, datetime, time
from typing import Any, Dict, Optional
from unittest import mock

import pytest
import pytz  # type: ignore

import config

# Modules to be tested (or whose interactions are tested)
import main


# Helper to create a mock datetime object, similar to unit tests for scheduler
from typing import TypeVar, Type

def mock_datetime_now_integration(mock_dt_object: datetime, target_tz: pytz.BaseTzInfo):
    _MockDateTimeT = TypeVar("_MockDateTimeT", bound="MockDateTime") # Moved inside

    class MockDateTime(datetime):
        @classmethod
        def now(cls: Type[_MockDateTimeT], tz: Optional[pytz.BaseTzInfo] = None) -> _MockDateTimeT:
            # Ensure returned datetime is in target_tz if tz is None (like datetime.now())
            # or convert if different tz passed (main_flow uses scheduler's get_current_market_time)

            # Create a new instance of cls (MockDateTime) from mock_dt_object parts
            # This ensures the return type is _MockDateTimeT as per superclass expectations
            dt_to_return = cls(
                mock_dt_object.year, mock_dt_object.month, mock_dt_object.day,
                mock_dt_object.hour, mock_dt_object.minute, mock_dt_object.second,
                mock_dt_object.microsecond
            )

            # Localize or adjust timezone
            if dt_to_return.tzinfo is None:
                dt_with_tz = target_tz.localize(dt_to_return)
            else:
                dt_with_tz = dt_to_return.astimezone(target_tz)

            # If a specific tz is requested for now(), convert again
            if tz:
                 final_dt = dt_with_tz.astimezone(tz)
            else:
                 final_dt = dt_with_tz

            # Reconstruct as cls instance to ensure _MockDateTimeT type
            return cls(
                final_dt.year, final_dt.month, final_dt.day,
                final_dt.hour, final_dt.minute, final_dt.second,
                final_dt.microsecond, tzinfo=final_dt.tzinfo
            )

        @classmethod
        def combine(
            cls: Type[_MockDateTimeT], d_date: date, t_time: time, tzinfo: Optional[pytz.BaseTzInfo] = None
        ) -> _MockDateTimeT:
            # Ensure the combined datetime is an instance of cls (MockDateTime)
            # and then potentially localize it if tzinfo is also from the mock_dt_object context
            # For simplicity, if tzinfo is passed, assume it's the final desired tz.
            # If not, and we want to ensure it's like mock_dt_object's tz, more logic needed.
            # Standard datetime.combine returns a naive datetime if tzinfo is None.

            # Create base datetime
            dt_naive = datetime.combine(d_date, t_time)
            # Reconstruct as cls instance
            dt_cls_instance = cls(
                dt_naive.year, dt_naive.month, dt_naive.day,
                dt_naive.hour, dt_naive.minute, dt_naive.second,
                dt_naive.microsecond, tzinfo=tzinfo # Pass tzinfo to constructor
            )
            return dt_cls_instance

    return MockDateTime


# Sample data for mocking API responses
SAMPLE_TICKER = "TESTSTOCK"
ORB_HIGH = 105.0
ORB_LOW = 95.0
BREAKOUT_PRICE = 110.0
HOLD_PRICE = 100.0


# Mock Alpha Vantage responses
def get_mock_orb_response(orb_date: date, symbol: str = SAMPLE_TICKER) -> Dict[str, Any]:
    # Make sure the date in the response matches what the DataFetcher will expect
    # The DataFetcher's _get_last_market_day will be based on the mocked 'now'
    orb_interval_str = f"{orb_date.strftime('%Y-%m-%d')} 09:30:00"
    return {
        f"Time Series ({config.ORB_INTERVAL})": {
            orb_interval_str: {
                "1. open": str(ORB_LOW + 1),
                "2. high": str(ORB_HIGH),
                "3. low": str(ORB_LOW),
                "4. close": str(ORB_HIGH - 1),
                "5. volume": "100000",
            }
        },
        "Meta Data": {"2. Symbol": symbol, "4. Interval": config.ORB_INTERVAL},
    }


def get_mock_price_response(price: float, symbol: str = SAMPLE_TICKER) -> Dict[str, Any]:
    return {
        "Global Quote": {
            "01. symbol": symbol,
            "05. price": str(price),
        }
    }


@pytest.fixture
def mock_config_values(monkeypatch):
    """Fixture to set specific config values for tests."""
    monkeypatch.setattr(config, "TICKER_SYMBOLS", [SAMPLE_TICKER])
    monkeypatch.setattr(config, "MONITORING_INTERVAL_SECONDS", 1)  # Fast for tests
    # Market hours can be default or also monkeypatched if needed for a specific scenario
    # For this test, we'll control time via datetime mocking.
    # Ensure API key is set for DataFetcher init
    if not config.ALPHA_VANTAGE_API_KEY:  # e.g. if test runner doesn't load .env
        monkeypatch.setattr(config, "ALPHA_VANTAGE_API_KEY", "fake_integration_test_key")


@mock.patch("main.time.sleep")  # Mock time.sleep to prevent actual sleeping
@mock.patch("main.requests.get")  # Mock requests.get used by DataFetcher
@mock.patch("main.datetime")  # Mock datetime module used by Scheduler
def test_main_flow_market_open_orb_breakout(
    mock_datetime_module,
    mock_requests_get,
    mock_time_sleep,
    mock_config_values,  # Apply mock config
    caplog,  # To capture logs, including alerts from LogAlerter
):
    """
    Test a simplified main flow:
    1. Market starts closed.
    2. Market opens.
    3. ORB is fetched.
    4. Price breaks out.
    5. Alert is generated.
    """
    caplog.set_level(logging.INFO)
    market_tz = pytz.timezone("America/New_York")

    # --- Define time progression ---
    # Time 1: Market closed (e.g., Mon 9:00 AM)
    time_market_closed = market_tz.localize(datetime(2024, 3, 4, 9, 0, 0))  # Monday
    # Time 2: Market opens (e.g., Mon 9:30 AM) - ORB should be fetched
    time_market_open_fetch_orb = market_tz.localize(
        datetime(2024, 3, 4, 9, 30, 15)
    )  # 15s after open
    # Time 3: Price check - breakout (e.g., Mon 9:32 AM)
    time_price_breakout = market_tz.localize(datetime(2024, 3, 4, 9, 32, 0))
    # Time 4: Price check - hold (e.g., Mon 9:34 AM) - to ensure alert fired only once
    time_price_hold_after_breakout = market_tz.localize(datetime(2024, 3, 4, 9, 34, 0))
    # Time 5: Market still open, but we stop the bot after this (e.g. Mon 9:36 AM)
    time_stop_bot = market_tz.localize(datetime(2024, 3, 4, 9, 36, 0))

    # Configure side effects for datetime.now()
    # The run_bot loop calls get_current_market_time, which calls datetime.now(tz)
    # We need to provide enough datetime objects for each iteration of the main loop.
    # Each "step" in the test might consume one or more `now()` calls.
    mock_dt_objects = [
        time_market_closed,  # Initial check, market closed
        time_market_open_fetch_orb,  # Market opens, ORB init
        time_market_open_fetch_orb,  # Inside ORB init (DataFetcher might call now)
        time_price_breakout,  # First price check after ORB
        time_price_hold_after_breakout,  # Second price check
        time_stop_bot,  # Final check before "stopping"
    ] * 2  # Multiply to be safe with internal calls to now()

    # Configure side effect for requests.get for Alpha Vantage
    # Call 1 (ORB): at time_market_open_fetch_orb
    orb_response_mock = mock.Mock()
    orb_response_mock.status_code = 200
    # The date for ORB data needs to match the *market day* DataFetcher calculates.
    # If time_market_open_fetch_orb is Mon 9:30, last_market_day is that Monday.
    orb_response_mock.json.return_value = get_mock_orb_response(
        orb_date=time_market_open_fetch_orb.date()
    )

    # Call 2 (Price): at time_price_breakout
    price_breakout_response_mock = mock.Mock()
    price_breakout_response_mock.status_code = 200
    price_breakout_response_mock.json.return_value = get_mock_price_response(BREAKOUT_PRICE)

    # Call 3 (Price): at time_price_hold_after_breakout
    price_hold_response_mock = mock.Mock()
    price_hold_response_mock.status_code = 200
    price_hold_response_mock.json.return_value = get_mock_price_response(
        HOLD_PRICE
    )  # Price moved back

    mock_requests_get.side_effect = [
        orb_response_mock,
        price_breakout_response_mock,
        price_hold_response_mock,
        # Add more if the loop runs longer / more symbols
    ]

    # Mock the datetime object used by the scheduler and potentially other places in main
    # The key is that scheduler.get_current_market_time() will use this mocked 'now'

    current_time_index = 0

    def get_next_mock_time(tz=None):
        nonlocal current_time_index
        if current_time_index >= len(mock_dt_objects):
            # If we run out of predefined times, raise an error or return a default
            # This indicates the test's time progression might be misaligned with loop iterations
            # For this test, we'll just keep returning the last one to avoid crashing.
            dt_to_return = mock_dt_objects[-1]
        else:
            dt_to_return = mock_dt_objects[current_time_index]
        current_time_index += 1

        # Ensure it's localized correctly for the caller
        if dt_to_return.tzinfo is None:
            dt_to_return = market_tz.localize(dt_to_return)
        if tz:
            return dt_to_return.astimezone(tz)
        return dt_to_return.astimezone(market_tz)

    class MockedDateTimeModuleIntegration:
        class datetime:
            @staticmethod
            def now(tz=None):
                return get_next_mock_time(tz=tz)

            @staticmethod
            def combine(
                d_date: date, t_time: time, tzinfo: Optional[pytz.BaseTzInfo] = None
            ) -> datetime:
                return datetime.combine(d_date, t_time, tzinfo=tzinfo)

            # Add other static methods if needed by main.py or its imports
            min = datetime.min
            max = datetime.max

    mock_datetime_module.datetime = MockedDateTimeModuleIntegration.datetime

    # --- Run the bot for a limited number of iterations ---
    # We need a way to stop the main loop. We can patch 'while True' or raise an exception.
    # A simpler way for testing is to limit the number of times 'time.sleep' is called.

    stop_after_n_evaluations = 3  # Market Closed, ORB Fetch + Eval, Second Eval

    original_time_sleep = time.sleep  # Keep original for other uses if any

    def limited_sleep_side_effect(*args, **kwargs):
        nonlocal stop_after_n_evaluations
        stop_after_n_evaluations -= 1
        if stop_after_n_evaluations < 0:
            raise KeyboardInterrupt("Stopping test loop via KeyboardInterrupt")  # Cleanly stop
        return original_time_sleep(0.001)  # Sleep a tiny bit to allow context switches if any

    mock_time_sleep.side_effect = limited_sleep_side_effect

    with pytest.raises(KeyboardInterrupt):  # Expect the loop to be stopped by this
        main.run_bot()

    # --- Assertions ---
    # 1. ORB Fetch (should happen once)
    # Check if the ORB fetch URL was called. Construct expected URL.
    # This is a bit brittle if URL construction changes.
    # A better check is that fetcher.get_opening_range_high_low was called on the strategy object.
    # For now, check requests.get calls.

    # Expected URL for ORB fetch:
    # Example: https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=TESTSTOCK&interval=15min&extended_hours=false&apikey=fake_integration_test_key
    orb_url_found = False
    price_url_found = False
    for call_args in mock_requests_get.call_args_list:
        url_called = call_args[0][0]
        if "TIME_SERIES_INTRADAY" in url_called and f"symbol={SAMPLE_TICKER}" in url_called:
            orb_url_found = True
        if "GLOBAL_QUOTE" in url_called and f"symbol={SAMPLE_TICKER}" in url_called:
            price_url_found = True

    assert orb_url_found, "ORB data fetch URL was not called."
    assert price_url_found, "Price data fetch URL was not called."

    # 2. Alert Generation
    alert_logs = [
        r for r in caplog.records if "ALERT - Subject:" in r.message and "BUY_BREAKOUT" in r.message
    ]
    assert len(alert_logs) == 1, "Should have logged exactly one BUY_BREAKOUT alert."

    breakout_alert_details = alert_logs[0].message
    assert SAMPLE_TICKER in breakout_alert_details
    assert f"Price: ${BREAKOUT_PRICE:.2f}" in breakout_alert_details
    assert f"ORB High: ${ORB_HIGH:.2f}" in breakout_alert_details

    # 3. Log messages indicating flow
    assert any("Market is OPEN" in record.message for record in caplog.records)
    assert any(
        f"ORB for {SAMPLE_TICKER}: H={ORB_HIGH:.2f}, L={ORB_LOW:.2f}" in record.message
        for record in caplog.records
    )
    assert any(
        f"Action: {SAMPLE_TICKER} BUY_BREAKOUT at ${BREAKOUT_PRICE:.2f}" in record.message
        for record in caplog.records
    )

    # Verify no subsequent breakout alert for hold price
    hold_price_breakout_logs = [
        r
        for r in caplog.records
        if "ALERT - Subject:" in r.message
        and "BUY_BREAKOUT" in r.message
        and f"Price: ${HOLD_PRICE:.2f}" in r.message
    ]
    assert len(hold_price_breakout_logs) == 0, (
        "Should not have logged a breakout alert at the hold price after initial breakout."
    )

    # 4. time.sleep calls
    # Based on limited_sleep_side_effect, it should have been called a few times.
    # The exact number can be tricky due to the market closed loop.
    # The first call to sleep in the "market closed" part, then for monitoring interval.
    assert mock_time_sleep.call_count > 1

    # Check that the "Bot shutdown requested" is logged
    assert any(
        "Bot shutdown requested (KeyboardInterrupt). Exiting..." in record.message
        for record in caplog.records
    )


# Note: This is a complex integration test. Smaller tests for specific
# interactions (e.g., Scheduler + Main loop for open/close) could also be useful.
