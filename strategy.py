# Module for defining trading strategies

import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import config
from data_fetcher import DataFetcher

# Basic logging setup
logging.basicConfig(
    level=config.LOG_LEVEL.upper(), format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Type alias for the result of the evaluate method
EvaluateResult = Tuple[Optional[str], Optional[float], Optional[str]]


class TradingStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    """

    def __init__(self, symbol: str, data_fetcher: DataFetcher) -> None:
        self.symbol: str = symbol
        self.data_fetcher: DataFetcher = data_fetcher
        self.orb_high: Optional[float] = None
        self.orb_low: Optional[float] = None
        self.alerted_today_breakout: bool = False
        self.alerted_today_breakdown: bool = False

    @abstractmethod
    def initialize_strategy_for_day(self) -> bool:
        """
        Initializes or resets any daily parameters for the strategy.
        For ORB, this means fetching the day's ORB.
        Returns True if initialization was successful, False otherwise.
        """
        pass

    @abstractmethod
    def evaluate(self) -> EvaluateResult:
        """
        Evaluates the strategy based on current market data.

        Returns:
            A tuple (action, current_price, message) or (None, None, None) if no action.
            action: str (e.g., "BUY_BREAKOUT", "SELL_BREAKDOWN") or None
            current_price: float or None
            message: str detailed message for the alert, or None
        """
        pass

    def reset_daily_state(self) -> None:
        """Resets flags that indicate if an alert has been sent for the day."""
        self.orb_high = None
        self.orb_low = None
        self.alerted_today_breakout = False
        self.alerted_today_breakdown = False
        logger.info(f"Daily state reset for {self.symbol}")


class ORBStrategy(TradingStrategy):
    """
    Opening Range Breakout (ORB) strategy.
    """

    def __init__(
        self, symbol: str, data_fetcher: DataFetcher, orb_interval: str = config.ORB_INTERVAL
    ) -> None:
        super().__init__(symbol, data_fetcher)
        self.orb_interval: str = orb_interval
        logger.info(f"ORBStrategy initialized for {self.symbol} with interval {self.orb_interval}")

    def initialize_strategy_for_day(self) -> bool:
        """
        Fetches and stores the Opening Range Breakout high and low for the symbol.
        Should be called once after market open.
        Returns True if initialization was successful, False otherwise.
        """
        if self.orb_high is not None and self.orb_low is not None:
            log_msg: str = (
                f"ORB already initialized for {self.symbol} today: "
                f"High={self.orb_high}, Low={self.orb_low}"
            )
            logger.info(log_msg)
            return True

        logger.info(f"Initializing ORB for {self.symbol} using {self.orb_interval} interval...")
        high, low = self.data_fetcher.get_opening_range_high_low(self.symbol, self.orb_interval)
        if high is not None and low is not None:
            self.orb_high = high
            self.orb_low = low
            log_msg_init: str = (  # Renamed to avoid conflict with outer scope log_msg
                f"ORB for {self.symbol} initialized: "
                f"High=${self.orb_high:.2f}, Low=${self.orb_low:.2f}"
            )
            logger.info(log_msg_init)
            return True
        else:
            logger.error(f"Failed to initialize ORB for {self.symbol}.")
            return False

    def evaluate(self) -> EvaluateResult:
        """
        Evaluates the ORB strategy.
        Checks if the current price breaks above ORB high or below ORB low.
        """
        if self.orb_high is None or self.orb_low is None:
            logger.warning(f"ORB not initialized for {self.symbol}. Cannot evaluate.")
            # Attempt to initialize if not done.
            if not self.initialize_strategy_for_day():
                return None, None, None  # Still couldn't initialize

        current_price: Optional[float] = self.data_fetcher.get_current_price(self.symbol)

        if current_price is None:
            logger.warning(f"Could not fetch current price for {self.symbol}. Skipping evaluation.")
            return None, None, None

        # Ensure orb_high and orb_low are floats for comparison, after null check above.
        # Guaranteed if current_price is not None & initialize_strategy_for_day passed,
        # or if they were already set. MyPy might need help here if it can't infer.
        # Logic flow implies they are floats if we reach here post-initialization.
        orb_high_val: float = self.orb_high  # type: ignore[assignment]
        orb_low_val: float = self.orb_low  # type: ignore[assignment]

        debug_msg: str = (
            f"{self.symbol}: Price=${current_price:.2f}, "
            f"ORB H=${orb_high_val:.2f}, L=${orb_low_val:.2f}"
        )
        logger.debug(debug_msg)

        action: Optional[str] = None
        message: Optional[str] = None

        if not self.alerted_today_breakout and current_price > orb_high_val:
            action = "BUY_BREAKOUT"
            self.alerted_today_breakout = True
            message = (
                f"📈 ORB BREAKOUT: {self.symbol}\n"
                f"Action: Potential BUY\n"
                f"Price: ${current_price:.2f}\n"
                f"ORB High: ${orb_high_val:.2f}\n"
                f"ORB Low: ${orb_low_val:.2f}"
            )
            logger.info(f"Breakout detected for {self.symbol} at ${current_price:.2f}")

        elif not self.alerted_today_breakdown and current_price < orb_low_val:
            action = "SELL_BREAKDOWN"
            self.alerted_today_breakdown = True
            message = (
                f"📉 ORB BREAKDOWN: {self.symbol}\n"
                f"Action: Potential SELL/SHORT\n"
                f"Price: ${current_price:.2f}\n"
                f"ORB High: ${orb_high_val:.2f}\n"
                f"ORB Low: ${orb_low_val:.2f}"
            )
            logger.info(f"Breakdown detected for {self.symbol} at ${current_price:.2f}")

        if action:
            return action, current_price, message
        else:
            return None, None, None


if __name__ == "__main__":
    logger.info("Testing ORBStrategy...")
    if not config.ALPHA_VANTAGE_API_KEY:
        logger.error(
            "ALPHA_VANTAGE_API_KEY not set in .env file. Please set it to test ORBStrategy."
        )
    else:
        fetcher = DataFetcher(api_key=config.ALPHA_VANTAGE_API_KEY)

        # Test with a known symbol
        test_symbol = (
            "AAPL"  # Make sure this is in your TICKER_SYMBOLS in config or use a fixed one
        )
        orb_strategy = ORBStrategy(symbol=test_symbol, data_fetcher=fetcher)

        logger.info(f"\n1. Attempting to initialize ORB for {test_symbol}...")
        initialized = orb_strategy.initialize_strategy_for_day()
        if initialized:
            log_msg = (
                f"ORB initialized for {test_symbol}: High={orb_strategy.orb_high}, "
                f"Low={orb_strategy.orb_low}"
            )
            logger.info(log_msg)

            logger.info(f"\n2. Simulating price checks for {test_symbol}:")
            # Simulate price above ORB high
            if orb_strategy.orb_high:
                simulated_breakout_price = orb_strategy.orb_high * 1.01
                # Mock get_current_price to return this simulated price
                original_get_price = fetcher.get_current_price
                fetcher.get_current_price = (  # type: ignore[method-assign]
                    lambda symbol: simulated_breakout_price if symbol == test_symbol else None
                )
                logger.info(
                    f"Simulating current price = ${simulated_breakout_price:.2f} (Breakout)"
                )
                action, price, msg = orb_strategy.evaluate()
                if action == "BUY_BREAKOUT":
                    success_msg = (
                        f"SUCCESS: Detected {action} for {test_symbol} at ${price:.2f}. "
                        f"Message: \n{msg}"
                    )
                    logger.info(success_msg)
                else:
                    logger.error(f"FAILURE: Expected BUY_BREAKOUT, got {action}")
                fetcher.get_current_price = original_get_price  # Restore
            else:
                logger.warning("Skipping breakout simulation as ORB high is not set.")

            # Simulate price below ORB low
            if orb_strategy.orb_low:
                simulated_breakdown_price = orb_strategy.orb_low * 0.99
                original_get_price = fetcher.get_current_price
                fetcher.get_current_price = (  # type: ignore[method-assign]
                    lambda symbol: simulated_breakdown_price if symbol == test_symbol else None
                )
                logger.info(
                    f"Simulating current price = ${simulated_breakdown_price:.2f} (Breakdown)"
                )
                action, price, msg = orb_strategy.evaluate()
                if action == "SELL_BREAKDOWN":
                    success_msg = (
                        f"SUCCESS: Detected {action} for {test_symbol} at ${price:.2f}. "
                        f"Message: \n{msg}"
                    )
                    logger.info(success_msg)
                else:
                    logger.error(f"FAILURE: Expected SELL_BREAKDOWN, got {action}")
                fetcher.get_current_price = original_get_price  # Restore
            else:
                logger.warning("Skipping breakdown simulation as ORB low is not set.")

            # Simulate price within range
            if orb_strategy.orb_low and orb_strategy.orb_high:
                simulated_hold_price = (orb_strategy.orb_high + orb_strategy.orb_low) / 2
                original_get_price = fetcher.get_current_price
                fetcher.get_current_price = (  # type: ignore[method-assign]
                    lambda symbol: simulated_hold_price if symbol == test_symbol else None
                )
                logger.info(f"Simulating current price = ${simulated_hold_price:.2f} (Hold)")
                action, price, msg = orb_strategy.evaluate()
                if action is None:
                    logger.info(
                        f"SUCCESS: No action for {test_symbol} at "
                        f"${simulated_hold_price:.2f}, as expected."
                    )
                else:
                    logger.error(f"FAILURE: Expected no action, got {action}")
                fetcher.get_current_price = original_get_price  # Restore
            else:
                logger.warning("Skipping in-range simulation as ORB is not fully set.")

            logger.info(
                f"\n3. Resetting daily state for {test_symbol} and re-evaluating "
                "(should not alert again immediately for breakout):"
            )
            # orb_strategy.reset_daily_state() # This would allow re-alerting.
            # We want to test it *doesn't* re-alert without reset.
            if orb_strategy.orb_high:
                simulated_breakout_price = orb_strategy.orb_high * 1.01
                original_get_price = fetcher.get_current_price
                fetcher.get_current_price = (  # type: ignore[method-assign]
                    lambda symbol: simulated_breakout_price if symbol == test_symbol else None
                )
                action, price_ignored, msg_ignored = orb_strategy.evaluate() # Use proper unpack
                if action is None:  # Because alerted_today_breakout should be True
                    logger.info(
                        f"SUCCESS: No further BUY_BREAKOUT alert for {test_symbol} as expected."
                    )
                else:
                    logger.error(
                        f"FAILURE: Expected no action, but got {action} on second breakout check."
                    )
                fetcher.get_current_price = original_get_price  # Restore
            else:
                logger.warning("Skipping re-alert test as ORB high is not set.")

        else:
            logger.error(f"Could not initialize ORB for {test_symbol} for full testing.")

        logger.info("\nORBStrategy tests complete.")
