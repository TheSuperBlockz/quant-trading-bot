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
from horus_client import HorusClient
from strategy import MACEStrategy, Action
from config.config import Config

class TradingBot:
    def __init__(self, enable_dashboard=False):
        self.config = Config()
        self.logger = TradingLogger()
        self.roostoo = RoostooClient()
        self.horus = HorusClient()
        self.strategy = MACEStrategy(
            fast_period=self.config.FAST_EMA_PERIOD,
            slow_period=self.config.SLOW_EMA_PERIOD,
            signal_period=self.config.SIGNAL_PERIOD
        )
        self.running = True
        self.enable_dashboard = enable_dashboard
        self.dashboard_thread = None
        
        # Trading constants
        self.MIN_BTC_AMOUNT = 0.00001  # Minimum BTC amount (5 decimal places per API spec)
        self.MIN_TRADE_VALUE = 1.0  # Minimum trade value in USD (MiniOrder = 1)
        
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
            # Validate input types
            if not isinstance(balance_data, dict):
                raise ValueError(f"Balance data must be a dictionary, got {type(balance_data)}")
            if not isinstance(current_prices, dict):
                raise ValueError(f"Current prices must be a dictionary, got {type(current_prices)}")
            
            # Safely get USD balance
            usd_balance = balance_data.get('USD', {})
            if not isinstance(usd_balance, dict):
                raise ValueError(f"USD balance must be a dictionary, got {type(usd_balance)}")
            
            cash = float(usd_balance.get('free', 0))
            total_value = cash
            
            # Calculate holdings value
            for coin, balance in balance_data.items():
                if coin == 'USD' or not isinstance(balance, dict):
                    continue
                    
                try:
                    free_amount = float(balance.get('free', 0))
                    coin_price = float(current_prices.get(coin, 0))
                    coin_value = free_amount * coin_price
                    total_value += coin_value
                except (TypeError, ValueError) as e:
                    self.logger.logger.error(f"Error calculating value for {coin}: {e}")
                    continue
            
            return total_value
        except Exception as e:
            self.logger.logger.error(f"Failed to calculate portfolio value: {e}")
            # Re-raise the exception to be handled by the main loop
            raise
    
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
                
                if quantity * decision.price < self.MIN_TRADE_VALUE:  # Minimum trade amount check
                    self.logger.logger.info(f"Trade amount too small (${quantity * decision.price:.2f} < ${self.MIN_TRADE_VALUE}), skipping")
                    return
                
                # Ensure quantity meets minimum precision (5 decimal places for BTC)
                quantity = round(quantity, 5)
                
                # Execute buy
                base_currency = symbol.split('/')[0]  # Get the coin symbol (e.g., BTC)
                result = self.roostoo.place_order(
                    coin=base_currency,
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
                # Use quantity from decision if provided (for exit signals), otherwise calculate
                if decision.quantity > 0:
                    quantity = decision.quantity
                else:
                    available_coin = balance_data.get(base_currency, {}).get('free', 0)
                    quantity = available_coin * self.config.MAX_POSITION_SIZE
                
                if quantity * decision.price < self.MIN_TRADE_VALUE:  # Minimum trade amount check
                    self.logger.logger.info(f"Trade amount too small (${quantity * decision.price:.2f} < ${self.MIN_TRADE_VALUE}), skipping")
                    return
                
                # Ensure quantity meets minimum precision (5 decimal places for BTC)
                quantity = round(quantity, 5)
                
                # Execute sell
                base_currency = symbol.split('/')[0]  # Get the coin symbol (e.g., BTC)
                result = self.roostoo.place_order(
                    coin=base_currency,
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
    
    def execute_initial_trade(self, current_price: float, balance_data: Dict):
        """Execute initial $1.14 BUY trade to satisfy competition requirement"""
        try:
            symbol = self.config.TRADE_PAIR
            base_currency = symbol.split('/')[0]  # BTC
            quote_currency = symbol.split('/')[1]  # USD
            
            # Calculate quantity for $1.14 trade (meme amount)
            trade_value = 1.14  # $1.14 USD
            quantity = trade_value / current_price
            quantity = round(quantity, 5)  # Round to 5 decimal places
            
            # Verify we have enough balance
            available_cash = balance_data.get(quote_currency, {}).get('free', 0)
            required_cash = quantity * current_price
            
            if available_cash < required_cash:
                self.logger.logger.error(
                    f"Insufficient balance for initial trade: need ${required_cash:.2f}, have ${available_cash:.2f}"
                )
                return False
            
            self.logger.logger.info(
                f"INITIAL TRADE: Executing $1.14 BUY to satisfy competition requirement"
            )
            self.logger.logger.info(
                f"Buying {quantity:.5f} BTC @ ${current_price:.2f} (${required_cash:.2f} total)"
            )
            
            # Execute buy order
            result = self.roostoo.place_order(
                coin=base_currency,
                side='BUY',
                quantity=quantity
            )
            
            if 'error' not in result:
                self.strategy.open_position(current_price, quantity)  # Track in strategy
                
                trade_data = {
                    'action': 'BUY',
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': current_price,
                    'total': quantity * current_price,
                    'reason': 'INITIAL TRADE: Competition requirement ($1.14 BTC purchase)'
                }
                self.logger.log_trade(trade_data)
                self.logger.logger.info("Initial trade executed successfully!")
                return True
            else:
                self.logger.logger.error(f"Initial trade failed: {result.get('error')}")
                return False
                
        except Exception as e:
            self.logger.logger.error(f"Failed to execute initial trade: {e}")
            return False
    
    def run(self):
        """Main trading loop"""
        self.logger.logger.info("Starting trading bot...")
        
        # Flag to track if initial trade has been executed
        initial_trade_executed = False
        
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
                
                # 2. Get current price from Roostoo (real-time)
                current_price = None
                try:
                    # Try to get price from market_data response
                    if 'Data' in market_data and self.config.TRADE_PAIR in market_data['Data']:
                        current_price = float(market_data['Data'][self.config.TRADE_PAIR].get('LastPrice', 0))
                    elif 'lastPrice' in market_data:
                        current_price = float(market_data['lastPrice'])
                    elif 'price' in market_data:
                        current_price = float(market_data['price'])
                    
                    if not current_price or current_price == 0:
                        self.logger.logger.error("Failed to extract current price from market data")
                        time.sleep(30)
                        continue
                        
                    self.logger.logger.info(f"Current price from Roostoo: {current_price}")
                except Exception as e:
                    self.logger.logger.error(f"Error getting current price: {e}")
                    time.sleep(30)
                    continue
                
                # 3. Get historical price data from Horus (for MACD calculation)
                base_currency = self.config.TRADE_PAIR.split('/')[0]  # Extract BTC from BTC/USD
                end_time = int(time.time())
                start_time = end_time - (15 * 60 * 100)  # Get last 100 15-minute candles
                
                klines = self.horus.get_price_history(
                    symbol=base_currency,
                    interval='15m',
                    start=start_time,
                    end=end_time
                )
                
                if 'error' in klines or not klines:
                    self.logger.logger.error("Failed to get historical price data from Horus")
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
                # Log the actual response for debugging
                self.logger.logger.debug(f"Raw balance data response: {balance_data}")
                
                if 'error' in balance_data or not isinstance(balance_data, dict):
                    self.logger.logger.error(f"Invalid balance data received: {balance_data}")
                    time.sleep(30)
                    continue
                
                # Validate balance data structure before proceeding
                required_fields = ['USD', 'BTC']
                if not all(field in balance_data for field in required_fields):
                    self.logger.logger.error(f"Balance data missing required fields. Fields present: {balance_data.keys()}")
                    time.sleep(30)
                    continue
                
                # 6. Log portfolio status
                current_prices = {
                    self.config.TRADE_PAIR.split('/')[0]: current_price  # e.g., "BTC": 102480.38
                }
                portfolio_value = self.get_portfolio_value(balance_data, current_prices)
                portfolio_data = {
                    'total_value': portfolio_value,
                    'cash_value': balance_data.get('USD', {}).get('free', 0),
                    'btc_balance': balance_data.get('BTC', {}).get('free', 0),
                    'btc_value': balance_data.get('BTC', {}).get('free', 0) * current_price,
                    'current_price': current_price
                }
                self.logger.log_portfolio_update(portfolio_data)
                
                # 6. Execute initial $1.14 trade (only once on first iteration)
                if not initial_trade_executed:
                    self.logger.logger.info("=" * 60)
                    self.logger.logger.info("EXECUTING INITIAL TRADE (Competition Requirement)")
                    self.logger.logger.info("=" * 60)
                    initial_trade_executed = self.execute_initial_trade(current_price, balance_data)
                    if initial_trade_executed:
                        # Wait a bit to let the trade settle
                        time.sleep(5)
                    self.logger.logger.info("=" * 60)
                
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
    # Production deployment - dashboard disabled for AWS
    bot = TradingBot(enable_dashboard=False)
    bot.run()