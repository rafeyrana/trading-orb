# Module for scheduling tasks, particularly for market hours

import datetime
import logging
import time

import pytz  # For robust timezone handling

import config
from typing import List # Moved to top

logger = logging.getLogger(__name__)


class MarketHoursScheduler:
    """
    Handles logic related to market hours and scheduling tasks accordingly.
    Assumes US Eastern Time for market hours as is typical for NYSE/NASDAQ.
    """

    def __init__(self) -> None:
        self.market_tz_str: str = "America/New_York"  # EST/EDT
        self.market_tz: pytz.BaseTzInfo # Use pytz specific type for localize
        try:
            self.market_tz = pytz.timezone(self.market_tz_str)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.error(
                f"Unknown timezone: {self.market_tz_str}. Defaulting to UTC for market hours."
            )
            self.market_tz = pytz.utc  # Fallback, though likely incorrect for market logic

        self.market_open_time: datetime.time = datetime.time(
            hour=config.MARKET_OPEN_HOUR_EST, minute=config.MARKET_OPEN_MINUTE_EST
        )
        self.market_close_time: datetime.time = datetime.time(
            hour=config.MARKET_CLOSE_HOUR_EST, minute=config.MARKET_CLOSE_MINUTE_EST
        )
        # Standard US market days: Monday (0) to Friday (4)
        self.market_days: List[int] = [0, 1, 2, 3, 4]

        logger.info(
            f"MarketHoursScheduler initialized for {self.market_tz_str}, "
            f"Open: {self.market_open_time.strftime('%H:%M')}, "
            f"Close: {self.market_close_time.strftime('%H:%M')}"
        )

    def get_current_market_time(
        self,
    ) -> datetime.datetime:  # Explicit return type was already there
        """Returns the current time in the market's timezone."""
        now: datetime.datetime = datetime.datetime.now(self.market_tz)
        return now

    def is_market_open(self) -> bool:
        """
        Checks if the US stock market is currently open.
        Considers day of the week and market hours.
        Does not account for market holidays.
        """
        # TODO: Implement market holiday checking using a library like `pandas_market_calendars`

        now_market_time: datetime.datetime = self.get_current_market_time()

        if now_market_time.weekday() not in self.market_days:
            logger.debug(
                f"Market is closed. Today ({now_market_time.strftime('%A')}) is not a market day."
            )
            return False

        current_time: datetime.time = now_market_time.time()
        is_open: bool = self.market_open_time <= current_time < self.market_close_time

        if is_open:
            logger.debug(
                f"Market is OPEN. Current market time: {current_time.strftime('%H:%M:%S')}"
            )
        else:
            debug_msg: str = (
                f"Market is CLOSED. Current market time: {current_time.strftime('%H:%M:%S')} "
                f"(Market hours: {self.market_open_time.strftime('%H:%M')} - "
                f"{self.market_close_time.strftime('%H:%M')})"
            )
            logger.debug(debug_msg)
        return is_open

    def get_time_until_next_market_open(self) -> float:
        """
        Calculates the time in seconds until the next market opening.
        Considers weekends and current time relative to market hours.
        Does not account for market holidays.
        """
        now_market_time: datetime.datetime = self.get_current_market_time()

        # Ensure market_tz is not None for localize method
        if self.market_tz is None:  # Should not happen with current __init__
            logger.error("Market timezone is not initialized.")
            return 3600.0  # Default to 1 hour wait

        today_market_open_dt: datetime.datetime = self.market_tz.localize(
            datetime.datetime.combine(now_market_time.date(), self.market_open_time)
        )

        # If it's a market day
        if now_market_time.weekday() in self.market_days:
            # If market is already open or it's before open today
            if now_market_time.time() < self.market_open_time:
                # Before market open today
                delta: datetime.timedelta = today_market_open_dt - now_market_time
                logger.info(
                    f"Next market open is today at {self.market_open_time.strftime('%H:%M %Z')}. "
                    f"Time until open: {delta}"
                )
                return delta.total_seconds()
            elif now_market_time.time() < self.market_close_time:
                # Market is currently open, technically no time *until* next open in this state,
                # but for practical purposes, we can return 0 or time to next day's open.
                # Let's return time to next day's open for consistency in "waiting" logic.
                pass  # Fall through to calculate next day's open

        # If market is closed for the day, or it's a weekend/holiday
        # Calculate next market day's open
        days_to_add: int = 1
        while True:
            next_potential_open_date: datetime.date = now_market_time.date() + datetime.timedelta(
                days=days_to_add
            )
            if next_potential_open_date.weekday() in self.market_days:
                # TODO: Check if next_potential_open_date is a market holiday
                next_market_open_dt: datetime.datetime = self.market_tz.localize(
                    datetime.datetime.combine(next_potential_open_date, self.market_open_time)
                )
                delta_next_day: datetime.timedelta = next_market_open_dt - now_market_time
                logger.info(
                    f"Next market open is on {next_potential_open_date.strftime('%Y-%m-%d')} "
                    f"at {self.market_open_time.strftime('%H:%M %Z')}. "
                    f"Time until open: {delta_next_day}"
                )
                return delta_next_day.total_seconds()
            days_to_add += 1
            if days_to_add > 7:  # Safety break, should not happen in normal circumstances
                logger.error("Could not determine next market open within 7 days.")
                return 3600.0  # Default to 1 hour wait if something is wrong

    def wait_until_market_open(self) -> None:
        """
        Blocks execution until the market opens.
        Checks periodically.
        """
        while not self.is_market_open():
            sleep_duration = self.get_time_until_next_market_open()
            # Cap sleep duration to avoid extremely long sleeps if preferred, e.g. 1 hour
            # And ensure it's at least a few seconds to avoid busy waiting if calculation is off
            sleep_duration = max(5, min(sleep_duration, 3600))

            log_msg = (
                f"Market closed. Sleeping {sleep_duration:.0f}s until next check / potential open."
            )
            logger.info(log_msg)
            time.sleep(sleep_duration)
        logger.info("Market is now open.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(module)s - %(message)s"
    )
    logger.info("Testing Scheduler module...")

    scheduler = MarketHoursScheduler()

    current_market_time = scheduler.get_current_market_time()
    logger.info(
        f"Current time in market tz ({scheduler.market_tz_str}): "
        f"{current_market_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )

    is_open = scheduler.is_market_open()
    logger.info(f"Is market currently open? {'Yes' if is_open else 'No'}")

    if not is_open:
        tts = scheduler.get_time_until_next_market_open()
        hours = tts // 3600
        minutes = (tts % 3600) // 60
        logger.info(
            f"Time until next market open: {tts:.0f} seconds "
            f"({hours:.0f} hours, {minutes:.0f} minutes)"
        )

        # Example of waiting (don't run this for too long in automated tests)
        # print(
        #     "\nTesting wait_until_market_open "
        #     "(will wait for a few seconds if market is closed)..."
        # )
        # scheduler.wait_until_market_open()
        # print("Returned from wait_until_market_open.")

    logger.info("\nScheduler tests complete.")
    logger.info("Note: If testing outside market hours, `is_market_open` should be 'No'.")
    logger.info(
        "If testing during market hours (Mon-Fri, 9:30 AM - 4:00 PM ET, "
        "excluding holidays), it should be 'Yes'."
    )
