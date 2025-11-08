import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum

class Action(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

@dataclass
class TradingDecision:
    action: Action
    confidence: float
    price: float
    quantity: float = 0
    reason: str = ""

class MACEStrategy:
    """
    Moving Average Convergence Divergence (MACD) with Exponential smoothing strategy
    """
    
    def __init__(self, fast_period=12, slow_period=26, signal_period=9):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
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
    
    def analyze(self, klines_data: List, current_price: float) -> TradingDecision:
        """
        Analyze market and generate trading decision

        Parameters:
            klines_data: K-line data [open_time, open, high, low, close, volume]
            current_price: Current price

        Returns:
            TradingDecision: Trading decision
        """
        if len(klines_data) < self.slow_period + self.signal_period:
            return TradingDecision(Action.HOLD, 0, current_price, reason="Insufficient data")
        
        # Extract prices from Horus API data format
        closes = [float(kline['price']) for kline in klines_data]  # Price is in 'price' field
        
        # Calculate MACD
        macd_line, signal_line, histogram = self.calculate_macd(closes)
        
        # Get latest values
        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        previous_macd = macd_line[-2] if len(macd_line) > 1 else None
        previous_signal = signal_line[-2] if len(signal_line) > 1 else None
        
        if (pd.isna(current_macd) or pd.isna(current_signal) or 
            pd.isna(previous_macd) or pd.isna(previous_signal)):
            return TradingDecision(Action.HOLD, 0, current_price, reason="MACD calculation incomplete")
        
        # Generate trading signal
        decision = TradingDecision(Action.HOLD, 0.5, current_price)
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"MACD Analysis - Current MACD: {current_macd:.4f}, Signal: {current_signal:.4f}, Previous MACD: {previous_macd:.4f}, Previous Signal: {previous_signal:.4f}")
        
        # MACD crosses above signal line - Buy signal
        if (previous_macd < previous_signal and current_macd > current_signal):
            decision.action = Action.BUY
            decision.confidence = 0.7
            decision.reason = "MACD golden cross, buy signal"
            
        # MACD crosses below signal line - Sell signal
        elif (previous_macd > previous_signal and current_macd < current_signal):
            decision.action = Action.SELL
            decision.confidence = 0.7
            decision.reason = "MACD death cross, sell signal"
            
        # Strong signal above zero line
        elif current_macd > 0 and current_macd > current_signal:
            decision.action = Action.BUY
            decision.confidence = 0.6
            decision.reason = "MACD above zero line and rising"
            
        # Weak signal below zero line
        elif current_macd < 0 and current_macd < current_signal:
            decision.action = Action.SELL
            decision.confidence = 0.6
            decision.reason = "MACD below zero line and falling"
        
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