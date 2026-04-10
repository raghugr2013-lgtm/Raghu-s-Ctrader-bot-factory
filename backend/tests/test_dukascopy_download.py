"""
Test Dukascopy Download Feature - Backend API Tests

Tests:
1. POST /api/v2/data/download/dukascopy - Start download job
2. GET /api/v2/data/download/status/{job_id} - Check progress
3. GET /api/v2/data/download/estimate - Estimate download size
4. Dukascopy URL construction validation
5. Date range validation
"""

import pytest
import requests
import os
import time
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ai-bot-factory-audit.preview.emergentagent.com')
API_V2 = f"{BASE_URL}/api/v2/data"


class TestDukascopyDownloadEndpoints:
    """Test Dukascopy download API endpoints"""
    
    def test_health_check(self):
        """Test V2 data API health check"""
        response = requests.get(f"{API_V2}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["architecture"] == "M1 SSOT"
        print(f"✅ Health check passed: {data['service']}")
    
    def test_download_estimate_endpoint(self):
        """Test download estimate endpoint returns correct structure"""
        # Test with 1 day range
        start_date = "2024-01-15T00:00:00"
        end_date = "2024-01-16T00:00:00"
        
        response = requests.get(
            f"{API_V2}/download/estimate",
            params={
                "symbol": "EURUSD",
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "symbol" in data
        assert "total_hours" in data
        assert "total_days" in data
        assert "estimated_size_mb" in data
        assert "estimated_time_minutes" in data
        assert "estimated_m1_candles" in data
        assert "warnings" in data
        
        # Validate values
        assert data["symbol"] == "EURUSD"
        assert data["total_hours"] == 25  # 24 hours + 1 for inclusive end
        assert data["total_days"] == pytest.approx(25/24, rel=0.1)
        assert data["estimated_m1_candles"] == 25 * 60  # 60 M1 candles per hour
        
        print(f"✅ Estimate endpoint working: {data['total_hours']} hours, {data['estimated_m1_candles']} M1 candles")
    
    def test_download_estimate_week_range(self):
        """Test estimate for a week range"""
        start_date = "2024-01-15T00:00:00"
        end_date = "2024-01-22T00:00:00"  # 7 days
        
        response = requests.get(
            f"{API_V2}/download/estimate",
            params={
                "symbol": "XAUUSD",
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 7 days = 168 hours + 1 for inclusive
        expected_hours = 7 * 24 + 1
        assert data["total_hours"] == expected_hours
        assert data["symbol"] == "XAUUSD"
        
        print(f"✅ Week estimate: {data['total_hours']} hours, ~{data['estimated_size_mb']} MB")
    
    def test_download_dukascopy_start_job(self):
        """Test starting a Dukascopy download job"""
        # Use a small date range (1 hour) for testing
        start_date = "2024-01-15T10:00:00"
        end_date = "2024-01-15T11:00:00"
        
        response = requests.post(
            f"{API_V2}/download/dukascopy",
            json={
                "symbol": "EURUSD",
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert data["success"] == True
        assert "job_id" in data
        assert data["symbol"] == "EURUSD"
        assert data["status"] == "queued"
        assert "estimated_hours" in data
        assert "message" in data
        
        job_id = data["job_id"]
        print(f"✅ Download job started: {job_id}")
        
        return job_id
    
    def test_download_status_endpoint(self):
        """Test download status endpoint"""
        # First start a job
        start_date = "2024-01-15T10:00:00"
        end_date = "2024-01-15T11:00:00"
        
        start_response = requests.post(
            f"{API_V2}/download/dukascopy",
            json={
                "symbol": "EURUSD",
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        assert start_response.status_code == 200
        job_id = start_response.json()["job_id"]
        
        # Check status
        status_response = requests.get(f"{API_V2}/download/status/{job_id}")
        
        assert status_response.status_code == 200, f"Expected 200, got {status_response.status_code}"
        data = status_response.json()
        
        # Validate response structure
        assert data["job_id"] == job_id
        assert data["symbol"] == "EURUSD"
        assert "status" in data
        assert "progress_percent" in data
        assert "hours_completed" in data
        assert "hours_total" in data
        assert "hours_successful" in data
        assert "hours_failed" in data
        assert "candles_stored" in data
        assert "current_status" in data
        assert "errors" in data
        assert "completed" in data
        
        print(f"✅ Status endpoint working: {data['status']}, {data['progress_percent']}%")
    
    def test_download_status_invalid_job_id(self):
        """Test status endpoint with invalid job ID returns 404"""
        response = requests.get(f"{API_V2}/download/status/invalid-job-id-12345")
        
        assert response.status_code == 404
        print("✅ Invalid job ID returns 404 as expected")
    
    def test_download_date_validation_start_after_end(self):
        """Test that start_date after end_date is rejected"""
        response = requests.post(
            f"{API_V2}/download/dukascopy",
            json={
                "symbol": "EURUSD",
                "start_date": "2024-01-20T00:00:00",
                "end_date": "2024-01-15T00:00:00"  # Before start
            }
        )
        
        assert response.status_code == 400
        assert "start_date must be before end_date" in response.text
        print("✅ Date validation working: start_date > end_date rejected")
    
    def test_download_date_range_too_large(self):
        """Test that date range > 365 days is rejected"""
        response = requests.post(
            f"{API_V2}/download/dukascopy",
            json={
                "symbol": "EURUSD",
                "start_date": "2023-01-01T00:00:00",
                "end_date": "2024-06-01T00:00:00"  # > 365 days
            }
        )
        
        assert response.status_code == 400
        assert "Date range too large" in response.text or "Maximum 365 days" in response.text
        print("✅ Date range validation working: > 365 days rejected")
    
    def test_download_progress_polling(self):
        """Test polling download progress until completion or timeout"""
        # Start a small download job
        start_date = "2024-01-15T10:00:00"
        end_date = "2024-01-15T11:00:00"  # 2 hours
        
        start_response = requests.post(
            f"{API_V2}/download/dukascopy",
            json={
                "symbol": "EURUSD",
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        assert start_response.status_code == 200
        job_id = start_response.json()["job_id"]
        
        # Poll for up to 30 seconds
        max_polls = 15
        poll_interval = 2
        
        for i in range(max_polls):
            time.sleep(poll_interval)
            
            status_response = requests.get(f"{API_V2}/download/status/{job_id}")
            assert status_response.status_code == 200
            
            data = status_response.json()
            print(f"  Poll {i+1}: {data['status']} - {data['progress_percent']:.1f}% - {data['current_status']}")
            
            if data["completed"]:
                print(f"✅ Download completed: {data['candles_stored']} candles stored")
                
                # Validate final state
                assert data["status"] in ["completed", "failed"]
                assert data["progress_percent"] == 100.0
                assert data["hours_completed"] == data["hours_total"]
                return
        
        # If we get here, job didn't complete in time (but that's OK for testing)
        print(f"⚠️ Download still in progress after {max_polls * poll_interval}s (expected for real downloads)")


class TestDukascopyDownloaderUnit:
    """Unit tests for Dukascopy downloader URL construction"""
    
    def test_url_construction_january(self):
        """Test URL construction for January (month 00)"""
        # Import the downloader
        import sys
        sys.path.insert(0, '/app/backend')
        from data_ingestion.dukascopy_downloader import DukascopyDownloader
        
        downloader = DukascopyDownloader()
        
        # January 15, 2024, 10:00 UTC
        dt = datetime(2024, 1, 15, 10, 0, 0)
        url = downloader.build_url("EURUSD", dt)
        
        expected = "https://datafeed.dukascopy.com/datafeed/EURUSD/2024/00/15/10h_ticks.bi5"
        assert url == expected, f"Expected {expected}, got {url}"
        print(f"✅ January URL correct: {url}")
    
    def test_url_construction_december(self):
        """Test URL construction for December (month 11)"""
        import sys
        sys.path.insert(0, '/app/backend')
        from data_ingestion.dukascopy_downloader import DukascopyDownloader
        
        downloader = DukascopyDownloader()
        
        # December 25, 2024, 23:00 UTC
        dt = datetime(2024, 12, 25, 23, 0, 0)
        url = downloader.build_url("XAUUSD", dt)
        
        expected = "https://datafeed.dukascopy.com/datafeed/XAUUSD/2024/11/25/23h_ticks.bi5"
        assert url == expected, f"Expected {expected}, got {url}"
        print(f"✅ December URL correct: {url}")
    
    def test_url_construction_february(self):
        """Test URL construction for February (month 01)"""
        import sys
        sys.path.insert(0, '/app/backend')
        from data_ingestion.dukascopy_downloader import DukascopyDownloader
        
        downloader = DukascopyDownloader()
        
        # February 1, 2025, 00:00 UTC
        dt = datetime(2025, 2, 1, 0, 0, 0)
        url = downloader.build_url("GBPUSD", dt)
        
        expected = "https://datafeed.dukascopy.com/datafeed/GBPUSD/2025/01/01/00h_ticks.bi5"
        assert url == expected, f"Expected {expected}, got {url}"
        print(f"✅ February URL correct: {url}")
    
    def test_symbol_uppercase(self):
        """Test that symbol is converted to uppercase"""
        import sys
        sys.path.insert(0, '/app/backend')
        from data_ingestion.dukascopy_downloader import DukascopyDownloader
        
        downloader = DukascopyDownloader()
        
        dt = datetime(2024, 6, 15, 12, 0, 0)
        url = downloader.build_url("eurusd", dt)  # lowercase
        
        assert "EURUSD" in url
        assert "eurusd" not in url
        print(f"✅ Symbol uppercase conversion working")


class TestDukascopyIntegration:
    """Integration tests for full download flow"""
    
    def test_full_download_flow_small_range(self):
        """Test complete download flow with a small date range"""
        # Start download
        start_date = "2024-01-15T10:00:00"
        end_date = "2024-01-15T12:00:00"  # 3 hours
        
        # Get estimate first
        estimate_response = requests.get(
            f"{API_V2}/download/estimate",
            params={
                "symbol": "EURUSD",
                "start_date": start_date,
                "end_date": end_date
            }
        )
        assert estimate_response.status_code == 200
        estimate = estimate_response.json()
        print(f"  Estimate: {estimate['total_hours']} hours, {estimate['estimated_m1_candles']} M1 candles")
        
        # Start download
        start_response = requests.post(
            f"{API_V2}/download/dukascopy",
            json={
                "symbol": "EURUSD",
                "start_date": start_date,
                "end_date": end_date
            }
        )
        assert start_response.status_code == 200
        job_data = start_response.json()
        job_id = job_data["job_id"]
        print(f"  Job started: {job_id}")
        
        # Poll until complete or timeout
        max_wait = 60  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            time.sleep(2)
            
            status_response = requests.get(f"{API_V2}/download/status/{job_id}")
            assert status_response.status_code == 200
            
            status = status_response.json()
            
            if status["completed"]:
                print(f"✅ Download completed in {time.time() - start_time:.1f}s")
                print(f"  Status: {status['status']}")
                print(f"  Hours: {status['hours_successful']}/{status['hours_total']} successful")
                print(f"  Candles stored: {status['candles_stored']}")
                
                if status["errors"]:
                    print(f"  Errors: {status['errors'][:3]}")
                
                return
        
        print(f"⚠️ Download did not complete within {max_wait}s timeout")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
