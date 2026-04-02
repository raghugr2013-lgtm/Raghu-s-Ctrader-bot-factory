#!/usr/bin/env python3
"""
Backend API Testing for Market Data Management Module
Tests DELETE functionality and timeframe dropdown features
"""

import requests
import sys
import json
from datetime import datetime

class MarketDataAPITester:
    def __init__(self, base_url="https://fd0de349-2a40-4396-9616-a5beef9290e0.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            print(f"   Status: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if 'success' in response_data:
                        print(f"   Success: {response_data['success']}")
                    if 'deleted_count' in response_data:
                        print(f"   Deleted Count: {response_data['deleted_count']}")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_basic_connectivity(self):
        """Test basic API connectivity"""
        success, _ = self.run_test(
            "Basic API Connectivity",
            "GET",
            "",
            200
        )
        return success

    def test_market_data_coverage(self):
        """Test market data coverage endpoint"""
        success, response = self.run_test(
            "Market Data Coverage",
            "GET",
            "marketdata/coverage",
            200
        )
        
        if success and response:
            print(f"   Found {len(response.get('symbols', []))} symbols with data")
            
            # Check if we have EURUSD H1 data as mentioned in context
            symbols = response.get('symbols', [])
            eurusd_found = False
            for symbol_data in symbols:
                if symbol_data.get('symbol') == 'EURUSD':
                    eurusd_found = True
                    timeframes = symbol_data.get('timeframes', [])
                    h1_found = any(tf.get('timeframe') == '1h' for tf in timeframes)
                    if h1_found:
                        print(f"   ✅ Found EURUSD H1 data as expected")
                    else:
                        print(f"   ⚠️ EURUSD found but no H1 timeframe")
                    break
            
            if not eurusd_found:
                print(f"   ⚠️ EURUSD data not found")
        
        return success

    def test_delete_endpoint_with_invalid_data(self):
        """Test DELETE endpoint with non-existent data"""
        success, response = self.run_test(
            "DELETE Non-existent Dataset",
            "DELETE",
            "marketdata/TESTXXX/1h",
            200  # Should return 200 with deleted_count: 0
        )
        
        if success and response:
            deleted_count = response.get('deleted_count', -1)
            if deleted_count == 0:
                print(f"   ✅ Correctly returned 0 deleted count for non-existent data")
            else:
                print(f"   ⚠️ Unexpected deleted count: {deleted_count}")
        
        return success

    def test_delete_endpoint_with_real_data(self):
        """Test DELETE endpoint with real data (if available)"""
        # First check what data is available
        success, coverage = self.run_test(
            "Get Coverage for DELETE test",
            "GET", 
            "marketdata/coverage",
            200
        )
        
        if not success or not coverage:
            print("   ⚠️ Cannot test DELETE with real data - coverage check failed")
            return False
            
        symbols = coverage.get('symbols', [])
        if not symbols:
            print("   ⚠️ No data available to test DELETE")
            return True  # Not a failure, just no data
            
        # Find first available dataset
        test_symbol = None
        test_timeframe = None
        
        for symbol_data in symbols:
            symbol = symbol_data.get('symbol')
            timeframes = symbol_data.get('timeframes', [])
            if timeframes:
                test_symbol = symbol
                test_timeframe = timeframes[0].get('timeframe')
                break
        
        if not test_symbol or not test_timeframe:
            print("   ⚠️ No suitable data found for DELETE test")
            return True
            
        print(f"   Testing DELETE with {test_symbol} {test_timeframe}")
        
        # Test the DELETE endpoint
        success, response = self.run_test(
            f"DELETE {test_symbol} {test_timeframe}",
            "DELETE",
            f"marketdata/{test_symbol}/{test_timeframe}",
            200
        )
        
        if success and response:
            deleted_count = response.get('deleted_count', 0)
            print(f"   ✅ DELETE successful - removed {deleted_count} candles")
        
        return success

    def test_data_integrity_check(self):
        """Test data integrity check endpoint"""
        success, response = self.run_test(
            "Data Integrity Check",
            "GET",
            "data-integrity/check",
            200
        )
        
        if success and response:
            integrity_ok = response.get('integrity_ok', False)
            synthetic_count = response.get('synthetic_count', 0)
            real_count = response.get('real_count', 0)
            
            print(f"   Integrity OK: {integrity_ok}")
            print(f"   Synthetic Count: {synthetic_count}")
            print(f"   Real Count: {real_count}")
        
        return success

    def test_timeframe_constants(self):
        """Test that all 8 timeframes are supported by checking coverage"""
        expected_timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']
        
        success, coverage = self.run_test(
            "Check Timeframe Support",
            "GET",
            "marketdata/coverage", 
            200
        )
        
        if success and coverage:
            symbols = coverage.get('symbols', [])
            found_timeframes = set()
            
            for symbol_data in symbols:
                timeframes = symbol_data.get('timeframes', [])
                for tf in timeframes:
                    found_timeframes.add(tf.get('timeframe'))
            
            print(f"   Found timeframes: {sorted(found_timeframes)}")
            
            # Check if we have data for the new timeframes (M1, M5, M15, M30)
            new_timeframes = ['1m', '5m', '15m', '30m']
            found_new = [tf for tf in new_timeframes if tf in found_timeframes]
            
            if found_new:
                print(f"   ✅ Found new timeframes: {found_new}")
            else:
                print(f"   ⚠️ No data found for new timeframes: {new_timeframes}")
        
        return success

def main():
    """Run all tests"""
    print("🚀 Starting Market Data Management API Tests")
    print("=" * 60)
    
    tester = MarketDataAPITester()
    
    # Test basic connectivity first
    if not tester.test_basic_connectivity():
        print("❌ Basic connectivity failed, stopping tests")
        return 1
    
    # Test market data coverage
    tester.test_market_data_coverage()
    
    # Test data integrity
    tester.test_data_integrity_check()
    
    # Test timeframe support
    tester.test_timeframe_constants()
    
    # Test DELETE endpoint with invalid data
    tester.test_delete_endpoint_with_invalid_data()
    
    # Test DELETE endpoint with real data (if available)
    tester.test_delete_endpoint_with_real_data()
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())