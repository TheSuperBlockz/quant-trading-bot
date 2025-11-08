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
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, auth_required: bool = False) -> Dict:
        """Send API request"""
        url = f"{self.base_url}{endpoint}"
        
        if params is None:
            params = {}
            
        if auth_required:
            # Add timestamp for authenticated endpoints
            params['timestamp'] = int(time.time() * 1000)
            
            # Generate signature and set headers
            headers = {
                'RST-API-KEY': self.api_key,
                'MSG-SIGNATURE': self._generate_signature(params)
            }
        else:
            headers = {}
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=10)
            elif method.upper() == 'POST':
                response = requests.post(url, data=params, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"API request error: {e}")
            return {'error': str(e)}
    
    def get_server_time(self) -> Dict:
        """Get server time"""
        return self._make_request('GET', '/v3/serverTime')
        
    def get_exchange_info(self) -> Dict:
        """Get exchange information"""
        return self._make_request('GET', '/v3/exchangeInfo')
    
    def get_account_balance(self) -> Dict:
        """Get account balance"""
        return self._make_request('GET', '/v3/balance', auth_required=True)
    
    def get_market_data(self, pair: str = None) -> Dict:
        """Get market data"""
        params = {}
        if pair:
            params['pair'] = pair
        params['timestamp'] = int(time.time())
        return self._make_request('GET', '/v3/ticker', params)
    
    def place_order(self, coin: str, side: str, quantity: float, price: float = None) -> Dict:
        """Place a new order"""
        params = {
            'pair': f"{coin}/USD",
            'side': side.upper(),
            'quantity': quantity
        }
        
        if not price:
            params['type'] = 'MARKET'
        else:
            params['type'] = 'LIMIT'
            params['price'] = price
            
        return self._make_request('POST', '/v3/place_order', params, auth_required=True)
    
    def get_open_orders(self, pair: str = None) -> Dict:
        """Get current open orders"""
        params = {}
        if pair:
            params['pair'] = pair
        params['pending_only'] = True
        return self._make_request('POST', '/v3/query_order', params, auth_required=True)
    
    def cancel_order(self, order_id: str = None, pair: str = None) -> Dict:
        """Cancel an order"""
        params = {}
        if order_id:
            params['order_id'] = order_id
        if pair:
            params['pair'] = pair
        return self._make_request('POST', '/v3/cancel_order', params, auth_required=True)
        
    def get_pending_count(self) -> Dict:
        """Get number of pending orders"""
        return self._make_request('GET', '/v3/pending_count', auth_required=True)
        
    def get_klines(self, pair: str, interval: str = '1m', limit: int = 100) -> List:
        """Get K-line (candlestick) data"""
        params = {
            'pair': pair,
            'interval': interval,
            'limit': limit,
            'timestamp': int(time.time())
        }
        return self._make_request('GET', '/v3/klines', params)