import importlib
import os
from unittest import mock

import pytest

# Import the module to be tested
# We will reload it in test functions to simulate different env var states
import config


def test_alpha_vantage_api_key_loaded(monkeypatch):
    """Test that ALPHA_VANTAGE_API_KEY is loaded from environment."""
    expected_key = "test_api_key_123"
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", expected_key)

    # Reload config to pick up the new environment variable
    importlib.reload(config)

    assert config.ALPHA_VANTAGE_API_KEY == expected_key


def test_alpha_vantage_api_key_not_set():
    """Test that ALPHA_VANTAGE_API_KEY is None if not set in environment."""
    # Ensure the variable is not in the environment for this test
    with mock.patch.dict(os.environ):
        if "ALPHA_VANTAGE_API_KEY" in os.environ:
            del os.environ["ALPHA_VANTAGE_API_KEY"]

        importlib.reload(config)
        assert config.ALPHA_VANTAGE_API_KEY is None


def test_default_ticker_symbols():
    """Test that default TICKER_SYMBOLS are set correctly."""
    # Reload config to ensure defaults are picked up if not overridden by any test env var
    # (though TICKER_SYMBOLS is not typically set by env var in current config.py)
    importlib.reload(config)
    expected_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    assert config.TICKER_SYMBOLS == expected_symbols


def test_default_orb_interval():
    """Test that default ORB_INTERVAL is set correctly."""
    importlib.reload(config)
    assert config.ORB_INTERVAL == "15min"


def test_default_monitoring_interval_seconds():
    """Test that default MONITORING_INTERVAL_SECONDS is set correctly."""
    importlib.reload(config)
    assert config.MONITORING_INTERVAL_SECONDS == 60


def test_default_market_hours():
    """Test that default market hours are set correctly."""
    importlib.reload(config)
    assert config.MARKET_OPEN_HOUR_EST == 9
    assert config.MARKET_OPEN_MINUTE_EST == 30
    assert config.MARKET_CLOSE_HOUR_EST == 16
    assert config.MARKET_CLOSE_MINUTE_EST == 0


def test_default_log_level():
    """Test that default LOG_LEVEL is set correctly."""
    importlib.reload(config)
    assert config.LOG_LEVEL == "INFO"


# To run these tests, navigate to the project root and run:
# pytest tests/unit/test_config.py
# Ensure .env file doesn't interfere by setting values that these tests don't expect,
# or ensure the tests explicitly manage/override environment for their scope.
# Monkeypatch is generally good for this.
# Note: python-dotenv loads .env on first import of config.py.
# Reloading config re-triggers os.getenv, but load_dotenv() may not re-read .env
# unless module is fully reloaded or load_dotenv called again.
# Monkeypatching os.environ or using monkeypatch.setenv is robust here.

# A better approach for testing config that relies on .env might be to
# mock dotenv.load_dotenv itself or to ensure a specific test .env file is used.
# However, for ALPHA_VANTAGE_API_KEY, os.getenv is direct, so monkeypatch works well.
# For other vars, they are hardcoded defaults in config.py, so reload is sufficient.


@pytest.fixture(autouse=True)
def clear_env_alpha_key_after_test():
    """Fixture to ensure ALPHA_VANTAGE_API_KEY is cleared from env after each test if set by it."""
    # This is to prevent a test that sets it from affecting a subsequent test
    # that expects it to be unset, due to Python's module caching.
    original_value = os.environ.get("ALPHA_VANTAGE_API_KEY")
    yield
    if original_value is None:
        if "ALPHA_VANTAGE_API_KEY" in os.environ:
            del os.environ["ALPHA_VANTAGE_API_KEY"]
    else:
        os.environ["ALPHA_VANTAGE_API_KEY"] = original_value
    # Reload config to restore its state based on the (now restored) environment
    importlib.reload(config)
