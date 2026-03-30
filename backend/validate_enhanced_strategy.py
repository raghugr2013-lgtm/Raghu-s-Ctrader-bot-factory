"""
Validation for Anti-Chop Gradient ENHANCED Strategy

Compares:
1. Original Gradient (baseline)
2. Enhanced Gradient (entry quality focus)

Goal: Achieve PF > 1.5 through better entries, not more filtering
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import datetime, timedelta

from market_data_service import init_market_data_service
from market_data_models import DataTimeframe
from backtest_models import BacktestConfig, Timeframe
from anti_chop_gradient import run_anti_chop_gradient_strategy
from anti_chop_gradient_enhanced import run_anti_chop_gradient_enhanced_strategy
from test_eurusd_strategy import calculate_metrics
from validate_gradient_strategy import (
    calculate_consistency_score,
    calculate_improvement_score,
    print_section_header,
    print_metrics_table
)

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')


async def run_enhanced_validation():
    """Validate enhanced strategy against gradient baseline"""
    
    print_section_header("ANTI-CHOP ENHANCED - ENTRY QUALITY VALIDATION")
    
    # Connect
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Load data
    print_section_header("DATA LOADING")
    print("\n📊 Loading EURUSD H1 data from MongoDB cache...")
    
    candles = await market_data_service.get_candles(
        symbol="EURUSD",
        timeframe=DataTimeframe.H1,
        start_date=None,
        end_date=None,
        limit=10000
    )
    
    if not candles:
        print("❌ No cached data found")
        client.close()
        return
    
    # Filter to last 3 months
    three_months_ago = datetime.now() - timedelta(days=90)
    candles = [c for c in candles if c.timestamp >= three_months_ago]
    
    print(f"✅ Loaded {len(candles)} candles")
    print(f"   Period: {candles[0].timestamp.strftime('%Y-%m-%d')} to {candles[-1].timestamp.strftime('%Y-%m-%d')}")
    print(f"   Duration: {(candles[-1].timestamp - candles[0].timestamp).days} days")
    
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
    
    # Parameters - optimized from previous run
    params = {
        "base_risk_pct": 0.7,
        "stop_loss_atr_mult": 1.9,
        "min_confirmations": 2,
        "max_trades_per_day": 3,
        "require_confirmation": True,
        "min_position_floor": 0.5,
        "enable_strong_signal_override": True,
        "override_min_signals": 3,
        "gradient_full_threshold": 32,
        "gradient_high_threshold": 47,
        "gradient_medium_threshold": 62,
        "override_adx_threshold": 29,
    }
    
    results = {}
    
    # ========================================================================
    # TEST 1: Gradient Strategy (Baseline - Optimized)
    # ========================================================================
    print_section_header("TEST 1: GRADIENT STRATEGY (BASELINE - OPTIMIZED)")
    
    print("\n🚀 Running gradient strategy...")
    gradient_params = {**params, "take_profit_atr_mult": 4.3}
    gradient_trades, gradient_equity = run_anti_chop_gradient_strategy(candles, config, gradient_params)
    
    print(f"✅ Completed: {len(gradient_trades)} trades")
    
    gradient_metrics = calculate_metrics(gradient_trades, gradient_equity, config.initial_balance)
    gradient_consistency = calculate_consistency_score(gradient_trades, segments=3)
    
    print_metrics_table("Gradient (Baseline)", gradient_metrics, gradient_consistency)
    
    gradient_score = calculate_improvement_score(
        gradient_metrics['profit_factor'],
        gradient_metrics['max_drawdown_pct'],
        gradient_consistency,
        gradient_metrics['total_trades']
    )
    
    print(f"\n🏆 Overall Score: {gradient_score:.1f}/100")
    print(f"   Risk-Reward: {gradient_metrics['avg_win'] / abs(gradient_metrics['avg_loss']):.2f}:1" 
          if gradient_metrics['avg_loss'] != 0 else "")
    
    results['gradient'] = {
        'trades': len(gradient_trades),
        'metrics': gradient_metrics,
        'consistency': gradient_consistency,
        'score': gradient_score,
    }
    
    # ========================================================================
    # TEST 2: Enhanced Strategy (Entry Quality Focus)
    # ========================================================================
    print_section_header("TEST 2: ENHANCED STRATEGY (ENTRY QUALITY FOCUS)")
    
    print("\n🚀 Running enhanced strategy...")
    enhanced_params = {
        **params,
        # Enhanced RR
        "take_profit_atr_mult": 4.8,
        # Quality filtering
        "enable_quality_filter": True,
        "min_quality_score": 55,
        "require_rsi_momentum_alignment": True,
        "require_positive_ema_slope": True,
        "min_pullback_quality": 40,
    }
    
    enhanced_trades, enhanced_equity = run_anti_chop_gradient_enhanced_strategy(candles, config, enhanced_params)
    
    print(f"✅ Completed: {len(enhanced_trades)} trades")
    
    enhanced_metrics = calculate_metrics(enhanced_trades, enhanced_equity, config.initial_balance)
    enhanced_consistency = calculate_consistency_score(enhanced_trades, segments=3)
    
    print_metrics_table("Enhanced (Quality)", enhanced_metrics, enhanced_consistency)
    
    enhanced_score = calculate_improvement_score(
        enhanced_metrics['profit_factor'],
        enhanced_metrics['max_drawdown_pct'],
        enhanced_consistency,
        enhanced_metrics['total_trades']
    )
    
    print(f"\n🏆 Overall Score: {enhanced_score:.1f}/100")
    print(f"   Risk-Reward: {enhanced_metrics['avg_win'] / abs(enhanced_metrics['avg_loss']):.2f}:1"
          if enhanced_metrics['avg_loss'] != 0 else "")
    
    results['enhanced'] = {
        'trades': len(enhanced_trades),
        'metrics': enhanced_metrics,
        'consistency': enhanced_consistency,
        'score': enhanced_score,
    }
    
    # ========================================================================
    # COMPARISON
    # ========================================================================
    print_section_header("COMPREHENSIVE COMPARISON")
    
    print(f"\n{'Strategy':<30} {'Trades':<10} {'PF':<10} {'DD%':<10} {'Cons%':<10} {'P&L':<15} {'Score':<10}")
    print("-" * 95)
    
    for name, display_name in [
        ('gradient', 'Gradient (Baseline)'),
        ('enhanced', 'Enhanced (Quality) ★')
    ]:
        r = results[name]
        m = r['metrics']
        marker = " ★" if name == 'enhanced' else ""
        print(f"{display_name:<30} {r['trades']:<10} {m['profit_factor']:<10.2f} "
              f"{m['max_drawdown_pct']:<10.2f} {r['consistency']:<10.1f} "
              f"${m['total_pnl']:<14.2f} {r['score']:<10.1f}")
    
    # Improvement Analysis
    print_section_header("ENHANCED vs GRADIENT - IMPROVEMENT ANALYSIS")
    
    improvements = {
        'Trades': (results['enhanced']['trades'] - results['gradient']['trades'],
                   results['gradient']['trades']),
        'Profit Factor': (results['enhanced']['metrics']['profit_factor'] - results['gradient']['metrics']['profit_factor'],
                         results['gradient']['metrics']['profit_factor']),
        'Max DD %': (results['enhanced']['metrics']['max_drawdown_pct'] - results['gradient']['metrics']['max_drawdown_pct'],
                    results['gradient']['metrics']['max_drawdown_pct']),
        'Consistency %': (results['enhanced']['consistency'] - results['gradient']['consistency'],
                         results['gradient']['consistency']),
        'Net P&L': (results['enhanced']['metrics']['total_pnl'] - results['gradient']['metrics']['total_pnl'],
                   results['gradient']['metrics']['total_pnl']),
        'Win Rate %': (results['enhanced']['metrics']['win_rate'] - results['gradient']['metrics']['win_rate'],
                      results['gradient']['metrics']['win_rate']),
        'Avg Win': (results['enhanced']['metrics']['avg_win'] - results['gradient']['metrics']['avg_win'],
                   results['gradient']['metrics']['avg_win']),
        'Avg Loss': (results['enhanced']['metrics']['avg_loss'] - results['gradient']['metrics']['avg_loss'],
                    results['gradient']['metrics']['avg_loss']),
        'Overall Score': (results['enhanced']['score'] - results['gradient']['score'],
                         results['gradient']['score']),
    }
    
    print(f"\n{'Metric':<25} {'Change':<20} {'% Change':<15} {'Status':<10}")
    print("-" * 70)
    
    for metric, (change, baseline) in improvements.items():
        pct_change = (change / baseline * 100) if baseline != 0 else 0
        
        # Determine status
        if metric in ['Max DD %', 'Avg Loss']:
            status = "✅" if change < 0 else "❌" if change > 0 else "⚠️"
        else:
            status = "✅" if change > 0 else "❌" if change < 0 else "⚠️"
        
        print(f"{metric:<25} {change:+.2f}{'':<14} {pct_change:+.1f}%{'':<9} {status:<10}")
    
    # Goal Achievement
    print_section_header("GOAL ACHIEVEMENT ANALYSIS")
    
    enhanced_m = results['enhanced']['metrics']
    enhanced_c = results['enhanced']['consistency']
    
    goals = {
        'Profit Factor > 1.5': (enhanced_m['profit_factor'] > 1.5, enhanced_m['profit_factor'], "1.5"),
        'Max Drawdown < 6%': (enhanced_m['max_drawdown_pct'] < 6.0, enhanced_m['max_drawdown_pct'], "6.0%"),
        'Consistency > 50%': (enhanced_c > 50, enhanced_c, "50%"),
        'Trades 25-40': (25 <= results['enhanced']['trades'] <= 40, results['enhanced']['trades'], "25-40"),
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
    
    # Win Rate Analysis
    print_section_header("WIN RATE & RISK-REWARD ANALYSIS")
    
    gradient_rr = gradient_metrics['avg_win'] / abs(gradient_metrics['avg_loss']) if gradient_metrics['avg_loss'] != 0 else 0
    enhanced_rr = enhanced_metrics['avg_win'] / abs(enhanced_metrics['avg_loss']) if enhanced_metrics['avg_loss'] != 0 else 0
    
    print(f"\n{'Metric':<25} {'Gradient':<20} {'Enhanced':<20} {'Change':<15}")
    print("-" * 80)
    print(f"{'Win Rate %':<25} {gradient_metrics['win_rate']:<20.1f} {enhanced_metrics['win_rate']:<20.1f} "
          f"{enhanced_metrics['win_rate'] - gradient_metrics['win_rate']:+.1f}%")
    print(f"{'Avg Win $':<25} {gradient_metrics['avg_win']:<20.2f} {enhanced_metrics['avg_win']:<20.2f} "
          f"{enhanced_metrics['avg_win'] - gradient_metrics['avg_win']:+.2f}")
    print(f"{'Avg Loss $':<25} {gradient_metrics['avg_loss']:<20.2f} {enhanced_metrics['avg_loss']:<20.2f} "
          f"{enhanced_metrics['avg_loss'] - gradient_metrics['avg_loss']:+.2f}")
    print(f"{'Risk-Reward Ratio':<25} {gradient_rr:<20.2f} {enhanced_rr:<20.2f} "
          f"{enhanced_rr - gradient_rr:+.2f}")
    
    # Final Verdict
    print_section_header("FINAL VERDICT & RECOMMENDATION")
    
    print(f"\n🎯 **ENHANCED STRATEGY PERFORMANCE**")
    print(f"   Overall Score: {results['enhanced']['score']:.1f}/100")
    
    if results['enhanced']['score'] >= 80:
        grade = "A (Excellent)"
        verdict = "✅ READY FOR PAPER TRADING"
    elif results['enhanced']['score'] >= 75:
        grade = "B+ (Very Good)"
        verdict = "✅ STRONG CANDIDATE - Minor refinement optional"
    elif results['enhanced']['score'] >= 70:
        grade = "B (Good)"
        verdict = "⚠️  GOOD PROGRESS - Consider parameter tuning"
    else:
        grade = "C+ (Acceptable)"
        verdict = "⚠️  NEEDS IMPROVEMENT"
    
    print(f"   Grade: {grade}")
    print(f"   Verdict: {verdict}")
    
    print(f"\n💡 **KEY INSIGHTS**")
    
    if results['enhanced']['score'] > results['gradient']['score']:
        improvement_pct = ((results['enhanced']['score'] - results['gradient']['score']) /
                          results['gradient']['score'] * 100)
        print(f"   ✅ Enhanced approach improved overall score by {improvement_pct:.1f}%")
    
    if enhanced_metrics['profit_factor'] > gradient_metrics['profit_factor']:
        pf_improvement = ((enhanced_metrics['profit_factor'] - gradient_metrics['profit_factor']) /
                         gradient_metrics['profit_factor'] * 100)
        print(f"   ✅ Profit Factor improved by {pf_improvement:.1f}%")
    
    if enhanced_metrics['profit_factor'] > 1.5:
        print(f"   ✅ **TARGET ACHIEVED**: Profit Factor {enhanced_metrics['profit_factor']:.2f} > 1.5")
    else:
        gap = 1.5 - enhanced_metrics['profit_factor']
        print(f"   ⚠️  Profit Factor: {enhanced_metrics['profit_factor']:.2f} (gap: -{gap:.2f} from target)")
    
    if enhanced_c > 50:
        print(f"   ✅ Consistency: {enhanced_c:.1f}% (target: >50%)")
    
    if enhanced_rr > gradient_rr:
        print(f"   ✅ Risk-Reward improved from {gradient_rr:.2f}:1 to {enhanced_rr:.2f}:1")
    
    print(f"\n📋 **RECOMMENDATION**")
    
    if goals_met >= 3:
        print(f"   ✅ Strategy shows strong performance")
        print(f"   ✅ Entry quality improvements working effectively")
        print(f"   ✅ Ready for extended backtesting (6+ months)")
        if goals_met == 4:
            print(f"   🚀 ALL GOALS MET - Proceed to paper trading")
    elif goals_met >= 2:
        print(f"   ⚠️  Partial success - Entry quality helping but needs refinement")
        print(f"   ⚠️  Consider adjusting quality thresholds or TP multiplier")
    else:
        print(f"   ❌ Entry quality enhancements insufficient")
        print(f"   ❌ Review quality scoring components")
    
    print(f"\n📈 **NEXT STEPS**")
    if enhanced_metrics['profit_factor'] > 1.5:
        print(f"   1. ✅ Run extended validation (6+ months)")
        print(f"   2. ✅ Monte Carlo simulation (1000+ runs)")
        print(f"   3. ✅ Paper trading deployment")
    else:
        print(f"   1. ⚠️  Fine-tune quality score thresholds")
        print(f"   2. ⚠️  Test different TP multipliers (4.5-5.5x)")
        print(f"   3. ⚠️  Analyze rejected setups for false negatives")
    
    print("\n" + "=" * 80)
    
    client.close()


if __name__ == "__main__":
    asyncio.run(run_enhanced_validation())
