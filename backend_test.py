#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class cTraderBotFactoryTester:
    def __init__(self, base_url="https://trading-engine-hub-1.preview.emergentagent.com"):
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

def main():
    print("🚀 Starting cTrader Bot Factory API Tests")
    print("=" * 50)
    
    tester = cTraderBotFactoryTester()
    
    # Test sequence
    tests = [
        ("Root API Endpoint", tester.test_root_endpoint),
        ("Database Connection", tester.test_database_connection),
        ("Compliance Profiles", tester.test_compliance_profiles),
        ("Code Validation", tester.test_code_validation),
        ("Bot Generation", tester.test_bot_generation),
        ("Full Pipeline Validation", tester.test_full_pipeline_validation),
    ]
    
    print(f"\n📋 Running {len(tests)} test categories...")
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*20} {test_name} {'='*20}")
            test_func()
        except Exception as e:
            print(f"❌ Test category '{test_name}' failed with exception: {str(e)}")
    
    # Print final results
    print(f"\n{'='*50}")
    print(f"📊 Test Results Summary")
    print(f"{'='*50}")
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    print(f"Tests failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run*100):.1f}%" if tester.tests_run > 0 else "No tests run")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())