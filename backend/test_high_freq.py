"""
Test High-Frequency EURUSD Strategy
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
from high_frequency_eurusd import run_high_frequency_eurusd
from test_eurusd_strategy import calculate_metrics, print_backtest_results

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')


async def test_high_freq():
    """Test high-frequency strategy"""
    
    print("="*70)
    print("HIGH-FREQUENCY EURUSD STRATEGY TEST")
    print("="*70)
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Fetch
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
    
    # Test different parameter sets
    test_configs = [
        {
            "name": "Base High-Freq",
            "params": {}  # Use defaults
        },
        {
            "name": "Wider RSI Zones",
            "params": {
                "rsi_pullback_buy_min": 30,
                "rsi_pullback_buy_max": 60,
                "rsi_pullback_sell_min": 40,
                "rsi_pullback_sell_max": 70,
            }
        },
        {
            "name": "Tighter Stops",
            "params": {
                "stop_loss_atr_mult": 2.0,
                "take_profit_atr_mult": 3.5,
                "trailing_atr_mult": 1.5,
            }
        },
        {
            "name": "More Trades",
            "params": {
                "max_trades_per_day": 7,
                "min_candles_between_trades": 1,
                "rsi_pullback_buy_min": 30,
                "rsi_pullback_buy_max": 65,
                "rsi_pullback_sell_min": 35,
                "rsi_pullback_sell_max": 70,
            }
        },
    ]
    
    results = []
    
    for cfg in test_configs:
        print(f"\n{'='*70}")
        print(f"Testing: {cfg['name']}")
        print(f"{'='*70}")
        
        trades, equity_curve = run_high_frequency_eurusd(candles, config, cfg['params'])
        metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
        
        print(f"\n📊 Results:")
        print(f"  Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.1f}%")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"  P&L: ${metrics['total_pnl']:.2f}")
        print(f"  Max DD: {metrics['max_drawdown_pct']:.2f}%")
        
        goal_trades = 50 <= metrics['total_trades'] <= 120
        goal_pf = metrics['profit_factor'] > 1.5
        goal_dd = metrics['max_drawdown_pct'] < 5.0
        all_goals = goal_trades and goal_pf and goal_dd
        
        print(f"  Trades Goal (50-120): {'✅' if goal_trades else '❌'} {metrics['total_trades']}")
        print(f"  PF Goal (>1.5): {'✅' if goal_pf else '❌'} {metrics['profit_factor']:.2f}")
        print(f"  DD Goal (<5%): {'✅' if goal_dd else '❌'} {metrics['max_drawdown_pct']:.2f}%")
        
        # Scoring
        score = 0
        if metrics['total_trades'] > 0:
            trade_score = min(metrics['total_trades'] / 85, 1.0)  # Optimal around 85
            pf_score = min(metrics['profit_factor'] / 2.0, 1.0)
            dd_score = max(1.0 - (metrics['max_drawdown_pct'] / 20), 0)
            pnl_score = max(metrics['total_pnl'] / 2000, -1)
            
            score = (trade_score * 0.3 + pf_score * 0.35 + dd_score * 0.25 + pnl_score * 0.1)
        
        results.append({
            "name": cfg['name'],
            "params": cfg['params'],
            "metrics": metrics,
            "goals_met": all_goals,
            "score": score,
            "trades": trades
        })
    
    # Summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}\n")
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, r in enumerate(results, 1):
        m = r['metrics']
        goals_str = "✅ ALL GOALS MET" if r['goals_met'] else "❌ Goals not met"
        print(f"{i}. {r['name']}")
        print(f"   Trades: {m['total_trades']} | WR: {m['win_rate']:.1f}% | PF: {m['profit_factor']:.2f}")
        print(f"   P&L: ${m['total_pnl']:.2f} | DD: {m['max_drawdown_pct']:.2f}% | Score: {r['score']:.3f}")
        print(f"   {goals_str}\n")
    
    # Best
    print(f"{'='*70}")
    print(f"🏆 BEST CONFIGURATION: {results[0]['name']}")
    print(f"{'='*70}")
    
    print_backtest_results(results[0]['params'], results[0]['metrics'], results[0]['trades'])
    
    client.close()


if __name__ == "__main__":
    asyncio.run(test_high_freq())
