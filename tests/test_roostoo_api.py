#!/usr/bin/env python3
"""
Interactive Roostoo API Testing Script

This script allows you to test all Roostoo API endpoints interactively.
It helps verify API connectivity and see actual response data.

Usage:
    python tests/test_roostoo_api.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
from src.roostoo_client import RoostooClient
from config.config import Config

class RoostooAPITester:
    def __init__(self):
        self.client = RoostooClient()
        self.config = Config()
        
    def print_separator(self):
        print("\n" + "="*80 + "\n")
    
    def print_json(self, data, title="Response"):
        """Pretty print JSON data"""
        print(f"\n{title}:")
        print("-" * 40)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("-" * 40)
    
    def test_market_data(self):
        """Test 1: Get Market Data (Ticker)"""
        self.print_separator()
        print("TEST 1: GET MARKET DATA (TICKER)")
        print(f"Endpoint: /v3/ticker")
        print(f"Trading Pair: {self.config.TRADE_PAIR}")
        
        try:
            result = self.client.get_market_data(self.config.TRADE_PAIR)
            self.print_json(result, "Market Data Response")
            
            # Try to extract key fields
            print("\n📊 Key Information:")
            if 'Data' in result and self.config.TRADE_PAIR in result['Data']:
                ticker_data = result['Data'][self.config.TRADE_PAIR]
                print(f"  Last Price: {ticker_data.get('LastPrice', 'N/A')}")
                print(f"  24h High: {ticker_data.get('High', 'N/A')}")
                print(f"  24h Low: {ticker_data.get('Low', 'N/A')}")
                print(f"  24h Volume: {ticker_data.get('Volume', 'N/A')}")
            elif 'lastPrice' in result:
                print(f"  Last Price: {result.get('lastPrice', 'N/A')}")
                print(f"  24h High: {result.get('high', 'N/A')}")
                print(f"  24h Low: {result.get('low', 'N/A')}")
                print(f"  24h Volume: {result.get('volume', 'N/A')}")
            else:
                print("  ⚠️  Unable to extract standard fields")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def test_account_balance(self):
        """Test 2: Get Account Balance"""
        self.print_separator()
        print("TEST 2: GET ACCOUNT BALANCE")
        print(f"Endpoint: /v3/balance")
        
        try:
            result = self.client.get_account_balance()
            self.print_json(result, "Balance Response")
            
            # Show normalized balance
            print("\n💰 Your Balances:")
            if isinstance(result, dict):
                for currency, balance_info in result.items():
                    if isinstance(balance_info, dict):
                        free = balance_info.get('free', 0)
                        locked = balance_info.get('locked', 0)
                        total = free + locked
                        print(f"  {currency}:")
                        print(f"    Free: {free}")
                        print(f"    Locked: {locked}")
                        print(f"    Total: {total}")
                    else:
                        print(f"  {currency}: {balance_info}")
            else:
                print("  ⚠️  Unexpected balance format")
                
            # Check if balance is sufficient for trading
            print("\n🔍 Trading Viability Check:")
            usd_balance = result.get('USD', {}).get('free', 0) if isinstance(result, dict) else 0
            btc_balance = result.get('BTC', {}).get('free', 0) if isinstance(result, dict) else 0
            
            min_trade_usd = 10  # Minimum trade amount in USD
            print(f"  USD Balance: ${usd_balance:.2f}")
            print(f"  BTC Balance: {btc_balance:.8f} BTC")
            print(f"  Minimum Trade Amount: ${min_trade_usd}")
            
            if usd_balance >= min_trade_usd:
                print(f"  ✅ You can place BUY orders (sufficient USD)")
            else:
                print(f"  ❌ Cannot place BUY orders (need at least ${min_trade_usd} USD)")
                
            # Estimate BTC value (assuming ~100k per BTC)
            estimated_btc_value = btc_balance * 100000
            if estimated_btc_value >= min_trade_usd:
                print(f"  ✅ You can place SELL orders (sufficient BTC)")
            else:
                print(f"  ❌ Cannot place SELL orders (BTC value ~${estimated_btc_value:.2f} < ${min_trade_usd})")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def test_place_order(self, side='BUY', quantity=0.001):
        """Test 3: Place Order (Use with caution!)"""
        self.print_separator()
        print("TEST 3: PLACE ORDER")
        print(f"Endpoint: /v3/place_order")
        print("⚠️  WARNING: This will attempt to place a REAL order!")
        
        base_currency = self.config.TRADE_PAIR.split('/')[0]  # BTC
        
        print(f"\nOrder Details:")
        print(f"  Coin: {base_currency}")
        print(f"  Side: {side}")
        print(f"  Quantity: {quantity}")
        
        confirm = input("\n⚠️  Type 'YES' to proceed with placing this order: ")
        
        if confirm != 'YES':
            print("❌ Order placement cancelled.")
            return
        
        try:
            result = self.client.place_order(
                coin=base_currency,
                side=side,
                quantity=quantity
            )
            self.print_json(result, "Place Order Response")
            
            if 'error' not in result:
                print("\n✅ Order placed successfully!")
                if 'orderId' in result:
                    print(f"  Order ID: {result['orderId']}")
                    return result['orderId']
            else:
                print(f"\n❌ Order failed: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        return None
    
    def test_query_order(self, order_id=None):
        """Test 4: Query Order Status"""
        self.print_separator()
        print("TEST 4: QUERY ORDER STATUS")
        print(f"Endpoint: /v3/query_order")
        
        if not order_id:
            order_id = input("\nEnter Order ID to query (or press Enter to skip): ").strip()
            if not order_id:
                print("❌ No order ID provided, skipping...")
                return
        
        base_currency = self.config.TRADE_PAIR.split('/')[0]  # BTC
        
        try:
            result = self.client.query_order(
                coin=base_currency,
                order_id=order_id
            )
            self.print_json(result, "Query Order Response")
            
            # Extract key order information
            print("\n📋 Order Information:")
            if 'status' in result:
                print(f"  Status: {result.get('status')}")
                print(f"  Side: {result.get('side', 'N/A')}")
                print(f"  Quantity: {result.get('quantity', 'N/A')}")
                print(f"  Filled: {result.get('filled', 'N/A')}")
                print(f"  Price: {result.get('price', 'N/A')}")
            else:
                print("  ⚠️  Unable to extract standard order fields")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def test_cancel_order(self, order_id=None):
        """Test 5: Cancel Order"""
        self.print_separator()
        print("TEST 5: CANCEL ORDER")
        print(f"Endpoint: /v3/cancel_order")
        print("⚠️  WARNING: This will cancel a real order!")
        
        if not order_id:
            order_id = input("\nEnter Order ID to cancel (or press Enter to skip): ").strip()
            if not order_id:
                print("❌ No order ID provided, skipping...")
                return
        
        base_currency = self.config.TRADE_PAIR.split('/')[0]  # BTC
        
        confirm = input(f"\n⚠️  Type 'YES' to cancel order {order_id}: ")
        
        if confirm != 'YES':
            print("❌ Order cancellation cancelled.")
            return
        
        try:
            result = self.client.cancel_order(
                coin=base_currency,
                order_id=order_id
            )
            self.print_json(result, "Cancel Order Response")
            
            if 'error' not in result:
                print("\n✅ Order cancelled successfully!")
            else:
                print(f"\n❌ Cancellation failed: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def test_all_readonly(self):
        """Run all read-only tests (safe to run)"""
        print("\n" + "🔬 ROOSTOO API TESTING SUITE" + "\n")
        print("Running all READ-ONLY tests (safe, no orders will be placed)")
        print("="*80)
        
        # Test 1: Market Data
        self.test_market_data()
        
        # Test 2: Account Balance
        self.test_account_balance()
        
        self.print_separator()
        print("✅ Read-only tests completed!")
        print("\nTo test order placement, query, and cancellation:")
        print("  Run this script and select option 3, 4, or 5 from the menu.")
    
    def run_interactive(self):
        """Interactive menu for testing"""
        while True:
            self.print_separator()
            print("🔬 ROOSTOO API TESTING MENU")
            print("\nSelect a test to run:")
            print("  1. Get Market Data (Ticker) - SAFE")
            print("  2. Get Account Balance - SAFE")
            print("  3. Place Order - ⚠️  REAL ORDER")
            print("  4. Query Order Status - SAFE")
            print("  5. Cancel Order - ⚠️  REAL CANCELLATION")
            print("  6. Run All Read-Only Tests - SAFE")
            print("  0. Exit")
            
            choice = input("\nEnter your choice (0-6): ").strip()
            
            if choice == '1':
                self.test_market_data()
            elif choice == '2':
                self.test_account_balance()
            elif choice == '3':
                side = input("Order side (BUY/SELL) [BUY]: ").strip().upper() or 'BUY'
                qty = input("Quantity (e.g., 0.001) [0.001]: ").strip()
                qty = float(qty) if qty else 0.001
                order_id = self.test_place_order(side, qty)
                
                # Ask if user wants to query the order
                if order_id:
                    query = input("\nQuery this order? (y/n) [y]: ").strip().lower()
                    if query != 'n':
                        self.test_query_order(order_id)
                        
            elif choice == '4':
                self.test_query_order()
            elif choice == '5':
                self.test_cancel_order()
            elif choice == '6':
                self.test_all_readonly()
            elif choice == '0':
                print("\n👋 Goodbye!")
                break
            else:
                print("\n❌ Invalid choice, please try again.")
            
            input("\nPress Enter to continue...")

def main():
    """Main entry point"""
    print("="*80)
    print("🔬 ROOSTOO API TESTER")
    print("="*80)
    print("\nThis tool helps you test all Roostoo API endpoints.")
    print("It will show you the actual API responses and help debug issues.")
    print("\n⚠️  Some operations (place/cancel order) affect your real account!")
    print("="*80)
    
    tester = RoostooAPITester()
    
    # Check if running with command line argument
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == 'all' or arg == 'readonly':
            tester.test_all_readonly()
        else:
            print(f"Unknown argument: {arg}")
            print("Usage: python test_roostoo_api.py [all|readonly]")
    else:
        # Run interactive menu
        tester.run_interactive()

if __name__ == "__main__":
    main()
