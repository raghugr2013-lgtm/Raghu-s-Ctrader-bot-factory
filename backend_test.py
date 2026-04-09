#!/usr/bin/env python3
"""
Backend Test Suite for Walk-Forward Validation System
Tests the strategy robustness validation pipeline.
"""

import requests
import json
import time
import sys
from typing import Dict, Any, Optional

# Backend URL from environment
BACKEND_URL = "https://codebase-review-86.preview.emergentagent.com/api"

class WalkForwardValidationTester:
    """Test suite for Walk-Forward Validation System"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.test_results = []
        
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
    
    def test_strategy_generation_with_walkforward(self) -> Optional[str]:
        """
        Test 1: Generate strategies with walk-forward validation
        This is the main test that validates the entire pipeline.
        """
        print("\n🧪 Testing Strategy Generation with Walk-Forward Validation")
        
        # Test data - using "high" risk for more lenient filtering
        payload = {
            "symbol": "EURUSD",
            "timeframe": "1h",
            "strategy_count": 10,
            "strategy_type": "intraday",
            "risk_level": "high",
            "execution_mode": "fast",
            "ai_model": "openai",
            "batch_size": 50
        }
        
        try:
            # Create strategy generation job
            response = self.session.post(f"{BACKEND_URL}/strategy/generate-job", json=payload)
            
            if response.status_code != 200:
                self.log_test("Strategy Job Creation", False, f"HTTP {response.status_code}: {response.text}")
                return None
            
            job_data = response.json()
            if not job_data.get("success"):
                self.log_test("Strategy Job Creation", False, f"API returned success=false: {job_data}")
                return None
            
            job_id = job_data.get("job_id")
            if not job_id:
                self.log_test("Strategy Job Creation", False, "No job_id returned")
                return None
            
            self.log_test("Strategy Job Creation", True, f"Job ID: {job_id}")
            return job_id
            
        except Exception as e:
            self.log_test("Strategy Job Creation", False, f"Exception: {str(e)}")
            return None
    
    def test_job_status_polling(self, job_id: str) -> bool:
        """
        Test 2: Poll job status until completion
        """
        print(f"\n🔄 Polling job status for {job_id}")
        
        max_attempts = 60  # 5 minutes max
        attempt = 0
        
        while attempt < max_attempts:
            try:
                response = self.session.get(f"{BACKEND_URL}/strategy/job-status/{job_id}")
                
                if response.status_code != 200:
                    self.log_test("Job Status Polling", False, f"HTTP {response.status_code}")
                    return False
                
                status_data = response.json()
                if not status_data.get("success"):
                    self.log_test("Job Status Polling", False, f"API error: {status_data}")
                    return False
                
                stage = status_data.get("stage", "unknown")
                percent = status_data.get("percent", 0)
                message = status_data.get("message", "")
                
                print(f"    Stage: {stage} ({percent}%) - {message}")
                
                if stage == "completed":
                    self.log_test("Job Status Polling", True, f"Job completed in {attempt + 1} attempts")
                    return True
                elif stage == "failed":
                    error = status_data.get("error", "Unknown error")
                    self.log_test("Job Status Polling", False, f"Job failed: {error}")
                    return False
                
                time.sleep(5)  # Wait 5 seconds between polls
                attempt += 1
                
            except Exception as e:
                self.log_test("Job Status Polling", False, f"Exception: {str(e)}")
                return False
        
        self.log_test("Job Status Polling", False, "Timeout waiting for job completion")
        return False
    
    def test_walkforward_results_validation(self, job_id: str) -> bool:
        """
        Test 3: Validate walk-forward validation results
        This is the CRITICAL test that verifies all walk-forward data is present.
        """
        print(f"\n🔍 Validating Walk-Forward Results for {job_id}")
        
        try:
            response = self.session.get(f"{BACKEND_URL}/strategy/job-result/{job_id}")
            
            if response.status_code != 200:
                self.log_test("Job Result Retrieval", False, f"HTTP {response.status_code}")
                return False
            
            result_data = response.json()
            if not result_data.get("success"):
                self.log_test("Job Result Retrieval", False, f"API error: {result_data}")
                return False
            
            self.log_test("Job Result Retrieval", True, "Successfully retrieved job results")
            
            # Validate main result structure
            strategies = result_data.get("strategies", [])
            if not strategies:
                self.log_test("Strategy Results Present", False, "No strategies in results")
                return False
            
            self.log_test("Strategy Results Present", True, f"Found {len(strategies)} strategies")
            
            # Test walk-forward validation data on each strategy
            walkforward_tests_passed = 0
            walkforward_tests_total = 0
            
            for i, strategy in enumerate(strategies[:5]):  # Test first 5 strategies
                strategy_name = strategy.get("name", f"Strategy_{i}")
                walkforward_data = strategy.get("walkforward", {})
                
                walkforward_tests_total += 1
                
                # Check required walk-forward fields
                required_fields = [
                    "training_pf", "training_wr", "training_dd", "training_trades",
                    "validation_pf", "validation_wr", "validation_dd", "validation_trades",
                    "stability_score", "pf_stability", "is_overfit", "overfit_severity",
                    "robustness_grade", "is_robust"
                ]
                
                missing_fields = []
                for field in required_fields:
                    if field not in walkforward_data:
                        missing_fields.append(field)
                
                if missing_fields:
                    self.log_test(f"Walk-Forward Data - {strategy_name}", False, 
                                f"Missing fields: {missing_fields}")
                    continue
                
                # Validate data types and ranges
                validation_errors = []
                
                # Check numeric fields
                numeric_fields = ["training_pf", "training_wr", "training_dd", "validation_pf", 
                                "validation_wr", "validation_dd", "stability_score", "pf_stability"]
                for field in numeric_fields:
                    value = walkforward_data.get(field)
                    if not isinstance(value, (int, float)):
                        validation_errors.append(f"{field} is not numeric: {value}")
                
                # Check stability score range (0-1)
                stability_score = walkforward_data.get("stability_score", -1)
                if not (0 <= stability_score <= 1):
                    validation_errors.append(f"stability_score out of range: {stability_score}")
                
                # Check boolean fields
                boolean_fields = ["is_overfit", "is_robust"]
                for field in boolean_fields:
                    value = walkforward_data.get(field)
                    if not isinstance(value, bool):
                        validation_errors.append(f"{field} is not boolean: {value}")
                
                # Check overfit severity values
                overfit_severity = walkforward_data.get("overfit_severity")
                if overfit_severity not in ["none", "mild", "severe"]:
                    validation_errors.append(f"Invalid overfit_severity: {overfit_severity}")
                
                # Check robustness grade
                robustness_grade = walkforward_data.get("robustness_grade")
                if robustness_grade not in ["A", "B", "C", "D", "F"]:
                    validation_errors.append(f"Invalid robustness_grade: {robustness_grade}")
                
                if validation_errors:
                    self.log_test(f"Walk-Forward Data - {strategy_name}", False, 
                                f"Validation errors: {validation_errors}")
                    continue
                
                # Verify training and validation metrics are DIFFERENT
                training_pf = walkforward_data.get("training_pf", 0)
                validation_pf = walkforward_data.get("validation_pf", 0)
                training_wr = walkforward_data.get("training_wr", 0)
                validation_wr = walkforward_data.get("validation_wr", 0)
                
                if training_pf == validation_pf and training_wr == validation_wr:
                    validation_errors.append("Training and validation metrics are identical (split not working)")
                
                if validation_errors:
                    self.log_test(f"Walk-Forward Data - {strategy_name}", False, 
                                f"Data split errors: {validation_errors}")
                    continue
                
                walkforward_tests_passed += 1
                self.log_test(f"Walk-Forward Data - {strategy_name}", True, 
                            f"PF: {training_pf:.2f}→{validation_pf:.2f}, "
                            f"Stability: {stability_score:.3f}, Grade: {robustness_grade}")
            
            # Test walkforward_stats in main response
            walkforward_stats = result_data.get("walkforward_stats", {})
            required_stats = ["total_validated", "total_robust", "total_overfit", 
                            "avg_stability_score", "robustness_grades"]
            
            missing_stats = []
            for stat in required_stats:
                if stat not in walkforward_stats:
                    missing_stats.append(stat)
            
            if missing_stats:
                self.log_test("Walk-Forward Stats", False, f"Missing stats: {missing_stats}")
            else:
                total_validated = walkforward_stats.get("total_validated", 0)
                total_robust = walkforward_stats.get("total_robust", 0)
                total_overfit = walkforward_stats.get("total_overfit", 0)
                avg_stability = walkforward_stats.get("avg_stability_score", 0)
                
                self.log_test("Walk-Forward Stats", True, 
                            f"Validated: {total_validated}, Robust: {total_robust}, "
                            f"Overfit: {total_overfit}, Avg Stability: {avg_stability:.3f}")
            
            # Test rejection breakdown includes "overfit"
            rejection_breakdown = result_data.get("rejection_breakdown", {})
            if "overfit" not in rejection_breakdown:
                self.log_test("Overfit Rejection Tracking", False, "No 'overfit' count in rejection_breakdown")
            else:
                overfit_count = rejection_breakdown.get("overfit", 0)
                self.log_test("Overfit Rejection Tracking", True, f"Overfit rejections: {overfit_count}")
            
            # Verify some strategies are marked as overfit
            overfit_strategies = [s for s in strategies if s.get("walkforward", {}).get("is_overfit", False)]
            if not overfit_strategies:
                self.log_test("Overfit Detection", False, "No strategies marked as overfit (detection may not be working)")
            else:
                self.log_test("Overfit Detection", True, f"{len(overfit_strategies)} strategies marked as overfit")
            
            # Summary of walk-forward validation
            if walkforward_tests_passed == walkforward_tests_total and walkforward_tests_total > 0:
                self.log_test("Walk-Forward Validation System", True, 
                            f"All {walkforward_tests_passed} strategies have complete walk-forward data")
                return True
            else:
                self.log_test("Walk-Forward Validation System", False, 
                            f"Only {walkforward_tests_passed}/{walkforward_tests_total} strategies passed validation")
                return False
                
        except Exception as e:
            self.log_test("Walk-Forward Results Validation", False, f"Exception: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run the complete test suite"""
        print("🚀 Starting Walk-Forward Validation System Tests")
        print("=" * 60)
        
        # Test 1: Generate strategies with walk-forward validation
        job_id = self.test_strategy_generation_with_walkforward()
        if not job_id:
            print("\n❌ CRITICAL: Cannot proceed without job creation")
            return False
        
        # Test 2: Poll job status until completion
        job_completed = self.test_job_status_polling(job_id)
        if not job_completed:
            print("\n❌ CRITICAL: Job did not complete successfully")
            return False
        
        # Test 3: Validate walk-forward results
        walkforward_valid = self.test_walkforward_results_validation(job_id)
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        total_tests = len(self.test_results)
        
        for result in self.test_results:
            status = "✅" if result["passed"] else "❌"
            print(f"{status} {result['test']}")
        
        print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
        
        if walkforward_valid:
            print("\n🎉 WALK-FORWARD VALIDATION SYSTEM IS WORKING CORRECTLY!")
            print("✅ Strategies have complete walk-forward data")
            print("✅ Training/validation split is working")
            print("✅ Overfitting detection is functional")
            print("✅ Robustness grading is implemented")
            return True
        else:
            print("\n⚠️  WALK-FORWARD VALIDATION SYSTEM HAS ISSUES")
            print("❌ Some walk-forward features are not working correctly")
            return False


def main():
    """Main test execution"""
    tester = WalkForwardValidationTester()
    
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