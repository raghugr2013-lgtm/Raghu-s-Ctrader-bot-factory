"""
Test script to verify M1 data loading and RealBacktester execution.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
import time

async def test_full_backtest():
    """Test complete backtest with real M1 data"""
    
    print("="*80)
    print("🧪 TESTING REAL M1 DATA BACKTEST")
    print("="*80)
    print()
    
    # Setup
    from data_ingestion.data_service_v2 import DataServiceV2
    from real_backtester import RealBacktester
    from intelligent_strategy_generator import IntelligentStrategyGenerator
    
    # Connect to database
    client = MongoClient("mongodb://localhost:27017")
    db = client["test_database"]
    
    # Initialize services
    data_service = DataServiceV2(db)
    backtester = RealBacktester()
    generator = IntelligentStrategyGenerator()
    
    print("1️⃣ Loading M1 Data from SSOT")
    print("-" * 80)
    
    # Define date range (365 days)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=365)
    
    print(f"   Symbol: EURUSD")
    print(f"   Period: {start_date.date()} to {end_date.date()}")
    print(f"   Days: 365")
    print()
    
    # Load data
    load_start = time.time()
    result = await data_service.get_candles(
        symbol="EURUSD",
        timeframe="M1",
        start_date=start_date,
        end_date=end_date,
        min_confidence="high",
        use_case="production_backtest"
    )
    load_time = time.time() - load_start
    
    print(f"   ✅ Data loaded in {load_time:.3f}s")
    print(f"   📊 Result type: {type(result).__name__}")
    print(f"   📊 Has candles attribute: {hasattr(result, 'candles')}")
    
    if hasattr(result, 'candles'):
        candles = result.candles
        print(f"   📊 Candles loaded: {len(candles):,}")
        print(f"   📊 Candles type: {type(candles)}")
        
        if candles:
            print(f"   📊 First candle: {candles[0] if len(candles) > 0 else 'N/A'}")
            print(f"   📊 First candle type: {type(candles[0])}")
    else:
        print("   ❌ No 'candles' attribute found")
        print(f"   Available attributes: {dir(result)}")
        return
    
    if not candles or len(candles) == 0:
        print()
        print("   ❌ NO CANDLES LOADED - Cannot proceed with backtest")
        print()
        return
    
    print()
    print("2️⃣ Generating Test Strategy")
    print("-" * 80)
    
    # Generate one strategy
    strategy = generator.generate_strategy(seed=42, symbol="EURUSD")
    print(f"   Strategy: {strategy.get('strategy_type', 'Unknown')}")
    print(f"   Template: {strategy.get('template_id', 'N/A')}")
    print()
    
    print("3️⃣ Running Backtest with RealBacktester")
    print("-" * 80)
    
    # Run backtest
    backtest_start = time.time()
    
    try:
        backtest_result = backtester.run_backtest(
            strategy=strategy,
            candles=candles,
            initial_balance=10000.0
        )
        backtest_time = time.time() - backtest_start
        
        print(f"   ✅ Backtest completed in {backtest_time:.3f}s")
        print()
        print("   📈 Backtest Results:")
        print(f"      Total Trades: {backtest_result.get('total_trades', 0)}")
        print(f"      Profit Factor: {backtest_result.get('profit_factor', 0):.2f}")
        print(f"      Win Rate: {backtest_result.get('win_rate', 0):.1f}%")
        print(f"      Max Drawdown: {backtest_result.get('max_drawdown_pct', 0):.2f}%")
        print(f"      Net Profit: ${backtest_result.get('net_profit', 0):.2f}")
        print(f"      Sharpe Ratio: {backtest_result.get('sharpe_ratio', 0):.2f}")
        
    except Exception as e:
        backtest_time = time.time() - backtest_start
        print(f"   ❌ Backtest failed in {backtest_time:.3f}s")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    print("="*80)
    print("📊 SUMMARY")
    print("="*80)
    print(f"   M1 Candles Processed: {len(candles):,}")
    print(f"   Data Load Time: {load_time:.3f}s")
    print(f"   Backtest Time: {backtest_time:.3f}s")
    print(f"   Total Time: {load_time + backtest_time:.3f}s")
    print(f"   Trades Executed: {backtest_result.get('total_trades', 0)}")
    print()
    
    # Verify full iteration
    expected_candles_per_year = 365 * 24 * 60  # 525,600 candles
    coverage_pct = (len(candles) / expected_candles_per_year) * 100
    
    print("   ✅ VERIFICATION:")
    print(f"      Real M1 data used: {'YES' if len(candles) > 10000 else 'NO'}")
    print(f"      Full loop execution: {'YES' if backtest_time > 0.1 else 'SUSPICIOUS - Too fast'}")
    print(f"      Coverage: {coverage_pct:.1f}% of expected {expected_candles_per_year:,} candles")
    print()
    
    if len(candles) > 100000:
        print("   ✅ CONFIRMED: Using real M1 historical data")
    else:
        print("   ⚠️  WARNING: Suspiciously few candles loaded")
    
    if backtest_time > 0.5:
        print("   ✅ CONFIRMED: Full backtest loop execution")
    else:
        print("   ⚠️  WARNING: Backtest too fast - may be using shortcuts")
    
    print()


if __name__ == "__main__":
    asyncio.run(test_full_backtest())
