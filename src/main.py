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
        """启动仪表盘（仅本地测试）"""
        try:
            from dashboard import start_dashboard
            self.dashboard_thread = threading.Thread(target=start_dashboard, daemon=True)
            self.dashboard_thread.start()
            self.logger.logger.info("仪表盘启动: http://localhost:8050")
        except Exception as e:
            self.logger.logger.error(f"启动仪表盘失败: {e}")
    
    def get_portfolio_value(self, balance_data: Dict, current_prices: Dict) -> float:
        """计算投资组合总价值"""
        try:
            cash = balance_data.get('USD', {}).get('free', 0)
            total_value = cash
            
            # 计算持仓价值
            for coin, balance in balance_data.items():
                if coin != 'USD' and balance.get('free', 0) > 0:
                    coin_value = balance['free'] * current_prices.get(coin, 0)
                    total_value += coin_value
            
            return total_value
        except Exception as e:
            self.logger.logger.error(f"计算投资组合价值失败: {e}")
            return 0
    
    def execute_trade(self, decision, balance_data: Dict):
        """执行交易"""
        try:
            symbol = self.config.TRADE_PAIR
            base_currency = symbol.split('/')[0]  # BTC
            quote_currency = symbol.split('/')[1]  # USD
            
            if decision.action == Action.BUY:
                # 计算购买数量
                available_cash = balance_data.get(quote_currency, {}).get('free', 0)
                max_trade_value = available_cash * self.config.MAX_POSITION_SIZE
                quantity = max_trade_value / decision.price
                
                if quantity * decision.price < 10:  # 最小交易金额检查
                    self.logger.logger.info("交易金额太小，跳过")
                    return
                
                # 执行买入
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
                # 计算卖出数量
                available_coin = balance_data.get(base_currency, {}).get('free', 0)
                quantity = available_coin * self.config.MAX_POSITION_SIZE
                
                if quantity * decision.price < 10:  # 最小交易金额检查
                    self.logger.logger.info("交易金额太小，跳过")
                    return
                
                # 执行卖出
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
            self.logger.logger.error(f"执行交易失败: {e}")
    
    def run(self):
        """主交易循环"""
        self.logger.logger.info("启动交易机器人...")
        
        iteration = 0
        while self.running:
            try:
                iteration += 1
                self.logger.logger.info(f"第 {iteration} 次迭代开始...")
                
                # 1. 获取市场数据
                market_data = self.roostoo.get_market_data(self.config.TRADE_PAIR)
                if 'error' in market_data:
                    self.logger.logger.error(f"获取市场数据失败: {market_data['error']}")
                    time.sleep(30)
                    continue
                
                # 记录市场数据
                self.logger.log_market_data(market_data)
                
                # 2. 获取K线数据
                klines = self.roostoo.get_klines(
                    symbol=self.config.TRADE_PAIR,
                    interval='1m',
                    limit=100
                )
                
                if 'error' in klines or not klines:
                    self.logger.logger.error("获取K线数据失败")
                    time.sleep(30)
                    continue
                
                # 3. 获取当前价格
                current_price = float(market_data.get('lastPrice', 0))
                if current_price == 0:
                    self.logger.logger.error("获取价格失败")
                    time.sleep(30)
                    continue
                
                # 4. 策略分析
                decision = self.strategy.analyze(klines, current_price)
                
                # 记录策略信号
                signal_data = {
                    'action': decision.action.value,
                    'confidence': decision.confidence,
                    'price': current_price,
                    'reason': decision.reason
                }
                self.logger.log_strategy_signal(signal_data)
                
                self.logger.logger.info(
                    f"策略决策: {decision.action.value}, "
                    f"信心度: {decision.confidence:.2f}, "
                    f"价格: {current_price:.2f}, "
                    f"原因: {decision.reason}"
                )
                
                # 5. 获取账户余额
                balance_data = self.roostoo.get_account_balance()
                if 'error' in balance_data:
                    self.logger.logger.error("获取账户余额失败")
                    time.sleep(30)
                    continue
                
                # 6. 记录投资组合状态
                portfolio_value = self.get_portfolio_value(balance_data, {self.config.TRADE_PAIR.split('/')[0]: current_price})
                portfolio_data = {
                    'total_value': portfolio_value,
                    'cash_value': balance_data.get('USD', {}).get('free', 0),
                    'btc_balance': balance_data.get('BTC', {}).get('free', 0),
                    'btc_value': balance_data.get('BTC', {}).get('free', 0) * current_price,
                    'current_price': current_price
                }
                self.logger.log_portfolio_update(portfolio_data)
                
                # 7. 执行交易决策
                if decision.action != Action.HOLD:
                    self.execute_trade(decision, balance_data)
                
                # 8. 等待下一次迭代
                self.logger.logger.info(f"等待 {self.config.TRADE_INTERVAL} 秒...")
                time.sleep(self.config.TRADE_INTERVAL)
                
            except KeyboardInterrupt:
                self.logger.logger.info("用户中断，停止机器人...")
                self.running = False
                
            except Exception as e:
                self.logger.logger.error(f"主循环错误: {e}")
                time.sleep(60)  # 出错时等待更久

if __name__ == "__main__":
    # 本地测试启用仪表盘，AWS部署时禁用
    bot = TradingBot(enable_dashboard=True)
    bot.run()