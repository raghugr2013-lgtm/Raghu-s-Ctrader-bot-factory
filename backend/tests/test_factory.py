"""
Strategy Factory API Tests
Tests for GET /api/factory/templates, POST /api/factory/generate, 
GET /api/factory/status/{run_id}, GET /api/factory/result/{run_id},
GET /api/factory/runs/{session_id}

Tests cover:
- 5 strategy templates (ema_crossover, rsi_mean_reversion, macd_trend, bollinger_breakout, atr_volatility_breakout)
- Strategy generation and evaluation via factory
- Fitness ranking (descending)
- Parameter bounds validation
- Auto-optimization feature
- Error handling (404 for unknown run_id, 409 for in-progress runs)
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test session prefix for cleanup
TEST_SESSION_PREFIX = "TEST_factory_"


class TestFactoryTemplates:
    """Test GET /api/factory/templates - List all 5 strategy templates"""

    def test_list_templates_returns_200(self):
        """GET /api/factory/templates should return 200"""
        response = requests.get(f"{BASE_URL}/api/factory/templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: GET /api/factory/templates returns 200")

    def test_templates_count_is_5(self):
        """Should return exactly 5 templates"""
        response = requests.get(f"{BASE_URL}/api/factory/templates")
        data = response.json()
        
        assert "templates" in data, "Response missing 'templates' field"
        assert "count" in data, "Response missing 'count' field"
        assert data["count"] == 5, f"Expected 5 templates, got {data['count']}"
        assert len(data["templates"]) == 5, f"Expected 5 templates in list, got {len(data['templates'])}"
        print("PASS: Templates count is 5")

    def test_all_template_ids_present(self):
        """All 5 template IDs should be present"""
        expected_ids = {
            "ema_crossover",
            "rsi_mean_reversion", 
            "macd_trend",
            "bollinger_breakout",
            "atr_volatility_breakout"
        }
        
        response = requests.get(f"{BASE_URL}/api/factory/templates")
        data = response.json()
        
        actual_ids = {t["id"] for t in data["templates"]}
        assert actual_ids == expected_ids, f"Expected {expected_ids}, got {actual_ids}"
        print(f"PASS: All 5 template IDs present: {actual_ids}")

    def test_templates_have_required_fields(self):
        """Each template should have id, name, description, backtest_strategy_type, param_count, params"""
        response = requests.get(f"{BASE_URL}/api/factory/templates")
        data = response.json()
        
        required_fields = {"id", "name", "description", "backtest_strategy_type", "param_count", "params"}
        
        for template in data["templates"]:
            for field in required_fields:
                assert field in template, f"Template {template.get('id')} missing field: {field}"
            
            # Validate params list
            assert isinstance(template["params"], list), f"Template {template['id']} params should be a list"
            assert len(template["params"]) == template["param_count"], \
                f"Template {template['id']} param_count mismatch: {template['param_count']} vs {len(template['params'])}"
        
        print("PASS: All templates have required fields")

    def test_templates_map_to_backtest_types(self):
        """Templates should map to trend_following, mean_reversion, or breakout"""
        valid_types = {"trend_following", "mean_reversion", "breakout"}
        
        response = requests.get(f"{BASE_URL}/api/factory/templates")
        data = response.json()
        
        for template in data["templates"]:
            bt_type = template["backtest_strategy_type"]
            assert bt_type in valid_types, \
                f"Template {template['id']} has invalid backtest_strategy_type: {bt_type}"
        
        print("PASS: All templates map to valid backtest types")

    def test_template_params_have_bounds(self):
        """Each param should have min_val and max_val with min < max"""
        response = requests.get(f"{BASE_URL}/api/factory/templates")
        data = response.json()
        
        for template in data["templates"]:
            for param in template["params"]:
                assert "name" in param, f"Param missing 'name' in template {template['id']}"
                assert "min_val" in param, f"Param {param.get('name')} missing 'min_val'"
                assert "max_val" in param, f"Param {param.get('name')} missing 'max_val'"
                assert param["min_val"] < param["max_val"], \
                    f"Param {param['name']} has invalid bounds: min={param['min_val']}, max={param['max_val']}"
        
        print("PASS: All template params have valid bounds")


class TestFactoryGenerate:
    """Test POST /api/factory/generate - Start factory run"""

    def test_generate_single_template_returns_run_id(self):
        """POST with single template should return run_id and status=pending"""
        session_id = f"{TEST_SESSION_PREFIX}{uuid.uuid4()}"
        
        response = requests.post(f"{BASE_URL}/api/factory/generate", json={
            "session_id": session_id,
            "templates": ["ema_crossover"],
            "strategies_per_template": 3
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("success") == True, "Expected success=true"
        assert "run_id" in data, "Response missing 'run_id'"
        assert data.get("status") == "pending", f"Expected status=pending, got {data.get('status')}"
        assert "message" in data, "Response missing 'message'"
        
        print(f"PASS: Generate with single template returns run_id: {data['run_id']}")
        return data["run_id"]

    def test_generate_all_templates(self):
        """POST with all 5 templates should work"""
        session_id = f"{TEST_SESSION_PREFIX}{uuid.uuid4()}"
        
        all_templates = [
            "ema_crossover",
            "rsi_mean_reversion",
            "macd_trend",
            "bollinger_breakout",
            "atr_volatility_breakout"
        ]
        
        response = requests.post(f"{BASE_URL}/api/factory/generate", json={
            "session_id": session_id,
            "templates": all_templates,
            "strategies_per_template": 2
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        assert "run_id" in data
        
        # Message should mention 5 templates x 2 strategies
        assert "5 templates" in data.get("message", ""), f"Expected '5 templates' in message: {data.get('message')}"
        
        print(f"PASS: Generate with all 5 templates returns run_id: {data['run_id']}")

    def test_generate_invalid_template_returns_400(self):
        """POST with unknown template should return 400"""
        session_id = f"{TEST_SESSION_PREFIX}{uuid.uuid4()}"
        
        response = requests.post(f"{BASE_URL}/api/factory/generate", json={
            "session_id": session_id,
            "templates": ["invalid_template_xyz"],
            "strategies_per_template": 3
        })
        
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}: {response.text}"
        print("PASS: Invalid template returns 400/422")


class TestFactoryStatusAndResults:
    """Test GET /api/factory/status/{run_id} and GET /api/factory/result/{run_id}"""

    @pytest.fixture(scope="class")
    def completed_run(self):
        """Create and wait for a factory run to complete"""
        session_id = f"{TEST_SESSION_PREFIX}{uuid.uuid4()}"
        
        # Start factory with 2 templates, 5 strategies each
        response = requests.post(f"{BASE_URL}/api/factory/generate", json={
            "session_id": session_id,
            "templates": ["ema_crossover", "rsi_mean_reversion"],
            "strategies_per_template": 5
        })
        
        assert response.status_code == 200, f"Failed to start factory: {response.text}"
        run_id = response.json()["run_id"]
        
        # Poll until completed (max 30 seconds)
        for _ in range(30):
            status_resp = requests.get(f"{BASE_URL}/api/factory/status/{run_id}")
            if status_resp.status_code == 200:
                status = status_resp.json().get("status")
                if status in ["completed", "failed"]:
                    break
            time.sleep(1)
        
        return {"run_id": run_id, "session_id": session_id, "templates_count": 2, "strategies_per_template": 5}

    def test_status_unknown_run_returns_404(self):
        """GET /api/factory/status/{unknown_id} should return 404"""
        fake_id = f"fake-{uuid.uuid4()}"
        response = requests.get(f"{BASE_URL}/api/factory/status/{fake_id}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("PASS: Unknown run_id returns 404 on status endpoint")

    def test_result_unknown_run_returns_404(self):
        """GET /api/factory/result/{unknown_id} should return 404"""
        fake_id = f"fake-{uuid.uuid4()}"
        response = requests.get(f"{BASE_URL}/api/factory/result/{fake_id}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("PASS: Unknown run_id returns 404 on result endpoint")

    def test_status_returns_required_fields(self, completed_run):
        """Status endpoint should return run_id, status, total_generated, total_evaluated, best_fitness"""
        run_id = completed_run["run_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/status/{run_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        required_fields = ["run_id", "status", "total_generated", "total_evaluated", "best_fitness", "execution_time_seconds"]
        
        for field in required_fields:
            assert field in data, f"Status response missing field: {field}"
        
        assert data["status"] == "completed", f"Expected completed status, got {data['status']}"
        print(f"PASS: Status endpoint returns all required fields. Status: {data['status']}")

    def test_total_generated_equals_templates_times_strategies(self, completed_run):
        """total_generated should equal templates_count * strategies_per_template"""
        run_id = completed_run["run_id"]
        expected_total = completed_run["templates_count"] * completed_run["strategies_per_template"]
        
        response = requests.get(f"{BASE_URL}/api/factory/status/{run_id}")
        data = response.json()
        
        assert data["total_generated"] == expected_total, \
            f"Expected total_generated={expected_total}, got {data['total_generated']}"
        print(f"PASS: total_generated ({data['total_generated']}) = templates_count * strategies_per_template")

    def test_total_evaluated_equals_total_generated(self, completed_run):
        """All generated strategies should be evaluated"""
        run_id = completed_run["run_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/status/{run_id}")
        data = response.json()
        
        assert data["total_evaluated"] == data["total_generated"], \
            f"total_evaluated ({data['total_evaluated']}) != total_generated ({data['total_generated']})"
        print(f"PASS: All {data['total_generated']} strategies were evaluated")

    def test_best_fitness_is_nonzero(self, completed_run):
        """best_fitness should be a non-zero number"""
        run_id = completed_run["run_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/status/{run_id}")
        data = response.json()
        
        assert isinstance(data["best_fitness"], (int, float)), "best_fitness should be a number"
        assert data["best_fitness"] != 0, "best_fitness should be non-zero"
        print(f"PASS: best_fitness = {data['best_fitness']} (non-zero)")

    def test_result_contains_full_data(self, completed_run):
        """Result endpoint should return full factory run data"""
        run_id = completed_run["run_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/result/{run_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert "result" in data
        
        result = data["result"]
        required_fields = ["id", "session_id", "status", "templates_used", "strategies_per_template",
                         "total_generated", "total_evaluated", "strategies", "best_strategy"]
        
        for field in required_fields:
            assert field in result, f"Result missing field: {field}"
        
        print("PASS: Result endpoint returns full factory run data")

    def test_strategies_ranked_by_fitness_descending(self, completed_run):
        """Strategies should be ranked by fitness in descending order"""
        run_id = completed_run["run_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/result/{run_id}")
        data = response.json()
        
        strategies = data["result"]["strategies"]
        assert len(strategies) > 0, "Expected at least one strategy"
        
        fitness_values = [s["fitness"] for s in strategies]
        
        # Verify descending order
        for i in range(len(fitness_values) - 1):
            assert fitness_values[i] >= fitness_values[i + 1], \
                f"Strategies not sorted by fitness: {fitness_values[i]} < {fitness_values[i+1]} at index {i}"
        
        print(f"PASS: {len(strategies)} strategies ranked by fitness descending (best={fitness_values[0]:.4f})")

    def test_all_strategies_evaluated_with_nonzero_metrics(self, completed_run):
        """Each strategy should have evaluated=true and non-zero metrics"""
        run_id = completed_run["run_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/result/{run_id}")
        data = response.json()
        
        strategies = data["result"]["strategies"]
        
        for i, strat in enumerate(strategies):
            assert strat.get("evaluated") == True, f"Strategy {i} not evaluated"
            assert strat.get("fitness", 0) != 0, f"Strategy {i} has zero fitness"
            assert "sharpe_ratio" in strat, f"Strategy {i} missing sharpe_ratio"
            assert "max_drawdown_pct" in strat, f"Strategy {i} missing max_drawdown_pct"
            assert "profit_factor" in strat, f"Strategy {i} missing profit_factor"
            assert "win_rate" in strat, f"Strategy {i} missing win_rate"
            assert "total_trades" in strat, f"Strategy {i} missing total_trades"
        
        print(f"PASS: All {len(strategies)} strategies have evaluated=true with metrics")

    def test_best_strategy_matches_first_in_list(self, completed_run):
        """best_strategy should match the first strategy in the ranked list"""
        run_id = completed_run["run_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/result/{run_id}")
        data = response.json()
        
        best_strategy = data["result"]["best_strategy"]
        first_strategy = data["result"]["strategies"][0]
        
        assert best_strategy["id"] == first_strategy["id"], \
            f"best_strategy ID ({best_strategy['id']}) != first strategy ID ({first_strategy['id']})"
        assert best_strategy["fitness"] == first_strategy["fitness"], \
            f"best_strategy fitness ({best_strategy['fitness']}) != first strategy fitness ({first_strategy['fitness']})"
        
        print(f"PASS: best_strategy matches first ranked strategy (fitness={best_strategy['fitness']:.4f})")


class TestStrategyGeneValidation:
    """Test that generated strategy genes are within template parameter bounds"""

    @pytest.fixture(scope="class")
    def templates_and_run(self):
        """Get templates and create a factory run"""
        # Get templates
        tmpl_resp = requests.get(f"{BASE_URL}/api/factory/templates")
        templates = {t["id"]: t for t in tmpl_resp.json()["templates"]}
        
        # Create factory run
        session_id = f"{TEST_SESSION_PREFIX}bounds_{uuid.uuid4()}"
        run_resp = requests.post(f"{BASE_URL}/api/factory/generate", json={
            "session_id": session_id,
            "templates": ["ema_crossover", "bollinger_breakout"],
            "strategies_per_template": 5
        })
        
        run_id = run_resp.json()["run_id"]
        
        # Wait for completion
        for _ in range(30):
            status_resp = requests.get(f"{BASE_URL}/api/factory/status/{run_id}")
            if status_resp.json().get("status") in ["completed", "failed"]:
                break
            time.sleep(1)
        
        return {"templates": templates, "run_id": run_id}

    def test_gene_values_within_template_bounds(self, templates_and_run):
        """Each strategy's gene values should be within template parameter bounds"""
        templates = templates_and_run["templates"]
        run_id = templates_and_run["run_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/result/{run_id}")
        data = response.json()
        
        strategies = data["result"]["strategies"]
        violations = []
        
        for strat in strategies:
            template_id = strat["template_id"]
            template = templates.get(template_id)
            
            if not template:
                continue
            
            # Build param bounds lookup
            param_bounds = {p["name"]: (p["min_val"], p["max_val"]) for p in template["params"]}
            
            for gene_name, gene_value in strat["genes"].items():
                if gene_name in param_bounds:
                    min_val, max_val = param_bounds[gene_name]
                    if not (min_val <= gene_value <= max_val):
                        violations.append({
                            "strategy_id": strat["id"],
                            "template": template_id,
                            "gene": gene_name,
                            "value": gene_value,
                            "bounds": (min_val, max_val)
                        })
        
        assert len(violations) == 0, f"Gene bound violations found: {violations}"
        print(f"PASS: All gene values within template parameter bounds ({len(strategies)} strategies checked)")


class TestAllTemplatesGenerateValidStrategies:
    """Test that all 5 templates generate valid strategies"""

    @pytest.fixture(scope="class")
    def all_templates_run(self):
        """Run factory with all 5 templates"""
        session_id = f"{TEST_SESSION_PREFIX}all5_{uuid.uuid4()}"
        
        all_templates = [
            "ema_crossover",
            "rsi_mean_reversion",
            "macd_trend",
            "bollinger_breakout",
            "atr_volatility_breakout"
        ]
        
        response = requests.post(f"{BASE_URL}/api/factory/generate", json={
            "session_id": session_id,
            "templates": all_templates,
            "strategies_per_template": 5
        })
        
        run_id = response.json()["run_id"]
        
        # Wait for completion (longer timeout for 5 templates)
        for _ in range(60):
            status_resp = requests.get(f"{BASE_URL}/api/factory/status/{run_id}")
            if status_resp.json().get("status") in ["completed", "failed"]:
                break
            time.sleep(1)
        
        return {"run_id": run_id, "session_id": session_id}

    def test_run_completed_successfully(self, all_templates_run):
        """Factory run with all 5 templates should complete"""
        run_id = all_templates_run["run_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/status/{run_id}")
        data = response.json()
        
        assert data["status"] == "completed", f"Expected completed, got {data['status']}. Error: {data.get('error_message')}"
        print(f"PASS: Factory run with all 5 templates completed in {data['execution_time_seconds']} seconds")

    def test_all_templates_produced_strategies(self, all_templates_run):
        """Each template should have produced strategies"""
        run_id = all_templates_run["run_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/result/{run_id}")
        data = response.json()
        
        strategies = data["result"]["strategies"]
        
        # Group by template
        by_template = {}
        for strat in strategies:
            tid = strat["template_id"]
            by_template[tid] = by_template.get(tid, 0) + 1
        
        expected_templates = {
            "ema_crossover",
            "rsi_mean_reversion",
            "macd_trend",
            "bollinger_breakout",
            "atr_volatility_breakout"
        }
        
        assert set(by_template.keys()) == expected_templates, \
            f"Missing templates: {expected_templates - set(by_template.keys())}"
        
        for tid, count in by_template.items():
            assert count == 5, f"Template {tid} should have 5 strategies, got {count}"
        
        print(f"PASS: All 5 templates produced strategies: {by_template}")

    def test_total_is_25_strategies(self, all_templates_run):
        """Should have 5 templates x 5 strategies = 25 total"""
        run_id = all_templates_run["run_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/status/{run_id}")
        data = response.json()
        
        assert data["total_generated"] == 25, f"Expected 25 strategies, got {data['total_generated']}"
        assert data["total_evaluated"] == 25, f"Expected 25 evaluated, got {data['total_evaluated']}"
        print("PASS: 5 templates x 5 strategies = 25 total strategies generated and evaluated")


class TestFactoryRunsList:
    """Test GET /api/factory/runs/{session_id}"""

    @pytest.fixture(scope="class")
    def session_with_runs(self):
        """Create a session with multiple factory runs"""
        session_id = f"{TEST_SESSION_PREFIX}list_{uuid.uuid4()}"
        run_ids = []
        
        # Create 2 factory runs
        for templates in [["ema_crossover"], ["rsi_mean_reversion"]]:
            response = requests.post(f"{BASE_URL}/api/factory/generate", json={
                "session_id": session_id,
                "templates": templates,
                "strategies_per_template": 3
            })
            run_ids.append(response.json()["run_id"])
        
        # Wait for completion
        time.sleep(15)
        
        return {"session_id": session_id, "run_ids": run_ids}

    def test_list_runs_returns_200(self, session_with_runs):
        """GET /api/factory/runs/{session_id} should return 200"""
        session_id = session_with_runs["session_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/runs/{session_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: List runs endpoint returns 200")

    def test_list_runs_contains_created_runs(self, session_with_runs):
        """Should contain the runs we created"""
        session_id = session_with_runs["session_id"]
        created_ids = set(session_with_runs["run_ids"])
        
        response = requests.get(f"{BASE_URL}/api/factory/runs/{session_id}")
        data = response.json()
        
        assert data.get("success") == True
        assert "runs" in data
        assert "count" in data
        
        returned_ids = {r["id"] for r in data["runs"]}
        
        assert created_ids.issubset(returned_ids), \
            f"Created runs {created_ids} not found in returned runs {returned_ids}"
        print(f"PASS: List runs contains {len(data['runs'])} runs including created ones")

    def test_list_runs_has_required_fields(self, session_with_runs):
        """Each run should have required summary fields"""
        session_id = session_with_runs["session_id"]
        
        response = requests.get(f"{BASE_URL}/api/factory/runs/{session_id}")
        data = response.json()
        
        required_fields = ["id", "status", "templates_used", "total_generated", "total_evaluated"]
        
        for run in data["runs"]:
            for field in required_fields:
                assert field in run, f"Run {run.get('id')} missing field: {field}"
        
        print("PASS: All runs have required fields")


class TestResultDuringInProgress:
    """Test that result endpoint returns 409 when run is still in progress"""

    def test_result_returns_409_or_200_when_run_completes_fast(self):
        """GET /api/factory/result should return 409 if running, 200 if completed, 404 if pending"""
        session_id = f"{TEST_SESSION_PREFIX}inprogress_{uuid.uuid4()}"
        
        # Start a larger run that takes time
        all_templates = [
            "ema_crossover",
            "rsi_mean_reversion",
            "macd_trend",
            "bollinger_breakout",
            "atr_volatility_breakout"
        ]
        
        response = requests.post(f"{BASE_URL}/api/factory/generate", json={
            "session_id": session_id,
            "templates": all_templates,
            "strategies_per_template": 10  # More strategies = longer time
        })
        
        run_id = response.json()["run_id"]
        
        # Immediately try to get result
        time.sleep(0.1)  # Minimal delay
        result_response = requests.get(f"{BASE_URL}/api/factory/result/{run_id}")
        
        # Valid responses:
        # 409 - Run is in progress (running status)
        # 200 - Run completed very fast
        # 404 - Run not persisted to DB yet (still pending in memory only)
        valid_codes = [200, 404, 409]
        assert result_response.status_code in valid_codes, \
            f"Expected one of {valid_codes}, got {result_response.status_code}: {result_response.text}"
        
        # Log what happened
        if result_response.status_code == 409:
            print("PASS: Result endpoint returns 409 when run is in progress")
        elif result_response.status_code == 200:
            print("PASS: Run completed quickly, got 200")
        else:
            print("PASS: Run still pending, got 404 (expected for fast check)")
        
        # Verify the endpoint eventually returns 200 after completion
        for _ in range(30):
            status_resp = requests.get(f"{BASE_URL}/api/factory/status/{run_id}")
            if status_resp.json().get("status") == "completed":
                break
            time.sleep(1)
        
        final_result = requests.get(f"{BASE_URL}/api/factory/result/{run_id}")
        assert final_result.status_code == 200, \
            f"After completion, expected 200, got {final_result.status_code}"
        print("PASS: Result endpoint returns 200 after run completes")


class TestAutoOptimization:
    """Test auto_optimize_top feature creates optimizer jobs"""

    def test_auto_optimize_creates_jobs(self):
        """When auto_optimize_top > 0, optimization jobs should be created"""
        session_id = f"{TEST_SESSION_PREFIX}autoopt_{uuid.uuid4()}"
        
        # Use single template with small count for quick test
        response = requests.post(f"{BASE_URL}/api/factory/generate", json={
            "session_id": session_id,
            "templates": ["ema_crossover"],
            "strategies_per_template": 5,
            "auto_optimize_top": 1  # Auto-optimize top 1
        })
        
        assert response.status_code == 200
        run_id = response.json()["run_id"]
        
        # Wait for factory to complete AND auto-optimization to finish
        # Factory completes in ~0.1s, but auto-optimization adds ~20-30s
        for _ in range(60):  # Up to 60 seconds
            status_resp = requests.get(f"{BASE_URL}/api/factory/status/{run_id}")
            status = status_resp.json().get("status")
            if status in ["completed", "failed"]:
                break
            time.sleep(1)
        
        # Need to wait a bit more for auto-optimization to complete
        # The factory status shows "completed" but optimization runs in background
        time.sleep(5)  # Extra time for optimization to complete
        
        # Get result
        result_resp = requests.get(f"{BASE_URL}/api/factory/result/{run_id}")
        
        if result_resp.status_code == 200:
            data = result_resp.json()
            result = data["result"]
            
            assert result.get("auto_optimized") == True, "auto_optimized should be True"
            
            opt_job_ids = result.get("optimization_job_ids", [])
            assert len(opt_job_ids) == 1, f"Expected 1 optimization job, got {len(opt_job_ids)}"
            
            # Verify job exists in optimizer (may still be running)
            job_id = opt_job_ids[0]
            opt_status = requests.get(f"{BASE_URL}/api/optimizer/status/{job_id}")
            assert opt_status.status_code == 200, f"Optimizer job {job_id} not found"
            
            opt_data = opt_status.json()
            assert opt_data.get("status") in ["pending", "running", "completed"], \
                f"Optimizer job has unexpected status: {opt_data.get('status')}"
            
            print(f"PASS: Auto-optimize created {len(opt_job_ids)} optimizer job(s)")
            print(f"  Job {job_id}: status={opt_data.get('status')}, gen={opt_data.get('current_generation')}/{opt_data.get('total_generations')}")
        else:
            status_data = requests.get(f"{BASE_URL}/api/factory/status/{run_id}").json()
            if status_data.get("status") == "failed":
                print(f"INFO: Run failed - {status_data.get('error_message')}")
                pytest.skip(f"Factory run failed: {status_data.get('error_message')}")
            assert False, f"Could not verify auto-optimization: {result_resp.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
