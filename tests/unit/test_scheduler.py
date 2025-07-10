from datetime import datetime, time, tzinfo
from unittest import mock
from typing import Optional # Added Optional
import logging # Added logging

import pytest
import pytz  # type: ignore

import config  # Used by scheduler

# Assuming scheduler.py is in the project root or accessible via PYTHONPATH
from scheduler import MarketHoursScheduler


# Helper to create a mock datetime object
def mock_datetime_now(mock_dt_object: datetime, mock_pytz_timezone):
    class MockDateTime(datetime):
        @classmethod
        def now(cls, tz: Optional[tzinfo] = None):
            if tz:
                # If a timezone is provided, localize the mock_dt_object to it
                # This simulates datetime.now(tz=some_timezone)
                if mock_dt_object.tzinfo is None:
                    return mock_pytz_timezone.localize(mock_dt_object)
                else:  # If mock_dt_object is already aware, convert it
                    return mock_dt_object.astimezone(mock_pytz_timezone)
            # If no tz, return the naive mock_dt_object or an aware one if it's already aware
            return mock_dt_object

    return MockDateTime


@pytest.fixture
def scheduler() -> MarketHoursScheduler:
    """Fixture to create a MarketHoursScheduler instance."""
    return MarketHoursScheduler()


# Parameterize tests for different times and days
# Times are in "America/New_York" (EST/EDT)
market_open_time_config = time(config.MARKET_OPEN_HOUR_EST, config.MARKET_OPEN_MINUTE_EST)
market_close_time_config = time(config.MARKET_CLOSE_HOUR_EST, config.MARKET_CLOSE_MINUTE_EST)

# Test cases: (description, year, month, day, hour, minute, second, expected_is_open)
# Note: weekday() for these dates:
# 2024-01-15 (Mon) = 0
# 2024-01-13 (Sat) = 5
# 2024-01-14 (Sun) = 6
TEST_CASES_IS_MARKET_OPEN = [
    ("Weekday, during market hours", 2024, 1, 15, 10, 0, 0, True),
    (
        "Weekday, at market open",
        2024,
        1,
        15,
        market_open_time_config.hour,
        market_open_time_config.minute,
        0,
        True,
    ),
    (
        "Weekday, just before market close",
        2024,
        1,
        15,
        market_close_time_config.hour - 1,
        market_close_time_config.minute + 59,
        59,
        True,
    ),  # Assuming default 16:00 close
    (
        "Weekday, at market close (should be false as it's exclusive)",
        2024,
        1,
        15,
        market_close_time_config.hour,
        market_close_time_config.minute,
        0,
        False,
    ),
    ("Weekday, before market open", 2024, 1, 15, 8, 0, 0, False),
    ("Weekday, after market close", 2024, 1, 15, 17, 0, 0, False),
    ("Saturday, during market hours", 2024, 1, 13, 10, 0, 0, False),  # Saturday
    ("Sunday, during market hours", 2024, 1, 14, 10, 0, 0, False),  # Sunday
]


@pytest.mark.parametrize(
    "desc, year, month, day, hour, minute, second, expected", TEST_CASES_IS_MARKET_OPEN
)
def test_is_market_open(desc, year, month, day, hour, minute, second, expected, scheduler):
    # Mock current time in "America/New_York"
    # pytz.timezone is needed by the scheduler, so we use it to make our mock_dt aware
    market_tz = pytz.timezone("America/New_York")
    mock_now = market_tz.localize(datetime(year, month, day, hour, minute, second))

    with mock.patch("scheduler.datetime") as mock_datetime_module:
        # Configure the 'now' method of the mocked datetime class
        mock_datetime_module.datetime = mock_datetime_now(mock_now, market_tz)
        assert scheduler.is_market_open() == expected


# Test cases for time_until_next_market_open
# (description, current_datetime_args, expected_delta_seconds (approx))
# current_datetime_args are (year, month, day, hour, minute, second) for "America/New_York"
# Note: Market opens 9:30 AM, closes 4:00 PM EST/EDT.
# Tests assume consistent offset for test dates (no dynamic DST).
# Calculations are rough estimates. Precise timedelta calculations are complex.
TEST_CASES_TIME_UNTIL_OPEN = [
    (
        "Before market open on a weekday (Mon 8:00 AM -> Mon 9:30 AM)",
        (2024, 1, 15, 8, 0, 0),  # Monday 8:00 AM
        1.5 * 3600,  # 1.5 hours
    ),
    (
        "After market close on a weekday (Mon 5:00 PM -> Tue 9:30 AM)",
        (2024, 1, 15, 17, 0, 0),  # Monday 5:00 PM
        (24 - 17 + 9.5) * 3600,  # (7 hours today + 9.5 hours tomorrow)
    ),
    (
        "Friday after close (Fri 5:00 PM -> Mon 9:30 AM)",
        (2024, 1, 12, 17, 0, 0),  # Friday 5:00 PM (Jan 12, 2024 is a Friday)
        ((24 - 17) + 2 * 24 + 9.5) * 3600,  # (7 hrs Fri + 48 hrs Sat/Sun + 9.5 hrs Mon)
    ),
    (
        "Saturday morning (Sat 10:00 AM -> Mon 9:30 AM)",
        (2024, 1, 13, 10, 0, 0),  # Saturday 10:00 AM
        ((24 - 10) + 1 * 24 + 9.5) * 3600,  # (14 hrs Sat + 24 hrs Sun + 9.5 hrs Mon)
    ),
    (
        "During market hours (Mon 10:00 AM -> Tue 9:30 AM, as it calculates for *next* open)",
        (2024, 1, 15, 10, 0, 0),  # Monday 10:00 AM
        ((24 - 10) + 9.5) * 3600,  # (14 hrs today + 9.5 hrs tomorrow)
    ),
]


@pytest.mark.parametrize("desc, current_dt_args, expected_seconds", TEST_CASES_TIME_UNTIL_OPEN)
def test_get_time_until_next_market_open(desc, current_dt_args, expected_seconds, scheduler):
    market_tz = pytz.timezone("America/New_York")
    mock_now = market_tz.localize(datetime(*current_dt_args))

    with mock.patch("scheduler.datetime") as mock_datetime_module:
        mock_datetime_module.datetime = mock_datetime_now(mock_now, market_tz)

        # Allow a small tolerance for floating point comparisons and DST nuances not deeply mocked
        # Pytest's approx is good for this.
        assert scheduler.get_time_until_next_market_open() == pytest.approx(
            expected_seconds, abs=60
        )


def test_wait_until_market_open_market_already_open(scheduler, caplog):
    """Test wait_until_market_open when market is already open."""
    market_tz = pytz.timezone("America/New_York")
    # Monday 10:00 AM
    mock_now = market_tz.localize(datetime(2024, 1, 15, 10, 0, 0))

    with (
        mock.patch("scheduler.datetime") as mock_datetime_module,
        mock.patch("scheduler.time.sleep") as mock_sleep,
    ):  # Mock time.sleep
        mock_datetime_module.datetime = mock_datetime_now(mock_now, market_tz)

        caplog.set_level(logging.INFO)
        scheduler.wait_until_market_open()

        mock_sleep.assert_not_called()  # Should not sleep if market is open
        assert any("Market is now open." in record.message for record in caplog.records)


def test_wait_until_market_open_market_closed_opens_on_first_check(scheduler, caplog):
    """Test wait_until_market_open when market is closed but opens on the first check."""
    market_tz = pytz.timezone("America/New_York")
    # Monday 9:29:58 AM (opens in 2 seconds)
    mock_initial_now = market_tz.localize(datetime(2024, 1, 15, 9, 29, 58))
    # Monday 9:30:00 AM (market open)
    mock_after_sleep_now = market_tz.localize(datetime(2024, 1, 15, 9, 30, 0))

    # This mock will return different times on subsequent calls to datetime.now()
    mock_now_side_effect = [mock_initial_now, mock_after_sleep_now, mock_after_sleep_now]

    def mock_dynamic_datetime_now(tz=None):
        # Pop from the list of times to return. If list is exhausted, keep returning the last one.
        if not mock_now_side_effect:
            # Should not happen in this test if side_effect list is long enough
            return market_tz.localize(datetime(2024, 1, 15, 10, 0, 0))

        current_mock_time = mock_now_side_effect.pop(0)
        if tz:
            if current_mock_time.tzinfo is None:
                return market_tz.localize(current_mock_time)
            return current_mock_time.astimezone(tz)
        return current_mock_time

    class MockedDateTimeModule:
        # Mimic the structure that scheduler.datetime.datetime.now() calls
        class datetime:
            @staticmethod
            def now(tz=None):
                return mock_dynamic_datetime_now(tz=tz)

            # Provide other datetime attrs if scheduler uses them directly from datetime.datetime
            # e.g., datetime.datetime.combine.
            # Assuming only .now() is critical for this dynamic mock for now.
            @staticmethod
            def combine(date_part, time_part):
                return datetime.combine(date_part, time_part)

    with (
        mock.patch("scheduler.datetime", MockedDateTimeModule),
        mock.patch("scheduler.time.sleep") as mock_sleep,
    ):
        caplog.set_level(logging.INFO)
        scheduler.wait_until_market_open()

        mock_sleep.assert_called_once()
        # The sleep duration should be short, capped at 5s for the first check if open is very soon
        assert mock_sleep.call_args[0][0] <= 5.0
        assert any("Market is now open." in record.message for record in caplog.records)
        assert any("Market closed. Sleeping" in record.message for record in caplog.records)


# Note: Testing for DST changes or specific holiday calendars is out of scope for these unit tests
# but would be important for a production system. pandas_market_calendars could be used for that.
