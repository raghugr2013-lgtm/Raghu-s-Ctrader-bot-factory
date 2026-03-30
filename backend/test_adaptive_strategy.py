"""
Test Adaptive EURUSD Strategy
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from auto_fetch_candles import auto_fetch_candles, MIN_CANDLES_REQUIRED
from market_data_service import init_market_data_service
from backtest_models import BacktestConfig, Timeframe
from adaptive_eurusd_strategy import run_adaptive_eurusd_strategy
from test_eurusd_strategy import calculate_metrics, print_backtest_results

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')


async def test_adaptive_strategy():
    """Test adaptive strategy"""
    
    print("="*70)
    print("ADAPTIVE EURUSD STRATEGY BACKTEST")
    print("="*70)
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Fetch data
    print(f"\n📊 Fetching EURUSD 1h data...")
    
    result = await auto_fetch_candles(
        db=db,
        market_data_service=market_data_service,
        symbol="EURUSD",
        timeframe="1h",
        min_candles=MIN_CANDLES_REQUIRED
    )
    
    if not result.success:
        print(f"❌ Failed to fetch data: {result.error}")
        client.close()
        return False
    
    print(f"✅ Fetched {result.candle_count} candles from {result.source}")
    
    candles = result.candles
    
    # Create config
    config = BacktestConfig(
        symbol="EURUSD",
        timeframe=Timeframe.H1,
        start_date=candles[0].timestamp,
        end_date=candles[-1].timestamp,
        initial_balance=10000.0,
        spread_pips=1.5,
        commission_per_lot=7.0,
        leverage=100,
    )
    
    print(f"\n⚙️  Running adaptive strategy...")
    
    # Run backtest
    trades, equity_curve = run_adaptive_eurusd_strategy(candles, config)
    
    # Calculate metrics
    metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
    
    # Print results
    print_backtest_results({}, metrics, trades)
    
    client.close()
    
    return metrics


if __name__ == "__main__":
    asyncio.run(test_adaptive_strategy())
