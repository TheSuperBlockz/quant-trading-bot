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
    Moving Average Convergence Divergence (MACD) with Exponential smoothing 策略
    """
    
    def __init__(self, fast_period=12, slow_period=26, signal_period=9):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.previous_macd = None
        self.previous_signal = None
        
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """计算指数移动平均线"""
        if len(prices) < period:
            return [np.nan] * len(prices)
            
        ema = []
        multiplier = 2 / (period + 1)
        
        # 第一个EMA是简单移动平均
        sma = sum(prices[:period]) / period
        ema.extend([sma] * (period - 1))
        
        current_ema = sma
        for price in prices[period:]:
            current_ema = (price - current_ema) * multiplier + current_ema
            ema.append(current_ema)
            
        return ema
    
    def calculate_macd(self, prices: List[float]) -> Tuple[List[float], List[float], List[float]]:
        """计算MACD指标"""
        fast_ema = self.calculate_ema(prices, self.fast_period)
        slow_ema = self.calculate_ema(prices, self.slow_period)
        
        # 计算MACD线
        macd_line = []
        for fast, slow in zip(fast_ema, slow_ema):
            if pd.isna(fast) or pd.isna(slow):
                macd_line.append(np.nan)
            else:
                macd_line.append(fast - slow)
        
        # 计算信号线
        signal_line = self.calculate_ema([x for x in macd_line if not pd.isna(x)], self.signal_period)
        
        # 对齐长度
        nan_padding = [np.nan] * (len(macd_line) - len(signal_line))
        signal_line = nan_padding + signal_line
        
        # 计算柱状图
        histogram = []
        for macd, signal in zip(macd_line, signal_line):
            if pd.isna(macd) or pd.isna(signal):
                histogram.append(np.nan)
            else:
                histogram.append(macd - signal)
                
        return macd_line, signal_line, histogram
    
    def analyze(self, klines_data: List, current_price: float) -> TradingDecision:
        """
        分析市场并生成交易决策
        
        参数:
            klines_data: K线数据 [开盘时间, 开盘价, 最高价, 最低价, 收盘价, 成交量]
            current_price: 当前价格
            
        返回:
            TradingDecision: 交易决策
        """
        if len(klines_data) < self.slow_period + self.signal_period:
            return TradingDecision(Action.HOLD, 0, current_price, reason="数据不足")
        
        # 提取收盘价
        closes = [float(kline[4]) for kline in klines_data]  # 收盘价在第5个位置
        
        # 计算MACD
        macd_line, signal_line, histogram = self.calculate_macd(closes)
        
        # 获取最新值
        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        previous_macd = macd_line[-2] if len(macd_line) > 1 else None
        previous_signal = signal_line[-2] if len(signal_line) > 1 else None
        
        if (pd.isna(current_macd) or pd.isna(current_signal) or 
            pd.isna(previous_macd) or pd.isna(previous_signal)):
            return TradingDecision(Action.HOLD, 0, current_price, reason="MACD计算不完整")
        
        # 生成交易信号
        decision = TradingDecision(Action.HOLD, 0.5, current_price)
        
        # MACD上穿信号线 - 买入信号
        if (previous_macd < previous_signal and current_macd > current_signal):
            decision.action = Action.BUY
            decision.confidence = 0.7
            decision.reason = "MACD金叉，买入信号"
            
        # MACD下穿信号线 - 卖出信号
        elif (previous_macd > previous_signal and current_macd < current_signal):
            decision.action = Action.SELL
            decision.confidence = 0.7
            decision.reason = "MACD死叉，卖出信号"
            
        # 零轴之上的强势信号
        elif current_macd > 0 and current_macd > current_signal:
            decision.action = Action.BUY
            decision.confidence = 0.6
            decision.reason = "MACD在零轴上方且上涨"
            
        # 零轴之下的弱势信号
        elif current_macd < 0 and current_macd < current_signal:
            decision.action = Action.SELL
            decision.confidence = 0.6
            decision.reason = "MACD在零轴下方且下跌"
        
        self.previous_macd = current_macd
        self.previous_signal = current_signal
        
        return decision
    
    def calculate_position_size(self, balance: float, price: float, confidence: float) -> float:
        """根据信心度计算仓位大小"""
        base_size = balance * 0.1  # 基础仓位10%
        adjusted_size = base_size * confidence
        max_trade_value = balance * 0.2  # 最大单次交易20%
        
        position_size = min(adjusted_size, max_trade_value)
        quantity = position_size / price
        
        return quantity