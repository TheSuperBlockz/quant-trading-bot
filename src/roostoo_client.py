import requests
import hashlib
import hmac
import time
import json
from typing import Dict, List, Optional
from config.config import Config

class RoostooClient:
    def __init__(self):
        self.config = Config()
        self.base_url = self.config.ROOSTOO_BASE_URL
        self.api_key = self.config.ROOSTOO_API_KEY
        self.secret = self.config.ROOSTOO_SECRET
        
    def _generate_signature(self, params: Dict) -> str:
        """Generate API signature"""
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        return hmac.new(
            self.secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Send API request"""
        url = f"{self.base_url}{endpoint}"
        
        if params is None:
            params = {}
            
        # Add common parameters
        params.update({
            'api_key': self.api_key,
            'timestamp': int(time.time() * 1000)
        })
        
        # Generate signature
        params['sign'] = self._generate_signature(params)
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=params, timeout=10)
            elif method.upper() == 'POST':
                response = requests.post(url, data=params, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"API request error: {e}")
            return {'error': str(e)}
    
    def get_account_balance(self) -> Dict:
        """Get account balance"""
        return self._make_request('GET', '/api/v1/account/balance')
    
    def get_market_data(self, symbol: str) -> Dict:
        """Get market data"""
        params = {'symbol': symbol}
        return self._make_request('GET', '/api/v1/market/ticker', params)
    
    def get_klines(self, symbol: str, interval: str = '1m', limit: int = 100) -> List:
        """Get K-line (candlestick) data"""
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        return self._make_request('GET', '/api/v1/market/klines', params)
    
    def place_order(self, symbol: str, side: str, quantity: float, order_type: str = 'MARKET') -> Dict:
        """Place a new order"""
        params = {
            'symbol': symbol,
            'side': side.upper(),
            'type': order_type.upper(),
            'quantity': quantity
        }
        return self._make_request('POST', '/api/v1/trade/order', params)
    
    def get_open_orders(self, symbol: str = None) -> List:
        """Get current open orders"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return self._make_request('GET', '/api/v1/trade/openOrders', params)
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        params = {'order_id': order_id}
        return self._make_request('POST', '/api/v1/trade/cancel', params)