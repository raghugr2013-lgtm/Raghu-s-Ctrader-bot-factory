"""
Market Analysis - Understand EURUSD behavior in our dataset
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
from backtest_real_engine import _calculate_ema
from improved_eurusd_strategy import calculate_atr

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')


async def analyze_market():
    """Analyze EURUSD market data"""
    
    print("="*70)
    print("EURUSD MARKET ANALYSIS")
    print("="*70)
    
    # Connect
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Fetch data
    result = await auto_fetch_candles(
        db=db,
        market_data_service=market_data_service,
        symbol="EURUSD",
        timeframe="1h",
        min_candles=MIN_CANDLES_REQUIRED
    )
    
    if not result.success:
        print(f"❌ Failed")
        client.close()
        return
    
    candles = result.candles
    
    print(f"\n📊 Dataset Overview:")
    print(f"  Candles: {len(candles)}")
    print(f"  Start: {candles[0].timestamp}")
    print(f"  End: {candles[-1].timestamp}")
    print(f"  Start Price: {candles[0].close:.5f}")
    print(f"  End Price: {candles[-1].close:.5f}")
    print(f"  Change: {(candles[-1].close - candles[0].close) / candles[0].close * 100:.2f}%")
    
    # Calculate EMAs
    ema20 = _calculate_ema(candles, 20)
    ema50 = _calculate_ema(candles, 50)
    ema200 = _calculate_ema(candles, 200)
    atr = calculate_atr(candles, 14)
    
    # Analyze trend
    print(f"\n📈 Trend Analysis:")
    
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    
    for i in range(200, len(candles)):
        if candles[i].close > ema200[i]:
            bullish_count += 1
        elif candles[i].close < ema200[i]:
            bearish_count += 1
        else:
            neutral_count += 1
    
    total = bullish_count + bearish_count + neutral_count
    print(f"  Bullish (above EMA200): {bullish_count} ({bullish_count/total*100:.1f}%)")
    print(f"  Bearish (below EMA200): {bearish_count} ({bearish_count/total*100:.1f}%)")
    print(f"  Neutral: {neutral_count} ({neutral_count/total*100:.1f}%)")
    
    # Price extremes
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    
    print(f"\n💹 Price Range:")
    print(f"  Highest: {max(highs):.5f}")
    print(f"  Lowest: {min(lows):.5f}")
    print(f"  Range: {max(highs) - min(lows):.5f} ({(max(highs) - min(lows)) / min(lows) * 100:.2f}%)")
    
    # Volatility
    avg_atr = sum(atr[200:]) / len(atr[200:])
    avg_price = sum(c.close for c in candles[200:]) / len(candles[200:])
    atr_pct = avg_atr / avg_price * 100
    
    print(f"\n📊 Volatility:")
    print(f"  Avg ATR: {avg_atr:.5f}")
    print(f"  ATR %: {atr_pct:.3f}%")
    
    # Find optimal EMA crossover
    print(f"\n🔍 Testing EMA Crossovers:")
    
    best_config = None
    best_profit = float('-inf')
    
    for fast in [5, 10, 15, 20]:
        for slow in [30, 50, 100, 200]:
            if fast >= slow:
                continue
            
            ema_f = _calculate_ema(candles, fast)
            ema_s = _calculate_ema(candles, slow)
            
            balance = 10000.0
            position = None
            trades = 0
            
            for i in range(max(fast, slow) + 1, len(candles)):
                if ema_f[i] is None or ema_s[i] is None:
                    continue
                
                # Entry
                if position is None:
                    if ema_f[i] > ema_s[i] and ema_f[i-1] <= ema_s[i-1]:
                        position = {"entry": candles[i].close, "type": "buy"}
                        trades += 1
                    elif ema_f[i] < ema_s[i] and ema_f[i-1] >= ema_s[i-1]:
                        position = {"entry": candles[i].close, "type": "sell"}
                        trades += 1
                
                # Exit
                elif position:
                    if (position["type"] == "buy" and ema_f[i] < ema_s[i]) or \
                       (position["type"] == "sell" and ema_f[i] > ema_s[i]):
                        if position["type"] == "buy":
                            pnl = (candles[i].close - position["entry"]) * 10000 * 10
                        else:
                            pnl = (position["entry"] - candles[i].close) * 10000 * 10
                        balance += pnl
                        position = None
            
            profit = balance - 10000.0
            if profit > best_profit:
                best_profit = profit
                best_config = (fast, slow, trades)
    
    if best_config:
        print(f"  Best: EMA{best_config[0]}/{best_config[1]}")
        print(f"    Trades: {best_config[2]}")
        print(f"    Profit: ${best_profit:.2f}")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(analyze_market())
