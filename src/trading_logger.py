import logging
import json
import pandas as pd
from datetime import datetime
import os
from pathlib import Path
from typing import Dict #SUGGESTED EDIT FROM COPILOT

class TradingLogger:
    def __init__(self):
        # Get project root directory (parent of src/)
        self.project_root = Path(__file__).resolve().parents[1]
        self.logs_dir = self.project_root / 'logs'
        self.setup_logging()
        
        # Load existing history from previous deployments
        self.trade_history = self._load_existing_trades()
        self.portfolio_history = self._load_existing_portfolio()
        
    def setup_logging(self):
        """Set up logging system"""
        # Create logs directory in project root
        self.logs_dir.mkdir(exist_ok=True)
        
        # Set log format
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.logs_dir / 'trading_bot.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _load_existing_trades(self):
        """Load existing trade history from previous deployments"""
        trade_file = self.logs_dir / 'trade_history.json'
        if trade_file.exists():
            try:
                with open(trade_file, 'r') as f:
                    data = json.load(f)
                    self.logger.info(f"Loaded {len(data)} existing trades from previous deployments")
                    return data
            except Exception as e:
                self.logger.warning(f"Could not load existing trade history: {e}")
        return []
    
    def _load_existing_portfolio(self):
        """Load existing portfolio history from previous deployments"""
        portfolio_file = self.logs_dir / 'portfolio_history.json'
        if portfolio_file.exists():
            try:
                with open(portfolio_file, 'r') as f:
                    data = json.load(f)
                    self.logger.info(f"Loaded {len(data)} existing portfolio records from previous deployments")
                    return data
            except Exception as e:
                self.logger.warning(f"Could not load existing portfolio history: {e}")
        return []
    
    def log_trade(self, trade_data: Dict):
        """Log trade execution"""
        trade_entry = {
            'timestamp': datetime.now().isoformat(),
            'trade_id': len(self.trade_history) + 1,
            **trade_data
        }
        
        self.trade_history.append(trade_entry)
        
        # Save to JSON file
        with open(self.logs_dir / 'trade_history.json', 'w') as f:
            json.dump(self.trade_history, f, indent=2)
            
        # Save to CSV file
        df = pd.DataFrame(self.trade_history)
        df.to_csv(self.logs_dir / 'trade_history.csv', index=False)

        self.logger.info(f"Trade executed: {trade_data}")
    
    def log_portfolio_update(self, portfolio_data: Dict):
        """Log portfolio update"""
        portfolio_entry = {
            'timestamp': datetime.now().isoformat(),
            **portfolio_data
        }
        
        self.portfolio_history.append(portfolio_entry)
        
        # Save to JSON file
        with open(self.logs_dir / 'portfolio_history.json', 'w') as f:
            json.dump(self.portfolio_history, f, indent=2)
            
        # Save to CSV file
        df = pd.DataFrame(self.portfolio_history)
        df.to_csv(self.logs_dir / 'portfolio_history.csv', index=False)
    
    def log_market_data(self, market_data: Dict):
        """Log market data"""
        market_entry = {
            'timestamp': datetime.now().isoformat(),
            **market_data
        }
        
        # Save to JSONL file
        try:
            with open(self.logs_dir / 'market_data.jsonl', 'a') as f:
                f.write(json.dumps(market_entry) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to log market data: {e}")
    
    def log_strategy_signal(self, signal_data: Dict):
        """Log strategy signal"""
        signal_entry = {
            'timestamp': datetime.now().isoformat(),
            **signal_data
        }
        
        # Save to JSONL file
        try:
            with open(self.logs_dir / 'strategy_signals.jsonl', 'a') as f:
                f.write(json.dumps(signal_entry) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to log strategy signal: {e}")