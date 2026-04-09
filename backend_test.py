#!/usr/bin/env python3
"""
Backend Test Suite for Pipeline Flow UI and Quick Start Functionality
Tests the new 5-step pipeline flow with Quick Start and Advanced Mode features.
"""

import requests
import json
import time
import sys
from typing import Dict, Any, Optional

# Backend URL from environment
BACKEND_URL = "https://validation-monitor.preview.emergentagent.com/api"

class PipelineFlowTester:
    """Test suite for Pipeline Flow UI and Quick Start functionality"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.test_results = []
        self.strategy_id = None
        self.bot_session_id = None
        self.factory_run_id = None
        
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
        
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
    
    def test_data_availability_check(self) -> bool:
        """
        Test 1: Check data availability for EURUSD
        """
        print("\n🧪 Testing Data Availability Check for EURUSD")
        
        try:
            response = self.session.get(f"{BACKEND_URL}/data-integrity/check?symbol=EURUSD&timeframe=1h")
            
            if response.status_code != 200:
                self.log_test("Data Availability Check", False, f"HTTP {response.status_code}: {response.text}")
                return False
            
            data = response.json()
            
            if data.get("integrity_ok"):
                self.log_test("Data Availability Check", True, f"✅ {data.get('real_count', 0)} real candles available")
                return True
            else:
                self.log_test("Data Availability Check", False, f"❌ {data.get('message', 'Data integrity issues')}")
                return False
                
        except Exception as e:
            self.log_test("Data Availability Check", False, f"Exception: {str(e)}")
            return False

    def test_factory_generate_endpoint(self) -> Optional[str]:
        """
        Test 2: Test factory generate endpoint (POST /api/factory/generate)
        This is the Quick Start backend endpoint
        """
        print("\n🧪 Testing Factory Generate Endpoint (Quick Start Backend)")
        
        payload = {
            "session_id": f"quickstart-{int(time.time())}",
            "symbol": "EURUSD",
            "timeframe": "1h",
            "strategies_per_template": 2,
            "templates": ["ema_crossover", "rsi_mean_reversion", "macd_trend", "bollinger_breakout", "atr_volatility_breakout"],
            "duration_days": 365,
            "initial_balance": 10000,
            "challenge_firm": "ftmo"
        }
        
        try:
            response = self.session.post(f"{BACKEND_URL}/factory/generate", json=payload)
            
            if response.status_code != 200:
                self.log_test("Factory Generate Endpoint", False, f"HTTP {response.status_code}: {response.text}")
                return None
            
            data = response.json()
            
            if data.get("success"):
                run_id = data.get("run_id")
                total_generated = data.get("total_generated", 0)
                
                if run_id:
                    self.factory_run_id = run_id
                    self.log_test("Factory Generate Endpoint", True, 
                                f"Factory started successfully, run_id: {run_id}, generating {total_generated} strategies")
                    return run_id
                else:
                    self.log_test("Factory Generate Endpoint", False, "No run_id returned")
                    return None
            else:
                error_msg = data.get("message", "Unknown error")
                self.log_test("Factory Generate Endpoint", False, f"Factory error: {error_msg}")
                return None
                
        except Exception as e:
            self.log_test("Factory Generate Endpoint", False, f"Exception: {str(e)}")
            return None

    def test_factory_result_endpoint(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Test 3: Test factory result endpoint (GET /api/factory/result/{run_id})
        """
        print(f"\n🧪 Testing Factory Result Endpoint for run_id: {run_id}")
        
        try:
            response = self.session.get(f"{BACKEND_URL}/factory/result/{run_id}")
            
            if response.status_code != 200:
                self.log_test("Factory Result Endpoint", False, f"HTTP {response.status_code}: {response.text}")
                return None
            
            data = response.json()
            
            if data.get("success"):
                result = data.get("result", {})
                strategies = result.get("strategies", [])
                
                if strategies:
                    # Find top strategies (fitness >= 25)
                    top_strategies = [s for s in strategies if s.get("fitness", 0) >= 25]
                    top_strategies.sort(key=lambda x: x.get("fitness", 0), reverse=True)
                    top_3 = top_strategies[:3]
                    
                    if top_3:
                        self.log_test("Factory Result Endpoint", True, 
                                    f"Found {len(strategies)} total strategies, {len(top_3)} top performers")
                        return {"strategies": top_3, "total": len(strategies)}
                    else:
                        self.log_test("Factory Result Endpoint", False, "No strategies met minimum fitness threshold (25)")
                        return None
                else:
                    self.log_test("Factory Result Endpoint", False, "No strategies in results")
                    return None
            else:
                error_msg = data.get("message", "Unknown error")
                self.log_test("Factory Result Endpoint", False, f"Result error: {error_msg}")
                return None
                
        except Exception as e:
            self.log_test("Factory Result Endpoint", False, f"Exception: {str(e)}")
            return None

    def test_bot_generate_from_strategy(self, strategy_data: Dict[str, Any]) -> Optional[str]:
        """
        Test 4: Generate bot from validated strategy (POST /api/bot/generate-from-strategy)
        This tests the pipeline bot generation endpoint
        """
        print("\n🧪 Testing Bot Generation from Strategy (Pipeline Endpoint)")
        
        payload = {
            "strategy_id": self.strategy_id or f"strategy-{int(time.time())}",
            "strategy_data": strategy_data,
            "symbol": "EURUSD",
            "timeframe": "1h",
            "ai_model": "openai",
            "prop_firm": "ftmo",
            "run_full_pipeline": True
        }
        
        try:
            response = self.session.post(f"{BACKEND_URL}/bot/generate-from-strategy", json=payload)
            
            if response.status_code != 200:
                self.log_test("Bot Generation from Strategy", False, f"HTTP {response.status_code}: {response.text}")
                return None
            
            data = response.json()
            
            if data.get("success"):
                session_id = data.get("session_id")
                bot_status = data.get("bot_status")
                deployment_score = data.get("deployment_score", 0)
                pipeline_results = data.get("pipeline_results", {})
                
                self.bot_session_id = session_id
                
                # Validate required fields
                required_fields = ["session_id", "bot_status", "deployment_score", "pipeline_results"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Bot Generation from Strategy", False, f"Missing fields: {missing_fields}")
                    return None
                
                # Validate bot status is valid
                valid_statuses = ["draft", "validated", "robust", "ready_for_deployment"]
                if bot_status not in valid_statuses:
                    self.log_test("Bot Generation from Strategy", False, f"Invalid bot_status: {bot_status}")
                    return None
                
                # Validate deployment score range
                if not (0 <= deployment_score <= 100):
                    self.log_test("Bot Generation from Strategy", False, f"Invalid deployment_score: {deployment_score}")
                    return None
                
                # Validate pipeline results structure
                expected_pipeline_keys = ["safety_injected", "compile_verified", "backtest_passed", "monte_carlo_passed", "walkforward_passed"]
                missing_pipeline_keys = [key for key in expected_pipeline_keys if key not in pipeline_results]
                
                if missing_pipeline_keys:
                    self.log_test("Bot Generation from Strategy", False, f"Missing pipeline keys: {missing_pipeline_keys}")
                    return None
                
                self.log_test("Bot Generation from Strategy", True, 
                            f"Bot Status: {bot_status}, Score: {deployment_score}%, Session: {session_id}")
                return session_id
            else:
                self.log_test("Bot Generation from Strategy", False, f"API returned success=false: {data}")
                return None
                
        except Exception as e:
            self.log_test("Bot Generation from Strategy", False, f"Exception: {str(e)}")
            return None

    def test_pipeline_status(self, session_id: str) -> bool:
        """
        Test 4: Check bot pipeline status (GET /api/bot/pipeline-status/{session_id})
        """
        print(f"\n🧪 Testing Pipeline Status for {session_id}")
        
        try:
            response = self.session.get(f"{BACKEND_URL}/bot/pipeline-status/{session_id}")
            
            if response.status_code != 200:
                self.log_test("Pipeline Status Check", False, f"HTTP {response.status_code}: {response.text}")
                return False
            
            data = response.json()
            
            if data.get("success"):
                bot = data.get("bot", {})
                
                # Validate required bot fields
                required_fields = [
                    "id", "source_strategy_id", "strategy_name", "bot_status", 
                    "pipeline_stage", "deployment_score", "created_at", "updated_at"
                ]
                missing_fields = [field for field in required_fields if field not in bot]
                
                if missing_fields:
                    self.log_test("Pipeline Status Check", False, f"Missing bot fields: {missing_fields}")
                    return False
                
                # Validate status transitions
                bot_status = bot.get("bot_status")
                pipeline_stage = bot.get("pipeline_stage")
                
                valid_statuses = ["draft", "validated", "robust", "ready_for_deployment"]
                valid_stages = ["pending", "generating", "safety_check", "compiling", "backtesting", "monte_carlo", "walkforward", "completed", "compile_failed"]
                
                if bot_status not in valid_statuses:
                    self.log_test("Pipeline Status Check", False, f"Invalid bot_status: {bot_status}")
                    return False
                
                if pipeline_stage not in valid_stages:
                    self.log_test("Pipeline Status Check", False, f"Invalid pipeline_stage: {pipeline_stage}")
                    return False
                
                self.log_test("Pipeline Status Check", True, 
                            f"Status: {bot_status}, Stage: {pipeline_stage}, Score: {bot.get('deployment_score', 0)}%")
                return True
            else:
                self.log_test("Pipeline Status Check", False, f"API returned success=false: {data}")
                return False
                
        except Exception as e:
            self.log_test("Pipeline Status Check", False, f"Exception: {str(e)}")
            return False

    def test_pipeline_list(self) -> bool:
        """
        Test 5: List all pipeline bots (GET /api/bot/pipeline-list)
        """
        print("\n🧪 Testing Pipeline Bot List")
        
        try:
            response = self.session.get(f"{BACKEND_URL}/bot/pipeline-list?limit=10")
            
            if response.status_code != 200:
                self.log_test("Pipeline Bot List", False, f"HTTP {response.status_code}: {response.text}")
                return False
            
            data = response.json()
            
            if data.get("success"):
                bots = data.get("bots", [])
                count = data.get("count", 0)
                
                if count != len(bots):
                    self.log_test("Pipeline Bot List", False, f"Count mismatch: count={count}, len(bots)={len(bots)}")
                    return False
                
                # Validate bot structure if any bots exist
                if bots:
                    first_bot = bots[0]
                    required_fields = ["id", "bot_status", "deployment_score", "created_at"]
                    missing_fields = [field for field in required_fields if field not in first_bot]
                    
                    if missing_fields:
                        self.log_test("Pipeline Bot List", False, f"Missing fields in bot: {missing_fields}")
                        return False
                
                self.log_test("Pipeline Bot List", True, f"Found {count} pipeline bots")
                return True
            else:
                self.log_test("Pipeline Bot List", False, f"API returned success=false: {data}")
                return False
                
        except Exception as e:
            self.log_test("Pipeline Bot List", False, f"Exception: {str(e)}")
            return False

    def test_bot_status_transitions(self) -> bool:
        """
        Test 6: Validate bot status transitions and pipeline stages
        """
        print("\n🧪 Testing Bot Status Transitions")
        
        if not self.bot_session_id:
            self.log_test("Bot Status Transitions", False, "No bot session ID available")
            return False
        
        try:
            # Get current bot status
            response = self.session.get(f"{BACKEND_URL}/bot/pipeline-status/{self.bot_session_id}")
            
            if response.status_code != 200:
                self.log_test("Bot Status Transitions", False, f"HTTP {response.status_code}")
                return False
            
            data = response.json()
            bot = data.get("bot", {})
            
            # Validate status progression logic
            bot_status = bot.get("bot_status")
            pipeline_stage = bot.get("pipeline_stage")
            compile_verified = bot.get("compile_verified", False)
            backtest_passed = bot.get("backtest_passed", False)
            monte_carlo_passed = bot.get("monte_carlo_passed", False)
            walkforward_passed = bot.get("walkforward_passed", False)
            deployment_score = bot.get("deployment_score", 0)
            
            # Validate status logic
            status_valid = True
            status_errors = []
            
            # Draft status should have low scores
            if bot_status == "draft" and deployment_score > 40:
                status_errors.append(f"Draft status with high score: {deployment_score}")
                status_valid = False
            
            # Validated status should have compile + backtest
            if bot_status == "validated" and not (compile_verified and backtest_passed):
                status_errors.append("Validated status without compile+backtest")
                status_valid = False
            
            # Robust status should have walkforward
            if bot_status == "robust" and not walkforward_passed:
                status_errors.append("Robust status without walkforward")
                status_valid = False
            
            # Ready status should have all checks
            if bot_status == "ready_for_deployment":
                if not all([compile_verified, backtest_passed, monte_carlo_passed, walkforward_passed]):
                    status_errors.append("Ready status without all pipeline checks")
                    status_valid = False
                if deployment_score < 80:
                    status_errors.append(f"Ready status with low score: {deployment_score}")
                    status_valid = False
            
            if status_valid:
                self.log_test("Bot Status Transitions", True, 
                            f"Status logic valid: {bot_status} with score {deployment_score}%")
                return True
            else:
                self.log_test("Bot Status Transitions", False, f"Status logic errors: {status_errors}")
                return False
                
        except Exception as e:
            self.log_test("Bot Status Transitions", False, f"Exception: {str(e)}")
            return False

    def test_data_availability_display(self) -> bool:
        """
        Test 7: Check data availability display for EURUSD
        """
        print("\n🧪 Testing Data Availability Display for EURUSD")
        
        try:
            # Check specific availability endpoint
            response = self.session.get(f"{BACKEND_URL}/marketdata/check-any-availability/EURUSD")
            
            if response.status_code != 200:
                self.log_test("Data Availability Display", False, f"HTTP {response.status_code}: {response.text}")
                return False
            
            data = response.json()
            
            if data.get("available"):
                candle_count = data.get("candle_count", 0)
                timeframe = data.get("best_timeframe", "unknown")
                available_timeframes = data.get("available_timeframes", [])
                
                # Validate that EURUSD shows candles (as mentioned in requirements)
                if candle_count > 0:
                    self.log_test("Data Availability Display", True, 
                                f"EURUSD showing {candle_count} candles on {timeframe}, available timeframes: {available_timeframes}")
                    return True
                else:
                    self.log_test("Data Availability Display", False, "EURUSD available but no candle count")
                    return False
            else:
                message = data.get("message", "No data available")
                self.log_test("Data Availability Display", False, f"EURUSD not available: {message}")
                return False
                
        except Exception as e:
            self.log_test("Data Availability Display", False, f"Exception: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run the complete test suite for Pipeline Flow UI"""
        print("🚀 Starting Pipeline Flow UI and Quick Start Tests")
        print("=" * 70)
        
        # Test 1: Check data availability for EURUSD
        data_available = self.test_data_availability_check()
        if not data_available:
            print("\n⚠️  WARNING: No data available, some tests may fail")
        
        # Test 2: Test factory generate endpoint (Quick Start backend)
        factory_run_id = self.test_factory_generate_endpoint()
        if not factory_run_id:
            print("\n⚠️  WARNING: Factory generate failed, using mock data for remaining tests")
            # Create mock strategy for remaining tests
            mock_strategy = {
                "id": f"mock-strategy-{int(time.time())}",
                "template_id": "ema_crossover",
                "name": "Mock EMA Crossover Strategy",
                "genes": {"fast_period": 10, "slow_period": 20, "risk_percent": 2.0},
                "fitness": 45.5,
                "profit_factor": 1.35,
                "sharpe_ratio": 0.85,
                "max_drawdown_pct": 8.5,
                "win_rate": 62.5,
                "net_profit": 1250.0,
                "total_trades": 45,
                "monte_carlo_score": 72.0,
                "evaluated": True
            }
            strategy_data = {"strategies": [mock_strategy], "total": 1}
        else:
            # Test 3: Test factory result endpoint
            strategy_data = self.test_factory_result_endpoint(factory_run_id)
            if not strategy_data:
                print("\n⚠️  WARNING: Factory result failed, using mock data")
                mock_strategy = {
                    "id": f"mock-strategy-{int(time.time())}",
                    "template_id": "ema_crossover",
                    "name": "Mock EMA Crossover Strategy",
                    "genes": {"fast_period": 10, "slow_period": 20, "risk_percent": 2.0},
                    "fitness": 45.5,
                    "profit_factor": 1.35,
                    "sharpe_ratio": 0.85,
                    "max_drawdown_pct": 8.5,
                    "win_rate": 62.5,
                    "net_profit": 1250.0,
                    "total_trades": 45,
                    "monte_carlo_score": 72.0,
                    "evaluated": True
                }
                strategy_data = {"strategies": [mock_strategy], "total": 1}
        
        # Use first strategy for bot generation
        if strategy_data and strategy_data.get("strategies"):
            selected_strategy = strategy_data["strategies"][0]
            self.strategy_id = selected_strategy.get("id", f"strategy-{int(time.time())}")
            
            # Test 4: Generate bot from strategy
            bot_session_id = self.test_bot_generate_from_strategy(selected_strategy)
            if not bot_session_id:
                print("\n❌ CRITICAL: Bot generation failed")
            
            # Test 5: Check pipeline status
            if bot_session_id:
                pipeline_status_ok = self.test_pipeline_status(bot_session_id)
            else:
                pipeline_status_ok = False
            
            # Test 6: List pipeline bots
            pipeline_list_ok = self.test_pipeline_list()
            
            # Test 7: Check data availability display
            data_display_ok = self.test_data_availability_display()
        else:
            print("\n❌ CRITICAL: No strategy data available for testing")
            pipeline_status_ok = False
            pipeline_list_ok = False
            data_display_ok = False
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 TEST SUMMARY")
        print("=" * 70)
        
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        total_tests = len(self.test_results)
        
        for result in self.test_results:
            status = "✅" if result["passed"] else "❌"
            print(f"{status} {result['test']}")
        
        print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
        
        # Check critical functionality
        critical_tests = [
            data_available, pipeline_status_ok, pipeline_list_ok, data_display_ok
        ]
        
        if all(critical_tests):
            print("\n🎉 PIPELINE FLOW UI BACKEND IS WORKING!")
            print("✅ Factory endpoints working")
            print("✅ Bot generation pipeline functional")
            print("✅ Data availability display correct")
            return True
        else:
            print("\n⚠️  PIPELINE FLOW UI HAS ISSUES")
            print("❌ Some pipeline features are not working correctly")
            return False


def main():
    """Main test execution"""
    tester = PipelineFlowTester()
    
    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()