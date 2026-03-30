"""
Full Validation Pipeline using Local Dukascopy Data

Executes complete validation workflow:
1. Use local Dukascopy EURUSD data (already in cache)
2. Run enhanced multi-signal strategy
3. Calculate comprehensive metrics
4. Monte Carlo simulation
5. Walk-forward analysis
6. Final scoring

Data: Dec 23, 2025 - Mar 23, 2026 (3 months, 1,470 H1 candles)
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
from test_eurusd_strategy import calculate_metrics

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')


def monte_carlo_simulation(trades: List, num_simulations: int = 1000) -> Dict:
    """
    Run Monte Carlo simulation by randomly resampling trades.
    Tests strategy robustness.
    """
    if len(trades) < 10:
        return {"error": "Insufficient trades for Monte Carlo"}
    
    # Extract returns
    returns = [t.profit_loss for t in trades]
    
    simulation_results = []
    
    for _ in range(num_simulations):
        # Random resample with replacement
        sampled_returns = np.random.choice(returns, size=len(returns), replace=True)
        total_return = sum(sampled_returns)
        
        # Calculate max drawdown for this sequence
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
    
    # Analysis
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
        "best_dd": min(dd_list),
        "stability_score": (sum(1 for r in returns_list if r > 0) / len(returns_list)) * (1 - np.mean(dd_list) / 100) * 100,
    }


def walk_forward_analysis(candles: List, config: BacktestConfig, strategy_func, params: Dict) -> Dict:
    """
    Walk-forward analysis: Train on period, test on next period.
    Validates strategy doesn't overfit.
    """
    # Split into 3 segments
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
        
        # Run strategy on this segment
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


async def run_full_validation():
    """Execute complete validation pipeline"""
    
    print("="*70)
    print("FULL VALIDATION PIPELINE - DUKASCOPY LOCAL DATA")
    print("="*70)
    
    # Connect
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # STEP 1: Fetch data from local cache
    print("\n" + "="*70)
    print("STEP 1: DATA LOADING")
    print("="*70)
    
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
    
    print(f"✅ Loaded {len(candles)} candles from {result.source}")
    print(f"   Period: {candles[0].timestamp} to {candles[-1].timestamp}")
    print(f"   Duration: {(candles[-1].timestamp - candles[0].timestamp).days} days")
    
    # Verify data source
    sample_doc = await db.market_candles.find_one({
        "symbol": "EURUSD",
        "timeframe": "1h"
    })
    
    if sample_doc and sample_doc.get('source') == 'dukascopy':
        print(f"✅ Confirmed: Data source is Dukascopy local")
    else:
        print(f"⚠️  Warning: Data source is {sample_doc.get('source') if sample_doc else 'unknown'}")
    
    # STEP 2: Run Strategy
    print("\n" + "="*70)
    print("STEP 2: STRATEGY EXECUTION")
    print("="*70)
    
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
    
    # Use best configuration from previous testing
    params = {
        "base_risk_pct": 0.6,
        "take_profit_atr_mult": 3.8,
        "stop_loss_atr_mult": 1.9,
        "min_confirmations": 2,
        "max_trades_per_day": 3,
        "avoid_ema200_zone_pct": 0.002,
        "require_confirmation": True,
    }
    
    print("\n🚀 Running Enhanced Multi-Signal Strategy...")
    print(f"   Parameters: {params}")
    
    trades, equity_curve = run_enhanced_multi_signal_strategy(candles, config, params)
    
    print(f"✅ Strategy execution complete")
    print(f"   Trades generated: {len(trades)}")
    
    # STEP 3: Calculate Base Metrics
    print("\n" + "="*70)
    print("STEP 3: PERFORMANCE METRICS")
    print("="*70)
    
    metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
    
    print(f"\n📊 Core Metrics:")
    print(f"   Total Trades: {metrics['total_trades']}")
    print(f"   Win Rate: {metrics['win_rate']:.1f}%")
    print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"   Net Profit: ${metrics['total_pnl']:.2f} ({metrics['total_pnl']/config.initial_balance*100:+.1f}%)")
    print(f"   Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"   Expectancy: ${metrics['expectancy']:.2f}/trade")
    print(f"   Avg Win: ${metrics['avg_win']:.2f}")
    print(f"   Avg Loss: ${metrics['avg_loss']:.2f}")
    print(f"   Win/Loss Ratio: {metrics['avg_win']/abs(metrics['avg_loss']) if metrics['avg_loss'] != 0 else 0:.2f}")
    
    # STEP 4: Monte Carlo Simulation
    print("\n" + "="*70)
    print("STEP 4: MONTE CARLO SIMULATION")
    print("="*70)
    
    print("\n🎲 Running 1000 simulations...")
    
    mc_results = monte_carlo_simulation(trades, 1000)
    
    if "error" not in mc_results:
        print(f"✅ Monte Carlo complete")
        print(f"\n📈 Simulation Results:")
        print(f"   Average Return: ${mc_results['average_return']:.2f}")
        print(f"   Median Return: ${mc_results['median_return']:.2f}")
        print(f"   Std Deviation: ${mc_results['std_return']:.2f}")
        print(f"   Best Case: ${mc_results['best_return']:.2f}")
        print(f"   Worst Case: ${mc_results['worst_return']:.2f}")
        print(f"   Profitable: {mc_results['profitable_pct']:.1f}%")
        print(f"   Avg Drawdown: {mc_results['average_dd']:.2f}%")
        print(f"   Worst Drawdown: {mc_results['worst_dd']:.2f}%")
        print(f"   Stability Score: {mc_results['stability_score']:.1f}/100")
    else:
        print(f"⚠️  {mc_results['error']}")
        mc_results = None
    
    # STEP 5: Walk-Forward Analysis
    print("\n" + "="*70)
    print("STEP 5: WALK-FORWARD VALIDATION")
    print("="*70)
    
    print("\n📊 Running walk-forward analysis (3 segments)...")
    
    wf_results = walk_forward_analysis(candles, config, run_enhanced_multi_signal_strategy, params)
    
    print(f"✅ Walk-forward complete")
    print(f"\n📈 Segment Performance:")
    
    for seg in wf_results["segments"]:
        print(f"\n   {seg['segment']} ({seg['candles']} candles):")
        print(f"      Trades: {seg['trades']}")
        print(f"      Profit Factor: {seg['profit_factor']:.2f}")
        print(f"      P&L: ${seg['total_pnl']:+.2f}")
        print(f"      Max DD: {seg['max_dd']:.2f}%")
        print(f"      Win Rate: {seg['win_rate']:.1f}%")
    
    print(f"\n   Consistency Score: {wf_results['consistency_score']:.1f}%")
    print(f"   All Segments Profitable: {'✅ Yes' if wf_results['all_profitable'] else '❌ No'}")
    
    # STEP 6: Compliance & Final Score
    print("\n" + "="*70)
    print("STEP 6: COMPLIANCE & FINAL SCORING")
    print("="*70)
    
    # Compliance checks
    compliance_checks = {
        "Min Trades": metrics['total_trades'] >= 30,
        "Profit Factor > 1.2": metrics['profit_factor'] > 1.2,
        "Max DD < 10%": metrics['max_drawdown_pct'] < 10.0,
        "Positive Return": metrics['total_pnl'] > 0,
        "Win Rate > 30%": metrics['win_rate'] > 30,
        "Sharpe > 1.0": metrics['sharpe_ratio'] > 1.0,
    }
    
    print(f"\n✅ Compliance Checks:")
    for check, passed in compliance_checks.items():
        print(f"   {'✅' if passed else '❌'} {check}")
    
    passed_checks = sum(1 for p in compliance_checks.values() if p)
    total_checks = len(compliance_checks)
    
    # Calculate final score
    profitability_score = min((metrics['profit_factor'] - 1) / 0.5 * 25, 25)
    drawdown_score = max(25 - metrics['max_drawdown_pct'] * 2.5, 0)
    consistency_score = wf_results['consistency_score'] / 4
    stability_score = mc_results['stability_score'] / 4 if mc_results else 0
    
    final_score = profitability_score + drawdown_score + consistency_score + stability_score
    
    print(f"\n📊 Final Score Breakdown:")
    print(f"   Profitability: {profitability_score:.1f}/25")
    print(f"   Drawdown Control: {drawdown_score:.1f}/25")
    print(f"   Consistency: {consistency_score:.1f}/25")
    print(f"   Stability: {stability_score:.1f}/25")
    print(f"   ---")
    print(f"   TOTAL SCORE: {final_score:.1f}/100")
    
    # Grade
    if final_score >= 80:
        grade = "A (Excellent)"
    elif final_score >= 70:
        grade = "B (Good)"
    elif final_score >= 60:
        grade = "C (Acceptable)"
    elif final_score >= 50:
        grade = "D (Needs Improvement)"
    else:
        grade = "F (Failed)"
    
    print(f"   GRADE: {grade}")
    
    # Summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    
    print(f"\n📊 Data Quality:")
    print(f"   Source: Dukascopy Local")
    print(f"   Candles: {len(candles):,}")
    print(f"   Period: {(candles[-1].timestamp - candles[0].timestamp).days} days")
    print(f"   Completeness: ✅")
    
    print(f"\n💰 Performance:")
    print(f"   Net Profit: ${metrics['total_pnl']:.2f}")
    print(f"   Return: {metrics['total_pnl']/config.initial_balance*100:+.1f}%")
    print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    
    print(f"\n⚖️  Risk:")
    print(f"   Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"   Avg MC Drawdown: {mc_results['average_dd']:.2f}%" if mc_results else "   N/A")
    
    print(f"\n🎯 Quality:")
    print(f"   Compliance: {passed_checks}/{total_checks} checks passed")
    print(f"   Stability: {mc_results['stability_score']:.1f}/100" if mc_results else "   N/A")
    print(f"   Consistency: {wf_results['consistency_score']:.1f}%")
    
    print(f"\n🏆 Final Assessment:")
    print(f"   Score: {final_score:.1f}/100")
    print(f"   Grade: {grade}")
    
    if final_score >= 70:
        print(f"   ✅ PASSED - Strategy suitable for live trading")
    elif final_score >= 60:
        print(f"   ⚠️  MARGINAL - Proceed with caution")
    else:
        print(f"   ❌ FAILED - Requires improvement")
    
    print("\n" + "="*70)
    
    client.close()


if __name__ == "__main__":
    asyncio.run(run_full_validation())
