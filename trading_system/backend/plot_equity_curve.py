#!/usr/bin/env python3
"""
Plot equity curve from execution simulation
"""
import json
import pandas as pd

# Load results
with open('/app/trading_system/backend/execution_simulation_results.json', 'r') as f:
    results = json.load(f)

equity_curve = results['equity_curve']
metrics = results['metrics']

# Create DataFrame
df = pd.DataFrame(equity_curve)
df['timestamp'] = pd.to_datetime(df['timestamp'])

print("\n" + "="*80)
print("EQUITY CURVE ANALYSIS")
print("="*80)
print()

# Summary stats
print(f"📊 Equity Curve Statistics:")
print(f"   Starting Balance: ${metrics['initial_balance']:,.2f}")
print(f"   Ending Balance:   ${metrics['final_balance']:,.2f}")
print(f"   Peak Balance:     ${metrics['peak_balance']:,.2f}")
print(f"   Number of Points: {len(df)}")
print()

# Drawdown analysis
max_dd_point = df.loc[df['drawdown_pct'].idxmax()]
print(f"💔 Maximum Drawdown Event:")
print(f"   Drawdown: {max_dd_point['drawdown_pct']:.2f}%")
print(f"   Balance: ${max_dd_point['balance']:,.2f}")
print(f"   Timestamp: {max_dd_point['timestamp']}")
print()

# Recovery analysis
final_from_peak = ((df.iloc[-1]['balance'] - metrics['peak_balance']) / metrics['peak_balance']) * 100
print(f"📈 Recovery Status:")
print(f"   Current vs Peak: {final_from_peak:+.2f}%")
if df.iloc[-1]['balance'] >= metrics['peak_balance']:
    print(f"   Status: ✅ At new high")
else:
    print(f"   Status: ⚠️ Below peak by ${metrics['peak_balance'] - df.iloc[-1]['balance']:.2f}")
print()

# Show first and last 5 equity points
print("📅 First 5 Equity Points:")
print(df.head(5).to_string(index=False))
print()

print("📅 Last 5 Equity Points:")
print(df.tail(5).to_string(index=False))
print()

print("="*80)

