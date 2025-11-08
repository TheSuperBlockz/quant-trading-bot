import os
from dotenv import load_dotenv

# Load environment variables from .env file (contains API keys)
load_dotenv()

class Config:
    # Roostoo API Configuration (from environment variables)
    ROOSTOO_API_KEY = os.getenv('ROOSTOO_API_KEY', 'your_api_key_here')
    ROOSTOO_SECRET = os.getenv('ROOSTOO_SECRET', 'your_secret_here')
    ROOSTOO_BASE_URL = os.getenv('ROOSTOO_BASE_URL', 'https://api.roostoo.com')
    
    # Trading Configuration
    INITIAL_CASH = 10000  # Initial capital
    TRADE_PAIR = "BTC/USD"  # Trading pair
    MAX_POSITION_SIZE = 0.1  # Maximum position size ratio
    
    # MACD Strategy Parameters
    FAST_EMA_PERIOD = 12
    SLOW_EMA_PERIOD = 26
    SIGNAL_PERIOD = 9
    
    # Risk Control
    STOP_LOSS_PCT = 0.02  # 2% stop loss
    TAKE_PROFIT_PCT = 0.05  # 5% take profit
    
    # Trading Frequency Control
    TRADE_INTERVAL = 60  # Trading check interval (seconds)
    
    # Logging Configuration
    LOG_LEVEL = "INFO"
    ENABLE_DASHBOARD = True  # Enable dashboard for local testing