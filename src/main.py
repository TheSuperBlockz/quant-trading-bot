#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project root to path so we can import config
project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import time
import threading
from datetime import datetime
from typing import Dict  #SUGGESTED EDIT FROM COPILOT
from trading_logger import TradingLogger
from roostoo_client import RoostooClient
from strategy import MACEStrategy, Action
from config.config import Config

class TradingBot:
    def __init__(self, enable_dashboard=False):
        self.config = Config()
        self.logger = TradingLogger()
        self.roostoo = RoostooClient()
        self.strategy = MACEStrategy(
            fast_period=self.config.FAST_EMA_PERIOD,
            slow_period=self.config.SLOW_EMA_PERIOD,
            signal_period=self.config.SIGNAL_PERIOD
        )
        self.running = True
        self.enable_dashboard = enable_dashboard
        self.dashboard_thread = None
        
        if enable_dashboard:
            self.start_dashboard()
    
    def start_dashboard(self):
        """Start dashboard (local testing only)"""
        try:
            from dashboard import start_dashboard
            self.dashboard_thread = threading.Thread(target=start_dashboard, daemon=True)
            self.dashboard_thread.start()
            self.logger.logger.info("Dashboard started: http://localhost:8050")
        except Exception as e:
            self.logger.logger.error(f"Failed to start dashboard: {e}")
    
    def get_portfolio_value(self, balance_data: Dict, current_prices: Dict) -> float:
        """Calculate total portfolio value"""
        try:
            cash = balance_data.get('USD', {}).get('free', 0)
            total_value = cash
            
            # Calculate holdings value
            for coin, balance in balance_data.items():
                if coin != 'USD' and balance.get('free', 0) > 0:
                    coin_value = balance['free'] * current_prices.get(coin, 0)
                    total_value += coin_value
            
            return total_value
        except Exception as e:
            self.logger.logger.error(f"Failed to calculate portfolio value: {e}")
            return 0
    
    def execute_trade(self, decision, balance_data: Dict):
        """Execute trade"""
        try:
            symbol = self.config.TRADE_PAIR
            base_currency = symbol.split('/')[0]  # BTC
            quote_currency = symbol.split('/')[1]  # USD
            
            if decision.action == Action.BUY:
                # Calculate buy quantity
                available_cash = balance_data.get(quote_currency, {}).get('free', 0)
                max_trade_value = available_cash * self.config.MAX_POSITION_SIZE
                quantity = max_trade_value / decision.price
                
                if quantity * decision.price < 10:  # Minimum trade amount check
                    self.logger.logger.info("Trade amount too small, skipping")
                    return
                
                # Execute buy
                result = self.roostoo.place_order(
                    symbol=symbol,
                    side='BUY',
                    quantity=quantity
                )
                
                if 'error' not in result:
                    trade_data = {
                        'action': 'BUY',
                        'symbol': symbol,
                        'quantity': quantity,
                        'price': decision.price,
                        'total': quantity * decision.price,
                        'reason': decision.reason
                    }
                    self.logger.log_trade(trade_data)
                    
            elif decision.action == Action.SELL:
                # Calculate sell quantity
                available_coin = balance_data.get(base_currency, {}).get('free', 0)
                quantity = available_coin * self.config.MAX_POSITION_SIZE
                
                if quantity * decision.price < 10:  # Minimum trade amount check
                    self.logger.logger.info("Trade amount too small, skipping")
                    return
                
                # Execute sell
                result = self.roostoo.place_order(
                    symbol=symbol,
                    side='SELL',
                    quantity=quantity
                )
                
                if 'error' not in result:
                    trade_data = {
                        'action': 'SELL',
                        'symbol': symbol,
                        'quantity': quantity,
                        'price': decision.price,
                        'total': quantity * decision.price,
                        'reason': decision.reason
                    }
                    self.logger.log_trade(trade_data)
                    
        except Exception as e:
            self.logger.logger.error(f"Failed to execute trade: {e}")
    
    def run(self):
        """Main trading loop"""
        self.logger.logger.info("Starting trading bot...")
        
        iteration = 0
        while self.running:
            try:
                iteration += 1
                self.logger.logger.info(f"Starting iteration {iteration}...")
                
                # 1. Get market data
                market_data = self.roostoo.get_market_data(self.config.TRADE_PAIR)
                if 'error' in market_data:
                    self.logger.logger.error(f"Failed to get market data: {market_data['error']}")
                    time.sleep(30)
                    continue
                
                # Log market data
                self.logger.log_market_data(market_data)
                
                # 2. Get K-line data
                klines = self.roostoo.get_klines(
                    symbol=self.config.TRADE_PAIR,
                    interval='1m',
                    limit=100
                )
                
                if 'error' in klines or not klines:
                    self.logger.logger.error("Failed to get K-line data")
                    time.sleep(30)
                    continue
                
                # 3. Get current price
                current_price = float(market_data.get('lastPrice', 0))
                if current_price == 0:
                    self.logger.logger.error("Failed to get price")
                    time.sleep(30)
                    continue
                
                # 4. Strategy analysis
                decision = self.strategy.analyze(klines, current_price)
                
                # Log strategy signal
                signal_data = {
                    'action': decision.action.value,
                    'confidence': decision.confidence,
                    'price': current_price,
                    'reason': decision.reason
                }
                self.logger.log_strategy_signal(signal_data)
                
                self.logger.logger.info(
                    f"Strategy decision: {decision.action.value}, "
                    f"Confidence: {decision.confidence:.2f}, "
                    f"Price: {current_price:.2f}, "
                    f"Reason: {decision.reason}"
                )
                
                # 5. Get account balance
                balance_data = self.roostoo.get_account_balance()
                if 'error' in balance_data:
                    self.logger.logger.error("Failed to get account balance")
                    time.sleep(30)
                    continue
                
                # 6. Log portfolio status
                portfolio_value = self.get_portfolio_value(balance_data, {self.config.TRADE_PAIR.split('/')[0]: current_price})
                portfolio_data = {
                    'total_value': portfolio_value,
                    'cash_value': balance_data.get('USD', {}).get('free', 0),
                    'btc_balance': balance_data.get('BTC', {}).get('free', 0),
                    'btc_value': balance_data.get('BTC', {}).get('free', 0) * current_price,
                    'current_price': current_price
                }
                self.logger.log_portfolio_update(portfolio_data)
                
                # 7. Execute trading decision
                if decision.action != Action.HOLD:
                    self.execute_trade(decision, balance_data)
                
                # 8. Wait for next iteration
                self.logger.logger.info(f"Waiting {self.config.TRADE_INTERVAL} seconds...")
                time.sleep(self.config.TRADE_INTERVAL)
                
            except KeyboardInterrupt:
                self.logger.logger.info("User interrupted, stopping bot...")
                self.running = False
                
            except Exception as e:
                self.logger.logger.error(f"Main loop error: {e}")
                time.sleep(60)  # Wait longer on error

if __name__ == "__main__":
    # Enable dashboard for local testing; disable for AWS deployment
    bot = TradingBot(enable_dashboard=True)
    bot.run()