import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Action(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class PositionState(Enum):
    NONE = "NONE"
    LONG = "LONG"
    # SHORT not implemented as Roostoo may not support short selling

@dataclass
class Position:
    """Track current trading position"""
    state: PositionState = PositionState.NONE
    entry_price: float = 0.0
    entry_time: Optional[datetime] = None
    quantity: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    highest_price: float = 0.0  # For trailing stop
    
@dataclass
class TradingDecision:
    action: Action
    confidence: float
    price: float
    quantity: float = 0
    reason: str = ""

class MACEStrategy:
    """
    Enhanced MACD Strategy with:
    - Position state management to prevent signal clustering
    - Take profit / Stop loss (3% default)
    - Trailing stop loss
    - Time-based exits
    - Cooldown periods between trades
    """
    
    def __init__(self, fast_period=12, slow_period=26, signal_period=9, 
                 stop_loss_pct=0.03, take_profit_pct=0.03, 
                 trailing_stop_pct=0.015, trailing_activation_pct=0.02,
                 max_position_hours=48, min_trade_interval_seconds=3600):
        """
        Initialize enhanced MACD strategy
        
        Args:
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line period (default 9)
            stop_loss_pct: Stop loss percentage (default 3%)
            take_profit_pct: Take profit percentage (default 3%)
            trailing_stop_pct: Trailing stop distance (default 1.5%)
            trailing_activation_pct: Profit level to activate trailing stop (default 2%)
            max_position_hours: Maximum hours to hold position (default 48)
            min_trade_interval_seconds: Minimum seconds between same-direction trades (default 3600 = 1 hour)
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        
        # Risk management parameters
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.trailing_activation_pct = trailing_activation_pct
        self.max_position_hours = max_position_hours
        self.min_trade_interval_seconds = min_trade_interval_seconds
        
        # Position tracking
        self.position = Position()
        
        # Trade history for cooldown
        self.last_trade_time = None
        self.last_trade_action = None
        
        # MACD state
        self.previous_macd = None
        self.previous_signal = None
        
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return [np.nan] * len(prices)
            
        ema = []
        multiplier = 2 / (period + 1)
        
        # First EMA value is Simple Moving Average (SMA)
        sma = sum(prices[:period]) / period
        ema.extend([sma] * (period - 1))
        
        current_ema = sma
        for price in prices[period:]:
            current_ema = (price - current_ema) * multiplier + current_ema
            ema.append(current_ema)
            
        return ema
    
    def calculate_macd(self, prices: List[float]) -> Tuple[List[float], List[float], List[float]]:
        """Calculate MACD indicator"""
        fast_ema = self.calculate_ema(prices, self.fast_period)
        slow_ema = self.calculate_ema(prices, self.slow_period)
        
        # Calculate MACD line
        macd_line = []
        for fast, slow in zip(fast_ema, slow_ema):
            if pd.isna(fast) or pd.isna(slow):
                macd_line.append(np.nan)
            else:
                macd_line.append(fast - slow)
        
        # Calculate signal line
        signal_line = self.calculate_ema([x for x in macd_line if not pd.isna(x)], self.signal_period)
        
        # Align lengths
        nan_padding = [np.nan] * (len(macd_line) - len(signal_line))
        signal_line = nan_padding + signal_line
        
        # Calculate histogram
        histogram = []
        for macd, signal in zip(macd_line, signal_line):
            if pd.isna(macd) or pd.isna(signal):
                histogram.append(np.nan)
            else:
                histogram.append(macd - signal)
                
        return macd_line, signal_line, histogram
    
    def open_position(self, price: float, quantity: float):
        """Open a new long position"""
        self.position = Position(
            state=PositionState.LONG,
            entry_price=price,
            entry_time=datetime.now(),
            quantity=quantity,
            stop_loss=price * (1 - self.stop_loss_pct),
            take_profit=price * (1 + self.take_profit_pct),
            highest_price=price
        )
        logger.info(
            f"Position opened - Entry: ${price:.2f}, "
            f"SL: ${self.position.stop_loss:.2f}, "
            f"TP: ${self.position.take_profit:.2f}, "
            f"Qty: {quantity:.8f}"
        )
    
    def close_position(self, reason: str):
        """Close current position"""
        logger.info(f"Position closed - Reason: {reason}")
        self.position = Position()  # Reset to empty position
    
    def update_trailing_stop(self, current_price: float):
        """Update trailing stop loss if price has increased"""
        if self.position.state != PositionState.LONG:
            return
        
        # Update highest price seen
        if current_price > self.position.highest_price:
            self.position.highest_price = current_price
            
            # Calculate profit percentage from entry
            profit_pct = (current_price - self.position.entry_price) / self.position.entry_price
            
            # Activate trailing stop if profit exceeds threshold
            if profit_pct >= self.trailing_activation_pct:
                new_trailing_stop = self.position.highest_price * (1 - self.trailing_stop_pct)
                
                # Only move stop loss up, never down
                if new_trailing_stop > self.position.stop_loss:
                    old_sl = self.position.stop_loss
                    self.position.stop_loss = new_trailing_stop
                    logger.info(
                        f"Trailing stop updated - New SL: ${new_trailing_stop:.2f} "
                        f"(was ${old_sl:.2f}), Profit: {profit_pct*100:.2f}%"
                    )
    
    def check_exit_conditions(self, current_price: float) -> Optional[TradingDecision]:
        """Check if any exit conditions are met for current position"""
        if self.position.state == PositionState.NONE:
            return None
        
        # Check stop loss
        if current_price <= self.position.stop_loss:
            self.close_position("Stop loss hit")
            return TradingDecision(
                action=Action.SELL,
                confidence=1.0,
                price=current_price,
                quantity=self.position.quantity,
                reason=f"Stop loss hit at ${current_price:.2f} (SL: ${self.position.stop_loss:.2f})"
            )
        
        # Check take profit
        if current_price >= self.position.take_profit:
            self.close_position("Take profit hit")
            return TradingDecision(
                action=Action.SELL,
                confidence=1.0,
                price=current_price,
                quantity=self.position.quantity,
                reason=f"Take profit hit at ${current_price:.2f} (TP: ${self.position.take_profit:.2f})"
            )
        
        # Check time-based exit
        if self.position.entry_time:
            hours_held = (datetime.now() - self.position.entry_time).total_seconds() / 3600
            if hours_held >= self.max_position_hours:
                self.close_position(f"Time stop: held for {hours_held:.1f} hours")
                return TradingDecision(
                    action=Action.SELL,
                    confidence=0.8,
                    price=current_price,
                    quantity=self.position.quantity,
                    reason=f"Time stop: position held for {hours_held:.1f} hours"
                )
        
        return None
    
    def can_trade(self, action: Action) -> bool:
        """Check if we can execute a trade based on cooldown period"""
        if self.last_trade_time is None:
            return True
        
        time_since_last_trade = (datetime.now() - self.last_trade_time).total_seconds()
        
        # Allow immediate reversal trades (BUY after SELL or vice versa)
        if action != self.last_trade_action:
            return True
        
        # Enforce cooldown for same-direction trades
        if time_since_last_trade < self.min_trade_interval_seconds:
            logger.debug(
                f"Trade cooldown active - {time_since_last_trade:.0f}s since last {self.last_trade_action.value}, "
                f"need {self.min_trade_interval_seconds}s"
            )
            return False
        
        return True
    
    def record_trade(self, action: Action):
        """Record trade for cooldown tracking"""
        self.last_trade_time = datetime.now()
        self.last_trade_action = action
    
    def analyze(self, klines_data: List, current_price: float) -> TradingDecision:
        """
        Analyze market and generate trading decision with enhanced risk management

        Parameters:
            klines_data: K-line data from Horus API [{timestamp, price}, ...]
            current_price: Current price from Roostoo

        Returns:
            TradingDecision: Trading decision with action, confidence, and reason
        """
        # First priority: Check exit conditions for existing position
        if self.position.state == PositionState.LONG:
            # Update trailing stop
            self.update_trailing_stop(current_price)
            
            # Check if any exit condition is met
            exit_decision = self.check_exit_conditions(current_price)
            if exit_decision:
                self.record_trade(exit_decision.action)
                return exit_decision
        
        # Validate data sufficiency
        if len(klines_data) < self.slow_period + self.signal_period:
            return TradingDecision(Action.HOLD, 0, current_price, reason="Insufficient data for MACD calculation")
        
        # Extract prices from Horus API data format
        closes = [float(kline['price']) for kline in klines_data]
        
        # Calculate MACD
        macd_line, signal_line, histogram = self.calculate_macd(closes)
        
        # Get latest values
        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        previous_macd = macd_line[-2] if len(macd_line) > 1 else None
        previous_signal = signal_line[-2] if len(signal_line) > 1 else None
        current_histogram = histogram[-1]
        previous_histogram = histogram[-2] if len(histogram) > 1 else None
        
        if (pd.isna(current_macd) or pd.isna(current_signal) or 
            pd.isna(previous_macd) or pd.isna(previous_signal)):
            return TradingDecision(Action.HOLD, 0, current_price, reason="MACD calculation incomplete")
        
        # Debug logging
        logger.info(
            f"MACD Analysis - Current: {current_macd:.4f}, Signal: {current_signal:.4f}, "
            f"Hist: {current_histogram:.4f}, Previous: {previous_macd:.4f}, {previous_signal:.4f}"
        )
        
        # === ENTRY LOGIC ===
        
        # BUY Signal Detection (Golden Cross + Confirmation)
        if (previous_macd < previous_signal and current_macd > current_signal):
            # Strong golden cross detected
            if self.position.state == PositionState.NONE and self.can_trade(Action.BUY):
                decision = TradingDecision(
                    action=Action.BUY,
                    confidence=0.8,
                    price=current_price,
                    reason="MACD golden cross (bullish crossover)"
                )
                logger.info(f"BUY signal generated: {decision.reason}")
                return decision
            else:
                reason = "Already in position" if self.position.state != PositionState.NONE else "Trade cooldown active"
                logger.debug(f"BUY signal ignored: {reason}")
        
        # Additional BUY confirmation: MACD positive and histogram growing
        elif (current_macd > 0 and current_macd > current_signal and 
              current_histogram > 0 and current_histogram > previous_histogram):
            if self.position.state == PositionState.NONE and self.can_trade(Action.BUY):
                # Calculate EMA200 for trend filter (if enough data)
                if len(closes) >= 200:
                    ema200 = self.calculate_ema(closes, 200)[-1]
                    if current_price < ema200:
                        logger.debug(f"BUY signal filtered: price ${current_price:.2f} below EMA200 ${ema200:.2f} (downtrend)")
                        return TradingDecision(Action.HOLD, 0.5, current_price, reason="Waiting for better entry (below long-term trend)")
                
                decision = TradingDecision(
                    action=Action.BUY,
                    confidence=0.65,
                    price=current_price,
                    reason="MACD bullish momentum (positive and rising)"
                )
                logger.info(f"BUY signal generated: {decision.reason}")
                return decision
        
        # SELL Signal Detection (Death Cross)
        elif (previous_macd > previous_signal and current_macd < current_signal):
            # Death cross detected
            if self.position.state == PositionState.LONG:
                # Exit existing position on reversal signal
                self.close_position("MACD death cross (bearish reversal)")
                decision = TradingDecision(
                    action=Action.SELL,
                    confidence=0.8,
                    price=current_price,
                    quantity=self.position.quantity,
                    reason="MACD death cross - closing long position"
                )
                self.record_trade(Action.SELL)
                logger.info(f"SELL signal generated: {decision.reason}")
                return decision
            else:
                logger.debug("SELL signal detected but no position to close")
        
        # Weak SELL signal: MACD negative and histogram declining
        elif (current_macd < 0 and current_macd < current_signal and 
              current_histogram < 0 and current_histogram < previous_histogram):
            if self.position.state == PositionState.LONG:
                # Consider exiting on weakening momentum
                profit_pct = (current_price - self.position.entry_price) / self.position.entry_price
                if profit_pct > 0:  # Only exit if in profit
                    self.close_position("MACD bearish momentum with profit")
                    decision = TradingDecision(
                        action=Action.SELL,
                        confidence=0.6,
                        price=current_price,
                        quantity=self.position.quantity,
                        reason=f"MACD bearish momentum - taking profit ({profit_pct*100:.2f}%)"
                    )
                    self.record_trade(Action.SELL)
                    logger.info(f"SELL signal generated: {decision.reason}")
                    return decision
        
        # Default: HOLD
        if self.position.state == PositionState.LONG:
            profit_pct = (current_price - self.position.entry_price) / self.position.entry_price
            return TradingDecision(
                Action.HOLD, 
                0.5, 
                current_price, 
                reason=f"Holding position, P/L: {profit_pct*100:+.2f}%, SL: ${self.position.stop_loss:.2f}, TP: ${self.position.take_profit:.2f}"
            )
        else:
            return TradingDecision(Action.HOLD, 0.5, current_price, reason="No clear signal, waiting for opportunity")
        
        self.previous_macd = current_macd
        self.previous_signal = current_signal
        
        return decision
    
    def calculate_position_size(self, balance: float, price: float, confidence: float) -> float:
        """Calculate position size based on confidence level"""
        base_size = balance * 0.1  # Base position 10%
        adjusted_size = base_size * confidence
        max_trade_value = balance * 0.2  # Maximum single trade 20%
        
        position_size = min(adjusted_size, max_trade_value)
        quantity = position_size / price
        
        return quantity