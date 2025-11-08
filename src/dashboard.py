import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
import json
import threading
import time
from datetime import datetime
import logging

class TradingDashboard:
    def __init__(self, port=8050):
        self.port = port
        self.app = dash.Dash(__name__)
        self.setup_dashboard()
        self.logger = logging.getLogger(__name__)
    
    def setup_dashboard(self):
        """设置仪表盘布局"""
        self.app.layout = html.Div([
            html.H1("🤖 交易机器人监控面板", style={'textAlign': 'center'}),
            
            # 实时指标
            html.Div([
                html.Div(id='live-metrics', style={
                    'display': 'flex',
                    'justifyContent': 'space-around',
                    'marginBottom': '20px'
                }),
            ]),
            
            # 图表
            html.Div([
                dcc.Graph(id='portfolio-value-chart'),
                dcc.Graph(id='price-chart'),
                dcc.Graph(id='trades-chart'),
            ], style={'display': 'flex', 'flexDirection': 'column', 'gap': '20px'}),
            
            # 交易历史表格
            html.Div([
                html.H3("最近交易"),
                html.Div(id='trade-table')
            ]),
            
            # 自动刷新
            dcc.Interval(
                id='interval-component',
                interval=2*1000,  # 每2秒更新
                n_intervals=0
            )
        ])
        
        # 设置回调
        self.setup_callbacks()
    
    def setup_callbacks(self):
        """设置仪表盘回调"""
        @self.app.callback(
            [Output('live-metrics', 'children'),
             Output('portfolio-value-chart', 'figure'),
             Output('price-chart', 'figure'),
             Output('trades-chart', 'figure'),
             Output('trade-table', 'children')],
            [Input('interval-component', 'n_intervals')]
        )
        def update_dashboard(n):
            try:
                # 加载最新数据
                portfolio_data = self.load_portfolio_data()
                trade_data = self.load_trade_data()
                market_data = self.load_market_data()
                
                # 更新指标
                metrics = self.update_metrics(portfolio_data, trade_data)
                
                # 更新图表
                portfolio_chart = self.create_portfolio_chart(portfolio_data)
                price_chart = self.create_price_chart(market_data)
                trades_chart = self.create_trades_chart(trade_data, portfolio_data)
                
                # 更新交易表格
                trade_table = self.create_trade_table(trade_data)
                
                return metrics, portfolio_chart, price_chart, trades_chart, trade_table
                
            except Exception as e:
                self.logger.error(f"仪表盘更新错误: {e}")
                # 出错时返回空数据
                return [], go.Figure(), go.Figure(), go.Figure(), html.Div("加载数据错误")
    
    def load_portfolio_data(self):
        """加载投资组合数据"""
        try:
            with open('logs/portfolio_history.json', 'r') as f:
                return json.load(f)
        except:
            return []
    
    def load_trade_data(self):
        """加载交易数据"""
        try:
            with open('logs/trade_history.json', 'r') as f:
                return json.load(f)
        except:
            return []
    
    def load_market_data(self):
        """加载市场数据"""
        try:
            market_data = []
            with open('logs/market_data.jsonl', 'r') as f:
                for line in f:
                    market_data.append(json.loads(line))
            return market_data[-100:]  # 最后100个数据点
        except:
            return []
    
    def update_metrics(self, portfolio_data, trade_data):
        """更新实时指标显示"""
        if not portfolio_data:
            return [html.Div("暂无数据")]
        
        latest_portfolio = portfolio_data[-1]
        total_trades = len(trade_data)
        
        # 计算今日盈亏
        daily_pnl = 0
        if len(portfolio_data) > 1:
            daily_pnl = latest_portfolio.get('total_value', 0) - portfolio_data[0].get('total_value', 0)
        
        metrics = [
            html.Div([
                html.H4(f"${latest_portfolio.get('total_value', 0):.2f}"),
                html.P("💰 投资组合总值")
            ], style={'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '10px'}),
            
            html.Div([
                html.H4(f"${latest_portfolio.get('cash_value', 0):.2f}"),
                html.P("💵 可用现金")
            ], style={'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '10px'}),
            
            html.Div([
                html.H4(f"${daily_pnl:+.2f}", style={'color': 'green' if daily_pnl >= 0 else 'red'}),
                html.P("📈 今日盈亏")
            ], style={'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '10px'}),
            
            html.Div([
                html.H4(f"{total_trades}"),
                html.P("🔄 总交易次数")
            ], style={'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '10px'})
        ]
        
        return metrics
    
    def create_portfolio_chart(self, portfolio_data):
        """创建投资组合价值图表"""
        if not portfolio_data:
            return go.Figure()
        
        df = pd.DataFrame(portfolio_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp'], 
            y=df['total_value'], 
            mode='lines', 
            name='投资组合价值', 
            line=dict(color='green', width=2)
        ))
        
        fig.update_layout(
            title='投资组合价值变化',
            xaxis_title='时间',
            yaxis_title='价值 (USD)'
        )
        
        return fig
    
    def create_price_chart(self, market_data):
        """创建价格图表"""
        if not market_data:
            return go.Figure()
        
        fig = go.Figure()
        
        # 提取价格数据
        timestamps = []
        prices = []
        
        for entry in market_data:
            if 'lastPrice' in entry:
                timestamps.append(pd.to_datetime(entry['timestamp']))
                prices.append(entry['lastPrice'])
        
        if timestamps and prices:
            fig.add_trace(go.Scatter(
                x=timestamps, 
                y=prices, 
                mode='lines', 
                name='BTC价格',
                line=dict(color='blue', width=1)
            ))
        
        fig.update_layout(
            title='BTC价格走势',
            xaxis_title='时间',
            yaxis_title='价格 (USD)'
        )
        
        return fig
    
    def create_trades_chart(self, trade_data, portfolio_data):
        """创建交易标记图表"""
        if not trade_data or not portfolio_data:
            return go.Figure()
        
        portfolio_df = pd.DataFrame(portfolio_data)
        portfolio_df['timestamp'] = pd.to_datetime(portfolio_df['timestamp'])
        
        trade_df = pd.DataFrame(trade_data)
        if not trade_df.empty:
            trade_df['timestamp'] = pd.to_datetime(trade_df['timestamp'])
        
        fig = go.Figure()
        
        # 投资组合价值
        fig.add_trace(go.Scatter(
            x=portfolio_df['timestamp'], 
            y=portfolio_df['total_value'], 
            mode='lines', 
            name='投资组合价值', 
            line=dict(color='blue', width=2)
        ))
        
        # 买入交易标记
        if not trade_df.empty and 'action' in trade_df.columns:
            buy_trades = trade_df[trade_df['action'] == 'BUY']
            if not buy_trades.empty:
                fig.add_trace(go.Scatter(
                    x=buy_trades['timestamp'],
                    y=[portfolio_df['total_value'].max() * 0.95] * len(buy_trades),
                    mode='markers',
                    name='买入',
                    marker=dict(color='green', size=12, symbol='triangle-up')
                ))
            
            # 卖出交易标记
            sell_trades = trade_df[trade_df['action'] == 'SELL']
            if not sell_trades.empty:
                fig.add_trace(go.Scatter(
                    x=sell_trades['timestamp'],
                    y=[portfolio_df['total_value'].min() * 1.05] * len(sell_trades),
                    mode='markers',
                    name='卖出',
                    marker=dict(color='red', size=12, symbol='triangle-down')
                ))
        
        fig.update_layout(
            title="投资组合价值与交易标记",
            xaxis_title="时间",
            yaxis_title="投资组合价值 (USD)"
        )
        
        return fig
    
    def create_trade_table(self, trade_data):
        """创建交易历史表格"""
        if not trade_data:
            return html.Div("暂无交易记录")
        
        # 获取最近10笔交易
        recent_trades = trade_data[-10:][::-1]  # 反转以显示最新的在前面
        
        table_rows = []
        for trade in recent_trades:
            action_color = 'green' if trade.get('action') == 'BUY' else 'red'
            table_rows.append(html.Tr([
                html.Td(trade.get('timestamp', '')[:19]),  # 去掉毫秒
                html.Td(trade.get('action', ''), style={'color': action_color}),
                html.Td(trade.get('symbol', '')),
                html.Td(f"{trade.get('quantity', 0):.4f}"),
                html.Td(f"${trade.get('price', 0):.2f}"),
                html.Td(f"${trade.get('total', 0):.2f}"),
                html.Td(trade.get('reason', ''))
            ]))
        
        table = html.Table([
            html.Thead(html.Tr([
                html.Th('时间'),
                html.Th('操作'),
                html.Th('交易对'),
                html.Th('数量'),
                html.Th('价格'),
                html.Th('总额'),
                html.Th('原因')
            ])),
            html.Tbody(table_rows)
        ], style={'width': '100%', 'border': '1px solid black', 'borderCollapse': 'collapse'})
        
        return table
    
    def run(self):
        """运行仪表盘"""
        self.logger.info(f"启动仪表盘: http://localhost:{self.port}")
        self.app.run_server(host='0.0.0.0', port=self.port, debug=False)

def start_dashboard():
    """启动仪表盘的函数"""
    dashboard = TradingDashboard()
    dashboard.run()

if __name__ == "__main__":
    start_dashboard()