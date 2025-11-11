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
        
        # Initialize strategy with crypto optimizations
        crypto_params = self.config.get_crypto_optimized_params()
        self.strategy = MACEStrategy(
            fast_period=self.config.FAST_EMA_PERIOD,
            slow_period=self.config.SLOW_EMA_PERIOD,
            signal_period=self.config.SIGNAL_PERIOD,
            volatility_lookback=crypto_params['volatility_lookback'],
            high_vol_multiplier=crypto_params['high_vol_multiplier']
        )
        self.running = True
        self.enable_dashboard = enable_dashboard
        self.dashboard_thread = None
        
        # Trading constants
        self.MIN_BTC_AMOUNT = 0.00001  # Minimum BTC amount (5 decimal places per API spec)
        self.MIN_TRADE_VALUE = 1.0  # Minimum trade value in USD (MiniOrder = 1)
        
        # Performance tracking
        self.daily_trade_count = 0
        self.last_trade_date = None
        self.consecutive_losses = 0
        self.peak_portfolio_value = 50000.0  # Starting balance
        
        # RECOVERY: Sync strategy state with actual positions from logs
        self._recover_position_state()
        
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
    
    def _recover_position_state(self):
        """
        Recover strategy position state from actual balance and trade logs.
        This prevents duplicate trades when bot restarts with existing positions.
        """
        try:
            self.logger.logger.info("=" * 60)
            self.logger.logger.info("CHECKING FOR EXISTING POSITIONS TO RECOVER")
            self.logger.logger.info("=" * 60)
            
            # Get actual balance from Roostoo
            balance = self.roostoo.get_account_balance()
            if 'error' in balance:
                self.logger.logger.warning(f"Could not fetch balance for recovery: {balance.get('error')}")
                return
            
            btc_holdings = balance.get('BTC', {}).get('free', 0)
            usd_balance = balance.get('USD', {}).get('free', 0)
            
            self.logger.logger.info(f"Current Balance - BTC: {btc_holdings:.8f}, USD: ${usd_balance:.2f}")
            
            # Check if we have significant BTC holdings (more than dust)
            if btc_holdings < 0.0001:
                self.logger.logger.info("No significant BTC position detected - starting fresh")
                self.logger.logger.info("=" * 60)
                return
            
            self.logger.logger.warning(f"⚠️  EXISTING BTC POSITION DETECTED: {btc_holdings:.8f} BTC")
            
            # Try to load trade history from logs
            import json
            trade_log_path = self.logger.logs_dir / 'trade_history.json'
            
            if not trade_log_path.exists():
                self.logger.logger.error(
                    "❌ BTC position exists but no trade_history.json found! "
                    "Cannot recover position state. Bot may attempt to buy again!"
                )
                self.logger.logger.error("RECOMMENDATION: Manually sell BTC or provide trade logs")
                self.logger.logger.info("=" * 60)
                return
            
            # Load trade history
            with open(trade_log_path, 'r') as f:
                trades = json.load(f)
            
            if not trades:
                self.logger.logger.error("❌ Trade history is empty! Cannot recover position.")
                self.logger.logger.info("=" * 60)
                return
            
            self.logger.logger.info(f"Found {len(trades)} trades in history")
            
            # Find all BUY trades to calculate average entry and total quantity
            buy_trades = [t for t in trades if t.get('action') == 'BUY']
            sell_trades = [t for t in trades if t.get('action') == 'SELL']
            
            if not buy_trades:
                self.logger.logger.error("❌ No BUY trades found in history!")
                self.logger.logger.info("=" * 60)
                return
            
            # Calculate total bought and sold
            total_bought_qty = sum(t.get('quantity', 0) for t in buy_trades)
            total_bought_value = sum(t.get('total', 0) for t in buy_trades)
            total_sold_qty = sum(t.get('quantity', 0) for t in sell_trades)
            
            # Net position should match actual balance
            net_position_qty = total_bought_qty - total_sold_qty
            
            self.logger.logger.info(f"Trade Summary:")
            self.logger.logger.info(f"  Total BUY: {total_bought_qty:.8f} BTC for ${total_bought_value:.2f}")
            self.logger.logger.info(f"  Total SELL: {total_sold_qty:.8f} BTC")
            self.logger.logger.info(f"  Net Position: {net_position_qty:.8f} BTC")
            self.logger.logger.info(f"  Actual Balance: {btc_holdings:.8f} BTC")
            
            # Calculate weighted average entry price
            if total_bought_qty > 0:
                avg_entry_price = total_bought_value / total_bought_qty
            else:
                avg_entry_price = buy_trades[-1].get('price', 0)
            
            # Use the last BUY trade for reference
            last_buy = buy_trades[-1]
            last_trade = trades[-1]  # Last trade of any type
            
            self.logger.logger.info(f"Recovery Details:")
            self.logger.logger.info(f"  Average Entry Price: ${avg_entry_price:.2f}")
            self.logger.logger.info(f"  Last BUY Price: ${last_buy.get('price', 0):.2f}")
            self.logger.logger.info(f"  Last BUY Time: {last_buy.get('timestamp', 'unknown')}")
            
            # Restore position in strategy using actual holdings and average entry
            self.strategy.open_position(avg_entry_price, btc_holdings)
            self.logger.logger.warning(
                f"✅ POSITION RESTORED - Entry: ${avg_entry_price:.2f}, "
                f"Qty: {btc_holdings:.8f} BTC, "
                f"Value: ${avg_entry_price * btc_holdings:.2f}"
            )
            self.logger.logger.info(
                f"   Stop Loss: ${self.strategy.position.stop_loss:.2f}, "
                f"Take Profit: ${self.strategy.position.take_profit:.2f}"
            )
            
            # Restore cooldown state from last trade (regardless of BUY/SELL)
            try:
                from datetime import datetime
                last_trade_time = datetime.fromisoformat(last_trade.get('timestamp'))
                last_trade_action = Action.BUY if last_trade.get('action') == 'BUY' else Action.SELL
                
                self.strategy.last_trade_time = last_trade_time
                self.strategy.last_trade_action = last_trade_action
                
                time_since_last_trade = (datetime.now() - last_trade_time).total_seconds()
                self.logger.logger.info(
                    f"✅ COOLDOWN RESTORED - Last {last_trade_action.value} was "
                    f"{time_since_last_trade:.0f}s ago ({time_since_last_trade/60:.1f} min)"
                )
                
                if time_since_last_trade < self.strategy.min_trade_interval_seconds:
                    remaining = self.strategy.min_trade_interval_seconds - time_since_last_trade
                    self.logger.logger.warning(
                        f"⏰ Cooldown active: {remaining:.0f}s remaining ({remaining/60:.1f} min)"
                    )
                else:
                    self.logger.logger.info("✅ Cooldown expired - ready to trade")
                    
            except Exception as e:
                self.logger.logger.error(f"Failed to restore cooldown state: {e}")
            
            self.logger.logger.info("=" * 60)
            self.logger.logger.info("✅ STRATEGY STATE RECOVERY COMPLETE")
            self.logger.logger.info("=" * 60)
            
        except Exception as e:
            self.logger.logger.error(f"❌ Failed to recover position state: {e}")
            self.logger.logger.error("Bot will start with clean state - may attempt duplicate trades!")
            self.logger.logger.info("=" * 60)
            import traceback
            traceback.print_exc()
    
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
    
    def crypto_risk_checks(self, current_price: float, balance_data: Dict) -> bool:
        """
        Crypto-specific risk management checks.
        Returns True if trade is allowed, False otherwise.
        """
        try:
            # 1. Daily trade limit
            from datetime import date
            today = date.today()
            
            if self.last_trade_date != today:
                self.daily_trade_count = 0
                self.last_trade_date = today
            
            if self.daily_trade_count >= self.config.DAILY_TRADE_LIMIT:
                self.logger.logger.warning(
                    f"⚠️ Daily trade limit reached ({self.config.DAILY_TRADE_LIMIT}), skipping trade"
                )
                return False
            
            # 2. Portfolio concentration (avoid over-exposure to single asset)
            btc_balance = balance_data.get('BTC', {}).get('free', 0)
            current_prices = {'BTC': current_price}
            total_value = self.get_portfolio_value(balance_data, current_prices)
            
            if total_value > 0:
                btc_value = btc_balance * current_price
                btc_percentage = (btc_value / total_value) * 100
                
                if btc_percentage > 85:  # Max 85% in BTC
                    self.logger.logger.warning(
                        f"⚠️ Portfolio too concentrated in BTC ({btc_percentage:.1f}%), skipping BUY"
                    )
                    return False
            
            return True
            
        except Exception as e:
            self.logger.logger.error(f"Error in crypto_risk_checks: {e}")
            return False  # Fail-safe: don't trade if risk check fails
    
    def monitor_performance(self, current_portfolio_value: float):
        """
        Monitor performance metrics for alerts.
        """
        try:
            # Update peak value
            if current_portfolio_value > self.peak_portfolio_value:
                self.peak_portfolio_value = current_portfolio_value
            
            # Calculate drawdown
            if self.peak_portfolio_value > 0:
                drawdown = (self.peak_portfolio_value - current_portfolio_value) / self.peak_portfolio_value
                
                if drawdown >= self.config.DRAWDOWN_ALERT:
                    self.logger.logger.warning(
                        f"⚠️ DRAWDOWN ALERT: {drawdown*100:.1f}% from peak "
                        f"(Peak: ${self.peak_portfolio_value:.2f}, Current: ${current_portfolio_value:.2f})"
                    )
            
            # Alert on consecutive losses
            if self.consecutive_losses >= self.config.CONSECUTIVE_LOSS_ALERT:
                self.logger.logger.warning(
                    f"⚠️ CONSECUTIVE LOSSES: {self.consecutive_losses} trades in a row"
                )
                
        except Exception as e:
            self.logger.logger.error(f"Error in monitor_performance: {e}")
    
    def execute_trade(self, decision, balance_data: Dict):
        """Execute trade with crypto risk checks"""
        try:
            symbol = self.config.TRADE_PAIR
            base_currency = symbol.split('/')[0]  # BTC
            quote_currency = symbol.split('/')[1]  # USD
            
            if decision.action == Action.BUY:
                # Perform crypto-specific risk checks for BUY orders
                if not self.crypto_risk_checks(decision.price, balance_data):
                    return
                
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
                    
                    # Update strategy position tracking and record trade
                    self.strategy.open_position(decision.price, quantity)
                    self.strategy.record_trade(Action.BUY)
                    self.logger.logger.info(f"BUY trade recorded in strategy - Position opened")
                    
                    # Update performance tracking
                    self.daily_trade_count += 1
                    
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
                    
                    # Strategy already handles close_position() and record_trade() internally for SELL
                    self.logger.logger.info(f"SELL trade logged - Strategy position should be closed")
                    
                    # Update performance tracking
                    self.daily_trade_count += 1
                    
                    # Track consecutive losses (if exit reason was stop loss)
                    if 'stop loss' in decision.reason.lower():
                        self.consecutive_losses += 1
                    else:
                        self.consecutive_losses = 0  # Reset on profitable exit
                    
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
                # Track position and record trade in strategy
                self.strategy.open_position(current_price, quantity)
                self.strategy.record_trade(Action.BUY)
                
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
                
                # Monitor performance for alerts
                self.monitor_performance(portfolio_value)
                
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