"""
Comprehensive Validation Pipeline for Anti-Chop Gradient Strategy

Compares:
1. anti_chop_strategy (original binary filtering)
2. anti_chop_gradient (new gradient position sizing)
3. adaptive_multi_signal (for reference)

Goal: Achieve PF > 1.5, DD < 6%, Consistency > 40% with stable trade frequency

Data: Latest 3-month Dukascopy dataset (EURUSD H1)
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
from anti_chop_strategy import run_anti_chop_strategy
from anti_chop_gradient import run_anti_chop_gradient_strategy
from adaptive_multi_signal import run_adaptive_multi_signal_strategy
from test_eurusd_strategy import calculate_metrics

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')


def calculate_consistency_score(trades: List, segments: int = 3) -> float:
    """
    Calculate consistency score by dividing trades into segments
    Returns percentage (0-100)
    """
    if len(trades) < segments * 3:
        return 0.0
    
    segment_size = len(trades) // segments
    segment_pnls = []
    
    for i in range(segments):
        start = i * segment_size
        end = (i + 1) * segment_size if i < segments - 1 else len(trades)
        segment_trades = trades[start:end]
        segment_pnl = sum(t.profit_loss for t in segment_trades)
        segment_pnls.append(segment_pnl)
    
    # Consistency: How many segments are profitable?
    profitable_segments = sum(1 for pnl in segment_pnls if pnl > 0)
    consistency = (profitable_segments / segments) * 100
    
    return consistency


def print_section_header(title: str):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)


def print_metrics_table(strategy_name: str, metrics: Dict, consistency: float):
    """Print formatted metrics table"""
    print(f"\n📊 {strategy_name} Performance:")
    print(f"{'Metric':<30} {'Value':<20} {'Target':<20} {'Status':<10}")
    print("-" * 80)
    
    metrics_to_show = [
        ("Total Trades", f"{metrics['total_trades']}", "30-50", 
         "✅" if 30 <= metrics['total_trades'] <= 50 else "⚠️"),
        ("Profit Factor", f"{metrics['profit_factor']:.2f}", "> 1.5",
         "✅" if metrics['profit_factor'] > 1.5 else "❌"),
        ("Max Drawdown %", f"{metrics['max_drawdown_pct']:.2f}%", "< 6%",
         "✅" if metrics['max_drawdown_pct'] < 6.0 else "❌"),
        ("Consistency %", f"{consistency:.1f}%", "> 40%",
         "✅" if consistency > 40 else "❌"),
        ("Net Profit", f"${metrics['total_pnl']:.2f}", "> 0",
         "✅" if metrics['total_pnl'] > 0 else "❌"),
        ("Win Rate %", f"{metrics['win_rate']:.1f}%", "> 50%",
         "✅" if metrics['win_rate'] > 50 else "⚠️"),
        ("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}", "> 1.0",
         "✅" if metrics['sharpe_ratio'] > 1.0 else "⚠️"),
        ("Avg Win/Loss Ratio", f"{metrics['avg_win'] / abs(metrics['avg_loss']):.2f}" if metrics['avg_loss'] != 0 else "N/A", "> 1.5",
         "✅" if metrics['avg_loss'] != 0 and (metrics['avg_win'] / abs(metrics['avg_loss'])) > 1.5 else "⚠️"),
    ]
    
    for metric_name, value, target, status in metrics_to_show:
        print(f"{metric_name:<30} {value:<20} {target:<20} {status:<10}")


def calculate_improvement_score(
    profit_factor: float,
    max_dd: float,
    consistency: float,
    total_trades: int
) -> float:
    """
    Calculate overall improvement score (0-100)
    
    Components:
    - Profitability: 30 points (PF > 1.5)
    - Risk Control: 30 points (DD < 6%)
    - Consistency: 30 points (> 40%)
    - Trade Frequency: 10 points (30-50 trades)
    """
    
    # Profitability score (0-30)
    if profit_factor >= 2.0:
        prof_score = 30
    elif profit_factor >= 1.5:
        prof_score = 20 + ((profit_factor - 1.5) / 0.5) * 10
    elif profit_factor >= 1.0:
        prof_score = ((profit_factor - 1.0) / 0.5) * 20
    else:
        prof_score = 0
    
    # Risk control score (0-30)
    if max_dd <= 3:
        risk_score = 30
    elif max_dd <= 6:
        risk_score = 20 + ((6 - max_dd) / 3) * 10
    elif max_dd <= 10:
        risk_score = ((10 - max_dd) / 4) * 20
    else:
        risk_score = 0
    
    # Consistency score (0-30)
    if consistency >= 60:
        cons_score = 30
    elif consistency >= 40:
        cons_score = 20 + ((consistency - 40) / 20) * 10
    elif consistency >= 20:
        cons_score = ((consistency - 20) / 20) * 20
    else:
        cons_score = 0
    
    # Trade frequency score (0-10)
    if 30 <= total_trades <= 50:
        freq_score = 10
    elif 20 <= total_trades < 30 or 50 < total_trades <= 70:
        freq_score = 7
    elif 10 <= total_trades < 20 or 70 < total_trades <= 100:
        freq_score = 5
    else:
        freq_score = 2
    
    total = prof_score + risk_score + cons_score + freq_score
    return min(100, max(0, total))


async def run_gradient_validation():
    """Run comprehensive validation comparing all three strategies"""
    
    print_section_header("ANTI-CHOP GRADIENT STRATEGY - COMPREHENSIVE VALIDATION")
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Load latest 3-month data
    print_section_header("DATA LOADING")
    
    print("\n📊 Loading EURUSD H1 data from MongoDB cache...")
    
    # Try to load from MongoDB cache directly
    from market_data_models import DataTimeframe
    
    # Get all available candles from cache
    candles = await market_data_service.get_candles(
        symbol="EURUSD",
        timeframe=DataTimeframe.H1,
        start_date=None,
        end_date=None,
        limit=10000
    )
    
    if not candles:
        print(f"❌ No cached data found in MongoDB.")
        print(f"   Run: python build_candle_cache.py")
        client.close()
        return
    
    # Filter to last 3 months
    three_months_ago = datetime.now() - timedelta(days=90)
    candles = [c for c in candles if c.timestamp >= three_months_ago]
    
    print(f"✅ Loaded {len(candles)} candles")
    print(f"   Period: {candles[0].timestamp.strftime('%Y-%m-%d')} to {candles[-1].timestamp.strftime('%Y-%m-%d')}")
    print(f"   Duration: {(candles[-1].timestamp - candles[0].timestamp).days} days")
    
    # Backtest configuration
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
    
    # Common parameters
    params = {
        "base_risk_pct": 0.7,
        "take_profit_atr_mult": 4.0,
        "stop_loss_atr_mult": 1.9,
        "min_confirmations": 2,
        "max_trades_per_day": 3,
        "require_confirmation": True,
    }
    
    # Results storage
    results = {}
    
    # ========================================================================
    # TEST 1: Original Anti-Chop Strategy (Binary Filtering)
    # ========================================================================
    print_section_header("TEST 1: ANTI-CHOP STRATEGY (BINARY FILTERING)")
    
    print("\n🚀 Running original anti-chop strategy...")
    anti_chop_trades, anti_chop_equity = run_anti_chop_strategy(candles, config, params)
    
    print(f"✅ Completed: {len(anti_chop_trades)} trades")
    
    anti_chop_metrics = calculate_metrics(anti_chop_trades, anti_chop_equity, config.initial_balance)
    anti_chop_consistency = calculate_consistency_score(anti_chop_trades, segments=3)
    
    print_metrics_table("Anti-Chop (Binary)", anti_chop_metrics, anti_chop_consistency)
    
    anti_chop_score = calculate_improvement_score(
        anti_chop_metrics['profit_factor'],
        anti_chop_metrics['max_drawdown_pct'],
        anti_chop_consistency,
        anti_chop_metrics['total_trades']
    )
    
    print(f"\n🏆 Overall Score: {anti_chop_score:.1f}/100")
    
    results['anti_chop'] = {
        'trades': len(anti_chop_trades),
        'metrics': anti_chop_metrics,
        'consistency': anti_chop_consistency,
        'score': anti_chop_score,
    }
    
    # ========================================================================
    # TEST 2: Anti-Chop Gradient Strategy (NEW)
    # ========================================================================
    print_section_header("TEST 2: ANTI-CHOP GRADIENT STRATEGY (GRADIENT POSITION SIZING)")
    
    print("\n🚀 Running gradient anti-chop strategy...")
    gradient_trades, gradient_equity = run_anti_chop_gradient_strategy(candles, config, params)
    
    print(f"✅ Completed: {len(gradient_trades)} trades")
    
    gradient_metrics = calculate_metrics(gradient_trades, gradient_equity, config.initial_balance)
    gradient_consistency = calculate_consistency_score(gradient_trades, segments=3)
    
    print_metrics_table("Anti-Chop Gradient", gradient_metrics, gradient_consistency)
    
    gradient_score = calculate_improvement_score(
        gradient_metrics['profit_factor'],
        gradient_metrics['max_drawdown_pct'],
        gradient_consistency,
        gradient_metrics['total_trades']
    )
    
    print(f"\n🏆 Overall Score: {gradient_score:.1f}/100")
    
    results['gradient'] = {
        'trades': len(gradient_trades),
        'metrics': gradient_metrics,
        'consistency': gradient_consistency,
        'score': gradient_score,
    }
    
    # ========================================================================
    # TEST 3: Adaptive Multi-Signal Strategy (Reference)
    # ========================================================================
    print_section_header("TEST 3: ADAPTIVE MULTI-SIGNAL STRATEGY (REFERENCE)")
    
    print("\n🚀 Running adaptive multi-signal strategy...")
    adaptive_trades, adaptive_equity = run_adaptive_multi_signal_strategy(candles, config, params)
    
    print(f"✅ Completed: {len(adaptive_trades)} trades")
    
    adaptive_metrics = calculate_metrics(adaptive_trades, adaptive_equity, config.initial_balance)
    adaptive_consistency = calculate_consistency_score(adaptive_trades, segments=3)
    
    print_metrics_table("Adaptive Multi-Signal", adaptive_metrics, adaptive_consistency)
    
    adaptive_score = calculate_improvement_score(
        adaptive_metrics['profit_factor'],
        adaptive_metrics['max_drawdown_pct'],
        adaptive_consistency,
        adaptive_metrics['total_trades']
    )
    
    print(f"\n🏆 Overall Score: {adaptive_score:.1f}/100")
    
    results['adaptive'] = {
        'trades': len(adaptive_trades),
        'metrics': adaptive_metrics,
        'consistency': adaptive_consistency,
        'score': adaptive_score,
    }
    
    # ========================================================================
    # COMPARISON ANALYSIS
    # ========================================================================
    print_section_header("COMPREHENSIVE COMPARISON")
    
    print(f"\n{'Strategy':<30} {'Trades':<10} {'PF':<10} {'DD%':<10} {'Cons%':<10} {'P&L':<15} {'Score':<10}")
    print("-" * 95)
    
    for name, display_name in [
        ('anti_chop', 'Anti-Chop (Binary)'),
        ('gradient', 'Anti-Chop Gradient ★'),
        ('adaptive', 'Adaptive Multi-Signal')
    ]:
        r = results[name]
        m = r['metrics']
        marker = " ★" if name == 'gradient' else ""
        print(f"{display_name:<30} {r['trades']:<10} {m['profit_factor']:<10.2f} "
              f"{m['max_drawdown_pct']:<10.2f} {r['consistency']:<10.1f} "
              f"${m['total_pnl']:<14.2f} {r['score']:<10.1f}")
    
    # Detailed Improvement Analysis
    print_section_header("GRADIENT vs BINARY - IMPROVEMENT ANALYSIS")
    
    improvements = {
        'Trades': (results['gradient']['trades'] - results['anti_chop']['trades'], 
                   results['anti_chop']['trades']),
        'Profit Factor': (results['gradient']['metrics']['profit_factor'] - results['anti_chop']['metrics']['profit_factor'],
                         results['anti_chop']['metrics']['profit_factor']),
        'Max DD %': (results['gradient']['metrics']['max_drawdown_pct'] - results['anti_chop']['metrics']['max_drawdown_pct'],
                    results['anti_chop']['metrics']['max_drawdown_pct']),
        'Consistency %': (results['gradient']['consistency'] - results['anti_chop']['consistency'],
                         results['anti_chop']['consistency']),
        'Net P&L': (results['gradient']['metrics']['total_pnl'] - results['anti_chop']['metrics']['total_pnl'],
                   results['anti_chop']['metrics']['total_pnl']),
        'Win Rate %': (results['gradient']['metrics']['win_rate'] - results['anti_chop']['metrics']['win_rate'],
                      results['anti_chop']['metrics']['win_rate']),
        'Overall Score': (results['gradient']['score'] - results['anti_chop']['score'],
                         results['anti_chop']['score']),
    }
    
    print(f"\n{'Metric':<25} {'Change':<20} {'% Change':<15} {'Status':<10}")
    print("-" * 70)
    
    for metric, (change, baseline) in improvements.items():
        pct_change = (change / baseline * 100) if baseline != 0 else 0
        
        # Determine status (for DD, lower is better)
        if metric == 'Max DD %':
            status = "✅" if change < 0 else "❌" if change > 0 else "⚠️"
        else:
            status = "✅" if change > 0 else "❌" if change < 0 else "⚠️"
        
        print(f"{metric:<25} {change:+.2f}{'':<14} {pct_change:+.1f}%{'':<9} {status:<10}")
    
    # ========================================================================
    # GOAL ACHIEVEMENT CHECK
    # ========================================================================
    print_section_header("GOAL ACHIEVEMENT ANALYSIS")
    
    gradient_m = results['gradient']['metrics']
    gradient_c = results['gradient']['consistency']
    
    goals = {
        'Profit Factor > 1.5': (gradient_m['profit_factor'] > 1.5, gradient_m['profit_factor'], "1.5"),
        'Max Drawdown < 6%': (gradient_m['max_drawdown_pct'] < 6.0, gradient_m['max_drawdown_pct'], "6.0%"),
        'Consistency > 40%': (gradient_c > 40, gradient_c, "40%"),
        'Trades 30-50': (30 <= results['gradient']['trades'] <= 50, results['gradient']['trades'], "30-50"),
    }
    
    print(f"\n{'Goal':<30} {'Achieved':<15} {'Actual':<20} {'Target':<15}")
    print("-" * 80)
    
    goals_met = 0
    for goal, (achieved, actual, target) in goals.items():
        status = "✅ YES" if achieved else "❌ NO"
        if achieved:
            goals_met += 1
        
        if isinstance(actual, float):
            actual_str = f"{actual:.2f}"
        else:
            actual_str = str(actual)
        
        print(f"{goal:<30} {status:<15} {actual_str:<20} {target:<15}")
    
    print(f"\n📊 Goals Achieved: {goals_met}/4 ({goals_met/4*100:.0f}%)")
    
    # ========================================================================
    # FINAL VERDICT
    # ========================================================================
    print_section_header("FINAL VERDICT & RECOMMENDATION")
    
    print(f"\n🎯 **GRADIENT STRATEGY PERFORMANCE**")
    print(f"   Overall Score: {results['gradient']['score']:.1f}/100")
    
    if results['gradient']['score'] >= 75:
        grade = "A (Excellent)"
        verdict = "✅ READY FOR PAPER TRADING"
    elif results['gradient']['score'] >= 60:
        grade = "B (Good)"
        verdict = "⚠️  GOOD PROGRESS - Consider minor refinements"
    elif results['gradient']['score'] >= 50:
        grade = "C (Acceptable)"
        verdict = "⚠️  NEEDS IMPROVEMENT"
    else:
        grade = "D/F (Poor)"
        verdict = "❌ REQUIRES SIGNIFICANT WORK"
    
    print(f"   Grade: {grade}")
    print(f"   Verdict: {verdict}")
    
    print(f"\n💡 **KEY INSIGHTS**")
    
    # Compare gradient vs binary
    if results['gradient']['score'] > results['anti_chop']['score']:
        improvement_pct = ((results['gradient']['score'] - results['anti_chop']['score']) / 
                          results['anti_chop']['score'] * 100)
        print(f"   ✅ Gradient approach improved overall score by {improvement_pct:.1f}%")
    else:
        print(f"   ❌ Gradient approach did not improve overall score")
    
    if results['gradient']['trades'] > results['anti_chop']['trades']:
        print(f"   ✅ Gradient strategy generated {results['gradient']['trades'] - results['anti_chop']['trades']} more trades")
    
    if results['gradient']['consistency'] > results['anti_chop']['consistency']:
        print(f"   ✅ Consistency improved by {results['gradient']['consistency'] - results['anti_chop']['consistency']:.1f}%")
    
    if gradient_m['profit_factor'] > 1.5:
        print(f"   ✅ Profit factor target achieved ({gradient_m['profit_factor']:.2f} > 1.5)")
    else:
        print(f"   ⚠️  Profit factor below target ({gradient_m['profit_factor']:.2f} < 1.5)")
    
    print(f"\n📋 **NEXT STEPS**")
    
    if goals_met >= 3:
        print(f"   1. ✅ Proceed to extended backtesting (6+ months)")
        print(f"   2. ✅ Run Monte Carlo simulation for robustness")
        print(f"   3. ✅ Deploy to paper trading environment")
    elif goals_met >= 2:
        print(f"   1. ⚠️  Analyze failed goals and adjust parameters")
        print(f"   2. ⚠️  Test on different market conditions")
        print(f"   3. ⚠️  Consider hybrid approach (gradient + additional filters)")
    else:
        print(f"   1. ❌ Review gradient thresholds and multipliers")
        print(f"   2. ❌ Analyze losing trades for patterns")
        print(f"   3. ❌ Consider alternative position sizing approaches")
    
    print("\n" + "=" * 80)
    
    client.close()


if __name__ == "__main__":
    asyncio.run(run_gradient_validation())
