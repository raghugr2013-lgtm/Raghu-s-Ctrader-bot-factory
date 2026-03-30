"""
Validation for Regime-Adaptive Trading System

Tests the complete adaptive system on 14-month dataset.
Compares with previous overfitted strategy.
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
from regime_adaptive_system import run_regime_adaptive_system
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


async def validate_regime_adaptive_system():
    """Validate regime-adaptive system on full 14-month dataset"""
    
    print_header("REGIME-ADAPTIVE SYSTEM VALIDATION", "=")
    print(f"Testing on 14-month dataset (Jan 2025 - Feb 2026)")
    
    # Connect
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Load data
    print_header("DATA LOADING", "-")
    print("\n📊 Loading EURUSD H1 data...")
    
    candles = await market_data_service.get_candles(
        symbol="EURUSD",
        timeframe=DataTimeframe.H1,
        start_date=None,
        end_date=None,
        limit=20000
    )
    
    if not candles:
        print("❌ No data found")
        client.close()
        return
    
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
    
    # Parameters - SIMPLE, NO OPTIMIZATION
    params = {
        "regime_lookback": 50,
        "min_regime_confidence": 0.6,
        "enable_trend_strategy": True,
        "enable_mean_reversion_strategy": True,
        "max_total_trades_per_day": 3,
        
        # Trend strategy params (standard, not optimized)
        "trend_params": {
            "ema_fast": 20,
            "ema_slow": 50,
            "rsi_period": 14,
            "stop_loss_atr_mult": 2.0,
            "take_profit_atr_mult": 4.0,
            "risk_per_trade_pct": 1.0,
        },
        
        # Mean-reversion params (standard, not optimized)
        "mean_reversion_params": {
            "bb_period": 20,
            "bb_std_dev": 2.0,
            "rsi_period": 14,
            "stop_loss_atr_mult": 2.5,
            "risk_per_trade_pct": 1.0,
        },
    }
    
    # Run regime-adaptive system
    print_header("RUNNING REGIME-ADAPTIVE SYSTEM", "-")
    
    trades, equity_curve, statistics = run_regime_adaptive_system(candles, config, params)
    
    # Calculate metrics
    print_header("PERFORMANCE ANALYSIS", "-")
    
    metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
    consistency = calculate_consistency_score(trades, segments=5)
    score = calculate_improvement_score(
        metrics['profit_factor'],
        metrics['max_drawdown_pct'],
        consistency,
        metrics['total_trades']
    )
    
    print(f"\n📊 **REGIME-ADAPTIVE SYSTEM RESULTS**")
    print(f"\n{'Metric':<30} {'Value':<20} {'Target':<15} {'Status':<10}")
    print("-" * 75)
    
    results_to_show = [
        ("Total Trades", f"{metrics['total_trades']}", "30-50", 
         "✅" if 30 <= metrics['total_trades'] <= 50 else "⚠️"),
        ("Profit Factor", f"{metrics['profit_factor']:.2f}", "> 1.5",
         "✅" if metrics['profit_factor'] > 1.5 else "❌"),
        ("Max Drawdown %", f"{metrics['max_drawdown_pct']:.2f}%", "< 6%",
         "✅" if metrics['max_drawdown_pct'] < 6.0 else "❌"),
        ("Consistency %", f"{consistency:.1f}%", "> 50%",
         "✅" if consistency > 50 else "❌"),
        ("Net Profit $", f"{metrics['total_pnl']:.2f}", "> 0",
         "✅" if metrics['total_pnl'] > 0 else "❌"),
        ("Win Rate %", f"{metrics['win_rate']:.1f}%", "> 40%",
         "✅" if metrics['win_rate'] > 40 else "⚠️"),
        ("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}", "> 1.0",
         "✅" if metrics['sharpe_ratio'] > 1.0 else "⚠️"),
        ("Overall Score", f"{score:.1f}/100", "> 70",
         "✅" if score > 70 else "⚠️"),
    ]
    
    for metric_name, value, target, status in results_to_show:
        print(f"{metric_name:<30} {value:<20} {target:<15} {status:<10}")
    
    # Strategy breakdown
    print(f"\n📊 **STRATEGY BREAKDOWN**")
    print(f"\n{'Strategy':<20} {'Trades':<10} {'P&L':<15} {'Avg P&L':<15}")
    print("-" * 60)
    
    for strategy, count in statistics['trade_by_strategy'].items():
        pnl = statistics['pnl_by_strategy'][strategy]
        avg_pnl = pnl / count if count > 0 else 0
        print(f"{strategy:<20} {count:<10} ${pnl:<14.2f} ${avg_pnl:<14.2f}")
    
    # Comparison with overfitted strategy
    print_header("COMPARISON WITH PREVIOUS STRATEGY", "-")
    
    print(f"\n{'Metric':<30} {'Overfitted':<15} {'Adaptive':<15} {'Change':<15} {'Status':<10}")
    print("-" * 85)
    
    # Previous overfitted strategy results (14-month)
    overfitted = {
        "trades": 13,
        "pf": 1.38,
        "dd": 4.31,
        "consistency": 0.0,
        "pnl": 188.24,
        "win_rate": 30.8,
        "score": 46.0,
    }
    
    comparisons = [
        ("Trades", overfitted["trades"], metrics['total_trades']),
        ("Profit Factor", overfitted["pf"], metrics['profit_factor']),
        ("Max DD %", overfitted["dd"], metrics['max_drawdown_pct']),
        ("Consistency %", overfitted["consistency"], consistency),
        ("Net P&L $", overfitted["pnl"], metrics['total_pnl']),
        ("Win Rate %", overfitted["win_rate"], metrics['win_rate']),
        ("Overall Score", overfitted["score"], score),
    ]
    
    for metric_name, old_val, new_val in comparisons:
        change = new_val - old_val
        change_pct = (change / old_val * 100) if old_val != 0 else 0
        
        # Determine status
        if metric_name == "Max DD %":
            status = "✅" if change < 0 else "⚠️" if change == 0 else "❌"
        else:
            status = "✅" if change > 0 else "⚠️" if change == 0 else "❌"
        
        if isinstance(old_val, float) and isinstance(new_val, float):
            print(f"{metric_name:<30} {old_val:<15.2f} {new_val:<15.2f} {change:+.2f} ({change_pct:+.1f}%) {status:<10}")
        else:
            print(f"{metric_name:<30} {old_val:<15} {new_val:<15} {change:+.1f} ({change_pct:+.1f}%) {status:<10}")
    
    # Validation criteria
    print_header("VALIDATION CRITERIA", "-")
    
    validation_checks = {
        "Profit Factor > 1.5": (metrics['profit_factor'] > 1.5, metrics['profit_factor'], "1.5"),
        "Max Drawdown < 6%": (metrics['max_drawdown_pct'] < 6.0, metrics['max_drawdown_pct'], "6%"),
        "Consistency > 50%": (consistency > 50, consistency, "50%"),
        "Win Rate > 40%": (metrics['win_rate'] > 40, metrics['win_rate'], "40%"),
        "Trades 30-50": (30 <= metrics['total_trades'] <= 50, metrics['total_trades'], "30-50"),
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
    
    # Final verdict
    print_header("FINAL VERDICT", "=")
    
    if checks_passed >= 4:
        grade = "A/B - GOOD"
        recommendation = "✅ APPROVED for paper trading"
    elif checks_passed >= 3:
        grade = "C - ACCEPTABLE"
        recommendation = "⚠️  CONDITIONAL - Monitor closely"
    else:
        grade = "D/F - INSUFFICIENT"
        recommendation = "❌ NOT APPROVED"
    
    print(f"\n🎯 Grade: {grade}")
    print(f"🎯 Recommendation: {recommendation}")
    
    print(f"\n💡 **KEY INSIGHTS**")
    
    if metrics['profit_factor'] > overfitted['pf']:
        pf_improvement = ((metrics['profit_factor'] - overfitted['pf']) / overfitted['pf'] * 100)
        print(f"   ✅ Profit Factor improved by {pf_improvement:.1f}%")
    
    if consistency > overfitted['consistency']:
        print(f"   ✅ Consistency improved from {overfitted['consistency']:.0f}% to {consistency:.0f}%")
    
    if metrics['total_trades'] > overfitted['trades']:
        print(f"   ✅ More trading opportunities ({metrics['total_trades']} vs {overfitted['trades']})")
    
    if score > overfitted['score']:
        score_improvement = score - overfitted['score']
        print(f"   ✅ Overall score improved by {score_improvement:.1f} points")
    
    if checks_passed >= 3:
        print(f"\n   ✅ Regime-adaptive approach shows promise")
        print(f"   ✅ Better than overfitted single-strategy system")
    else:
        print(f"\n   ⚠️  Needs further refinement")
    
    print(f"\n{'='*100}\n")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(validate_regime_adaptive_system())
