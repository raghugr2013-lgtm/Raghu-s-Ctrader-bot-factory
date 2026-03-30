"""
Genetic Algorithm Strategy Optimizer - Backend Tests
Tests: GET /strategies, POST /run, GET /status, GET /result, GET /list
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test session ID for isolation
TEST_SESSION_ID = f"TEST_optimizer_{uuid.uuid4().hex[:8]}"


class TestOptimizerStrategies:
    """Tests for GET /api/optimizer/strategies endpoint"""
    
    def test_list_strategies_returns_200(self):
        """Verify strategies endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/optimizer/strategies")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: GET /strategies returns 200")
    
    def test_list_strategies_contains_expected_types(self):
        """Verify all 3 strategy types are returned: trend_following, mean_reversion, scalping"""
        response = requests.get(f"{BASE_URL}/api/optimizer/strategies")
        data = response.json()
        
        assert "strategies" in data, "Response missing 'strategies' key"
        strategies = data["strategies"]
        
        expected_types = ["trend_following", "mean_reversion", "scalping"]
        for strategy_type in expected_types:
            assert strategy_type in strategies, f"Missing strategy type: {strategy_type}"
            assert isinstance(strategies[strategy_type], list), f"{strategy_type} params should be a list"
            assert len(strategies[strategy_type]) > 0, f"{strategy_type} should have parameter definitions"
        
        print(f"PASS: All 3 strategy types found: {list(strategies.keys())}")
    
    def test_strategy_params_have_required_fields(self):
        """Verify each param definition has name, param_type, min_val, max_val"""
        response = requests.get(f"{BASE_URL}/api/optimizer/strategies")
        data = response.json()
        
        for strategy_type, params in data["strategies"].items():
            for param in params:
                assert "name" in param, f"Param in {strategy_type} missing 'name'"
                assert "param_type" in param, f"Param {param.get('name')} missing 'param_type'"
                assert "min_val" in param, f"Param {param.get('name')} missing 'min_val'"
                assert "max_val" in param, f"Param {param.get('name')} missing 'max_val'"
                assert param["min_val"] < param["max_val"], f"min_val should be < max_val for {param.get('name')}"
        
        print("PASS: All param definitions have required fields with valid ranges")


class TestOptimizerRunEndpoint:
    """Tests for POST /api/optimizer/run endpoint"""
    
    def test_run_optimization_returns_job_id(self):
        """Verify POST /run starts optimization and returns job_id"""
        payload = {
            "session_id": TEST_SESSION_ID,
            "strategy_type": "trend_following",
            "symbol": "EURUSD",
            "timeframe": "1h",
            "population_size": 10,
            "num_generations": 5,
            "initial_balance": 10000.0
        }
        
        response = requests.post(f"{BASE_URL}/api/optimizer/run", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data and data["success"] == True, "Response should have success=True"
        assert "job_id" in data, "Response missing 'job_id'"
        assert "status" in data and data["status"] == "pending", "Status should be 'pending'"
        assert "message" in data, "Response missing 'message'"
        
        print(f"PASS: POST /run returns job_id: {data['job_id']}")
        return data["job_id"]
    
    def test_run_optimization_unknown_strategy_returns_400(self):
        """Verify unknown strategy type returns 400 error"""
        payload = {
            "session_id": TEST_SESSION_ID,
            "strategy_type": "invalid_strategy_type",
            "symbol": "EURUSD",
            "population_size": 10,
            "num_generations": 5
        }
        
        response = requests.post(f"{BASE_URL}/api/optimizer/run", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Error response should have 'detail'"
        assert "invalid_strategy_type" in data["detail"].lower() or "unknown" in data["detail"].lower(), \
            f"Error should mention unknown strategy: {data['detail']}"
        
        print(f"PASS: Unknown strategy type returns 400: {data['detail']}")


class TestOptimizerStatusEndpoint:
    """Tests for GET /api/optimizer/status/{job_id} endpoint"""
    
    def test_status_unknown_job_returns_404(self):
        """Verify status endpoint returns 404 for unknown job_id"""
        fake_job_id = f"nonexistent-{uuid.uuid4()}"
        response = requests.get(f"{BASE_URL}/api/optimizer/status/{fake_job_id}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("PASS: GET /status/{unknown_id} returns 404")
    
    def test_status_returns_expected_fields(self):
        """Verify status endpoint returns required fields"""
        # Start a small optimization
        payload = {
            "session_id": TEST_SESSION_ID,
            "strategy_type": "scalping",
            "symbol": "GBPUSD",
            "population_size": 10,
            "num_generations": 5
        }
        
        run_response = requests.post(f"{BASE_URL}/api/optimizer/run", json=payload)
        assert run_response.status_code == 200, f"Failed to start optimization: {run_response.text}"
        job_id = run_response.json()["job_id"]
        
        # Check status immediately
        status_response = requests.get(f"{BASE_URL}/api/optimizer/status/{job_id}")
        assert status_response.status_code == 200, f"Expected 200, got {status_response.status_code}"
        
        data = status_response.json()
        required_fields = ["job_id", "status", "current_generation", "total_generations"]
        for field in required_fields:
            assert field in data, f"Status response missing '{field}'"
        
        assert data["job_id"] == job_id, "Job ID mismatch"
        assert data["status"] in ["pending", "running", "completed", "failed"], f"Invalid status: {data['status']}"
        
        print(f"PASS: GET /status returns required fields: {list(data.keys())}")
        return job_id


class TestOptimizerResultEndpoint:
    """Tests for GET /api/optimizer/result/{job_id} endpoint"""
    
    def test_result_unknown_job_returns_404(self):
        """Verify result endpoint returns 404 for unknown job_id"""
        fake_job_id = f"nonexistent-{uuid.uuid4()}"
        response = requests.get(f"{BASE_URL}/api/optimizer/result/{fake_job_id}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("PASS: GET /result/{unknown_id} returns 404")


class TestOptimizerListEndpoint:
    """Tests for GET /api/optimizer/list/{session_id} endpoint"""
    
    def test_list_optimizations_returns_200(self):
        """Verify list endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/optimizer/list/{TEST_SESSION_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data and data["success"] == True, "Response should have success=True"
        assert "optimizations" in data, "Response missing 'optimizations'"
        assert "count" in data, "Response missing 'count'"
        assert isinstance(data["optimizations"], list), "optimizations should be a list"
        
        print(f"PASS: GET /list returns {data['count']} optimizations for session")


class TestOptimizerFullWorkflow:
    """End-to-end tests for complete optimization workflow"""
    
    def test_trend_following_optimization_completes(self):
        """Test full workflow with trend_following strategy"""
        job_id = self._run_and_wait_for_completion(
            strategy_type="trend_following",
            test_name="trend_following"
        )
        self._verify_result(job_id, "trend_following")
    
    def test_mean_reversion_optimization_completes(self):
        """Test full workflow with mean_reversion strategy"""
        job_id = self._run_and_wait_for_completion(
            strategy_type="mean_reversion",
            test_name="mean_reversion"
        )
        self._verify_result(job_id, "mean_reversion")
    
    def test_scalping_optimization_completes(self):
        """Test full workflow with scalping strategy"""
        job_id = self._run_and_wait_for_completion(
            strategy_type="scalping",
            test_name="scalping"
        )
        self._verify_result(job_id, "scalping")
    
    def _run_and_wait_for_completion(self, strategy_type: str, test_name: str) -> str:
        """Start optimization and poll until completed"""
        payload = {
            "session_id": TEST_SESSION_ID,
            "strategy_type": strategy_type,
            "symbol": "EURUSD",
            "timeframe": "1h",
            "population_size": 10,  # Small for faster tests
            "num_generations": 5,
            "initial_balance": 10000.0,
            "duration_days": 30
        }
        
        # Start optimization
        run_response = requests.post(f"{BASE_URL}/api/optimizer/run", json=payload)
        assert run_response.status_code == 200, f"Failed to start {test_name}: {run_response.text}"
        job_id = run_response.json()["job_id"]
        print(f"Started {test_name} optimization: {job_id}")
        
        # Poll status until completed or timeout
        max_wait = 60  # seconds
        poll_interval = 3
        waited = 0
        
        while waited < max_wait:
            status_response = requests.get(f"{BASE_URL}/api/optimizer/status/{job_id}")
            assert status_response.status_code == 200, f"Status check failed: {status_response.text}"
            
            status_data = status_response.json()
            status = status_data["status"]
            
            if status == "completed":
                print(f"PASS: {test_name} optimization completed in ~{waited}s")
                return job_id
            elif status == "failed":
                pytest.fail(f"{test_name} optimization failed: {status_data.get('error_message')}")
            
            print(f"  {test_name} status: {status}, gen {status_data.get('current_generation', 0)}/{status_data.get('total_generations', 0)}")
            time.sleep(poll_interval)
            waited += poll_interval
        
        pytest.fail(f"{test_name} optimization did not complete within {max_wait}s")
    
    def _verify_result(self, job_id: str, strategy_type: str):
        """Verify result structure and data integrity"""
        result_response = requests.get(f"{BASE_URL}/api/optimizer/result/{job_id}")
        assert result_response.status_code == 200, f"Failed to get result: {result_response.text}"
        
        data = result_response.json()
        assert "success" in data and data["success"] == True, "Result should have success=True"
        assert "result" in data, "Result response missing 'result'"
        
        result = data["result"]
        
        # Verify basic fields
        assert result["status"] == "completed", f"Expected completed status, got {result['status']}"
        assert result["strategy_type"] == strategy_type, f"Strategy type mismatch"
        
        # Verify generation_history
        assert "generation_history" in result, "Missing generation_history"
        gen_history = result["generation_history"]
        expected_gen_count = result["num_generations"] + 1  # Initial + generations
        assert len(gen_history) == expected_gen_count, \
            f"Expected {expected_gen_count} generation entries, got {len(gen_history)}"
        print(f"  generation_history has correct {len(gen_history)} entries")
        
        # Verify best_genome
        assert "best_genome" in result and result["best_genome"], "Missing best_genome"
        best = result["best_genome"]
        assert "genes" in best, "best_genome missing 'genes'"
        assert "fitness" in best, "best_genome missing 'fitness'"
        assert best["fitness"] > 0, "best_genome fitness should be > 0"
        
        # Verify gene values are within bounds
        self._verify_genes_within_bounds(best["genes"], strategy_type)
        print(f"  best_genome fitness: {best['fitness']}")
        
        # Verify top_genomes
        assert "top_genomes" in result, "Missing top_genomes"
        top = result["top_genomes"]
        assert len(top) > 0, "top_genomes should not be empty"
        
        # Verify top_genomes are ranked by fitness descending
        fitness_values = [g["fitness"] for g in top]
        assert fitness_values == sorted(fitness_values, reverse=True), \
            "top_genomes should be ranked by fitness descending"
        print(f"  top_genomes count: {len(top)}, fitness range: {fitness_values[-1]:.2f} - {fitness_values[0]:.2f}")
        
        print(f"PASS: {strategy_type} result verified successfully")
    
    def _verify_genes_within_bounds(self, genes: dict, strategy_type: str):
        """Verify gene values are within parameter bounds"""
        # Get param definitions
        strategies_response = requests.get(f"{BASE_URL}/api/optimizer/strategies")
        params = strategies_response.json()["strategies"][strategy_type]
        
        for param in params:
            name = param["name"]
            if name in genes:
                value = genes[name]
                assert param["min_val"] <= value <= param["max_val"], \
                    f"Gene '{name}' value {value} out of bounds [{param['min_val']}, {param['max_val']}]"
        
        print(f"  All {len(genes)} gene values within parameter bounds")


class TestOptimizerDataAssertions:
    """Additional data integrity tests"""
    
    def test_generation_history_structure(self):
        """Verify generation history entries have correct structure"""
        # First run a quick optimization
        payload = {
            "session_id": TEST_SESSION_ID,
            "strategy_type": "trend_following",
            "population_size": 10,
            "num_generations": 3  # Very small for speed
        }
        
        run_response = requests.post(f"{BASE_URL}/api/optimizer/run", json=payload)
        job_id = run_response.json()["job_id"]
        
        # Wait for completion
        max_wait = 45
        waited = 0
        while waited < max_wait:
            status = requests.get(f"{BASE_URL}/api/optimizer/status/{job_id}").json()
            if status["status"] == "completed":
                break
            time.sleep(2)
            waited += 2
        
        # Get result
        result = requests.get(f"{BASE_URL}/api/optimizer/result/{job_id}").json()["result"]
        
        # Verify generation history
        for gen_entry in result["generation_history"]:
            required_fields = ["generation", "population_size", "best_fitness", "avg_fitness", 
                              "worst_fitness", "diversity"]
            for field in required_fields:
                assert field in gen_entry, f"Generation entry missing '{field}'"
            
            # Verify fitness ordering
            assert gen_entry["best_fitness"] >= gen_entry["avg_fitness"], \
                "best_fitness should be >= avg_fitness"
            assert gen_entry["avg_fitness"] >= gen_entry["worst_fitness"], \
                "avg_fitness should be >= worst_fitness"
        
        print("PASS: Generation history structure verified")
    
    def test_genome_metrics_validity(self):
        """Verify genome metrics have valid values"""
        # Run small optimization
        payload = {
            "session_id": TEST_SESSION_ID,
            "strategy_type": "scalping",
            "population_size": 10,
            "num_generations": 3
        }
        
        run_response = requests.post(f"{BASE_URL}/api/optimizer/run", json=payload)
        job_id = run_response.json()["job_id"]
        
        # Wait for completion
        max_wait = 45
        waited = 0
        while waited < max_wait:
            status = requests.get(f"{BASE_URL}/api/optimizer/status/{job_id}").json()
            if status["status"] == "completed":
                break
            time.sleep(2)
            waited += 2
        
        result = requests.get(f"{BASE_URL}/api/optimizer/result/{job_id}").json()["result"]
        best = result["best_genome"]
        
        # Verify metric ranges
        assert 0 <= best.get("win_rate", 0) <= 100, f"Invalid win_rate: {best.get('win_rate')}"
        assert best.get("profit_factor", 0) >= 0, f"Invalid profit_factor: {best.get('profit_factor')}"
        assert 0 <= best.get("max_drawdown_pct", 0) <= 100, f"Invalid max_drawdown_pct"
        assert best.get("total_trades", 0) >= 0, f"Invalid total_trades"
        
        print("PASS: Genome metrics have valid values")


# Run tests when executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
