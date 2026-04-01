"""
Real Data Auto-Fetch Tests
Tests for CRITICAL feature: All backtests and validations must use REAL market data only.
Auto-fetch from Twelve Data / Alpha Vantage if not cached. Never use mock data silently.
"""

import pytest
import requests
import os
import time

# Get BASE_URL from environment - production external URL
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')


class TestEnsureRealDataEndpoint:
    """Tests for POST /api/marketdata/ensure-real-data - Auto-fetch real candles"""

    def test_ensure_real_data_eurusd_1h(self):
        """Test auto-fetching EURUSD 1h candles - should return success with real data source"""
        response = requests.post(
            f"{BASE_URL}/api/marketdata/ensure-real-data",
            json={
                "symbol": "EURUSD",
                "timeframe": "1h",
                "min_candles": 60
            },
            timeout=60  # Allow time for API fetch
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        
        # CRITICAL: Must return success with real data
        assert data.get("success") == True, "Expected success=True for real data fetch"
        
        # CRITICAL: data_source must NOT be 'mock' or empty
        data_source = data.get("data_source", "")
        assert data_source in ["cache", "twelve_data", "alpha_vantage"], f"Unexpected data_source: {data_source}"
        assert data_source != "mock", "CRITICAL: data_source should NEVER be 'mock'"
        
        # CRITICAL: is_real_data must be True
        assert data.get("is_real_data") == True, "Expected is_real_data=True"
        
        # Verify candle count
        candle_count = data.get("candle_count", 0)
        assert candle_count >= 60, f"Expected at least 60 candles, got {candle_count}"
        
        print(f"SUCCESS: Got {candle_count} real candles from {data_source}")

    def test_ensure_real_data_different_symbols(self):
        """Test auto-fetch for multiple forex symbols"""
        symbols = ["GBPUSD", "USDJPY", "AUDUSD"]
        
        for symbol in symbols:
            response = requests.post(
                f"{BASE_URL}/api/marketdata/ensure-real-data",
                json={
                    "symbol": symbol,
                    "timeframe": "1h",
                    "min_candles": 60
                },
                timeout=60
            )
            
            print(f"\n{symbol} Response: {response.status_code}")
            data = response.json()
            print(f"{symbol} Result: success={data.get('success')}, source={data.get('data_source')}")
            
            # Either succeed with real data, or fail with clear warning (NOT mock)
            if data.get("success"):
                assert data.get("is_real_data") == True
                assert data.get("data_source") != "mock"
            else:
                # If failed, must have warning message - NOT silently use mock
                assert "warning" in data or "error" in data
                assert data.get("data_source") != "mock"

    def test_ensure_real_data_returns_warning_on_failure(self):
        """Test that failure returns clear warning, not silent mock data"""
        # Try an invalid symbol that should fail
        response = requests.post(
            f"{BASE_URL}/api/marketdata/ensure-real-data",
            json={
                "symbol": "INVALIDXYZ",  # Invalid symbol
                "timeframe": "1h",
                "min_candles": 60
            },
            timeout=30
        )
        
        print(f"Invalid symbol response: {response.status_code}")
        data = response.json()
        print(f"Response data: {data}")
        
        # For invalid symbols, should fail with error/warning - NOT return mock data
        if data.get("success") == False:
            # Good - failed properly
            assert "warning" in data or "error" in data
            assert "is_real_data" not in data or data.get("is_real_data") == False
        else:
            # If it succeeded somehow, must be real data
            assert data.get("data_source") != "mock"


class TestBacktestSimulateRealData:
    """Tests for POST /api/backtest/simulate - Must use REAL candles"""

    def test_backtest_simulate_returns_real_data(self):
        """Test backtest/simulate uses real candles and returns is_real_data=true"""
        response = requests.post(
            f"{BASE_URL}/api/backtest/simulate",
            json={
                "bot_name": "TestBot_RealData",
                "symbol": "EURUSD",
                "timeframe": "1h",
                "duration_days": 30,
                "initial_balance": 10000,
                "strategy_type": "trend_following",
                "session_id": "test_real_data_session"
            },
            timeout=90  # Allow time for data fetch + backtest
        )
        
        print(f"Backtest simulate response: {response.status_code}")
        data = response.json()
        print(f"Response: {data}")
        
        assert response.status_code == 200
        
        # Check if operation succeeded or failed with clear warning
        if data.get("success"):
            # CRITICAL: Must indicate real data was used
            assert data.get("is_real_data") == True, "Expected is_real_data=True"
            
            # CRITICAL: data_source must NOT be 'mock'
            data_source = data.get("data_source", "")
            assert data_source != "mock", "CRITICAL: data_source should NEVER be 'mock'"
            assert data_source in ["cache", "twelve_data", "alpha_vantage"], f"Unexpected data_source: {data_source}"
            
            # Verify backtest results exist
            assert "summary" in data
            assert data.get("backtest_id") is not None
            
            print(f"SUCCESS: Backtest completed with real data from {data_source}")
            print(f"Candles used: {data.get('candles_used', 'N/A')}")
        else:
            # If failed, must have clear warning - NOT silent mock fallback
            assert data.get("warning") == "REAL_DATA_UNAVAILABLE" or "error" in data
            assert data.get("is_real_data") == False or data.get("is_real_data") is None
            print(f"EXPECTED FAILURE: {data.get('error', data.get('message', 'Unknown'))}")

    def test_backtest_simulate_no_mock_fallback(self):
        """Verify backtest does NOT silently fall back to mock data"""
        response = requests.post(
            f"{BASE_URL}/api/backtest/simulate",
            json={
                "bot_name": "TestBot_NoMock",
                "symbol": "EURUSD",
                "timeframe": "4h",
                "duration_days": 60,
                "initial_balance": 10000,
                "strategy_type": "mean_reversion",
                "session_id": "test_no_mock_session"
            },
            timeout=90
        )
        
        print(f"Backtest (no mock) response: {response.status_code}")
        data = response.json()
        
        # CRITICAL CHECK: data_source must NEVER be 'mock'
        data_source = data.get("data_source", "")
        assert data_source != "mock", f"CRITICAL FAILURE: Mock data was used! data_source={data_source}"
        
        if data.get("success"):
            assert data.get("is_real_data") == True
            print(f"SUCCESS: No mock fallback, used {data_source}")
        else:
            # Proper failure with warning is acceptable
            assert "warning" in data or "error" in data
            print(f"Proper failure with warning (no silent mock): {data.get('warning', data.get('error'))}")


class TestFactoryGenerateRealData:
    """Tests for POST /api/factory/generate - Must use REAL candles, not mock"""

    def test_factory_generate_uses_real_data(self):
        """Test factory/generate uses real candles, not mock generator"""
        response = requests.post(
            f"{BASE_URL}/api/factory/generate",
            json={
                "templates": ["ema_crossover"],
                "strategies_per_template": 2,
                "symbol": "EURUSD",
                "timeframe": "1h",
                "initial_balance": 10000,
                "duration_days": 30,
                "session_id": "test_factory_real_data"
            },
            timeout=30
        )
        
        print(f"Factory generate response: {response.status_code}")
        data = response.json()
        print(f"Response: {data}")
        
        assert response.status_code == 200
        assert data.get("success") == True
        
        run_id = data.get("run_id")
        assert run_id is not None
        
        # Poll for completion
        max_wait = 120  # 2 minutes
        poll_interval = 5
        elapsed = 0
        
        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            
            status_response = requests.get(
                f"{BASE_URL}/api/factory/status/{run_id}",
                timeout=10
            )
            
            if status_response.status_code != 200:
                continue
                
            status_data = status_response.json()
            print(f"Factory status: {status_data.get('status')}")
            
            if status_data.get("status") in ["completed", "failed"]:
                break
        
        # Get full result
        result_response = requests.get(
            f"{BASE_URL}/api/factory/result/{run_id}",
            timeout=30
        )
        
        if result_response.status_code == 200:
            result_data = result_response.json().get("result", {})
            
            # CRITICAL: Check data_source is NOT mock
            data_source = result_data.get("data_source", "")
            print(f"Factory data_source: {data_source}")
            
            assert data_source != "mock", f"CRITICAL FAILURE: Factory used mock data! data_source={data_source}"
            
            if result_data.get("status") == "completed":
                assert data_source in ["cache", "twelve_data", "alpha_vantage", "FAILED_NO_REAL_DATA"]
                print(f"SUCCESS: Factory used real data from {data_source}")
            elif result_data.get("status") == "failed":
                # Acceptable if it failed due to no real data (not silent mock)
                error_msg = result_data.get("error_message", "")
                print(f"Factory failed (expected if no real data): {error_msg}")
                assert "real" in error_msg.lower() or "data" in error_msg.lower() or data_source == "FAILED_NO_REAL_DATA"
        else:
            print(f"Could not get factory result: {result_response.status_code}")


class TestNoMockGeneratorFallback:
    """Verify mock_generator is NEVER used silently"""

    def test_verify_no_silent_mock_in_backtest(self):
        """Comprehensive test to ensure no silent mock fallback"""
        # Run multiple backtests and verify none use mock
        test_configs = [
            {"symbol": "EURUSD", "timeframe": "1h", "strategy_type": "trend_following"},
            {"symbol": "GBPUSD", "timeframe": "1h", "strategy_type": "mean_reversion"},
            {"symbol": "EURUSD", "timeframe": "4h", "strategy_type": "breakout"},
        ]
        
        for config in test_configs:
            response = requests.post(
                f"{BASE_URL}/api/backtest/simulate",
                json={
                    "bot_name": f"NoMockTest_{config['symbol']}_{config['timeframe']}",
                    "symbol": config["symbol"],
                    "timeframe": config["timeframe"],
                    "duration_days": 30,
                    "initial_balance": 10000,
                    "strategy_type": config["strategy_type"],
                    "session_id": "no_mock_verification"
                },
                timeout=90
            )
            
            data = response.json()
            
            # CRITICAL: Never use mock
            data_source = data.get("data_source", "")
            assert data_source != "mock", f"CRITICAL: {config} used mock data!"
            
            print(f"{config['symbol']} {config['timeframe']}: data_source={data_source}, success={data.get('success')}")


class TestDataSourceTracking:
    """Test that data source is properly tracked in all responses"""

    def test_ensure_data_tracks_source(self):
        """Verify ensure-real-data returns correct data source"""
        response = requests.post(
            f"{BASE_URL}/api/marketdata/ensure-real-data",
            json={"symbol": "EURUSD", "timeframe": "1h", "min_candles": 60},
            timeout=60
        )
        
        data = response.json()
        
        if data.get("success"):
            # data_source must be one of the valid sources
            assert data.get("data_source") in ["cache", "twelve_data", "alpha_vantage"]
            assert data.get("is_real_data") == True
            assert data.get("candle_count") >= 60
        else:
            # If failed, must have clear error
            assert "error" in data or "warning" in data

    def test_backtest_tracks_source(self):
        """Verify backtest/simulate returns correct data source"""
        response = requests.post(
            f"{BASE_URL}/api/backtest/simulate",
            json={
                "bot_name": "SourceTrackingTest",
                "symbol": "EURUSD",
                "timeframe": "1h",
                "duration_days": 30,
                "initial_balance": 10000,
                "strategy_type": "trend_following",
                "session_id": "source_tracking_test"
            },
            timeout=90
        )
        
        data = response.json()
        
        # Must always include data tracking fields
        assert "is_real_data" in data or "warning" in data
        assert "data_source" in data or "warning" in data
        
        if data.get("success"):
            assert data.get("data_source") in ["cache", "twelve_data", "alpha_vantage"]
            assert data.get("is_real_data") == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
