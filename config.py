# Configuration for the trading bot
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# API Keys
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

# Trading Parameters
TICKER_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"] # Example tickers
ORB_INTERVAL = "15min" # Interval for ORB calculation
MONITORING_INTERVAL_SECONDS = 60 # How often to check for price updates

# Market Hours (EST)
# TODO: Use pytz for robust timezone handling
MARKET_OPEN_HOUR_EST = 9
MARKET_OPEN_MINUTE_EST = 30
MARKET_CLOSE_HOUR_EST = 16
MARKET_CLOSE_MINUTE_EST = 0

# Basic Logging Configuration (can be expanded)
LOG_LEVEL = "INFO"
