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
    Enhanced MACD Strategy with Cryptocurrency Optimizations:
    - Volatility-adjusted parameters
    - Flash crash protection
    - Market hours awareness
    - Crypto-specific risk management
    """
    
    def __init__(self, fast_period=12, slow_period=26, signal_period=9, 
                 stop_loss_pct=0.03, take_profit_pct=0.03, 
                 trailing_stop_pct=0.015, trailing_activation_pct=0.02,
                 max_position_hours=48, min_trade_interval_seconds=3600,
                 # Cryptocurrency optimizations
                 volatility_lookback=20, high_vol_multiplier=1.5):
        """
        Initialize crypto-optimized MACD strategy
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
        
        # Cryptocurrency optimizations
        self.volatility_lookback = volatility_lookback
        self.high_vol_multiplier = high_vol_multiplier
        self.previous_price = None
        self.current_volatility = 0.02
        
        # Position tracking
        self.position = Position()
        
        # Trade history for cooldown
        self.last_trade_time = None
        self.last_trade_action = None
        
        # MACD state
        self.previous_macd = None
        self.previous_signal = None
        
        logger.info("Crypto-optimized MACD Strategy initialized")
    
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
    
    def calculate_crypto_volatility(self, prices: List[float]) -> float:
        """Calculate cryptocurrency volatility for parameter adjustment"""
        if len(prices) < 2:
            return 0.02
            
        returns = []
        lookback = min(len(prices) - 1, self.volatility_lookback)
        
        for i in range(1, lookback + 1):
            if prices[-i-1] != 0:
                price_change = abs(prices[-i] - prices[-i-1]) / prices[-i-1]
                returns.append(price_change)
        
        volatility = np.mean(returns) if returns else 0.02
        self.current_volatility = volatility
        return volatility
    
    def adjust_parameters_for_volatility(self, current_volatility: float):
        """Dynamically adjust parameters based on market volatility"""
        base_sl = 0.03
        base_tp = 0.03
        
        if current_volatility > 0.05:  # High volatility market
            self.stop_loss_pct = min(base_sl * self.high_vol_multiplier, 0.08)
            self.take_profit_pct = min(base_tp * self.high_vol_multiplier, 0.08)
            logger.info(f"High volatility detected: {current_volatility*100:.1f}%, adjusting SL/TP to {self.stop_loss_pct*100:.1f}%")
        elif current_volatility < 0.01:  # Low volatility market
            self.stop_loss_pct = max(base_sl * 0.7, 0.015)
            self.take_profit_pct = max(base_tp * 0.7, 0.015)
            logger.info(f"Low volatility detected: {current_volatility*100:.1f}%, tightening SL/TP to {self.stop_loss_pct*100:.1f}%")
        else:
            self.stop_loss_pct = base_sl
            self.take_profit_pct = base_tp
    
    def flash_crash_protection(self, current_price: float) -> bool:
        """Flash crash detection for cryptocurrency markets"""
        if self.previous_price is None:
            self.previous_price = current_price
            return False
            
        price_change_pct = abs(current_price - self.previous_price) / self.previous_price
        
        # If price changes more than 7% in one interval, likely flash crash
        if price_change_pct > 0.07:
            logger.warning(f"Flash crash detected: {price_change_pct*100:.2f}% price change")
            self.previous_price = current_price
            return True
        
        self.previous_price = current_price
        return False
    
    def is_high_volatility_hours(self) -> bool:
        """Identify cryptocurrency high volatility periods"""
        from datetime import datetime
        utc_hour = datetime.utcnow().hour
        
        # Asian market hours (0-8 UTC) + Euro/US overlap (13-17 UTC)
        high_vol_hours = list(range(0, 8)) + list(range(13, 18))
        return utc_hour in high_vol_hours
    
    def adjust_confidence_for_market_hours(self, decision: TradingDecision) -> TradingDecision:
        """Adjust trading confidence based on market hours"""
        if self.is_high_volatility_hours():
            # More conservative during high volatility hours
            if decision.confidence < 0.75:
                decision.confidence *= 0.8
                decision.reason += " | High vol hours"
                logger.debug("Reduced confidence due to high volatility hours")
        else:
            # Slightly more aggressive during low volatility, but still conservative
            if decision.confidence > 0.6:
                decision.confidence = min(decision.confidence * 1.1, 0.9)
        
        return decision
    
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
            f"SL: ${self.position.stop_loss:.2f} ({self.stop_loss_pct*100:.1f}%), "
            f"TP: ${self.position.take_profit:.2f} ({self.take_profit_pct*100:.1f}%), "
            f"Qty: {quantity:.8f}"
        )
    
    def close_position(self, reason: str):
        """Close current position"""
        logger.info(f"Position closed - Reason: {reason}")
        self.position = Position()
    
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
        Analyze market with cryptocurrency optimizations
        """
        # Flash crash protection check
        if self.flash_crash_protection(current_price):
            return TradingDecision(
                Action.HOLD, 0.9, current_price, 
                reason="Flash crash protection - skipping trade"
            )
        
        # Extract prices and calculate volatility
        closes = [float(kline['price']) for kline in klines_data]
        volatility = self.calculate_crypto_volatility(closes)
        self.adjust_parameters_for_volatility(volatility)
        
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
            f"Hist: {current_histogram:.4f}, Volatility: {volatility*100:.2f}%"
        )
        
        # === ENTRY LOGIC ===
        decision = None
        
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
                        logger.debug(f"BUY signal filtered: price ${current_price:.2f} below EMA200 ${ema200:.2f}")
                        return TradingDecision(Action.HOLD, 0.5, current_price, reason="Price below long-term trend")
                
                decision = TradingDecision(
                    action=Action.BUY,
                    confidence=0.65,
                    price=current_price,
                    reason="MACD bullish momentum (positive and rising)"
                )
                logger.info(f"BUY signal generated: {decision.reason}")
        
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
        
        # Default: HOLD
        if decision is None:
            if self.position.state == PositionState.LONG:
                profit_pct = (current_price - self.position.entry_price) / self.position.entry_price
                return TradingDecision(
                    Action.HOLD, 
                    0.5, 
                    current_price, 
                    reason=f"Holding position, P/L: {profit_pct*100:+.2f}%, SL: ${self.position.stop_loss:.2f}"
                )
            else:
                return TradingDecision(Action.HOLD, 0.5, current_price, reason="No clear signal, waiting for opportunity")
        
        # Apply market hours adjustment
        decision = self.adjust_confidence_for_market_hours(decision)
        
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
