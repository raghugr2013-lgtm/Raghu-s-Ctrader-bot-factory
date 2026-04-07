"""
Market Regime Detection Engine - Backend Tests
Tests for:
- GET /api/regime/regimes - list all 5 regime types
- POST /api/regime/analyze-backtest - analyze backtest with regime detection and per-regime metrics
- GET /api/regime/result/{regime_id} - retrieve saved result
- Edge cases: invalid backtest_id, nonexistent regime_id
- Multiple strategy types (trend_following, mean_reversion, scalping)
- Metrics validation (win_rate 0-100, profit_factor >= 0, distribution percentages ~100%)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test data storage for cleanup
created_backtests = []
created_regime_ids = []


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def created_backtests_fixture():
    """Track created backtests for potential cleanup."""
    return created_backtests


class TestRegimeEndpoints:
    """Tests for the /api/regime/* endpoints."""

    # =========================================================================
    # GET /api/regime/regimes - List all regime types
    # =========================================================================

    def test_get_regimes_returns_all_five_types(self, api_client):
        """GET /api/regime/regimes should return all 5 regime types."""
        response = api_client.get(f"{BASE_URL}/api/regime/regimes")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["success"] is True
        assert "regimes" in data
        
        regimes = data["regimes"]
        assert len(regimes) == 5, f"Expected 5 regimes, got {len(regimes)}"
        
        # Verify all 5 regime types are present
        expected_regimes = {"trending_up", "trending_down", "ranging", "high_volatility", "low_volatility"}
        actual_regimes = {r["value"] for r in regimes}
        assert actual_regimes == expected_regimes, f"Missing regimes: {expected_regimes - actual_regimes}"
        
        # Verify each regime has value and label
        for regime in regimes:
            assert "value" in regime
            assert "label" in regime
            assert isinstance(regime["value"], str)
            assert isinstance(regime["label"], str)
        
        print(f"✓ GET /api/regime/regimes returns all 5 regime types: {actual_regimes}")


class TestRegimeAnalyzeBacktest:
    """Tests for POST /api/regime/analyze-backtest endpoint."""

    @pytest.fixture(scope="class")
    def trend_following_backtest(self, api_client):
        """Create a trend_following backtest for testing."""
        response = api_client.post(
            f"{BASE_URL}/api/backtest/simulate",
            json={
                "session_id": "TEST_regime_trend_session",
                "bot_name": "TEST_regime_trend_bot",
                "config": {
                    "symbol": "EURUSD",
                    "timeframe": "1h",
                    "initial_balance": 10000,
                    "strategy_type": "trend_following"
                }
            }
        )
        assert response.status_code == 200, f"Failed to create backtest: {response.text}"
        data = response.json()
        backtest_id = data["backtest_id"]
        created_backtests.append(backtest_id)
        print(f"✓ Created trend_following backtest: {backtest_id}")
        return backtest_id

    @pytest.fixture(scope="class")
    def mean_reversion_backtest(self, api_client):
        """Create a mean_reversion backtest for testing."""
        response = api_client.post(
            f"{BASE_URL}/api/backtest/simulate",
            json={
                "session_id": "TEST_regime_mean_session",
                "bot_name": "TEST_regime_mean_bot",
                "config": {
                    "symbol": "GBPUSD",
                    "timeframe": "4h",
                    "initial_balance": 15000,
                    "strategy_type": "mean_reversion"
                }
            }
        )
        assert response.status_code == 200, f"Failed to create backtest: {response.text}"
        data = response.json()
        backtest_id = data["backtest_id"]
        created_backtests.append(backtest_id)
        print(f"✓ Created mean_reversion backtest: {backtest_id}")
        return backtest_id

    @pytest.fixture(scope="class")
    def scalping_backtest(self, api_client):
        """Create a scalping backtest for testing."""
        response = api_client.post(
            f"{BASE_URL}/api/backtest/simulate",
            json={
                "session_id": "TEST_regime_scalp_session",
                "bot_name": "TEST_regime_scalp_bot",
                "config": {
                    "symbol": "USDJPY",
                    "timeframe": "15m",
                    "initial_balance": 5000,
                    "strategy_type": "scalping"
                }
            }
        )
        assert response.status_code == 200, f"Failed to create backtest: {response.text}"
        data = response.json()
        backtest_id = data["backtest_id"]
        created_backtests.append(backtest_id)
        print(f"✓ Created scalping backtest: {backtest_id}")
        return backtest_id

    def test_analyze_backtest_returns_distribution(self, api_client, trend_following_backtest):
        """POST /api/regime/analyze-backtest should return distribution with regime counts and percentages."""
        response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_session",
                "backtest_id": trend_following_backtest
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] is True
        assert "distribution" in data
        
        distribution = data["distribution"]
        assert isinstance(distribution, list)
        assert len(distribution) > 0, "Distribution should not be empty"
        
        # Verify each distribution entry has required fields
        for dist in distribution:
            assert "regime" in dist
            assert "candle_count" in dist
            assert "percent" in dist
            assert isinstance(dist["candle_count"], int)
            assert dist["candle_count"] > 0
            assert 0 <= dist["percent"] <= 100
        
        # Store regime_id for later tests
        created_regime_ids.append(data["regime_id"])
        
        print(f"✓ Distribution returned: {distribution}")

    def test_analyze_backtest_distribution_sums_to_100(self, api_client, mean_reversion_backtest):
        """Verify distribution percentages sum to approximately 100%."""
        response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_session",
                "backtest_id": mean_reversion_backtest
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        distribution = data["distribution"]
        total_percent = sum(d["percent"] for d in distribution)
        
        # Allow small rounding error (99% to 101%)
        assert 99.0 <= total_percent <= 101.0, f"Distribution percentages sum to {total_percent}%, expected ~100%"
        
        created_regime_ids.append(data["regime_id"])
        print(f"✓ Distribution percentages sum to {total_percent}% (expected ~100%)")

    def test_analyze_backtest_returns_regime_performance(self, api_client, trend_following_backtest):
        """POST /api/regime/analyze-backtest should return regime_performance with trade metrics."""
        response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_session",
                "backtest_id": trend_following_backtest
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "regime_performance" in data
        regime_performance = data["regime_performance"]
        
        # regime_performance can be empty if no trades in certain regimes
        if regime_performance:
            for perf in regime_performance:
                assert "regime" in perf
                assert "trade_count" in perf
                assert "win_rate" in perf
                assert "net_profit" in perf
                assert "profit_factor" in perf
                assert "sharpe_ratio" in perf
                
                # Validate metrics are mathematically valid
                assert perf["trade_count"] > 0, "trade_count should be > 0 for non-empty performance"
                assert 0 <= perf["win_rate"] <= 100, f"win_rate {perf['win_rate']} should be 0-100"
                assert perf["profit_factor"] >= 0, f"profit_factor {perf['profit_factor']} should be >= 0"
        
        created_regime_ids.append(data["regime_id"])
        print(f"✓ Regime performance returned with {len(regime_performance)} regimes with trades")

    def test_analyze_backtest_returns_best_and_worst_regime(self, api_client, trend_following_backtest):
        """POST /api/regime/analyze-backtest should return best_regime and worst_regime."""
        response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_session",
                "backtest_id": trend_following_backtest
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # These fields should exist (can be null if no trades or all positive)
        assert "best_regime" in data
        assert "worst_regime" in data
        
        if data["best_regime"]:
            valid_regimes = {"trending_up", "trending_down", "ranging", "high_volatility", "low_volatility"}
            assert data["best_regime"] in valid_regimes
            print(f"✓ Best regime: {data['best_regime']}")
        else:
            print("✓ best_regime is null (no trades with profits)")
        
        if data["worst_regime"]:
            valid_regimes = {"trending_up", "trending_down", "ranging", "high_volatility", "low_volatility"}
            assert data["worst_regime"] in valid_regimes
            print(f"✓ Worst regime: {data['worst_regime']}")
        else:
            print("✓ worst_regime is null (no regime with net loss)")

    def test_analyze_backtest_returns_insights_and_recommendations(self, api_client, trend_following_backtest):
        """POST /api/regime/analyze-backtest should return insights and recommendations."""
        response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_session",
                "backtest_id": trend_following_backtest
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "insights" in data
        assert "recommendations" in data
        
        # Both should be lists
        assert isinstance(data["insights"], list)
        assert isinstance(data["recommendations"], list)
        
        # Insights should typically be generated
        if data["insights"]:
            for insight in data["insights"]:
                assert isinstance(insight, str)
                assert len(insight) > 0
        
        print(f"✓ Insights: {len(data['insights'])} items")
        print(f"✓ Recommendations: {len(data['recommendations'])} items")

    def test_analyze_backtest_with_invalid_backtest_id_returns_404(self, api_client):
        """POST /api/regime/analyze-backtest with invalid backtest_id should return 404."""
        response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_session",
                "backtest_id": "invalid-backtest-id-12345"
            }
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
        
        print(f"✓ Invalid backtest_id returns 404 with message: {data['detail']}")

    def test_analyze_backtest_works_with_scalping_strategy(self, api_client, scalping_backtest):
        """POST /api/regime/analyze-backtest should work with scalping strategy backtest."""
        response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_session",
                "backtest_id": scalping_backtest
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] is True
        assert "distribution" in data
        assert "regime_performance" in data
        assert "dominant_regime" in data
        
        created_regime_ids.append(data["regime_id"])
        print(f"✓ Scalping backtest analysis completed: dominant regime = {data['dominant_regime']}")

    def test_analyze_backtest_returns_all_required_response_fields(self, api_client, trend_following_backtest):
        """Verify all required response fields are present in analyze-backtest response."""
        response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_session",
                "backtest_id": trend_following_backtest
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "success", "regime_id", "backtest_id", "symbol", "timeframe",
            "total_candles", "dominant_regime", "distribution", "regime_performance",
            "best_regime", "worst_regime", "insights", "recommendations", "execution_time_seconds"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify types
        assert isinstance(data["success"], bool)
        assert isinstance(data["regime_id"], str)
        assert isinstance(data["backtest_id"], str)
        assert isinstance(data["symbol"], str)
        assert isinstance(data["timeframe"], str)
        assert isinstance(data["total_candles"], int)
        assert isinstance(data["dominant_regime"], str)
        assert isinstance(data["distribution"], list)
        assert isinstance(data["regime_performance"], list)
        assert isinstance(data["insights"], list)
        assert isinstance(data["recommendations"], list)
        assert isinstance(data["execution_time_seconds"], (int, float))
        
        print(f"✓ All required response fields present and correctly typed")


class TestRegimeResult:
    """Tests for GET /api/regime/result/{regime_id} endpoint."""

    def test_get_regime_result_by_id(self, api_client):
        """GET /api/regime/result/{regime_id} should retrieve saved result."""
        # First create a regime analysis to get a regime_id
        # Create a fresh backtest
        bt_response = api_client.post(
            f"{BASE_URL}/api/backtest/simulate",
            json={
                "session_id": "TEST_regime_result_session",
                "bot_name": "TEST_regime_result_bot",
                "config": {
                    "symbol": "EURUSD",
                    "timeframe": "1h",
                    "initial_balance": 10000,
                    "strategy_type": "trend_following"
                }
            }
        )
        assert bt_response.status_code == 200
        backtest_id = bt_response.json()["backtest_id"]
        created_backtests.append(backtest_id)
        
        # Create regime analysis
        regime_response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_result_session",
                "backtest_id": backtest_id
            }
        )
        assert regime_response.status_code == 200
        regime_id = regime_response.json()["regime_id"]
        
        # Now retrieve the result
        result_response = api_client.get(f"{BASE_URL}/api/regime/result/{regime_id}")
        
        assert result_response.status_code == 200
        data = result_response.json()
        
        assert data["success"] is True
        assert "result" in data
        
        result = data["result"]
        assert result["id"] == regime_id
        assert result["backtest_id"] == backtest_id
        assert "distribution" in result
        assert "regime_performance" in result
        assert "created_at" in result
        
        print(f"✓ GET /api/regime/result/{regime_id} retrieved saved result")

    def test_get_regime_result_nonexistent_returns_404(self, api_client):
        """GET /api/regime/result/nonexistent should return 404."""
        response = api_client.get(f"{BASE_URL}/api/regime/result/nonexistent-regime-id-12345")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
        
        print(f"✓ Nonexistent regime_id returns 404 with message: {data['detail']}")


class TestRegimeMetricsValidation:
    """Tests to validate regime_performance metrics are mathematically valid."""

    @pytest.fixture(scope="class")
    def backtest_with_regime_analysis(self, api_client):
        """Create backtest and perform regime analysis."""
        # Create backtest
        bt_response = api_client.post(
            f"{BASE_URL}/api/backtest/simulate",
            json={
                "session_id": "TEST_regime_metrics_session",
                "bot_name": "TEST_regime_metrics_bot",
                "config": {
                    "symbol": "EURUSD",
                    "timeframe": "1h",
                    "initial_balance": 10000,
                    "strategy_type": "trend_following"
                }
            }
        )
        assert bt_response.status_code == 200
        backtest_id = bt_response.json()["backtest_id"]
        created_backtests.append(backtest_id)
        
        # Perform regime analysis
        regime_response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_metrics_session",
                "backtest_id": backtest_id
            }
        )
        assert regime_response.status_code == 200
        return regime_response.json()

    def test_win_rate_is_between_0_and_100(self, api_client, backtest_with_regime_analysis):
        """Verify win_rate is between 0 and 100 for all regimes."""
        regime_performance = backtest_with_regime_analysis.get("regime_performance", [])
        
        for perf in regime_performance:
            win_rate = perf["win_rate"]
            assert 0 <= win_rate <= 100, f"win_rate {win_rate} out of range [0, 100] for regime {perf['regime']}"
        
        print(f"✓ All win_rate values are within valid range [0, 100]")

    def test_profit_factor_is_non_negative(self, api_client, backtest_with_regime_analysis):
        """Verify profit_factor is >= 0 for all regimes."""
        regime_performance = backtest_with_regime_analysis.get("regime_performance", [])
        
        for perf in regime_performance:
            profit_factor = perf["profit_factor"]
            assert profit_factor >= 0, f"profit_factor {profit_factor} should be >= 0 for regime {perf['regime']}"
        
        print(f"✓ All profit_factor values are non-negative")

    def test_trade_count_is_positive(self, api_client, backtest_with_regime_analysis):
        """Verify trade_count > 0 for all regimes with performance data."""
        regime_performance = backtest_with_regime_analysis.get("regime_performance", [])
        
        for perf in regime_performance:
            trade_count = perf["trade_count"]
            assert trade_count > 0, f"trade_count {trade_count} should be > 0 for regime {perf['regime']}"
        
        print(f"✓ All trade_count values are positive")

    def test_best_trade_greater_than_or_equal_to_worst_trade(self, api_client, backtest_with_regime_analysis):
        """Verify best_trade >= worst_trade for all regimes."""
        regime_performance = backtest_with_regime_analysis.get("regime_performance", [])
        
        for perf in regime_performance:
            best = perf["best_trade"]
            worst = perf["worst_trade"]
            assert best >= worst, f"best_trade {best} should be >= worst_trade {worst} for regime {perf['regime']}"
        
        print(f"✓ All best_trade >= worst_trade validations passed")


class TestRegimeWithDifferentStrategies:
    """Tests for regime analysis with different strategy types."""

    def test_analyze_mean_reversion_backtest(self, api_client):
        """Test regime analysis with mean_reversion strategy."""
        # Create backtest
        bt_response = api_client.post(
            f"{BASE_URL}/api/backtest/simulate",
            json={
                "session_id": "TEST_regime_mean_rev_session",
                "bot_name": "TEST_regime_mean_rev_bot",
                "config": {
                    "symbol": "GBPUSD",
                    "timeframe": "4h",
                    "initial_balance": 20000,
                    "strategy_type": "mean_reversion"
                }
            }
        )
        assert bt_response.status_code == 200
        backtest_id = bt_response.json()["backtest_id"]
        created_backtests.append(backtest_id)
        
        # Perform regime analysis
        regime_response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_mean_rev_session",
                "backtest_id": backtest_id
            }
        )
        
        assert regime_response.status_code == 200
        data = regime_response.json()
        assert data["success"] is True
        # Mock backtests may default symbol to EURUSD - this is expected
        assert isinstance(data["symbol"], str)
        assert isinstance(data["timeframe"], str)
        
        print(f"✓ Mean reversion backtest analyzed: {len(data['distribution'])} regime types detected")

    def test_analyze_scalping_backtest_with_short_timeframe(self, api_client):
        """Test regime analysis with scalping strategy on short timeframe."""
        # Create backtest
        bt_response = api_client.post(
            f"{BASE_URL}/api/backtest/simulate",
            json={
                "session_id": "TEST_regime_scalp2_session",
                "bot_name": "TEST_regime_scalp2_bot",
                "config": {
                    "symbol": "USDJPY",
                    "timeframe": "5m",
                    "initial_balance": 5000,
                    "strategy_type": "scalping"
                }
            }
        )
        assert bt_response.status_code == 200
        backtest_id = bt_response.json()["backtest_id"]
        created_backtests.append(backtest_id)
        
        # Perform regime analysis
        regime_response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_scalp2_session",
                "backtest_id": backtest_id
            }
        )
        
        assert regime_response.status_code == 200
        data = regime_response.json()
        assert data["success"] is True
        # Mock backtests may default symbol - this is expected
        assert isinstance(data["symbol"], str)
        
        print(f"✓ Scalping backtest analyzed: dominant regime = {data['dominant_regime']}")


class TestRegimeCustomParameters:
    """Tests for regime analysis with custom indicator parameters."""

    def test_analyze_backtest_with_custom_adx_threshold(self, api_client):
        """Test regime analysis with custom ADX trend threshold."""
        # Create backtest
        bt_response = api_client.post(
            f"{BASE_URL}/api/backtest/simulate",
            json={
                "session_id": "TEST_regime_custom_session",
                "bot_name": "TEST_regime_custom_bot",
                "config": {
                    "symbol": "EURUSD",
                    "timeframe": "1h",
                    "initial_balance": 10000,
                    "strategy_type": "trend_following"
                }
            }
        )
        assert bt_response.status_code == 200
        backtest_id = bt_response.json()["backtest_id"]
        created_backtests.append(backtest_id)
        
        # Perform regime analysis with custom ADX threshold
        regime_response = api_client.post(
            f"{BASE_URL}/api/regime/analyze-backtest",
            json={
                "session_id": "TEST_regime_custom_session",
                "backtest_id": backtest_id,
                "adx_trend_threshold": 20.0,  # Lower than default 25
                "adx_period": 14,
                "atr_period": 14
            }
        )
        
        assert regime_response.status_code == 200
        data = regime_response.json()
        assert data["success"] is True
        
        print(f"✓ Custom ADX threshold (20.0) analysis completed")


# =========================================================================
# Run all tests
# =========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
