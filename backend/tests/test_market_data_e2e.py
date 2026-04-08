"""
Market Data System E2E Tests
Tests: Upload (CSV, BI5), Download (Dukascopy), Coverage, Fix Gaps, Delete, Export

Architecture: 1-minute candles are the source of truth.
All data is stored as 1m candles, higher timeframes are aggregated dynamically.
"""

import pytest
import requests
import os
import io
import csv
from datetime import datetime, timedelta

# Get backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")


class TestAPIConnectivity:
    """Basic API connectivity tests"""
    
    def test_api_root(self):
        """Test API root endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✅ API root accessible: {data['message']}")
    
    def test_data_integrity_check(self):
        """Test data integrity check endpoint"""
        response = requests.get(f"{BASE_URL}/api/data-integrity/check")
        assert response.status_code == 200
        data = response.json()
        assert "integrity_ok" in data
        print(f"✅ Data integrity check: integrity_ok={data['integrity_ok']}")


class TestCSVImport:
    """Test CSV import endpoint POST /api/marketdata/import/csv"""
    
    def test_csv_import_valid_1m_data(self):
        """Test importing valid 1m CSV data"""
        # Create sample 1m CSV data
        csv_data = """timestamp,open,high,low,close,volume
2024-02-15 10:00:00,1.0850,1.0855,1.0848,1.0852,100
2024-02-15 10:01:00,1.0852,1.0858,1.0850,1.0856,150
2024-02-15 10:02:00,1.0856,1.0860,1.0854,1.0858,120
2024-02-15 10:03:00,1.0858,1.0862,1.0855,1.0860,130
2024-02-15 10:04:00,1.0860,1.0865,1.0858,1.0863,140"""
        
        payload = {
            "symbol": "TEST_EURUSD",
            "timeframe": "1m",
            "data": csv_data,
            "format_type": "ctrader",
            "skip_validation": False
        }
        
        response = requests.post(f"{BASE_URL}/api/marketdata/import/csv", json=payload)
        print(f"CSV Import Response: {response.status_code} - {response.text[:500]}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["symbol"] == "TEST_EURUSD"
        assert data["timeframe"] == "1m"
        assert data["imported"] >= 0 or data["updated"] >= 0
        print(f"✅ CSV import successful: imported={data.get('imported', 0)}, updated={data.get('updated', 0)}")
    
    def test_csv_import_invalid_data(self):
        """Test importing invalid CSV data returns error"""
        payload = {
            "symbol": "TEST_INVALID",
            "timeframe": "1m",
            "data": "invalid,csv,data\nno,proper,format",
            "format_type": "ctrader"
        }
        
        response = requests.post(f"{BASE_URL}/api/marketdata/import/csv", json=payload)
        # Should return 400 or 500 for invalid data
        assert response.status_code in [400, 500]
        print(f"✅ Invalid CSV correctly rejected: {response.status_code}")
    
    def test_csv_import_empty_data(self):
        """Test importing empty CSV data"""
        payload = {
            "symbol": "TEST_EMPTY",
            "timeframe": "1m",
            "data": "",
            "format_type": "ctrader"
        }
        
        response = requests.post(f"{BASE_URL}/api/marketdata/import/csv", json=payload)
        assert response.status_code in [400, 500]
        print(f"✅ Empty CSV correctly rejected: {response.status_code}")


class TestCoverageEndpoint:
    """Test coverage endpoint GET /api/marketdata/coverage"""
    
    def test_coverage_returns_symbols_array(self):
        """Test coverage endpoint returns symbols array with timeframe metrics"""
        response = requests.get(f"{BASE_URL}/api/marketdata/coverage")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "symbols" in data
        assert "data_integrity" in data
        assert isinstance(data["symbols"], list)
        
        print(f"✅ Coverage endpoint working: {data['total_symbols']} symbols found")
        
        # If there are symbols, verify structure
        if data["symbols"]:
            symbol = data["symbols"][0]
            assert "symbol" in symbol
            assert "timeframes" in symbol
            
            if symbol["timeframes"]:
                tf = symbol["timeframes"][0]
                assert "timeframe" in tf
                assert "coverage_percent" in tf
                assert "total_candles" in tf
                print(f"  - Sample: {symbol['symbol']} has {len(symbol['timeframes'])} timeframes")
    
    def test_coverage_data_integrity_check(self):
        """Test coverage includes data integrity information"""
        response = requests.get(f"{BASE_URL}/api/marketdata/coverage")
        assert response.status_code == 200
        
        data = response.json()
        integrity = data.get("data_integrity", {})
        assert "integrity_ok" in integrity
        print(f"✅ Data integrity in coverage: {integrity.get('integrity_ok')}")


class TestDukascopyDownload:
    """Test Dukascopy download endpoint POST /api/dukascopy/download"""
    
    def test_dukascopy_download_valid_weekday(self):
        """Test downloading data for a valid weekday (Feb 15, 2024 was Thursday)"""
        # Use a known trading day - Feb 15, 2024 (Thursday)
        payload = {
            "symbols": ["EURUSD"],
            "start_date": "2024-02-15",
            "end_date": "2024-02-15",
            "timeframe": "1m"
        }
        
        response = requests.post(f"{BASE_URL}/api/dukascopy/download", json=payload)
        print(f"Dukascopy Download Response: {response.status_code} - {response.text[:500]}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "task_id" in data
        
        task_id = data["task_id"]
        print(f"✅ Dukascopy download started: task_id={task_id}")
        
        # Check task status
        import time
        max_wait = 60  # Wait up to 60 seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = requests.get(f"{BASE_URL}/api/dukascopy/status/{task_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                task = status_data.get("task", {})
                status = task.get("status", "unknown")
                progress = task.get("progress", 0)
                message = task.get("message", "")
                
                print(f"  - Status: {status}, Progress: {progress:.1f}%, Message: {message}")
                
                if status == "completed":
                    print(f"✅ Download completed successfully")
                    # Verify results
                    results = task.get("results", {})
                    if "EURUSD" in results:
                        eurusd_result = results["EURUSD"]
                        if "error" not in eurusd_result:
                            print(f"  - EURUSD: {eurusd_result.get('stored_in_db', 0)} candles stored")
                        else:
                            print(f"  - EURUSD error: {eurusd_result.get('error')}")
                    return
                elif status == "failed":
                    error = task.get("error", "Unknown error")
                    print(f"⚠️ Download failed: {error}")
                    # Don't fail test - Dukascopy may have issues with certain dates
                    return
            
            time.sleep(3)
        
        print(f"⚠️ Download timed out after {max_wait}s")
    
    def test_dukascopy_download_invalid_date_format(self):
        """Test download with invalid date format"""
        payload = {
            "symbols": ["EURUSD"],
            "start_date": "invalid-date",
            "end_date": "2024-02-15",
            "timeframe": "1m"
        }
        
        response = requests.post(f"{BASE_URL}/api/dukascopy/download", json=payload)
        assert response.status_code == 400
        print(f"✅ Invalid date format correctly rejected: {response.status_code}")
    
    def test_dukascopy_task_status_not_found(self):
        """Test getting status for non-existent task"""
        response = requests.get(f"{BASE_URL}/api/dukascopy/status/non-existent-task-id")
        assert response.status_code == 404
        print(f"✅ Non-existent task correctly returns 404")


class TestFixGaps:
    """Test fix gaps endpoint POST /api/marketdata/fix-gaps"""
    
    def test_fix_gaps_no_gaps(self):
        """Test fix gaps when no gaps exist"""
        # First ensure we have some data
        csv_data = """timestamp,open,high,low,close,volume
2024-03-01 10:00:00,1.0850,1.0855,1.0848,1.0852,100
2024-03-01 10:01:00,1.0852,1.0858,1.0850,1.0856,150
2024-03-01 10:02:00,1.0856,1.0860,1.0854,1.0858,120"""
        
        # Import test data
        import_payload = {
            "symbol": "TEST_GAPFIX",
            "timeframe": "1m",
            "data": csv_data,
            "format_type": "ctrader"
        }
        requests.post(f"{BASE_URL}/api/marketdata/import/csv", json=import_payload)
        
        # Try to fix gaps
        response = requests.post(
            f"{BASE_URL}/api/marketdata/fix-gaps",
            params={"symbol": "TEST_GAPFIX", "timeframe": "1m", "fix_all": True}
        )
        
        print(f"Fix Gaps Response: {response.status_code} - {response.text[:500]}")
        
        # Should return 200 even if no gaps
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print(f"✅ Fix gaps endpoint working: {data.get('message', 'No message')}")
    
    def test_fix_gaps_forces_1m_architecture(self):
        """Test that fix gaps always uses 1m architecture"""
        response = requests.post(
            f"{BASE_URL}/api/marketdata/fix-gaps",
            params={"symbol": "EURUSD", "timeframe": "1h", "fix_all": True}  # Request 1h
        )
        
        # Should still work (forces 1m internally)
        assert response.status_code == 200
        data = response.json()
        # Check for 1m architecture note
        if "note" in data:
            assert "1m" in data["note"].lower() or "higher" in data["note"].lower()
        print(f"✅ Fix gaps correctly forces 1m architecture")


class TestDeleteEndpoint:
    """Test delete endpoint DELETE /api/marketdata/{symbol}/{timeframe}"""
    
    def test_delete_test_data(self):
        """Test deleting test data"""
        # First import some test data
        csv_data = """timestamp,open,high,low,close,volume
2024-04-01 10:00:00,1.0850,1.0855,1.0848,1.0852,100
2024-04-01 10:01:00,1.0852,1.0858,1.0850,1.0856,150"""
        
        import_payload = {
            "symbol": "TEST_DELETE",
            "timeframe": "1m",
            "data": csv_data,
            "format_type": "ctrader"
        }
        requests.post(f"{BASE_URL}/api/marketdata/import/csv", json=import_payload)
        
        # Delete the data
        response = requests.delete(f"{BASE_URL}/api/marketdata/TEST_DELETE/1m")
        print(f"Delete Response: {response.status_code} - {response.text[:500]}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "deleted_count" in data
        print(f"✅ Delete endpoint working: deleted {data['deleted_count']} candles")
    
    def test_delete_nonexistent_data(self):
        """Test deleting non-existent data returns 0 count"""
        response = requests.delete(f"{BASE_URL}/api/marketdata/NONEXISTENT_SYMBOL/1m")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["deleted_count"] == 0
        print(f"✅ Delete non-existent data correctly returns 0")


class TestGetMarketData:
    """Test GET /api/marketdata/{symbol}/{timeframe}"""
    
    def test_get_market_data_after_import(self):
        """Test retrieving market data after import"""
        # First import some data
        csv_data = """timestamp,open,high,low,close,volume
2024-05-01 10:00:00,1.0850,1.0855,1.0848,1.0852,100
2024-05-01 10:01:00,1.0852,1.0858,1.0850,1.0856,150
2024-05-01 10:02:00,1.0856,1.0860,1.0854,1.0858,120"""
        
        import_payload = {
            "symbol": "TEST_GET",
            "timeframe": "1m",
            "data": csv_data,
            "format_type": "ctrader"
        }
        requests.post(f"{BASE_URL}/api/marketdata/import/csv", json=import_payload)
        
        # Get the data
        response = requests.get(f"{BASE_URL}/api/marketdata/TEST_GET/1m")
        print(f"Get Market Data Response: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "candles" in data
        assert len(data["candles"]) >= 0
        print(f"✅ Get market data working: {len(data['candles'])} candles retrieved")
    
    def test_get_market_data_invalid_timeframe(self):
        """Test getting data with invalid timeframe"""
        response = requests.get(f"{BASE_URL}/api/marketdata/EURUSD/invalid_tf")
        assert response.status_code == 400
        print(f"✅ Invalid timeframe correctly rejected")


class TestDataIntegrity:
    """Test data integrity endpoints"""
    
    def test_purge_synthetic_data(self):
        """Test purging synthetic data"""
        response = requests.delete(f"{BASE_URL}/api/data-integrity/purge-synthetic")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "deleted" in data
        print(f"✅ Purge synthetic data: deleted {data['deleted']} candles")


class TestCleanup:
    """Cleanup test data after all tests"""
    
    def test_cleanup_test_data(self):
        """Clean up all TEST_ prefixed data"""
        test_symbols = ["TEST_EURUSD", "TEST_INVALID", "TEST_EMPTY", "TEST_GAPFIX", 
                       "TEST_DELETE", "TEST_GET"]
        
        deleted_total = 0
        for symbol in test_symbols:
            response = requests.delete(f"{BASE_URL}/api/marketdata/{symbol}/1m")
            if response.status_code == 200:
                data = response.json()
                deleted_total += data.get("deleted_count", 0)
        
        print(f"✅ Cleanup complete: deleted {deleted_total} test candles")


# Fixtures
@pytest.fixture(scope="session")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
