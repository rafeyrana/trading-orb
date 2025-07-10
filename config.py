# Configuration for the trading bot
import os
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# API Keys
ALPHA_VANTAGE_API_KEY: Optional[str] = os.getenv("ALPHA_VANTAGE_API_KEY")

# Trading Parameters
TICKER_SYMBOLS: List[str] = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]  # Example tickers
ORB_INTERVAL: str = "15min"  # Interval for ORB calculation
MONITORING_INTERVAL_SECONDS: int = 60  # How often to check for price updates

# Market Hours (EST)
# TODO: Use pytz for robust timezone handling
MARKET_OPEN_HOUR_EST: int = 9
MARKET_OPEN_MINUTE_EST: int = 30
MARKET_CLOSE_HOUR_EST: int = 16
MARKET_CLOSE_MINUTE_EST: int = 0

# Basic Logging Configuration (can be expanded)
LOG_LEVEL: str = "INFO"
