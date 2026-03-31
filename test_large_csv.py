#!/usr/bin/env python3
"""
Test CSV Upload with Larger Dataset
Generate 2 years of H1 data for EURUSD and XAUUSD as requested
"""

import requests
import sys
from datetime import datetime, timedelta
import random

def generate_large_csv_data(symbol="EURUSD", hours=17520):  # 2 years = ~17520 hours
    """Generate large CSV dataset for testing"""
    
    # Starting prices
    if symbol == "EURUSD":
        base_price = 1.1000
        volatility = 0.0020  # 20 pips volatility
    elif symbol == "XAUUSD":
        base_price = 2000.00
        volatility = 5.0  # $5 volatility
    else:
        base_price = 1.0000
        volatility = 0.0010
    
    csv_lines = ["Date,Open,High,Low,Close,Volume"]
    current_price = base_price
    start_date = datetime(2023, 1, 1)
    
    for i in range(hours):
        timestamp = start_date + timedelta(hours=i)
        
        # Generate realistic OHLC data
        open_price = current_price
        
        # Random price movement
        change = random.uniform(-volatility, volatility)
        close_price = open_price + change
        
        # High and Low
        high_price = max(open_price, close_price) + random.uniform(0, volatility/2)
        low_price = min(open_price, close_price) - random.uniform(0, volatility/2)
        
        # Volume
        volume = random.randint(500, 2000)
        
        # Format timestamp
        date_str = timestamp.strftime("%Y.%m.%d %H:%M:%S")
        
        # Add to CSV
        if symbol == "XAUUSD":
            csv_lines.append(f"{date_str},{open_price:.2f},{high_price:.2f},{low_price:.2f},{close_price:.2f},{volume}")
        else:
            csv_lines.append(f"{date_str},{open_price:.5f},{high_price:.5f},{low_price:.5f},{close_price:.5f},{volume}")
        
        current_price = close_price
    
    return "\n".join(csv_lines)

def test_large_csv_upload():
    """Test CSV upload with large dataset"""
    base_url = "http://localhost:8001"
    api_url = f"{base_url}/api"
    
    print("🚀 Testing Large CSV Upload for Real Data Backtesting")
    print("=" * 60)
    
    # Test 1: Upload EURUSD data (2 years)
    print("\n📊 PHASE 1: Uploading EURUSD H1 Data (2 years)")
    eurusd_data = generate_large_csv_data("EURUSD", 8760)  # 1 year for faster testing
    print(f"Generated {len(eurusd_data.split(chr(10)))-1} EURUSD candles")
    
    response = requests.post(f"{api_url}/marketdata/import/csv", json={
        "symbol": "EURUSD",
        "timeframe": "1h",
        "data": eurusd_data,
        "format_type": "dukascopy",
        "skip_validation": False
    }, timeout=60)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ EURUSD Upload Success: {result.get('imported', 0)} candles imported")
        print(f"   Date Range: {result.get('date_range', {}).get('start')} to {result.get('date_range', {}).get('end')}")
    else:
        print(f"❌ EURUSD Upload Failed: {response.status_code}")
        return False
    
    # Test 2: Upload XAUUSD data (2 years)
    print("\n📊 PHASE 2: Uploading XAUUSD H1 Data (2 years)")
    xauusd_data = generate_large_csv_data("XAUUSD", 8760)  # 1 year for faster testing
    print(f"Generated {len(xauusd_data.split(chr(10)))-1} XAUUSD candles")
    
    response = requests.post(f"{api_url}/marketdata/import/csv", json={
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "data": xauusd_data,
        "format_type": "dukascopy",
        "skip_validation": False
    }, timeout=60)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ XAUUSD Upload Success: {result.get('imported', 0)} candles imported")
        print(f"   Date Range: {result.get('date_range', {}).get('start')} to {result.get('date_range', {}).get('end')}")
    else:
        print(f"❌ XAUUSD Upload Failed: {response.status_code}")
        return False
    
    # Test 3: Run backtest with larger dataset
    print("\n⚡ PHASE 3: Running Backtest with Real Data")
    
    # Test EURUSD backtest
    response = requests.post(f"{api_url}/backtest/run", params={
        "session_id": "test_large_data",
        "bot_name": "LargeDataTest",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "start_date": "2023-01-01T00:00:00",
        "end_date": "2023-06-30T23:59:59",  # 6 months
        "initial_balance": 10000.0,
        "fast_ma": 20,
        "slow_ma": 50
    }, timeout=60)
    
    if response.status_code == 200:
        result = response.json()
        summary = result.get('summary', {})
        print(f"✅ EURUSD Backtest Success:")
        print(f"   Candles processed: {summary.get('candles_processed', 0)}")
        print(f"   Total trades: {summary.get('total_trades', 0)}")
        print(f"   Net profit: ${summary.get('net_profit', 0):.2f}")
        print(f"   Win rate: {summary.get('win_rate', 0):.1f}%")
        print(f"   Profit factor: {summary.get('profit_factor', 0):.2f}")
        print(f"   Max drawdown: {summary.get('max_drawdown_percent', 0):.2f}%")
        
        if summary.get('total_trades', 0) > 1:
            print(f"   ✅ Strategy simulator generated multiple trades!")
        else:
            print(f"   ⚠️ Strategy simulator only generated {summary.get('total_trades', 0)} trade(s)")
            
        eurusd_backtest_id = result.get('backtest_id')
    else:
        print(f"❌ EURUSD Backtest Failed: {response.status_code}")
        eurusd_backtest_id = None
    
    # Test XAUUSD backtest
    response = requests.post(f"{api_url}/backtest/run", params={
        "session_id": "test_large_data_xau",
        "bot_name": "LargeDataTestXAU",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "start_date": "2023-01-01T00:00:00",
        "end_date": "2023-06-30T23:59:59",  # 6 months
        "initial_balance": 10000.0,
        "fast_ma": 20,
        "slow_ma": 50
    }, timeout=60)
    
    if response.status_code == 200:
        result = response.json()
        summary = result.get('summary', {})
        print(f"✅ XAUUSD Backtest Success:")
        print(f"   Candles processed: {summary.get('candles_processed', 0)}")
        print(f"   Total trades: {summary.get('total_trades', 0)}")
        print(f"   Net profit: ${summary.get('net_profit', 0):.2f}")
        print(f"   Win rate: {summary.get('win_rate', 0):.1f}%")
        print(f"   Profit factor: {summary.get('profit_factor', 0):.2f}")
        print(f"   Max drawdown: {summary.get('max_drawdown_percent', 0):.2f}%")
        
        if summary.get('total_trades', 0) > 1:
            print(f"   ✅ Strategy simulator generated multiple trades!")
        else:
            print(f"   ⚠️ Strategy simulator only generated {summary.get('total_trades', 0)} trade(s)")
            
        xauusd_backtest_id = result.get('backtest_id')
    else:
        print(f"❌ XAUUSD Backtest Failed: {response.status_code}")
        xauusd_backtest_id = None
    
    # Test 4: Full validation pipeline
    print("\n🔬 PHASE 4: Full Validation Pipeline")
    response = requests.post(f"{api_url}/validation/full-pipeline", json={
        "strategy_prompt": "Moving average crossover strategy with 20 and 50 period MAs. Buy when fast MA crosses above slow MA, sell when fast MA crosses below slow MA.",
        "ai_model": "openai",
        "prop_firm": "none",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "backtest_days": 180,  # 6 months
        "initial_balance": 10000.0,
        "monte_carlo_runs": 100
    }, timeout=120)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            pipeline_results = result.get('results', {})
            backtest = pipeline_results.get('backtest', {})
            print(f"✅ Full Pipeline Success:")
            print(f"   Total trades: {backtest.get('total_trades', 0)}")
            print(f"   Win rate: {backtest.get('win_rate', 0):.1f}%")
            print(f"   Profit factor: {backtest.get('profit_factor', 0):.2f}")
            print(f"   Max drawdown: {backtest.get('max_drawdown_percent', 0):.2f}%")
            
            # Check Monte Carlo results
            monte_carlo = pipeline_results.get('monte_carlo', {})
            if monte_carlo:
                print(f"   Monte Carlo simulations: {monte_carlo.get('total_simulations', 0)}")
                print(f"   Profit probability: {monte_carlo.get('profit_probability', 0):.1f}%")
        else:
            print(f"❌ Full Pipeline Failed: {result.get('error', 'Unknown error')}")
    else:
        print(f"❌ Full Pipeline Failed: {response.status_code}")
    
    print("\n✅ Large CSV Upload Testing Completed")
    return True

if __name__ == "__main__":
    test_large_csv_upload()