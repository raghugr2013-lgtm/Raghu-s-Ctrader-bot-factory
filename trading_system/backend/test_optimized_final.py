"""
Test Optimized EURUSD Strategy with parameter variations
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
from optimized_eurusd_strategy import run_optimized_eurusd_strategy
from test_eurusd_strategy import calculate_metrics, print_backtest_results

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')


async def test_optimized():
    """Test optimized strategy with multiple configurations"""
    
    print("="*70)
    print("OPTIMIZED EURUSD STRATEGY - PARAMETER TESTING")
    print("="*70)
    
    # Connect
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Fetch data
    print(f"\n📊 Fetching data...")
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
    
    print(f"✅ Fetched {result.candle_count} candles")
    
    candles = result.candles
    
    # Config
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
    
    # Test configurations
    configs = [
        {
            "name": "Base (EMA 5/20)",
            "params": {
                "ema_fast": 5,
                "ema_medium": 20,
                "stop_loss_atr_mult": 2.5,
                "take_profit_atr_mult": 4.0,
                "max_trades_per_day": 5,
            }
        },
        {
            "name": "Faster (EMA 3/15)",
            "params": {
                "ema_fast": 3,
                "ema_medium": 15,
                "stop_loss_atr_mult": 2.0,
                "take_profit_atr_mult": 3.5,
                "max_trades_per_day": 6,
            }
        },
        {
            "name": "Medium (EMA 8/25)",
            "params": {
                "ema_fast": 8,
                "ema_medium": 25,
                "stop_loss_atr_mult": 2.8,
                "take_profit_atr_mult": 4.5,
                "max_trades_per_day": 4,
            }
        },
        {
            "name": "Optimal from Analysis (EMA 5/50)",
            "params": {
                "ema_fast": 5,
                "ema_medium": 50,
                "stop_loss_atr_mult": 3.0,
                "take_profit_atr_mult": 5.0,
                "max_trades_per_day": 5,
            }
        },
        {
            "name": "Tight Stops (EMA 5/20)",
            "params": {
                "ema_fast": 5,
                "ema_medium": 20,
                "stop_loss_atr_mult": 1.5,
                "take_profit_atr_mult": 3.0,
                "max_trades_per_day": 7,
                "use_trailing_stop": False,
            }
        },
    ]
    
    results = []
    
    for cfg in configs:
        print(f"\n{'='*70}")
        print(f"Testing: {cfg['name']}")
        print(f"{'='*70}")
        
        trades, equity_curve = run_optimized_eurusd_strategy(candles, config, cfg['params'])
        metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
        
        print(f"\n📊 Quick Results:")
        print(f"  Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.1f}%")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"  P&L: ${metrics['total_pnl']:.2f}")
        print(f"  Max DD: {metrics['max_drawdown_pct']:.2f}%")
        
        # Check goals
        goal_trades = 50 <= metrics['total_trades'] <= 120
        goal_pf = metrics['profit_factor'] > 1.5
        goal_dd = metrics['max_drawdown_pct'] < 5.0
        all_goals = goal_trades and goal_pf and goal_dd
        
        score = 0
        if metrics['total_trades'] > 0:
            # Scoring: prioritize profitability and low drawdown
            score = (metrics['total_pnl'] / 1000) * (1 - min(metrics['max_drawdown_pct'] / 100, 0.9)) * (metrics['total_trades'] / 50)
        
        results.append({
            "name": cfg['name'],
            "params": cfg['params'],
            "metrics": metrics,
            "goals_met": all_goals,
            "score": score,
            "trades": trades,
        })
        
        print(f"  Goals Met: {'✅' if all_goals else '❌'}")
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY - RANKED BY SCORE")
    print(f"{'='*70}\n")
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, r in enumerate(results, 1):
        m = r['metrics']
        print(f"{i}. {r['name']}")
        print(f"   Trades: {m['total_trades']} | WR: {m['win_rate']:.1f}% | PF: {m['profit_factor']:.2f} | "
              f"P&L: ${m['total_pnl']:.2f} | DD: {m['max_drawdown_pct']:.2f}% | Score: {r['score']:.3f}")
    
    # Best result
    print(f"\n{'='*70}")
    print(f"🏆 BEST STRATEGY: {results[0]['name']}")
    print(f"{'='*70}")
    
    print_backtest_results(results[0]['params'], results[0]['metrics'], results[0]['trades'])
    
    client.close()


if __name__ == "__main__":
    asyncio.run(test_optimized())
