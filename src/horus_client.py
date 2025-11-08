import requests
from typing import Dict, List, Optional
from config.config import Config

class HorusClient:
    """Client for interacting with the Horus API"""
    
    BASE_URL = "https://api-horus.com"
    
    def __init__(self):
        self.config = Config()
        self.api_key = self.config.HORUS_API_KEY
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Send API request to Horus"""
        url = f"{self.BASE_URL}{endpoint}"
        
        headers = {
            'X-API-Key': self.api_key
        }
        
        try:
            print(f"Making request to: {url}")
            print(f"With params: {params}")
            print(f"With headers: {headers}")
            response = requests.get(url, params=params, headers=headers, timeout=10)
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request error: {e}")
            if hasattr(e.response, 'text'):
                print(f"Error response content: {e.response.text}")
            return {'error': str(e)}
    
    def get_price_history(self, symbol: str = "BTC", interval: str = "15m", 
                         start: Optional[int] = None, end: Optional[int] = None) -> List:
        """
        Get historical price data from Horus API
        
        Args:
            symbol: Asset symbol (e.g., "BTC", "ETH")
            interval: Time interval ("1d", "1h", "15m")
            start: Start timestamp in seconds (inclusive)
            end: End timestamp in seconds (exclusive)
            
        Returns:
            List of price data points
        """
        # Start with just the required parameters that worked in Postman
        params = {
            'asset': symbol
        }
        
        # Only add optional parameters if they are specifically needed
        if interval != "1d":  # Add interval only if it's not the default
            params['interval'] = interval
        if start is not None:
            params['start'] = start
        if end is not None:
            params['end'] = end
            
        return self._make_request('/market/price', params)  # The full URL will be https://api-horus.com/market/price