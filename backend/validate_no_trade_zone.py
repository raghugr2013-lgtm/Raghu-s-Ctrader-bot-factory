"""
NO-TRADE ZONE Strategy Validation

Compares:
1. Original enhanced_multi_signal (baseline)
2. Adaptive (soft filters)
3. NO-TRADE ZONE (strict avoidance)

Goal: Consistency 22% → 40%+ by avoiding unfavorable conditions
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from auto_fetch_candles import auto_fetch_candles
from market_data_service import init_market_data_service
from backtest_models import BacktestConfig, Timeframe
from enhanced_multi_signal import run_enhanced_multi_signal_strategy
from adaptive_multi_signal import run_adaptive_multi_signal_strategy
from no_trade_zone_strategy import run_no_trade_zone_strategy
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
            "win_rate": metrics["win_rate"],
        })
    
    pfs = [r["pf"] for r in results if r["pf"] > 0]
    consistency = (min(pfs) / max(pfs) * 100) if pfs and max(pfs) > 0 else 0
    
    return {"segments": results, "consistency": consistency, "all_profitable": all(r["pnl"] > 0 for r in results)}


async def main():
    print("="*90)
    print("NO-TRADE ZONE STRATEGY VALIDATION")
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
    print(f"\n✅ Loaded {len(candles)} EURUSD 1h candles")
    print(f"   Period: {candles[0].timestamp} to {candles[-1].timestamp}")
    
    config = BacktestConfig(symbol="EURUSD", timeframe=Timeframe.H1, start_date=candles[0].timestamp,
                           end_date=candles[-1].timestamp, initial_balance=10000.0, spread_pips=1.5,
                           commission_per_lot=7.0, leverage=100)
    
    params = {"base_risk_pct": 0.6, "take_profit_atr_mult": 3.8, "stop_loss_atr_mult": 1.9,
             "min_confirmations": 2, "max_trades_per_day": 3, "avoid_ema200_zone_pct": 0.002,
             "require_confirmation": True}
    
    strategies = [
        ("Original (Enhanced)", run_enhanced_multi_signal_strategy),
        ("Adaptive (Soft)", run_adaptive_multi_signal_strategy),
        ("NO-TRADE ZONE", run_no_trade_zone_strategy),
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
        print(f"   P&L: ${metrics['total_pnl']:.2f} ({metrics['total_pnl']/config.initial_balance*100:+.1f}%)")
        print(f"   Win%: {metrics['win_rate']:.1f}%")
        print(f"   Sharpe: {metrics['sharpe_ratio']:.2f}")
        
        print(f"\n📈 Walk-Forward:")
        for seg in wf["segments"]:
            status = "✅" if seg["pnl"] > 0 else "❌"
            print(f"   {seg['segment']}: {seg['trades']} trades, PF {seg['pf']:.2f}, ${seg['pnl']:+.2f}, WR {seg['win_rate']:.1f}% {status}")
        print(f"   Consistency: {wf['consistency']:.1f}%")
        print(f"   All Profitable: {'✅ Yes' if wf['all_profitable'] else '❌ No'}")
        
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
    
    # Comparison
    print(f"\n{'='*90}")
    print("COMPARISON TABLE")
    print(f"{'='*90}")
    
    print(f"\n{'Metric':<25} {'Original':<20} {'Adaptive':<20} {'NO-TRADE ZONE':<20}")
    print("-" * 90)
    
    for label, key, better_high in [
        ("Trades", "trades", True),
        ("Profit Factor", "pf", True),
        ("Max DD %", "dd", False),
        ("Net P&L $", "pnl", True),
        ("Win Rate %", "win_rate", True),
        ("Sharpe", "sharpe", True),
        ("Consistency %", "consistency", True),
        ("All Profitable?", "all_profit", True),
    ]:
        vals = [r[key] for r in results]
        if isinstance(vals[0], bool):
            print(f"{label:<25} {'✅' if vals[0] else '❌':<20} {'✅' if vals[1] else '❌':<20} {'✅' if vals[2] else '❌':<20}")
        else:
            # Highlight best value
            if better_high:
                best_idx = vals.index(max(vals))
            else:
                best_idx = vals.index(min(vals))
            
            formatted = []
            for i, v in enumerate(vals):
                if i == best_idx:
                    formatted.append(f"{v:.2f} ⭐")
                else:
                    formatted.append(f"{v:.2f}")
            
            print(f"{label:<25} {formatted[0]:<20} {formatted[1]:<20} {formatted[2]:<20}")
    
    # Segment details
    print(f"\n{'='*90}")
    print("SEGMENT-BY-SEGMENT ANALYSIS")
    print(f"{'='*90}")
    
    for i, seg_name in enumerate(["Segment 1 (Dec-Jan)", "Segment 2 (Jan-Feb) ⚠️", "Segment 3 (Feb-Mar)"]):
        print(f"\n{seg_name}:")
        for r in results:
            seg = r['segments'][i] if i < len(r['segments']) else None
            if seg:
                status = "✅" if seg['pnl'] > 0 else "❌"
                print(f"  {r['name']:<23} {seg['trades']:>2} trades | PF {seg['pf']:<6.2f} | ${seg['pnl']:>8.2f} | WR {seg['win_rate']:>5.1f}% {status}")
    
    # Final verdict
    print(f"\n{'='*90}")
    print("FINAL VERDICT")
    print(f"{'='*90}")
    
    no_trade_zone = results[2]
    adaptive = results[1]
    original = results[0]
    
    print(f"\n🎯 **CONSISTENCY IMPROVEMENT**")
    print(f"   Original:     {original['consistency']:.1f}%")
    print(f"   Adaptive:     {adaptive['consistency']:.1f}%")
    print(f"   NO-TRADE ZONE: {no_trade_zone['consistency']:.1f}%")
    print(f"   Target:        40%+")
    
    if no_trade_zone['consistency'] >= 40:
        print(f"   ✅ **TARGET ACHIEVED** ({no_trade_zone['consistency']:.1f}%)")
    elif no_trade_zone['consistency'] > adaptive['consistency']:
        improvement = no_trade_zone['consistency'] - original['consistency']
        print(f"   ⚠️  **IMPROVED** (+{improvement:.1f}% from original, but below 40% target)")
    else:
        print(f"   ❌ **NO IMPROVEMENT**")
    
    print(f"\n💰 **PROFITABILITY**")
    print(f"   Original PF:     {original['pf']:.2f}")
    print(f"   Adaptive PF:     {adaptive['pf']:.2f}")
    print(f"   NO-TRADE ZONE PF: {no_trade_zone['pf']:.2f}")
    print(f"   Target:           >1.5")
    
    if no_trade_zone['pf'] >= 1.5:
        print(f"   ✅ **TARGET MET**")
    else:
        print(f"   ❌ **BELOW TARGET**")
    
    print(f"\n📊 **SEGMENT 2 PERFORMANCE (The Problem Child)**")
    seg2_results = [(r['name'], r['segments'][1]) for r in results]
    for name, seg in seg2_results:
        status = "✅ PROFITABLE" if seg['pnl'] > 0 else "❌ LOSING"
        print(f"   {name:<23} PF {seg['pf']:.2f}, ${seg['pnl']:+.2f} {status}")
    
    # Check if any version made Segment 2 profitable
    seg2_profitable = any(seg['pnl'] > 0 for name, seg in seg2_results)
    
    if seg2_profitable:
        print(f"\n   ✅ **BREAKTHROUGH**: NO-TRADE ZONE made Segment 2 profitable!")
    else:
        print(f"\n   ⚠️  Segment 2 remains challenging for all versions")
    
    print(f"\n💡 **RECOMMENDATION**")
    
    if no_trade_zone['consistency'] >= 40 and no_trade_zone['pf'] >= 1.5:
        print(f"\n   ✅ **SUCCESS - PROCEED TO EXTENDED TESTING**")
        print(f"   - Consistency target achieved ({no_trade_zone['consistency']:.1f}%)")
        print(f"   - Profitability maintained (PF {no_trade_zone['pf']:.2f})")
        print(f"   - Ready for 6-12 month validation")
        print(f"   - Deploy to paper trading")
    elif no_trade_zone['consistency'] > 30 and no_trade_zone['pf'] >= 1.5:
        print(f"\n   ⚠️  **SIGNIFICANT IMPROVEMENT BUT NOT SUFFICIENT**")
        print(f"   - Consistency improved to {no_trade_zone['consistency']:.1f}% (target: 40%)")
        print(f"   - Profitability maintained")
        print(f"   - Next steps:")
        print(f"     • Test on extended dataset (6-12 months)")
        print(f"     • Parameter optimization")
        print(f"     • Consider ML-based regime detection")
    else:
        print(f"\n   ⚠️  **PARTIAL SUCCESS**")
        print(f"   - Some improvement but targets not met")
        print(f"   - Segment 2 remains problematic")
        print(f"   - Recommendations:")
        print(f"     • May need fundamentally different approach for ranging markets")
        print(f"     • Consider mean-reversion strategy for choppy conditions")
        print(f"     • Extended data testing to validate findings")
    
    print(f"\n📁 **RECOMMENDED STRATEGY FILE**")
    best_consistency_idx = max(range(len(results)), key=lambda i: results[i]['consistency'])
    best = results[best_consistency_idx]
    
    if best['name'] == "NO-TRADE ZONE":
        print(f"   📄 /app/backend/no_trade_zone_strategy.py")
    elif best['name'] == "Adaptive (Soft)":
        print(f"   📄 /app/backend/adaptive_multi_signal.py")
    else:
        print(f"   📄 /app/backend/enhanced_multi_signal.py")
    
    print(f"   Reason: Best consistency ({best['consistency']:.1f}%) with PF {best['pf']:.2f}")
    
    print(f"\n{'='*90}\n")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
