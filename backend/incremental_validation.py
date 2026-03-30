"""
INCREMENTAL REGIME-ADAPTIVE VALIDATION WITH CHECKPOINTING

Processes large datasets in small batches to avoid timeout.
Saves progress after each batch - can resume from interruptions.

Key features:
- Processes 500 candles per batch (well under 120s timeout)
- Saves checkpoint after each batch to JSON state file
- Resume from last checkpoint if interrupted
- Aggregates all results at the end
- Full validation of 15-month dataset possible
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
import json
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from market_data_service import init_market_data_service
from market_data_models import DataTimeframe
from backtest_models import BacktestConfig, Timeframe
from regime_adaptive_system import run_regime_adaptive_system
from test_eurusd_strategy import calculate_metrics

load_dotenv(Path(__file__).parent / '.env')

# Configuration
CHECKPOINT_FILE = '/app/validation_checkpoint.json'
BATCH_SIZE = 500  # Process 500 candles at a time
INITIAL_BALANCE = 10000.0


def load_checkpoint():
    """Load checkpoint from disk if exists"""
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r') as f:
                return json.load(f)
        except:
            return None
    return None


def save_checkpoint(checkpoint_data):
    """Save checkpoint to disk"""
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(checkpoint_data, f, indent=2, default=str)


def create_initial_checkpoint(total_candles):
    """Create fresh checkpoint"""
    return {
        "batch_number": 0,
        "last_processed_index": 0,
        "total_candles": total_candles,
        "cumulative_balance": INITIAL_BALANCE,
        "all_trades": [],
        "batch_results": [],
        "started_at": datetime.utcnow().isoformat(),
        "last_updated": datetime.utcnow().isoformat(),
        "completed": False,
    }


async def process_batch(candles_batch, batch_num, cumulative_balance, params):
    """
    Process a single batch of candles
    
    Returns: (trades, metrics, final_balance, stats)
    """
    
    if len(candles_batch) < 50:
        # Not enough candles for meaningful backtest
        return [], None, cumulative_balance, {}
    
    # Create config for this batch
    config = BacktestConfig(
        symbol="EURUSD",
        timeframe=Timeframe.H1,
        start_date=candles_batch[0].timestamp,
        end_date=candles_batch[-1].timestamp,
        initial_balance=cumulative_balance,
        spread_pips=1.5,
        commission_per_lot=7.0,
        leverage=100,
    )
    
    # Run regime-adaptive system on this batch
    trades, equity_curve, stats = run_regime_adaptive_system(candles_batch, config, params)
    
    # Calculate metrics if trades exist
    metrics = None
    final_balance = cumulative_balance
    
    if trades:
        metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
        final_balance = config.initial_balance + metrics['total_pnl']
    
    return trades, metrics, final_balance, stats


async def main():
    print("="*80)
    print("INCREMENTAL REGIME-ADAPTIVE VALIDATION")
    print("WITH CHECKPOINTING & RESUME CAPABILITY")
    print("="*80)
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(os.environ.get('MONGO_URL'))
    db = client[os.environ.get('DB_NAME', 'ctrader_bot_factory')]
    mds = init_market_data_service(db)
    
    # Strategy parameters (IMPROVED - Relaxed for more opportunities)
    params = {
        "regime_lookback": 50,
        "min_regime_confidence": 0.4,  # REDUCED from 0.6
        "enable_trend_strategy": True,
        "enable_mean_reversion_strategy": True,
        "max_total_trades_per_day": 5,  # INCREASED from 3
        "trend_params": {
            "ema_fast": 12,  # Faster EMAs
            "ema_slow": 26,
            "stop_loss_atr_mult": 1.5,  # Tighter stops
            "take_profit_atr_mult": 3.0,  # More realistic targets
            "risk_per_trade_pct": 1.0,
            "min_regime_confidence": 0.4,  # REDUCED
            "max_trades_per_day": 3,
        },
        "mean_reversion_params": {
            "bb_period": 20,
            "bb_std_dev": 1.8,  # Narrower bands for more touches
            "rsi_oversold_extreme": 40,  # RELAXED from 30
            "rsi_overbought_extreme": 60,  # RELAXED from 70
            "stop_loss_atr_mult": 2.5,
            "risk_per_trade_pct": 1.0,
            "min_regime_confidence": 0.4,  # REDUCED
            "max_trades_per_day": 3,
        },
    }
    
    # Load all candles
    print("\n📊 Loading full dataset from MongoDB...")
    all_candles = await mds.get_candles("EURUSD", DataTimeframe.H1, None, None, 20000)
    print(f"✅ {len(all_candles)} candles loaded")
    print(f"   Range: {all_candles[0].timestamp} to {all_candles[-1].timestamp}")
    print(f"   Duration: {(all_candles[-1].timestamp - all_candles[0].timestamp).days} days")
    
    # Check for existing checkpoint
    checkpoint = load_checkpoint()
    
    if checkpoint and not checkpoint.get('completed', False):
        print(f"\n🔄 RESUMING from checkpoint:")
        print(f"   Last batch: {checkpoint['batch_number']}")
        print(f"   Progress: {checkpoint['last_processed_index']}/{checkpoint['total_candles']} candles")
        print(f"   Current balance: ${checkpoint['cumulative_balance']:.2f}")
        resume = True
    else:
        print(f"\n🆕 Starting FRESH validation")
        checkpoint = create_initial_checkpoint(len(all_candles))
        save_checkpoint(checkpoint)
        resume = False
    
    # Process in batches
    start_index = checkpoint['last_processed_index']
    batch_num = checkpoint['batch_number']
    cumulative_balance = checkpoint['cumulative_balance']
    all_trades = checkpoint.get('all_trades', [])
    batch_results = checkpoint.get('batch_results', [])
    
    print(f"\n{'='*80}")
    print(f"PROCESSING BATCHES (Size: {BATCH_SIZE} candles)")
    print(f"{'='*80}\n")
    
    while start_index < len(all_candles):
        batch_num += 1
        end_index = min(start_index + BATCH_SIZE, len(all_candles))
        candles_batch = all_candles[start_index:end_index]
        
        print(f"🔄 Batch {batch_num}: Processing candles {start_index} to {end_index} ({len(candles_batch)} candles)")
        print(f"   Period: {candles_batch[0].timestamp.strftime('%Y-%m-%d')} to {candles_batch[-1].timestamp.strftime('%Y-%m-%d')}")
        print(f"   Current balance: ${cumulative_balance:.2f}")
        
        try:
            # Process this batch
            trades, metrics, final_balance, stats = await process_batch(
                candles_batch, batch_num, cumulative_balance, params
            )
            
            # Store results
            if metrics:
                batch_result = {
                    "batch": batch_num,
                    "start_index": start_index,
                    "end_index": end_index,
                    "candles": len(candles_batch),
                    "trades": len(trades),
                    "initial_balance": cumulative_balance,
                    "final_balance": final_balance,
                    "pnl": metrics['total_pnl'],
                    "profit_factor": metrics['profit_factor'],
                    "max_dd_pct": metrics['max_drawdown_pct'],
                    "win_rate": metrics['win_rate'],
                    "return_pct": (final_balance / cumulative_balance - 1) * 100 if cumulative_balance > 0 else 0,
                    "trade_by_strategy": stats.get('trade_by_strategy', {}),
                    "pnl_by_strategy": stats.get('pnl_by_strategy', {}),
                }
                batch_results.append(batch_result)
                
                # Convert trades to dict for JSON serialization
                trades_dict = [
                    {
                        "entry_time": t.entry_time.isoformat(),
                        "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                        "direction": t.direction.value if hasattr(t.direction, 'value') else str(t.direction),
                        "entry_price": t.entry_price,
                        "exit_price": t.exit_price,
                        "profit_loss": t.profit_loss,
                        "pips": t.profit_loss_pips if hasattr(t, 'profit_loss_pips') else 0,
                    }
                    for t in trades
                ]
                all_trades.extend(trades_dict)
                
                # Update cumulative balance
                cumulative_balance = final_balance
                
                print(f"   ✅ {len(trades)} trades | PF: {metrics['profit_factor']:.2f} | "
                      f"P&L: ${metrics['total_pnl']:.2f} | Balance: ${final_balance:.2f}")
            else:
                print(f"   ⚠️  No trades in this batch")
                batch_results.append({
                    "batch": batch_num,
                    "start_index": start_index,
                    "end_index": end_index,
                    "candles": len(candles_batch),
                    "trades": 0,
                    "initial_balance": cumulative_balance,
                    "final_balance": cumulative_balance,
                    "pnl": 0,
                    "profit_factor": 0,
                    "max_dd_pct": 0,
                    "win_rate": 0,
                    "return_pct": 0,
                })
            
            # Update checkpoint
            checkpoint['batch_number'] = batch_num
            checkpoint['last_processed_index'] = end_index
            checkpoint['cumulative_balance'] = cumulative_balance
            checkpoint['all_trades'] = all_trades
            checkpoint['batch_results'] = batch_results
            checkpoint['last_updated'] = datetime.utcnow().isoformat()
            save_checkpoint(checkpoint)
            
            print(f"   💾 Checkpoint saved (Progress: {end_index}/{len(all_candles)} = {end_index/len(all_candles)*100:.1f}%)\n")
            
            # Move to next batch
            start_index = end_index
            
        except Exception as e:
            print(f"   ❌ Error in batch {batch_num}: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            print(f"   💾 Checkpoint saved - you can resume from here")
            client.close()
            return
    
    # Mark as completed
    checkpoint['completed'] = True
    checkpoint['completed_at'] = datetime.utcnow().isoformat()
    save_checkpoint(checkpoint)
    
    # Calculate overall metrics
    print(f"\n{'='*80}")
    print("AGGREGATED RESULTS - FULL DATASET")
    print(f"{'='*80}")
    
    total_trades = sum(r['trades'] for r in batch_results)
    total_pnl = cumulative_balance - INITIAL_BALANCE
    total_return_pct = (cumulative_balance / INITIAL_BALANCE - 1) * 100
    
    # Calculate overall profit factor
    total_wins = sum(r['pnl'] for r in batch_results if r['pnl'] > 0)
    total_losses = abs(sum(r['pnl'] for r in batch_results if r['pnl'] < 0))
    overall_pf = (total_wins / total_losses) if total_losses > 0 else 0
    
    # Max drawdown (worst across all batches)
    max_dd_overall = max((r['max_dd_pct'] for r in batch_results if r['trades'] > 0), default=0)
    
    # Win rate
    winning_trades = sum(1 for t in all_trades if t.get('profit_loss', 0) > 0)
    overall_win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Consistency (profitable batches)
    profitable_batches = sum(1 for r in batch_results if r['pnl'] > 0)
    consistency = (profitable_batches / len(batch_results) * 100) if batch_results else 0
    
    print(f"\n📊 **OVERALL PERFORMANCE**")
    print(f"\nTotal Batches Processed: {len(batch_results)}")
    print(f"Total Trades: {total_trades}")
    print(f"Profit Factor: {overall_pf:.2f}")
    print(f"Max Drawdown: {max_dd_overall:.2f}%")
    print(f"Consistency: {consistency:.1f}% ({profitable_batches}/{len(batch_results)} profitable batches)")
    print(f"Win Rate: {overall_win_rate:.1f}%")
    print(f"")
    print(f"Initial Capital: ${INITIAL_BALANCE:.2f}")
    print(f"Final Capital: ${cumulative_balance:.2f}")
    print(f"Net Profit: ${total_pnl:.2f}")
    print(f"Total Return: {total_return_pct:.2f}%")
    
    # Batch breakdown
    print(f"\n📊 **BATCH BREAKDOWN**")
    print(f"\n{'Batch':<8} {'Candles':<10} {'Trades':<8} {'PF':<8} {'P&L':<12} {'Balance':<12} {'Status':<8}")
    print("-" * 80)
    
    for r in batch_results:
        status = "✅" if r['pnl'] > 0 else "❌" if r['pnl'] < 0 else "⚪"
        print(f"{r['batch']:<8} {r['candles']:<10} {r['trades']:<8} {r['profit_factor']:<8.2f} "
              f"${r['pnl']:<11.2f} ${r['final_balance']:<11.2f} {status:<8}")
    
    # Strategy breakdown
    print(f"\n📊 **STRATEGY BREAKDOWN**")
    
    strategy_totals = {}
    for r in batch_results:
        for strategy, count in r.get('trade_by_strategy', {}).items():
            if strategy not in strategy_totals:
                strategy_totals[strategy] = {'trades': 0, 'pnl': 0.0}
            strategy_totals[strategy]['trades'] += count
            strategy_totals[strategy]['pnl'] += r.get('pnl_by_strategy', {}).get(strategy, 0.0)
    
    print(f"\n{'Strategy':<25} {'Trades':<10} {'Total P&L':<15} {'Avg P&L/Trade':<15}")
    print("-" * 65)
    for strategy, stats in strategy_totals.items():
        avg_pnl = stats['pnl'] / stats['trades'] if stats['trades'] > 0 else 0
        print(f"{strategy:<25} {stats['trades']:<10} ${stats['pnl']:<14.2f} ${avg_pnl:<14.2f}")
    
    # Validation criteria
    print(f"\n{'='*80}")
    print("VALIDATION CRITERIA")
    print(f"{'='*80}")
    
    validation_checks = {
        "Profit Factor > 1.5": (overall_pf > 1.5, overall_pf, "1.5"),
        "Max Drawdown < 6%": (max_dd_overall < 6.0, max_dd_overall, "6%"),
        "Consistency > 50%": (consistency > 50, consistency, "50%"),
        "Win Rate > 40%": (overall_win_rate > 40, overall_win_rate, "40%"),
        "Positive Return": (total_return_pct > 0, total_return_pct, "> 0%"),
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
        recommendation = "❌ NOT APPROVED - Needs refinement"
    
    print(f"\n🎯 Grade: {grade}")
    print(f"🎯 Recommendation: {recommendation}")
    
    # Save final results
    final_results = {
        "validation_type": "incremental_full_dataset",
        "completed_at": datetime.utcnow().isoformat(),
        "dataset": {
            "total_candles": len(all_candles),
            "start_date": all_candles[0].timestamp.isoformat(),
            "end_date": all_candles[-1].timestamp.isoformat(),
            "duration_days": (all_candles[-1].timestamp - all_candles[0].timestamp).days,
        },
        "overall": {
            "total_batches": len(batch_results),
            "total_trades": total_trades,
            "profit_factor": overall_pf,
            "max_drawdown_pct": max_dd_overall,
            "consistency": consistency,
            "win_rate": overall_win_rate,
            "total_pnl": total_pnl,
            "return_pct": total_return_pct,
            "initial_capital": INITIAL_BALANCE,
            "final_capital": cumulative_balance,
        },
        "validation": {
            "checks_passed": checks_passed,
            "total_checks": 5,
            "score_pct": checks_passed * 20,
            "grade": grade,
            "recommendation": recommendation,
        },
        "batches": batch_results,
        "strategy_breakdown": strategy_totals,
    }
    
    with open('/app/incremental_validation_results.json', 'w') as f:
        json.dump(final_results, f, indent=2, default=str)
    
    print(f"\n📄 Full results saved to: /app/incremental_validation_results.json")
    print(f"📄 Checkpoint saved to: {CHECKPOINT_FILE}")
    print(f"\n{'='*80}\n")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
