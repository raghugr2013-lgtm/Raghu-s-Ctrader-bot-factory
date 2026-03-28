#!/usr/bin/env python3
"""
Phase 2D: Robustness Testing (FIXED VERSION)
Proper train/test split with independent result files
"""
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
import pandas as pd
import shutil
import os

class RobustnessTesterFixed:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        
        print("\n" + "="*80)
        print("PHASE 2D: ROBUSTNESS TESTING (FIXED)")
        print("="*80)
        print(f"\nDataset: {csv_path}")
        print(f"Total candles: {len(self.df)}")
        print(f"Period: {self.df['timestamp'].min()} to {self.df['timestamp'].max()}")
        print()
    
    def train_test_split(self, train_pct=0.70):
        """Split data into train and test sets"""
        split_idx = int(len(self.df) * train_pct)
        
        train_df = self.df.iloc[:split_idx].copy()
        test_df = self.df.iloc[split_idx:].copy()
        
        print(f"📊 Train/Test Split ({int(train_pct*100)}/{int((1-train_pct)*100)})")
        print(f"   Train: {len(train_df)} candles ({train_df['timestamp'].min()} to {train_df['timestamp'].max()})")
        print(f"   Test:  {len(test_df)} candles ({test_df['timestamp'].min()} to {test_df['timestamp'].max()})")
        print()
        
        # Save splits
        train_path = "/tmp/robustness_train.csv"
        test_path = "/tmp/robustness_test.csv"
        
        train_df.to_csv(train_path, index=False)
        test_df.to_csv(test_path, index=False)
        
        return train_path, test_path
    
    def run_optimization(self, data_path: str, output_path: str, phase_name: str):
        """Run optimizer and save to unique output file"""
        import time
        
        print(f"🔄 Running optimization on {phase_name} data...")
        print(f"   Input: {data_path}")
        
        # Use absolute path for results
        default_results = "/app/trading_system/backend/results.json"
        
        # Delete old results.json to ensure fresh run
        if os.path.exists(default_results):
            os.remove(default_results)
        
        cmd = [
            sys.executable,
            "/app/trading_system/backend/phase2a_optimizer.py",
            "--csv", data_path
        ]
        
        # Run from backend directory to ensure results.json is created there
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                              cwd="/app/trading_system/backend")
        
        if result.returncode != 0:
            print(f"❌ Optimization failed (return code: {result.returncode})")
            print(f"   STDOUT: {result.stdout[-500:]}")
            print(f"   STDERR: {result.stderr[-500:]}")
            return None
        
        # Check if optimization actually ran by looking for output
        if "OPTIMIZATION COMPLETE" not in result.stdout:
            print(f"❌ Optimization did not complete successfully")
            print(f"   Output: {result.stdout[-1000:]}")
            return None
        
        # Wait for file to be fully written
        time.sleep(1)
        
        # Verify results.json was created
        if not os.path.exists(default_results):
            print(f"❌ Results file not created at {default_results}!")
            return None
        
        # IMMEDIATELY copy before next optimization can overwrite
        shutil.copy(default_results, output_path)
        
        # Verify the copy by reading it
        with open(output_path, 'r') as f:
            results = json.load(f)
        
        candles = results['optimization_run']['data_info']['candles']
        period_start = results['optimization_run']['data_info']['start_date']
        period_end = results['optimization_run']['data_info']['end_date']
        
        print(f"✅ {phase_name} complete:")
        print(f"   Processed: {candles} candles")
        print(f"   Period: {period_start} to {period_end}")
        print(f"   Saved to: {output_path}")
        print()
        
        # Verify no tampering
        with open(data_path, 'r') as f:
            input_df = pd.read_csv(f)
            expected_candles = len(input_df)
        
        if candles != expected_candles:
            print(f"⚠️ WARNING: Candle count mismatch!")
            print(f"   Expected: {expected_candles}, Got: {candles}")
            print(f"   This indicates the optimizer is not using the correct input file!")
        
        return results
    
    def compare_performance(self, train_results, test_results):
        """Compare train vs test performance"""
        print("\n" + "="*80)
        print("STABILITY ANALYSIS")
        print("="*80)
        print()
        
        train_strategies = sorted(train_results.get('all_results', []), 
                                key=lambda x: x.get('ranking_score', 0), reverse=True)[:10]
        test_strategies_dict = {s['variation_id']: s for s in test_results.get('all_results', [])}
        
        stable_strategies = []
        
        print(f"{'Strategy':<30} {'Train PF':>10} {'Test PF':>10} {'Delta %':>10} {'Stable':>8}")
        print("-" * 80)
        
        for train_strat in train_strategies:
            var_id = train_strat['variation_id']
            train_pf = train_strat['performance']['profit_factor']
            
            if var_id in test_strategies_dict:
                test_strat = test_strategies_dict[var_id]
                test_pf = test_strat['performance']['profit_factor']
                
                # Calculate stability metrics
                pf_delta_pct = ((test_pf - train_pf) / train_pf) * 100 if train_pf > 0 else 0
                
                # Stability criteria
                is_stable = (
                    abs(pf_delta_pct) < 50 and  # PF doesn't change >50%
                    test_pf > 0.80 and  # Test is not losing badly
                    train_pf > 1.0  # Train is profitable
                )
                
                stability_icon = "✅" if is_stable else "❌"
                
                print(f"{var_id:<30} {train_pf:>10.2f} {test_pf:>10.2f} {pf_delta_pct:>9.1f}% {stability_icon:>8}")
                
                if is_stable:
                    stable_strategies.append({
                        'variation_id': var_id,
                        'train_pf': train_pf,
                        'test_pf': test_pf,
                        'pf_delta_pct': abs(pf_delta_pct),
                        'stability_score': 100 - abs(pf_delta_pct),
                        'train_trades': train_strat['performance']['total_trades'],
                        'test_trades': test_strat['performance']['total_trades'],
                        'train_return': train_strat['performance']['return_pct'],
                        'test_return': test_strat['performance']['return_pct']
                    })
        
        print()
        print(f"Stable strategies: {len(stable_strategies)}/{len(train_strategies)}")
        print()
        
        return stable_strategies
    
    def generate_report(self, stable_strategies, train_results, test_results):
        """Generate final robustness report"""
        print("\n" + "="*80)
        print("ROBUSTNESS REPORT")
        print("="*80)
        print()
        
        if stable_strategies:
            print(f"✅ Found {len(stable_strategies)} stable strategies")
            print()
            print("Top 5 Most Stable Strategies:")
            print(f"{'Strategy':<30} {'Train PF':>10} {'Test PF':>10} {'Delta':>10} {'Stability':>10}")
            print("-" * 80)
            
            sorted_stable = sorted(stable_strategies, key=lambda x: x['stability_score'], reverse=True)
            
            for strat in sorted_stable[:5]:
                print(f"{strat['variation_id']:<30} "
                      f"{strat['train_pf']:>10.2f} "
                      f"{strat['test_pf']:>10.2f} "
                      f"{strat['pf_delta_pct']:>9.1f}% "
                      f"{strat['stability_score']:>9.1f}%")
            
            print()
            
            # Calculate aggregate metrics
            avg_train_pf = sum(s['train_pf'] for s in stable_strategies) / len(stable_strategies)
            avg_test_pf = sum(s['test_pf'] for s in stable_strategies) / len(stable_strategies)
            avg_stability = sum(s['stability_score'] for s in stable_strategies) / len(stable_strategies)
            avg_delta = sum(s['pf_delta_pct'] for s in stable_strategies) / len(stable_strategies)
            
            print(f"📊 Average Metrics:")
            print(f"   Train PF: {avg_train_pf:.2f}")
            print(f"   Test PF:  {avg_test_pf:.2f}")
            print(f"   Average PF Delta: {avg_delta:.1f}%")
            print(f"   Average Stability: {avg_stability:.1f}%")
            
            # Check data info
            train_candles = train_results['optimization_run']['data_info']['candles']
            test_candles = test_results['optimization_run']['data_info']['candles']
            
            print()
            print(f"📂 Data Verification:")
            print(f"   Train candles: {train_candles}")
            print(f"   Test candles:  {test_candles}")
            print(f"   Total: {train_candles + test_candles}")
            
        else:
            print("❌ No stable strategies found")
            print("   Recommendation: Revisit strategy or accept lower stability threshold")
        
        print("\n" + "="*80)
        
        return {
            'stable_strategies': stable_strategies,
            'summary': {
                'avg_train_pf': avg_train_pf if stable_strategies else 0,
                'avg_test_pf': avg_test_pf if stable_strategies else 0,
                'avg_stability': avg_stability if stable_strategies else 0
            }
        }

def main():
    csv_path = "/app/trading_system/data/EURUSD_H1.csv"
    
    tester = RobustnessTesterFixed(csv_path)
    
    # 1. Train/Test Split
    train_path, test_path = tester.train_test_split(train_pct=0.70)
    
    # 2. Run optimization on train data (save to unique file)
    train_output = "/tmp/train_results.json"
    train_results = tester.run_optimization(train_path, train_output, "TRAIN")
    if not train_results:
        print("❌ Train optimization failed")
        return
    
    # 3. Run optimization on test data (save to unique file)
    test_output = "/tmp/test_results.json"
    test_results = tester.run_optimization(test_path, test_output, "TEST")
    if not test_results:
        print("❌ Test optimization failed")
        return
    
    # 4. Compare performance
    stable_strategies = tester.compare_performance(train_results, test_results)
    
    # 5. Generate report
    report = tester.generate_report(stable_strategies, train_results, test_results)
    
    # Save report
    report_path = "/app/trading_system/backend/robustness_report_fixed.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n💾 Report saved to: {report_path}")

if __name__ == "__main__":
    main()

