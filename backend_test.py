#!/usr/bin/env python3
"""
Backend API Testing for Strategy Generation System
Tests new strategy generation endpoints and job-based processing
"""

import requests
import sys
import json
import time
from datetime import datetime

class StrategyGenerationAPITester:
    def __init__(self, base_url="https://codebase-review-86.preview.emergentagent.com"):
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
        if data and len(str(data)) < 500:  # Only show data if it's not too large
            print(f"   Data: {json.dumps(data, indent=2)}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                if data:
                    response = requests.post(url, json=data, headers=headers)
                else:
                    response = requests.post(url, headers=headers)
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

    def import_sample_data(self):
        """Import sample EURUSD data for testing"""
        print("\n🔍 Importing Sample Data...")
        
        # Create a larger sample CSV data for testing in MT4 format (need 100+ candles)
        sample_csv = """2024.01.04 18:00,1.095045,1.09544,1.094605,1.0947,17983
2024.01.04 19:00,1.094720,1.094985,1.094345,1.094705,13209
2024.01.04 20:00,1.094700,1.094925,1.094320,1.094920,20185
2024.01.04 21:00,1.094915,1.095005,1.094380,1.094440,10594
2024.01.04 22:00,1.094510,1.095025,1.094480,1.094735,7338
2024.01.04 23:00,1.094685,1.094895,1.094330,1.094635,3978
2024.01.05 00:00,1.094620,1.095150,1.094445,1.095090,7118
2024.01.05 01:00,1.095085,1.095595,1.095025,1.095165,18493
2024.01.05 02:00,1.095170,1.095430,1.094670,1.094700,12424
2024.01.05 03:00,1.094695,1.094740,1.093920,1.093925,11791"""
        
        # Generate more data points to reach 100+ candles
        base_data = []
        for i in range(100):
            hour = 4 + i
            day = 5 + (hour // 24)
            hour = hour % 24
            price = 1.0940 + (i % 20) * 0.0001
            base_data.append(f"2024.01.{day:02d} {hour:02d}:00,{price:.5f},{price+0.0005:.5f},{price-0.0005:.5f},{price+0.0002:.5f},{1000+i*10}")
        
        sample_csv += "\n" + "\n".join(base_data)
        
        try:
            import_data = {
                "symbol": "EURUSD",
                "timeframe": "1h", 
                "data": sample_csv,
                "format_type": "mt4",
                "provider": "csv_import"
            }
            
            success, response = self.run_test(
                "Import EURUSD H1 Sample Data",
                "POST",
                "marketdata/import/csv",
                200,
                data=import_data
            )
            
            if success and response:
                imported_count = response.get('imported_count', 0)
                print(f"   ✅ Imported {imported_count} candles")
                return imported_count >= 100
            else:
                print(f"   ⚠️ Failed to import sample data")
                return False
                
        except Exception as e:
            print(f"   ❌ Error importing data: {str(e)}")
            return False

    # =====================================================
    # STRATEGY GENERATION SYSTEM TESTS
    # =====================================================

    def test_data_availability_check(self):
        """Test the new data availability check endpoint"""
        print("\n🔍 Testing Data Availability Check...")
        
        success, response = self.run_test(
            "Data Availability Check for EURUSD",
            "GET",
            "marketdata/check-any-availability/EURUSD",
            200
        )
        
        if success and response:
            available = response.get('available', False)
            available_timeframes = response.get('available_timeframes', [])
            best_timeframe = response.get('best_timeframe')
            candle_count = response.get('candle_count', 0)
            
            print(f"   Available: {available}")
            print(f"   Available Timeframes: {available_timeframes}")
            print(f"   Best Timeframe: {best_timeframe}")
            print(f"   Candle Count: {candle_count}")
            
            if available and available_timeframes:
                print(f"   ✅ Data availability check working correctly")
            else:
                print(f"   ⚠️ No data available for EURUSD")
        
        return success

    def test_strategy_job_creation(self):
        """Test strategy job creation endpoint"""
        print("\n🔍 Testing Strategy Job Creation...")
        
        job_data = {
            "symbol": "EURUSD",
            "timeframe": "1h",
            "strategy_count": 10,
            "strategy_type": "intraday",
            "risk_level": "medium",
            "execution_mode": "fast",
            "ai_model": "openai",
            "batch_size": 50
        }
        
        success, response = self.run_test(
            "Create Strategy Generation Job",
            "POST",
            "strategy/generate-job",
            200,
            data=job_data
        )
        
        if success and response:
            job_id = response.get('job_id')
            total_strategies = response.get('total_strategies')
            total_batches = response.get('total_batches')
            
            print(f"   Job ID: {job_id}")
            print(f"   Total Strategies: {total_strategies}")
            print(f"   Total Batches: {total_batches}")
            
            if job_id:
                print(f"   ✅ Job created successfully")
                return success, job_id
            else:
                print(f"   ❌ No job_id returned")
                return False, None
        
        return success, None

    def test_job_status_polling(self, job_id):
        """Test job status polling endpoint"""
        if not job_id:
            print("   ⚠️ No job_id provided for status polling")
            return False
            
        print(f"\n🔍 Testing Job Status Polling for {job_id}...")
        
        # Poll status multiple times to see progress
        max_polls = 10
        poll_count = 0
        
        while poll_count < max_polls:
            success, response = self.run_test(
                f"Job Status Poll #{poll_count + 1}",
                "GET",
                f"strategy/job-status/{job_id}",
                200
            )
            
            if success and response:
                stage = response.get('stage')
                percent = response.get('percent', 0)
                message = response.get('message', '')
                current_batch = response.get('current_batch', 0)
                total_batches = response.get('total_batches', 0)
                strategies_generated = response.get('strategies_generated', 0)
                
                print(f"   Stage: {stage}")
                print(f"   Progress: {percent}%")
                print(f"   Message: {message}")
                print(f"   Batch: {current_batch}/{total_batches}")
                print(f"   Strategies Generated: {strategies_generated}")
                
                if stage == "completed":
                    print(f"   ✅ Job completed successfully")
                    return True
                elif stage == "failed":
                    print(f"   ❌ Job failed")
                    return False
                
                # Wait before next poll
                time.sleep(2)
                poll_count += 1
            else:
                print(f"   ❌ Failed to get job status")
                return False
        
        print(f"   ⚠️ Job still running after {max_polls} polls")
        return True  # Not a failure, just still running

    def test_invalid_strategy_count(self):
        """Test validation with invalid strategy count"""
        print("\n🔍 Testing Invalid Strategy Count Validation...")
        
        job_data = {
            "symbol": "EURUSD",
            "timeframe": "1h",
            "strategy_count": 5000,  # Invalid - too high
            "strategy_type": "intraday",
            "risk_level": "medium",
            "execution_mode": "fast",
            "ai_model": "openai"
        }
        
        success, response = self.run_test(
            "Invalid Strategy Count (5000)",
            "POST",
            "strategy/generate-job",
            400,  # Should return 400 error
            data=job_data
        )
        
        if success:
            print(f"   ✅ Correctly rejected invalid strategy count")
        
        return success

    def test_nonexistent_symbol(self):
        """Test with non-existent symbol"""
        print("\n🔍 Testing Non-existent Symbol...")
        
        job_data = {
            "symbol": "FAKESYM",
            "timeframe": "1h",
            "strategy_count": 10,
            "strategy_type": "intraday",
            "risk_level": "medium",
            "execution_mode": "fast",
            "ai_model": "openai"
        }
        
        success, response = self.run_test(
            "Non-existent Symbol (FAKESYM)",
            "POST",
            "strategy/generate-job",
            400,  # Should return 400 error for insufficient data
            data=job_data
        )
        
        if success:
            print(f"   ✅ Correctly handled non-existent symbol")
        
        return success

    def test_job_result_endpoint(self, job_id):
        """Test job result retrieval endpoint"""
        if not job_id:
            print("   ⚠️ No job_id provided for result retrieval")
            return False
            
        print(f"\n🔍 Testing Job Result Retrieval for {job_id}...")
        
        success, response = self.run_test(
            "Get Job Result",
            "GET",
            f"strategy/job-result/{job_id}",
            200  # May return 400 if job not completed
        )
        
        if success and response:
            strategies = response.get('strategies', [])
            total_generated = response.get('total_generated', 0)
            passed_filters = response.get('passed_filters', 0)
            
            print(f"   Total Generated: {total_generated}")
            print(f"   Passed Filters: {passed_filters}")
            print(f"   Top Strategies: {len(strategies)}")
            
            if strategies:
                print(f"   ✅ Job results retrieved successfully")
                # Show first strategy details
                first_strategy = strategies[0]
                print(f"   Best Strategy: {first_strategy.get('name', 'Unknown')}")
                print(f"   Score: {first_strategy.get('score', 0)}")
            else:
                print(f"   ⚠️ No strategies in result")
        
        return success

def main():
    """Run all tests"""
    print("🚀 Starting Strategy Generation System API Tests")
    print("=" * 60)
    
    tester = StrategyGenerationAPITester()
    
    # Test basic connectivity first
    if not tester.test_basic_connectivity():
        print("❌ Basic connectivity failed, stopping tests")
        return 1
    
    # Import sample data for testing
    print("\n" + "=" * 40)
    print("DATA SETUP")
    print("=" * 40)
    
    data_imported = tester.import_sample_data()
    
    # =====================================================
    # HIGH PRIORITY TESTS (as per review request)
    # =====================================================
    
    print("\n" + "=" * 40)
    print("HIGH PRIORITY TESTS")
    print("=" * 40)
    
    # 1. Test Data Availability Check
    tester.test_data_availability_check()
    
    # 2. Test Strategy Job Creation (check if we have enough data)
    # Re-check data availability after import
    success, response = tester.run_test(
        "Check Data After Import",
        "GET",
        "marketdata/check-any-availability/EURUSD",
        200
    )
    
    has_enough_data = False
    if success and response:
        candle_count = response.get('candle_count', 0)
        has_enough_data = candle_count >= 100
        print(f"   Found {candle_count} candles, enough for testing: {has_enough_data}")
    
    if has_enough_data:
        job_success, job_id = tester.test_strategy_job_creation()
        
        # 3. Test Job Status Polling
        if job_success and job_id:
            tester.test_job_status_polling(job_id)
            
            # 4. Test Job Result Retrieval (if job completed)
            tester.test_job_result_endpoint(job_id)
    else:
        print("⚠️ Skipping strategy job tests - insufficient data (need 100+ candles)")
    
    # =====================================================
    # VALIDATION TESTS
    # =====================================================
    
    print("\n" + "=" * 40)
    print("VALIDATION TESTS")
    print("=" * 40)
    
    # Test invalid strategy count
    tester.test_invalid_strategy_count()
    
    # Test non-existent symbol
    tester.test_nonexistent_symbol()
    
    # =====================================================
    # LEGACY TESTS (Market Data)
    # =====================================================
    
    print("\n" + "=" * 40)
    print("LEGACY MARKET DATA TESTS")
    print("=" * 40)
    
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