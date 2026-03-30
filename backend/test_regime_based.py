"""
Test Regime-Based EURUSD Strategy

Goals:
- Profit Factor > 1.5
- Max Drawdown < 5%
- 50-100 trades
- Stable equity curve across regimes
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from auto_fetch_candles import auto_fetch_candles, MIN_CANDLES_REQUIRED
from market_data_service import init_market_data_service
from backtest_models import BacktestConfig, Timeframe
from regime_based_strategy import run_regime_based_strategy, MarketRegime
from test_eurusd_strategy import calculate_metrics, print_backtest_results

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')


async def test_regime_based():
    """Test regime-based strategy with variations"""
    
    print("="*70)
    print("REGIME-BASED EURUSD STRATEGY")
    print("="*70)
    print("\n🎯 Goals:")
    print("  - Profit Factor > 1.5")
    print("  - Max Drawdown < 5%")
    print("  - Trades: 50-100")
    print("  - Stable equity across regimes")
    
    # Connect
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Fetch data
    print(f"\n📊 Fetching EURUSD 1h data...")
    result = await auto_fetch_candles(
        db=db,
        market_data_service=market_data_service,
        symbol="EURUSD",
        timeframe="1h",
        min_candles=MIN_CANDLES_REQUIRED
    )
    
    if not result.success:
        print(f"❌ Failed: {result.error}")
        client.close()
        return
    
    print(f"✅ Fetched {result.candle_count} candles from {result.source}")
    
    candles = result.candles
    
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
    
    print(f"\n⚙️  Configuration:")
    print(f"  Period: {config.start_date.date()} to {config.end_date.date()}")
    print(f"  Initial Balance: ${config.initial_balance:.2f}")
    
    # Test configurations
    test_configs = [
        {
            "name": "Base Regime Strategy",
            "params": {}  # Use all defaults
        },
        {
            "name": "Conservative Risk (0.5%)",
            "params": {
                "risk_per_trade_pct": 0.5,
                "trend_stop_atr_mult": 2.5,
            }
        },
        {
            "name": "Aggressive Risk (1%)",
            "params": {
                "risk_per_trade_pct": 1.0,
                "max_trades_per_day": 4,
            }
        },
        {
            "name": "Wider Trend Thresholds",
            "params": {
                "trend_slope_threshold": 0.08,
                "min_trend_distance_pct": 0.15,
                "range_slope_threshold": 0.03,
            }
        },
        {
            "name": "Tighter Range Strategy",
            "params": {
                "rsi_oversold": 25,
                "rsi_overbought": 75,
                "bb_std_mult": 2.5,
            }
        },
    ]
    
    results = []
    
    for i, cfg in enumerate(test_configs, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}/{len(test_configs)}: {cfg['name']}")
        print(f"{'='*70}")
        
        # Run backtest
        trades, equity_curve = run_regime_based_strategy(candles, config, cfg['params'])
        
        # Calculate metrics
        metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
        
        # Display results
        print(f"\n📊 Performance:")
        print(f"  Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.1f}%")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"  Total P&L: ${metrics['total_pnl']:.2f} ({metrics['total_pnl']/config.initial_balance*100:.1f}%)")
        print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"  Expectancy: ${metrics['expectancy']:.2f}")
        
        # Analyze by strategy type
        if trades:
            trend_trades = [t for t in trades if hasattr(t, 'close_reason') and 
                          ('Trend' in t.close_reason or 'trend' in str(t.close_reason).lower())]
            range_trades = [t for t in trades if hasattr(t, 'close_reason') and 
                          ('Mean' in t.close_reason or 'range' in str(t.close_reason).lower())]
            
            print(f"\n📈 Strategy Breakdown:")
            print(f"  Trend Trades: {len(trend_trades)} ({len(trend_trades)/len(trades)*100:.1f}%)")
            print(f"  Range Trades: {len(range_trades)} ({len(range_trades)/len(trades)*100:.1f}%)")
        
        # Check goals
        goal_trades = 50 <= metrics['total_trades'] <= 100
        goal_pf = metrics['profit_factor'] > 1.5
        goal_dd = metrics['max_drawdown_pct'] < 5.0
        
        print(f"\n🎯 Goal Achievement:")
        print(f"  {'✅' if goal_trades else '❌'} Trades (50-100): {metrics['total_trades']}")
        print(f"  {'✅' if goal_pf else '❌'} Profit Factor (>1.5): {metrics['profit_factor']:.2f}")
        print(f"  {'✅' if goal_dd else '❌'} Max Drawdown (<5%): {metrics['max_drawdown_pct']:.2f}%")
        
        all_goals = goal_trades and goal_pf and goal_dd
        
        # Calculate score
        trade_score = 0
        if 50 <= metrics['total_trades'] <= 100:
            trade_score = 1.0 - abs(metrics['total_trades'] - 75) / 50
        elif metrics['total_trades'] > 30:
            trade_score = 0.5
        
        pf_score = min(metrics['profit_factor'] / 2.0, 1.0)
        dd_score = max(1.0 - (metrics['max_drawdown_pct'] / 10), 0)
        return_score = max(min(metrics['total_pnl'] / 3000, 1.0), -0.5)
        sharpe_score = max(min(metrics['sharpe_ratio'] / 3.0, 1.0), 0)
        
        score = (trade_score * 0.15 + 
                pf_score * 0.35 + 
                dd_score * 0.30 + 
                return_score * 0.10 +
                sharpe_score * 0.10)
        
        results.append({
            "name": cfg['name'],
            "params": cfg['params'],
            "metrics": metrics,
            "goals_met": all_goals,
            "score": score,
            "trades": trades,
            "equity_curve": equity_curve,
        })
        
        print(f"  Overall Score: {score:.3f}")
        print(f"  {'✅✅✅ ALL GOALS MET!' if all_goals else '⚠️  Partial success'}")
    
    # Summary
    print(f"\n{'='*70}")
    print("COMPREHENSIVE SUMMARY")
    print(f"{'='*70}\n")
    
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"{'Rank':<6} {'Configuration':<35} {'Score':<8}")
    print("-"*70)
    for i, r in enumerate(results, 1):
        m = r['metrics']
        goals_icon = "✅" if r['goals_met'] else "⚠️"
        print(f"{i:<6} {r['name']:<35} {r['score']:<8.3f}")
        print(f"       Trades: {m['total_trades']:<3} | WR: {m['win_rate']:>5.1f}% | "
              f"PF: {m['profit_factor']:>4.2f} | Return: {m['total_pnl']/config.initial_balance*100:>6.1f}% | "
              f"DD: {m['max_drawdown_pct']:>5.2f}% {goals_icon}")
    
    # Best result detailed view
    best = results[0]
    print(f"\n{'='*70}")
    print(f"🏆 BEST CONFIGURATION: {best['name']}")
    print(f"{'='*70}")
    
    print_backtest_results(best['params'], best['metrics'], best['trades'])
    
    # Equity curve analysis
    print(f"\n{'='*70}")
    print("EQUITY CURVE ANALYSIS")
    print(f"{'='*70}")
    
    eq = best['equity_curve']
    if eq:
        # Sample equity points
        samples = [0, len(eq)//4, len(eq)//2, 3*len(eq)//4, len(eq)-1]
        print(f"\n{'Date':<20} {'Balance':<12} {'Equity':<12} {'DD%':<8}")
        print("-"*55)
        for idx in samples:
            point = eq[idx]
            print(f"{str(point.timestamp):<20} ${point.balance:<11.2f} ${point.equity:<11.2f} {point.drawdown_percent:<7.2f}%")
        
        # Calculate smoothness
        if len(eq) > 1:
            returns = []
            for i in range(1, len(eq)):
                if eq[i-1].equity > 0:
                    ret = (eq[i].equity - eq[i-1].equity) / eq[i-1].equity
                    returns.append(ret)
            
            if returns:
                avg_return = sum(returns) / len(returns)
                variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
                std_dev = variance ** 0.5
                
                print(f"\n📈 Equity Curve Smoothness:")
                print(f"  Std Dev of Returns: {std_dev*100:.4f}%")
                print(f"  Average Return/Candle: {avg_return*100:.4f}%")
                print(f"  {'✅ Very smooth' if std_dev < 0.005 else ('✅ Smooth' if std_dev < 0.01 else '⚠️  Volatile')} equity curve")
    
    # Strategy distribution analysis
    print(f"\n{'='*70}")
    print("STRATEGY PERFORMANCE BY TYPE")
    print(f"{'='*70}")
    
    best_trades = best['trades']
    if best_trades:
        # Categorize trades by strategy (based on exit reason or other markers)
        exit_reasons = {}
        for t in best_trades:
            reason = t.close_reason
            if reason not in exit_reasons:
                exit_reasons[reason] = []
            exit_reasons[reason].append(t)
        
        print(f"\nExit Reason Distribution:")
        for reason, trades_list in sorted(exit_reasons.items(), key=lambda x: len(x[1]), reverse=True):
            count = len(trades_list)
            profitable = len([t for t in trades_list if t.profit_loss > 0])
            total_pnl = sum(t.profit_loss for t in trades_list)
            print(f"  {reason}: {count} ({count/len(best_trades)*100:.1f}%) | "
                  f"Winners: {profitable}/{count} | P&L: ${total_pnl:.2f}")
    
    client.close()
    
    # Final assessment
    print(f"\n{'='*70}")
    if best['goals_met']:
        print("✅✅✅ SUCCESS - ALL GOALS ACHIEVED!")
        print("\n🎉 The regime-based approach successfully:")
        print("  • Adapted to market conditions")
        print("  • Achieved profit factor > 1.5")
        print("  • Kept drawdown under 5%")
        print("  • Generated optimal trade frequency")
    else:
        print("⚠️  RESULTS SUMMARY")
        m = best['metrics']
        if not (50 <= m['total_trades'] <= 100):
            print(f"   Trade Frequency: {m['total_trades']} (target 50-100)")
        if m['profit_factor'] <= 1.5:
            print(f"   Profit Factor: {m['profit_factor']:.2f} (target >1.5)")
        if m['max_drawdown_pct'] >= 5.0:
            print(f"   Max Drawdown: {m['max_drawdown_pct']:.2f}% (target <5%)")
        
        if m['total_pnl'] > 0:
            print(f"\n✅ Strategy is PROFITABLE (+${m['total_pnl']:.2f})")
        else:
            print(f"\n❌ Strategy needs improvement")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(test_regime_based())
