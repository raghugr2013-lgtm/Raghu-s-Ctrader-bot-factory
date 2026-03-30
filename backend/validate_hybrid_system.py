"""
HYBRID TRADING SYSTEM Validation

Compares:
1. Original (trend-following only)
2. Adaptive (improved trend-following)
3. Mean-Reversion (ranging only)
4. HYBRID (intelligent switching)

Goal: Consistency >40% by using appropriate strategy for each regime
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
from mean_reversion_strategy import run_mean_reversion_strategy
from hybrid_trading_system import run_hybrid_trading_system
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
    print("="*100)
    print("HYBRID TRADING SYSTEM VALIDATION")
    print("="*100)
    
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
    
    params = {"base_risk_pct": 0.6, "base_risk_pct_trend": 0.7, "base_risk_pct_range": 0.5,
             "take_profit_atr_mult": 3.8, "stop_loss_atr_mult": 1.9,
             "min_confirmations": 2, "max_trades_per_day": 3, "avoid_ema200_zone_pct": 0.002,
             "require_confirmation": True}
    
    strategies = [
        ("Adaptive (Trend)", run_adaptive_multi_signal_strategy),
        ("Mean-Reversion", run_mean_reversion_strategy),
        ("🔥 HYBRID", run_hybrid_trading_system),
    ]
    
    results = []
    
    for name, func in strategies:
        print(f"\n{'='*100}")
        print(f"TESTING: {name}")
        print(f"{'='*100}")
        
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
            print(f"   {seg['segment']}: {seg['trades']:>2} trades | PF {seg['pf']:<6.2f} | ${seg['pnl']:>8.2f} | WR {seg['win_rate']:>5.1f}% {status}")
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
    print(f"\n{'='*100}")
    print("COMPARISON TABLE")
    print(f"{'='*100}")
    
    print(f"\n{'Metric':<25} {'Adaptive':<25} {'Mean-Reversion':<25} {'🔥 HYBRID':<25}")
    print("-" * 100)
    
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
            print(f"{label:<25} {'✅' if vals[0] else '❌':<25} {'✅' if vals[1] else '❌':<25} {'✅' if vals[2] else '❌':<25}")
        else:
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
            
            print(f"{label:<25} {formatted[0]:<25} {formatted[1]:<25} {formatted[2]:<25}")
    
    # Segment details
    print(f"\n{'='*100}")
    print("SEGMENT-BY-SEGMENT ANALYSIS")
    print(f"{'='*100}")
    
    for i, seg_name in enumerate(["Segment 1 (Dec-Jan)", "Segment 2 (Jan-Feb) 🎯", "Segment 3 (Feb-Mar)"]):
        print(f"\n{seg_name}:")
        for r in results:
            seg = r['segments'][i] if i < len(r['segments']) else None
            if seg:
                status = "✅" if seg['pnl'] > 0 else "❌"
                print(f"  {r['name']:<25} {seg['trades']:>2} trades | PF {seg['pf']:<6.2f} | ${seg['pnl']:>8.2f} | WR {seg['win_rate']:>5.1f}% {status}")
    
    # Final verdict
    print(f"\n{'='*100}")
    print("FINAL VERDICT")
    print(f"{'='*100}")
    
    hybrid = results[2]
    adaptive = results[0]
    
    print(f"\n🎯 **CONSISTENCY TARGET**")
    print(f"   Adaptive (Trend):     {adaptive['consistency']:.1f}%")
    print(f"   HYBRID:              {hybrid['consistency']:.1f}%")
    print(f"   Target:               40%+")
    
    if hybrid['consistency'] >= 40:
        print(f"   ✅ **TARGET ACHIEVED** ({hybrid['consistency']:.1f}%)")
    elif hybrid['consistency'] > adaptive['consistency']:
        improvement = hybrid['consistency'] - adaptive['consistency']
        print(f"   ⚠️  **IMPROVED** (+{improvement:.1f}% from adaptive, but below 40% target)")
    else:
        print(f"   ❌ **NO IMPROVEMENT**")
    
    print(f"\n💰 **PROFITABILITY**")
    print(f"   Adaptive PF:     {adaptive['pf']:.2f}")
    print(f"   HYBRID PF:      {hybrid['pf']:.2f}")
    print(f"   Target:          >1.5")
    
    if hybrid['pf'] >= 1.5:
        print(f"   ✅ **TARGET MET**")
    else:
        print(f"   ❌ **BELOW TARGET**")
    
    print(f"\n📊 **SEGMENT 2 BREAKTHROUGH CHECK** 🎯")
    seg2_results = [(r['name'], r['segments'][1]) for r in results]
    for name, seg in seg2_results:
        status = "✅ PROFITABLE" if seg['pnl'] > 0 else "❌ LOSING"
        print(f"   {name:<25} PF {seg['pf']:.2f}, ${seg['pnl']:+.2f} {status}")
    
    seg2_profitable = any(seg['pnl'] > 0 for name, seg in seg2_results)
    
    if hybrid['segments'][1]['pnl'] > 0:
        print(f"\n   🎉 **BREAKTHROUGH!** Hybrid made Segment 2 profitable!")
    else:
        best_seg2_loss = max(seg['pnl'] for name, seg in seg2_results)
        print(f"\n   ⚠️  Segment 2 remains challenging")
        print(f"   Best loss reduction: ${best_seg2_loss:+.2f}")
    
    print(f"\n💡 **RECOMMENDATION**")
    
    if hybrid['consistency'] >= 40 and hybrid['pf'] >= 1.5:
        print(f"\n   🏆 **SUCCESS - READY FOR EXTENDED TESTING**")
        print(f"   ✅ Consistency target achieved ({hybrid['consistency']:.1f}%)")
        print(f"   ✅ Profitability maintained (PF {hybrid['pf']:.2f})")
        print(f"   ✅ All segments profitable: {'Yes' if hybrid['all_profit'] else 'No'}")
        print(f"\n   Next steps:")
        print(f"   - Test on 6-12 months of data")
        print(f"   - Deploy to paper trading")
        print(f"   - Multi-symbol validation")
    elif hybrid['consistency'] > 30 and hybrid['pf'] >= 1.5:
        print(f"\n   ⚠️  **SIGNIFICANT IMPROVEMENT BUT NOT SUFFICIENT**")
        print(f"   - Consistency improved to {hybrid['consistency']:.1f}% (target: 40%)")
        print(f"   - Profitability maintained (PF {hybrid['pf']:.2f})")
        print(f"\n   Next steps:")
        print(f"   - Extended data testing (6-12 months)")
        print(f"   - Parameter optimization")
        print(f"   - Consider ML-based regime detection")
    else:
        print(f"\n   ⚠️  **PARTIAL SUCCESS**")
        print(f"   - Some improvement but targets not fully met")
        print(f"   - Segment 2 remains challenging")
        print(f"\n   Recommendations:")
        print(f"   - Review mean-reversion parameters for ranging markets")
        print(f"   - Test on longer dataset to validate approach")
        print(f"   - Consider additional regime classification (breakout, consolidation)")
    
    print(f"\n📁 **RECOMMENDED STRATEGY FILE**")
    best_consistency_idx = max(range(len(results)), key=lambda i: results[i]['consistency'])
    best = results[best_consistency_idx]
    
    if best['name'] == "🔥 HYBRID":
        print(f"   📄 /app/backend/hybrid_trading_system.py ⭐")
        print(f"   Why: Best consistency ({best['consistency']:.1f}%) with PF {best['pf']:.2f}")
    else:
        print(f"   📄 /app/backend/adaptive_multi_signal.py")
        print(f"   Why: {best['name']} - Best consistency ({best['consistency']:.1f}%)")
    
    print(f"\n{'='*100}\n")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
