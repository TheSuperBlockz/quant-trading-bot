#!/usr/bin/env python3
"""
Paper Trading Mode - Simulated Balance Tracking

This script runs the trading bot with simulated balance tracking.
Use this for testing before the competition starts.

When the competition begins, use main.py instead (which uses real API balances).

Usage:
    python paper_trading.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import time
import threading
from datetime import datetime
from typing import Dict
from src.trading_logger import TradingLogger
from src.roostoo_client import RoostooClient
from src.horus_client import HorusClient
from src.strategy import MACEStrategy, Action
from config.config import Config


class PaperTradingBot:
    """Trading bot with simulated balance tracking"""
    
    def __init__(self, initial_usd=10000.0, initial_btc=0.0, enable_dashboard=False):
        # Initialize components
        self.config = Config()
        self.logger = TradingLogger()
        self.roostoo = RoostooClient()
        self.horus = HorusClient()
        self.strategy = MACEStrategy(
            fast_period=self.config.FAST_EMA_PERIOD,
            slow_period=self.config.SLOW_EMA_PERIOD,
            signal_period=self.config.SIGNAL_PERIOD
        )
        
        # Simulated balance (paper trading)
        self.paper_balance = {
            'USD': {'free': initial_usd, 'locked': 0.0},
            'BTC': {'free': initial_btc, 'locked': 0.0}
        }
        
        self.running = True
        self.enable_dashboard = enable_dashboard
        self.dashboard_thread = None
        
        self.logger.logger.info(f"PAPER TRADING MODE - Starting with ${initial_usd:.2f} USD, {initial_btc:.8f} BTC")
        
        if enable_dashboard:
            self.start_dashboard()
    
    def start_dashboard(self):
        """Start dashboard"""
        try:
            from src.dashboard import start_dashboard
            self.dashboard_thread = threading.Thread(target=start_dashboard, daemon=True)
            self.dashboard_thread.start()
            self.logger.logger.info("Dashboard started: http://localhost:8050")
        except Exception as e:
            self.logger.logger.error(f"Failed to start dashboard: {e}")
    
    def get_portfolio_value(self, current_prices: Dict) -> float:
        """Calculate total portfolio value from paper balance"""
        cash = self.paper_balance['USD']['free']
        btc_amount = self.paper_balance['BTC']['free']
        btc_price = current_prices.get('BTC', 0)
        btc_value = btc_amount * btc_price
        return cash + btc_value
    
    def execute_paper_trade(self, decision, current_price):
        """Execute simulated trade and update paper balance"""
        try:
            symbol = self.config.TRADE_PAIR
            base_currency = symbol.split('/')[0]  # BTC
            quote_currency = symbol.split('/')[1]  # USD
            
            # Commission rate (0.1% as shown in API response)
            commission_rate = 0.001
            
            if decision.action == Action.BUY:
                # Calculate buy quantity
                available_cash = self.paper_balance[quote_currency]['free']
                max_trade_value = available_cash * self.config.MAX_POSITION_SIZE
                quantity = max_trade_value / current_price
                total_cost = quantity * current_price
                commission = total_cost * commission_rate
                
                self.logger.logger.info(
                    f"BUY calculation - Available: ${available_cash:.2f}, "
                    f"Max trade (10%): ${max_trade_value:.2f}, "
                    f"Total cost: ${total_cost:.2f}"
                )
                
                if total_cost < 10:  # Minimum trade amount check
                    self.logger.logger.info("Trade amount too small, skipping")
                    return
                
                # Simulate order execution
                self.logger.logger.info(f"Simulating BUY order: {quantity:.8f} {base_currency} @ ${current_price:.2f}")
                
                # Update paper balance
                self.paper_balance[quote_currency]['free'] -= (total_cost + commission)
                self.paper_balance[base_currency]['free'] += quantity
                
                # Update strategy position tracking
                self.strategy.open_position(current_price, quantity)
                
                self.logger.logger.info(
                    f"Paper BUY executed - Cost: ${total_cost:.2f}, "
                    f"Commission: ${commission:.2f}, "
                    f"Received: {quantity:.8f} {base_currency}"
                )
                
                # Log trade
                trade_data = {
                    'action': 'BUY',
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': current_price,
                    'total': total_cost,
                    'commission': commission,
                    'reason': decision.reason
                }
                self.logger.log_trade(trade_data)
                
            elif decision.action == Action.SELL:
                # Use quantity from decision if provided (for exit signals), otherwise calculate
                if decision.quantity > 0:
                    quantity = decision.quantity
                else:
                    available_coin = self.paper_balance[base_currency]['free']
                    quantity = available_coin * self.config.MAX_POSITION_SIZE
                
                total_value = quantity * current_price
                commission = total_value * commission_rate
                
                self.logger.logger.info(
                    f"SELL calculation - Quantity: {quantity:.8f} BTC, "
                    f"Total value: ${total_value:.2f}"
                )
                
                if total_value < 10:  # Minimum trade amount check
                    self.logger.logger.info("Trade amount too small, skipping")
                    return
                
                # Simulate order execution
                self.logger.logger.info(f"Simulating SELL order: {quantity:.8f} {base_currency} @ ${current_price:.2f}")
                
                # Update paper balance
                self.paper_balance[base_currency]['free'] -= quantity
                self.paper_balance[quote_currency]['free'] += (total_value - commission)
                
                self.logger.logger.info(
                    f"Paper SELL executed - Revenue: ${total_value:.2f}, "
                    f"Commission: ${commission:.2f}, "
                    f"Net: ${total_value - commission:.2f}"
                )
                
                # Log trade
                trade_data = {
                    'action': 'SELL',
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': current_price,
                    'total': total_value,
                    'commission': commission,
                    'reason': decision.reason
                }
                self.logger.log_trade(trade_data)
                
        except Exception as e:
            self.logger.logger.error(f"Failed to execute paper trade: {e}")
    
    def run(self):
        """Main paper trading loop"""
        self.logger.logger.info("Starting paper trading bot...")
        
        iteration = 0
        while self.running:
            try:
                iteration += 1
                self.logger.logger.info(f"Starting iteration {iteration}...")
                
                # 1. Get market data from Roostoo
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
                base_currency = self.config.TRADE_PAIR.split('/')[0]
                end_time = int(time.time())
                start_time = end_time - (15 * 60 * 100)
                
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
                
                # 5. Log paper balance and portfolio status
                current_prices = {base_currency: current_price}
                portfolio_value = self.get_portfolio_value(current_prices)
                
                self.logger.logger.info(
                    f"Paper Balance - "
                    f"USD: ${self.paper_balance['USD']['free']:.2f}, "
                    f"BTC: {self.paper_balance['BTC']['free']:.8f}, "
                    f"Total Value: ${portfolio_value:.2f}"
                )
                
                portfolio_data = {
                    'total_value': portfolio_value,
                    'cash_value': self.paper_balance['USD']['free'],
                    'btc_balance': self.paper_balance['BTC']['free'],
                    'btc_value': self.paper_balance['BTC']['free'] * current_price,
                    'current_price': current_price
                }
                self.logger.log_portfolio_update(portfolio_data)
                
                # 6. Execute paper trading decision
                if decision.action != Action.HOLD:
                    self.execute_paper_trade(decision, current_price)
                
                # 7. Wait for next iteration
                self.logger.logger.info(f"Waiting {self.config.TRADE_INTERVAL} seconds...")
                time.sleep(self.config.TRADE_INTERVAL)
                
            except KeyboardInterrupt:
                self.logger.logger.info("User interrupted, stopping bot...")
                self.running = False
                
            except Exception as e:
                self.logger.logger.error(f"Main loop error: {e}")
                time.sleep(60)
        
        # Print final summary
        self.print_summary()
    
    def print_summary(self):
        """Print final paper trading summary"""
        print("\n" + "="*80)
        print("PAPER TRADING SUMMARY")
        print("="*80)
        print(f"Final Balance:")
        print(f"  USD: ${self.paper_balance['USD']['free']:.2f}")
        print(f"  BTC: {self.paper_balance['BTC']['free']:.8f}")
        print("="*80 + "\n")


if __name__ == "__main__":
    print("="*80)
    print("PAPER TRADING MODE")
    print("="*80)
    print("\nThis mode simulates trading with a virtual balance.")
    print("Perfect for testing before the competition starts!")
    print("\nStarting balance: $5,000,000 USD + 50 BTC (~$10M total)")
    print("When competition starts, use main.py instead.")
    print("="*80 + "\n")
    
    # Start paper trading bot with $5M USD + 50 BTC initial balance
    bot = PaperTradingBot(
        initial_usd=5000000.0,
        initial_btc=50.0,  # Start with 50 BTC (~$5M worth)
        enable_dashboard=True
    )
    bot.run()
