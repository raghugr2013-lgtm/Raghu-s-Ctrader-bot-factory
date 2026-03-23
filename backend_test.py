#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class cTraderBotFactoryTester:
    def __init__(self, base_url="https://raghu-trading-bot.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.session_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if not endpoint.startswith('http') else endpoint
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
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)

            print(f"   Status: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    print(f"   Response: {response.text[:200]}...")
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {json.dumps(error_data, indent=2)[:200]}...")
                except:
                    print(f"   Error: {response.text[:200]}...")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test /api/ root endpoint"""
        success, response = self.run_test(
            "Root API Endpoint",
            "GET",
            "",
            200
        )
        return success

    def test_full_pipeline_validation(self):
        """Test POST /api/validation/full-pipeline endpoint"""
        # Sample C# cBot code for testing
        sample_code = '''
using System;
using cAlgo.API;
using cAlgo.API.Indicators;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class TestBot : Robot
    {
        [Parameter("Fast MA", DefaultValue = 10)]
        public int FastMA { get; set; }

        [Parameter("Slow MA", DefaultValue = 20)]
        public int SlowMA { get; set; }

        private MovingAverage fastMA;
        private MovingAverage slowMA;

        protected override void OnStart()
        {
            fastMA = Indicators.MovingAverage(Bars.ClosePrices, FastMA, MovingAverageType.Simple);
            slowMA = Indicators.MovingAverage(Bars.ClosePrices, SlowMA, MovingAverageType.Simple);
        }

        protected override void OnBar()
        {
            if (fastMA.Result.LastValue > slowMA.Result.LastValue && 
                fastMA.Result.Last(1) <= slowMA.Result.Last(1))
            {
                ExecuteMarketOrder(TradeType.Buy, SymbolName, 1000, "Buy Signal");
            }
            else if (fastMA.Result.LastValue < slowMA.Result.LastValue && 
                     fastMA.Result.Last(1) >= slowMA.Result.Last(1))
            {
                ExecuteMarketOrder(TradeType.Sell, SymbolName, 1000, "Sell Signal");
            }
        }
    }
}
'''

        success, response = self.run_test(
            "Full Pipeline Validation",
            "POST",
            "validation/full-pipeline",
            200,
            data={"code": sample_code}
        )
        
        if success and response:
            # Check for expected pipeline stages
            expected_stages = ["generate", "fix", "compile", "compliance", "backtest", "monte_carlo", "walk_forward"]
            stages_found = []
            
            if 'stages' in response:
                stages_found = list(response['stages'].keys()) if isinstance(response['stages'], dict) else response['stages']
            
            print(f"   Pipeline stages found: {stages_found}")
            
            # Check for final score and decision
            if 'final_score' in response:
                print(f"   Final score: {response['final_score']}")
            if 'grade' in response:
                print(f"   Grade: {response['grade']}")
            if 'decision' in response:
                print(f"   Decision: {response['decision']}")
                
            # Validate expected stages are present
            missing_stages = [stage for stage in expected_stages if stage not in str(response)]
            if missing_stages:
                print(f"   ⚠️  Missing stages: {missing_stages}")
            else:
                print(f"   ✅ All expected pipeline stages present")
                
        return success

    def test_bot_generation(self):
        """Test basic bot generation endpoint"""
        success, response = self.run_test(
            "Bot Generation",
            "POST",
            "bot/generate",
            200,
            data={
                "strategy_prompt": "Simple moving average crossover strategy",
                "ai_model": "openai",
                "prop_firm": "none"
            }
        )
        
        if success and response:
            if 'session_id' in response:
                self.session_id = response['session_id']
                print(f"   Session ID: {self.session_id}")
            if 'code' in response:
                print(f"   Generated code length: {len(response['code'])} characters")
                
        return success

    def test_code_validation(self):
        """Test code validation endpoint"""
        sample_code = '''
using System;
using cAlgo.API;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC)]
    public class SimpleBot : Robot
    {
        protected override void OnStart()
        {
            Print("Bot started");
        }
    }
}
'''
        
        success, response = self.run_test(
            "Code Validation",
            "POST",
            "code/validate",
            200,
            data={
                "code": sample_code,
                "prop_firm": "none"
            }
        )
        return success

    def test_database_connection(self):
        """Test database debug endpoint"""
        success, response = self.run_test(
            "Database Connection",
            "GET",
            "debug/db",
            200
        )
        
        if success and response:
            print(f"   Database: {response.get('db_name', 'Unknown')}")
            print(f"   Bots count: {response.get('bots_count', 0)}")
            print(f"   Trades count: {response.get('trades_count', 0)}")
            
        return success

    def test_compliance_profiles(self):
        """Test compliance profiles endpoint"""
        success, response = self.run_test(
            "Compliance Profiles",
            "GET",
            "compliance/profiles",
            200
        )
        
        if success and response:
            profiles = response.get('profiles', [])
            print(f"   Available profiles: {len(profiles)}")
            for profile in profiles[:3]:  # Show first 3
                print(f"     - {profile.get('name', 'Unknown')}")
                
        return success

    def test_symbols_supported(self):
        """Test GET /api/symbols/supported endpoint"""
        success, response = self.run_test(
            "Symbols Supported",
            "GET",
            "symbols/supported",
            200
        )
        
        if success and response:
            symbols = response.get('symbols', [])
            print(f"   Symbols found: {len(symbols)}")
            
            # Check for expected symbols
            expected_symbols = ["EURUSD", "XAUUSD", "US100", "ETHUSD"]
            found_symbols = [s.get('symbol') for s in symbols]
            
            for expected in expected_symbols:
                if expected in found_symbols:
                    print(f"   ✅ {expected} found")
                else:
                    print(f"   ❌ {expected} missing")
                    success = False
            
            # Check symbol configuration fields
            if symbols:
                first_symbol = symbols[0]
                required_fields = ['symbol', 'type', 'pip_value', 'lot_size', 'spread', 
                                 'default_sl_pips', 'default_tp_pips', 'volatility_multiplier']
                for field in required_fields:
                    if field in first_symbol:
                        print(f"   ✅ Field '{field}' present")
                    else:
                        print(f"   ❌ Field '{field}' missing")
                        success = False
                        
        return success

    def test_symbol_config(self):
        """Test GET /api/symbols/{symbol}/config for each symbol"""
        symbols = ["EURUSD", "XAUUSD", "US100", "ETHUSD"]
        all_success = True
        
        for symbol in symbols:
            success, response = self.run_test(
                f"Symbol Config - {symbol}",
                "GET",
                f"symbols/{symbol}/config",
                200
            )
            
            if success and response:
                config = response.get('config', {})
                required_fields = ['type', 'pip_value', 'lot_size', 'spread', 'min_lot', 'max_lot',
                                 'pip_digits', 'value_per_pip_per_lot', 'default_stop_loss_pips',
                                 'default_take_profit_pips', 'volatility_multiplier', 'dukascopy_symbol']
                
                missing_fields = [field for field in required_fields if field not in config]
                if missing_fields:
                    print(f"   ❌ Missing fields for {symbol}: {missing_fields}")
                    all_success = False
                else:
                    print(f"   ✅ All required fields present for {symbol}")
            else:
                all_success = False
                
        return all_success

    def test_pro_validation_eurusd(self):
        """Test POST /api/validation/pro with EURUSD"""
        success, response = self.run_test(
            "PRO Validation - EURUSD",
            "POST",
            "validation/pro",
            200,
            data={
                "symbol": "EURUSD",
                "timeframe": "M15",
                "backtest_days": 7,
                "data_source": "api"
            }
        )
        
        if success and response:
            # Check required response fields
            required_fields = ['success', 'mode', 'data_source', 'symbol', 'stages', 
                             'final_score', 'grade', 'decision']
            
            for field in required_fields:
                if field in response:
                    print(f"   ✅ Field '{field}' present: {response.get(field)}")
                else:
                    print(f"   ❌ Field '{field}' missing")
                    success = False
            
            # Check stages array
            stages = response.get('stages', [])
            if isinstance(stages, list) and len(stages) > 0:
                print(f"   ✅ Stages array has {len(stages)} stages")
                for stage in stages[:3]:  # Show first 3 stages
                    stage_name = stage.get('stage', 'Unknown')
                    stage_success = stage.get('success', False)
                    print(f"     - {stage_name}: {'✅' if stage_success else '❌'}")
            else:
                print(f"   ❌ Stages array is empty or invalid")
                success = False
                
        return success

    def test_pro_validation_xauusd(self):
        """Test POST /api/validation/pro with XAUUSD"""
        success, response = self.run_test(
            "PRO Validation - XAUUSD",
            "POST",
            "validation/pro",
            200,
            data={
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "backtest_days": 7,
                "data_source": "api"
            }
        )
        
        if success and response:
            # Check that symbol is correctly set
            if response.get('symbol') == 'XAUUSD':
                print(f"   ✅ Symbol correctly set to XAUUSD")
            else:
                print(f"   ❌ Symbol mismatch: expected XAUUSD, got {response.get('symbol')}")
                success = False
                
            # Check for final score and grade
            final_score = response.get('final_score')
            grade = response.get('grade')
            if final_score is not None:
                print(f"   ✅ Final score: {final_score}")
            if grade:
                print(f"   ✅ Grade: {grade}")
                
        return success

    def test_data_status_endpoints(self):
        """Test GET /api/validation/pro/data-status/{symbol} for each symbol"""
        symbols = ["EURUSD", "XAUUSD", "US100", "ETHUSD"]
        all_success = True
        
        for symbol in symbols:
            success, response = self.run_test(
                f"Data Status - {symbol}",
                "GET",
                f"validation/pro/data-status/{symbol}",
                200
            )
            
            if success and response:
                # Check required fields
                required_fields = ['success', 'symbol', 'dukascopy_symbol', 'cache_info', 'supported_timeframes']
                
                for field in required_fields:
                    if field in response:
                        print(f"   ✅ Field '{field}' present for {symbol}")
                    else:
                        print(f"   ❌ Field '{field}' missing for {symbol}")
                        all_success = False
                
                # Check supported timeframes
                timeframes = response.get('supported_timeframes', [])
                expected_timeframes = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
                if set(expected_timeframes).issubset(set(timeframes)):
                    print(f"   ✅ All expected timeframes supported for {symbol}")
                else:
                    print(f"   ❌ Missing timeframes for {symbol}")
                    all_success = False
            else:
                all_success = False
                
        return all_success

    def test_existing_endpoints_still_work(self):
        """Test that existing endpoints still work after PRO validation implementation"""
        print("\n🔍 Testing existing endpoints compatibility...")
        
        # Test full-pipeline validation
        success1, _ = self.run_test(
            "Existing Full Pipeline",
            "POST",
            "validation/full-pipeline",
            200,
            data={"code": "using System; using cAlgo.API; namespace cAlgo.Robots { [Robot] public class TestBot : Robot { protected override void OnStart() { Print(\"Test\"); } } }"}
        )
        
        # Test bot generation
        success2, _ = self.run_test(
            "Existing Bot Generation",
            "POST",
            "bot/generate",
            200,
            data={
                "strategy_prompt": "Simple test strategy",
                "ai_model": "openai",
                "prop_firm": "none"
            }
        )
        
        return success1 and success2

def main():
    print("🚀 Starting cTrader Bot Factory PRO Validation API Tests")
    print("=" * 60)
    
    tester = cTraderBotFactoryTester()
    
    # Test sequence - PRO Validation Features
    tests = [
        ("Root API Endpoint", tester.test_root_endpoint),
        ("Database Connection", tester.test_database_connection),
        ("Symbols Supported", tester.test_symbols_supported),
        ("Symbol Configuration", tester.test_symbol_config),
        ("PRO Validation - EURUSD", tester.test_pro_validation_eurusd),
        ("PRO Validation - XAUUSD", tester.test_pro_validation_xauusd),
        ("Data Status Endpoints", tester.test_data_status_endpoints),
        ("Existing Endpoints Compatibility", tester.test_existing_endpoints_still_work),
        ("Compliance Profiles", tester.test_compliance_profiles),
        ("Code Validation", tester.test_code_validation),
    ]
    
    print(f"\n📋 Running {len(tests)} test categories for PRO Validation + Multi-Symbol Support...")
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*20} {test_name} {'='*20}")
            test_func()
        except Exception as e:
            print(f"❌ Test category '{test_name}' failed with exception: {str(e)}")
    
    # Print final results
    print(f"\n{'='*60}")
    print(f"📊 PRO Validation Test Results Summary")
    print(f"{'='*60}")
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    print(f"Tests failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run*100):.1f}%" if tester.tests_run > 0 else "No tests run")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All PRO Validation tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())