# Main application script for the ORB Trading Bot

import logging
import time
from datetime import date, datetime
from typing import List, Optional

import config  # For loading configurations (implicitly loads .env)
from alerter import Alerter, LogAlerter  # Import base class for type hint
from data_fetcher import DataFetcher
from scheduler import MarketHoursScheduler
from strategy import ORBStrategy, TradingStrategy  # Import base class for type hint

# --- Logging Setup ---
# Using basicConfig for simplicity, but a more advanced setup (e.g., file logging) could be used.
logging.basicConfig(
    level=config.LOG_LEVEL.upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_bot() -> None:
    """
    Main function to run the trading bot.
    """
    logger.info("------------------------------------------------------")
    logger.info("--- ORB Trading Bot Starting ---")
    logger.info("------------------------------------------------------")

    # --- Initialization ---
    if not config.ALPHA_VANTAGE_API_KEY:
        logger.critical(
            "ALPHA_VANTAGE_API_KEY is not set. "
            "Please configure it in your .env file or environment."
        )
        return

    data_fetcher: DataFetcher = DataFetcher(api_key=config.ALPHA_VANTAGE_API_KEY)
    alerter: Alerter = LogAlerter()  # Use base class for type hint
    scheduler: MarketHoursScheduler = MarketHoursScheduler()

    strategies: List[TradingStrategy] = []  # Use base class for list type hint
    if not config.TICKER_SYMBOLS:
        logger.warning("No TICKER_SYMBOLS configured. The bot will not monitor any stocks.")
    else:
        logger.info(f"Configured to monitor symbols: {', '.join(config.TICKER_SYMBOLS)}")
        for symbol_config in config.TICKER_SYMBOLS:  # Renamed to avoid clash with 'symbol' module
            strategies.append(ORBStrategy(symbol=symbol_config, data_fetcher=data_fetcher))

    logger.info(f"Monitoring interval set to: {config.MONITORING_INTERVAL_SECONDS} seconds.")
    logger.info(f"ORB interval set to: {config.ORB_INTERVAL}.")

    last_market_day_checked: Optional[date] = None

    # --- Main Application Loop ---
    try:
        while True:
            now_market_time: datetime = scheduler.get_current_market_time()
            current_market_date: date = now_market_time.date()

            if scheduler.is_market_open():
                logger.info(
                    f"Market is OPEN. Current EST: {now_market_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )

                # Reset strategy states if it's a new market day
                if last_market_day_checked != current_market_date:
                    logger.info(
                        f"New market day ({current_market_date}). "
                        "Resetting daily states for all strategies."
                    )
                    for strategy_instance in strategies:
                        strategy_instance.reset_daily_state()
                    last_market_day_checked = current_market_date
                    # Allow some time for market data to settle, e.g., first ORB calculation
                    logger.info(
                        "Waiting a moment after market open for data to stabilize "
                        "before first ORB fetch..."
                    )
                    time.sleep(15)  # Brief pause

                # Initialize ORB for strategies if not already done for the day
                for strategy_instance in strategies:
                    # Assuming strategies in the list are ORBStrategy based on current logic.
                    # For stricter type safety with List[TradingStrategy], isinstance checks are used.
                    if isinstance(strategy_instance, ORBStrategy):  # Type guard
                        if strategy_instance.orb_high is None or strategy_instance.orb_low is None:
                            logger.info(
                                f"Attempting to initialize ORB for {strategy_instance.symbol} "
                                f"for {current_market_date}..."
                            )
                            initialized: bool = strategy_instance.initialize_strategy_for_day()
                            if not initialized:
                                logger.warning(
                                    f"Could not initialize ORB for {strategy_instance.symbol}. "
                                    "Will retry on next cycle."
                                )
                            else:
                                # These are Optional[float], so check before use if strict
                                orb_h: Optional[float] = strategy_instance.orb_high
                                orb_l: Optional[float] = strategy_instance.orb_low
                                if orb_h is not None and orb_l is not None:
                                    logger.info(
                                        f"ORB for {strategy_instance.symbol}: H={orb_h:.2f}, L={orb_l:.2f}"
                                    )
                                else:
                                    logger.warning(
                                        f"ORB initialized but values still None for {strategy_instance.symbol}"
                                    )

                # Evaluate strategies
                if not strategies:
                    logger.info("No strategies loaded. Waiting for next monitoring interval.")
                else:
                    logger.info("Evaluating strategies...")

                for strategy_instance in strategies:
                    if isinstance(strategy_instance, ORBStrategy):  # Type guard
                        if strategy_instance.orb_high is None or strategy_instance.orb_low is None:
                            logger.debug(
                                f"Skipping {strategy_instance.symbol}: ORB not initialized."
                            )
                            continue  # Skip if ORB failed to initialize

                    action, price, alert_message = (
                        strategy_instance.evaluate()
                    )  # Renamed message to avoid clash
                    if action and price is not None and alert_message is not None:
                        logger.info(f"Action: {strategy_instance.symbol} {action} at ${price:.2f}")
                        alerter.send_alert(
                            subject=f"{strategy_instance.symbol} - {action}", message=alert_message
                        )
                    else:
                        logger.debug(f"No action for {strategy_instance.symbol} at this time.")

                logger.info(
                    f"Sleeping for {config.MONITORING_INTERVAL_SECONDS} seconds until next check..."
                )
                time.sleep(config.MONITORING_INTERVAL_SECONDS)

            else:  # Market is closed
                market_closed_msg: str = (
                    f"Market is CLOSED. Current EST: "
                    f"{now_market_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                logger.info(market_closed_msg)
                # Reset daily states if the market just closed for this date,
                # ensuring they are fresh for next open
                if last_market_day_checked == current_market_date:
                    logger.info(
                        f"Market closed for {current_market_date}. "
                        "Marking daily states for reset for next session."
                    )
                    # Ensures bot resets if restarted before next day.
                    # Primary reset is at new market day start.
                    last_market_day_checked = None

                time_to_open: float = scheduler.get_time_until_next_market_open()
                # Sensible sleep: check every 5-30 minutes when market is closed,
                # or until next open if it's soon.
                # This avoids extremely long sleeps and allows quicker restart
                # if the script is stopped/started.
                sleep_duration: float = min(time_to_open, 30 * 60)  # Sleep at most 30 minutes
                sleep_duration = max(
                    sleep_duration, 5 * 60
                )  # Sleep at least 5 minutes, unless open is sooner

                if time_to_open < (5 * 60):  # If opening in less than 5 mins, sleep exact duration
                    sleep_duration = time_to_open

                if sleep_duration <= 0:  # Should not happen if logic is correct, but as a safeguard
                    sleep_duration = 60.0  # Use float

                sleep_msg: str = (
                    f"Next market open: {time_to_open / 3600:.2f} hrs. "
                    f"Sleeping for {sleep_duration / 60:.1f} mins."
                )
                logger.info(sleep_msg)
                time.sleep(sleep_duration)

    except KeyboardInterrupt:
        logger.info("Bot shutdown requested (KeyboardInterrupt). Exiting...")
    except Exception as e:
        logger.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
        # In a real server environment, you might want to add more robust error handling
        # or a mechanism to restart the bot.
    finally:
        logger.info("------------------------------------------------------")
        logger.info("--- ORB Trading Bot Shutting Down ---")
        logger.info("------------------------------------------------------")


if __name__ == "__main__":
    run_bot()
