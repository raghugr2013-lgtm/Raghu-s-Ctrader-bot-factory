#!/usr/bin/env python3
"""
Backend Test Suite for M1 SSOT Data Ingestion V2 API
Testing all endpoints as specified in the review request.
"""

import requests
import json
import io
import csv
from datetime import datetime, timedelta
import time

# Configuration
BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api/v2/data"

def create_test_m1_csv():
    """Create a test M1 CSV with 5 minutes of data"""
    start_time = datetime(2024, 1, 15, 10, 0, 0)
    csv_content = "timestamp,open,high,low,close,volume\n"
    
    for i in range(5):  # 5 minutes of M1 data
        ts = start_time + timedelta(minutes=i)
        open_price = 1.0900 + (i * 0.0001)
        high_price = open_price + 0.0005
        low_price = open_price - 0.0003
        close_price = open_price + 0.0002
        volume = 100 + i
        
        csv_content += f"{ts.strftime('%Y-%m-%d %H:%M:%S')},{open_price},{high_price},{low_price},{close_price},{volume}\n"
    
    return csv_content

def create_test_h1_csv():
    """Create a test H1 CSV with hourly data (should be rejected)"""
    start_time = datetime(2024, 1, 15, 10, 0, 0)
    csv_content = "timestamp,open,high,low,close,volume\n"
    
    for i in range(3):  # 3 hours of H1 data
        ts = start_time + timedelta(hours=i)
        open_price = 1.0900 + (i * 0.0010)
        high_price = open_price + 0.0020
        low_price = open_price - 0.0015
        close_price = open_price + 0.0005
        volume = 1000 + (i * 100)
        
        csv_content += f"{ts.strftime('%Y-%m-%d %H:%M:%S')},{open_price},{high_price},{low_price},{close_price},{volume}\n"
    
    return csv_content

def test_health_check():
    """Test 1: Health Check - GET /api/v2/data/health"""
    print("\n=== TEST 1: Health Check ===")
    
    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if data.get("status") == "healthy":
                print("✅ PASS: Health check returned 'healthy' status")
                return True
            else:
                print(f"❌ FAIL: Expected status 'healthy', got '{data.get('status')}'")
                return False
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_csv_upload_m1():
    """Test 2: CSV Upload (M1) - POST /api/v2/data/upload/csv"""
    print("\n=== TEST 2: CSV Upload (M1) ===")
    
    try:
        # Create test M1 CSV
        csv_content = create_test_m1_csv()
        csv_lines = csv_content.split('\n')
        print(f"Created M1 CSV with {len(csv_lines)-2} rows")
        
        # Prepare file upload
        files = {
            'file': ('test_m1.csv', io.StringIO(csv_content), 'text/csv')
        }
        data = {
            'symbol': 'GBPUSD'
        }
        
        response = requests.post(f"{API_BASE}/upload/csv", files=files, data=data, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            
            if result.get("success") and result.get("candles_stored", 0) > 0:
                print(f"✅ PASS: M1 upload successful - {result.get('candles_stored')} candles stored")
                return True
            else:
                print(f"❌ FAIL: Upload failed or no candles stored")
                return False
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_csv_upload_h1_reject():
    """Test 3: CSV Upload (H1 - Should REJECT) - POST /api/v2/data/upload/csv"""
    print("\n=== TEST 3: CSV Upload (H1 - Should REJECT) ===")
    
    try:
        # Create test H1 CSV
        csv_content = create_test_h1_csv()
        csv_lines = csv_content.split('\n')
        print(f"Created H1 CSV with {len(csv_lines)-2} rows")
        
        # Prepare file upload
        files = {
            'file': ('test_h1.csv', io.StringIO(csv_content), 'text/csv')
        }
        data = {
            'symbol': 'GBPUSD'
        }
        
        response = requests.post(f"{API_BASE}/upload/csv", files=files, data=data, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            
            if not result.get("success") and result.get("detected_timeframe") == "H1":
                print("✅ PASS: H1 upload correctly rejected with detected_timeframe=H1")
                return True
            else:
                print(f"❌ FAIL: Expected rejection with H1 detection, got success={result.get('success')}, detected_timeframe={result.get('detected_timeframe')}")
                return False
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_coverage_check():
    """Test 4: Coverage Check - GET /api/v2/data/coverage/GBPUSD"""
    print("\n=== TEST 4: Coverage Check ===")
    
    try:
        response = requests.get(f"{API_BASE}/coverage/GBPUSD", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            total_candles = data.get("total_m1_candles", 0)
            high_confidence = data.get("high_confidence_count", 0)
            
            if total_candles > 0 and high_confidence > 0:
                print(f"✅ PASS: Coverage check successful - {total_candles} total M1 candles, {high_confidence} high confidence")
                return True
            else:
                print(f"❌ FAIL: Expected total_m1_candles > 0 and high_confidence_count > 0")
                return False
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_export_m1():
    """Test 5: Export M1 - GET /api/v2/data/export/m1/GBPUSD"""
    print("\n=== TEST 5: Export M1 ===")
    
    try:
        params = {
            'start_date': '2024-01-15T10:00:00',
            'end_date': '2024-01-15T10:10:00'
        }
        
        response = requests.get(f"{API_BASE}/export/m1/GBPUSD", params=params, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        
        if response.status_code == 200:
            content = response.text
            print(f"Response length: {len(content)} characters")
            print(f"First 200 characters: {content[:200]}")
            
            # Check if it's CSV format
            if 'timestamp,open,high,low,close,volume' in content:
                lines = content.strip().split('\n')
                data_lines = [line for line in lines if not line.startswith('#') and line.strip() and 'timestamp' not in line]
                print(f"✅ PASS: CSV export successful - {len(data_lines)} data rows returned")
                return True
            else:
                print("❌ FAIL: Response doesn't appear to be valid CSV format")
                return False
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_gap_detection():
    """Test 6: Gap Detection - GET /api/v2/data/gaps/GBPUSD/detect"""
    print("\n=== TEST 6: Gap Detection ===")
    
    try:
        response = requests.get(f"{API_BASE}/gaps/GBPUSD/detect", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if "gaps" in data and isinstance(data["gaps"], list):
                print(f"✅ PASS: Gap detection successful - found {len(data['gaps'])} gaps")
                return True
            else:
                print("❌ FAIL: Response doesn't contain 'gaps' array")
                return False
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_delete_data():
    """Test 7: Delete Test - DELETE /api/v2/data/delete/GBPUSD"""
    print("\n=== TEST 7: Delete Test Data ===")
    
    try:
        params = {'confirm': 'true'}
        response = requests.delete(f"{API_BASE}/delete/GBPUSD", params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if data.get("success"):
                print(f"✅ PASS: Data deletion successful - {data.get('deleted_count', 0)} candles deleted")
                return True
            else:
                print("❌ FAIL: Deletion was not successful")
                return False
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting M1 SSOT Data Ingestion V2 API Tests")
    print(f"Backend URL: {BASE_URL}")
    print(f"API Base: {API_BASE}")
    
    tests = [
        ("Health Check", test_health_check),
        ("CSV Upload (M1)", test_csv_upload_m1),
        ("CSV Upload (H1 - Should REJECT)", test_csv_upload_h1_reject),
        ("Coverage Check", test_coverage_check),
        ("Export M1", test_export_m1),
        ("Gap Detection", test_gap_detection),
        ("Delete Test", test_delete_data)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ CRITICAL ERROR in {test_name}: {str(e)}")
            results.append((test_name, False))
        
        # Small delay between tests
        time.sleep(1)
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {failed} TEST(S) FAILED")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)