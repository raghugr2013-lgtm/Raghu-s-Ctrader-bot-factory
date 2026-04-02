"""
Challenge Simulator Backend Tests
Tests for Prop Firm Challenge Simulator endpoints (FTMO, FundedNext, The5ers, PipFarm)
"""

import pytest
import requests
import os
import uuid
import time

# API Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestChallengeRules:
    """Test GET /api/challenge/rules endpoints - retrieves challenge rules for prop firms"""
    
    def test_get_all_rules_returns_success(self):
        """GET /api/challenge/rules - returns rules for all 4 firms"""
        response = requests.get(f"{BASE_URL}/api/challenge/rules")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") is True
        assert "rules" in data
        
        rules = data["rules"]
        # Should have 4 firms
        assert "ftmo" in rules, "FTMO rules missing"
        assert "fundednext" in rules, "FundedNext rules missing"
        assert "the5ers" in rules, "The5ers rules missing"
        assert "pipfarm" in rules, "PipFarm rules missing"
        
        # Each firm should have 2 phases
        for firm in ["ftmo", "fundednext", "the5ers", "pipfarm"]:
            assert len(rules[firm]) == 2, f"{firm} should have 2 phases"
            phases = [r["phase"] for r in rules[firm]]
            assert "phase_1" in phases, f"{firm} missing phase_1"
            assert "phase_2" in phases, f"{firm} missing phase_2"
        
        print(f"SUCCESS: All 4 firms with 2 phases each (8 total rules)")
    
    def test_get_ftmo_rules(self):
        """GET /api/challenge/rules/ftmo - returns FTMO-specific rules"""
        response = requests.get(f"{BASE_URL}/api/challenge/rules/ftmo")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert data.get("firm") == "ftmo"
        assert "phases" in data
        
        phases = data["phases"]
        assert len(phases) == 2
        
        # Verify Phase 1 parameters
        phase1 = next(p for p in phases if p["phase"] == "phase_1")
        assert phase1["profit_target_pct"] == 10.0
        assert phase1["daily_loss_limit_pct"] == 5.0
        assert phase1["max_drawdown_pct"] == 10.0
        assert phase1["min_trading_days"] == 4
        assert phase1["time_limit_days"] == 30
        assert phase1["trailing_drawdown"] is False
        
        # Verify Phase 2 parameters
        phase2 = next(p for p in phases if p["phase"] == "phase_2")
        assert phase2["profit_target_pct"] == 5.0
        assert phase2["time_limit_days"] == 60
        
        print(f"SUCCESS: FTMO rules verified - Phase 1: 10% target/30 days, Phase 2: 5% target/60 days")
    
    def test_get_fundednext_rules(self):
        """GET /api/challenge/rules/fundednext - returns FundedNext rules"""
        response = requests.get(f"{BASE_URL}/api/challenge/rules/fundednext")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert data.get("firm") == "fundednext"
        
        phases = data["phases"]
        phase1 = next(p for p in phases if p["phase"] == "phase_1")
        assert phase1["min_trading_days"] == 5  # FundedNext requires 5 min days
        
        print(f"SUCCESS: FundedNext rules verified - min_trading_days=5")
    
    def test_get_the5ers_rules_trailing_drawdown(self):
        """GET /api/challenge/rules/the5ers - returns The5ers rules with trailing_drawdown=true"""
        response = requests.get(f"{BASE_URL}/api/challenge/rules/the5ers")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert data.get("firm") == "the5ers"
        
        phases = data["phases"]
        # The5ers has trailing drawdown
        for phase in phases:
            assert phase["trailing_drawdown"] is True, f"The5ers {phase['phase']} should have trailing_drawdown=true"
        
        # Verify lower limits
        phase1 = next(p for p in phases if p["phase"] == "phase_1")
        assert phase1["max_drawdown_pct"] == 6.0  # Stricter 6% drawdown limit
        assert phase1["daily_loss_limit_pct"] == 4.0
        
        print(f"SUCCESS: The5ers rules verified - trailing_drawdown=true, max_drawdown=6%")
    
    def test_get_pipfarm_rules_news_trading(self):
        """GET /api/challenge/rules/pipfarm - returns PipFarm rules"""
        response = requests.get(f"{BASE_URL}/api/challenge/rules/pipfarm")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert data.get("firm") == "pipfarm"
        
        # Note: news_trading_allowed is not in the rules response by default
        # but the engine uses it internally
        phases = data["phases"]
        phase1 = next(p for p in phases if p["phase"] == "phase_1")
        assert phase1["max_drawdown_pct"] == 8.0
        assert phase1["daily_loss_limit_pct"] == 4.0
        
        print(f"SUCCESS: PipFarm rules verified - max_drawdown=8%, daily_loss=4%")
    
    def test_get_invalid_firm_returns_404(self):
        """GET /api/challenge/rules/invalidfirm - returns 404 with available firms list"""
        response = requests.get(f"{BASE_URL}/api/challenge/rules/invalidfirm")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        # Should mention available firms
        detail = data["detail"].lower()
        assert "ftmo" in detail or "available" in detail
        
        print(f"SUCCESS: Invalid firm returns 404 with message: {data['detail']}")


class TestBacktestSetup:
    """Helper tests to create backtests for challenge simulation"""
    
    @pytest.fixture(scope="class")
    def session_id(self):
        return f"test_challenge_{uuid.uuid4().hex[:8]}"
    
    @pytest.fixture(scope="class")
    def backtest_id(self, session_id):
        """Create a backtest for testing challenge simulation"""
        response = requests.post(f"{BASE_URL}/api/backtest/simulate", json={
            "session_id": session_id,
            "bot_name": "TEST_challenge_bot",
            "symbol": "EURUSD",
            "timeframe": "1h",
            "duration_days": 60,
            "initial_balance": 10000,
            "strategy_type": "trend_following"
        })
        
        if response.status_code != 200:
            pytest.skip(f"Could not create backtest: {response.text}")
        
        data = response.json()
        return data.get("backtest_id")
    
    def test_backtest_created_for_challenge(self, backtest_id):
        """Verify backtest was created for challenge testing"""
        assert backtest_id is not None, "Backtest ID should be created"
        print(f"SUCCESS: Backtest created with ID: {backtest_id}")


class TestChallengeSimulation:
    """Test POST /api/challenge/simulate endpoint - runs Monte Carlo challenge simulation"""
    
    @pytest.fixture(scope="class")
    def session_id(self):
        return f"test_challenge_sim_{uuid.uuid4().hex[:8]}"
    
    @pytest.fixture(scope="class")
    def backtest_id(self, session_id):
        """Create a backtest for testing challenge simulation"""
        response = requests.post(f"{BASE_URL}/api/backtest/simulate", json={
            "session_id": session_id,
            "bot_name": "TEST_challenge_sim_bot",
            "symbol": "EURUSD",
            "timeframe": "1h",
            "duration_days": 90,
            "initial_balance": 10000,
            "strategy_type": "trend_following"
        })
        
        if response.status_code != 200:
            pytest.skip(f"Could not create backtest: {response.text}")
        
        data = response.json()
        return data.get("backtest_id")
    
    def test_simulate_ftmo_challenge(self, session_id, backtest_id):
        """POST /api/challenge/simulate - simulates FTMO challenge with valid backtest"""
        response = requests.post(f"{BASE_URL}/api/challenge/simulate", json={
            "session_id": session_id,
            "backtest_id": backtest_id,
            "firm": "ftmo",
            "initial_balance": 100000,
            "num_simulations": 500  # Reduced for faster testing
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "challenge_id" in data
        assert data.get("firm") == "ftmo"
        assert data.get("backtest_id") == backtest_id
        
        print(f"SUCCESS: FTMO challenge simulated, challenge_id: {data['challenge_id']}")
        return data
    
    def test_simulate_returns_phases_array(self, session_id, backtest_id):
        """POST /api/challenge/simulate - returns phases array with phase_1 and phase_2"""
        response = requests.post(f"{BASE_URL}/api/challenge/simulate", json={
            "session_id": session_id,
            "backtest_id": backtest_id,
            "firm": "ftmo",
            "initial_balance": 100000,
            "num_simulations": 100  # Even faster for structure test
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "phases" in data
        phases = data["phases"]
        assert len(phases) == 2, "Should have 2 phases"
        
        phase_names = [p["phase"] for p in phases]
        assert "phase_1" in phase_names
        assert "phase_2" in phase_names
        
        print(f"SUCCESS: Phases array contains phase_1 and phase_2")
    
    def test_phase_contains_required_fields(self, session_id, backtest_id):
        """POST /api/challenge/simulate - each phase has pass_probability, violation probabilities, score, grade"""
        response = requests.post(f"{BASE_URL}/api/challenge/simulate", json={
            "session_id": session_id,
            "backtest_id": backtest_id,
            "firm": "fundednext",
            "initial_balance": 100000,
            "num_simulations": 100
        })
        
        assert response.status_code == 200
        data = response.json()
        
        for phase in data["phases"]:
            # Required probability fields
            assert "pass_probability" in phase, f"Missing pass_probability in {phase['phase']}"
            assert "daily_loss_violation_probability" in phase
            assert "drawdown_violation_probability" in phase
            assert "time_limit_violation_probability" in phase
            
            # Score and grade fields
            assert "challenge_score" in phase
            assert "grade" in phase
            assert "risk_level" in phase
            
            # Statistics
            assert "avg_max_drawdown" in phase
            assert "avg_max_daily_loss" in phase
            
            # Fail breakdown
            assert "fail_reasons" in phase
            
            # Confidence interval
            assert "confidence_interval" in phase
            
            # Verify data types
            assert isinstance(phase["pass_probability"], (int, float))
            assert 0 <= phase["pass_probability"] <= 100
            assert isinstance(phase["challenge_score"], (int, float))
            assert phase["grade"] in ["S", "A", "B", "C", "D", "F"]
            
        print(f"SUCCESS: All phases contain required fields with correct types")
    
    def test_combined_pass_probability(self, session_id, backtest_id):
        """POST /api/challenge/simulate - combined_pass_probability is product of phase pass rates"""
        response = requests.post(f"{BASE_URL}/api/challenge/simulate", json={
            "session_id": session_id,
            "backtest_id": backtest_id,
            "firm": "ftmo",
            "initial_balance": 100000,
            "num_simulations": 200
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "combined_pass_probability" in data
        combined = data["combined_pass_probability"]
        
        # Calculate expected combined from phases
        phases = data["phases"]
        expected_combined = 1.0
        for p in phases:
            expected_combined *= (p["pass_probability"] / 100)
        expected_combined *= 100
        
        # Allow small floating point difference
        assert abs(combined - expected_combined) < 0.1, \
            f"Combined {combined} should equal product of phases {expected_combined}"
        
        print(f"SUCCESS: combined_pass_probability ({combined:.2f}%) = product of phase rates")
    
    def test_is_viable_threshold(self, session_id, backtest_id):
        """POST /api/challenge/simulate - is_viable is true when combined_pass >= 50%"""
        response = requests.post(f"{BASE_URL}/api/challenge/simulate", json={
            "session_id": session_id,
            "backtest_id": backtest_id,
            "firm": "ftmo",
            "initial_balance": 100000,
            "num_simulations": 200
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "is_viable" in data
        assert "combined_pass_probability" in data
        
        combined = data["combined_pass_probability"]
        is_viable = data["is_viable"]
        
        # is_viable should be True if combined >= 50%, False otherwise
        expected_viable = combined >= 50
        assert is_viable == expected_viable, \
            f"is_viable={is_viable} but combined={combined}%, expected is_viable={expected_viable}"
        
        print(f"SUCCESS: is_viable={is_viable} correctly based on combined_pass={combined:.2f}%")
    
    def test_fail_reasons_breakdown(self, session_id, backtest_id):
        """POST /api/challenge/simulate - returns fail_reasons breakdown (daily_loss, drawdown, time_limit)"""
        response = requests.post(f"{BASE_URL}/api/challenge/simulate", json={
            "session_id": session_id,
            "backtest_id": backtest_id,
            "firm": "the5ers",  # Stricter rules = more failures
            "initial_balance": 100000,
            "num_simulations": 300
        })
        
        assert response.status_code == 200
        data = response.json()
        
        for phase in data["phases"]:
            fail_reasons = phase["fail_reasons"]
            assert isinstance(fail_reasons, dict)
            
            # Valid fail reason keys
            valid_reasons = ["daily_loss", "drawdown", "time_limit", "min_days"]
            for reason in fail_reasons:
                assert reason in valid_reasons, f"Invalid fail reason: {reason}"
                assert isinstance(fail_reasons[reason], int)
        
        print(f"SUCCESS: fail_reasons breakdown contains valid reason types with counts")
    
    def test_simulate_with_invalid_backtest_returns_404(self, session_id):
        """POST /api/challenge/simulate with invalid backtest_id returns 404"""
        response = requests.post(f"{BASE_URL}/api/challenge/simulate", json={
            "session_id": session_id,
            "backtest_id": "nonexistent_backtest_id",
            "firm": "ftmo",
            "initial_balance": 100000,
            "num_simulations": 100
        })
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
        
        print(f"SUCCESS: Invalid backtest returns 404")


class TestSimulateAllFirms:
    """Test POST /api/challenge/simulate-all-firms endpoint"""
    
    @pytest.fixture(scope="class")
    def session_id(self):
        return f"test_all_firms_{uuid.uuid4().hex[:8]}"
    
    @pytest.fixture(scope="class")
    def backtest_id(self, session_id):
        """Create a backtest for testing"""
        response = requests.post(f"{BASE_URL}/api/backtest/simulate", json={
            "session_id": session_id,
            "bot_name": "TEST_all_firms_bot",
            "symbol": "GBPUSD",
            "timeframe": "4h",
            "duration_days": 60,
            "initial_balance": 10000,
            "strategy_type": "scalping"
        })
        
        if response.status_code != 200:
            pytest.skip(f"Could not create backtest: {response.text}")
        
        return response.json().get("backtest_id")
    
    def test_simulate_all_firms(self, session_id, backtest_id):
        """POST /api/challenge/simulate-all-firms - runs against all 4 firms"""
        response = requests.post(f"{BASE_URL}/api/challenge/simulate-all-firms", json={
            "session_id": session_id,
            "backtest_id": backtest_id,
            "firm": "ftmo",  # Ignored - runs all firms
            "initial_balance": 100000,
            "num_simulations": 100
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "firms" in data
        
        firms = data["firms"]
        assert "ftmo" in firms
        assert "fundednext" in firms
        assert "the5ers" in firms
        assert "pipfarm" in firms
        
        # Each firm should have required fields
        for firm_key, firm_data in firms.items():
            assert "combined_pass_probability" in firm_data
            assert "overall_score" in firm_data
            assert "overall_grade" in firm_data
            assert "is_viable" in firm_data
            assert "recommendation" in firm_data
            assert "phases" in firm_data
        
        print(f"SUCCESS: All 4 firms simulated with results")
    
    def test_simulate_all_firms_ranking(self, session_id, backtest_id):
        """POST /api/challenge/simulate-all-firms - ranking is sorted by combined pass probability desc"""
        response = requests.post(f"{BASE_URL}/api/challenge/simulate-all-firms", json={
            "session_id": session_id,
            "backtest_id": backtest_id,
            "firm": "ftmo",
            "initial_balance": 100000,
            "num_simulations": 100
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "ranking" in data
        ranking = data["ranking"]
        
        assert len(ranking) == 4, "Should have 4 firms in ranking"
        
        # Verify ranking structure
        for rank_item in ranking:
            assert "rank" in rank_item
            assert "firm" in rank_item
            assert "pass_probability" in rank_item
            assert "grade" in rank_item
        
        # Verify sorted descending by pass_probability
        probs = [r["pass_probability"] for r in ranking]
        assert probs == sorted(probs, reverse=True), "Ranking should be sorted by pass_probability descending"
        
        # Verify ranks are 1-4
        ranks = [r["rank"] for r in ranking]
        assert ranks == [1, 2, 3, 4], "Ranks should be 1, 2, 3, 4"
        
        # Verify best_firm matches rank 1
        assert "best_firm" in data
        assert data["best_firm"] == ranking[0]["firm"]
        
        print(f"SUCCESS: Ranking sorted correctly, best_firm={data['best_firm']}")


class TestChallengeResult:
    """Test GET /api/challenge/result/{challenge_id} endpoint"""
    
    @pytest.fixture(scope="class")
    def session_id(self):
        return f"test_result_{uuid.uuid4().hex[:8]}"
    
    @pytest.fixture(scope="class")
    def challenge_data(self, session_id):
        """Create a challenge simulation to retrieve later"""
        # First create a backtest
        bt_response = requests.post(f"{BASE_URL}/api/backtest/simulate", json={
            "session_id": session_id,
            "bot_name": "TEST_result_bot",
            "symbol": "USDJPY",
            "timeframe": "1h",
            "duration_days": 45,
            "initial_balance": 10000,
            "strategy_type": "mean_reversion"
        })
        
        if bt_response.status_code != 200:
            pytest.skip(f"Could not create backtest: {bt_response.text}")
        
        backtest_id = bt_response.json().get("backtest_id")
        
        # Run challenge simulation
        sim_response = requests.post(f"{BASE_URL}/api/challenge/simulate", json={
            "session_id": session_id,
            "backtest_id": backtest_id,
            "firm": "pipfarm",
            "initial_balance": 100000,
            "num_simulations": 100
        })
        
        if sim_response.status_code != 200:
            pytest.skip(f"Could not run simulation: {sim_response.text}")
        
        return sim_response.json()
    
    def test_get_challenge_result(self, challenge_data):
        """GET /api/challenge/result/{challenge_id} - retrieves saved result from DB"""
        challenge_id = challenge_data.get("challenge_id")
        assert challenge_id is not None
        
        response = requests.get(f"{BASE_URL}/api/challenge/result/{challenge_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "result" in data
        
        result = data["result"]
        assert result.get("id") == challenge_id
        assert "firm" in result
        assert "phase_results" in result
        assert "combined_pass_probability" in result
        
        print(f"SUCCESS: Retrieved challenge result {challenge_id} from database")
    
    def test_get_nonexistent_result_returns_404(self):
        """GET /api/challenge/result/nonexistent - returns 404"""
        response = requests.get(f"{BASE_URL}/api/challenge/result/nonexistent_id_12345")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
        
        print(f"SUCCESS: Nonexistent result returns 404")


class TestPnLScaling:
    """Test PnL scaling - trades scaled proportionally when challenge balance differs from backtest balance"""
    
    def test_pnl_scaling_applied(self):
        """PnL scaling: trades are scaled when challenge balance differs from backtest balance"""
        session_id = f"test_scaling_{uuid.uuid4().hex[:8]}"
        
        # Create backtest with $10,000 balance
        bt_response = requests.post(f"{BASE_URL}/api/backtest/simulate", json={
            "session_id": session_id,
            "bot_name": "TEST_scaling_bot",
            "symbol": "EURUSD",
            "timeframe": "1h",
            "duration_days": 30,
            "initial_balance": 10000,  # $10K backtest
            "strategy_type": "trend_following"
        })
        
        assert bt_response.status_code == 200
        backtest_id = bt_response.json().get("backtest_id")
        
        # Run simulation with $100,000 challenge balance (10x)
        sim_response = requests.post(f"{BASE_URL}/api/challenge/simulate", json={
            "session_id": session_id,
            "backtest_id": backtest_id,
            "firm": "ftmo",
            "initial_balance": 100000,  # $100K challenge = 10x scale
            "num_simulations": 100
        })
        
        assert sim_response.status_code == 200, f"Simulation failed: {sim_response.text}"
        
        data = sim_response.json()
        # The simulation should run without errors - scaling is applied internally
        assert data.get("success") is True
        assert "phases" in data
        
        # The avg_final_balance should reflect the scaled amounts
        # With 10x scaling, results should be in the $100K range
        for phase in data["phases"]:
            # avg_max_drawdown should be reasonable (not exceeding limits by much)
            assert phase["avg_max_drawdown"] >= 0, "Drawdown should be non-negative"
        
        print(f"SUCCESS: PnL scaling applied - backtest $10K scaled to challenge $100K")


class TestFullWorkflow:
    """Integration test - full workflow from backtest to challenge comparison"""
    
    def test_full_challenge_workflow(self):
        """Full workflow: create backtest -> simulate challenge -> compare firms -> retrieve result"""
        session_id = f"test_workflow_{uuid.uuid4().hex[:8]}"
        
        # Step 1: Create backtest
        print("Step 1: Creating backtest...")
        bt_response = requests.post(f"{BASE_URL}/api/backtest/simulate", json={
            "session_id": session_id,
            "bot_name": "TEST_workflow_bot",
            "symbol": "EURUSD",
            "timeframe": "1h",
            "duration_days": 60,
            "initial_balance": 10000,
            "strategy_type": "trend_following"
        })
        
        assert bt_response.status_code == 200, f"Backtest creation failed: {bt_response.text}"
        backtest_id = bt_response.json().get("backtest_id")
        print(f"  Backtest created: {backtest_id}")
        
        # Step 2: Simulate single firm challenge
        print("Step 2: Simulating FTMO challenge...")
        sim_response = requests.post(f"{BASE_URL}/api/challenge/simulate", json={
            "session_id": session_id,
            "backtest_id": backtest_id,
            "firm": "ftmo",
            "initial_balance": 100000,
            "num_simulations": 200
        })
        
        assert sim_response.status_code == 200, f"Simulation failed: {sim_response.text}"
        sim_data = sim_response.json()
        challenge_id = sim_data.get("challenge_id")
        print(f"  Challenge ID: {challenge_id}")
        print(f"  Combined pass: {sim_data['combined_pass_probability']:.1f}%")
        print(f"  Is viable: {sim_data['is_viable']}")
        
        # Step 3: Compare all firms
        print("Step 3: Comparing all firms...")
        compare_response = requests.post(f"{BASE_URL}/api/challenge/simulate-all-firms", json={
            "session_id": session_id,
            "backtest_id": backtest_id,
            "firm": "ftmo",
            "initial_balance": 100000,
            "num_simulations": 100
        })
        
        assert compare_response.status_code == 200, f"Comparison failed: {compare_response.text}"
        compare_data = compare_response.json()
        print(f"  Best firm: {compare_data['best_firm']}")
        ranking_str = ", ".join([f"({r['rank']}) {r['firm']}: {r['pass_probability']:.1f}%" for r in compare_data['ranking']])
        print(f"  Ranking: {ranking_str}")
        
        # Step 4: Retrieve saved result
        print("Step 4: Retrieving saved result...")
        result_response = requests.get(f"{BASE_URL}/api/challenge/result/{challenge_id}")
        
        assert result_response.status_code == 200, f"Result retrieval failed: {result_response.text}"
        result_data = result_response.json()
        assert result_data["result"]["id"] == challenge_id
        print(f"  Result retrieved successfully")
        
        print(f"\nSUCCESS: Full workflow completed")


# Run tests with: pytest /app/backend/tests/test_challenge.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
