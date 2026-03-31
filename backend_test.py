#!/usr/bin/env python3
"""
Backend API Testing for CSV Upload Functionality
Tests all CSV upload endpoints and real data backtest integration
"""

import requests
import sys
import json
from datetime import datetime
import time

class CSVUploadAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)

            print(f"   Status: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and 'success' in response_data:
                        print(f"   Success: {response_data.get('success')}")
                    return True, response_data
                except:
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                    self.failed_tests.append({
                        'test': name,
                        'expected': expected_status,
                        'actual': response.status_code,
                        'error': error_data
                    })
                except:
                    print(f"   Error: {response.text}")
                    self.failed_tests.append({
                        'test': name,
                        'expected': expected_status,
                        'actual': response.status_code,
                        'error': response.text
                    })
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({
                'test': name,
                'expected': expected_status,
                'actual': 'Exception',
                'error': str(e)
            })
            return False, {}

    def test_csv_import_dukascopy(self):
        """Test CSV import with Dukascopy format"""
        # Sample Dukascopy CSV data
        csv_data = """Date,Open,High,Low,Close,Volume
2024.01.01 00:00:00,1.1050,1.1055,1.1045,1.1052,1000
2024.01.01 01:00:00,1.1052,1.1058,1.1048,1.1055,1200
2024.01.01 02:00:00,1.1055,1.1062,1.1051,1.1060,1100
2024.01.01 03:00:00,1.1060,1.1065,1.1056,1.1063,1300
2024.01.01 04:00:00,1.1063,1.1068,1.1059,1.1065,1150"""

        success, response = self.run_test(
            "CSV Import - Dukascopy Format",
            "POST",
            "marketdata/import/csv",
            200,
            data={
                "symbol": "EURUSD",
                "timeframe": "1h",
                "data": csv_data,
                "format_type": "dukascopy",
                "skip_validation": False
            }
        )
        
        if success and response.get('success'):
            print(f"   Imported: {response.get('imported', 0)} candles")
            print(f"   Symbol: {response.get('symbol')}")
            print(f"   Date Range: {response.get('date_range', {}).get('start')} to {response.get('date_range', {}).get('end')}")
            return response.get('symbol'), response.get('timeframe')
        return None, None

    def test_csv_import_xauusd(self):
        """Test CSV import with XAUUSD data"""
        # Sample XAUUSD CSV data
        csv_data = """Date,Open,High,Low,Close,Volume
2024.01.01 00:00:00,2050.50,2055.75,2048.25,2053.80,500
2024.01.01 01:00:00,2053.80,2058.90,2051.20,2056.45,650
2024.01.01 02:00:00,2056.45,2061.30,2054.10,2059.75,720
2024.01.01 03:00:00,2059.75,2063.85,2057.40,2062.20,580
2024.01.01 04:00:00,2062.20,2066.50,2060.15,2064.80,610"""

        success, response = self.run_test(
            "CSV Import - XAUUSD Data",
            "POST",
            "marketdata/import/csv",
            200,
            data={
                "symbol": "XAUUSD",
                "timeframe": "1h",
                "data": csv_data,
                "format_type": "dukascopy",
                "skip_validation": False
            }
        )
        
        if success and response.get('success'):
            print(f"   Imported: {response.get('imported', 0)} candles")
            return response.get('symbol'), response.get('timeframe')
        return None, None

    def test_data_validation(self, symbol, timeframe):
        """Test data validation endpoint"""
        if not symbol or not timeframe:
            print("⚠️ Skipping validation test - no symbol/timeframe from import")
            return False
            
        success, response = self.run_test(
            f"Data Validation - {symbol} {timeframe}",
            "POST",
            f"marketdata/validate?symbol={symbol}&timeframe={timeframe}",
            200
        )
        
        if success and response.get('success'):
            quality = response.get('quality', {})
            print(f"   Quality Score: {quality.get('score', 0)}%")
            print(f"   Coverage: {quality.get('coverage_percent', 0)}%")
            print(f"   Gaps: {quality.get('gaps_detected', 0)}")
            return True
        return False

    def test_available_market_data(self):
        """Test available market data endpoint"""
        success, response = self.run_test(
            "Available Market Data",
            "GET",
            "marketdata/available",
            200
        )
        
        if success and response.get('success'):
            symbols = response.get('symbols', [])
            print(f"   Available symbols: {len(symbols)}")
            for symbol_info in symbols[:3]:  # Show first 3
                print(f"   - {symbol_info.get('symbol')}: {symbol_info.get('timeframes', [])}")
            return symbols
        return []

    def test_real_data_backtest(self, symbol="EURUSD", timeframe="1h"):
        """Test real data backtest endpoint"""
        session_id = f"test_session_{int(time.time())}"
        endpoint = f"backtest/run?session_id={session_id}&bot_name=TestBot&symbol={symbol}&timeframe={timeframe}&start_date=2024-01-01T00:00:00&end_date=2024-01-01T23:59:59&initial_balance=10000.0&fast_ma=10&slow_ma=20"
        
        success, response = self.run_test(
            f"Real Data Backtest - {symbol} {timeframe}",
            "POST",
            endpoint,
            200
        )
        
        if success and response.get('success'):
            summary = response.get('summary', {})
            print(f"   Candles processed: {summary.get('candles_processed', 0)}")
            print(f"   Total trades: {summary.get('total_trades', 0)}")
            print(f"   Net profit: ${summary.get('net_profit', 0):.2f}")
            print(f"   Win rate: {summary.get('win_rate', 0):.1f}%")
            return response.get('backtest_id')
        return None

    def test_ensure_real_data(self, symbol="EURUSD", timeframe="1h"):
        """Test ensure real data endpoint"""
        success, response = self.run_test(
            f"Ensure Real Data - {symbol} {timeframe}",
            "POST",
            "marketdata/ensure-real-data",
            200,
            data={
                "symbol": symbol,
                "timeframe": timeframe,
                "min_candles": 60
            }
        )
        
        if success:
            print(f"   Data available: {response.get('success', False)}")
            print(f"   Candle count: {response.get('candle_count', 0)}")
            print(f"   Data source: {response.get('data_source', 'unknown')}")
            return response.get('success', False)
        return False

    def test_market_data_stats(self, symbol="EURUSD", timeframe="1h"):
        """Test market data statistics endpoint"""
        success, response = self.run_test(
            f"Market Data Stats - {symbol} {timeframe}",
            "GET",
            f"marketdata/{symbol}/{timeframe}/stats",
            200
        )
        
        if success and response.get('success'):
            stats = response.get('stats', {})
            print(f"   Total candles: {stats.get('total_candles', 0)}")
            print(f"   Date range: {stats.get('date_range_days', 0)} days")
            print(f"   Provider: {stats.get('provider', 'unknown')}")
            return True
        return False

    def test_delete_market_data(self, symbol="EURUSD", timeframe="1h"):
        """Test delete market data endpoint"""
        success, response = self.run_test(
            f"Delete Market Data - {symbol} {timeframe}",
            "DELETE",
            f"marketdata/{symbol}?timeframe={timeframe}",
            200
        )
        
        if success:
            print(f"   Deletion result: {response.get('success', False)}")
            return response.get('success', False)
        return False

def main():
    print("🚀 Starting CSV Upload Backend API Tests")
    print("=" * 60)
    
    tester = CSVUploadAPITester()
    
    # Test 1: CSV Import with Dukascopy format
    print("\n📊 PHASE 1: CSV Data Import")
    symbol1, timeframe1 = tester.test_csv_import_dukascopy()
    
    # Test 2: CSV Import with XAUUSD data
    symbol2, timeframe2 = tester.test_csv_import_xauusd()
    
    # Test 3: Data validation
    print("\n🔍 PHASE 2: Data Validation")
    if symbol1 and timeframe1:
        tester.test_data_validation(symbol1, timeframe1)
    if symbol2 and timeframe2:
        tester.test_data_validation(symbol2, timeframe2)
    
    # Test 4: Available market data
    print("\n📋 PHASE 3: Available Data Query")
    available_symbols = tester.test_available_market_data()
    
    # Test 5: Market data statistics
    print("\n📈 PHASE 4: Data Statistics")
    if symbol1 and timeframe1:
        tester.test_market_data_stats(symbol1, timeframe1)
    
    # Test 6: Ensure real data endpoint
    print("\n🔄 PHASE 5: Real Data Availability")
    if symbol1 and timeframe1:
        tester.test_ensure_real_data(symbol1, timeframe1)
    
    # Test 7: Real data backtest
    print("\n⚡ PHASE 6: Real Data Backtest")
    if symbol1 and timeframe1:
        backtest_id = tester.test_real_data_backtest(symbol1, timeframe1)
        if backtest_id:
            print(f"   Backtest ID: {backtest_id}")
    
    # Test 8: Cleanup - Delete test data
    print("\n🧹 PHASE 7: Cleanup")
    if symbol1 and timeframe1:
        tester.test_delete_market_data(symbol1, timeframe1)
    if symbol2 and timeframe2:
        tester.test_delete_market_data(symbol2, timeframe2)
    
    # Print results
    print("\n" + "=" * 60)
    print(f"📊 TEST RESULTS")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if tester.failed_tests:
        print(f"\n❌ FAILED TESTS ({len(tester.failed_tests)}):")
        for i, failure in enumerate(tester.failed_tests, 1):
            print(f"{i}. {failure['test']}")
            print(f"   Expected: {failure['expected']}, Got: {failure['actual']}")
            print(f"   Error: {failure['error']}")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())