import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Roostoo API配置
    ROOSTOO_API_KEY = os.getenv('ROOSTOO_API_KEY', 'your_api_key_here')
    ROOSTOO_SECRET = os.getenv('ROOSTOO_SECRET', 'your_secret_here')
    ROOSTOO_BASE_URL = os.getenv('ROOSTOO_BASE_URL', 'https://api.roostoo.com')
    
    # 交易配置
    INITIAL_CASH = 10000  # 初始资金
    TRADE_PAIR = "BTC/USD"  # 交易对
    MAX_POSITION_SIZE = 0.1  # 最大仓位比例
    
    # MACE策略参数
    FAST_EMA_PERIOD = 12
    SLOW_EMA_PERIOD = 26
    SIGNAL_PERIOD = 9
    
    # 风险控制
    STOP_LOSS_PCT = 0.02  # 2% 止损
    TAKE_PROFIT_PCT = 0.05  # 5% 止盈
    
    # 交易频率控制
    TRADE_INTERVAL = 60  # 交易检查间隔（秒）
    
    # 日志配置
    LOG_LEVEL = "INFO"
    ENABLE_DASHBOARD = True  # 本地测试时启用仪表盘