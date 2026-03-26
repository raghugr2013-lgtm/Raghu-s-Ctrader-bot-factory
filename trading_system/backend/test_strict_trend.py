"""
Test Strict Trend-Following Strategy

Goals:
- Profit Factor > 1.5
- Max Drawdown < 5%
- 50-70 trades
- Smooth equity curve
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
from strict_trend_following import run_strict_trend_following
from test_eurusd_strategy import calculate_metrics, print_backtest_results

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')


async def test_strict_trend_following():
    """Test strict trend-following with parameter variations"""
    
    print("="*70)
    print("STRICT TREND-FOLLOWING EURUSD STRATEGY")
    print("="*70)
    print("\n🎯 Goals:")
    print("  - Profit Factor > 1.5")
    print("  - Max Drawdown < 5%")
    print("  - Trades: 50-70")
    print("  - Smooth equity curve")
    
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
            "name": "Conservative (SL 2.2, TP 3.5)",
            "params": {
                "stop_loss_atr_mult": 2.2,
                "take_profit_atr_mult": 3.5,
                "max_trades_per_day": 3,
                "rsi_pullback_long_max": 55,
                "rsi_pullback_short_min": 45,
            }
        },
        {
            "name": "Balanced (SL 2.0, TP 3.2)",
            "params": {
                "stop_loss_atr_mult": 2.0,
                "take_profit_atr_mult": 3.2,
                "max_trades_per_day": 3,
                "rsi_pullback_long_max": 60,
                "rsi_pullback_short_min": 40,
            }
        },
        {
            "name": "Tight Stops (SL 1.8, TP 3.0)",
            "params": {
                "stop_loss_atr_mult": 1.8,
                "take_profit_atr_mult": 3.0,
                "max_trades_per_day": 4,
                "trailing_activation_atr": 1.2,
                "trailing_distance_atr": 1.0,
            }
        },
        {
            "name": "More Selective (Narrow RSI)",
            "params": {
                "stop_loss_atr_mult": 2.0,
                "take_profit_atr_mult": 3.5,
                "rsi_pullback_long_min": 40,
                "rsi_pullback_long_max": 55,
                "rsi_pullback_short_min": 45,
                "rsi_pullback_short_max": 60,
                "max_trades_per_day": 2,
                "min_candles_between_trades": 4,
            }
        },
        {
            "name": "Optimal (Wider RSI, Good Risk/Reward)",
            "params": {
                "stop_loss_atr_mult": 2.0,
                "take_profit_atr_mult": 3.5,
                "rsi_pullback_long_min": 35,
                "rsi_pullback_long_max": 62,
                "rsi_pullback_short_min": 38,
                "rsi_pullback_short_max": 65,
                "max_trades_per_day": 4,
                "min_candles_between_trades": 2,
                "emergency_exit_atr": -1.2,
            }
        },
    ]
    
    results = []
    
    for i, cfg in enumerate(test_configs, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}/{len(test_configs)}: {cfg['name']}")
        print(f"{'='*70}")
        
        # Run backtest
        trades, equity_curve = run_strict_trend_following(candles, config, cfg['params'])
        
        # Calculate metrics
        metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
        
        # Display results
        print(f"\n📊 Results:")
        print(f"  Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.1f}%")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"  Total P&L: ${metrics['total_pnl']:.2f}")
        print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"  Expectancy: ${metrics['expectancy']:.2f}")
        
        # Check goals
        goal_trades = 50 <= metrics['total_trades'] <= 70
        goal_pf = metrics['profit_factor'] > 1.5
        goal_dd = metrics['max_drawdown_pct'] < 5.0
        
        print(f"\n🎯 Goal Achievement:")
        print(f"  {'✅' if goal_trades else '❌'} Trades (50-70): {metrics['total_trades']}")
        print(f"  {'✅' if goal_pf else '❌'} Profit Factor (>1.5): {metrics['profit_factor']:.2f}")
        print(f"  {'✅' if goal_dd else '❌'} Max Drawdown (<5%): {metrics['max_drawdown_pct']:.2f}%")
        
        all_goals = goal_trades and goal_pf and goal_dd
        
        # Calculate comprehensive score
        trade_score = 0
        if 50 <= metrics['total_trades'] <= 70:
            trade_score = 1.0 - abs(metrics['total_trades'] - 60) / 20  # Optimal at 60
        elif metrics['total_trades'] > 40:
            trade_score = 0.5
        
        pf_score = min(metrics['profit_factor'] / 2.0, 1.0)
        dd_score = max(1.0 - (metrics['max_drawdown_pct'] / 10), 0)
        pnl_score = max(min(metrics['total_pnl'] / 3000, 1.0), -0.5)
        sharpe_score = max(min(metrics['sharpe_ratio'] / 3.0, 1.0), 0)
        
        score = (trade_score * 0.20 + 
                pf_score * 0.30 + 
                dd_score * 0.30 + 
                pnl_score * 0.10 +
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
              f"PF: {m['profit_factor']:>4.2f} | P&L: ${m['total_pnl']:>8.2f} | "
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
        
        # Calculate smoothness (variance of returns)
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
                print(f"  {'✅ Smooth' if std_dev < 0.01 else '⚠️  Volatile'} equity curve")
    
    # Trade distribution analysis
    print(f"\n{'='*70}")
    print("TRADE DISTRIBUTION")
    print(f"{'='*70}")
    
    best_trades = best['trades']
    if best_trades:
        longs = [t for t in best_trades if t.direction.value == "BUY"]
        shorts = [t for t in best_trades if t.direction.value == "SELL"]
        
        print(f"\nDirection Split:")
        print(f"  LONG: {len(longs)} trades ({len(longs)/len(best_trades)*100:.1f}%)")
        print(f"  SHORT: {len(shorts)} trades ({len(shorts)/len(best_trades)*100:.1f}%)")
        
        # Exit reason distribution
        exit_reasons = {}
        for t in best_trades:
            reason = t.close_reason
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        print(f"\nExit Reasons:")
        for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
            print(f"  {reason}: {count} ({count/len(best_trades)*100:.1f}%)")
    
    client.close()
    
    # Final assessment
    print(f"\n{'='*70}")
    if best['goals_met']:
        print("✅✅✅ SUCCESS - ALL GOALS ACHIEVED!")
    else:
        print("⚠️  PARTIAL SUCCESS - Some goals not met")
        m = best['metrics']
        if not (50 <= m['total_trades'] <= 70):
            print(f"   - Adjust trade frequency: {m['total_trades']} trades")
        if m['profit_factor'] <= 1.5:
            print(f"   - Improve profit factor: {m['profit_factor']:.2f}")
        if m['max_drawdown_pct'] >= 5.0:
            print(f"   - Reduce drawdown: {m['max_drawdown_pct']:.2f}%")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(test_strict_trend_following())
