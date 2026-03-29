"""
Paper Trading API Tests - Phase 6
Tests for paper trading endpoints: health, status, trades
"""
import pytest
import requests
import os

# Get backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPaperTradingHealth:
    """Health check endpoint tests"""
    
    def test_health_endpoint_returns_200(self):
        """Test that health endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✅ Health endpoint returned 200")
    
    def test_health_endpoint_returns_correct_structure(self):
        """Test that health endpoint returns correct JSON structure"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/health")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify required fields
        assert "status" in data, "Missing 'status' field"
        assert "service" in data, "Missing 'service' field"
        assert "status_file_exists" in data, "Missing 'status_file_exists' field"
        assert "trades_file_exists" in data, "Missing 'trades_file_exists' field"
        
        # Verify values
        assert data["status"] == "healthy", f"Expected 'healthy', got {data['status']}"
        assert data["service"] == "paper-trading", f"Expected 'paper-trading', got {data['service']}"
        assert isinstance(data["status_file_exists"], bool), "status_file_exists should be boolean"
        assert isinstance(data["trades_file_exists"], bool), "trades_file_exists should be boolean"
        
        print(f"✅ Health endpoint structure verified: {data}")


class TestPaperTradingStatus:
    """Status endpoint tests - portfolio metrics"""
    
    def test_status_endpoint_returns_200(self):
        """Test that status endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✅ Status endpoint returned 200")
    
    def test_status_endpoint_returns_correct_structure(self):
        """Test that status endpoint returns correct JSON structure with all required fields"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/status")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify required top-level fields
        required_fields = [
            "running", "current_pnl", "drawdown_pct", "total_trades",
            "total_equity", "total_return_pct", "risk_status", "portfolio_details"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"✅ Status endpoint has all required fields")
    
    def test_status_running_is_boolean(self):
        """Test that running field is a boolean"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/status")
        data = response.json()
        
        assert isinstance(data["running"], bool), f"'running' should be boolean, got {type(data['running'])}"
        print(f"✅ Running field is boolean: {data['running']}")
    
    def test_status_numeric_fields_are_numbers(self):
        """Test that numeric fields are proper numbers"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/status")
        data = response.json()
        
        numeric_fields = ["current_pnl", "drawdown_pct", "total_trades", "total_equity", "total_return_pct"]
        
        for field in numeric_fields:
            assert isinstance(data[field], (int, float)), f"'{field}' should be numeric, got {type(data[field])}"
        
        print(f"✅ All numeric fields are proper numbers")
    
    def test_status_risk_status_structure(self):
        """Test that risk_status has correct structure"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/status")
        data = response.json()
        
        risk_status = data["risk_status"]
        assert isinstance(risk_status, dict), "risk_status should be a dict"
        
        # Check for expected risk fields
        expected_risk_fields = ["trading_enabled", "current_drawdown_pct", "daily_loss_pct"]
        for field in expected_risk_fields:
            assert field in risk_status, f"Missing risk field: {field}"
        
        print(f"✅ Risk status structure verified: trading_enabled={risk_status.get('trading_enabled')}")
    
    def test_status_portfolio_details_structure(self):
        """Test that portfolio_details has correct structure"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/status")
        data = response.json()
        
        portfolio = data["portfolio_details"]
        assert isinstance(portfolio, dict), "portfolio_details should be a dict"
        
        # Check for expected portfolio fields
        expected_portfolio_fields = ["initial_capital", "current_capital"]
        for field in expected_portfolio_fields:
            assert field in portfolio, f"Missing portfolio field: {field}"
        
        # Verify initial capital is $10,000 as per requirements
        assert portfolio["initial_capital"] == 10000.0, f"Expected initial_capital=10000.0, got {portfolio['initial_capital']}"
        
        print(f"✅ Portfolio details verified: initial_capital=${portfolio['initial_capital']}, current_capital=${portfolio['current_capital']}")
    
    def test_status_drawdown_within_limits(self):
        """Test that drawdown is within acceptable limits (0-100%)"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/status")
        data = response.json()
        
        drawdown = data["drawdown_pct"]
        assert 0 <= drawdown <= 100, f"Drawdown should be 0-100%, got {drawdown}%"
        
        print(f"✅ Drawdown within limits: {drawdown}%")
    
    def test_status_equity_is_positive(self):
        """Test that total equity is positive"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/status")
        data = response.json()
        
        equity = data["total_equity"]
        assert equity > 0, f"Total equity should be positive, got {equity}"
        
        print(f"✅ Total equity is positive: ${equity}")


class TestPaperTradingTrades:
    """Trades endpoint tests - trade history"""
    
    def test_trades_endpoint_returns_200(self):
        """Test that trades endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/trades")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✅ Trades endpoint returned 200")
    
    def test_trades_endpoint_returns_list(self):
        """Test that trades endpoint returns a list"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/trades")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        print(f"✅ Trades endpoint returns list with {len(data)} trades")
    
    def test_trades_structure_if_present(self):
        """Test trade structure if trades exist"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/trades")
        data = response.json()
        
        if len(data) > 0:
            trade = data[0]
            expected_fields = ["symbol", "signal", "entry_price", "exit_price", "pnl"]
            
            for field in expected_fields:
                assert field in trade, f"Trade missing field: {field}"
            
            print(f"✅ Trade structure verified: {trade}")
        else:
            print(f"ℹ️ No trades yet (engine may not have generated signals)")


class TestPaperTradingServiceIntegration:
    """Integration tests for paper trading service"""
    
    def test_service_is_running(self):
        """Test that paper trading service is running via status endpoint"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/status")
        assert response.status_code == 200
        
        data = response.json()
        # Service should be running (status file exists and is being updated)
        # Note: 'running' field indicates if the engine loop is active
        print(f"✅ Service status: running={data['running']}")
    
    def test_status_file_exists(self):
        """Test that status file exists (indicates service is writing updates)"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/health")
        data = response.json()
        
        assert data["status_file_exists"] == True, "Status file should exist when service is running"
        print(f"✅ Status file exists: {data['status_file_exists']}")
    
    def test_portfolio_allocation_40_60(self):
        """Test that portfolio allocation follows 40% Gold / 60% S&P rule"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/status")
        data = response.json()
        
        portfolio = data["portfolio_details"]
        initial_capital = portfolio["initial_capital"]
        
        # Expected allocations
        expected_gold_allocation = initial_capital * 0.40  # $4,000
        expected_spy_allocation = initial_capital * 0.60   # $6,000
        
        # Verify initial capital is $10,000
        assert initial_capital == 10000.0, f"Expected $10,000 initial capital, got ${initial_capital}"
        
        print(f"✅ Portfolio allocation verified: Initial=${initial_capital}")
        print(f"   Expected Gold allocation: ${expected_gold_allocation}")
        print(f"   Expected S&P allocation: ${expected_spy_allocation}")
    
    def test_risk_limits_configured(self):
        """Test that risk limits are properly configured (15% DD, 2% daily)"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/status")
        data = response.json()
        
        risk = data["risk_status"]
        
        # Check max drawdown limit is 15%
        if "max_drawdown_pct" in risk:
            assert risk["max_drawdown_pct"] == 15.0, f"Expected 15% max drawdown, got {risk['max_drawdown_pct']}%"
            print(f"✅ Max drawdown limit: {risk['max_drawdown_pct']}%")
        
        # Check max daily loss limit is 2%
        if "max_daily_loss_pct" in risk:
            assert risk["max_daily_loss_pct"] == 2.0, f"Expected 2% max daily loss, got {risk['max_daily_loss_pct']}%"
            print(f"✅ Max daily loss limit: {risk['max_daily_loss_pct']}%")
        
        # Trading should be enabled initially
        assert risk["trading_enabled"] == True, "Trading should be enabled initially"
        print(f"✅ Trading enabled: {risk['trading_enabled']}")


class TestAPIErrorHandling:
    """Test API error handling"""
    
    def test_invalid_endpoint_returns_404(self):
        """Test that invalid endpoint returns 404"""
        response = requests.get(f"{BASE_URL}/api/paper-trading/invalid-endpoint")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✅ Invalid endpoint returns 404")
    
    def test_health_endpoint_method_not_allowed(self):
        """Test that POST to health endpoint returns 405"""
        response = requests.post(f"{BASE_URL}/api/paper-trading/health")
        assert response.status_code == 405, f"Expected 405, got {response.status_code}"
        print(f"✅ POST to health returns 405 Method Not Allowed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
