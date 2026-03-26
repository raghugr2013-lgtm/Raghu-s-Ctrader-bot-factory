"""
FULL VALIDATION PHASE - Anti-Chop Gradient Enhanced Strategy

Comprehensive validation on 15-month dataset (Jan 2025 - Mar 2026)

Tests:
1. Extended Backtest (full period)
2. Walk-Forward Analysis (rolling windows)
3. Monte Carlo Simulation (1000+ runs)
4. Trade Distribution Analysis
5. Regime Analysis (trending/choppy/volatile)

Goal: Confirm strategy robustness for live deployment
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
from typing import List, Dict, Tuple
from collections import defaultdict

from market_data_service import init_market_data_service
from market_data_models import DataTimeframe
from backtest_models import BacktestConfig, Timeframe, TradeRecord
from anti_chop_gradient_enhanced import run_anti_chop_gradient_enhanced_strategy
from test_eurusd_strategy import calculate_metrics
from validate_gradient_strategy import calculate_consistency_score, calculate_improvement_score

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')


def print_header(title: str, char: str = "="):
    """Print formatted header"""
    print(f"\n{char * 100}")
    print(f"{title.center(100)}")
    print(f"{char * 100}")


def monte_carlo_simulation(trades: List[TradeRecord], num_simulations: int = 1000) -> Dict:
    """
    Monte Carlo simulation by shuffling trade sequence
    
    Returns statistics on worst-case scenarios and stability
    """
    if len(trades) < 10:
        return {"error": "Insufficient trades for Monte Carlo"}
    
    returns = [t.profit_loss for t in trades]
    initial_balance = 10000.0
    
    simulation_results = []
    
    for _ in range(num_simulations):
        # Randomly shuffle trade sequence
        sampled_returns = np.random.choice(returns, size=len(returns), replace=True)
        
        # Calculate equity curve
        equity = initial_balance
        peak = equity
        max_dd = 0
        max_dd_pct = 0
        
        for ret in sampled_returns:
            equity += ret
            if equity > peak:
                peak = equity
            dd = peak - equity
            dd_pct = (dd / peak * 100) if peak > 0 else 0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                max_dd = dd
        
        final_return = equity - initial_balance
        
        simulation_results.append({
            "final_equity": equity,
            "total_return": final_return,
            "max_dd": max_dd,
            "max_dd_pct": max_dd_pct,
        })
    
    # Calculate statistics
    returns_list = [s["total_return"] for s in simulation_results]
    dd_list = [s["max_dd_pct"] for s in simulation_results]
    
    # Percentiles
    return {
        "num_simulations": num_simulations,
        "avg_return": np.mean(returns_list),
        "median_return": np.median(returns_list),
        "std_return": np.std(returns_list),
        "worst_return": np.percentile(returns_list, 5),  # 5th percentile
        "best_return": np.percentile(returns_list, 95),  # 95th percentile
        "profitable_pct": sum(1 for r in returns_list if r > 0) / len(returns_list) * 100,
        "avg_dd": np.mean(dd_list),
        "median_dd": np.median(dd_list),
        "worst_dd": np.percentile(dd_list, 95),  # 95th percentile worst DD
        "best_dd": np.percentile(dd_list, 5),    # 5th percentile best DD
        "stability_score": (sum(1 for r in returns_list if r > 0) / len(returns_list)) * (1 - np.mean(dd_list) / 100) * 100,
    }


def walk_forward_analysis(candles: List, config: BacktestConfig, params: Dict, segment_months: int = 3) -> Dict:
    """
    Walk-forward analysis: Split into time-based segments
    
    Returns performance across each segment
    """
    from market_data_models import Candle
    
    # Calculate segment boundaries
    start_date = candles[0].timestamp
    end_date = candles[-1].timestamp
    
    total_days = (end_date - start_date).days
    segment_days = segment_months * 30
    
    segments = []
    current_start = start_date
    
    while current_start < end_date:
        current_end = current_start + timedelta(days=segment_days)
        if current_end > end_date:
            current_end = end_date
        
        segment_candles = [c for c in candles if current_start <= c.timestamp < current_end]
        
        if len(segment_candles) > 100:  # Minimum candles for valid test
            segments.append({
                "name": f"{current_start.strftime('%b %Y')} - {current_end.strftime('%b %Y')}",
                "start": current_start,
                "end": current_end,
                "candles": segment_candles
            })
        
        current_start = current_end
    
    results = []
    
    for seg in segments:
        # Create config for this segment
        seg_config = BacktestConfig(
            symbol=config.symbol,
            timeframe=config.timeframe,
            start_date=seg["start"],
            end_date=seg["end"],
            initial_balance=config.initial_balance,
            spread_pips=config.spread_pips,
            commission_per_lot=config.commission_per_lot,
            leverage=config.leverage,
        )
        
        trades, equity_curve = run_anti_chop_gradient_enhanced_strategy(seg["candles"], seg_config, params)
        metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
        
        results.append({
            "segment": seg["name"],
            "start": seg["start"],
            "end": seg["end"],
            "candles": len(seg["candles"]),
            "trades": len(trades),
            "profit_factor": metrics["profit_factor"],
            "total_pnl": metrics["total_pnl"],
            "max_dd_pct": metrics["max_drawdown_pct"],
            "win_rate": metrics["win_rate"],
            "sharpe": metrics["sharpe_ratio"],
        })
    
    # Calculate consistency
    profitable_segments = sum(1 for r in results if r["total_pnl"] > 0)
    consistency = (profitable_segments / len(results) * 100) if results else 0
    
    # Calculate PF consistency
    pfs = [r["profit_factor"] for r in results if r["profit_factor"] > 0]
    pf_consistency = (min(pfs) / max(pfs) * 100) if pfs and len(pfs) > 1 else 0
    
    return {
        "segments": results,
        "consistency_pct": consistency,
        "pf_consistency": pf_consistency,
        "profitable_segments": profitable_segments,
        "total_segments": len(results),
    }


def analyze_trade_distribution(trades: List[TradeRecord]) -> Dict:
    """
    Analyze trade P&L distribution
    Check if performance depends on few large winners
    """
    if not trades:
        return {"error": "No trades"}
    
    pnls = [t.profit_loss for t in trades]
    pnls.sort(reverse=True)
    
    total_pnl = sum(pnls)
    
    # Top N% contribution
    top_5_pnl = sum(pnls[:max(1, len(pnls) // 20)]) if len(pnls) >= 20 else sum(pnls[:1])
    top_10_pnl = sum(pnls[:max(1, len(pnls) // 10)]) if len(pnls) >= 10 else sum(pnls[:2])
    top_20_pnl = sum(pnls[:max(1, len(pnls) // 5)]) if len(pnls) >= 5 else sum(pnls[:3])
    
    top_5_pct = (top_5_pnl / total_pnl * 100) if total_pnl > 0 else 0
    top_10_pct = (top_10_pnl / total_pnl * 100) if total_pnl > 0 else 0
    top_20_pct = (top_20_pnl / total_pnl * 100) if total_pnl > 0 else 0
    
    # Outlier detection (trades > 2 std dev from mean)
    mean_pnl = np.mean(pnls)
    std_pnl = np.std(pnls)
    outliers_positive = [p for p in pnls if p > mean_pnl + 2 * std_pnl]
    outliers_negative = [p for p in pnls if p < mean_pnl - 2 * std_pnl]
    
    return {
        "total_trades": len(trades),
        "total_pnl": total_pnl,
        "mean_pnl": mean_pnl,
        "median_pnl": np.median(pnls),
        "std_pnl": std_pnl,
        "top_5_contribution_pct": top_5_pct,
        "top_10_contribution_pct": top_10_pct,
        "top_20_contribution_pct": top_20_pct,
        "outliers_positive": len(outliers_positive),
        "outliers_negative": len(outliers_negative),
        "largest_win": max(pnls),
        "largest_loss": min(pnls),
    }


def analyze_market_regimes(candles: List, trades: List[TradeRecord]) -> Dict:
    """
    Analyze performance across different market regimes
    """
    from no_trade_zone_strategy import calculate_adx
    from improved_eurusd_strategy import calculate_atr
    
    # Calculate regime indicators for all candles
    adx = calculate_adx(candles, 14)
    atr = calculate_atr(candles, 14)
    
    # Calculate ATR percentile for volatility classification
    valid_atr = [a for a in atr if a is not None]
    if not valid_atr:
        return {"error": "No valid ATR data"}
    
    atr_33 = np.percentile(valid_atr, 33)
    atr_66 = np.percentile(valid_atr, 66)
    
    # Classify trades by regime
    regime_stats = defaultdict(lambda: {"trades": 0, "pnl": 0, "wins": 0, "losses": 0})
    
    for trade in trades:
        # Find candle index for entry
        entry_idx = None
        for i, candle in enumerate(candles):
            if candle.timestamp == trade.entry_time:
                entry_idx = i
                break
        
        if entry_idx is None or adx[entry_idx] is None or atr[entry_idx] is None:
            continue
        
        # Classify trend (ADX-based)
        if adx[entry_idx] >= 25:
            trend = "trending"
        elif adx[entry_idx] >= 20:
            trend = "moderate"
        else:
            trend = "choppy"
        
        # Classify volatility (ATR-based)
        if atr[entry_idx] >= atr_66:
            volatility = "high_vol"
        elif atr[entry_idx] >= atr_33:
            volatility = "medium_vol"
        else:
            volatility = "low_vol"
        
        regime = f"{trend}_{volatility}"
        
        regime_stats[regime]["trades"] += 1
        regime_stats[regime]["pnl"] += trade.profit_loss
        if trade.profit_loss > 0:
            regime_stats[regime]["wins"] += 1
        else:
            regime_stats[regime]["losses"] += 1
    
    # Calculate metrics per regime
    results = {}
    for regime, stats in regime_stats.items():
        win_rate = (stats["wins"] / stats["trades"] * 100) if stats["trades"] > 0 else 0
        avg_pnl = stats["pnl"] / stats["trades"] if stats["trades"] > 0 else 0
        
        results[regime] = {
            "trades": stats["trades"],
            "total_pnl": stats["pnl"],
            "avg_pnl": avg_pnl,
            "win_rate": win_rate,
            "wins": stats["wins"],
            "losses": stats["losses"],
        }
    
    return results


async def run_full_validation():
    """Run comprehensive validation phase"""
    
    print_header("FULL VALIDATION PHASE - ANTI-CHOP GRADIENT ENHANCED", "=")
    print(f"Dataset: 15 months (Jan 2025 - Mar 2026)")
    print(f"Strategy: Enhanced with Entry Quality Improvements")
    
    # Connect
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # ========================================================================
    # PHASE 1: LOAD FULL 15-MONTH DATASET
    # ========================================================================
    print_header("PHASE 1: DATA LOADING", "-")
    
    print("\n📊 Loading full EURUSD H1 dataset...")
    
    candles = await market_data_service.get_candles(
        symbol="EURUSD",
        timeframe=DataTimeframe.H1,
        start_date=None,
        end_date=None,
        limit=20000  # Load all available data
    )
    
    if not candles:
        print("❌ No data found")
        client.close()
        return
    
    print(f"✅ Loaded {len(candles)} candles")
    print(f"   Period: {candles[0].timestamp.strftime('%Y-%m-%d')} to {candles[-1].timestamp.strftime('%Y-%m-%d')}")
    print(f"   Duration: {(candles[-1].timestamp - candles[0].timestamp).days} days ({(candles[-1].timestamp - candles[0].timestamp).days / 30:.1f} months)")
    
    # ========================================================================
    # PHASE 2: EXTENDED BACKTEST (FULL 15 MONTHS)
    # ========================================================================
    print_header("PHASE 2: EXTENDED BACKTEST (FULL 15 MONTHS)", "-")
    
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
    
    # Optimal parameters from 3-month tuning
    params = {
        "base_risk_pct": 0.7,
        "stop_loss_atr_mult": 1.9,
        "take_profit_atr_mult": 4.8,
        "min_confirmations": 2,
        "max_trades_per_day": 3,
        "gradient_full_threshold": 32,
        "gradient_high_threshold": 47,
        "gradient_medium_threshold": 62,
        "override_adx_threshold": 29,
        # Enhanced quality settings
        "enable_quality_filter": True,
        "min_quality_score": 45,
        "min_pullback_quality": 30,
        "require_rsi_momentum_alignment": True,
        "require_positive_ema_slope": True,
    }
    
    print("\n🚀 Running full 15-month backtest...")
    full_trades, full_equity = run_anti_chop_gradient_enhanced_strategy(candles, config, params)
    
    print(f"✅ Backtest complete: {len(full_trades)} trades")
    
    full_metrics = calculate_metrics(full_trades, full_equity, config.initial_balance)
    full_consistency = calculate_consistency_score(full_trades, segments=5)  # 5 segments for 15 months
    full_score = calculate_improvement_score(
        full_metrics['profit_factor'],
        full_metrics['max_drawdown_pct'],
        full_consistency,
        full_metrics['total_trades']
    )
    
    print(f"\n📊 15-Month Performance:")
    print(f"{'Metric':<30} {'Value':<20} {'Status':<10}")
    print("-" * 60)
    print(f"{'Total Trades':<30} {full_metrics['total_trades']:<20} ")
    print(f"{'Profit Factor':<30} {full_metrics['profit_factor']:<20.2f} {'✅' if full_metrics['profit_factor'] > 1.5 else '❌'}")
    print(f"{'Max Drawdown %':<30} {full_metrics['max_drawdown_pct']:<20.2f} {'✅' if full_metrics['max_drawdown_pct'] < 6.0 else '❌'}")
    print(f"{'Consistency %':<30} {full_consistency:<20.1f} {'✅' if full_consistency > 50 else '❌'}")
    print(f"{'Net Profit $':<30} {full_metrics['total_pnl']:<20.2f} {'✅' if full_metrics['total_pnl'] > 0 else '❌'}")
    print(f"{'Win Rate %':<30} {full_metrics['win_rate']:<20.1f} ")
    print(f"{'Sharpe Ratio':<30} {full_metrics['sharpe_ratio']:<20.2f} ")
    print(f"{'Overall Score':<30} {full_score:<20.1f} ")
    
    # Compare with 3-month result
    print(f"\n📊 Comparison: 15-Month vs 3-Month (Dec-Mar)")
    print(f"{'Metric':<30} {'3-Month':<15} {'15-Month':<15} {'Difference':<15}")
    print("-" * 75)
    
    # 3-month reference values
    ref_3m = {
        "trades": 19,
        "pf": 2.23,
        "dd": 2.31,
        "consistency": 100.0,
        "pnl": 718.56,
        "win_rate": 47.4,
    }
    
    print(f"{'Trades':<30} {ref_3m['trades']:<15} {full_metrics['total_trades']:<15} {full_metrics['total_trades'] - ref_3m['trades']:+}")
    print(f"{'Profit Factor':<30} {ref_3m['pf']:<15.2f} {full_metrics['profit_factor']:<15.2f} {full_metrics['profit_factor'] - ref_3m['pf']:+.2f}")
    print(f"{'Max DD %':<30} {ref_3m['dd']:<15.2f} {full_metrics['max_drawdown_pct']:<15.2f} {full_metrics['max_drawdown_pct'] - ref_3m['dd']:+.2f}")
    print(f"{'Consistency %':<30} {ref_3m['consistency']:<15.1f} {full_consistency:<15.1f} {full_consistency - ref_3m['consistency']:+.1f}")
    print(f"{'Net P&L $':<30} {ref_3m['pnl']:<15.2f} {full_metrics['total_pnl']:<15.2f} {full_metrics['total_pnl'] - ref_3m['pnl']:+.2f}")
    print(f"{'Win Rate %':<30} {ref_3m['win_rate']:<15.1f} {full_metrics['win_rate']:<15.1f} {full_metrics['win_rate'] - ref_3m['win_rate']:+.1f}")
    
    # ========================================================================
    # PHASE 3: WALK-FORWARD ANALYSIS
    # ========================================================================
    print_header("PHASE 3: WALK-FORWARD ANALYSIS", "-")
    
    print("\n🔄 Running walk-forward analysis (3-month segments)...")
    wf_results = walk_forward_analysis(candles, config, params, segment_months=3)
    
    print(f"\n✅ Walk-forward complete: {wf_results['total_segments']} segments")
    print(f"   Profitable segments: {wf_results['profitable_segments']}/{wf_results['total_segments']}")
    print(f"   Consistency: {wf_results['consistency_pct']:.1f}%")
    print(f"   PF Consistency: {wf_results['pf_consistency']:.1f}%")
    
    print(f"\n{'Segment':<25} {'Trades':<10} {'PF':<10} {'DD%':<10} {'P&L':<15} {'Status':<10}")
    print("-" * 80)
    
    for seg in wf_results['segments']:
        status = "✅" if seg['total_pnl'] > 0 else "❌"
        print(f"{seg['segment']:<25} {seg['trades']:<10} {seg['profit_factor']:<10.2f} "
              f"{seg['max_dd_pct']:<10.2f} ${seg['total_pnl']:<14.2f} {status:<10}")
    
    # ========================================================================
    # PHASE 4: MONTE CARLO SIMULATION
    # ========================================================================
    print_header("PHASE 4: MONTE CARLO SIMULATION (1000 RUNS)", "-")
    
    print("\n🎲 Running Monte Carlo simulation...")
    mc_results = monte_carlo_simulation(full_trades, num_simulations=1000)
    
    print(f"\n✅ Monte Carlo complete: {mc_results['num_simulations']} simulations")
    
    print(f"\n{'Metric':<30} {'Value':<20}")
    print("-" * 50)
    print(f"{'Average Return':<30} ${mc_results['avg_return']:<20.2f}")
    print(f"{'Median Return':<30} ${mc_results['median_return']:<20.2f}")
    print(f"{'Std Deviation':<30} ${mc_results['std_return']:<20.2f}")
    print(f"{'Worst Case (5th %ile)':<30} ${mc_results['worst_return']:<20.2f}")
    print(f"{'Best Case (95th %ile)':<30} ${mc_results['best_return']:<20.2f}")
    print(f"{'Profitable %':<30} {mc_results['profitable_pct']:<20.1f}%")
    print(f"{'Average DD':<30} {mc_results['avg_dd']:<20.2f}%")
    print(f"{'Median DD':<30} {mc_results['median_dd']:<20.2f}%")
    print(f"{'Worst DD (95th %ile)':<30} {mc_results['worst_dd']:<20.2f}%")
    print(f"{'Best DD (5th %ile)':<30} {mc_results['best_dd']:<20.2f}%")
    print(f"{'Stability Score':<30} {mc_results['stability_score']:<20.1f}/100")
    
    # Risk assessment
    print(f"\n⚠️  Risk Assessment:")
    if mc_results['worst_dd'] < 10:
        print(f"   ✅ Worst-case DD acceptable ({mc_results['worst_dd']:.2f}% < 10%)")
    else:
        print(f"   ❌ WARNING: Worst-case DD high ({mc_results['worst_dd']:.2f}% > 10%)")
    
    if mc_results['profitable_pct'] > 90:
        print(f"   ✅ High probability of profitability ({mc_results['profitable_pct']:.1f}%)")
    elif mc_results['profitable_pct'] > 75:
        print(f"   ⚠️  Good probability of profitability ({mc_results['profitable_pct']:.1f}%)")
    else:
        print(f"   ❌ WARNING: Lower probability of profitability ({mc_results['profitable_pct']:.1f}%)")
    
    # ========================================================================
    # PHASE 5: TRADE DISTRIBUTION ANALYSIS
    # ========================================================================
    print_header("PHASE 5: TRADE DISTRIBUTION ANALYSIS", "-")
    
    print("\n📊 Analyzing trade P&L distribution...")
    dist_results = analyze_trade_distribution(full_trades)
    
    print(f"\n{'Metric':<40} {'Value':<20}")
    print("-" * 60)
    print(f"{'Total Trades':<40} {dist_results['total_trades']:<20}")
    print(f"{'Mean P&L':<40} ${dist_results['mean_pnl']:<20.2f}")
    print(f"{'Median P&L':<40} ${dist_results['median_pnl']:<20.2f}")
    print(f"{'Std Deviation':<40} ${dist_results['std_pnl']:<20.2f}")
    print(f"{'Top 5% Contribution':<40} {dist_results['top_5_contribution_pct']:<20.1f}%")
    print(f"{'Top 10% Contribution':<40} {dist_results['top_10_contribution_pct']:<20.1f}%")
    print(f"{'Top 20% Contribution':<40} {dist_results['top_20_contribution_pct']:<20.1f}%")
    print(f"{'Positive Outliers (>2σ)':<40} {dist_results['outliers_positive']:<20}")
    print(f"{'Negative Outliers (<-2σ)':<40} {dist_results['outliers_negative']:<20}")
    print(f"{'Largest Win':<40} ${dist_results['largest_win']:<20.2f}")
    print(f"{'Largest Loss':<40} ${dist_results['largest_loss']:<20.2f}")
    
    # Dependency assessment
    print(f"\n📈 Dependency Assessment:")
    if dist_results['top_20_contribution_pct'] < 50:
        print(f"   ✅ Performance well-distributed (top 20% = {dist_results['top_20_contribution_pct']:.1f}%)")
    elif dist_results['top_20_contribution_pct'] < 70:
        print(f"   ⚠️  Moderate concentration (top 20% = {dist_results['top_20_contribution_pct']:.1f}%)")
    else:
        print(f"   ❌ WARNING: High dependency on few trades (top 20% = {dist_results['top_20_contribution_pct']:.1f}%)")
    
    # ========================================================================
    # PHASE 6: REGIME ANALYSIS
    # ========================================================================
    print_header("PHASE 6: MARKET REGIME ANALYSIS", "-")
    
    print("\n📊 Analyzing performance across market regimes...")
    regime_results = analyze_market_regimes(candles, full_trades)
    
    if "error" not in regime_results:
        print(f"\n{'Regime':<25} {'Trades':<10} {'Win%':<10} {'Avg P&L':<15} {'Total P&L':<15}")
        print("-" * 75)
        
        for regime, stats in sorted(regime_results.items(), key=lambda x: x[1]['trades'], reverse=True):
            print(f"{regime:<25} {stats['trades']:<10} {stats['win_rate']:<10.1f} "
                  f"${stats['avg_pnl']:<14.2f} ${stats['total_pnl']:<14.2f}")
        
        # Regime strength assessment
        print(f"\n💡 Regime Insights:")
        
        trending_pnl = sum(v['total_pnl'] for k, v in regime_results.items() if 'trending' in k)
        choppy_pnl = sum(v['total_pnl'] for k, v in regime_results.items() if 'choppy' in k)
        
        if trending_pnl > 0 and choppy_pnl > 0:
            print(f"   ✅ Strategy profitable in both trending AND choppy markets")
        elif trending_pnl > 0:
            print(f"   ⚠️  Strategy primarily profitable in trending markets")
        elif choppy_pnl > 0:
            print(f"   ⚠️  Strategy primarily profitable in choppy markets")
        else:
            print(f"   ❌ WARNING: Strategy struggling in all market regimes")
    
    # ========================================================================
    # PHASE 7: FINAL ASSESSMENT
    # ========================================================================
    print_header("PHASE 7: FINAL VALIDATION ASSESSMENT", "=")
    
    print(f"\n🎯 **VALIDATION CRITERIA CHECK**")
    
    validation_checks = {
        "Profit Factor > 1.5": (full_metrics['profit_factor'] > 1.5, full_metrics['profit_factor'], "1.5"),
        "Max Drawdown < 6%": (full_metrics['max_drawdown_pct'] < 6.0, full_metrics['max_drawdown_pct'], "6%"),
        "Consistency > 50%": (full_consistency > 50, full_consistency, "50%"),
        "MC Worst DD < 10%": (mc_results['worst_dd'] < 10, mc_results['worst_dd'], "10%"),
        "MC Profitable > 75%": (mc_results['profitable_pct'] > 75, mc_results['profitable_pct'], "75%"),
        "WF Consistency > 60%": (wf_results['consistency_pct'] > 60, wf_results['consistency_pct'], "60%"),
        "Top 20% < 60% of P&L": (dist_results['top_20_contribution_pct'] < 60, dist_results['top_20_contribution_pct'], "60%"),
    }
    
    print(f"\n{'Criterion':<30} {'Status':<10} {'Actual':<20} {'Target':<15}")
    print("-" * 75)
    
    checks_passed = 0
    for criterion, (passed, actual, target) in validation_checks.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        if passed:
            checks_passed += 1
        
        if isinstance(actual, float):
            actual_str = f"{actual:.2f}"
        else:
            actual_str = str(actual)
        
        print(f"{criterion:<30} {status:<10} {actual_str:<20} {target:<15}")
    
    print(f"\n📊 Validation Score: {checks_passed}/{len(validation_checks)} ({checks_passed/len(validation_checks)*100:.0f}%)")
    
    # Deployment recommendation
    print(f"\n{'=' * 100}")
    print("DEPLOYMENT RECOMMENDATION")
    print(f"{'=' * 100}")
    
    if checks_passed >= 6:
        grade = "A - EXCELLENT"
        recommendation = "✅ APPROVED FOR LIVE DEPLOYMENT"
        next_steps = [
            "1. Deploy to paper trading (30 days)",
            "2. Monitor daily performance",
            "3. Gradual capital allocation (start 10% of target)",
            "4. Full deployment after 30-day validation"
        ]
    elif checks_passed >= 5:
        grade = "B - GOOD"
        recommendation = "⚠️  APPROVED WITH CAUTION - Extended paper trading recommended"
        next_steps = [
            "1. Extended paper trading (60 days)",
            "2. Monitor failed validation criteria closely",
            "3. Consider parameter refinement",
            "4. Conservative capital allocation"
        ]
    elif checks_passed >= 4:
        grade = "C - ACCEPTABLE"
        recommendation = "⚠️  PAPER TRADING ONLY - Further optimization needed"
        next_steps = [
            "1. Paper trading mandatory (90+ days)",
            "2. Analyze failure points",
            "3. Parameter re-optimization",
            "4. Re-validate before live deployment"
        ]
    else:
        grade = "D/F - INSUFFICIENT"
        recommendation = "❌ NOT APPROVED - Significant improvements required"
        next_steps = [
            "1. Do NOT deploy to live",
            "2. Review failed validation criteria",
            "3. Consider strategy redesign",
            "4. Test on different time periods"
        ]
    
    print(f"\n🎯 Grade: {grade}")
    print(f"🎯 Recommendation: {recommendation}")
    
    print(f"\n📋 Next Steps:")
    for step in next_steps:
        print(f"   {step}")
    
    # Risk warnings
    print(f"\n⚠️  Risk Warnings:")
    warnings = []
    
    if full_metrics['profit_factor'] < 1.5:
        warnings.append(f"Profit Factor ({full_metrics['profit_factor']:.2f}) below target (1.5)")
    
    if mc_results['worst_dd'] > 8:
        warnings.append(f"Monte Carlo worst-case DD high ({mc_results['worst_dd']:.2f}%)")
    
    if dist_results['top_20_contribution_pct'] > 60:
        warnings.append(f"Performance concentrated in top trades ({dist_results['top_20_contribution_pct']:.1f}%)")
    
    if wf_results['consistency_pct'] < 60:
        warnings.append(f"Walk-forward consistency low ({wf_results['consistency_pct']:.1f}%)")
    
    if warnings:
        for warning in warnings:
            print(f"   ⚠️  {warning}")
    else:
        print(f"   ✅ No significant risk warnings")
    
    print(f"\n{'=' * 100}")
    print(f"VALIDATION COMPLETE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 100}")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(run_full_validation())
