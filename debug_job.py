#!/usr/bin/env python3
"""
Debug script to examine job results
"""

import requests
import json

BACKEND_URL = "https://codebase-review-86.preview.emergentagent.com/api"

def debug_job_result():
    # Use the job ID from the previous test
    job_id = "c21f18af-821d-4929-846d-e5912b804a2a"
    
    session = requests.Session()
    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    
    try:
        response = session.get(f"{BACKEND_URL}/strategy/job-result/{job_id}")
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result_data = response.json()
            print("\n=== FULL RESPONSE ===")
            print(json.dumps(result_data, indent=2))
            
            # Check specific fields
            print(f"\n=== KEY FIELDS ===")
            print(f"Success: {result_data.get('success')}")
            print(f"Total Generated: {result_data.get('total_generated', 'N/A')}")
            print(f"Total Backtested: {result_data.get('total_backtested', 'N/A')}")
            print(f"Total Passed Filters: {result_data.get('total_passed_filters', 'N/A')}")
            print(f"Total Robust: {result_data.get('total_robust', 'N/A')}")
            print(f"Strategies Count: {len(result_data.get('strategies', []))}")
            print(f"All Strategies Count: {len(result_data.get('all_strategies', []))}")
            
            # Check rejection breakdown
            rejection = result_data.get('rejection_breakdown', {})
            print(f"\n=== REJECTION BREAKDOWN ===")
            for reason, count in rejection.items():
                print(f"{reason}: {count}")
                
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Exception: {str(e)}")

if __name__ == "__main__":
    debug_job_result()