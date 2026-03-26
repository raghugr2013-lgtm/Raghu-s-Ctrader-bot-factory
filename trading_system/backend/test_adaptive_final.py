"""
Test Adaptive EURUSD Strategy (Final Version)

Goals:
- 50-100 trades
- Profit Factor > 1.5
- Drawdown < 5%
- Stable equity curve
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
from adaptive_eurusd_final import run_adaptive_eurusd_strategy
from test_eurusd_strategy import calculate_metrics, print_backtest_results

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')


async def test_adaptive_final():
    """Test adaptive strategy"""
    
    print("="*70)
    print("ADAPTIVE EURUSD STRATEGY - FINAL VERSION")
    print("="*70)
    print("\n💡 Approach: Adapt behavior, don't block trades")
    print("\n🎯 Goals:")
    print("  - 50-100 trades")
    print("  - Profit Factor > 1.5")
    print("  - Max Drawdown < 5%")
    print("  - Stable equity curve")
    
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
            "name": "Base Adaptive",
            "params": {}
        },
        {
            "name": "Conservative (0.6% base risk)",
            "params": {
                "base_risk_pct": 0.6,
                "base_stop_atr_mult": 2.2,
            }
        },
        {
            "name": "Moderate (0.75% base risk)",
            "params": {
                "base_risk_pct": 0.75,
                "base_stop_atr_mult": 2.0,
                "base_tp_atr_mult": 3.2,
            }
        },
        {
            "name": "Aggressive (1% base risk)",
            "params": {
                "base_risk_pct": 1.0,
                "max_trades_per_day": 5,
            }
        },
        {
            "name": "With RSI Confirmation",
            "params": {
                "use_rsi_confirmation": True,
                "rsi_neutral_min": 35,
                "rsi_neutral_max": 65,
            }
        },
    ]
    
    results = []
    
    for i, cfg in enumerate(test_configs, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}/{len(test_configs)}: {cfg['name']}")
        print(f"{'='*70}")
        
        # Run backtest
        trades, equity_curve = run_adaptive_eurusd_strategy(candles, config, cfg['params'])
        
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
        goal_trades = 50 <= metrics['total_trades'] <= 100
        goal_pf = metrics['profit_factor'] > 1.5
        goal_dd = metrics['max_drawdown_pct'] < 5.0
        goal_positive = metrics['total_pnl'] > 0
        
        print(f"\n🎯 Goal Achievement:")
        print(f"  {'✅' if goal_trades else '⚠️' if metrics['total_trades'] > 30 else '❌'} Trades (50-100): {metrics['total_trades']}")
        print(f"  {'✅' if goal_pf else '⚠️' if goal_pf > 1.2 else '❌'} Profit Factor (>1.5): {metrics['profit_factor']:.2f}")
        print(f"  {'✅' if goal_dd else '⚠️' if goal_dd < 10 else '❌'} Max Drawdown (<5%): {metrics['max_drawdown_pct']:.2f}%")
        print(f"  {'✅' if goal_positive else '❌'} Profitable: {'Yes' if goal_positive else 'No'}")
        
        all_goals = goal_trades and goal_pf and goal_dd
        
        # Scoring
        trade_score = min(metrics['total_trades'] / 75, 1.5) if metrics['total_trades'] > 0 else 0
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
        print(f"  {'✅✅✅ ALL GOALS MET!' if all_goals else '⚠️  Partial success' if metrics['total_pnl'] > 0 else '❌ Needs improvement'}")
    
    # Summary
    print(f"\n{'='*70}")
    print("COMPREHENSIVE SUMMARY")
    print(f"{'='*70}\n")
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"{'Rank':<6} {'Configuration':<35} {'Score':<8}")
    print("-"*70)
    for i, r in enumerate(results, 1):
        m = r['metrics']
        status = "✅" if r['goals_met'] else ("⚠️" if m['total_pnl'] > 0 else "❌")
        print(f"{i:<6} {r['name']:<35} {r['score']:<8.3f}")
        print(f"       Trades: {m['total_trades']:<3} | WR: {m['win_rate']:>5.1f}% | "
              f"PF: {m['profit_factor']:>4.2f} | Return: {m['total_pnl']/config.initial_balance*100:>6.1f}% | "
              f"DD: {m['max_drawdown_pct']:>5.2f}% {status}")
    
    # Best result
    best = results[0]
    print(f"\n{'='*70}")
    print(f"🏆 BEST CONFIGURATION: {best['name']}")
    print(f"{'='*70}")
    
    print_backtest_results(best['params'], best['metrics'], best['trades'])
    
    # Compare with previous best
    print(f"\n{'='*70}")
    print("COMPARISON WITH PREVIOUS BEST")
    print(f"{'='*70}")
    
    print(f"\n{'Strategy':<30} {'Trades':<8} {'PF':<6} {'Return':<10} {'DD':<8}")
    print("-"*70)
    print(f"{'Previous Best (EMA 5/50)':<30} {16:<8} {1.33:<6.2f} {'+5.0%':<10} {'13.04%':<8}")
    print(f"{'Adaptive (Current)':<30} {best['metrics']['total_trades']:<8} "
          f"{best['metrics']['profit_factor']:<6.2f} "
          f"{best['metrics']['total_pnl']/config.initial_balance*100:+.1f}%{'':<6} "
          f"{best['metrics']['max_drawdown_pct']:.2f}%")
    
    # Final assessment
    print(f"\n{'='*70}")
    if best['goals_met']:
        print("✅✅✅ SUCCESS - ALL GOALS ACHIEVED!")
        print("\n🎉 The adaptive approach successfully:")
        print("  • Generated target trade frequency")
        print("  • Maintained profit factor > 1.5")
        print("  • Kept drawdown under 5%")
        print("  • Adapted to market conditions")
    else:
        m = best['metrics']
        print("RESULTS ANALYSIS")
        print(f"\n✅ Strengths:")
        if m['total_trades'] >= 30:
            print(f"  • Good trade frequency: {m['total_trades']} trades")
        if m['total_pnl'] > 0:
            print(f"  • Profitable: +${m['total_pnl']:.2f}")
        if m['max_drawdown_pct'] < 10:
            print(f"  • Controlled drawdown: {m['max_drawdown_pct']:.2f}%")
        
        print(f"\n⚠️  Areas for Improvement:")
        if not (50 <= m['total_trades'] <= 100):
            print(f"  • Trade frequency: {m['total_trades']} (target 50-100)")
        if m['profit_factor'] <= 1.5:
            print(f"  • Profit factor: {m['profit_factor']:.2f} (target >1.5)")
        if m['max_drawdown_pct'] >= 5.0:
            print(f"  • Drawdown: {m['max_drawdown_pct']:.2f}% (target <5%)")
    
    print(f"{'='*70}")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(test_adaptive_final())
