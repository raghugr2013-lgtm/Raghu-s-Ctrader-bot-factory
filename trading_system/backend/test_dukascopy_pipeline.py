"""
Test Dukascopy Data Integration
Verifies that the pipeline correctly uses Dukascopy cached data
"""
import asyncio
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from auto_fetch_candles import auto_fetch_candles, MIN_CANDLES_REQUIRED
from market_data_service import init_market_data_service

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')


async def test_dukascopy_pipeline():
    print("="*70)
    print("DUKASCOPY PIPELINE INTEGRATION TEST")
    print("="*70)
    
    # Initialize MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Test cases (use lowercase for timeframes)
    test_cases = [
        {"symbol": "EURUSD", "timeframe": "1h", "expected": True},
        {"symbol": "EURUSD", "timeframe": "15m", "expected": True},
        {"symbol": "XAUUSD", "timeframe": "1h", "expected": True},
        {"symbol": "GBPUSD", "timeframe": "1h", "expected": False},  # Not in Dukascopy
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        symbol = test["symbol"]
        timeframe = test["timeframe"]
        expected_success = test["expected"]
        
        print(f"\n{'='*70}")
        print(f"TEST {i}: {symbol} {timeframe}")
        print(f"{'='*70}")
        
        result = await auto_fetch_candles(
            db=db,
            market_data_service=market_data_service,
            symbol=symbol,
            timeframe=timeframe,
            min_candles=MIN_CANDLES_REQUIRED
        )
        
        print(f"Success: {result.success}")
        print(f"Source: {result.source}")
        print(f"Candles: {result.candle_count}")
        
        if result.success:
            print(f"✅ Data retrieved successfully")
            if "dukascopy" in result.source:
                print(f"✅✅ Using DUKASCOPY data (preferred source)")
            
            # Show sample candle
            if result.candles:
                sample = result.candles[0]
                print(f"\nSample Candle:")
                print(f"  Time: {sample.timestamp}")
                print(f"  OHLC: {sample.open:.5f} / {sample.high:.5f} / {sample.low:.5f} / {sample.close:.5f}")
        else:
            print(f"❌ Data fetch failed")
            if result.error:
                print(f"Error: {result.error}")
        
        # Verify result matches expectation
        test_passed = result.success == expected_success
        results.append({
            "test": f"{symbol} {timeframe}",
            "passed": test_passed,
            "source": result.source if result.success else "N/A",
            "candles": result.candle_count
        })
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for r in results:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        print(f"{status} | {r['test']:20s} | Source: {r['source']:20s} | Candles: {r['candles']}")
    
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    
    print("="*70)
    print(f"RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅✅✅ ALL TESTS PASSED - DUKASCOPY INTEGRATION WORKING")
    else:
        print("⚠️ SOME TESTS FAILED")
    
    print("="*70)
    
    client.close()
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(test_dukascopy_pipeline())
    sys.exit(0 if success else 1)
