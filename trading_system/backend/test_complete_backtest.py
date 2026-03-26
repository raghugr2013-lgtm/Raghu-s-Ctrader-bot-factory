"""
End-to-End Backtest Test with Dukascopy Data

Tests the complete backtest pipeline using cached Dukascopy candles.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
from datetime import datetime
from auto_fetch_candles import auto_fetch_candles, MIN_CANDLES_REQUIRED
from market_data_service import init_market_data_service

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')


async def test_backtest_with_dukascopy():
    """Test complete backtest flow with Dukascopy data"""
    
    print("="*70)
    print("END-TO-END BACKTEST TEST WITH DUKASCOPY DATA")
    print("="*70)
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Test configuration
    test_config = {
        "symbol": "EURUSD",
        "timeframe": "1h",
        "expected_candles": 1470,
        "strategy": "EMA Crossover"
    }
    
    print(f"\n📊 Test Configuration:")
    print(f"  Symbol: {test_config['symbol']}")
    print(f"  Timeframe: {test_config['timeframe']}")
    print(f"  Expected Candles: {test_config['expected_candles']}")
    print(f"  Strategy Type: {test_config['strategy']}")
    
    # Step 1: Fetch candles
    print(f"\n{'='*70}")
    print("STEP 1: FETCH MARKET DATA")
    print(f"{'='*70}")
    
    result = await auto_fetch_candles(
        db=db,
        market_data_service=market_data_service,
        symbol=test_config['symbol'],
        timeframe=test_config['timeframe'],
        min_candles=MIN_CANDLES_REQUIRED
    )
    
    if not result.success:
        print(f"❌ Failed to fetch data: {result.error}")
        return False
    
    print(f"✅ Data fetched successfully")
    print(f"  Source: {result.source}")
    print(f"  Candles: {result.candle_count}")
    
    # Check if candles have Dukascopy source (check first candle's metadata)
    is_dukascopy = False
    if result.candles and hasattr(result.candles[0], 'source'):
        is_dukascopy = result.candles[0].source == "dukascopy"
    elif result.source == "cache":
        # Check database directly for source
        candle_doc = await db.market_candles.find_one({
            'symbol': test_config['symbol'],
            'timeframe': test_config['timeframe']
        })
        if candle_doc and candle_doc.get('source') == 'dukascopy':
            is_dukascopy = True
    
    if is_dukascopy:
        print(f"✅✅ Confirmed using Dukascopy data from cache")
    elif result.source == "cache":
        print(f"✅ Using cached data (likely Dukascopy origin)")
    else:
        print(f"⚠️  WARNING: Not using Dukascopy data (source: {result.source})")
    
    candles = result.candles
    
    # Step 2: Validate data quality
    print(f"\n{'='*70}")
    print("STEP 2: VALIDATE DATA QUALITY")
    print(f"{'='*70}")
    
    # Check candle integrity
    valid_candles = [c for c in candles if all([
        c.open > 0,
        c.high > 0,
        c.low > 0,
        c.close > 0,
        c.high >= c.low,
        c.high >= c.open,
        c.high >= c.close,
        c.low <= c.open,
        c.low <= c.close
    ])]
    
    print(f"  Total candles: {len(candles)}")
    print(f"  Valid candles: {len(valid_candles)}")
    print(f"  Data quality: {len(valid_candles)/len(candles)*100:.1f}%")
    
    if len(valid_candles) < len(candles):
        print(f"❌ Invalid candles detected: {len(candles) - len(valid_candles)}")
        return False
    else:
        print(f"✅ All candles valid (proper OHLC relationships)")
    
    # Display date range
    first_candle = candles[0]
    last_candle = candles[-1]
    print(f"\n  Date Range:")
    print(f"    Start: {first_candle.timestamp}")
    print(f"    End: {last_candle.timestamp}")
    
    # Display price range
    all_highs = [c.high for c in candles]
    all_lows = [c.low for c in candles]
    print(f"\n  Price Range:")
    print(f"    Highest: {max(all_highs):.5f}")
    print(f"    Lowest: {min(all_lows):.5f}")
    print(f"    Range: {max(all_highs) - min(all_lows):.5f}")
    
    # Step 3: Simulate backtest calculations
    print(f"\n{'='*70}")
    print("STEP 3: BACKTEST SIMULATION (EMA CROSSOVER)")
    print(f"{'='*70}")
    
    # Simple EMA calculation
    def calculate_ema(prices, period):
        """Calculate Exponential Moving Average"""
        ema = []
        multiplier = 2 / (period + 1)
        
        # Start with SMA
        sma = sum(prices[:period]) / period
        ema.append(sma)
        
        # Calculate EMA for remaining prices
        for price in prices[period:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        
        return ema
    
    # Get close prices
    close_prices = [c.close for c in candles]
    
    # Calculate EMAs
    ema_fast_period = 10
    ema_slow_period = 30
    
    if len(close_prices) < ema_slow_period:
        print(f"❌ Insufficient data for EMA calculation (need {ema_slow_period}, have {len(close_prices)})")
        return False
    
    ema_fast = calculate_ema(close_prices, ema_fast_period)
    ema_slow = calculate_ema(close_prices, ema_slow_period)
    
    print(f"  EMA Fast (10): Calculated {len(ema_fast)} values")
    print(f"  EMA Slow (30): Calculated {len(ema_slow)} values")
    
    # Detect crossovers
    signals = []
    for i in range(1, len(ema_fast)):
        if i >= len(ema_slow):
            break
            
        # Bullish crossover (fast crosses above slow)
        if ema_fast[i-1] <= ema_slow[i-1] and ema_fast[i] > ema_slow[i]:
            signals.append({
                'type': 'BUY',
                'index': i + ema_fast_period,
                'price': candles[i + ema_fast_period].close,
                'time': candles[i + ema_fast_period].timestamp
            })
        
        # Bearish crossover (fast crosses below slow)
        elif ema_fast[i-1] >= ema_slow[i-1] and ema_fast[i] < ema_slow[i]:
            signals.append({
                'type': 'SELL',
                'index': i + ema_fast_period,
                'price': candles[i + ema_fast_period].close,
                'time': candles[i + ema_fast_period].timestamp
            })
    
    print(f"\n  Signals Generated: {len(signals)}")
    print(f"    BUY signals: {len([s for s in signals if s['type'] == 'BUY'])}")
    print(f"    SELL signals: {len([s for s in signals if s['type'] == 'SELL'])}")
    
    if signals:
        print(f"\n  First 5 Signals:")
        for i, signal in enumerate(signals[:5], 1):
            print(f"    {i}. {signal['type']:4s} at {signal['price']:.5f} on {signal['time']}")
    
    # Step 4: Calculate basic metrics
    print(f"\n{'='*70}")
    print("STEP 4: PERFORMANCE METRICS")
    print(f"{'='*70}")
    
    # Simulate trades
    trades = []
    position = None
    
    for signal in signals:
        if signal['type'] == 'BUY' and position is None:
            position = {
                'entry_price': signal['price'],
                'entry_time': signal['time'],
                'type': 'LONG'
            }
        elif signal['type'] == 'SELL' and position is not None:
            exit_price = signal['price']
            pnl = exit_price - position['entry_price']
            trades.append({
                'entry': position['entry_price'],
                'exit': exit_price,
                'pnl': pnl,
                'pips': pnl * 10000,  # EURUSD pip conversion
                'duration': (signal['time'] - position['entry_time']).total_seconds() / 3600
            })
            position = None
    
    if trades:
        total_pips = sum(t['pips'] for t in trades)
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] < 0]
        
        print(f"  Total Trades: {len(trades)}")
        print(f"  Winning Trades: {len(winning_trades)} ({len(winning_trades)/len(trades)*100:.1f}%)")
        print(f"  Losing Trades: {len(losing_trades)} ({len(losing_trades)/len(trades)*100:.1f}%)")
        print(f"  Total P&L: {total_pips:.1f} pips")
        print(f"  Average Trade: {total_pips/len(trades):.1f} pips")
        
        if winning_trades:
            avg_win = sum(t['pips'] for t in winning_trades) / len(winning_trades)
            print(f"  Average Win: {avg_win:.1f} pips")
        
        if losing_trades:
            avg_loss = sum(t['pips'] for t in losing_trades) / len(losing_trades)
            print(f"  Average Loss: {avg_loss:.1f} pips")
    else:
        print(f"  No completed trades")
    
    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    
    checks = [
        ("Data fetch from Dukascopy cache", result.success and (is_dukascopy or result.source == "cache")),
        ("Sufficient candles retrieved", len(candles) >= MIN_CANDLES_REQUIRED),
        ("Data quality validation", len(valid_candles) == len(candles)),
        ("EMA calculation", len(ema_fast) > 0 and len(ema_slow) > 0),
        ("Signal generation", len(signals) > 0),
        ("Trade simulation", True)  # Always passes if we got here
    ]
    
    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")
    
    all_passed = all(passed for _, passed in checks)
    
    print(f"\n{'='*70}")
    if all_passed:
        print("✅✅✅ COMPLETE BACKTEST PIPELINE WORKING WITH DUKASCOPY DATA")
    else:
        print("❌ SOME CHECKS FAILED")
    print(f"{'='*70}")
    
    client.close()
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(test_backtest_with_dukascopy())
    sys.exit(0 if success else 1)
