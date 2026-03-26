"""
Test Multi-Signal EURUSD Strategy

Goals:
- 60-120 trades
- Profit Factor > 1.5
- Drawdown < 5%
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
from multi_signal_strategy import run_multi_signal_strategy
from test_eurusd_strategy import calculate_metrics, print_backtest_results

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')


async def test_multi_signal():
    """Test multi-signal strategy"""
    
    print("="*70)
    print("MULTI-SIGNAL EURUSD STRATEGY")
    print("="*70)
    print("\n💡 Concept: Multiple entry methods, single directional bias")
    print("\n🎯 Goals:")
    print("  - 60-120 trades")
    print("  - Profit Factor > 1.5")
    print("  - Max Drawdown < 5%")
    
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
    
    print(f"✅ Fetched {result.candle_count} candles from {result.source}")
    
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
    
    print(f"\n⚙️  Configuration:")
    print(f"  Period: {config.start_date.date()} to {config.end_date.date()}")
    print(f"  Initial Balance: ${config.initial_balance:.2f}")
    
    # Test configurations
    test_configs = [
        {
            "name": "Base Multi-Signal",
            "params": {}
        },
        {
            "name": "Conservative (0.6% risk)",
            "params": {
                "base_risk_pct": 0.6,
                "stop_loss_atr_mult": 2.0,
                "take_profit_atr_mult": 3.0,
            }
        },
        {
            "name": "Aggressive Signals",
            "params": {
                "pullback_rsi_max": 65,
                "momentum_threshold": 0.7,
                "max_trades_per_day": 6,
            }
        },
        {
            "name": "Tight Stops",
            "params": {
                "stop_loss_atr_mult": 1.5,
                "take_profit_atr_mult": 2.5,
                "base_risk_pct": 0.8,
            }
        },
        {
            "name": "Wide Targets",
            "params": {
                "stop_loss_atr_mult": 2.0,
                "take_profit_atr_mult": 3.5,
                "pullback_distance_pct": 0.004,
            }
        },
    ]
    
    results = []
    
    for i, cfg in enumerate(test_configs, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}/{len(test_configs)}: {cfg['name']}")
        print(f"{'='*70}")
        
        # Run backtest
        trades, equity_curve = run_multi_signal_strategy(candles, config, cfg['params'])
        
        # Calculate metrics
        metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
        
        # Display results
        print(f"\n📊 Performance:")
        print(f"  Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.1f}%")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"  Total P&L: ${metrics['total_pnl']:.2f} ({metrics['total_pnl']/config.initial_balance*100:+.1f}%)")
        print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"  Expectancy: ${metrics['expectancy']:.2f}")
        
        # Check goals
        goal_trades = 60 <= metrics['total_trades'] <= 120
        goal_pf = metrics['profit_factor'] > 1.5
        goal_dd = metrics['max_drawdown_pct'] < 5.0
        goal_positive = metrics['total_pnl'] > 0
        
        print(f"\n🎯 Goal Achievement:")
        print(f"  {'✅' if goal_trades else '⚠️' if metrics['total_trades'] > 40 else '❌'} Trades (60-120): {metrics['total_trades']}")
        print(f"  {'✅' if goal_pf else '⚠️' if metrics['profit_factor'] > 1.2 else '❌'} Profit Factor (>1.5): {metrics['profit_factor']:.2f}")
        print(f"  {'✅' if goal_dd else '⚠️' if metrics['max_drawdown_pct'] < 10 else '❌'} Max Drawdown (<5%): {metrics['max_drawdown_pct']:.2f}%")
        print(f"  {'✅' if goal_positive else '❌'} Profitable: {'Yes' if goal_positive else 'No'}")
        
        all_goals = goal_trades and goal_pf and goal_dd and goal_positive
        
        # Scoring
        trade_score = min(metrics['total_trades'] / 90, 1.5) if metrics['total_trades'] > 0 else 0
        pf_score = min(metrics['profit_factor'] / 2.0, 1.0)
        dd_score = max(1.0 - (metrics['max_drawdown_pct'] / 15), 0)
        return_score = max(min(metrics['total_pnl'] / 3000, 1.0), -0.5)
        sharpe_score = max(min(metrics['sharpe_ratio'] / 3.0, 1.0), 0)
        
        score = (trade_score * 0.20 + 
                pf_score * 0.35 + 
                dd_score * 0.25 + 
                return_score * 0.10 +
                sharpe_score * 0.10)
        
        results.append({
            "name": cfg['name'],
            "params": cfg['params'],
            "metrics": metrics,
            "goals_met": all_goals,
            "score": score,
            "trades": trades,
            "equity_curve": equity_curve,
        })
        
        print(f"  Overall Score: {score:.3f}")
        print(f"  {'✅✅✅ ALL GOALS MET!' if all_goals else '⚠️  Partial success' if goal_positive else '❌ Needs improvement'}")
    
    # Summary
    print(f"\n{'='*70}")
    print("COMPREHENSIVE SUMMARY")
    print(f"{'='*70}\n")
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"{'Rank':<6} {'Configuration':<30} {'Score':<8}")
    print("-"*70)
    for i, r in enumerate(results, 1):
        m = r['metrics']
        status = "✅" if r['goals_met'] else ("⚠️" if m['total_pnl'] > 0 else "❌")
        print(f"{i:<6} {r['name']:<30} {r['score']:<8.3f}")
        print(f"       T:{m['total_trades']:<4} WR:{m['win_rate']:>5.1f}% "
              f"PF:{m['profit_factor']:>4.2f} Ret:{m['total_pnl']/config.initial_balance*100:>6.1f}% "
              f"DD:{m['max_drawdown_pct']:>5.2f}% {status}")
    
    # Best result
    best = results[0]
    print(f"\n{'='*70}")
    print(f"🏆 BEST CONFIGURATION: {best['name']}")
    print(f"{'='*70}")
    
    print_backtest_results(best['params'], best['metrics'], best['trades'])
    
    # Signal analysis (if available)
    if best['trades']:
        print(f"\n{'='*70}")
        print("SIGNAL PERFORMANCE ANALYSIS")
        print(f"{'='*70}")
        
        # Group by signal type (would need to track this in trades)
        print("\nNote: Detailed signal breakdown logged in strategy output")
    
    # Comparison
    print(f"\n{'='*70}")
    print("STRATEGY COMPARISON")
    print(f"{'='*70}\n")
    
    print(f"{'Strategy':<25} {'Trades':<8} {'PF':<6} {'Return':<10} {'DD':<8} {'Status'}")
    print("-"*70)
    print(f"{'EMA 5/50 Optimal':<25} {16:<8} {1.33:<6.2f} {'+5.0%':<10} {'13.04%':<8} {'✅ Best so far'}")
    print(f"{'Multi-Signal (Best)':<25} {best['metrics']['total_trades']:<8} "
          f"{best['metrics']['profit_factor']:<6.2f} "
          f"{best['metrics']['total_pnl']/config.initial_balance*100:+.1f}%{'':<6} "
          f"{best['metrics']['max_drawdown_pct']:.2f}%{'':<4} "
          f"{'✅ NEW BEST' if best['goals_met'] else '⚠️ Close'}")
    
    # Final verdict
    print(f"\n{'='*70}")
    if best['goals_met']:
        print("✅✅✅ SUCCESS - ALL GOALS ACHIEVED!")
        print("\n🎉 Multi-signal approach delivered:")
        print(f"  • Trade frequency: {best['metrics']['total_trades']} trades")
        print(f"  • Quality maintained: PF {best['metrics']['profit_factor']:.2f}")
        print(f"  • Low drawdown: {best['metrics']['max_drawdown_pct']:.2f}%")
        print(f"  • Profitable: +${best['metrics']['total_pnl']:.2f}")
    else:
        print("FINAL ASSESSMENT")
        m = best['metrics']
        
        if m['total_pnl'] > 0:
            print(f"\n✅ Strategy is PROFITABLE: +${m['total_pnl']:.2f}")
        else:
            print(f"\n❌ Strategy needs improvement")
        
        print(f"\n📊 Performance vs Goals:")
        print(f"  Trades: {m['total_trades']} (target 60-120) - {'✅' if 60<=m['total_trades']<=120 else '❌'}")
        print(f"  Profit Factor: {m['profit_factor']:.2f} (target >1.5) - {'✅' if m['profit_factor']>1.5 else '❌'}")
        print(f"  Drawdown: {m['max_drawdown_pct']:.2f}% (target <5%) - {'✅' if m['max_drawdown_pct']<5 else '❌'}")
        
        if m['total_pnl'] > 0 and m['total_trades'] > 50:
            print(f"\n⚠️  Close to goals - recommend further tuning")
        elif m['total_pnl'] > 0:
            print(f"\n✅ Profitable but needs more opportunities")
    
    print(f"{'='*70}")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(test_multi_signal())
