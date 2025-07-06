from unittest import mock
from typing import Optional # Added Optional

import pytest

from data_fetcher import DataFetcher  # For type hinting mock
from strategy import ORBStrategy  # Assuming strategy.py is accessible


@pytest.fixture
def mock_data_fetcher() -> mock.Mock:
    """Fixture to create a mock DataFetcher."""
    fetcher = mock.Mock(spec=DataFetcher)
    # Default mock values, can be overridden in tests
    fetcher.get_opening_range_high_low.return_value = (None, None)
    fetcher.get_current_price.return_value = None
    return fetcher


@pytest.fixture
def orb_strategy(mock_data_fetcher: mock.Mock) -> ORBStrategy:
    """Fixture to create an ORBStrategy instance with a mock DataFetcher."""
    return ORBStrategy(symbol="TESTSYM", data_fetcher=mock_data_fetcher, orb_interval="15min")


# --- TradingStrategy Base Class (Minimal tests, as it's abstract) ---
def test_trading_strategy_init(mock_data_fetcher: mock.Mock):
    """Test basic initialization of a concrete class derived from TradingStrategy."""
    strategy = ORBStrategy(symbol="BASESYM", data_fetcher=mock_data_fetcher)
    assert strategy.symbol == "BASESYM"
    assert strategy.data_fetcher == mock_data_fetcher
    assert strategy.orb_high is None
    assert strategy.orb_low is None
    assert not strategy.alerted_today_breakout
    assert not strategy.alerted_today_breakdown


def test_trading_strategy_reset_daily_state(orb_strategy: ORBStrategy):
    """Test reset_daily_state method."""
    # Set some state
    orb_strategy.orb_high = 100.0
    orb_strategy.orb_low = 90.0
    orb_strategy.alerted_today_breakout = True
    orb_strategy.alerted_today_breakdown = True

    orb_strategy.reset_daily_state()

    assert orb_strategy.orb_high is None
    assert orb_strategy.orb_low is None
    assert not orb_strategy.alerted_today_breakout
    assert not orb_strategy.alerted_today_breakdown


# --- ORBStrategy Tests ---
def test_orb_strategy_init(mock_data_fetcher: mock.Mock):
    """Test ORBStrategy specific initialization."""
    strategy = ORBStrategy(symbol="ORBTEST", data_fetcher=mock_data_fetcher, orb_interval="5min")
    assert strategy.symbol == "ORBTEST"
    assert strategy.orb_interval == "5min"


def test_initialize_strategy_for_day_success(
    orb_strategy: ORBStrategy, mock_data_fetcher: mock.Mock
):
    """Test initialize_strategy_for_day successfully fetches and sets ORB."""
    mock_data_fetcher.get_opening_range_high_low.return_value = (105.0, 95.0)

    initialized = orb_strategy.initialize_strategy_for_day()

    assert initialized is True
    assert orb_strategy.orb_high == 105.0
    assert orb_strategy.orb_low == 95.0
    mock_data_fetcher.get_opening_range_high_low.assert_called_once_with("TESTSYM", "15min")


def test_initialize_strategy_for_day_already_initialized(
    orb_strategy: ORBStrategy, mock_data_fetcher: mock.Mock
):
    """Test initialize_strategy_for_day does nothing if ORB already set."""
    orb_strategy.orb_high = 100.0
    orb_strategy.orb_low = 90.0

    initialized = orb_strategy.initialize_strategy_for_day()

    assert initialized is True  # Still returns True as it's "initialized"
    assert orb_strategy.orb_high == 100.0  # Unchanged
    assert orb_strategy.orb_low == 90.0  # Unchanged
    mock_data_fetcher.get_opening_range_high_low.assert_not_called()


def test_initialize_strategy_for_day_fetch_fails(
    orb_strategy: ORBStrategy, mock_data_fetcher: mock.Mock
):
    """Test initialize_strategy_for_day when data fetcher returns None."""
    mock_data_fetcher.get_opening_range_high_low.return_value = (None, None)

    initialized = orb_strategy.initialize_strategy_for_day()

    assert initialized is False
    assert orb_strategy.orb_high is None
    assert orb_strategy.orb_low is None


# --- ORBStrategy.evaluate() Tests ---
def test_evaluate_orb_not_initialized_tries_to_init(
    orb_strategy: ORBStrategy, mock_data_fetcher: mock.Mock
):
    """Test evaluate calls initialize_strategy_for_day if ORB is not set."""
    mock_data_fetcher.get_opening_range_high_low.return_value = (110.0, 100.0)  # Successful init
    mock_data_fetcher.get_current_price.return_value = 105.0  # Price within range

    action, price, message = orb_strategy.evaluate()

    mock_data_fetcher.get_opening_range_high_low.assert_called_once()
    assert orb_strategy.orb_high == 110.0  # Check that init happened
    assert action is None  # No breakout/down


def test_evaluate_orb_init_fails_during_evaluate(
    orb_strategy: ORBStrategy, mock_data_fetcher: mock.Mock
):
    """Test evaluate returns None if ORB init fails during the call."""
    mock_data_fetcher.get_opening_range_high_low.return_value = (None, None)  # Init fails

    action, price, message = orb_strategy.evaluate()

    assert action is None
    assert price is None
    assert message is None
    # Should not try to get price if ORB failed
    mock_data_fetcher.get_current_price.assert_not_called()


def test_evaluate_get_current_price_fails(orb_strategy: ORBStrategy, mock_data_fetcher: mock.Mock):
    """Test evaluate returns None if get_current_price fails."""
    orb_strategy.orb_high = 110.0
    orb_strategy.orb_low = 100.0
    mock_data_fetcher.get_current_price.return_value = None  # Current price fetch fails

    action, price, message = orb_strategy.evaluate()

    assert action is None
    assert price is None
    assert message is None


# Parameterize evaluate for different price scenarios
# (current_price, expected_action, description)
EVALUATE_SCENARIOS = [
    (115.0, "BUY_BREAKOUT", "Price breaks above ORB high"),
    (95.0, "SELL_BREAKDOWN", "Price breaks below ORB low"),
    (105.0, None, "Price within ORB range"),
    (110.0, None, "Price equals ORB high (no breakout)"),  # Assuming > for breakout
    (100.0, None, "Price equals ORB low (no breakdown)"),  # Assuming < for breakdown
]


@pytest.mark.parametrize("current_mock_price, expected_action, description", EVALUATE_SCENARIOS)
def test_evaluate_breakout_breakdown_hold(
    current_mock_price: float,
    expected_action: Optional[str],
    description: str,
    orb_strategy: ORBStrategy,
    mock_data_fetcher: mock.Mock,
):
    """Test evaluate for breakout, breakdown, and hold scenarios."""
    orb_strategy.orb_high = 110.0
    orb_strategy.orb_low = 100.0
    orb_strategy.alerted_today_breakout = False  # Ensure fresh state for alerts
    orb_strategy.alerted_today_breakdown = False

    mock_data_fetcher.get_current_price.return_value = current_mock_price

    action, price, message = orb_strategy.evaluate()

    assert action == expected_action
    if expected_action:
        assert price == current_mock_price
        assert message is not None
        assert orb_strategy.symbol in message
        if expected_action == "BUY_BREAKOUT":
            assert "BREAKOUT" in message
            assert orb_strategy.alerted_today_breakout is True
        elif expected_action == "SELL_BREAKDOWN":
            assert "BREAKDOWN" in message
            assert orb_strategy.alerted_today_breakdown is True
    else:
        assert price is None
        assert message is None


def test_evaluate_no_repeated_breakout_alert(
    orb_strategy: ORBStrategy, mock_data_fetcher: mock.Mock
):
    """Test that a second breakout alert is not generated on the same day."""
    orb_strategy.orb_high = 110.0
    orb_strategy.orb_low = 100.0
    mock_data_fetcher.get_current_price.return_value = 115.0  # Breakout price

    # First breakout
    action1, _, _ = orb_strategy.evaluate()
    assert action1 == "BUY_BREAKOUT"
    assert orb_strategy.alerted_today_breakout is True

    # Second attempt at breakout price
    action2, _, _ = orb_strategy.evaluate()
    assert action2 is None  # Should not alert again


def test_evaluate_no_repeated_breakdown_alert(
    orb_strategy: ORBStrategy, mock_data_fetcher: mock.Mock
):
    """Test that a second breakdown alert is not generated on the same day."""
    orb_strategy.orb_high = 110.0
    orb_strategy.orb_low = 100.0
    mock_data_fetcher.get_current_price.return_value = 95.0  # Breakdown price

    # First breakdown
    action1, _, _ = orb_strategy.evaluate()
    assert action1 == "SELL_BREAKDOWN"
    assert orb_strategy.alerted_today_breakdown is True

    # Second attempt at breakdown price
    action2, _, _ = orb_strategy.evaluate()
    assert action2 is None  # Should not alert again


def test_evaluate_breakout_then_breakdown_alerts_both(
    orb_strategy: ORBStrategy, mock_data_fetcher: mock.Mock
):
    """Test if a breakout occurs, and then a breakdown, both should alert."""
    orb_strategy.orb_high = 110.0
    orb_strategy.orb_low = 100.0

    # Simulate Breakout
    mock_data_fetcher.get_current_price.return_value = 115.0
    action_breakout, _, _ = orb_strategy.evaluate()
    assert action_breakout == "BUY_BREAKOUT"
    assert orb_strategy.alerted_today_breakout is True
    assert orb_strategy.alerted_today_breakdown is False  # Ensure this wasn't touched

    # Simulate Breakdown
    mock_data_fetcher.get_current_price.return_value = 95.0
    action_breakdown, _, _ = orb_strategy.evaluate()
    assert action_breakdown == "SELL_BREAKDOWN"
    assert orb_strategy.alerted_today_breakdown is True
    # alerted_today_breakout should still be true from previous event
    assert orb_strategy.alerted_today_breakout is True


# To run: pytest tests/unit/test_strategy.py
