import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file (contains API keys)
load_dotenv()

class Config:
    """
    Crypto-Optimized Trading Bot Configuration
    Enhanced for cryptocurrency spot trading competition
    """
    
    def __init__(self):
        # ==================== API Configuration ====================
        self.ROOSTOO_API_KEY = os.getenv('ROOSTOO_API_KEY', 'your_api_key_here')
        self.ROOSTOO_SECRET = os.getenv('ROOSTOO_SECRET', 'your_secret_here')
        self.ROOSTOO_BASE_URL = os.getenv('ROOSTOO_BASE_URL', 'https://api.roostoo.com')
        
        self.HORUS_API_KEY = os.getenv('HORUS_API_KEY', 'your_horus_api_key_here')
        self.HORUS_BASE_URL = os.getenv('HORUS_BASE_URL', 'https://api.horus.com')
        
        # ==================== Trading Basic Configuration ====================
        self.INITIAL_CASH = 10000              # Initial capital
        
        # Multi-pair support (BTC and ETH)
        self.SUPPORTED_PAIRS = ["BTC/USD", "ETH/USD"]  # Pairs to trade
        self.TRADE_PAIR = "BTC/USD"            # Default trading pair (for backward compatibility)
        self.BASE_CURRENCY = "BTC"             # Base currency
        self.QUOTE_CURRENCY = "USD"            # Quote currency
        
        # ==================== MACD Strategy Parameters ====================
        self.FAST_EMA_PERIOD = 12              # Fast EMA period
        self.SLOW_EMA_PERIOD = 26              # Slow EMA period  
        self.SIGNAL_PERIOD = 9                 # Signal line period
        
        # ==================== Cryptocurrency Optimization Parameters ====================
        self.CRYPTO_OPTIMIZED_PARAMS = {
            'BTC/USD': {'fast_period': 8, 'slow_period': 21, 'signal_period': 5},
            'ETH/USD': {'fast_period': 6, 'slow_period': 18, 'signal_period': 4},
            'default': {'fast_period': 10, 'slow_period': 24, 'signal_period': 6}
        }
        
        # Volatility adaptive parameters
        self.VOLATILITY_LOOKBACK = 20          # Volatility lookback window
        self.HIGH_VOL_MULTIPLIER = 1.5         # High volatility multiplier
        self.VOLATILITY_ALERT_THRESHOLD = 0.08 # Volatility alert threshold (8%)
        self.MIN_VOLATILITY_FOR_TRADE = 0.005  # Minimum volatility requirement (0.5%)
        
        # ==================== Risk Management Parameters ====================
        # Stop loss and take profit
        self.STOP_LOSS_PCT = 0.03              # Base stop loss 3%
        self.TAKE_PROFIT_PCT = 0.03            # Base take profit 3%
        self.TRAILING_STOP_PCT = 0.015         # Trailing stop distance 1.5%
        self.TRAILING_ACTIVATION_PCT = 0.02    # Trailing stop activation 2%
        
        # Position management
        self.MAX_POSITION_SIZE = 0.2           # Maximum single position size 20%
        self.MAX_SINGLE_POSITION = 0.2         # Maximum single asset allocation 20%
        self.MIN_TRADE_VALUE = 1.0             # Minimum trade amount $1
        self.MIN_BTC_AMOUNT = 0.00001          # Minimum BTC trade amount
        
        # ==================== Time Control Parameters ====================
        self.TRADE_INTERVAL = 60               # Trading interval 60 seconds
        self.MAX_POSITION_HOURS = 48           # Maximum holding period 48 hours
        self.MIN_TRADE_INTERVAL_SECONDS = 3600 # Same-direction trade cooldown 1 hour
        
        # ==================== Cryptocurrency Trading Limits ====================
        self.DAILY_TRADE_LIMIT = 15            # Maximum daily trades
        self.ENABLE_MARKET_HOURS_FILTER = True # Enable market hours filtering
        self.REDUCE_TRADING_IN_HIGH_VOL_HOURS = True  # Reduce trading in high volatility hours
        
        # ==================== Risk Alert Thresholds ====================
        self.DRAWDOWN_ALERT = 0.05             # Drawdown alert 5%
        self.CONSECUTIVE_LOSS_ALERT = 3        # Consecutive loss alert count
        self.PORTFOLIO_CONCENTRATION_ALERT = 0.85  # Portfolio concentration alert 85%
        
        # ==================== Logging and Monitoring Configuration ====================
        self.LOG_LEVEL = "INFO"
        self.ENABLE_DASHBOARD = False          # Disable dashboard in production
        
        # ==================== Initial Trade Configuration ====================
        self.INITIAL_TRADE_AMOUNT = 1.14       # Initial trade amount $1.14 (competition requirement)
        
    def get_crypto_optimized_params(self, symbol: str = None) -> Dict[str, int]:
        """
        Get cryptocurrency-optimized MACD parameters
        """
        if symbol and symbol in self.CRYPTO_OPTIMIZED_PARAMS:
            return self.CRYPTO_OPTIMIZED_PARAMS[symbol]
        return self.CRYPTO_OPTIMIZED_PARAMS['default']
    
    def validate_config(self) -> bool:
        """
        Validate configuration parameter sanity
        """
        try:
            # Check required API keys
            if self.ROOSTOO_API_KEY in ['your_api_key_here', '']:
                raise ValueError("ROOSTOO_API_KEY not configured")
                
            if self.ROOSTOO_SECRET in ['your_secret_here', '']:
                raise ValueError("ROOSTOO_SECRET not configured")
            
            # Check risk parameter sanity
            if self.STOP_LOSS_PCT <= 0 or self.STOP_LOSS_PCT > 0.1:
                raise ValueError("STOP_LOSS_PCT must be between 0 and 0.1")
                
            if self.MAX_POSITION_SIZE <= 0 or self.MAX_POSITION_SIZE > 0.5:
                raise ValueError("MAX_POSITION_SIZE must be between 0 and 0.5")
                
            if self.TRADE_INTERVAL < 30:
                raise ValueError("TRADE_INTERVAL must be at least 30 seconds")
            
            return True
            
        except Exception as e:
            print(f"Configuration validation failed: {e}")
            return False
