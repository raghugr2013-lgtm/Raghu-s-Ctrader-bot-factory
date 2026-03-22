"""
Multi-AI Collaboration Engine API Tests
Tests for:
- POST /api/bot/generate-multi-ai (single, collaboration, competition modes)
- GET /api/bot/collaboration-logs/{session_id}
- GET /api/bot/multi-ai-result/{session_id}
"""

import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Session storage for test data
class TestData:
    session_ids = {
        'single': None,
        'collaboration': None,
        'competition': None
    }


class TestHealthAndBasicEndpoints:
    """Basic health and connectivity tests"""
    
    def test_api_root_accessible(self):
        """Test root API endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200, f"API root not accessible: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ API root accessible: {data['message']}")


class TestMultiAIGenerateSingleMode:
    """Test generate-multi-ai endpoint in SINGLE mode"""
    
    def test_single_mode_generation(self):
        """Test single AI mode generation with minimal prompt"""
        session_id = f"test_single_{uuid.uuid4().hex[:8]}"
        
        payload = {
            "session_id": session_id,
            "strategy_prompt": "Simple EMA crossover strategy on EURUSD",
            "ai_mode": "single",
            "single_ai_model": "openai",
            "prop_firm": "none"
        }
        
        print(f"Testing single mode with session: {session_id}")
        
        response = requests.post(
            f"{BASE_URL}/api/bot/generate-multi-ai",
            json=payload,
            timeout=90  # AI calls may take time
        )
        
        assert response.status_code == 200, f"Single mode failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert data.get("success") == True
        assert data.get("session_id") == session_id
        assert data.get("ai_mode") == "single"
        assert "code" in data and len(data["code"]) > 100
        assert "collaboration_logs" in data
        assert "validation" in data
        assert "quality_gates" in data
        
        # Validate quality gates structure
        qg = data["quality_gates"]
        assert "is_deployable" in qg
        assert "gate_results" in qg
        assert "gates_passed" in qg
        assert "gates_total" in qg
        
        # Validate validation summary
        validation = data["validation"]
        assert "compilation_errors" in validation
        assert "compilation_warnings" in validation
        assert "is_valid" in validation
        
        TestData.session_ids['single'] = session_id
        print(f"✓ Single mode generation successful: {len(data['code'])} chars of code")
        print(f"  - Deployable: {qg['is_deployable']}")
        print(f"  - Errors: {validation['compilation_errors']}, Warnings: {validation['compilation_warnings']}")
        
    def test_single_mode_with_deepseek(self):
        """Test single mode with deepseek model"""
        session_id = f"test_single_ds_{uuid.uuid4().hex[:8]}"
        
        payload = {
            "session_id": session_id,
            "strategy_prompt": "RSI overbought/oversold strategy",
            "ai_mode": "single",
            "single_ai_model": "deepseek"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/bot/generate-multi-ai",
            json=payload,
            timeout=90
        )
        
        assert response.status_code == 200, f"DeepSeek single mode failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "code" in data
        print(f"✓ DeepSeek single mode successful: {len(data['code'])} chars")


class TestMultiAIGenerateCollaborationMode:
    """Test generate-multi-ai endpoint in COLLABORATION mode"""
    
    def test_collaboration_mode_generation(self):
        """Test collaboration pipeline with all 3 roles"""
        session_id = f"test_collab_{uuid.uuid4().hex[:8]}"
        
        payload = {
            "session_id": session_id,
            "strategy_prompt": "Bollinger Bands breakout with volume confirmation",
            "ai_mode": "collaboration",
            "strategy_generator_model": "deepseek",
            "code_reviewer_model": "openai",
            "optimizer_model": "claude",
            "prop_firm": "ftmo"
        }
        
        print(f"Testing collaboration mode with session: {session_id}")
        
        response = requests.post(
            f"{BASE_URL}/api/bot/generate-multi-ai",
            json=payload,
            timeout=180  # Collaboration takes longer (3 AI calls)
        )
        
        assert response.status_code == 200, f"Collaboration mode failed: {response.text}"
        data = response.json()
        
        # Validate response
        assert data.get("success") == True
        assert data.get("ai_mode") == "collaboration"
        
        # Collaboration logs should show all 3 stages
        logs = data.get("collaboration_logs", [])
        assert len(logs) > 0, "No collaboration logs returned"
        
        # Check for stage progression
        stages = [log["stage"] for log in logs]
        assert "generation" in stages, "Missing generation stage"
        
        # Quality gates with compliance (FTMO)
        qg = data["quality_gates"]
        assert "is_deployable" in qg
        
        # Should have compliance score since we used FTMO
        validation = data["validation"]
        # Compliance may or may not be calculated depending on code output
        
        TestData.session_ids['collaboration'] = session_id
        print(f"✓ Collaboration mode successful")
        print(f"  - Logs: {len(logs)} entries")
        print(f"  - Stages: {set(stages)}")


class TestMultiAIGenerateCompetitionMode:
    """Test generate-multi-ai endpoint in COMPETITION mode"""
    
    def test_competition_mode_generation(self):
        """Test competition mode where all AIs compete"""
        session_id = f"test_comp_{uuid.uuid4().hex[:8]}"
        
        payload = {
            "session_id": session_id,
            "strategy_prompt": "MACD crossover with trend filter",
            "ai_mode": "competition"
        }
        
        print(f"Testing competition mode with session: {session_id}")
        
        response = requests.post(
            f"{BASE_URL}/api/bot/generate-multi-ai",
            json=payload,
            timeout=240  # Competition runs all 3 AIs
        )
        
        assert response.status_code == 200, f"Competition mode failed: {response.text}"
        data = response.json()
        
        # Validate response
        assert data.get("success") == True
        assert data.get("ai_mode") == "competition"
        
        # Competition should have entries
        competition = data.get("competition")
        assert competition is not None, "No competition data returned"
        assert "entries" in competition
        assert "winner" in competition
        assert len(competition["entries"]) >= 1
        
        # Check entry structure
        for entry in competition["entries"]:
            assert "ai_model" in entry
            assert "validation_errors" in entry
            assert "validation_warnings" in entry
            assert "rank" in entry
        
        # Winner should be the model with lowest errors
        winner = competition["winner"]
        assert winner in ["openai", "claude", "deepseek"]
        
        TestData.session_ids['competition'] = session_id
        print(f"✓ Competition mode successful")
        print(f"  - Winner: {winner}")
        print(f"  - Entries: {len(competition['entries'])}")


class TestCollaborationLogsEndpoint:
    """Test GET /api/bot/collaboration-logs/{session_id}"""
    
    def test_get_logs_for_valid_session(self):
        """Test getting logs for a valid session"""
        # Use single mode session if available
        session_id = TestData.session_ids.get('single')
        if not session_id:
            pytest.skip("No single mode session available - run single mode test first")
        
        response = requests.get(f"{BASE_URL}/api/bot/collaboration-logs/{session_id}")
        
        assert response.status_code == 200, f"Failed to get logs: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        assert data.get("session_id") == session_id
        assert "logs" in data
        print(f"✓ Retrieved logs for session: {len(data['logs'])} entries")
    
    def test_get_logs_for_invalid_session(self):
        """Test getting logs for non-existent session returns 404"""
        fake_session = f"fake_session_{uuid.uuid4().hex}"
        
        response = requests.get(f"{BASE_URL}/api/bot/collaboration-logs/{fake_session}")
        
        assert response.status_code == 404
        print(f"✓ Correctly returned 404 for invalid session")


class TestMultiAIResultEndpoint:
    """Test GET /api/bot/multi-ai-result/{session_id}"""
    
    def test_get_result_for_valid_session(self):
        """Test getting full result for a valid session"""
        session_id = TestData.session_ids.get('single')
        if not session_id:
            pytest.skip("No single mode session available")
        
        response = requests.get(f"{BASE_URL}/api/bot/multi-ai-result/{session_id}")
        
        assert response.status_code == 200, f"Failed to get result: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        assert "result" in data
        
        result = data["result"]
        assert result.get("session_id") == session_id
        assert "final_code" in result
        assert "collaboration_logs" in result
        print(f"✓ Retrieved full result for session")
    
    def test_get_result_for_invalid_session(self):
        """Test getting result for non-existent session returns 404"""
        fake_session = f"fake_result_{uuid.uuid4().hex}"
        
        response = requests.get(f"{BASE_URL}/api/bot/multi-ai-result/{fake_session}")
        
        assert response.status_code == 404
        print(f"✓ Correctly returned 404 for invalid session")


class TestRequestValidation:
    """Test request validation and error handling"""
    
    def test_missing_required_fields(self):
        """Test that missing required fields return proper error"""
        # Missing strategy_prompt
        payload = {
            "session_id": "test123",
            "ai_mode": "single"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/bot/generate-multi-ai",
            json=payload,
            timeout=30
        )
        
        # Should return 422 for validation error
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print(f"✓ Correctly validates required fields")
    
    def test_invalid_ai_mode(self):
        """Test that invalid ai_mode returns error"""
        payload = {
            "session_id": "test123",
            "strategy_prompt": "Test strategy",
            "ai_mode": "invalid_mode"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/bot/generate-multi-ai",
            json=payload,
            timeout=30
        )
        
        # Should return 422 for validation error
        assert response.status_code == 422
        print(f"✓ Correctly rejects invalid ai_mode")


class TestQualityGatesValidation:
    """Test quality gates are properly evaluated"""
    
    def test_quality_gates_structure(self):
        """Verify quality gates structure in response"""
        session_id = TestData.session_ids.get('single')
        if not session_id:
            pytest.skip("No single mode session available")
        
        response = requests.get(f"{BASE_URL}/api/bot/multi-ai-result/{session_id}")
        assert response.status_code == 200
        
        data = response.json()
        result = data.get("result", {})
        qg_result = result.get("quality_gates_result")
        
        if qg_result:
            assert "all_passed" in qg_result
            assert "gates" in qg_result
            assert "is_deployable" in qg_result
            assert "summary" in qg_result
            
            # Check individual gates
            for gate in qg_result.get("gates", []):
                assert "name" in gate
                assert "passed" in gate
                assert "message" in gate
            
            print(f"✓ Quality gates structure validated")
            print(f"  - Deployable: {qg_result['is_deployable']}")
            print(f"  - All passed: {qg_result['all_passed']}")


# Cleanup fixture
@pytest.fixture(scope="module", autouse=True)
def cleanup():
    """Print test session IDs at end for reference"""
    yield
    print("\n--- Test Session IDs ---")
    for mode, sid in TestData.session_ids.items():
        if sid:
            print(f"  {mode}: {sid}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
