#!/usr/bin/env python3
"""
Test improved strategy with execution costs
"""
import sys
sys.path.append('/app/trading_system/backend')

from phase4_improved_strategy import ImprovedEMAStrategy
from phase3_execution_simulator import ExecutionSimulator
import pandas as pd
import json

# Load data
csv_path = "/app/trading_system/data/EURUSD_H1.csv"
df = pd.read_csv(csv_path)
df['timestamp'] = pd.to_datetime(df['timestamp'])

print("\n" + "="*80)
print("IMPROVED STRATEGY WITH EXECUTION COSTS")
print("="*80)
print()

# Run improved strategy
strategy = ImprovedEMAStrategy(df, ema_fast=10, ema_slow=150, risk_pct=0.5)
trades, signal_df = strategy.run()

print(f"📊 Generated {len(trades)} high-quality trades")
print()

# Simulate execution with costs
print("💰 Simulating with real-world execution costs...")
simulator = ExecutionSimulator(
    initial_balance=10000,
    spread_pips=1.5,
    commission=0,
    slippage_pips_range=(0.5, 1.0)
)

enhanced_trades, final_balance = simulator.simulate_trades(df, trades, risk_pct=0.5)
metrics = simulator.calculate_metrics(enhanced_trades, final_balance)

print()
print("="*80)
print("FINAL RESULTS (After All Costs)")
print("="*80)
print()

print(f"💵 Account Performance:")
print(f"   Initial Balance:  ${metrics['initial_balance']:,.2f}")
print(f"   Final Balance:    ${metrics['final_balance']:,.2f}")
print(f"   Net Return:       {metrics['net_return_pct']:+.2f}% (${metrics['net_return_dollars']:+,.2f})")
print(f"   Peak Balance:     ${metrics['peak_balance']:,.2f}")
print(f"   Max Drawdown:     {metrics['max_drawdown_pct']:.2f}%")
print()

print(f"📈 Trade Statistics:")
print(f"   Total Trades:     {metrics['total_trades']}")
print(f"   Winning Trades:   {metrics['winning_trades']} ({metrics['win_rate_pct']:.1f}%)")
print(f"   Losing Trades:    {metrics['losing_trades']}")
print(f"   Profit Factor:    {metrics['profit_factor']:.2f}")
print(f"   Average Win:      ${metrics['avg_win']:,.2f}")
print(f"   Average Loss:     ${metrics['avg_loss']:,.2f}")
print()

print(f"💸 Trading Costs:")
print(f"   Total Costs:      ${metrics['total_costs']:,.2f} ({(metrics['total_costs']/10000)*100:.2f}% of capital)")
print()

print(f"📊 Risk Metrics:")
print(f"   Sharpe-like Ratio: {metrics['sharpe_like_ratio']:.3f}")
print(f"   Return/DD Ratio:   {(metrics['net_return_pct']/metrics['max_drawdown_pct']):.2f}")
print()

# Compare with baseline
print("="*80)
print("COMPARISON: Baseline vs Improved")
print("="*80)
print()

baseline = {
    'trades': 93,
    'pf': 1.05,
    'return': 1.10,
    'dd': 7.12,
    'costs': 143
}

improved = {
    'trades': metrics['total_trades'],
    'pf': metrics['profit_factor'],
    'return': metrics['net_return_pct'],
    'dd': metrics['max_drawdown_pct'],
    'costs': metrics['total_costs']
}

print(f"{'Metric':<20} {'Baseline':>12} {'Improved':>12} {'Change':>12}")
print("-" * 60)
print(f"{'Trades':<20} {baseline['trades']:>12} {improved['trades']:>12} {improved['trades']-baseline['trades']:>+12}")
print(f"{'Profit Factor':<20} {baseline['pf']:>12.2f} {improved['pf']:>12.2f} {improved['pf']-baseline['pf']:>+12.2f}")
print(f"{'Return %':<20} {baseline['return']:>12.2f} {improved['return']:>12.2f} {improved['return']-baseline['return']:>+12.2f}")
print(f"{'Max DD %':<20} {baseline['dd']:>12.2f} {improved['dd']:>12.2f} {improved['dd']-baseline['dd']:>+12.2f}")
print(f"{'Total Costs $':<20} {baseline['costs']:>12.0f} {improved['costs']:>12.0f} {improved['costs']-baseline['costs']:>+12.0f}")
print()

improvement_pct = ((improved['return'] - baseline['return']) / baseline['return']) * 100 if baseline['return'] > 0 else 0
print(f"📈 Overall Improvement: {improvement_pct:+.1f}%")
print()

print("="*80)

# Save results
results = {
    'improved_metrics': metrics,
    'baseline_metrics': baseline,
    'improvement_pct': improvement_pct
}

with open('/app/trading_system/backend/improved_vs_baseline.json', 'w') as f:
    json.dump(results, f, indent=2)

print("💾 Comparison saved to: /app/trading_system/backend/improved_vs_baseline.json")
print()

