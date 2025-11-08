import logging
import json
import pandas as pd
from datetime import datetime
import os
from pathlib import Path
from typing import Dict #SUGGESTED EDIT FROM COPILOT

class TradingLogger:
    def __init__(self):
        self.setup_logging()
        self.trade_history = []
        self.portfolio_history = []
        
    def setup_logging(self):
        """设置日志系统"""
        # 创建logs目录
        os.makedirs('logs', exist_ok=True)
        
        # 设置日志格式
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/trading_bot.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log_trade(self, trade_data: Dict):
        """记录交易"""
        trade_entry = {
            'timestamp': datetime.now().isoformat(),
            'trade_id': len(self.trade_history) + 1,
            **trade_data
        }
        
        self.trade_history.append(trade_entry)
        
        # 保存到JSON文件
        with open('logs/trade_history.json', 'w') as f:
            json.dump(self.trade_history, f, indent=2)
            
        # 保存到CSV文件
        df = pd.DataFrame(self.trade_history)
        df.to_csv('logs/trade_history.csv', index=False)
        
        self.logger.info(f"交易执行: {trade_data}")
    
    def log_portfolio_update(self, portfolio_data: Dict):
        """记录投资组合更新"""
        portfolio_entry = {
            'timestamp': datetime.now().isoformat(),
            **portfolio_data
        }
        
        self.portfolio_history.append(portfolio_entry)
        
        # 保存到JSON文件
        with open('logs/portfolio_history.json', 'w') as f:
            json.dump(self.portfolio_history, f, indent=2)
            
        # 保存到CSV文件
        df = pd.DataFrame(self.portfolio_history)
        df.to_csv('logs/portfolio_history.csv', index=False)
    
    def log_market_data(self, market_data: Dict):
        """记录市场数据"""
        market_entry = {
            'timestamp': datetime.now().isoformat(),
            **market_data
        }
        
        # 保存到JSONL文件
        try:
            with open('logs/market_data.jsonl', 'a') as f:
                f.write(json.dumps(market_entry) + '\n')
        except Exception as e:
            self.logger.error(f"记录市场数据失败: {e}")
    
    def log_strategy_signal(self, signal_data: Dict):
        """记录策略信号"""
        signal_entry = {
            'timestamp': datetime.now().isoformat(),
            **signal_data
        }
        
        # 保存到JSONL文件
        try:
            with open('logs/strategy_signals.jsonl', 'a') as f:
                f.write(json.dumps(signal_entry) + '\n')
        except Exception as e:
            self.logger.error(f"记录策略信号失败: {e}")