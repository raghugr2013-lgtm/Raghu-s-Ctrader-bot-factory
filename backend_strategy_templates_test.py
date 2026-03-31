#!/usr/bin/env python3
"""
Backend API Testing for Strategy Templates Functionality
Tests all strategy template endpoints and backtest integration
"""

import requests
import sys
import json
from datetime import datetime
import time

class StrategyTemplatesAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, timeout=120):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)

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

    def test_get_strategy_templates(self):
        """Test GET /api/strategy/templates - should return 4 templates"""
        success, response = self.run_test(
            "GET Strategy Templates",
            "GET",
            "strategy/templates",
            200
        )
        
        if success and response.get('success'):
            templates = response.get('templates', [])
            print(f"   Templates found: {len(templates)}")
            
            # Check if we have exactly 4 templates
            if len(templates) == 4:
                print("   ✅ Correct number of templates (4)")
            else:
                print(f"   ⚠️ Expected 4 templates, got {len(templates)}")
            
            # Check template IDs
            expected_ids = ['mean_reversion', 'trend_following', 'breakout', 'hybrid']
            found_ids = [t.get('id') for t in templates]
            
            for expected_id in expected_ids:
                if expected_id in found_ids:
                    template = next(t for t in templates if t.get('id') == expected_id)
                    print(f"   ✅ {template.get('name', expected_id)}: {template.get('description', 'No description')}")
                else:
                    print(f"   ❌ Missing template: {expected_id}")
            
            return templates
        return []

    def test_mean_reversion_backtest(self):
        """Test Mean Reversion template backtest"""
        return self.test_template_backtest(
            "mean_reversion", 
            "Mean Reversion Template Backtest",
            expected_features=["Bollinger Bands", "RSI", "oversold", "overbought"]
        )

    def test_trend_following_backtest(self):
        """Test Trend Following template backtest"""
        return self.test_template_backtest(
            "trend_following", 
            "Trend Following Template Backtest",
            expected_features=["EMA", "pullback", "trend"]
        )

    def test_breakout_backtest(self):
        """Test Breakout template backtest"""
        return self.test_template_backtest(
            "breakout", 
            "Breakout Template Backtest",
            expected_features=["high", "low", "volume", "ATR"]
        )

    def test_hybrid_backtest(self):
        """Test Hybrid template backtest"""
        return self.test_template_backtest(
            "hybrid", 
            "Hybrid Template Backtest",
            expected_features=["ADX", "auto-switch", "regime"]
        )

    def test_template_backtest(self, template_id, test_name, expected_features=None):
        """Test a specific template backtest"""
        success, response = self.run_test(
            test_name,
            "POST",
            f"strategy/templates/{template_id}/backtest",
            200,
            data={
                "template_id": template_id,
                "symbol": "XAUUSD",  # Using XAUUSD as it typically has more data
                "timeframe": "1h",
                "backtest_days": 365,
                "initial_balance": 10000.0
            },
            timeout=120  # Longer timeout for backtest
        )
        
        if success and response.get('success'):
            # Check template info
            template = response.get('template', {})
            print(f"   Template: {template.get('name', 'Unknown')}")
            
            # Check backtest info
            backtest = response.get('backtest', {})
            print(f"   Candles used: {backtest.get('candles_used', 0):,}")
            print(f"   Date range: {backtest.get('date_range', 'Unknown')}")
            print(f"   Data source: {backtest.get('data_source', 'Unknown')}")
            
            # Check metrics
            metrics = response.get('metrics', {})
            print(f"   Total trades: {metrics.get('total_trades', 0)}")
            print(f"   Win rate: {metrics.get('win_rate', 0):.1f}%")
            print(f"   Profit factor: {metrics.get('profit_factor', 0):.2f}")
            print(f"   Max drawdown: {metrics.get('max_drawdown_percent', 0):.2f}%")
            
            # Check score
            score = response.get('score', {})
            print(f"   Strategy score: {score.get('total_score', 0):.1f}")
            print(f"   Grade: {score.get('grade', 'N/A')}")
            
            # Check equity curve summary
            equity_summary = response.get('equity_curve_summary', {})
            print(f"   Start equity: ${equity_summary.get('start_equity', 0):.2f}")
            print(f"   End equity: ${equity_summary.get('end_equity', 0):.2f}")
            print(f"   Peak equity: ${equity_summary.get('peak_equity', 0):.2f}")
            
            # Validate required fields
            required_fields = ['total_trades', 'win_rate', 'profit_factor', 'max_drawdown_percent']
            missing_fields = []
            for field in required_fields:
                if field not in metrics:
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"   ⚠️ Missing required fields: {missing_fields}")
            else:
                print(f"   ✅ All required metrics present")
            
            # Check if trades were generated
            if metrics.get('total_trades', 0) > 0:
                print(f"   ✅ Strategy generated trades")
            else:
                print(f"   ⚠️ No trades generated")
            
            return {
                'template_id': template_id,
                'metrics': metrics,
                'score': score,
                'backtest': backtest,
                'trades_generated': metrics.get('total_trades', 0) > 0
            }
        
        return None

    def test_api_root(self):
        """Test API root endpoint"""
        success, response = self.run_test(
            "API Root",
            "GET",
            "",
            200
        )
        
        if success:
            print(f"   Response: {response}")
            return True
        return False

def main():
    print("🚀 Starting Strategy Templates Backend API Tests")
    print("=" * 70)
    
    tester = StrategyTemplatesAPITester()
    
    # Test 0: API Root
    print("\n🔗 PHASE 0: API Connectivity")
    tester.test_api_root()
    
    # Test 1: Get Strategy Templates
    print("\n📋 PHASE 1: Strategy Templates List")
    templates = tester.test_get_strategy_templates()
    
    # Test 2-5: Individual Template Backtests
    print("\n⚡ PHASE 2: Template Backtests")
    
    backtest_results = []
    
    # Mean Reversion
    print("\n📉 Testing Mean Reversion Strategy")
    result = tester.test_mean_reversion_backtest()
    if result:
        backtest_results.append(result)
    
    # Trend Following  
    print("\n📈 Testing Trend Following Strategy")
    result = tester.test_trend_following_backtest()
    if result:
        backtest_results.append(result)
    
    # Breakout
    print("\n⚡ Testing Breakout Strategy")
    result = tester.test_breakout_backtest()
    if result:
        backtest_results.append(result)
    
    # Hybrid
    print("\n🔄 Testing Hybrid Strategy")
    result = tester.test_hybrid_backtest()
    if result:
        backtest_results.append(result)
    
    # Analysis of Results
    print("\n" + "=" * 70)
    print("📊 BACKTEST RESULTS ANALYSIS")
    
    if backtest_results:
        print(f"\nSuccessful backtests: {len(backtest_results)}/4")
        
        for result in backtest_results:
            template_id = result['template_id']
            metrics = result['metrics']
            score = result['score']
            
            print(f"\n{template_id.upper().replace('_', ' ')}:")
            print(f"  Trades: {metrics.get('total_trades', 0)}")
            print(f"  Win Rate: {metrics.get('win_rate', 0):.1f}%")
            print(f"  Profit Factor: {metrics.get('profit_factor', 0):.2f}")
            print(f"  Max DD: {metrics.get('max_drawdown_percent', 0):.2f}%")
            print(f"  Score: {score.get('total_score', 0):.1f} (Grade: {score.get('grade', 'N/A')})")
            
            # Highlight exceptional results
            if metrics.get('profit_factor', 0) > 10:
                print(f"  🌟 EXCEPTIONAL: Profit Factor > 10!")
            if metrics.get('win_rate', 0) > 70:
                print(f"  🎯 HIGH WIN RATE: {metrics.get('win_rate', 0):.1f}%")
            if metrics.get('max_drawdown_percent', 0) < 1:
                print(f"  🛡️ LOW DRAWDOWN: {metrics.get('max_drawdown_percent', 0):.2f}%")
    
    # Print final results
    print("\n" + "=" * 70)
    print(f"📊 FINAL TEST RESULTS")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if tester.failed_tests:
        print(f"\n❌ FAILED TESTS ({len(tester.failed_tests)}):")
        for i, failure in enumerate(tester.failed_tests, 1):
            print(f"{i}. {failure['test']}")
            print(f"   Expected: {failure['expected']}, Got: {failure['actual']}")
            print(f"   Error: {failure['error']}")
    else:
        print("\n✅ ALL TESTS PASSED!")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())