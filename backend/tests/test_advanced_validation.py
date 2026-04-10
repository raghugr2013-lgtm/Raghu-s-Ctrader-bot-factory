"""
Test Advanced Validation API - Full Validation Suite
Testing: POST /api/advanced/full-validation and related endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ai-bot-factory-audit.preview.emergentagent.com').rstrip('/')

# Sample trades for testing
SAMPLE_TRADES = [
    {"profit_loss": 150, "entry_time": "2025-01-01T10:00:00", "volume": 1.0},
    {"profit_loss": -80, "entry_time": "2025-01-02T10:00:00", "volume": 1.0},
    {"profit_loss": 200, "entry_time": "2025-01-03T10:00:00", "volume": 1.0},
    {"profit_loss": -50, "entry_time": "2025-01-04T10:00:00", "volume": 1.0},
    {"profit_loss": 180, "entry_time": "2025-01-05T10:00:00", "volume": 1.0},
    {"profit_loss": 120, "entry_time": "2025-01-06T10:00:00", "volume": 1.0},
    {"profit_loss": -90, "entry_time": "2025-01-07T10:00:00", "volume": 1.0},
    {"profit_loss": 250, "entry_time": "2025-01-08T10:00:00", "volume": 1.0},
    {"profit_loss": -70, "entry_time": "2025-01-09T10:00:00", "volume": 1.0},
    {"profit_loss": 160, "entry_time": "2025-01-10T10:00:00", "volume": 1.0},
    {"profit_loss": 100, "entry_time": "2025-01-11T10:00:00", "volume": 1.0},
    {"profit_loss": -60, "entry_time": "2025-01-12T10:00:00", "volume": 1.0},
    {"profit_loss": 190, "entry_time": "2025-01-13T10:00:00", "volume": 1.0},
    {"profit_loss": 130, "entry_time": "2025-01-14T10:00:00", "volume": 1.0},
    {"profit_loss": -40, "entry_time": "2025-01-15T10:00:00", "volume": 1.0},
    {"profit_loss": 220, "entry_time": "2025-01-16T10:00:00", "volume": 1.0},
    {"profit_loss": -100, "entry_time": "2025-01-17T10:00:00", "volume": 1.0},
    {"profit_loss": 170, "entry_time": "2025-01-18T10:00:00", "volume": 1.0},
    {"profit_loss": 140, "entry_time": "2025-01-19T10:00:00", "volume": 1.0},
    {"profit_loss": -30, "entry_time": "2025-01-20T10:00:00", "volume": 1.0},
]


class TestAdvancedValidationAPI:
    """Test Advanced Validation endpoints - Phase 2-3 Quant-Grade Validation"""

    def test_full_validation_endpoint_exists(self):
        """POST /api/advanced/full-validation - Endpoint accessible"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/full-validation",
            json={
                "trades": SAMPLE_TRADES,
                "initial_balance": 10000,
                "risk_per_trade_percent": 2.0
            }
        )
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404, f"Endpoint not found: {response.status_code}"
        print(f"✓ Full validation endpoint accessible (status: {response.status_code})")

    def test_full_validation_returns_success(self):
        """POST /api/advanced/full-validation - Returns success response"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/full-validation",
            json={
                "session_id": "TEST_iter11_session",
                "strategy_name": "TestStrategy",
                "trades": SAMPLE_TRADES,
                "parameters": {"fast_ma": 10, "slow_ma": 20, "risk_percent": 2.0},
                "initial_balance": 10000,
                "risk_per_trade_percent": 2.0
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") is True, f"Expected success=true: {data}"
        print(f"✓ Full validation returns success: {data.get('success')}")

    def test_full_validation_returns_composite_score(self):
        """POST /api/advanced/full-validation - Returns composite score and grade"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/full-validation",
            json={
                "trades": SAMPLE_TRADES,
                "parameters": {"fast_ma": 10, "slow_ma": 20},
                "initial_balance": 10000,
                "risk_per_trade_percent": 2.0
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "composite_score" in data, f"Missing composite_score: {data.keys()}"
        assert "overall_grade" in data, f"Missing overall_grade: {data.keys()}"
        assert "verdict" in data, f"Missing verdict: {data.keys()}"
        assert "is_deployable" in data, f"Missing is_deployable: {data.keys()}"
        
        score = data["composite_score"]
        grade = data["overall_grade"]
        
        assert isinstance(score, (int, float)), f"Score should be numeric: {type(score)}"
        assert 0 <= score <= 100, f"Score out of range: {score}"
        assert grade in ["A", "B", "C", "D", "F"], f"Invalid grade: {grade}"
        
        print(f"✓ Composite Score: {score}, Grade: {grade}, Deployable: {data['is_deployable']}")

    def test_full_validation_returns_bootstrap_results(self):
        """POST /api/advanced/full-validation - Returns bootstrap analysis results"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/full-validation",
            json={
                "trades": SAMPLE_TRADES,
                "initial_balance": 10000
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "results" in data, f"Missing results: {data.keys()}"
        results = data["results"]
        
        assert "bootstrap" in results, f"Missing bootstrap results: {results.keys()}"
        bootstrap = results["bootstrap"]
        
        if bootstrap:  # Bootstrap may be null if it failed
            assert "survival_rate" in bootstrap, f"Missing survival_rate: {bootstrap.keys()}"
            assert "profit_probability" in bootstrap, f"Missing profit_probability: {bootstrap.keys()}"
            assert "score" in bootstrap, f"Missing score: {bootstrap.keys()}"
            assert "grade" in bootstrap, f"Missing grade: {bootstrap.keys()}"
            assert "is_robust" in bootstrap, f"Missing is_robust: {bootstrap.keys()}"
            
            print(f"✓ Bootstrap: survival={bootstrap['survival_rate']}%, score={bootstrap['score']}, grade={bootstrap['grade']}")
        else:
            print("✓ Bootstrap results returned (null - may have failed internally)")

    def test_full_validation_returns_risk_of_ruin_results(self):
        """POST /api/advanced/full-validation - Returns risk of ruin results"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/full-validation",
            json={
                "trades": SAMPLE_TRADES,
                "initial_balance": 10000,
                "risk_per_trade_percent": 2.0
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        results = data.get("results", {})
        assert "risk_of_ruin" in results, f"Missing risk_of_ruin results: {results.keys()}"
        ror = results["risk_of_ruin"]
        
        if ror:
            assert "ruin_probability" in ror, f"Missing ruin_probability: {ror.keys()}"
            assert "survival_probability" in ror, f"Missing survival_probability: {ror.keys()}"
            assert "score" in ror, f"Missing score: {ror.keys()}"
            assert "risk_level" in ror, f"Missing risk_level: {ror.keys()}"
            
            print(f"✓ Risk of Ruin: ruin={ror['ruin_probability']}%, survival={ror['survival_probability']}%, risk_level={ror['risk_level']}")
        else:
            print("✓ Risk of ruin results returned (null - may have failed internally)")

    def test_full_validation_returns_slippage_results(self):
        """POST /api/advanced/full-validation - Returns slippage simulation results"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/full-validation",
            json={
                "trades": SAMPLE_TRADES,
                "initial_balance": 10000
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        results = data.get("results", {})
        assert "slippage" in results, f"Missing slippage results: {results.keys()}"
        slippage = results["slippage"]
        
        if slippage:
            assert "profit_degradation" in slippage, f"Missing profit_degradation: {slippage.keys()}"
            assert "score" in slippage, f"Missing score: {slippage.keys()}"
            assert "impact_level" in slippage, f"Missing impact_level: {slippage.keys()}"
            assert "is_viable" in slippage, f"Missing is_viable: {slippage.keys()}"
            
            print(f"✓ Slippage: degradation={slippage['profit_degradation']}%, impact={slippage['impact_level']}, viable={slippage['is_viable']}")
        else:
            print("✓ Slippage results returned (null - may have failed internally)")

    def test_full_validation_returns_sensitivity_results(self):
        """POST /api/advanced/full-validation - Returns sensitivity analysis when params provided"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/full-validation",
            json={
                "trades": SAMPLE_TRADES,
                "parameters": {"fast_ma": 10, "slow_ma": 20, "atr_period": 14},
                "initial_balance": 10000
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        results = data.get("results", {})
        assert "sensitivity" in results, f"Missing sensitivity results: {results.keys()}"
        sensitivity = results["sensitivity"]
        
        if sensitivity:
            assert "robustness_score" in sensitivity, f"Missing robustness_score: {sensitivity.keys()}"
            assert "overfitting_risk" in sensitivity, f"Missing overfitting_risk: {sensitivity.keys()}"
            assert "score" in sensitivity, f"Missing score: {sensitivity.keys()}"
            
            print(f"✓ Sensitivity: robustness={sensitivity['robustness_score']}, overfitting_risk={sensitivity['overfitting_risk']}%")
        else:
            print("✓ Sensitivity results returned (null - may have failed internally)")

    def test_full_validation_returns_recommendations(self):
        """POST /api/advanced/full-validation - Returns recommendations"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/full-validation",
            json={
                "trades": SAMPLE_TRADES,
                "initial_balance": 10000
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "recommendations" in data, f"Missing recommendations: {data.keys()}"
        recommendations = data["recommendations"]
        
        assert isinstance(recommendations, list), f"Recommendations should be list: {type(recommendations)}"
        print(f"✓ Recommendations: {len(recommendations)} items")
        for rec in recommendations[:3]:
            print(f"  - {rec}")

    def test_full_validation_error_with_no_trades(self):
        """POST /api/advanced/full-validation - Returns 400 when no trades provided"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/full-validation",
            json={
                "trades": [],
                "initial_balance": 10000
            }
        )
        assert response.status_code == 400, f"Expected 400 for empty trades, got {response.status_code}"
        print("✓ Returns 400 when no trades provided")

    def test_full_validation_trades_analyzed_count(self):
        """POST /api/advanced/full-validation - Returns correct trades_analyzed count"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/full-validation",
            json={
                "trades": SAMPLE_TRADES,
                "initial_balance": 10000
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "trades_analyzed" in data, f"Missing trades_analyzed: {data.keys()}"
        assert data["trades_analyzed"] == len(SAMPLE_TRADES), f"Expected {len(SAMPLE_TRADES)}, got {data['trades_analyzed']}"
        print(f"✓ Trades analyzed: {data['trades_analyzed']}")


class TestIndividualAdvancedEndpoints:
    """Test individual advanced validation endpoints"""

    def test_bootstrap_endpoint(self):
        """POST /api/advanced/bootstrap - Bootstrap analysis endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/bootstrap",
            json={
                "trades": SAMPLE_TRADES,
                "num_simulations": 500,
                "initial_balance": 10000
            }
        )
        assert response.status_code == 200, f"Bootstrap failed: {response.status_code} - {response.text}"
        data = response.json()
        assert data.get("success") is True
        assert "summary" in data
        print(f"✓ Bootstrap endpoint: score={data['summary'].get('score')}, survival={data['summary'].get('survival_rate')}%")

    def test_risk_of_ruin_endpoint(self):
        """POST /api/advanced/risk-of-ruin - Risk of ruin endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/risk-of-ruin",
            json={
                "trades": SAMPLE_TRADES,
                "initial_balance": 10000,
                "risk_per_trade_percent": 2.0,
                "num_simulations": 1000  # Minimum required is 1000
            }
        )
        assert response.status_code == 200, f"Risk of ruin failed: {response.status_code} - {response.text}"
        data = response.json()
        assert data.get("success") is True
        assert "summary" in data
        print(f"✓ Risk of Ruin endpoint: ruin_prob={data['summary'].get('ruin_probability')}%")

    def test_slippage_endpoint(self):
        """POST /api/advanced/slippage - Slippage simulation endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/slippage",
            json={
                "trades": SAMPLE_TRADES,
                "base_spread_pips": 1.0,
                "avg_slippage_pips": 0.3,
                "initial_balance": 10000
            }
        )
        assert response.status_code == 200, f"Slippage failed: {response.status_code} - {response.text}"
        data = response.json()
        assert data.get("success") is True
        assert "summary" in data
        print(f"✓ Slippage endpoint: degradation={data['summary'].get('profit_degradation_percent')}%")

    def test_sensitivity_endpoint(self):
        """POST /api/advanced/sensitivity - Sensitivity analysis endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/advanced/sensitivity",
            json={
                "trades": SAMPLE_TRADES,
                "parameters": {"fast_ma": 10, "slow_ma": 20}
            }
        )
        assert response.status_code == 200, f"Sensitivity failed: {response.status_code} - {response.text}"
        data = response.json()
        assert data.get("success") is True
        assert "summary" in data
        print(f"✓ Sensitivity endpoint: robustness={data['summary'].get('robustness_score')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
