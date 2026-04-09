#!/usr/bin/env python3
"""
Test with more strategies to increase chances of getting some that pass filters
"""

import requests
import json
import time

BACKEND_URL = "https://codebase-review-86.preview.emergentagent.com/api"

def test_with_more_strategies():
    session = requests.Session()
    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    
    # Test with 50 strategies to increase chances of getting some that pass
    payload = {
        "symbol": "EURUSD",
        "timeframe": "1h",
        "strategy_count": 50,  # More strategies
        "strategy_type": "intraday",
        "risk_level": "high",  # Most lenient filtering
        "execution_mode": "fast",
        "ai_model": "openai",
        "batch_size": 50
    }
    
    try:
        print("🧪 Creating job with 50 strategies...")
        response = session.post(f"{BACKEND_URL}/strategy/generate-job", json=payload)
        
        if response.status_code != 200:
            print(f"❌ Job creation failed: {response.status_code}")
            return None
        
        job_data = response.json()
        job_id = job_data.get("job_id")
        print(f"✅ Job created: {job_id}")
        
        # Poll for completion
        print("🔄 Waiting for completion...")
        max_attempts = 120  # 10 minutes
        attempt = 0
        
        while attempt < max_attempts:
            response = session.get(f"{BACKEND_URL}/strategy/job-status/{job_id}")
            status_data = response.json()
            
            stage = status_data.get("stage", "unknown")
            percent = status_data.get("percent", 0)
            message = status_data.get("message", "")
            
            print(f"    {stage} ({percent}%) - {message}")
            
            if stage == "completed":
                print("✅ Job completed!")
                break
            elif stage == "failed":
                print(f"❌ Job failed: {status_data.get('error')}")
                return None
            
            time.sleep(5)
            attempt += 1
        
        if attempt >= max_attempts:
            print("❌ Timeout waiting for completion")
            return None
        
        # Get results
        print("📊 Getting results...")
        response = session.get(f"{BACKEND_URL}/strategy/job-result/{job_id}")
        result_data = response.json()
        
        print(f"\n=== RESULTS SUMMARY ===")
        print(f"Total Generated: {result_data.get('total_generated')}")
        print(f"Total Backtested: {result_data.get('total_backtested')}")
        print(f"Total Passed Filters: {result_data.get('total_passed_filters')}")
        print(f"Total Robust: {result_data.get('total_robust')}")
        print(f"Strategies Returned: {len(result_data.get('strategies', []))}")
        
        rejection = result_data.get('rejection_breakdown', {})
        print(f"\n=== REJECTION BREAKDOWN ===")
        for reason, count in rejection.items():
            print(f"{reason}: {count}")
        
        # Check if we have any strategies that passed
        strategies = result_data.get('strategies', [])
        if strategies:
            print(f"\n🎉 SUCCESS! {len(strategies)} strategies passed filters")
            
            # Check first strategy for walk-forward data
            first_strategy = strategies[0]
            walkforward_data = first_strategy.get('walkforward', {})
            
            if walkforward_data:
                print(f"\n=== WALK-FORWARD DATA SAMPLE ===")
                print(f"Strategy: {first_strategy.get('name')}")
                print(f"Training PF: {walkforward_data.get('training_pf')}")
                print(f"Validation PF: {walkforward_data.get('validation_pf')}")
                print(f"Stability Score: {walkforward_data.get('stability_score')}")
                print(f"Is Overfit: {walkforward_data.get('is_overfit')}")
                print(f"Robustness Grade: {walkforward_data.get('robustness_grade')}")
                print(f"Is Robust: {walkforward_data.get('is_robust')}")
                
                # Check walkforward_stats
                wf_stats = result_data.get('walkforward_stats', {})
                print(f"\n=== WALK-FORWARD STATS ===")
                print(f"Total Validated: {wf_stats.get('total_validated')}")
                print(f"Total Robust: {wf_stats.get('total_robust')}")
                print(f"Total Overfit: {wf_stats.get('total_overfit')}")
                print(f"Avg Stability Score: {wf_stats.get('avg_stability_score')}")
                print(f"Robustness Grades: {wf_stats.get('robustness_grades')}")
                
                return True
            else:
                print("❌ No walk-forward data found in strategies")
                return False
        else:
            print("❌ No strategies passed filters")
            return False
            
    except Exception as e:
        print(f"💥 Exception: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_with_more_strategies()
    if success:
        print("\n🎉 WALK-FORWARD VALIDATION SYSTEM IS WORKING!")
    else:
        print("\n⚠️ Need to investigate further...")