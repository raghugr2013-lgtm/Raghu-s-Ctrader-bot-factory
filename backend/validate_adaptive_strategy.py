"""
Full Validation Pipeline for Adaptive Multi-Signal Strategy

Compares:
1. Original enhanced_multi_signal (baseline)
2. New adaptive_multi_signal (improved)

Goal: Improve consistency from 18.7% to 50%+ without reducing profitability
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
import numpy as np
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import List, Dict

from auto_fetch_candles import auto_fetch_candles
from market_data_service import init_market_data_service
from backtest_models import BacktestConfig, Timeframe
from enhanced_multi_signal import run_enhanced_multi_signal_strategy
from adaptive_multi_signal import run_adaptive_multi_signal_strategy
from test_eurusd_strategy import calculate_metrics

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')


def monte_carlo_simulation(trades: List, num_simulations: int = 1000) -> Dict:
    """Run Monte Carlo simulation"""
    if len(trades) < 10:
        return {"error": "Insufficient trades for Monte Carlo"}
    
    returns = [t.profit_loss for t in trades]
    simulation_results = []
    
    for _ in range(num_simulations):
        sampled_returns = np.random.choice(returns, size=len(returns), replace=True)
        total_return = sum(sampled_returns)
        
        equity = 10000.0
        peak = equity
        max_dd = 0
        
        for ret in sampled_returns:
            equity += ret
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        simulation_results.append({
            "total_return": total_return,
            "final_equity": equity,
            "max_dd": max_dd,
        })
    
    returns_list = [s["total_return"] for s in simulation_results]
    dd_list = [s["max_dd"] for s in simulation_results]
    
    return {
        "num_simulations": num_simulations,
        "average_return": np.mean(returns_list),
        "median_return": np.median(returns_list),
        "std_return": np.std(returns_list),
        "worst_return": min(returns_list),
        "best_return": max(returns_list),
        "profitable_pct": sum(1 for r in returns_list if r > 0) / len(returns_list) * 100,
        "average_dd": np.mean(dd_list),
        "worst_dd": max(dd_list),
        "stability_score": (sum(1 for r in returns_list if r > 0) / len(returns_list)) * (1 - np.mean(dd_list) / 100) * 100,
    }


def walk_forward_analysis(candles: List, config: BacktestConfig, strategy_func, params: Dict) -> Dict:
    """Walk-forward analysis: 3 segments"""
    segment_size = len(candles) // 3
    
    segments = [
        {"name": "Segment 1", "data": candles[0:segment_size]},
        {"name": "Segment 2", "data": candles[segment_size:segment_size*2]},
        {"name": "Segment 3", "data": candles[segment_size*2:]},
    ]
    
    results = []
    
    for seg in segments:
        if len(seg["data"]) < 100:
            continue
        
        trades, equity_curve = strategy_func(seg["data"], config, params)
        metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
        
        results.append({
            "segment": seg["name"],
            "candles": len(seg["data"]),
            "trades": metrics["total_trades"],
            "profit_factor": metrics["profit_factor"],
            "total_pnl": metrics["total_pnl"],
            "max_dd": metrics["max_drawdown_pct"],
            "win_rate": metrics["win_rate"],
        })
    
    # Calculate consistency
    if len(results) >= 2:
        pfs = [r["profit_factor"] for r in results if r["profit_factor"] > 0]
        consistency_score = (min(pfs) / max(pfs) * 100) if pfs and max(pfs) > 0 else 0
    else:
        consistency_score = 0
    
    return {
        "segments": results,
        "consistency_score": consistency_score,
        "all_profitable": all(r["total_pnl"] > 0 for r in results),
    }


def calculate_final_score(metrics: Dict, wf_results: Dict, mc_results: Dict) -> float:
    """Calculate final score out of 100"""
    profitability_score = min((metrics['profit_factor'] - 1) / 0.5 * 25, 25)
    drawdown_score = max(25 - metrics['max_drawdown_pct'] * 2.5, 0)
    consistency_score = wf_results['consistency_score'] / 4
    stability_score = mc_results['stability_score'] / 4 if mc_results and 'stability_score' in mc_results else 0
    
    return profitability_score + drawdown_score + consistency_score + stability_score


async def run_comparison_validation():
    """Run side-by-side comparison of original vs adaptive strategy"""
    
    print("="*80)
    print("ADAPTIVE STRATEGY VALIDATION - COMPARISON TEST")
    print("="*80)
    
    # Connect
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Load data
    print("\n" + "="*80)
    print("DATA LOADING")
    print("="*80)
    
    print("\n📊 Loading EURUSD data from Dukascopy cache...")
    
    result = await auto_fetch_candles(
        db=db,
        market_data_service=market_data_service,
        symbol="EURUSD",
        timeframe="1h",
        min_candles=200
    )
    
    if not result.success:
        print(f"❌ Failed to load data: {result.error}")
        client.close()
        return
    
    candles = result.candles
    print(f"✅ Loaded {len(candles)} candles")
    print(f"   Period: {candles[0].timestamp} to {candles[-1].timestamp}")
    
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
    
    params = {
        "base_risk_pct": 0.6,
        "take_profit_atr_mult": 3.8,
        "stop_loss_atr_mult": 1.9,
        "min_confirmations": 2,
        "max_trades_per_day": 3,
        "avoid_ema200_zone_pct": 0.002,
        "require_confirmation": True,
    }
    
    # ========================================================================
    # TEST 1: Original Enhanced Multi-Signal (Baseline)
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 1: ORIGINAL ENHANCED_MULTI_SIGNAL (BASELINE)")
    print("="*80)
    
    print("\n🚀 Running original strategy...")
    original_trades, original_equity = run_enhanced_multi_signal_strategy(candles, config, params)
    
    print(f"✅ Original: {len(original_trades)} trades")
    
    original_metrics = calculate_metrics(original_trades, original_equity, config.initial_balance)
    
    print(f"\n📊 Original Performance:")
    print(f"   Profit Factor: {original_metrics['profit_factor']:.2f}")
    print(f"   Max Drawdown: {original_metrics['max_drawdown_pct']:.2f}%")
    print(f"   Net Profit: ${original_metrics['total_pnl']:.2f}")
    print(f"   Win Rate: {original_metrics['win_rate']:.1f}%")
    print(f"   Sharpe: {original_metrics['sharpe_ratio']:.2f}")
    
    print("\n🎲 Running Monte Carlo (original)...")
    original_mc = monte_carlo_simulation(original_trades, 1000)
    print(f"   Stability: {original_mc['stability_score']:.1f}/100")
    print(f"   Profitable: {original_mc['profitable_pct']:.1f}%")
    
    print("\n📊 Running Walk-Forward (original)...")
    original_wf = walk_forward_analysis(candles, config, run_enhanced_multi_signal_strategy, params)
    print(f"   Consistency: {original_wf['consistency_score']:.1f}%")
    print(f"   All Profitable: {'✅' if original_wf['all_profitable'] else '❌'}")
    
    for seg in original_wf["segments"]:
        print(f"   {seg['segment']}: PF {seg['profit_factor']:.2f}, P&L ${seg['total_pnl']:+.2f}")
    
    original_score = calculate_final_score(original_metrics, original_wf, original_mc)
    print(f"\n🏆 Original Score: {original_score:.1f}/100")
    
    # ========================================================================
    # TEST 2: Adaptive Multi-Signal (Improved)
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 2: ADAPTIVE_MULTI_SIGNAL (IMPROVED)")
    print("="*80)
    
    print("\n🚀 Running adaptive strategy...")
    adaptive_trades, adaptive_equity = run_adaptive_multi_signal_strategy(candles, config, params)
    
    print(f"✅ Adaptive: {len(adaptive_trades)} trades")
    
    adaptive_metrics = calculate_metrics(adaptive_trades, adaptive_equity, config.initial_balance)
    
    print(f"\n📊 Adaptive Performance:")
    print(f"   Profit Factor: {adaptive_metrics['profit_factor']:.2f}")
    print(f"   Max Drawdown: {adaptive_metrics['max_drawdown_pct']:.2f}%")
    print(f"   Net Profit: ${adaptive_metrics['total_pnl']:.2f}")
    print(f"   Win Rate: {adaptive_metrics['win_rate']:.1f}%")
    print(f"   Sharpe: {adaptive_metrics['sharpe_ratio']:.2f}")
    
    print("\n🎲 Running Monte Carlo (adaptive)...")
    adaptive_mc = monte_carlo_simulation(adaptive_trades, 1000)
    print(f"   Stability: {adaptive_mc['stability_score']:.1f}/100")
    print(f"   Profitable: {adaptive_mc['profitable_pct']:.1f}%")
    
    print("\n📊 Running Walk-Forward (adaptive)...")
    adaptive_wf = walk_forward_analysis(candles, config, run_adaptive_multi_signal_strategy, params)
    print(f"   Consistency: {adaptive_wf['consistency_score']:.1f}%")
    print(f"   All Profitable: {'✅' if adaptive_wf['all_profitable'] else '❌'}")
    
    for seg in adaptive_wf["segments"]:
        print(f"   {seg['segment']}: PF {seg['profit_factor']:.2f}, P&L ${seg['total_pnl']:+.2f}")
    
    adaptive_score = calculate_final_score(adaptive_metrics, adaptive_wf, adaptive_mc)
    print(f"\n🏆 Adaptive Score: {adaptive_score:.1f}/100")
    
    # ========================================================================
    # COMPARISON
    # ========================================================================
    print("\n" + "="*80)
    print("SIDE-BY-SIDE COMPARISON")
    print("="*80)
    
    print(f"\n{'Metric':<25} {'Original':<20} {'Adaptive':<20} {'Change':<15}")
    print("-" * 80)
    
    metrics_comparison = [
        ("Trades", len(original_trades), len(adaptive_trades)),
        ("Profit Factor", original_metrics['profit_factor'], adaptive_metrics['profit_factor']),
        ("Max Drawdown %", original_metrics['max_drawdown_pct'], adaptive_metrics['max_drawdown_pct']),
        ("Net Profit $", original_metrics['total_pnl'], adaptive_metrics['total_pnl']),
        ("Win Rate %", original_metrics['win_rate'], adaptive_metrics['win_rate']),
        ("Sharpe Ratio", original_metrics['sharpe_ratio'], adaptive_metrics['sharpe_ratio']),
        ("MC Stability", original_mc['stability_score'], adaptive_mc['stability_score']),
        ("Consistency %", original_wf['consistency_score'], adaptive_wf['consistency_score']),
        ("Final Score", original_score, adaptive_score),
    ]
    
    for metric_name, orig_val, adapt_val in metrics_comparison:
        if isinstance(orig_val, float):
            change = adapt_val - orig_val
            change_pct = (change / orig_val * 100) if orig_val != 0 else 0
            
            if metric_name == "Max Drawdown %":
                # Lower is better for drawdown
                indicator = "✅" if change < 0 else "⚠️" if change == 0 else "❌"
            else:
                # Higher is better for others
                indicator = "✅" if change > 0 else "⚠️" if change == 0 else "❌"
            
            print(f"{metric_name:<25} {orig_val:<20.2f} {adapt_val:<20.2f} {change:+.2f} ({change_pct:+.1f}%) {indicator}")
        else:
            change = adapt_val - orig_val
            indicator = "✅" if change >= 0 else "❌"
            print(f"{metric_name:<25} {orig_val:<20} {adapt_val:<20} {change:+d} {indicator}")
    
    # ========================================================================
    # FINAL VERDICT
    # ========================================================================
    print("\n" + "="*80)
    print("FINAL VERDICT")
    print("="*80)
    
    print(f"\n🎯 **PRIMARY GOAL: Improve Consistency**")
    print(f"   Target: >50% consistency score")
    print(f"   Original: {original_wf['consistency_score']:.1f}%")
    print(f"   Adaptive: {adaptive_wf['consistency_score']:.1f}%")
    
    consistency_improvement = adaptive_wf['consistency_score'] - original_wf['consistency_score']
    
    if adaptive_wf['consistency_score'] >= 50:
        print(f"   ✅ **TARGET ACHIEVED** (+{consistency_improvement:.1f}% improvement)")
    elif consistency_improvement > 0:
        print(f"   ⚠️  **PARTIAL IMPROVEMENT** (+{consistency_improvement:.1f}%, but below 50% target)")
    else:
        print(f"   ❌ **NO IMPROVEMENT** ({consistency_improvement:.1f}% change)")
    
    print(f"\n💰 **Profitability Check**")
    print(f"   Target: Maintain or improve PF > 1.5")
    print(f"   Original PF: {original_metrics['profit_factor']:.2f}")
    print(f"   Adaptive PF: {adaptive_metrics['profit_factor']:.2f}")
    
    if adaptive_metrics['profit_factor'] >= 1.5 and adaptive_metrics['profit_factor'] >= original_metrics['profit_factor']:
        print(f"   ✅ **PROFITABILITY MAINTAINED**")
    elif adaptive_metrics['profit_factor'] >= 1.5:
        print(f"   ⚠️  **PROFITABILITY ACCEPTABLE** (above 1.5 but slightly lower)")
    else:
        print(f"   ❌ **PROFITABILITY DEGRADED**")
    
    print(f"\n📊 **Walk-Forward Segment Analysis**")
    print(f"\n   Original Segments:")
    for seg in original_wf["segments"]:
        status = "✅" if seg['total_pnl'] > 0 else "❌"
        print(f"   {seg['segment']}: PF {seg['profit_factor']:.2f}, ${seg['total_pnl']:+.2f} {status}")
    
    print(f"\n   Adaptive Segments:")
    for seg in adaptive_wf["segments"]:
        status = "✅" if seg['total_pnl'] > 0 else "❌"
        print(f"   {seg['segment']}: PF {seg['profit_factor']:.2f}, ${seg['total_pnl']:+.2f} {status}")
    
    print(f"\n🏆 **Overall Score Improvement**")
    score_improvement = adaptive_score - original_score
    print(f"   Original: {original_score:.1f}/100")
    print(f"   Adaptive: {adaptive_score:.1f}/100")
    print(f"   Change: {score_improvement:+.1f} points")
    
    if adaptive_score >= 70:
        grade = "B (Good)" if adaptive_score < 80 else "A (Excellent)"
        print(f"   ✅ **GRADE: {grade}** - Ready for consideration")
    elif adaptive_score >= 60:
        print(f"   ⚠️  **GRADE: C (Acceptable)** - Further improvements recommended")
    else:
        print(f"   ❌ **GRADE: D/F** - Requires significant work")
    
    # Recommendation
    print(f"\n💡 **RECOMMENDATION**")
    
    if (adaptive_wf['consistency_score'] >= 50 and 
        adaptive_metrics['profit_factor'] >= 1.5 and 
        adaptive_score >= 70):
        print(f"   ✅ **DEPLOY TO PAPER TRADING**")
        print(f"   Strategy shows improved consistency and maintains profitability.")
        print(f"   Next step: 30-day paper trading validation")
    elif (adaptive_wf['consistency_score'] > original_wf['consistency_score'] and 
          adaptive_metrics['profit_factor'] >= 1.5):
        print(f"   ⚠️  **IMPROVEMENT ACHIEVED BUT NOT SUFFICIENT**")
        print(f"   Consistency improved but below 50% target.")
        print(f"   Consider: Extended data testing, parameter optimization")
    else:
        print(f"   ❌ **REQUIRES FURTHER WORK**")
        print(f"   Adaptive strategy did not achieve consistency goals.")
        print(f"   Revisit: Regime detection logic, confirmation requirements")
    
    print("\n" + "="*80)
    
    client.close()


if __name__ == "__main__":
    asyncio.run(run_comparison_validation())
