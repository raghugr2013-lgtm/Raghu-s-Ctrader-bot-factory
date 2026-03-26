"""
Test Enhanced Multi-Signal Strategy

Goal: Push PF above 1.5 while keeping DD below 5%
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
from enhanced_multi_signal import run_enhanced_multi_signal_strategy
from test_eurusd_strategy import calculate_metrics, print_backtest_results

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')


async def test_enhanced():
    """Test enhanced multi-signal strategy"""
    
    print("="*70)
    print("ENHANCED MULTI-SIGNAL EURUSD STRATEGY")
    print("="*70)
    print("\n💡 Improvements:")
    print("  • Confirmation requirements (2 minimum)")
    print("  • Avoid EMA 200 uncertain zone")
    print("  • Better risk/reward (4:1)")
    print("  • Quality over quantity")
    
    print("\n🎯 Goals:")
    print("  - Profit Factor > 1.5")
    print("  - Drawdown < 5%")
    print("  - Trades: 45-70")
    
    # Connect
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
        print(f"❌ Failed: {result.error}")
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
    test_configs = [
        {
            "name": "Base Enhanced",
            "params": {}
        },
        {
            "name": "Wider Targets (4.2 ATR)",
            "params": {
                "take_profit_atr_mult": 4.2,
                "stop_loss_atr_mult": 1.9,
            }
        },
        {
            "name": "Strict Confirmations (3 required)",
            "params": {
                "min_confirmations": 3,
                "max_trades_per_day": 4,
            }
        },
        {
            "name": "Moderate Risk (0.6%)",
            "params": {
                "base_risk_pct": 0.6,
                "take_profit_atr_mult": 3.8,
            }
        },
        {
            "name": "Balanced",
            "params": {
                "take_profit_atr_mult": 4.0,
                "stop_loss_atr_mult": 1.8,
                "min_confirmations": 2,
                "max_trades_per_day": 3,
                "avoid_ema200_zone_pct": 0.0025,
            }
        },
    ]
    
    results = []
    
    for i, cfg in enumerate(test_configs, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}/{len(test_configs)}: {cfg['name']}")
        print(f"{'='*70}")
        
        trades, equity_curve = run_enhanced_multi_signal_strategy(candles, config, cfg['params'])
        metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
        
        print(f"\n📊 Performance:")
        print(f"  Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.1f}%")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"  Total P&L: ${metrics['total_pnl']:.2f} ({metrics['total_pnl']/config.initial_balance*100:+.1f}%)")
        print(f"  Max DD: {metrics['max_drawdown_pct']:.2f}%")
        print(f"  Sharpe: {metrics['sharpe_ratio']:.2f}")
        print(f"  Expectancy: ${metrics['expectancy']:.2f}")
        print(f"  Win/Loss Ratio: {metrics['avg_win']/abs(metrics['avg_loss']) if metrics['avg_loss'] != 0 else 0:.2f}")
        
        goal_trades = 45 <= metrics['total_trades'] <= 70
        goal_pf = metrics['profit_factor'] > 1.5
        goal_dd = metrics['max_drawdown_pct'] < 5.0
        goal_positive = metrics['total_pnl'] > 0
        
        print(f"\n🎯 Goal Achievement:")
        print(f"  {'✅' if goal_trades else '⚠️' if metrics['total_trades'] > 35 else '❌'} Trades (45-70): {metrics['total_trades']}")
        print(f"  {'✅' if goal_pf else '⚠️' if metrics['profit_factor'] > 1.3 else '❌'} Profit Factor (>1.5): {metrics['profit_factor']:.2f}")
        print(f"  {'✅' if goal_dd else '⚠️' if metrics['max_drawdown_pct'] < 7 else '❌'} Drawdown (<5%): {metrics['max_drawdown_pct']:.2f}%")
        print(f"  {'✅' if goal_positive else '❌'} Profitable: {'Yes' if goal_positive else 'No'}")
        
        all_goals = goal_trades and goal_pf and goal_dd and goal_positive
        
        score = (
            min(metrics['total_trades'] / 57.5, 1.5) * 0.15 +
            min(metrics['profit_factor'] / 2.0, 1.0) * 0.40 +
            max(1.0 - (metrics['max_drawdown_pct'] / 12), 0) * 0.25 +
            max(min(metrics['total_pnl'] / 3000, 1.0), -0.5) * 0.10 +
            max(min(metrics['sharpe_ratio'] / 3.0, 1.0), 0) * 0.10
        )
        
        results.append({
            "name": cfg['name'],
            "params": cfg['params'],
            "metrics": metrics,
            "goals_met": all_goals,
            "score": score,
            "trades": trades,
        })
        
        print(f"  Score: {score:.3f}")
        print(f"  {'✅✅✅ ALL GOALS MET!' if all_goals else '⚠️  Close' if goal_positive else '❌ Needs work'}")
    
    # Summary
    print(f"\n{'='*70}")
    print("RESULTS SUMMARY")
    print(f"{'='*70}\n")
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, r in enumerate(results, 1):
        m = r['metrics']
        status = "✅" if r['goals_met'] else ("⚠️" if m['total_pnl'] > 0 else "❌")
        print(f"{i}. {r['name']}")
        print(f"   T:{m['total_trades']:<3} WR:{m['win_rate']:>5.1f}% PF:{m['profit_factor']:>4.2f} "
              f"Ret:{m['total_pnl']/config.initial_balance*100:>6.1f}% DD:{m['max_drawdown_pct']:>5.2f}% {status}")
    
    # Best
    best = results[0]
    print(f"\n{'='*70}")
    print(f"🏆 BEST: {best['name']}")
    print(f"{'='*70}")
    
    print_backtest_results(best['params'], best['metrics'], best['trades'])
    
    # Comparison
    print(f"\n{'='*70}")
    print("EVOLUTION COMPARISON")
    print(f"{'='*70}\n")
    
    print(f"{'Strategy':<25} {'Trades':<8} {'PF':<6} {'Return':<10} {'DD':<8}")
    print("-"*70)
    print(f"{'Multi-Signal v1':<25} {55:<8} {1.34:<6.2f} {'+7.8%':<10} {'4.58%':<8}")
    print(f"{'Enhanced (Best)':<25} {best['metrics']['total_trades']:<8} "
          f"{best['metrics']['profit_factor']:<6.2f} "
          f"{best['metrics']['total_pnl']/config.initial_balance*100:+.1f}%{'':<6} "
          f"{best['metrics']['max_drawdown_pct']:.2f}%")
    
    print(f"\n{'='*70}")
    if best['goals_met']:
        print("✅✅✅ SUCCESS - ALL GOALS ACHIEVED!")
        print(f"\n🎉 Profit Factor: {best['metrics']['profit_factor']:.2f} (>1.5) ✅")
        print(f"🎉 Drawdown: {best['metrics']['max_drawdown_pct']:.2f}% (<5%) ✅")
        print(f"🎉 Trades: {best['metrics']['total_trades']} (45-70) ✅")
        print(f"🎉 Return: +${best['metrics']['total_pnl']:.2f} ✅")
    else:
        m = best['metrics']
        print("ASSESSMENT")
        if m['total_pnl'] > 0:
            print(f"\n✅ Profitable: +${m['total_pnl']:.2f}")
        
        gaps = []
        if not (45 <= m['total_trades'] <= 70):
            gaps.append(f"Trades: {m['total_trades']} (need 45-70)")
        if m['profit_factor'] <= 1.5:
            gaps.append(f"PF: {m['profit_factor']:.2f} (need >1.5)")
        if m['max_drawdown_pct'] >= 5.0:
            gaps.append(f"DD: {m['max_drawdown_pct']:.2f}% (need <5%)")
        
        if gaps:
            print("\n⚠️  Remaining gaps:")
            for gap in gaps:
                print(f"  • {gap}")
    
    print(f"{'='*70}")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(test_enhanced())
