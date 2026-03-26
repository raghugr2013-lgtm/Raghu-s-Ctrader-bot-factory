"""
Final Validation: Compare all 3 strategy versions

1. Original enhanced_multi_signal (baseline)
2. Adaptive multi_signal (soft filters)
3. Aggressive adaptive (can skip trading)
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
import numpy as np
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from auto_fetch_candles import auto_fetch_candles
from market_data_service import init_market_data_service
from backtest_models import BacktestConfig, Timeframe
from enhanced_multi_signal import run_enhanced_multi_signal_strategy
from adaptive_multi_signal import run_adaptive_multi_signal_strategy
from aggressive_adaptive_strategy import run_aggressive_adaptive_strategy
from test_eurusd_strategy import calculate_metrics

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')


def walk_forward_analysis(candles, config, strategy_func, params):
    """3-segment walk-forward"""
    segment_size = len(candles) // 3
    segments = [
        {"name": "Seg1", "data": candles[0:segment_size]},
        {"name": "Seg2", "data": candles[segment_size:segment_size*2]},
        {"name": "Seg3", "data": candles[segment_size*2:]},
    ]
    
    results = []
    for seg in segments:
        if len(seg["data"]) < 100:
            continue
        trades, equity_curve = strategy_func(seg["data"], config, params)
        metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
        results.append({
            "segment": seg["name"],
            "trades": metrics["total_trades"],
            "pf": metrics["profit_factor"],
            "pnl": metrics["total_pnl"],
            "dd": metrics["max_drawdown_pct"],
        })
    
    pfs = [r["pf"] for r in results if r["pf"] > 0]
    consistency = (min(pfs) / max(pfs) * 100) if pfs and max(pfs) > 0 else 0
    
    return {"segments": results, "consistency": consistency, "all_profitable": all(r["pnl"] > 0 for r in results)}


async def main():
    print("="*90)
    print("FINAL STRATEGY COMPARISON: 3 VERSIONS")
    print("="*90)
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    result = await auto_fetch_candles(db=db, market_data_service=market_data_service, 
                                      symbol="EURUSD", timeframe="1h", min_candles=200)
    
    if not result.success:
        print(f"❌ Data load failed")
        client.close()
        return
    
    candles = result.candles
    print(f"\n✅ Loaded {len(candles)} EURUSD 1h candles ({candles[0].timestamp} to {candles[-1].timestamp})")
    
    config = BacktestConfig(symbol="EURUSD", timeframe=Timeframe.H1, start_date=candles[0].timestamp,
                           end_date=candles[-1].timestamp, initial_balance=10000.0, spread_pips=1.5,
                           commission_per_lot=7.0, leverage=100)
    
    params = {"base_risk_pct": 0.6, "take_profit_atr_mult": 3.8, "stop_loss_atr_mult": 1.9,
             "min_confirmations": 2, "max_trades_per_day": 3, "avoid_ema200_zone_pct": 0.002,
             "require_confirmation": True}
    
    strategies = [
        ("Original (Enhanced)", run_enhanced_multi_signal_strategy),
        ("Adaptive (Soft)", run_adaptive_multi_signal_strategy),
        ("Aggressive (Skip)", run_aggressive_adaptive_strategy),
    ]
    
    results = []
    
    for name, func in strategies:
        print(f"\n{'='*90}")
        print(f"TESTING: {name}")
        print(f"{'='*90}")
        
        trades, equity = func(candles, config, params)
        metrics = calculate_metrics(trades, equity, config.initial_balance)
        wf = walk_forward_analysis(candles, config, func, params)
        
        print(f"\n📊 Performance:")
        print(f"   Trades: {len(trades)}")
        print(f"   PF: {metrics['profit_factor']:.2f}")
        print(f"   DD: {metrics['max_drawdown_pct']:.2f}%")
        print(f"   P&L: ${metrics['total_pnl']:.2f}")
        print(f"   Win%: {metrics['win_rate']:.1f}%")
        print(f"   Sharpe: {metrics['sharpe_ratio']:.2f}")
        
        print(f"\n📈 Walk-Forward:")
        for seg in wf["segments"]:
            status = "✅" if seg["pnl"] > 0 else "❌"
            print(f"   {seg['segment']}: PF {seg['pf']:.2f}, ${seg['pnl']:+.2f} {status}")
        print(f"   Consistency: {wf['consistency']:.1f}%")
        
        results.append({
            "name": name,
            "trades": len(trades),
            "pf": metrics['profit_factor'],
            "dd": metrics['max_drawdown_pct'],
            "pnl": metrics['total_pnl'],
            "win_rate": metrics['win_rate'],
            "sharpe": metrics['sharpe_ratio'],
            "consistency": wf['consistency'],
            "all_profit": wf['all_profitable'],
            "segments": wf['segments'],
        })
    
    # Comparison table
    print(f"\n{'='*90}")
    print("COMPARISON TABLE")
    print(f"{'='*90}")
    
    print(f"\n{'Metric':<20} {'Original':<20} {'Adaptive':<20} {'Aggressive':<20}")
    print("-" * 90)
    
    metrics_to_compare = [
        ("Trades", "trades"),
        ("Profit Factor", "pf"),
        ("Max DD %", "dd"),
        ("Net P&L $", "pnl"),
        ("Win Rate %", "win_rate"),
        ("Sharpe", "sharpe"),
        ("Consistency %", "consistency"),
        ("All Profitable?", "all_profit"),
    ]
    
    for label, key in metrics_to_compare:
        vals = [r[key] for r in results]
        if isinstance(vals[0], bool):
            print(f"{label:<20} {'✅ Yes' if vals[0] else '❌ No':<20} "
                  f"{'✅ Yes' if vals[1] else '❌ No':<20} {'✅ Yes' if vals[2] else '❌ No':<20}")
        elif isinstance(vals[0], (int, float)):
            print(f"{label:<20} {vals[0]:<20.2f} {vals[1]:<20.2f} {vals[2]:<20.2f}")
    
    # Segment comparison
    print(f"\n{'='*90}")
    print("SEGMENT-BY-SEGMENT COMPARISON")
    print(f"{'='*90}")
    
    for i, seg_name in enumerate(["Segment 1", "Segment 2", "Segment 3"]):
        print(f"\n{seg_name}:")
        for r in results:
            seg = r['segments'][i] if i < len(r['segments']) else None
            if seg:
                status = "✅" if seg['pnl'] > 0 else "❌"
                print(f"  {r['name']:<22} PF {seg['pf']:<6.2f} P&L ${seg['pnl']:+8.2f} {status}")
    
    # Final recommendation
    print(f"\n{'='*90}")
    print("RECOMMENDATION")
    print(f"{'='*90}")
    
    # Find best consistency
    best_consistency_idx = max(range(len(results)), key=lambda i: results[i]['consistency'])
    best_consistency = results[best_consistency_idx]
    
    print(f"\n🎯 **Consistency Winner**: {best_consistency['name']}")
    print(f"   Consistency Score: {best_consistency['consistency']:.1f}%")
    print(f"   Target: 50%+")
    
    if best_consistency['consistency'] >= 50:
        print(f"   ✅ **TARGET ACHIEVED**")
    else:
        print(f"   ⚠️  Still below 50% target")
    
    # Check profitability maintained
    original_pf = results[0]['pf']
    best_pf_idx = max(range(len(results)), key=lambda i: results[i]['pf'])
    best_pf = results[best_pf_idx]
    
    print(f"\n💰 **Profitability Check**:")
    print(f"   Original PF: {original_pf:.2f}")
    print(f"   Best PF: {best_pf['pf']:.2f} ({best_pf['name']})")
    
    if best_pf['pf'] >= 1.5:
        print(f"   ✅ Target PF >1.5 maintained")
    else:
        print(f"   ⚠️  PF below 1.5 target")
    
    # Overall recommendation
    print(f"\n💡 **Final Recommendation**:")
    
    # Find strategy that balances consistency and profitability
    scores = []
    for r in results:
        # Score = consistency + profitability bonus
        score = r['consistency'] + (r['pf'] - 1) * 50  # Weight PF heavily
        scores.append(score)
    
    best_overall_idx = max(range(len(results)), key=lambda i: scores[i])
    best_overall = results[best_overall_idx]
    
    print(f"\n   **Best Overall**: {best_overall['name']}")
    print(f"   - Profit Factor: {best_overall['pf']:.2f}")
    print(f"   - Consistency: {best_overall['consistency']:.1f}%")
    print(f"   - All Segments Profitable: {'✅ Yes' if best_overall['all_profit'] else '❌ No'}")
    
    if best_overall['consistency'] >= 40 and best_overall['pf'] >= 1.5:
        print(f"\n   ✅ **PROCEED TO EXTENDED TESTING**")
        print(f"   - Test on 6-12 months of data")
        print(f"   - Multi-symbol validation")
        print(f"   - Parameter optimization")
    elif best_overall['pf'] >= 1.5:
        print(f"\n   ⚠️  **PARTIAL SUCCESS**")
        print(f"   - Profitability maintained")
        print(f"   - Consistency improved but below target")
        print(f"   - Consider: Different regime detection methods")
    else:
        print(f"\n   ❌ **REQUIRES MORE WORK**")
        print(f"   - Revisit strategy fundamentals")
        print(f"   - May need different approach for Segment 2 conditions")
    
    print(f"\n{'='*90}\n")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
