#!/usr/bin/env python3
"""
Phase 2D: Robustness Testing (DEBUG VERSION)
Verify train/test split and independent evaluation
"""
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
import pandas as pd

class RobustnessTesterDebug:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        
        print("\n" + "="*80)
        print("PHASE 2D: ROBUSTNESS TESTING (DEBUG MODE)")
        print("="*80)
        print(f"\nOriginal Dataset: {csv_path}")
        print(f"Total candles: {len(self.df)}")
        print(f"Period: {self.df['timestamp'].min()} to {self.df['timestamp'].max()}")
        print(f"Price range: {self.df['close'].min():.5f} to {self.df['close'].max():.5f}")
        print()
    
    def train_test_split(self, train_pct=0.70):
        """Split data into train and test sets with verification"""
        split_idx = int(len(self.df) * train_pct)
        
        train_df = self.df.iloc[:split_idx].copy()
        test_df = self.df.iloc[split_idx:].copy()
        
        print(f"📊 Train/Test Split ({int(train_pct*100)}/{int((1-train_pct)*100)})")
        print(f"   Split index: {split_idx}")
        print()
        
        print("TRAIN SET:")
        print(f"   Candles: {len(train_df)}")
        print(f"   Period: {train_df['timestamp'].min()} to {train_df['timestamp'].max()}")
        print(f"   Price range: {train_df['close'].min():.5f} to {train_df['close'].max():.5f}")
        print(f"   First 3 timestamps:")
        for ts in train_df['timestamp'].head(3):
            print(f"      {ts}")
        print(f"   Last 3 timestamps:")
        for ts in train_df['timestamp'].tail(3):
            print(f"      {ts}")
        print()
        
        print("TEST SET:")
        print(f"   Candles: {len(test_df)}")
        print(f"   Period: {test_df['timestamp'].min()} to {test_df['timestamp'].max()}")
        print(f"   Price range: {test_df['close'].min():.5f} to {test_df['close'].max():.5f}")
        print(f"   First 3 timestamps:")
        for ts in test_df['timestamp'].head(3):
            print(f"      {ts}")
        print(f"   Last 3 timestamps:")
        for ts in test_df['timestamp'].tail(3):
            print(f"      {ts}")
        print()
        
        # Verify no overlap
        train_dates = set(train_df['timestamp'])
        test_dates = set(test_df['timestamp'])
        overlap = train_dates.intersection(test_dates)
        
        if overlap:
            print(f"❌ WARNING: {len(overlap)} overlapping timestamps found!")
            print("   This indicates data leakage!")
        else:
            print(f"✅ Verified: No overlap between train and test datasets")
        print()
        
        # Save splits with unique names to avoid caching
        train_path = "/tmp/train_data_debug.csv"
        test_path = "/tmp/test_data_debug.csv"
        
        train_df.to_csv(train_path, index=False)
        test_df.to_csv(test_path, index=False)
        
        # Verify files were written correctly
        train_verify = pd.read_csv(train_path)
        test_verify = pd.read_csv(test_path)
        
        print(f"✅ Train file saved: {len(train_verify)} candles")
        print(f"✅ Test file saved: {len(test_verify)} candles")
        print()
        
        return train_path, test_path
    
    def run_optimization(self, data_path: str, phase_name: str):
        """Run optimizer on specified data with verification"""
        print(f"🔄 Running optimization on {phase_name} data...")
        print(f"   Input file: {data_path}")
        
        # Verify input data
        verify_df = pd.read_csv(data_path)
        print(f"   Verified: {len(verify_df)} candles in input")
        print(f"   Date range: {verify_df['timestamp'].min()} to {verify_df['timestamp'].max()}")
        
        cmd = [
            sys.executable,
            "/app/trading_system/backend/phase2a_optimizer.py",
            "--csv", data_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            print(f"❌ Optimization failed")
            print(f"   Error: {result.stderr[-500:]}")
            return None
        
        # Load results
        results_path = "/app/trading_system/backend/results.json"
        with open(results_path, 'r') as f:
            results = json.load(f)
        
        # Verify results match input data
        data_info = results.get('optimization_run', {}).get('data_info', {})
        result_candles = data_info.get('candles', 0)
        
        print(f"✅ {phase_name} optimization complete")
        print(f"   Results show: {result_candles} candles processed")
        
        if result_candles != len(verify_df):
            print(f"   ⚠️ WARNING: Candle count mismatch!")
            print(f"   Input: {len(verify_df)}, Results: {result_candles}")
        
        print()
        
        return results
    
    def compare_specific_strategy(self, train_results, test_results, strategy_id="trend_ema20_150_adx20"):
        """Deep dive into one strategy to verify correctness"""
        print("\n" + "="*80)
        print(f"DETAILED VERIFICATION: {strategy_id}")
        print("="*80)
        print()
        
        # Extract strategy from both results
        train_strategies = train_results.get('all_results', [])
        test_strategies = test_results.get('all_results', [])
        
        train_strat = next((s for s in train_strategies if s['variation_id'] == strategy_id), None)
        test_strat = next((s for s in test_strategies if s['variation_id'] == strategy_id), None)
        
        if not train_strat or not test_strat:
            print(f"❌ Strategy {strategy_id} not found in results")
            return
        
        print("TRAIN PERFORMANCE:")
        print(f"   PF: {train_strat['performance']['profit_factor']}")
        print(f"   Trades: {train_strat['performance']['total_trades']}")
        print(f"   Win Rate: {train_strat['performance']['win_rate']:.2f}%")
        print(f"   Net P&L: ${train_strat['performance']['net_pnl']:.2f}")
        print(f"   Return: {train_strat['performance']['return_pct']:.2f}%")
        print(f"   Max DD: {train_strat['performance']['max_drawdown_pct']:.2f}%")
        print()
        
        print("TEST PERFORMANCE:")
        print(f"   PF: {test_strat['performance']['profit_factor']}")
        print(f"   Trades: {test_strat['performance']['total_trades']}")
        print(f"   Win Rate: {test_strat['performance']['win_rate']:.2f}%")
        print(f"   Net P&L: ${test_strat['performance']['net_pnl']:.2f}")
        print(f"   Return: {test_strat['performance']['return_pct']:.2f}%")
        print(f"   Max DD: {test_strat['performance']['max_drawdown_pct']:.2f}%")
        print()
        
        # Calculate differences
        pf_diff = test_strat['performance']['profit_factor'] - train_strat['performance']['profit_factor']
        trades_diff = test_strat['performance']['total_trades'] - train_strat['performance']['total_trades']
        return_diff = test_strat['performance']['return_pct'] - train_strat['performance']['return_pct']
        
        print("DIFFERENCES (Test - Train):")
        print(f"   PF Delta: {pf_diff:+.3f} ({abs(pf_diff/train_strat['performance']['profit_factor']*100):.1f}%)")
        print(f"   Trades Delta: {trades_diff:+d}")
        print(f"   Return Delta: {return_diff:+.2f}%")
        print()
        
        if pf_diff == 0 and trades_diff == 0:
            print("❌ CRITICAL: Identical results detected!")
            print("   This indicates data leakage or caching issue")
        else:
            print("✅ Results differ - evaluation appears independent")
        
        print()

def main():
    csv_path = "/app/trading_system/data/EURUSD_H1.csv"
    
    tester = RobustnessTesterDebug(csv_path)
    
    # 1. Train/Test Split with verification
    train_path, test_path = tester.train_test_split(train_pct=0.70)
    
    # 2. Run optimization on train data
    print("="*80)
    print("PHASE 1: TRAIN OPTIMIZATION")
    print("="*80)
    print()
    train_results = tester.run_optimization(train_path, "TRAIN")
    if not train_results:
        print("❌ Train optimization failed")
        return
    
    # 3. Run optimization on test data (independent)
    print("="*80)
    print("PHASE 2: TEST OPTIMIZATION")
    print("="*80)
    print()
    test_results = tester.run_optimization(test_path, "TEST")
    if not test_results:
        print("❌ Test optimization failed")
        return
    
    # 4. Deep verification of one strategy
    tester.compare_specific_strategy(train_results, test_results, "trend_ema20_150_adx20")
    
    # 5. Summary comparison
    print("="*80)
    print("SUMMARY COMPARISON (Top 5 Strategies)")
    print("="*80)
    print()
    
    train_strategies = sorted(train_results.get('all_results', []), 
                            key=lambda x: x.get('ranking_score', 0), reverse=True)[:5]
    test_strategies_dict = {s['variation_id']: s for s in test_results.get('all_results', [])}
    
    print(f"{'Strategy':<25} {'Train PF':>10} {'Test PF':>10} {'Delta %':>10} {'Same?':>8}")
    print("-" * 80)
    
    for train_strat in train_strategies:
        var_id = train_strat['variation_id']
        train_pf = train_strat['performance']['profit_factor']
        
        if var_id in test_strategies_dict:
            test_strat = test_strategies_dict[var_id]
            test_pf = test_strat['performance']['profit_factor']
            
            pf_delta_pct = ((test_pf - train_pf) / train_pf) * 100 if train_pf > 0 else 0
            same = "YES ❌" if abs(pf_delta_pct) < 0.1 else "NO ✅"
            
            print(f"{var_id:<25} {train_pf:>10.3f} {test_pf:>10.3f} {pf_delta_pct:>9.1f}% {same:>8}")
    
    print()
    print("="*80)

if __name__ == "__main__":
    main()

