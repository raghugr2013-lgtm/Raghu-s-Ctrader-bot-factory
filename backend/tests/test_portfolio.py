"""
Portfolio Strategy Engine - Backend API Tests
Phase 7: Portfolio Management, Correlation, Backtesting, Monte Carlo, Allocation Optimization

Endpoints tested:
- POST /api/portfolio/create - creates a new empty portfolio
- GET /api/portfolio/{portfolio_id} - returns portfolio with all nested data
- GET /api/portfolio/list/{session_id} - lists portfolios for a session
- POST /api/portfolio/{portfolio_id}/add-strategy - adds strategy from backtest to portfolio
- DELETE /api/portfolio/{portfolio_id}/strategy/{strategy_id} - removes strategy from portfolio
- POST /api/portfolio/{portfolio_id}/analyze-correlation - runs correlation analysis
- POST /api/portfolio/{portfolio_id}/backtest - runs combined portfolio backtest
- POST /api/portfolio/{portfolio_id}/monte-carlo - runs portfolio Monte Carlo simulation
- POST /api/portfolio/{portfolio_id}/optimize - optimizes allocation
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="session")
def api_client():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ---------------------------------------------------------------------------
# Test: Health check and API connectivity
# ---------------------------------------------------------------------------

class TestHealthCheck:
    """Basic connectivity tests."""
    
    def test_api_root_accessible(self, api_client):
        """Verify API root is accessible."""
        response = api_client.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        print(f"API root status: {response.status_code}")


# ---------------------------------------------------------------------------
# Test: Portfolio CRUD Operations
# ---------------------------------------------------------------------------

class TestPortfolioCRUD:
    """Portfolio create, read, list operations."""
    
    def test_create_portfolio_success(self, api_client):
        """Test creating a new portfolio."""
        payload = {
            "session_id": f"test_portfolio_{uuid.uuid4().hex[:8]}",
            "name": "TEST_Portfolio_Create",
            "description": "Test portfolio for API testing",
            "initial_balance": 50000.0
        }
        response = api_client.post(f"{BASE_URL}/api/portfolio/create", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Data assertions
        assert data.get("success") is True
        assert "portfolio_id" in data
        assert data.get("name") == "TEST_Portfolio_Create"
        assert len(data.get("portfolio_id", "")) > 0
        
        # Store for later tests
        TestPortfolioCRUD.created_portfolio_id = data["portfolio_id"]
        TestPortfolioCRUD.created_session_id = payload["session_id"]
        print(f"Created portfolio: {data['portfolio_id']}")
    
    def test_get_portfolio_success(self, api_client):
        """Test retrieving a portfolio by ID."""
        # Use existing portfolio from main agent notes
        portfolio_id = "8b3a39fd-373c-4c71-92d6-443d877f04e1"
        
        response = api_client.get(f"{BASE_URL}/api/portfolio/{portfolio_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Data assertions
        assert data.get("success") is True
        assert "portfolio" in data
        
        portfolio = data["portfolio"]
        assert portfolio.get("id") == portfolio_id
        assert "session_id" in portfolio
        assert "name" in portfolio
        assert "strategies" in portfolio
        assert isinstance(portfolio["strategies"], list)
        
        # Check nested data present
        if len(portfolio["strategies"]) > 0:
            strat = portfolio["strategies"][0]
            assert "strategy_id" in strat
            assert "name" in strat
            assert "backtest_id" in strat
            assert "weight" in strat
            print(f"Portfolio has {len(portfolio['strategies'])} strategies")
        
        # Check results if available
        if portfolio.get("correlation_result"):
            assert "average_correlation" in portfolio["correlation_result"]
            print("Correlation result present")
        if portfolio.get("backtest_result"):
            assert "metrics" in portfolio["backtest_result"]
            print("Backtest result present")
        if portfolio.get("monte_carlo_result"):
            assert "profit_probability" in portfolio["monte_carlo_result"]
            print("Monte Carlo result present")
        if portfolio.get("allocation_result"):
            assert "weights" in portfolio["allocation_result"]
            print("Allocation result present")
    
    def test_get_portfolio_not_found(self, api_client):
        """Test 404 for non-existent portfolio."""
        response = api_client.get(f"{BASE_URL}/api/portfolio/nonexistent-portfolio-id-123")
        assert response.status_code == 404
        print("Get non-existent portfolio correctly returns 404")
    
    def test_list_portfolios_success(self, api_client):
        """Test listing portfolios for a session."""
        session_id = "test_session_1"
        response = api_client.get(f"{BASE_URL}/api/portfolio/list/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Data assertions
        assert data.get("success") is True
        assert "portfolios" in data
        assert "count" in data
        assert isinstance(data["portfolios"], list)
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
        
        print(f"Found {data['count']} portfolios for session {session_id}")
    
    def test_list_portfolios_empty_session(self, api_client):
        """Test listing portfolios for non-existent session returns empty."""
        session_id = f"nonexistent_session_{uuid.uuid4().hex[:8]}"
        response = api_client.get(f"{BASE_URL}/api/portfolio/list/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") is True
        assert data.get("count") == 0
        assert data.get("portfolios") == []
        print("Empty session correctly returns empty portfolios list")


# ---------------------------------------------------------------------------
# Test: Add/Remove Strategy
# ---------------------------------------------------------------------------

class TestStrategyManagement:
    """Test adding and removing strategies from portfolios."""
    
    @pytest.fixture(scope="class")
    def test_portfolio_id(self, api_client):
        """Create a test portfolio for strategy management tests."""
        payload = {
            "session_id": f"test_strat_mgmt_{uuid.uuid4().hex[:8]}",
            "name": "TEST_Strategy_Management_Portfolio",
            "description": "Portfolio for strategy management testing"
        }
        response = api_client.post(f"{BASE_URL}/api/portfolio/create", json=payload)
        assert response.status_code == 200
        return response.json()["portfolio_id"]
    
    @pytest.fixture(scope="class")
    def backtest_ids(self, api_client):
        """Create simulated backtests for testing."""
        backtest_ids = []
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        
        for symbol in symbols:
            payload = {
                "session_id": f"test_bt_{uuid.uuid4().hex[:8]}",
                "bot_name": f"TEST_Bot_{symbol}",
                "symbol": symbol,
                "timeframe": "1h",
                "trade_count": 50
            }
            response = api_client.post(f"{BASE_URL}/api/backtest/simulate", json=payload)
            assert response.status_code == 200, f"Failed to create backtest: {response.text}"
            backtest_ids.append(response.json()["backtest_id"])
        
        return backtest_ids
    
    def test_add_strategy_success(self, api_client, test_portfolio_id, backtest_ids):
        """Test adding a strategy to portfolio."""
        payload = {
            "backtest_id": backtest_ids[0],
            "name": "TEST_Strategy_EURUSD"
        }
        response = api_client.post(
            f"{BASE_URL}/api/portfolio/{test_portfolio_id}/add-strategy",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Data assertions
        assert data.get("success") is True
        assert data.get("portfolio_id") == test_portfolio_id
        assert data.get("strategy_added") == "TEST_Strategy_EURUSD"
        assert data.get("total_strategies") == 1
        
        print(f"Added strategy: {data.get('strategy_added')}")
    
    def test_add_strategy_nonexistent_portfolio(self, api_client, backtest_ids):
        """Test 404 when adding to non-existent portfolio."""
        payload = {
            "backtest_id": backtest_ids[0],
            "name": "TEST_Strategy"
        }
        response = api_client.post(
            f"{BASE_URL}/api/portfolio/nonexistent-portfolio-id/add-strategy",
            json=payload
        )
        assert response.status_code == 404
        print("Add strategy to non-existent portfolio correctly returns 404")
    
    def test_add_strategy_nonexistent_backtest(self, api_client, test_portfolio_id):
        """Test 404 when adding with non-existent backtest."""
        payload = {
            "backtest_id": "nonexistent-backtest-id-123",
            "name": "TEST_Strategy_Invalid"
        }
        response = api_client.post(
            f"{BASE_URL}/api/portfolio/{test_portfolio_id}/add-strategy",
            json=payload
        )
        assert response.status_code == 404
        print("Add strategy with non-existent backtest correctly returns 404")
    
    def test_remove_strategy_success(self, api_client, test_portfolio_id, backtest_ids):
        """Test removing a strategy from portfolio."""
        # First add a second strategy
        payload = {
            "backtest_id": backtest_ids[1],
            "name": "TEST_Strategy_To_Remove"
        }
        add_response = api_client.post(
            f"{BASE_URL}/api/portfolio/{test_portfolio_id}/add-strategy",
            json=payload
        )
        assert add_response.status_code == 200
        
        # Get portfolio to find strategy_id
        get_response = api_client.get(f"{BASE_URL}/api/portfolio/{test_portfolio_id}")
        portfolio = get_response.json()["portfolio"]
        strategies = portfolio.get("strategies", [])
        
        # Find the strategy we just added
        strategy_to_remove = None
        for s in strategies:
            if s.get("name") == "TEST_Strategy_To_Remove":
                strategy_to_remove = s
                break
        
        assert strategy_to_remove is not None
        strategy_id = strategy_to_remove["strategy_id"]
        
        # Remove it
        delete_response = api_client.delete(
            f"{BASE_URL}/api/portfolio/{test_portfolio_id}/strategy/{strategy_id}"
        )
        
        assert delete_response.status_code == 200
        data = delete_response.json()
        
        assert data.get("success") is True
        assert "remaining_strategies" in data
        print(f"Removed strategy, remaining: {data.get('remaining_strategies')}")
    
    def test_remove_strategy_nonexistent_portfolio(self, api_client):
        """Test 404 when removing from non-existent portfolio."""
        response = api_client.delete(
            f"{BASE_URL}/api/portfolio/nonexistent-portfolio/strategy/some-strategy-id"
        )
        assert response.status_code == 404
        print("Remove strategy from non-existent portfolio correctly returns 404")


# ---------------------------------------------------------------------------
# Test: Correlation Analysis
# ---------------------------------------------------------------------------

class TestCorrelationAnalysis:
    """Test correlation analysis endpoint."""
    
    def test_correlation_analysis_success(self, api_client):
        """Test correlation analysis with existing portfolio."""
        # Use existing portfolio with 3 strategies
        portfolio_id = "8b3a39fd-373c-4c71-92d6-443d877f04e1"
        
        response = api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/analyze-correlation")
        
        assert response.status_code == 200
        data = response.json()
        
        # Data assertions
        assert data.get("success") is True
        assert data.get("portfolio_id") == portfolio_id
        assert "average_correlation" in data
        assert "diversification_score" in data
        assert "pairs" in data
        assert "recommendations" in data
        
        # Verify types
        assert isinstance(data["average_correlation"], (int, float))
        assert isinstance(data["diversification_score"], (int, float))
        assert isinstance(data["pairs"], list)
        assert isinstance(data["recommendations"], list)
        
        # Check pairs structure
        if len(data["pairs"]) > 0:
            pair = data["pairs"][0]
            assert "strategy_a" in pair
            assert "strategy_b" in pair
            assert "correlation" in pair
            assert "interpretation" in pair
        
        print(f"Correlation analysis: avg={data['average_correlation']}, div_score={data['diversification_score']}")
    
    def test_correlation_requires_two_strategies(self, api_client):
        """Test that correlation requires at least 2 strategies."""
        # Create new portfolio with only 1 strategy
        create_payload = {
            "session_id": f"test_corr_{uuid.uuid4().hex[:8]}",
            "name": "TEST_Single_Strategy_Portfolio"
        }
        create_response = api_client.post(f"{BASE_URL}/api/portfolio/create", json=create_payload)
        assert create_response.status_code == 200
        portfolio_id = create_response.json()["portfolio_id"]
        
        # Create a backtest
        bt_payload = {
            "session_id": f"test_bt_{uuid.uuid4().hex[:8]}",
            "bot_name": "TEST_Bot_Single",
            "symbol": "EURUSD",
            "timeframe": "1h",
            "trade_count": 30
        }
        bt_response = api_client.post(f"{BASE_URL}/api/backtest/simulate", json=bt_payload)
        assert bt_response.status_code == 200, f"Failed to create backtest: {bt_response.text}"
        backtest_id = bt_response.json()["backtest_id"]
        
        # Add only 1 strategy
        add_payload = {"backtest_id": backtest_id, "name": "TEST_Single"}
        api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/add-strategy", json=add_payload)
        
        # Try correlation - should fail with 400
        response = api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/analyze-correlation")
        
        assert response.status_code == 400
        assert "at least 2 strategies" in response.json().get("detail", "").lower()
        print("Correlation correctly requires 2+ strategies (400 returned)")
    
    def test_correlation_nonexistent_portfolio(self, api_client):
        """Test 404 for non-existent portfolio."""
        response = api_client.post(f"{BASE_URL}/api/portfolio/nonexistent-id/analyze-correlation")
        assert response.status_code == 404
        print("Correlation on non-existent portfolio correctly returns 404")


# ---------------------------------------------------------------------------
# Test: Portfolio Backtest
# ---------------------------------------------------------------------------

class TestPortfolioBacktest:
    """Test portfolio backtest endpoint."""
    
    def test_portfolio_backtest_success(self, api_client):
        """Test running combined portfolio backtest."""
        portfolio_id = "8b3a39fd-373c-4c71-92d6-443d877f04e1"
        
        payload = {
            "session_id": "test_session_1",
            "initial_balance": 100000.0
        }
        response = api_client.post(
            f"{BASE_URL}/api/portfolio/{portfolio_id}/backtest",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Data assertions
        assert data.get("success") is True
        assert data.get("portfolio_id") == portfolio_id
        assert "backtest_id" in data
        assert "summary" in data
        assert "strategy_results" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert "net_profit" in summary
        assert "total_return_percent" in summary
        assert "profit_factor" in summary
        assert "max_drawdown_percent" in summary
        assert "sharpe_ratio" in summary
        assert "win_rate" in summary
        assert "total_trades" in summary
        assert "diversification_ratio" in summary
        assert "portfolio_score" in summary
        assert "grade" in summary
        assert "is_deployable" in summary
        
        # Verify strategy_results structure
        assert isinstance(data["strategy_results"], list)
        if len(data["strategy_results"]) > 0:
            sr = data["strategy_results"][0]
            assert "name" in sr
            assert "weight" in sr
            assert "net_profit" in sr
            assert "contribution_percent" in sr
        
        print(f"Portfolio backtest: score={summary['portfolio_score']}, grade={summary['grade']}")
    
    def test_portfolio_backtest_empty_portfolio(self, api_client):
        """Test backtest on empty portfolio returns 400."""
        # Create empty portfolio
        create_payload = {
            "session_id": f"test_empty_bt_{uuid.uuid4().hex[:8]}",
            "name": "TEST_Empty_Backtest"
        }
        create_response = api_client.post(f"{BASE_URL}/api/portfolio/create", json=create_payload)
        portfolio_id = create_response.json()["portfolio_id"]
        
        # Try to backtest
        payload = {"session_id": "test_empty"}
        response = api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/backtest", json=payload)
        
        assert response.status_code == 400
        print("Backtest on empty portfolio correctly returns 400")
    
    def test_portfolio_backtest_nonexistent(self, api_client):
        """Test 404 for non-existent portfolio."""
        payload = {"session_id": "test"}
        response = api_client.post(f"{BASE_URL}/api/portfolio/nonexistent-id/backtest", json=payload)
        assert response.status_code == 404
        print("Backtest on non-existent portfolio correctly returns 404")


# ---------------------------------------------------------------------------
# Test: Monte Carlo Simulation
# ---------------------------------------------------------------------------

class TestPortfolioMonteCarlo:
    """Test portfolio Monte Carlo simulation endpoint."""
    
    def test_monte_carlo_success(self, api_client):
        """Test running Monte Carlo simulation."""
        portfolio_id = "8b3a39fd-373c-4c71-92d6-443d877f04e1"
        
        payload = {
            "session_id": "test_session_1",
            "num_simulations": 500,  # Fewer for faster test
            "ruin_threshold_percent": 50.0
        }
        response = api_client.post(
            f"{BASE_URL}/api/portfolio/{portfolio_id}/monte-carlo",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Data assertions
        assert data.get("success") is True
        assert data.get("portfolio_id") == portfolio_id
        assert "summary" in data
        assert "confidence_intervals" in data
        assert "insights" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert "profit_probability" in summary
        assert "ruin_probability" in summary
        assert "expected_return_percent" in summary
        assert "worst_case_drawdown" in summary
        assert "robustness_score" in summary
        assert "grade" in summary
        assert "risk_level" in summary
        
        # Verify confidence intervals
        ci = data["confidence_intervals"]
        assert "balance_95_ci" in ci
        assert "return_95_ci" in ci
        assert isinstance(ci["balance_95_ci"], list)
        assert len(ci["balance_95_ci"]) == 2
        
        # Verify insights
        insights = data["insights"]
        assert "strengths" in insights
        assert "weaknesses" in insights
        assert "recommendations" in insights
        
        print(f"Monte Carlo: profit_prob={summary['profit_probability']}%, risk={summary['risk_level']}")
    
    def test_monte_carlo_empty_portfolio(self, api_client):
        """Test Monte Carlo on empty portfolio returns 400."""
        # Create empty portfolio
        create_payload = {
            "session_id": f"test_empty_mc_{uuid.uuid4().hex[:8]}",
            "name": "TEST_Empty_MC"
        }
        create_response = api_client.post(f"{BASE_URL}/api/portfolio/create", json=create_payload)
        portfolio_id = create_response.json()["portfolio_id"]
        
        payload = {"session_id": "test_empty"}
        response = api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/monte-carlo", json=payload)
        
        assert response.status_code == 400
        print("Monte Carlo on empty portfolio correctly returns 400")
    
    def test_monte_carlo_nonexistent(self, api_client):
        """Test 404 for non-existent portfolio."""
        payload = {"session_id": "test"}
        response = api_client.post(f"{BASE_URL}/api/portfolio/nonexistent-id/monte-carlo", json=payload)
        assert response.status_code == 404
        print("Monte Carlo on non-existent portfolio correctly returns 404")


# ---------------------------------------------------------------------------
# Test: Allocation Optimization
# ---------------------------------------------------------------------------

class TestAllocationOptimization:
    """Test portfolio allocation optimization endpoint."""
    
    def test_optimize_equal_weight(self, api_client):
        """Test optimization with equal_weight method."""
        portfolio_id = "8b3a39fd-373c-4c71-92d6-443d877f04e1"
        
        payload = {"method": "equal_weight"}
        response = api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/optimize", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        self._verify_optimization_response(data, portfolio_id, "equal_weight")
        
        # Verify equal weights
        weights = data["weights"]
        weight_values = list(weights.values())
        # All weights should be approximately equal
        assert all(abs(w - weight_values[0]) < 0.01 for w in weight_values)
        print(f"Equal weight: {weights}")
    
    def test_optimize_risk_parity(self, api_client):
        """Test optimization with risk_parity method."""
        portfolio_id = "8b3a39fd-373c-4c71-92d6-443d877f04e1"
        
        payload = {"method": "risk_parity"}
        response = api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/optimize", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        self._verify_optimization_response(data, portfolio_id, "risk_parity")
        print(f"Risk parity weights: {data['weights']}")
    
    def test_optimize_max_sharpe(self, api_client):
        """Test optimization with max_sharpe method."""
        portfolio_id = "8b3a39fd-373c-4c71-92d6-443d877f04e1"
        
        payload = {"method": "max_sharpe"}
        response = api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/optimize", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        self._verify_optimization_response(data, portfolio_id, "max_sharpe")
        print(f"Max Sharpe weights: {data['weights']}")
    
    def test_optimize_min_variance(self, api_client):
        """Test optimization with min_variance method."""
        portfolio_id = "8b3a39fd-373c-4c71-92d6-443d877f04e1"
        
        payload = {"method": "min_variance"}
        response = api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/optimize", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        self._verify_optimization_response(data, portfolio_id, "min_variance")
        print(f"Min variance weights: {data['weights']}")
    
    def test_optimize_max_diversification(self, api_client):
        """Test optimization with max_diversification method."""
        portfolio_id = "8b3a39fd-373c-4c71-92d6-443d877f04e1"
        
        payload = {"method": "max_diversification"}
        response = api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/optimize", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        self._verify_optimization_response(data, portfolio_id, "max_diversification")
        print(f"Max diversification weights: {data['weights']}")
    
    def _verify_optimization_response(self, data, portfolio_id, method):
        """Helper to verify optimization response structure."""
        assert data.get("success") is True
        assert data.get("portfolio_id") == portfolio_id
        assert data.get("method") == method
        assert "weights" in data
        assert "expected_return" in data
        assert "expected_volatility" in data
        assert "expected_sharpe" in data
        assert "improvement_vs_equal" in data
        assert "recommendations" in data
        
        # Verify weights sum to ~1.0
        weights = data["weights"]
        assert isinstance(weights, dict)
        weight_sum = sum(weights.values())
        assert abs(weight_sum - 1.0) < 0.01, f"Weights don't sum to 1.0: {weight_sum}"
    
    def test_optimize_requires_two_strategies(self, api_client):
        """Test that optimization requires at least 2 strategies."""
        # Create portfolio with 1 strategy
        create_payload = {
            "session_id": f"test_opt_{uuid.uuid4().hex[:8]}",
            "name": "TEST_Single_Opt"
        }
        create_response = api_client.post(f"{BASE_URL}/api/portfolio/create", json=create_payload)
        portfolio_id = create_response.json()["portfolio_id"]
        
        # Create and add 1 strategy
        bt_payload = {
            "session_id": f"test_bt_{uuid.uuid4().hex[:8]}",
            "bot_name": "TEST_Bot_Opt_Single",
            "symbol": "EURUSD",
            "timeframe": "1h",
            "trade_count": 30
        }
        bt_response = api_client.post(f"{BASE_URL}/api/backtest/simulate", json=bt_payload)
        assert bt_response.status_code == 200, f"Failed to create backtest: {bt_response.text}"
        backtest_id = bt_response.json()["backtest_id"]
        
        add_payload = {"backtest_id": backtest_id, "name": "TEST_Single"}
        api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/add-strategy", json=add_payload)
        
        # Try to optimize - should fail
        payload = {"method": "max_sharpe"}
        response = api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/optimize", json=payload)
        
        assert response.status_code == 400
        assert "at least 2 strategies" in response.json().get("detail", "").lower()
        print("Optimization correctly requires 2+ strategies (400 returned)")
    
    def test_optimize_nonexistent_portfolio(self, api_client):
        """Test 404 for non-existent portfolio."""
        payload = {"method": "equal_weight"}
        response = api_client.post(f"{BASE_URL}/api/portfolio/nonexistent-id/optimize", json=payload)
        assert response.status_code == 404
        print("Optimization on non-existent portfolio correctly returns 404")


# ---------------------------------------------------------------------------
# Test: Full Workflow Integration
# ---------------------------------------------------------------------------

class TestFullWorkflow:
    """Test complete portfolio workflow: create -> add strategies -> analyze -> optimize."""
    
    def test_complete_workflow(self, api_client):
        """Test the complete portfolio workflow end-to-end."""
        test_id = uuid.uuid4().hex[:8]
        session_id = f"test_full_workflow_{test_id}"
        
        # Step 1: Create portfolio
        create_payload = {
            "session_id": session_id,
            "name": f"TEST_Full_Workflow_{test_id}",
            "description": "Complete workflow test",
            "initial_balance": 75000.0
        }
        create_response = api_client.post(f"{BASE_URL}/api/portfolio/create", json=create_payload)
        assert create_response.status_code == 200
        portfolio_id = create_response.json()["portfolio_id"]
        print(f"Step 1: Created portfolio {portfolio_id}")
        
        # Step 2: Create backtests
        backtest_ids = []
        for i, symbol in enumerate(["EURUSD", "GBPUSD"]):
            bt_payload = {
                "session_id": f"{session_id}_bt_{i}",
                "bot_name": f"TEST_Bot_{symbol}_{i}",
                "symbol": symbol,
                "timeframe": "1h",
                "trade_count": 40
            }
            bt_response = api_client.post(f"{BASE_URL}/api/backtest/simulate", json=bt_payload)
            assert bt_response.status_code == 200, f"Failed to create backtest: {bt_response.text}"
            backtest_ids.append(bt_response.json()["backtest_id"])
        print(f"Step 2: Created {len(backtest_ids)} backtests")
        
        # Step 3: Add strategies to portfolio
        for i, bt_id in enumerate(backtest_ids):
            add_payload = {
                "backtest_id": bt_id,
                "name": f"TEST_Strategy_{i+1}"
            }
            add_response = api_client.post(
                f"{BASE_URL}/api/portfolio/{portfolio_id}/add-strategy",
                json=add_payload
            )
            assert add_response.status_code == 200
        print(f"Step 3: Added {len(backtest_ids)} strategies to portfolio")
        
        # Step 4: Run correlation analysis
        corr_response = api_client.post(f"{BASE_URL}/api/portfolio/{portfolio_id}/analyze-correlation")
        assert corr_response.status_code == 200
        corr_data = corr_response.json()
        assert corr_data.get("success") is True
        print(f"Step 4: Correlation analysis - div_score={corr_data['diversification_score']}")
        
        # Step 5: Run portfolio backtest
        bt_payload = {"session_id": session_id}
        bt_response = api_client.post(
            f"{BASE_URL}/api/portfolio/{portfolio_id}/backtest",
            json=bt_payload
        )
        assert bt_response.status_code == 200
        bt_data = bt_response.json()
        assert bt_data.get("success") is True
        print(f"Step 5: Portfolio backtest - score={bt_data['summary']['portfolio_score']}")
        
        # Step 6: Run Monte Carlo
        mc_payload = {"session_id": session_id, "num_simulations": 200}
        mc_response = api_client.post(
            f"{BASE_URL}/api/portfolio/{portfolio_id}/monte-carlo",
            json=mc_payload
        )
        assert mc_response.status_code == 200
        mc_data = mc_response.json()
        assert mc_data.get("success") is True
        print(f"Step 6: Monte Carlo - profit_prob={mc_data['summary']['profit_probability']}%")
        
        # Step 7: Optimize allocation
        opt_payload = {"method": "max_sharpe"}
        opt_response = api_client.post(
            f"{BASE_URL}/api/portfolio/{portfolio_id}/optimize",
            json=opt_payload
        )
        assert opt_response.status_code == 200
        opt_data = opt_response.json()
        assert opt_data.get("success") is True
        print(f"Step 7: Optimization - sharpe={opt_data['expected_sharpe']}")
        
        # Step 8: Verify portfolio contains all results
        final_response = api_client.get(f"{BASE_URL}/api/portfolio/{portfolio_id}")
        assert final_response.status_code == 200
        portfolio = final_response.json()["portfolio"]
        
        assert len(portfolio["strategies"]) == 2
        assert portfolio.get("correlation_result") is not None
        assert portfolio.get("backtest_result") is not None
        assert portfolio.get("monte_carlo_result") is not None
        assert portfolio.get("allocation_result") is not None
        
        print(f"Step 8: Verified all results stored in portfolio")
        print("FULL WORKFLOW TEST PASSED!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
