"""
EURUSD Strategy Backtest & Optimization

Tests the improved EURUSD strategy with Dukascopy data and optimizes parameters.
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from auto_fetch_candles import auto_fetch_candles, MIN_CANDLES_REQUIRED
from market_data_service import init_market_data_service
from backtest_models import BacktestConfig, Timeframe
from improved_eurusd_strategy import run_improved_eurusd_strategy

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')


def calculate_metrics(trades, equity_curve, initial_balance):
    """Calculate comprehensive performance metrics"""
    if not trades:
        return {
            "total_trades": 0,
            "profitable_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "expectancy": 0.0,
        }
    
    # Basic trade statistics
    total_trades = len(trades)
    profitable = [t for t in trades if t.profit_loss > 0]
    losing = [t for t in trades if t.profit_loss < 0]
    
    profitable_trades = len(profitable)
    losing_trades = len(losing)
    win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Profit factor
    gross_profit = sum(t.profit_loss for t in profitable) if profitable else 0
    gross_loss = abs(sum(t.profit_loss for t in losing)) if losing else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (10.0 if gross_profit > 0 else 0.0)
    
    # PnL
    total_pnl = sum(t.profit_loss for t in trades)
    
    # Drawdown
    max_dd_pct = max((ep.drawdown_percent for ep in equity_curve), default=0.0)
    
    # Sharpe ratio (simplified)
    returns = [t.profit_loss for t in trades]
    if len(returns) > 1:
        avg_return = sum(returns) / len(returns)
        std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
        sharpe_ratio = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0.0
    else:
        sharpe_ratio = 0.0
    
    # Win/loss analysis
    avg_win = (sum(t.profit_loss for t in profitable) / len(profitable)) if profitable else 0.0
    avg_loss = (sum(t.profit_loss for t in losing) / len(losing)) if losing else 0.0
    largest_win = max((t.profit_loss for t in profitable), default=0.0)
    largest_loss = min((t.profit_loss for t in losing), default=0.0)
    
    # Expectancy
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)
    
    return {
        "total_trades": total_trades,
        "profitable_trades": profitable_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_pnl": total_pnl,
        "max_drawdown_pct": max_dd_pct,
        "sharpe_ratio": sharpe_ratio,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "largest_win": largest_win,
        "largest_loss": largest_loss,
        "expectancy": expectancy,
    }


def print_backtest_results(params: Dict, metrics: Dict, trades: List):
    """Pretty print backtest results"""
    print("\n" + "="*70)
    print("BACKTEST RESULTS")
    print("="*70)
    
    print("\n📊 PARAMETERS:")
    for key, value in params.items():
        print(f"  {key}: {value}")
    
    print("\n📈 PERFORMANCE METRICS:")
    print(f"  Total Trades: {metrics['total_trades']}")
    print(f"  Profitable: {metrics['profitable_trades']} ({metrics['win_rate']:.1f}%)")
    print(f"  Losing: {metrics['losing_trades']}")
    print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"  Total P&L: ${metrics['total_pnl']:.2f}")
    print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    
    print("\n💰 WIN/LOSS ANALYSIS:")
    print(f"  Average Win: ${metrics['avg_win']:.2f}")
    print(f"  Average Loss: ${metrics['avg_loss']:.2f}")
    print(f"  Largest Win: ${metrics['largest_win']:.2f}")
    print(f"  Largest Loss: ${metrics['largest_loss']:.2f}")
    print(f"  Expectancy: ${metrics['expectancy']:.2f}")
    
    # Goal checks
    print("\n🎯 GOAL CHECKS:")
    goal_trades = 50 <= metrics['total_trades'] <= 120
    goal_pf = metrics['profit_factor'] > 1.5
    goal_dd = metrics['max_drawdown_pct'] < 5.0
    
    print(f"  {'✅' if goal_trades else '❌'} Trades in range (50-120): {metrics['total_trades']}")
    print(f"  {'✅' if goal_pf else '❌'} Profit Factor > 1.5: {metrics['profit_factor']:.2f}")
    print(f"  {'✅' if goal_dd else '❌'} Drawdown < 5%: {metrics['max_drawdown_pct']:.2f}%")
    
    all_goals = goal_trades and goal_pf and goal_dd
    print(f"\n{'✅✅✅ ALL GOALS MET!' if all_goals else '⚠️  Some goals not met'}")
    
    # Show sample trades
    if trades:
        print("\n📋 FIRST 10 TRADES:")
        for i, trade in enumerate(trades[:10], 1):
            direction = "BUY " if trade.direction.value == "BUY" else "SELL"
            pnl_sign = "+" if trade.profit_loss > 0 else ""
            print(f"  {i:2d}. {direction} | Entry: {trade.entry_price:.5f} | Exit: {trade.exit_price:.5f} | "
                  f"P&L: {pnl_sign}${trade.profit_loss:.2f} ({pnl_sign}{trade.profit_loss_pips:.1f} pips) | "
                  f"{trade.close_reason}")
    
    print("="*70)
    
    return all_goals


async def test_single_configuration(params: Dict = None):
    """Test a single parameter configuration"""
    
    print("="*70)
    print("EURUSD STRATEGY BACKTEST - DUKASCOPY DATA")
    print("="*70)
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Fetch EURUSD 1h data
    symbol = "EURUSD"
    timeframe = "1h"
    
    print(f"\n📊 Fetching {symbol} {timeframe} data from Dukascopy cache...")
    
    result = await auto_fetch_candles(
        db=db,
        market_data_service=market_data_service,
        symbol=symbol,
        timeframe=timeframe,
        min_candles=MIN_CANDLES_REQUIRED
    )
    
    if not result.success:
        print(f"❌ Failed to fetch data: {result.error}")
        client.close()
        return False
    
    print(f"✅ Fetched {result.candle_count} candles from {result.source}")
    
    candles = result.candles
    
    # Create backtest config
    config = BacktestConfig(
        symbol=symbol,
        timeframe=Timeframe.H1,
        start_date=candles[0].timestamp,
        end_date=candles[-1].timestamp,
        initial_balance=10000.0,
        spread_pips=1.5,
        commission_per_lot=7.0,
        leverage=100,
    )
    
    print(f"\n⚙️  Backtest Configuration:")
    print(f"  Period: {config.start_date} to {config.end_date}")
    print(f"  Initial Balance: ${config.initial_balance:.2f}")
    print(f"  Spread: {config.spread_pips} pips")
    
    # Run backtest
    print(f"\n🚀 Running backtest...")
    
    trades, equity_curve = run_improved_eurusd_strategy(candles, config, params)
    
    # Calculate metrics
    metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
    
    # Print results
    all_goals = print_backtest_results(params or {}, metrics, trades)
    
    client.close()
    
    return all_goals


async def optimize_parameters():
    """Test multiple parameter configurations to find optimal settings"""
    
    print("="*70)
    print("EURUSD STRATEGY OPTIMIZATION")
    print("="*70)
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Fetch data once
    print(f"\n📊 Fetching EURUSD 1h data...")
    
    result = await auto_fetch_candles(
        db=db,
        market_data_service=market_data_service,
        symbol="EURUSD",
        timeframe="1h",
        min_candles=MIN_CANDLES_REQUIRED
    )
    
    if not result.success:
        print(f"❌ Failed to fetch data: {result.error}")
        client.close()
        return
    
    print(f"✅ Fetched {result.candle_count} candles")
    
    candles = result.candles
    
    # Configuration
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
    
    # Parameter configurations to test
    configurations = [
        # Base configuration (moderate)
        {
            "name": "Base Strategy",
            "params": {
                "rsi_buy_min": 35,
                "rsi_buy_max": 45,
                "rsi_sell_min": 55,
                "rsi_sell_max": 65,
                "stop_loss_atr_mult": 2.0,
                "take_profit_atr_mult": 3.0,
                "max_trades_per_day": 5,
            }
        },
        # More aggressive entries
        {
            "name": "Aggressive",
            "params": {
                "rsi_buy_min": 30,
                "rsi_buy_max": 50,
                "rsi_sell_min": 50,
                "rsi_sell_max": 70,
                "stop_loss_atr_mult": 1.5,
                "take_profit_atr_mult": 3.5,
                "max_trades_per_day": 7,
            }
        },
        # Conservative (quality over quantity)
        {
            "name": "Conservative",
            "params": {
                "rsi_buy_min": 38,
                "rsi_buy_max": 42,
                "rsi_sell_min": 58,
                "rsi_sell_max": 62,
                "stop_loss_atr_mult": 2.5,
                "take_profit_atr_mult": 4.0,
                "max_trades_per_day": 3,
            }
        },
        # Wide RSI, tight stops
        {
            "name": "Wide RSI + Tight Stops",
            "params": {
                "rsi_buy_min": 32,
                "rsi_buy_max": 48,
                "rsi_sell_min": 52,
                "rsi_sell_max": 68,
                "stop_loss_atr_mult": 1.8,
                "take_profit_atr_mult": 3.5,
                "max_trades_per_day": 6,
            }
        },
        # Balanced
        {
            "name": "Balanced",
            "params": {
                "rsi_buy_min": 37,
                "rsi_buy_max": 43,
                "rsi_sell_min": 57,
                "rsi_sell_max": 63,
                "stop_loss_atr_mult": 2.2,
                "take_profit_atr_mult": 3.2,
                "max_trades_per_day": 4,
            }
        },
    ]
    
    results = []
    
    for i, cfg in enumerate(configurations, 1):
        print(f"\n{'='*70}")
        print(f"CONFIGURATION {i}/{len(configurations)}: {cfg['name']}")
        print(f"{'='*70}")
        
        # Run backtest
        trades, equity_curve = run_improved_eurusd_strategy(candles, config, cfg['params'])
        
        # Calculate metrics
        metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
        
        # Print summary
        print(f"\n📊 Results:")
        print(f"  Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.1f}%")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"  Total P&L: ${metrics['total_pnl']:.2f}")
        print(f"  Max DD: {metrics['max_drawdown_pct']:.2f}%")
        
        # Check goals
        goal_trades = 50 <= metrics['total_trades'] <= 120
        goal_pf = metrics['profit_factor'] > 1.5
        goal_dd = metrics['max_drawdown_pct'] < 5.0
        all_goals = goal_trades and goal_pf and goal_dd
        
        print(f"  Goals Met: {'✅ YES' if all_goals else '❌ NO'}")
        
        results.append({
            "name": cfg['name'],
            "params": cfg['params'],
            "metrics": metrics,
            "goals_met": all_goals,
            "score": metrics['profit_factor'] * (1 - metrics['max_drawdown_pct'] / 100) * (metrics['total_trades'] / 100)
        })
    
    # Summary
    print(f"\n{'='*70}")
    print("OPTIMIZATION SUMMARY")
    print(f"{'='*70}\n")
    
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"{'Rank':<5} {'Configuration':<25} {'Trades':<8} {'PF':<6} {'DD%':<6} {'P&L':<10} {'Goals':<6} {'Score':<8}")
    print("-"*70)
    
    for i, r in enumerate(results, 1):
        goals_str = "✅" if r['goals_met'] else "❌"
        print(f"{i:<5} {r['name']:<25} {r['metrics']['total_trades']:<8} "
              f"{r['metrics']['profit_factor']:<6.2f} {r['metrics']['max_drawdown_pct']:<6.2f} "
              f"${r['metrics']['total_pnl']:<9.2f} {goals_str:<6} {r['score']:<8.3f}")
    
    print(f"\n{'='*70}")
    print(f"🏆 BEST CONFIGURATION: {results[0]['name']}")
    print(f"{'='*70}")
    print_backtest_results(results[0]['params'], results[0]['metrics'], [])
    
    client.close()


async def main():
    """Main entry point"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "optimize":
        await optimize_parameters()
    else:
        # Test single configuration
        params = {
            "rsi_buy_min": 35,
            "rsi_buy_max": 45,
            "rsi_sell_min": 55,
            "rsi_sell_max": 65,
            "stop_loss_atr_mult": 2.0,
            "take_profit_atr_mult": 3.0,
            "max_trades_per_day": 5,
        }
        await test_single_configuration(params)


if __name__ == "__main__":
    asyncio.run(main())
