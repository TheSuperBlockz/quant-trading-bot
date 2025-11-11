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
        
        # Create a strategy instance for each trading pair
        self.strategies = {}
        for pair in self.config.SUPPORTED_PAIRS:
            self.strategies[pair] = MACEStrategy(
                fast_period=self.config.FAST_EMA_PERIOD,
                slow_period=self.config.SLOW_EMA_PERIOD,
                signal_period=self.config.SIGNAL_PERIOD,
                volatility_lookback=self.config.VOLATILITY_LOOKBACK,
                high_vol_multiplier=self.config.HIGH_VOL_MULTIPLIER
            )
        
        self.running = True
        self.enable_dashboard = enable_dashboard
        self.dashboard_thread = None
        
        # Trading constants
        self.MIN_BTC_AMOUNT = 0.00001  # Minimum BTC amount (5 decimal places per API spec)
        self.MIN_TRADE_VALUE = 1.0  # Minimum trade value in USD (MiniOrder = 1)
        
        # Performance tracking (shared across all pairs)
        self.daily_trade_count = 0
        self.last_trade_date = None
        self.consecutive_losses = 0
        self.peak_portfolio_value = 50000.0  # Starting balance
        
        # Track which pairs have executed initial trades
        self.initial_trades_executed = {pair: False for pair in self.config.SUPPORTED_PAIRS}
        
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
        Now supports multiple trading pairs (BTC/USD, ETH/USD).
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
            
            # Check each supported pair for existing positions
            for pair in self.config.SUPPORTED_PAIRS:
                base_currency = pair.split('/')[0]  # BTC or ETH
                quote_currency = pair.split('/')[1]  # USD
                
                base_holdings = balance.get(base_currency, {}).get('free', 0)
                
                self.logger.logger.info(f"[{pair}] Current Balance: {base_holdings:.8f} {base_currency}")
                
                # Check if we have significant holdings (more than dust)
                if base_holdings < 0.0001:
                    self.logger.logger.info(f"[{pair}] No significant position detected - starting fresh")
                    continue
                
                self.logger.logger.warning(f"[{pair}] [WARNING] EXISTING POSITION DETECTED: {base_holdings:.8f} {base_currency}")
                
                # Try to load trade history from logs
                import json
                trade_log_path = self.logger.logs_dir / 'trade_history.json'
                
                if not trade_log_path.exists():
                    self.logger.logger.error(
                        f"[{pair}] [ERROR] Position exists but no trade_history.json found! "
                        "Cannot recover position state. Bot may attempt to buy again!"
                    )
                    continue
                
                # Load trade history
                with open(trade_log_path, 'r') as f:
                    trades = json.load(f)
                
                if not trades:
                    self.logger.logger.error(f"[{pair}] [ERROR] Trade history is empty! Cannot recover position.")
                    continue
                
                # Filter trades for this specific pair
                pair_trades = [t for t in trades if t.get('symbol') == pair]
                
                if not pair_trades:
                    self.logger.logger.warning(f"[{pair}] No trade history found for this pair")
                    continue
                
                self.logger.logger.info(f"[{pair}] Found {len(pair_trades)} trades in history")
                
                # Find all BUY trades to calculate average entry and total quantity
                buy_trades = [t for t in pair_trades if t.get('action') == 'BUY']
                sell_trades = [t for t in pair_trades if t.get('action') == 'SELL']
                
                if not buy_trades:
                    self.logger.logger.error(f"[{pair}] [ERROR] No BUY trades found in history!")
                    continue
                
                # Calculate total bought and sold
                total_bought_qty = sum(t.get('quantity', 0) for t in buy_trades)
                total_bought_value = sum(t.get('total', 0) for t in buy_trades)
                total_sold_qty = sum(t.get('quantity', 0) for t in sell_trades)
                
                # Net position should match actual balance
                net_position_qty = total_bought_qty - total_sold_qty
                
                self.logger.logger.info(f"[{pair}] Trade Summary:")
                self.logger.logger.info(f"[{pair}]   Total BUY: {total_bought_qty:.8f} {base_currency} for ${total_bought_value:.2f}")
                self.logger.logger.info(f"[{pair}]   Total SELL: {total_sold_qty:.8f} {base_currency}")
                self.logger.logger.info(f"[{pair}]   Net Position: {net_position_qty:.8f} {base_currency}")
                self.logger.logger.info(f"[{pair}]   Actual Balance: {base_holdings:.8f} {base_currency}")
                
                # Calculate weighted average entry price
                if total_bought_qty > 0:
                    avg_entry_price = total_bought_value / total_bought_qty
                else:
                    avg_entry_price = buy_trades[-1].get('price', 0)
                
                # Use the last BUY trade for reference
                last_buy = buy_trades[-1]
                last_trade = pair_trades[-1]  # Last trade of any type for this pair
                
                self.logger.logger.info(f"[{pair}] Recovery Details:")
                self.logger.logger.info(f"[{pair}]   Average Entry Price: ${avg_entry_price:.2f}")
                self.logger.logger.info(f"[{pair}]   Last BUY Price: ${last_buy.get('price', 0):.2f}")
                self.logger.logger.info(f"[{pair}]   Last BUY Time: {last_buy.get('timestamp', 'unknown')}")
                
                # Restore position in strategy using actual holdings and average entry
                self.strategies[pair].open_position(avg_entry_price, base_holdings)
                self.logger.logger.warning(
                    f"[{pair}] [SUCCESS] POSITION RESTORED - Entry: ${avg_entry_price:.2f}, "
                    f"Qty: {base_holdings:.8f} {base_currency}, "
                    f"Value: ${avg_entry_price * base_holdings:.2f}"
                )
                self.logger.logger.info(
                    f"[{pair}]    Stop Loss: ${self.strategies[pair].position.stop_loss:.2f}, "
                    f"Take Profit: ${self.strategies[pair].position.take_profit:.2f}"
                )
                
                # Restore cooldown state from last trade (regardless of BUY/SELL)
                try:
                    from datetime import datetime
                    last_trade_time = datetime.fromisoformat(last_trade.get('timestamp'))
                    last_trade_action = Action.BUY if last_trade.get('action') == 'BUY' else Action.SELL
                    
                    self.strategies[pair].last_trade_time = last_trade_time
                    self.strategies[pair].last_trade_action = last_trade_action
                    
                    time_since_last_trade = (datetime.now() - last_trade_time).total_seconds()
                    self.logger.logger.info(
                        f"[{pair}] [SUCCESS] COOLDOWN RESTORED - Last {last_trade_action.value} was "
                        f"{time_since_last_trade:.0f}s ago ({time_since_last_trade/60:.1f} min)"
                    )
                    
                    if time_since_last_trade < self.strategies[pair].min_trade_interval_seconds:
                        remaining = self.strategies[pair].min_trade_interval_seconds - time_since_last_trade
                        self.logger.logger.warning(
                            f"[{pair}] [COOLDOWN] Cooldown active: {remaining:.0f}s remaining ({remaining/60:.1f} min)"
                        )
                    else:
                        self.logger.logger.info(f"[{pair}] [SUCCESS] Cooldown expired - ready to trade")
                        
                except Exception as e:
                    self.logger.logger.error(f"[{pair}] Failed to restore cooldown state: {e}")
            
            self.logger.logger.info("=" * 60)
            self.logger.logger.info("[SUCCESS] STRATEGY STATE RECOVERY COMPLETE FOR ALL PAIRS")
            self.logger.logger.info("=" * 60)
            
        except Exception as e:
            self.logger.logger.error(f"[ERROR] Failed to recover position state: {e}")
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
    
    def crypto_risk_checks(self, current_price: float, balance_data: Dict, pair: str = None) -> bool:
        """
        Crypto-specific risk management checks.
        Returns True if trade is allowed, False otherwise.
        
        Args:
            current_price: Current price of the asset
            balance_data: Account balance data
            pair: Trading pair (e.g., "BTC/USD" or "ETH/USD")
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
                    f"[WARNING] Daily trade limit reached ({self.config.DAILY_TRADE_LIMIT}), skipping trade"
                )
                return False
            
            # 2. Portfolio concentration (avoid over-exposure to single asset)
            if pair:
                base_currency = pair.split('/')[0]  # BTC or ETH
                coin_balance = balance_data.get(base_currency, {}).get('free', 0)
                
                # Get current prices for all coins
                current_prices = {}
                for supported_pair in self.config.SUPPORTED_PAIRS:
                    coin = supported_pair.split('/')[0]
                    if coin == base_currency:
                        current_prices[coin] = current_price
                    else:
                        # For other coins, try to get price from balance or use 0
                        # This is a simplified approach - in production you'd want real-time prices
                        current_prices[coin] = 0  # Will be updated by main loop
                
                total_value = self.get_portfolio_value(balance_data, current_prices)
                
                if total_value > 0:
                    coin_value = coin_balance * current_price
                    coin_percentage = (coin_value / total_value) * 100
                    
                    if coin_percentage > 85:  # Max 85% in any single asset
                        self.logger.logger.warning(
                            f"[{pair}] [WARNING] Portfolio too concentrated in {base_currency} ({coin_percentage:.1f}%), skipping BUY"
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
                        f"[WARNING] DRAWDOWN ALERT: {drawdown*100:.1f}% from peak "
                        f"(Peak: ${self.peak_portfolio_value:.2f}, Current: ${current_portfolio_value:.2f})"
                    )
            
            # Alert on consecutive losses
            if self.consecutive_losses >= self.config.CONSECUTIVE_LOSS_ALERT:
                self.logger.logger.warning(
                    f"[WARNING] CONSECUTIVE LOSSES: {self.consecutive_losses} trades in a row"
                )
                
        except Exception as e:
            self.logger.logger.error(f"Error in monitor_performance: {e}")
    
    def execute_trade(self, decision, balance_data: Dict, pair: str):
        """Execute trade with crypto risk checks for a specific trading pair"""
        try:
            symbol = pair
            base_currency = symbol.split('/')[0]  # BTC or ETH
            quote_currency = symbol.split('/')[1]  # USD
            
            if decision.action == Action.BUY:
                # Perform crypto-specific risk checks for BUY orders
                if not self.crypto_risk_checks(decision.price, balance_data, pair):
                    return
                
                # Calculate buy quantity
                available_cash = balance_data.get(quote_currency, {}).get('free', 0)
                max_trade_value = available_cash * self.config.MAX_POSITION_SIZE
                quantity = max_trade_value / decision.price
                
                if quantity * decision.price < self.MIN_TRADE_VALUE:  # Minimum trade amount check
                    self.logger.logger.info(f"[{pair}] Trade amount too small (${quantity * decision.price:.2f} < ${self.MIN_TRADE_VALUE}), skipping")
                    return
                
                # Ensure quantity meets minimum precision (5 decimal places)
                quantity = round(quantity, 5)
                
                # Execute buy
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
                    self.strategies[pair].open_position(decision.price, quantity)
                    self.strategies[pair].record_trade(Action.BUY)
                    self.logger.logger.info(f"[{pair}] BUY trade recorded in strategy - Position opened")
                    
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
                    self.logger.logger.info(f"[{pair}] Trade amount too small (${quantity * decision.price:.2f} < ${self.MIN_TRADE_VALUE}), skipping")
                    return
                
                # Ensure quantity meets minimum precision (5 decimal places)
                quantity = round(quantity, 5)
                
                # Execute sell
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
                    self.logger.logger.info(f"[{pair}] SELL trade logged - Strategy position should be closed")
                    
                    # Update performance tracking
                    self.daily_trade_count += 1
                    
                    # Track consecutive losses (if exit reason was stop loss)
                    if 'stop loss' in decision.reason.lower():
                        self.consecutive_losses += 1
                    else:
                        self.consecutive_losses = 0  # Reset on profitable exit
                    
        except Exception as e:
            self.logger.logger.error(f"[{pair}] Failed to execute trade: {e}")
    
    def execute_initial_trade(self, current_price: float, balance_data: Dict, pair: str):
        """Execute initial $1.14 BUY trade to satisfy competition requirement"""
        try:
            symbol = pair
            base_currency = symbol.split('/')[0]  # BTC or ETH
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
                    f"[{pair}] Insufficient balance for initial trade: need ${required_cash:.2f}, have ${available_cash:.2f}"
                )
                return False
            
            self.logger.logger.info(
                f"[{pair}] INITIAL TRADE: Executing $1.14 BUY to satisfy competition requirement"
            )
            self.logger.logger.info(
                f"[{pair}] Buying {quantity:.5f} {base_currency} @ ${current_price:.2f} (${required_cash:.2f} total)"
            )
            
            # Execute buy order
            result = self.roostoo.place_order(
                coin=base_currency,
                side='BUY',
                quantity=quantity
            )
            
            if 'error' not in result:
                # Track position and record trade in strategy
                self.strategies[pair].open_position(current_price, quantity)
                self.strategies[pair].record_trade(Action.BUY)
                
                trade_data = {
                    'action': 'BUY',
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': current_price,
                    'total': quantity * current_price,
                    'reason': f'INITIAL TRADE: Competition requirement ($1.14 {base_currency} purchase)'
                }
                self.logger.log_trade(trade_data)
                self.logger.logger.info(f"[{pair}] Initial trade executed successfully!")
                return True
            else:
                self.logger.logger.error(f"[{pair}] Initial trade failed: {result.get('error')}")
                return False
                
        except Exception as e:
            self.logger.logger.error(f"Failed to execute initial trade: {e}")
            return False
    
    def run(self):
        """Main trading loop - now supports multiple trading pairs"""
        self.logger.logger.info("Starting multi-pair trading bot...")
        self.logger.logger.info(f"Trading pairs: {', '.join(self.config.SUPPORTED_PAIRS)}")
        
        iteration = 0
        while self.running:
            try:
                iteration += 1
                self.logger.logger.info(f"=" * 80)
                self.logger.logger.info(f"Starting iteration {iteration}...")
                self.logger.logger.info(f"=" * 80)
                
                # Get account balance once per iteration (shared across all pairs)
                balance_data = self.roostoo.get_account_balance()
                self.logger.logger.debug(f"Raw balance data response: {balance_data}")
                
                if 'error' in balance_data or not isinstance(balance_data, dict):
                    self.logger.logger.error(f"Invalid balance data received: {balance_data}")
                    time.sleep(30)
                    continue
                
                # Validate balance data has USD (always required)
                if 'USD' not in balance_data:
                    self.logger.logger.error(f"Balance data missing USD. Present: {balance_data.keys()}")
                    time.sleep(30)
                    continue
                
                # Note: BTC/ETH may not be present until first trade - that's OK!
                
                # Process each trading pair sequentially
                current_prices = {}  # Track prices for portfolio calculation
                
                for pair in self.config.SUPPORTED_PAIRS:
                    try:
                        self.logger.logger.info(f"\n--- Processing {pair} ---")
                        
                        # 1. Get market data for this pair
                        market_data = self.roostoo.get_market_data(pair)
                        if 'error' in market_data:
                            self.logger.logger.error(f"[{pair}] Failed to get market data: {market_data['error']}")
                            continue
                        
                        # Log market data
                        self.logger.log_market_data(market_data)
                        
                        # 2. Get current price from Roostoo
                        current_price = None
                        try:
                            if 'Data' in market_data and pair in market_data['Data']:
                                current_price = float(market_data['Data'][pair].get('LastPrice', 0))
                            elif 'lastPrice' in market_data:
                                current_price = float(market_data['lastPrice'])
                            elif 'price' in market_data:
                                current_price = float(market_data['price'])
                            
                            if not current_price or current_price == 0:
                                self.logger.logger.error(f"[{pair}] Failed to extract current price")
                                continue
                                
                            self.logger.logger.info(f"[{pair}] Current price: ${current_price:.2f}")
                            current_prices[pair.split('/')[0]] = current_price  # Store for portfolio calc
                            
                        except Exception as e:
                            self.logger.logger.error(f"[{pair}] Error getting current price: {e}")
                            continue
                        
                        # 3. Get historical price data from Horus
                        base_currency = pair.split('/')[0]  # BTC or ETH
                        end_time = int(time.time())
                        start_time = end_time - (15 * 60 * 100)  # Last 100 15-minute candles
                        
                        klines = self.horus.get_price_history(
                            symbol=base_currency,
                            interval='15m',
                            start=start_time,
                            end=end_time
                        )
                        
                        if 'error' in klines or not klines:
                            self.logger.logger.error(f"[{pair}] Failed to get historical data from Horus")
                            continue
                        
                        # 4. Strategy analysis
                        decision = self.strategies[pair].analyze(klines, current_price)
                        
                        # Log strategy signal
                        signal_data = {
                            'symbol': pair,
                            'action': decision.action.value,
                            'confidence': decision.confidence,
                            'price': current_price,
                            'reason': decision.reason
                        }
                        self.logger.log_strategy_signal(signal_data)
                        
                        self.logger.logger.info(
                            f"[{pair}] Decision: {decision.action.value}, "
                            f"Confidence: {decision.confidence:.2f}, "
                            f"Reason: {decision.reason}"
                        )
                        
                        # 5. Execute initial trade if needed (per pair)
                        if not self.initial_trades_executed[pair]:
                            self.logger.logger.info(f"[{pair}] EXECUTING INITIAL $1.14 TRADE")
                            success = self.execute_initial_trade(current_price, balance_data, pair)
                            if success:
                                self.initial_trades_executed[pair] = True
                                time.sleep(2)  # Brief pause after initial trade
                        
                        # 6. Execute trading decision
                        if decision.action != Action.HOLD:
                            self.execute_trade(decision, balance_data, pair)
                        
                    except Exception as e:
                        self.logger.logger.error(f"[{pair}] Error processing pair: {e}")
                        continue
                
                # 7. Log portfolio status (after processing all pairs)
                portfolio_value = self.get_portfolio_value(balance_data, current_prices)
                
                # Build comprehensive portfolio data
                portfolio_data = {
                    'total_value': portfolio_value,
                    'cash_value': balance_data.get('USD', {}).get('free', 0),
                    'btc_balance': balance_data.get('BTC', {}).get('free', 0),
                    'btc_value': balance_data.get('BTC', {}).get('free', 0) * current_prices.get('BTC', 0),
                    'eth_balance': balance_data.get('ETH', {}).get('free', 0),
                    'eth_value': balance_data.get('ETH', {}).get('free', 0) * current_prices.get('ETH', 0),
                    'btc_price': current_prices.get('BTC', 0),
                    'eth_price': current_prices.get('ETH', 0)
                }
                self.logger.log_portfolio_update(portfolio_data)
                
                # Monitor performance
                self.monitor_performance(portfolio_value)
                
                # 8. Wait for next iteration
                self.logger.logger.info(f"\n{'=' * 80}")
                self.logger.logger.info(f"Iteration {iteration} complete. Waiting {self.config.TRADE_INTERVAL} seconds...")
                self.logger.logger.info(f"{'=' * 80}\n")
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