import requests
import hashlib
import hmac
import time
import json
from typing import Dict, List, Optional, Any
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
        """Get account balance and normalize to a unified structure.

        Returns a dict like:
        {
            'USD': {'free': float, 'locked': float},
            'BTC': {'free': float, 'locked': float},
            ...
        }
        """
        raw = self._make_request('GET', '/v3/balance', auth_required=True)
        # If API errored or returned a direct error payload, pass it through
        if not isinstance(raw, dict) or 'error' in raw:
            return raw

        try:
            return self._normalize_balance(raw)
        except Exception as e:
            # Fallback to raw on unexpected shape so caller can log
            return {'error': f"Failed to normalize balance: {e}", 'raw': raw}

    def _normalize_balance(self, resp: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """Normalize various wallet response shapes into {'ASSET': {'free', 'locked'}}.

        Supports Roostoo v3 mock shape with keys: 'SpotWallet', 'MarginWallet'.
        Tries common field names for symbols and amounts.
        """
        normalized: Dict[str, Dict[str, float]] = {}

        def to_float(val: Any, default: float = 0.0) -> float:
            try:
                if val is None:
                    return default
                return float(val)
            except (TypeError, ValueError):
                return default

        def merge_asset(symbol: str, free_val: Any = None, locked_val: Any = None, total_val: Any = None, available_val: Any = None, hold_val: Any = None):
            sym = (symbol or '').strip().upper()
            if not sym:
                return

            # Unify stablecoin naming to USD for downstream usage
            if sym in ('USDT', 'USD$'):
                sym = 'USD'

            # Determine free/locked using best-effort heuristics
            free_amt = to_float(
                free_val if free_val is not None else
                available_val if available_val is not None else
                None,
                0.0
            )

            locked_amt = to_float(locked_val, 0.0)

            total_amt = to_float(total_val, None)
            hold_amt = to_float(hold_val, 0.0)

            # If total provided but free is missing, derive from total - locked/hold
            if total_amt is not None and free_amt == 0.0:
                derived_locked = locked_amt if locked_amt else hold_amt
                if total_amt >= derived_locked:
                    free_amt = total_amt - derived_locked

            # Merge into existing entry if any
            entry = normalized.get(sym, {'free': 0.0, 'locked': 0.0})
            entry['free'] = to_float(entry.get('free', 0.0)) + free_amt
            entry['locked'] = to_float(entry.get('locked', 0.0)) + locked_amt
            normalized[sym] = entry

        def extract_symbol(item: Dict[str, Any]) -> Optional[str]:
            for key in ('Coin', 'coin', 'Asset', 'asset', 'Symbol', 'symbol', 'Currency', 'currency', 'Name', 'name'):
                if key in item and item[key]:
                    return str(item[key])
            # Some APIs embed it as id fields
            for key in ('CoinId', 'coinId', 'assetId', 'AssetId'):
                if key in item and item[key]:
                    return str(item[key])
            return None

        def extract_amounts(item: Dict[str, Any]) -> Dict[str, Any]:
            # Try common naming patterns
            free_candidates = [
                item.get('free'), item.get('Free'), item.get('available'), item.get('Available'),
                item.get('availableBalance'), item.get('AvailableBalance'), item.get('avail'), item.get('Avail')
            ]
            locked_candidates = [item.get('locked'), item.get('Locked'), item.get('hold'), item.get('Hold'), item.get('onHold'), item.get('OnHold')]
            total_candidates = [item.get('total'), item.get('Total'), item.get('balance'), item.get('Balance'), item.get('amount'), item.get('Amount')]

            def first_non_none(vals):
                for v in vals:
                    if v is not None:
                        return v
                return None

            return {
                'free': first_non_none(free_candidates),
                'locked': first_non_none(locked_candidates),
                'total': first_non_none(total_candidates)
            }

        # Handle SpotWallet list
        spot = resp.get('SpotWallet')
        if isinstance(spot, list):
            for item in spot:
                if not isinstance(item, dict):
                    continue
                sym = extract_symbol(item)
                amts = extract_amounts(item)
                merge_asset(sym, free_val=amts['free'], locked_val=amts['locked'], total_val=amts['total'])
        elif isinstance(spot, dict):
            # Some shapes wrap balances under a key like 'Balances'
            balances = spot.get('Balances') or spot.get('balances') or spot.get('Assets') or spot.get('assets')
            if isinstance(balances, list):
                for item in balances:
                    if not isinstance(item, dict):
                        continue
                    sym = extract_symbol(item)
                    amts = extract_amounts(item)
                    merge_asset(sym, free_val=amts['free'], locked_val=amts['locked'], total_val=amts['total'])

        # Optionally incorporate MarginWallet free balances if present
        margin = resp.get('MarginWallet')
        if isinstance(margin, list):
            for item in margin:
                if not isinstance(item, dict):
                    continue
                sym = extract_symbol(item)
                amts = extract_amounts(item)
                merge_asset(sym, free_val=amts['free'], locked_val=amts['locked'], total_val=amts['total'])

        # Ensure required keys exist with zeros to satisfy downstream logic
        for required in ('USD', 'BTC'):
            if required not in normalized:
                normalized[required] = {'free': 0.0, 'locked': 0.0}

        return normalized
    
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