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
        """生成API签名"""
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        return hmac.new(
            self.secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """发送API请求"""
        url = f"{self.base_url}{endpoint}"
        
        if params is None:
            params = {}
            
        # 添加公共参数
        params.update({
            'api_key': self.api_key,
            'timestamp': int(time.time() * 1000)
        })
        
        # 生成签名
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
            print(f"API请求错误: {e}")
            return {'error': str(e)}
    
    def get_account_balance(self) -> Dict:
        """获取账户余额"""
        return self._make_request('GET', '/api/v1/account/balance')
    
    def get_market_data(self, symbol: str) -> Dict:
        """获取市场数据"""
        params = {'symbol': symbol}
        return self._make_request('GET', '/api/v1/market/ticker', params)
    
    def get_klines(self, symbol: str, interval: str = '1m', limit: int = 100) -> List:
        """获取K线数据"""
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        return self._make_request('GET', '/api/v1/market/klines', params)
    
    def place_order(self, symbol: str, side: str, quantity: float, order_type: str = 'MARKET') -> Dict:
        """下单"""
        params = {
            'symbol': symbol,
            'side': side.upper(),
            'type': order_type.upper(),
            'quantity': quantity
        }
        return self._make_request('POST', '/api/v1/trade/order', params)
    
    def get_open_orders(self, symbol: str = None) -> List:
        """获取当前挂单"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return self._make_request('GET', '/api/v1/trade/openOrders', params)
    
    def cancel_order(self, order_id: str) -> Dict:
        """取消订单"""
        params = {'order_id': order_id}
        return self._make_request('POST', '/api/v1/trade/cancel', params)