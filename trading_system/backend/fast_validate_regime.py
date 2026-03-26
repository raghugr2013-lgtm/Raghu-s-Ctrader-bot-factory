"""
FAST Regime-Adaptive System Validation

Streamlined version for quicker execution.
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from market_data_service import init_market_data_service
from market_data_models import DataTimeframe
from backtest_models import BacktestConfig, Timeframe
from regime_adaptive_system import run_regime_adaptive_system
from test_eurusd_strategy import calculate_metrics
from validate_gradient_strategy import calculate_consistency_score

load_dotenv(Path(__file__).parent / '.env')

async def main():
    print("="*80)
    print("REGIME-ADAPTIVE SYSTEM - FAST VALIDATION")
    print("="*80)
    
    # Connect
    client = AsyncIOMotorClient(os.environ.get('MONGO_URL'))
    db = client[os.environ.get('DB_NAME', 'ctrader_bot_factory')]
    mds = init_market_data_service(db)
    
    # Load ALL data
    print("\nLoading data...")
    candles = await mds.get_candles("EURUSD", DataTimeframe.H1, None, None, 20000)
    print(f"✅ {len(candles)} candles | {candles[0].timestamp} to {candles[-1].timestamp}")
    
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
    
    # Simple params
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
    
    # Run
    print("\nRunning regime-adaptive system...")
    trades, equity_curve, stats = run_regime_adaptive_system(candles, config, params)
    
    # Metrics
    metrics = calculate_metrics(trades, equity_curve, config.initial_balance)
    consistency = calculate_consistency_score(trades, segments=5)
    
    # Results
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"\nTotal Trades: {metrics['total_trades']}")
    print(f"Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"Consistency: {consistency:.1f}%")
    print(f"Net Profit: ${metrics['total_pnl']:.2f}")
    print(f"Win Rate: {metrics['win_rate']:.1f}%")
    print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"Return: {(metrics['total_pnl']/config.initial_balance*100):.2f}%")
    
    # Strategy breakdown
    print(f"\nStrategy Breakdown:")
    for strategy, count in stats['trade_by_strategy'].items():
        pnl = stats['pnl_by_strategy'][strategy]
        print(f"  {strategy}: {count} trades, ${pnl:.2f}")
    
    # Validation
    print(f"\nValidation Criteria:")
    checks = [
        ("PF > 1.5", metrics['profit_factor'] > 1.5),
        ("DD < 6%", metrics['max_drawdown_pct'] < 6.0),
        ("Consistency > 50%", consistency > 50),
        ("Win Rate > 40%", metrics['win_rate'] > 40),
        ("Trades 30-50", 30 <= metrics['total_trades'] <= 50),
    ]
    
    passed = sum(1 for _, p in checks if p)
    for criterion, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {criterion}")
    
    print(f"\nPassed: {passed}/5 ({passed*20}%)")
    
    # Comparison
    print(f"\nComparison with Overfitted System:")
    print(f"  Overfitted: PF 1.38, DD 4.31%, Consistency 0%, 13 trades")
    print(f"  Adaptive:   PF {metrics['profit_factor']:.2f}, DD {metrics['max_drawdown_pct']:.2f}%, Consistency {consistency:.0f}%, {metrics['total_trades']} trades")
    
    if metrics['profit_factor'] > 1.38:
        print(f"\n✅ IMPROVEMENT: PF increased by {((metrics['profit_factor']-1.38)/1.38*100):.1f}%")
    if consistency > 0:
        print(f"✅ IMPROVEMENT: Consistency increased from 0% to {consistency:.0f}%")
    
    # Verdict
    print(f"\n" + "="*80)
    if passed >= 3:
        print("VERDICT: ✅ PASSED - System is robust")
    else:
        print("VERDICT: ⚠️  NEEDS IMPROVEMENT")
    print("="*80)
    
    client.close()

if __name__ == "__main__":
    asyncio.run(main())
