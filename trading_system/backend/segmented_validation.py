"""
SEGMENTED REGIME-ADAPTIVE VALIDATION

Processes dataset in 3-month chunks to avoid timeouts.
Aggregates results for final metrics.
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
import json
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from market_data_service import init_market_data_service
from market_data_models import DataTimeframe
from backtest_models import BacktestConfig, Timeframe
from regime_adaptive_system import run_regime_adaptive_system
from test_eurusd_strategy import calculate_metrics

load_dotenv(Path(__file__).parent / '.env')

async def main():
    print("="*80)
    print("REGIME-ADAPTIVE SYSTEM - SEGMENTED VALIDATION")
    print("="*80)
    
    # Connect
    client = AsyncIOMotorClient(os.environ.get('MONGO_URL'))
    db = client[os.environ.get('DB_NAME', 'ctrader_bot_factory')]
    mds = init_market_data_service(db)
    
    # Load ALL data
    print("\n📊 Loading full dataset...")
    all_candles = await mds.get_candles("EURUSD", DataTimeframe.H1, None, None, 20000)
    print(f"✅ {len(all_candles)} candles loaded")
    print(f"   Range: {all_candles[0].timestamp} to {all_candles[-1].timestamp}")
    print(f"   Duration: {(all_candles[-1].timestamp - all_candles[0].timestamp).days} days")
    
    # Define 3-month segments
    start_date = all_candles[0].timestamp
    end_date = all_candles[-1].timestamp
    
    segments = []
    current_start = start_date
    segment_num = 1
    
    while current_start < end_date:
        current_end = current_start + timedelta(days=90)
        if current_end > end_date:
            current_end = end_date
        
        segment_candles = [c for c in all_candles if current_start <= c.timestamp < current_end]
        
        if len(segment_candles) > 100:  # Minimum candles for valid test
            segments.append({
                "num": segment_num,
                "name": f"Segment {segment_num}",
                "start": current_start,
                "end": current_end,
                "candles": segment_candles
            })
            segment_num += 1
        
        current_start = current_end
    
    print(f"\n📅 Created {len(segments)} segments:")
    for seg in segments:
        days = (seg['end'] - seg['start']).days
        print(f"   {seg['name']}: {seg['start'].strftime('%Y-%m-%d')} to {seg['end'].strftime('%Y-%m-%d')} ({len(seg['candles'])} candles, {days} days)")
    
    # Parameters - SIMPLE, NO OPTIMIZATION
    params = {
        "regime_lookback": 50,
        "min_regime_confidence": 0.6,
        "enable_trend_strategy": True,
        "enable_mean_reversion_strategy": True,
        "max_total_trades_per_day": 3,
        "trend_params": {
            "ema_fast": 20,
            "ema_slow": 50,
            "stop_loss_atr_mult": 2.0,
            "take_profit_atr_mult": 4.0,
            "risk_per_trade_pct": 1.0,
        },
        "mean_reversion_params": {
            "bb_period": 20,
            "bb_std_dev": 2.0,
            "stop_loss_atr_mult": 2.5,
            "risk_per_trade_pct": 1.0,
        },
    }
    
    # Process each segment
    print(f"\n{'='*80}")
    print("PROCESSING SEGMENTS")
    print(f"{'='*80}")
    
    segment_results = []
    all_trades = []
    cumulative_balance = 10000.0
    
    for seg in segments:
        print(f"\n🔄 Processing {seg['name']}...")
        print(f"   Period: {seg['start'].strftime('%Y-%m-%d')} to {seg['end'].strftime('%Y-%m-%d')}")
        print(f"   Candles: {len(seg['candles'])}")
        
        # Config for this segment
        config = BacktestConfig(
            symbol="EURUSD",
            timeframe=Timeframe.H1,
            start_date=seg['start'],
            end_date=seg['end'],
            initial_balance=cumulative_balance,  # Use cumulative balance
            spread_pips=1.5,
            commission_per_lot=7.0,
            leverage=100,
        )
        
        # Run segment
        try:
            trades, equity_curve, stats = run_regime_adaptive_system(seg['candles'], config, params)
            
            # Calculate metrics
            if trades:
                metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
                
                # Update cumulative balance
                final_balance = config.initial_balance + metrics['total_pnl']
                cumulative_balance = final_balance
                
                # Store results
                result = {
                    "segment": seg['name'],
                    "start": seg['start'].strftime('%Y-%m-%d'),
                    "end": seg['end'].strftime('%Y-%m-%d'),
                    "initial_balance": config.initial_balance,
                    "final_balance": final_balance,
                    "trades": len(trades),
                    "profit_factor": metrics['profit_factor'],
                    "max_dd_pct": metrics['max_drawdown_pct'],
                    "total_pnl": metrics['total_pnl'],
                    "win_rate": metrics['win_rate'],
                    "sharpe": metrics['sharpe_ratio'],
                    "return_pct": (final_balance / config.initial_balance - 1) * 100,
                    "profitable": metrics['total_pnl'] > 0,
                    "trade_by_strategy": stats['trade_by_strategy'],
                    "pnl_by_strategy": stats['pnl_by_strategy'],
                }
                
                segment_results.append(result)
                all_trades.extend(trades)
                
                # Print segment summary
                print(f"   ✅ Complete: {len(trades)} trades")
                print(f"      PF: {metrics['profit_factor']:.2f} | DD: {metrics['max_drawdown_pct']:.2f}% | P&L: ${metrics['total_pnl']:.2f}")
                print(f"      Balance: ${config.initial_balance:.2f} → ${final_balance:.2f} ({result['return_pct']:+.2f}%)")
            else:
                print(f"   ⚠️  No trades in this segment")
                result = {
                    "segment": seg['name'],
                    "start": seg['start'].strftime('%Y-%m-%d'),
                    "end": seg['end'].strftime('%Y-%m-%d'),
                    "initial_balance": config.initial_balance,
                    "final_balance": config.initial_balance,
                    "trades": 0,
                    "profit_factor": 0,
                    "max_dd_pct": 0,
                    "total_pnl": 0,
                    "win_rate": 0,
                    "sharpe": 0,
                    "return_pct": 0,
                    "profitable": False,
                    "trade_by_strategy": {},
                    "pnl_by_strategy": {},
                }
                segment_results.append(result)
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
            continue
    
    # Calculate combined metrics
    print(f"\n{'='*80}")
    print("COMBINED RESULTS")
    print(f"{'='*80}")
    
    total_trades = sum(r['trades'] for r in segment_results)
    profitable_segments = sum(1 for r in segment_results if r['profitable'])
    consistency = (profitable_segments / len(segment_results) * 100) if segment_results else 0
    
    # Overall return
    initial_capital = 10000.0
    final_capital = cumulative_balance
    total_return_pct = (final_capital / initial_capital - 1) * 100
    total_pnl = final_capital - initial_capital
    
    # Aggregate max DD (worst across all segments)
    max_dd_overall = max(r['max_dd_pct'] for r in segment_results) if segment_results else 0
    
    # Calculate overall profit factor
    total_wins = sum(t.profit_loss for t in all_trades if t.profit_loss > 0)
    total_losses = abs(sum(t.profit_loss for t in all_trades if t.profit_loss < 0))
    overall_pf = (total_wins / total_losses) if total_losses > 0 else 0
    
    # Win rate
    winning_trades = sum(1 for t in all_trades if t.profit_loss > 0)
    overall_win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    print(f"\n📊 **OVERALL PERFORMANCE**")
    print(f"\nTotal Trades: {total_trades}")
    print(f"Profit Factor: {overall_pf:.2f}")
    print(f"Max Drawdown: {max_dd_overall:.2f}%")
    print(f"Consistency: {consistency:.1f}% ({profitable_segments}/{len(segment_results)} profitable segments)")
    print(f"Win Rate: {overall_win_rate:.1f}%")
    print(f"")
    print(f"Initial Capital: ${initial_capital:.2f}")
    print(f"Final Capital: ${final_capital:.2f}")
    print(f"Net Profit: ${total_pnl:.2f}")
    print(f"Total Return: {total_return_pct:.2f}%")
    
    # Segment breakdown
    print(f"\n📊 **SEGMENT BREAKDOWN**")
    print(f"\n{'Segment':<15} {'Trades':<8} {'PF':<8} {'DD%':<8} {'Return%':<10} {'P&L':<12} {'Status':<8}")
    print("-" * 75)
    
    for r in segment_results:
        status = "✅" if r['profitable'] else "❌"
        print(f"{r['segment']:<15} {r['trades']:<8} {r['profit_factor']:<8.2f} "
              f"{r['max_dd_pct']:<8.2f} {r['return_pct']:<10.1f} ${r['total_pnl']:<11.2f} {status:<8}")
    
    # Strategy breakdown
    print(f"\n📊 **STRATEGY BREAKDOWN (COMBINED)**")
    
    strategy_totals = {}
    for r in segment_results:
        for strategy, count in r['trade_by_strategy'].items():
            if strategy not in strategy_totals:
                strategy_totals[strategy] = {'trades': 0, 'pnl': 0.0}
            strategy_totals[strategy]['trades'] += count
            strategy_totals[strategy]['pnl'] += r['pnl_by_strategy'].get(strategy, 0.0)
    
    print(f"\n{'Strategy':<20} {'Trades':<10} {'P&L':<15} {'Avg P&L':<15}")
    print("-" * 60)
    for strategy, stats in strategy_totals.items():
        avg_pnl = stats['pnl'] / stats['trades'] if stats['trades'] > 0 else 0
        print(f"{strategy:<20} {stats['trades']:<10} ${stats['pnl']:<14.2f} ${avg_pnl:<14.2f}")
    
    # Validation criteria
    print(f"\n{'='*80}")
    print("VALIDATION CRITERIA")
    print(f"{'='*80}")
    
    validation_checks = {
        "Profit Factor > 1.5": (overall_pf > 1.5, overall_pf, "1.5"),
        "Max Drawdown < 6%": (max_dd_overall < 6.0, max_dd_overall, "6%"),
        "Consistency > 50%": (consistency > 50, consistency, "50%"),
        "Win Rate > 40%": (overall_win_rate > 40, overall_win_rate, "40%"),
        "Trades 30-50": (30 <= total_trades <= 50, total_trades, "30-50"),
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
    
    print(f"\n📊 Validation Score: {checks_passed}/5 ({checks_passed*20}%)")
    
    # Comparison with overfitted system
    print(f"\n{'='*80}")
    print("COMPARISON WITH OVERFITTED SYSTEM")
    print(f"{'='*80}")
    
    overfitted = {
        "trades": 13,
        "pf": 1.38,
        "dd": 4.31,
        "consistency": 0.0,
        "pnl": 188.24,
        "win_rate": 30.8,
    }
    
    print(f"\n{'Metric':<25} {'Overfitted':<15} {'Adaptive':<15} {'Change':<15} {'Status':<10}")
    print("-" * 80)
    
    comparisons = [
        ("Trades", overfitted["trades"], total_trades),
        ("Profit Factor", overfitted["pf"], overall_pf),
        ("Max DD %", overfitted["dd"], max_dd_overall),
        ("Consistency %", overfitted["consistency"], consistency),
        ("Net P&L $", overfitted["pnl"], total_pnl),
        ("Win Rate %", overfitted["win_rate"], overall_win_rate),
    ]
    
    for metric_name, old_val, new_val in comparisons:
        change = new_val - old_val
        if old_val != 0:
            change_pct = (change / old_val * 100)
            change_str = f"{change:+.2f} ({change_pct:+.1f}%)"
        else:
            change_str = f"{change:+.2f}"
        
        # Determine status
        if metric_name == "Max DD %":
            status = "✅" if change < 0 else "⚠️" if abs(change) < 1 else "❌"
        else:
            status = "✅" if change > 0 else "⚠️" if abs(change) < 0.1 else "❌"
        
        print(f"{metric_name:<25} {old_val:<15.2f} {new_val:<15.2f} {change_str:<15} {status:<10}")
    
    # Final verdict
    print(f"\n{'='*80}")
    print("FINAL VERDICT")
    print(f"{'='*80}")
    
    if checks_passed >= 4:
        grade = "A/B - EXCELLENT"
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
    
    if overall_pf > overfitted['pf']:
        improvement = ((overall_pf - overfitted['pf']) / overfitted['pf'] * 100)
        print(f"   ✅ Profit Factor improved by {improvement:.1f}%")
    else:
        decline = ((overfitted['pf'] - overall_pf) / overfitted['pf'] * 100)
        print(f"   ❌ Profit Factor declined by {decline:.1f}%")
    
    if consistency > overfitted['consistency']:
        print(f"   ✅ Consistency improved from {overfitted['consistency']:.0f}% to {consistency:.0f}%")
    
    if total_trades > overfitted['trades']:
        print(f"   ✅ More trading opportunities ({total_trades} vs {overfitted['trades']})")
    
    if total_pnl > overfitted['pnl']:
        improvement = ((total_pnl - overfitted['pnl']) / overfitted['pnl'] * 100)
        print(f"   ✅ Net profit improved by {improvement:.1f}%")
    
    if checks_passed >= 3:
        print(f"\n   ✅ Regime-adaptive system shows significant improvement")
    else:
        print(f"\n   ⚠️  System needs refinement")
    
    # Save results
    results_summary = {
        "overall": {
            "trades": total_trades,
            "profit_factor": overall_pf,
            "max_drawdown_pct": max_dd_overall,
            "consistency": consistency,
            "win_rate": overall_win_rate,
            "total_pnl": total_pnl,
            "return_pct": total_return_pct,
            "initial_capital": initial_capital,
            "final_capital": final_capital,
        },
        "validation": {
            "checks_passed": checks_passed,
            "total_checks": 5,
            "grade": grade,
            "recommendation": recommendation,
        },
        "segments": segment_results,
        "strategy_breakdown": strategy_totals,
    }
    
    with open('/app/regime_validation_results.json', 'w') as f:
        json.dump(results_summary, f, indent=2, default=str)
    
    print(f"\n📄 Results saved to: /app/regime_validation_results.json")
    print(f"\n{'='*80}\n")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(main())
