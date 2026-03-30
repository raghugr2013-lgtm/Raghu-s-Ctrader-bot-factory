#!/usr/bin/env python3
"""
TASK 2: Baseline Backtest Execution
Run existing strategies on clean data with realistic conditions
"""

import pandas as pd
import sys
sys.path.append('/app/trading_system/backend')

from strategy_backtest_framework import SimpleBacktester, BacktestConfig, print_backtest_results
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def load_clean_data(symbol):
    """Load clean CSV data"""
    filepath = f'/tmp/{symbol.lower()}_h1_clean.csv'
    df = pd.read_csv(filepath)
    df['time'] = pd.to_datetime(df['time'], format='mixed')
    df = df.set_index('time')
    return df

def run_baseline_backtests():
    """
    TASK 2: Run baseline backtests on both symbols
    """
    print("\n" + "="*70)
    print("TASK 2: BASELINE BACKTEST (STRICT - NO CHANGES)")
    print("="*70)
    
    # Configuration with realistic conditions
    config = BacktestConfig(
        initial_balance=10000,
        position_size=0.01,  # 0.01 lots (micro lot)
        spread_pips=2.0,     # 2 pip spread
        slippage_pips=1.0,   # 1 pip slippage
        commission_per_lot=7.0  # $7 per lot commission
    )
    
    print("\n⚙️  REALISTIC CONDITIONS:")
    print(f"   Initial Balance: ${config.initial_balance}")
    print(f"   Position Size: {config.position_size} lots")
    print(f"   Spread: {config.spread_pips} pips")
    print(f"   Slippage: {config.slippage_pips} pip")
    print(f"   Commission: ${config.commission_per_lot} per lot")
    
    results = {}
    
    # Test both symbols
    for symbol in ['EURUSD', 'XAUUSD']:
        print(f"\n{'='*70}")
        print(f"TESTING {symbol}")
        print(f"{'='*70}")
        
        # Load data
        df = load_clean_data(symbol)
        logger.info(f"Loaded {len(df)} candles for {symbol}")
        
        # Initialize backtester
        backtester = SimpleBacktester(df, config, symbol)
        backtester.calculate_indicators()
        
        # Strategy 1: Trend Following
        print(f"\n--- Strategy 1: Trend Following (EMA 20/50 Cross) ---")
        trend_signals = backtester.trend_following_strategy()
        trend_result = backtester.execute_backtest(trend_signals, "Trend Following")
        print_backtest_results(trend_result)
        
        results[f"{symbol}_trend"] = trend_result
        
        # Strategy 2: Mean Reversion
        print(f"\n--- Strategy 2: Mean Reversion (Bollinger Bands) ---")
        mean_reversion_signals = backtester.mean_reversion_strategy()
        mr_result = backtester.execute_backtest(mean_reversion_signals, "Mean Reversion")
        print_backtest_results(mr_result)
        
        results[f"{symbol}_mean_reversion"] = mr_result
    
    # Overall Summary
    print(f"\n{'='*70}")
    print("📋 BASELINE SUMMARY - ALL STRATEGIES")
    print(f"{'='*70}")
    
    for key, result in results.items():
        symbol = result.symbol
        strategy = result.strategy_name
        pf = result.profit_factor
        trades = result.total_trades
        wr = result.win_rate
        dd = result.max_drawdown_pct
        
        # Status
        if pf > 1.3 and 30 <= trades <= 60 and wr > 40 and dd < 20:
            status = "✅ PASS"
        elif pf > 1.0:
            status = "⚠️  NEEDS IMPROVEMENT"
        else:
            status = "❌ FAIL"
        
        print(f"\n{symbol} - {strategy}: {status}")
        print(f"   PF: {pf:.2f} | Trades: {trades} | WR: {wr:.1f}% | DD: {dd:.1f}%")
    
    print(f"\n{'='*70}")
    print("✅ TASK 2 COMPLETE - Baseline results captured")
    print(f"{'='*70}")
    
    return results


if __name__ == '__main__':
    results = run_baseline_backtests()
