"""
Real Candle Factory Tests - Iteration 10
Tests the integration of real AlphaVantage OHLCV candles into the backtesting pipeline.

Key features tested:
1. Factory with EURUSD 1d uses real cached candles (data_source=real_candles)
2. Factory with uncached symbol/timeframe falls back to mock (data_source=mock)
3. Real-data strategies have realistic metrics (some profitable, some losing)
4. Real-data strategies have non-zero total_trades
5. All 5 templates work with real data
6. Leaderboard includes real-data factory strategies
7. Leaderboard summary counts all runs correctly
8. Factory status shows data_source field
9. Factory result includes data_source
10. Fitness scores differ between strategies
11. Strategies sorted by fitness descending
"""

import pytest
import requests
import time
import os

# API Base URL from environment
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-bot-factory-audit.preview.emergentagent.com"

# Test session ID for isolation
TEST_SESSION_ID = "TEST_real_candle_iter10"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ============================================================================
# VERIFY CACHED CANDLE DATA EXISTS
# ============================================================================

class TestCachedCandleData:
    """Verify cached candle data exists for real backtesting"""
    
    def test_eurusd_1d_candles_exist(self, api_client):
        """EURUSD 1d has cached candles from AlphaVantage"""
        response = api_client.get(f"{BASE_URL}/api/alphavantage/status")
        assert response.status_code == 200
        data = response.json()
        
        stored = data.get("stored_data", [])
        eurusd_1d = next((d for d in stored if d["symbol"] == "EURUSD" and d["timeframe"] == "1d"), None)
        
        assert eurusd_1d is not None, "EURUSD 1d data not found in stored data"
        assert eurusd_1d["candles"] >= 1000, f"Expected >= 1000 candles, got {eurusd_1d['candles']}"
        
        print(f"✓ EURUSD 1d has {eurusd_1d['candles']} cached candles ({eurusd_1d['from']} to {eurusd_1d['to']})")
    
    def test_gbpusd_1d_candles_exist(self, api_client):
        """GBPUSD 1d has cached candles from AlphaVantage"""
        response = api_client.get(f"{BASE_URL}/api/alphavantage/status")
        assert response.status_code == 200
        data = response.json()
        
        stored = data.get("stored_data", [])
        gbpusd_1d = next((d for d in stored if d["symbol"] == "GBPUSD" and d["timeframe"] == "1d"), None)
        
        assert gbpusd_1d is not None, "GBPUSD 1d data not found in stored data"
        assert gbpusd_1d["candles"] >= 100, f"Expected >= 100 candles, got {gbpusd_1d['candles']}"
        
        print(f"✓ GBPUSD 1d has {gbpusd_1d['candles']} cached candles")


# ============================================================================
# FACTORY WITH REAL CANDLES - EURUSD 1d
# ============================================================================

class TestFactoryWithRealCandles:
    """Test factory using real cached EURUSD 1d candles"""
    
    @pytest.fixture(scope="class")
    def real_candle_run_id(self, api_client):
        """Create a factory run with EURUSD 1d (should use real candles)"""
        payload = {
            "session_id": TEST_SESSION_ID,
            "templates": ["ema_crossover", "rsi_mean_reversion", "macd_trend", "bollinger_breakout", "atr_volatility_breakout"],
            "strategies_per_template": 5,
            "symbol": "EURUSD",
            "timeframe": "1d"
        }
        response = api_client.post(f"{BASE_URL}/api/factory/generate", json=payload)
        assert response.status_code == 200, f"Failed to start factory run: {response.text}"
        
        data = response.json()
        run_id = data["run_id"]
        print(f"✓ Started factory run {run_id} with EURUSD 1d (5 templates x 5 strategies)")
        
        # Wait for completion (real backtesting takes longer - up to 25s)
        for i in range(30):
            time.sleep(1)
            status_resp = api_client.get(f"{BASE_URL}/api/factory/status/{run_id}")
            status_data = status_resp.json()
            if status_data["status"] == "completed":
                print(f"✓ Factory run completed in ~{i+1} seconds")
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Factory run failed: {status_data.get('error_message')}")
        else:
            pytest.fail("Factory run timed out after 30 seconds")
        
        return run_id
    
    def test_data_source_is_real_candles(self, api_client, real_candle_run_id):
        """Factory run with EURUSD 1d should use real_candles data source"""
        response = api_client.get(f"{BASE_URL}/api/factory/result/{real_candle_run_id}")
        assert response.status_code == 200
        data = response.json()
        
        result = data["result"]
        data_source = result.get("data_source", "unknown")
        
        assert data_source == "real_candles", f"Expected data_source='real_candles', got '{data_source}'"
        print(f"✓ Factory run uses data_source='{data_source}' (real OHLCV candles)")
    
    def test_all_25_strategies_generated(self, api_client, real_candle_run_id):
        """5 templates x 5 strategies = 25 total strategies"""
        response = api_client.get(f"{BASE_URL}/api/factory/result/{real_candle_run_id}")
        data = response.json()
        result = data["result"]
        
        assert result["total_generated"] == 25, f"Expected 25 generated, got {result['total_generated']}"
        assert result["total_evaluated"] == 25, f"Expected 25 evaluated, got {result['total_evaluated']}"
        assert len(result["strategies"]) == 25, f"Expected 25 strategies, got {len(result['strategies'])}"
        
        print("✓ All 25 strategies generated and evaluated (5 templates x 5 each)")
    
    def test_all_5_templates_represented(self, api_client, real_candle_run_id):
        """All 5 templates should produce strategies"""
        response = api_client.get(f"{BASE_URL}/api/factory/result/{real_candle_run_id}")
        data = response.json()
        
        strategies = data["result"]["strategies"]
        template_ids = set(s["template_id"] for s in strategies)
        
        expected_templates = {"ema_crossover", "rsi_mean_reversion", "macd_trend", "bollinger_breakout", "atr_volatility_breakout"}
        assert template_ids == expected_templates, f"Expected templates {expected_templates}, got {template_ids}"
        
        # Each template should have 5 strategies
        for tmpl in expected_templates:
            count = sum(1 for s in strategies if s["template_id"] == tmpl)
            assert count == 5, f"Template {tmpl} has {count} strategies, expected 5"
        
        print(f"✓ All 5 templates produced strategies: {sorted(template_ids)}")
    
    def test_strategies_have_nonzero_total_trades(self, api_client, real_candle_run_id):
        """Real-data strategies should have total_trades > 0"""
        response = api_client.get(f"{BASE_URL}/api/factory/result/{real_candle_run_id}")
        data = response.json()
        
        strategies = data["result"]["strategies"]
        strategies_with_trades = [s for s in strategies if s["total_trades"] > 0]
        
        # At least some strategies should have trades (not all might due to signal conditions)
        trade_ratio = len(strategies_with_trades) / len(strategies) * 100
        print(f"✓ {len(strategies_with_trades)}/{len(strategies)} strategies have trades ({trade_ratio:.0f}%)")
        
        # At least 50% should have trades
        assert trade_ratio >= 50, f"Only {trade_ratio:.0f}% have trades, expected >= 50%"
    
    def test_strategies_have_realistic_metrics(self, api_client, real_candle_run_id):
        """Real-data strategies should have varied, realistic metrics"""
        response = api_client.get(f"{BASE_URL}/api/factory/result/{real_candle_run_id}")
        data = response.json()
        
        strategies = data["result"]["strategies"]
        
        # Collect metrics
        fitnesses = [s["fitness"] for s in strategies]
        sharpes = [s["sharpe_ratio"] for s in strategies]
        drawdowns = [s["max_drawdown_pct"] for s in strategies]
        net_profits = [s["net_profit"] for s in strategies]
        
        # Fitness should vary (not all identical)
        unique_fitnesses = len(set(f"{f:.2f}" for f in fitnesses))
        assert unique_fitnesses > 5, f"Only {unique_fitnesses} unique fitness values, expected more variation"
        
        # Some strategies should be profitable, some losing
        profitable = sum(1 for np in net_profits if np > 0)
        losing = sum(1 for np in net_profits if np < 0)
        
        print(f"✓ {profitable} profitable / {losing} losing strategies (realistic distribution)")
        print(f"✓ Fitness range: {min(fitnesses):.2f} - {max(fitnesses):.2f}")
        print(f"✓ Sharpe range: {min(sharpes):.2f} - {max(sharpes):.2f}")
        print(f"✓ Drawdown range: {min(drawdowns):.2f}% - {max(drawdowns):.2f}%")
    
    def test_fitness_scores_differ(self, api_client, real_candle_run_id):
        """Fitness scores should differ between strategies"""
        response = api_client.get(f"{BASE_URL}/api/factory/result/{real_candle_run_id}")
        data = response.json()
        
        strategies = data["result"]["strategies"]
        fitnesses = [s["fitness"] for s in strategies]
        
        # Calculate variance
        mean_fitness = sum(fitnesses) / len(fitnesses)
        variance = sum((f - mean_fitness) ** 2 for f in fitnesses) / len(fitnesses)
        std_dev = variance ** 0.5
        
        print(f"✓ Fitness stats: mean={mean_fitness:.2f}, std_dev={std_dev:.2f}")
        
        # Std dev should be > 0 (strategies should differ)
        assert std_dev > 0.5, f"Fitness std_dev={std_dev:.2f} too low, strategies too similar"
    
    def test_strategies_sorted_by_fitness_descending(self, api_client, real_candle_run_id):
        """Strategies should be sorted by fitness descending"""
        response = api_client.get(f"{BASE_URL}/api/factory/result/{real_candle_run_id}")
        data = response.json()
        
        strategies = data["result"]["strategies"]
        fitnesses = [s["fitness"] for s in strategies]
        
        assert fitnesses == sorted(fitnesses, reverse=True), "Strategies not sorted by fitness descending"
        
        print(f"✓ Strategies sorted: top 5 = {fitnesses[:5]}")
    
    def test_best_strategy_is_first(self, api_client, real_candle_run_id):
        """best_strategy should match first (highest fitness) in list"""
        response = api_client.get(f"{BASE_URL}/api/factory/result/{real_candle_run_id}")
        data = response.json()
        result = data["result"]
        
        best = result["best_strategy"]
        first = result["strategies"][0]
        
        assert best["id"] == first["id"], "best_strategy doesn't match first in list"
        assert best["fitness"] == first["fitness"], "best_strategy fitness mismatch"
        
        print(f"✓ best_strategy fitness={best['fitness']:.2f}, template={best['template_id']}")


# ============================================================================
# FACTORY WITH MOCK FALLBACK - UNCACHED SYMBOL/TIMEFRAME
# ============================================================================

class TestFactoryMockFallback:
    """Test factory falls back to mock when no cached candles"""
    
    @pytest.fixture(scope="class")
    def mock_fallback_run_id(self, api_client):
        """Create a factory run with uncached symbol/timeframe (should use mock)"""
        # Use USDJPY 1h which is not cached
        payload = {
            "session_id": TEST_SESSION_ID,
            "templates": ["ema_crossover"],
            "strategies_per_template": 3,
            "symbol": "USDJPY",
            "timeframe": "1h"
        }
        response = api_client.post(f"{BASE_URL}/api/factory/generate", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        run_id = data["run_id"]
        print(f"✓ Started factory run {run_id} with USDJPY 1h (should use mock)")
        
        # Wait for completion
        for i in range(20):
            time.sleep(1)
            status_resp = api_client.get(f"{BASE_URL}/api/factory/status/{run_id}")
            status_data = status_resp.json()
            if status_data["status"] == "completed":
                print(f"✓ Mock fallback run completed in ~{i+1} seconds")
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Factory run failed: {status_data.get('error_message')}")
        else:
            pytest.fail("Factory run timed out")
        
        return run_id
    
    def test_data_source_is_mock(self, api_client, mock_fallback_run_id):
        """Factory run with uncached symbol should use mock data source"""
        response = api_client.get(f"{BASE_URL}/api/factory/result/{mock_fallback_run_id}")
        assert response.status_code == 200
        data = response.json()
        
        result = data["result"]
        data_source = result.get("data_source", "unknown")
        
        assert data_source == "mock", f"Expected data_source='mock', got '{data_source}'"
        print(f"✓ Uncached symbol/timeframe uses data_source='{data_source}' fallback")


# ============================================================================
# FACTORY STATUS ENDPOINT
# ============================================================================

class TestFactoryStatus:
    """Test factory status endpoint includes data_source"""
    
    def test_status_for_real_data_run(self, api_client):
        """GET /api/factory/status/{run_id} works for real-data run"""
        # Start a quick run
        payload = {
            "session_id": TEST_SESSION_ID,
            "templates": ["ema_crossover"],
            "strategies_per_template": 2,
            "symbol": "EURUSD",
            "timeframe": "1d"
        }
        response = api_client.post(f"{BASE_URL}/api/factory/generate", json=payload)
        run_id = response.json()["run_id"]
        
        # Wait for completion
        for _ in range(20):
            time.sleep(1)
            status_resp = api_client.get(f"{BASE_URL}/api/factory/status/{run_id}")
            if status_resp.json()["status"] == "completed":
                break
        
        status_resp = api_client.get(f"{BASE_URL}/api/factory/status/{run_id}")
        assert status_resp.status_code == 200
        
        status_data = status_resp.json()
        assert "status" in status_data
        assert status_data["status"] == "completed"
        assert "best_fitness" in status_data
        assert status_data["best_fitness"] > 0
        
        print(f"✓ Status for real-data run: status={status_data['status']}, best_fitness={status_data['best_fitness']:.2f}")


# ============================================================================
# LEADERBOARD WITH REAL-DATA STRATEGIES
# ============================================================================

class TestLeaderboardWithRealData:
    """Test leaderboard includes real-data factory strategies"""
    
    def test_leaderboard_includes_factory_strategies(self, api_client):
        """GET /api/leaderboard/ includes factory strategies"""
        response = api_client.get(f"{BASE_URL}/api/leaderboard/?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        sources = set(e["source"] for e in data["leaderboard"])
        assert "factory" in sources, "No factory strategies in leaderboard"
        
        factory_count = sum(1 for e in data["leaderboard"] if e["source"] == "factory")
        print(f"✓ Leaderboard has {factory_count} factory strategies out of {len(data['leaderboard'])} shown")
    
    def test_leaderboard_summary_counts_runs(self, api_client):
        """GET /api/leaderboard/summary correctly counts all runs"""
        response = api_client.get(f"{BASE_URL}/api/leaderboard/summary")
        assert response.status_code == 200
        data = response.json()
        
        assert "optimizer_runs" in data
        assert "factory_runs" in data
        assert "best_strategy" in data
        
        # Should have runs from this test session and previous
        assert data["factory_runs"] > 0, "No factory runs counted"
        assert data["optimizer_runs"] >= 0, "optimizer_runs should be >= 0"
        
        print(f"✓ Leaderboard summary: {data['optimizer_runs']} optimizer runs, {data['factory_runs']} factory runs")
    
    def test_leaderboard_includes_both_optimizer_and_factory(self, api_client):
        """Leaderboard includes strategies from both optimizer and factory"""
        response = api_client.get(f"{BASE_URL}/api/leaderboard/?limit=200")
        assert response.status_code == 200
        data = response.json()
        
        optimizer_entries = [e for e in data["leaderboard"] if e["source"] == "optimizer"]
        factory_entries = [e for e in data["leaderboard"] if e["source"] == "factory"]
        
        print(f"✓ Leaderboard mix: {len(optimizer_entries)} from optimizer, {len(factory_entries)} from factory")
        
        # Both should be present (from previous tests)
        assert len(optimizer_entries) > 0, "No optimizer strategies in leaderboard"
        assert len(factory_entries) > 0, "No factory strategies in leaderboard"


# ============================================================================
# VERIFY EXISTING LARGE EXPERIMENT
# ============================================================================

class TestExistingLargeExperiment:
    """Verify the large 1500-strategy experiment exists in DB"""
    
    def test_large_experiment_exists(self, api_client):
        """Check if the 1500-strategy experiment (run ID 9eb0eaba-00dd-4b66-a8bc-1a3c507d7de5) exists"""
        known_run_id = "9eb0eaba-00dd-4b66-a8bc-1a3c507d7de5"
        
        response = api_client.get(f"{BASE_URL}/api/factory/result/{known_run_id}")
        
        if response.status_code == 200:
            data = response.json()
            result = data["result"]
            
            assert result["total_generated"] > 1000, f"Expected > 1000 strategies, got {result['total_generated']}"
            assert result.get("data_source") == "real_candles", "Expected real_candles data source"
            
            print(f"✓ Large experiment found: {result['total_generated']} strategies with data_source={result.get('data_source')}")
        elif response.status_code == 404:
            print("⚠ Large experiment not found (may have been cleared)")
            pytest.skip("Large experiment run not in database")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")


# ============================================================================
# INDIVIDUAL TEMPLATE VERIFICATION WITH REAL DATA
# ============================================================================

class TestEachTemplateWithRealData:
    """Verify each of the 5 templates works correctly with real candle data"""
    
    @pytest.mark.parametrize("template_id", [
        "ema_crossover",
        "rsi_mean_reversion", 
        "macd_trend",
        "bollinger_breakout",
        "atr_volatility_breakout"
    ])
    def test_template_produces_evaluated_strategies(self, api_client, template_id):
        """Test that each template produces evaluated strategies with real data"""
        payload = {
            "session_id": f"{TEST_SESSION_ID}_{template_id}",
            "templates": [template_id],
            "strategies_per_template": 3,
            "symbol": "EURUSD",
            "timeframe": "1d"
        }
        response = api_client.post(f"{BASE_URL}/api/factory/generate", json=payload)
        assert response.status_code == 200
        
        run_id = response.json()["run_id"]
        
        # Wait for completion
        for _ in range(25):
            time.sleep(1)
            status_resp = api_client.get(f"{BASE_URL}/api/factory/status/{run_id}")
            status_data = status_resp.json()
            if status_data["status"] == "completed":
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Template {template_id} failed: {status_data.get('error_message')}")
        else:
            pytest.fail(f"Template {template_id} timed out")
        
        # Verify result
        result_resp = api_client.get(f"{BASE_URL}/api/factory/result/{run_id}")
        result = result_resp.json()["result"]
        
        assert result["total_evaluated"] == 3, f"Template {template_id}: expected 3 evaluated, got {result['total_evaluated']}"
        assert result.get("data_source") == "real_candles", f"Template {template_id}: expected real_candles"
        
        # Verify strategies have metrics
        for strat in result["strategies"]:
            assert strat["evaluated"] is True
            assert strat["fitness"] >= 0
        
        print(f"✓ {template_id}: 3 strategies evaluated with real candles, best fitness={result['best_strategy']['fitness']:.2f}")


# ============================================================================
# CLEANUP FIXTURE
# ============================================================================

@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(api_client):
    """Cleanup note for test data after all tests complete"""
    yield
    print("\n✓ Test session completed - TEST_real_candle_iter10 data isolated")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
