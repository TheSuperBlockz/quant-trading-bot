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
        
        # Suppress werkzeug HTTP request logs
        logging.getLogger('werkzeug').setLevel(logging.WARNING)

    def setup_dashboard(self):
        """Set up dashboard layout"""
        self.app.layout = html.Div([
            html.H1("Trading Bot Dashboard", style={'textAlign': 'center'}),

            # Real-time metrics
            html.Div([
                html.Div(id='live-metrics', style={
                    'display': 'flex',
                    'justifyContent': 'space-around',
                    'marginBottom': '20px'
                }),
            ]),

            # Charts
            html.Div([
                dcc.Graph(id='portfolio-value-chart'),
                dcc.Graph(id='price-chart'),
                dcc.Graph(id='trades-chart'),
            ], style={'display': 'flex', 'flexDirection': 'column', 'gap': '20px'}),

            # Trade history table
            html.Div([
                html.H3("Recent Trades"),
                html.Div(id='trade-table')
            ]),

            # Auto refresh
            dcc.Interval(
                id='interval-component',
                interval=2*1000,  # Update every 2 seconds
                n_intervals=0
            )
        ])

        # Set up callbacks
        self.setup_callbacks()

    def setup_callbacks(self):
        """Set up dashboard callbacks"""
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
                # Load latest data
                portfolio_data = self.load_portfolio_data()
                trade_data = self.load_trade_data()
                market_data = self.load_market_data()

                # Update metrics
                metrics = self.update_metrics(portfolio_data, trade_data)

                # Update charts
                portfolio_chart = self.create_portfolio_chart(portfolio_data)
                price_chart = self.create_price_chart(market_data)
                trades_chart = self.create_trades_chart(trade_data, portfolio_data)

                # Update trade table
                trade_table = self.create_trade_table(trade_data)

                return metrics, portfolio_chart, price_chart, trades_chart, trade_table

            except Exception as e:
                self.logger.error(f"Dashboard update error: {e}")
                # Return empty data on error
                return [], go.Figure(), go.Figure(), go.Figure(), html.Div("Error loading data")

    def load_portfolio_data(self):
        """Load portfolio data"""
        try:
            with open('logs/portfolio_history.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def load_trade_data(self):
        """Load trade data"""
        try:
            with open('logs/trade_history.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def load_market_data(self):
        """Load market data"""
        try:
            market_data = []
            with open('logs/market_data.jsonl', 'r', encoding='utf-8') as f:
                for line in f:
                    market_data.append(json.loads(line))
            return market_data[-100:]  # Last 100 data points
        except:
            return []

    def update_metrics(self, portfolio_data, trade_data):
        """Update real-time metrics display"""
        if not portfolio_data:
            return [html.Div("No data available")]

        latest_portfolio = portfolio_data[-1]
        total_trades = len(trade_data)

        # calculate daily pnl
        daily_pnl = 0
        if len(portfolio_data) > 1:
            daily_pnl = latest_portfolio.get('total_value', 0) - portfolio_data[0].get('total_value', 0)

        metrics = [
            html.Div([
                html.H4(f"${latest_portfolio.get('total_value', 0):.2f}"),
                html.P("Portfolio Total Value"),
            ], style={'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '10px'}),

            html.Div([
                html.H4(f"${latest_portfolio.get('cash_value', 0):.2f}"),
                html.P("USD Cash"),
            ], style={'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '10px'}),

            html.Div([
                html.H4(f"{latest_portfolio.get('btc_balance', 0):.8f} BTC"),
                html.P(f"${latest_portfolio.get('btc_value', 0):.2f}"),
            ], style={'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '10px'}),

            html.Div([
                html.H4(f"${daily_pnl:+.2f}", style={'color': 'green' if daily_pnl >= 0 else 'red'}),
                html.P("Today's P/L"),
            ], style={'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '10px'}),

            html.Div([
                html.H4(f"{total_trades}"),
                html.P("Total Trades"),
            ], style={'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '10px'})
        ]

        return metrics

    def create_portfolio_chart(self, portfolio_data):
        """Create portfolio value chart"""
        if not portfolio_data:
            return go.Figure()

        df = pd.DataFrame(portfolio_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['total_value'],
            mode='lines',
            name='Portfolio Value',
            line=dict(color='green', width=2)
        ))

        fig.update_layout(
            title='Portfolio Value Change',
            xaxis_title='Time',
            yaxis_title='Value (USD)'
        )

        return fig

    def create_price_chart(self, market_data):
        """Create price chart"""
        if not market_data:
            return go.Figure()

        fig = go.Figure()

        # Extract price data
        timestamps = []
        prices = []

        for entry in market_data:
            # Try multiple field names for price
            price = None
            
            # Check nested structure: entry['Data']['BTC/USD']['LastPrice']
            if 'Data' in entry and isinstance(entry['Data'], dict):
                for pair_key, pair_data in entry['Data'].items():
                    if isinstance(pair_data, dict) and 'LastPrice' in pair_data:
                        price = pair_data['LastPrice']
                        break
            
            # Fallback to top-level fields
            if price is None:
                for field in ['lastPrice', 'LastPrice', 'last_price', 'price']:
                    if field in entry:
                        price = entry[field]
                        break
            
            if price is not None:
                timestamps.append(pd.to_datetime(entry['timestamp']))
                prices.append(float(price))

        if timestamps and prices:
            fig.add_trace(go.Scatter(
                x=timestamps,
                y=prices,
                mode='lines',
                name='BTC Price',
                line=dict(color='blue', width=1)
            ))

        fig.update_layout(
            title='BTC Price Trend',
            xaxis_title='Time',
            yaxis_title='Price (USD)'
        )

        return fig

    def create_trades_chart(self, trade_data, portfolio_data):
        """Create trade markers chart"""
        fig = go.Figure()
        
        # Set layout first (even for empty chart)
        fig.update_layout(
            title="Portfolio Value with Trade Markers",
            xaxis_title="Time",
            yaxis_title="Portfolio Value (USD)"
        )
        
        if not portfolio_data:
            return fig

        portfolio_df = pd.DataFrame(portfolio_data)
        portfolio_df['timestamp'] = pd.to_datetime(portfolio_df['timestamp'])

        # Portfolio value
        fig.add_trace(go.Scatter(
            x=portfolio_df['timestamp'],
            y=portfolio_df['total_value'],
            mode='lines',
            name='Portfolio Value',
            line=dict(color='blue', width=2)
        ))

        # Add trade markers if we have trade data
        if trade_data:
            trade_df = pd.DataFrame(trade_data)
            if not trade_df.empty:
                trade_df['timestamp'] = pd.to_datetime(trade_df['timestamp'])
                
                # Buy trade markers
                if 'action' in trade_df.columns:
                    buy_trades = trade_df[trade_df['action'] == 'BUY']
                    if not buy_trades.empty:
                        fig.add_trace(go.Scatter(
                            x=buy_trades['timestamp'],
                            y=[portfolio_df['total_value'].max() * 0.95] * len(buy_trades),
                            mode='markers',
                            name='Buy',
                            marker=dict(color='green', size=12, symbol='triangle-up')
                        ))

                    # Sell trade markers
                    sell_trades = trade_df[trade_df['action'] == 'SELL']
                    if not sell_trades.empty:
                        fig.add_trace(go.Scatter(
                            x=sell_trades['timestamp'],
                            y=[portfolio_df['total_value'].min() * 1.05] * len(sell_trades),
                            mode='markers',
                            name='Sell',
                            marker=dict(color='red', size=12, symbol='triangle-down')
                        ))

        return fig

    def create_trade_table(self, trade_data):
        """Create trade history table"""
        if not trade_data:
            return html.Div("No trade records")

        # Get last 10 trades
        recent_trades = trade_data[-10:][::-1]  # Reverse to show newest first

        table_rows = []
        for trade in recent_trades:
            action_color = 'green' if trade.get('action') == 'BUY' else 'red'
            table_rows.append(html.Tr([
                html.Td(trade.get('timestamp', '')[:19]),  # Remove milliseconds
                html.Td(trade.get('action', ''), style={'color': action_color}),
                html.Td(trade.get('symbol', '')),
                html.Td(f"{trade.get('quantity', 0):.4f}"),
                html.Td(f"${trade.get('price', 0):.2f}"),
                html.Td(f"${trade.get('total', 0):.2f}"),
                html.Td(trade.get('reason', ''))
            ]))

        table = html.Table([
            html.Thead(html.Tr([
                html.Th('Time'),
                html.Th('Action'),
                html.Th('Pair'),
                html.Th('Quantity'),
                html.Th('Price'),
                html.Th('Total'),
                html.Th('Reason')
            ])),
            html.Tbody(table_rows)
        ], style={'width': '100%', 'border': '1px solid black', 'borderCollapse': 'collapse'})

        return table

    def run(self):
        """Run dashboard"""
        self.logger.info(f"Starting dashboard: http://localhost:{self.port}")
        self.app.run(host='0.0.0.0', port=self.port, debug=False)


def start_dashboard():
    """Function to start the dashboard"""
    dashboard = TradingDashboard()
    dashboard.run()


if __name__ == "__main__":
    start_dashboard()