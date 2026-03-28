#!/usr/bin/env python3
"""
Phase 2D: Robustness Testing
Train/Test Split and Walk-Forward Validation
"""
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
import pandas as pd

class RobustnessTester:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        
        print("\n" + "="*80)
        print("PHASE 2D: ROBUSTNESS TESTING")
        print("="*80)
        print(f"\nDataset: {csv_path}")
        print(f"Total candles: {len(self.df)}")
        print(f"Period: {self.df['timestamp'].min()} to {self.df['timestamp'].max()}")
        print()
    
    def train_test_split(self, train_pct=0.70):
        """Split data into train and test sets"""
        split_idx = int(len(self.df) * train_pct)
        
        train_df = self.df.iloc[:split_idx]
        test_df = self.df.iloc[split_idx:]
        
        print(f"📊 Train/Test Split ({int(train_pct*100)}/{int((1-train_pct)*100)})")
        print(f"   Train: {len(train_df)} candles ({train_df['timestamp'].min()} to {train_df['timestamp'].max()})")
        print(f"   Test:  {len(test_df)} candles ({test_df['timestamp'].min()} to {test_df['timestamp'].max()})")
        print()
        
        # Save splits
        train_path = "/tmp/train_data.csv"
        test_path = "/tmp/test_data.csv"
        
        train_df.to_csv(train_path, index=False)
        test_df.to_csv(test_path, index=False)
        
        return train_path, test_path
    
    def run_optimization(self, data_path: str, phase_name: str):
        """Run optimizer on specified data"""
        print(f"🔄 Running optimization on {phase_name} data...")
        
        cmd = [
            sys.executable,
            "/app/trading_system/backend/phase2a_optimizer.py",
            "--csv", data_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            print(f"❌ Optimization failed: {result.stderr}")
            return None
        
        # Load results
        results_path = "/app/trading_system/backend/results.json"
        with open(results_path, 'r') as f:
            results = json.load(f)
        
        print(f"✅ {phase_name} optimization complete")
        
        return results
    
    def extract_top_strategies(self, results, top_n=5):
        """Extract top N strategies from results"""
        # The results structure uses 'all_results' key
        strategies = results.get('all_results', [])
        
        if not strategies:
            print("⚠️ Warning: No variations found in results")
            return []
        
        # Sort by ranking score
        sorted_strategies = sorted(strategies, key=lambda x: x.get('ranking_score', 0), reverse=True)
        
        return sorted_strategies[:top_n]
    
    def compare_performance(self, train_results, test_results):
        """Compare train vs test performance"""
        print("\n" + "="*80)
        print("STABILITY ANALYSIS")
        print("="*80)
        print()
        
        train_strategies = self.extract_top_strategies(train_results, top_n=10)
        test_strategies_dict = {s['variation_id']: s for s in test_results.get('all_results', [])}
        
        stable_strategies = []
        
        print(f"{'Strategy':<30} {'Train PF':>10} {'Test PF':>10} {'Delta %':>10} {'Stable':>8}")
        print("-" * 80)
        
        for train_strat in train_strategies:
            var_id = train_strat['variation_id']
            train_pf = train_strat['performance']['profit_factor']
            
            # Find matching test strategy
            if var_id in test_strategies_dict:
                test_strat = test_strategies_dict[var_id]
                test_pf = test_strat['performance']['profit_factor']
                
                # Calculate stability metrics
                pf_delta_pct = ((test_pf - train_pf) / train_pf) * 100 if train_pf > 0 else 0
                
                # Stability criteria
                is_stable = (
                    abs(pf_delta_pct) < 30 and  # PF doesn't change >30%
                    test_pf > 0.95 and  # Test is not losing badly
                    train_pf > 1.0 and  # Train is profitable
                    test_pf > 0.90  # Test is near breakeven or better
                )
                
                stability_icon = "✅" if is_stable else "❌"
                
                print(f"{var_id:<30} {train_pf:>10.2f} {test_pf:>10.2f} {pf_delta_pct:>9.1f}% {stability_icon:>8}")
                
                if is_stable:
                    stable_strategies.append({
                        'variation_id': var_id,
                        'train_pf': train_pf,
                        'test_pf': test_pf,
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
    
    def walk_forward_test(self, window_months=6, test_months=3):
        """Basic walk-forward testing"""
        print("\n" + "="*80)
        print("WALK-FORWARD TESTING")
        print("="*80)
        print(f"\nTrain window: {window_months} months")
        print(f"Test window: {test_months} months")
        print()
        
        # Calculate window size in candles (approximate)
        train_candles = window_months * 30 * 24  # ~24 candles per day
        test_candles = test_months * 30 * 24
        
        results = []
        window_num = 0
        
        start_idx = 0
        while start_idx + train_candles + test_candles <= len(self.df):
            window_num += 1
            
            train_end = start_idx + train_candles
            test_end = train_end + test_candles
            
            train_window = self.df.iloc[start_idx:train_end]
            test_window = self.df.iloc[train_end:test_end]
            
            print(f"\n🔍 Window {window_num}:")
            print(f"   Train: {train_window['timestamp'].min()} to {train_window['timestamp'].max()}")
            print(f"   Test:  {test_window['timestamp'].min()} to {test_window['timestamp'].max()}")
            
            # Save windows
            train_path = f"/tmp/wf_train_{window_num}.csv"
            test_path = f"/tmp/wf_test_{window_num}.csv"
            
            train_window.to_csv(train_path, index=False)
            test_window.to_csv(test_path, index=False)
            
            # Run optimization on train
            train_results = self.run_optimization(train_path, f"Window {window_num} Train")
            if not train_results:
                break
            
            # Evaluate on test
            test_results = self.run_optimization(test_path, f"Window {window_num} Test")
            if not test_results:
                break
            
            # Get best strategy from train
            best_train = self.extract_top_strategies(train_results, top_n=1)[0]
            
            # Find same strategy in test
            test_strategies_dict = {s['variation_id']: s for s in test_results.get('all_results', [])}
            best_test = test_strategies_dict.get(best_train['variation_id'])
            
            if best_test:
                results.append({
                    'window': window_num,
                    'strategy': best_train['variation_id'],
                    'train_pf': best_train['performance']['profit_factor'],
                    'test_pf': best_test['performance']['profit_factor'],
                    'train_trades': best_train['performance']['total_trades'],
                    'test_trades': best_test['performance']['total_trades']
                })
            
            # Slide window forward (50% overlap)
            start_idx += train_candles // 2
        
        return results
    
    def generate_report(self, stable_strategies, wf_results=None):
        """Generate final robustness report"""
        print("\n" + "="*80)
        print("ROBUSTNESS REPORT")
        print("="*80)
        print()
        
        if stable_strategies:
            print(f"✅ Found {len(stable_strategies)} stable strategies")
            print()
            print("Top 5 Most Stable Strategies:")
            print(f"{'Strategy':<30} {'Train PF':>10} {'Test PF':>10} {'Stability':>10}")
            print("-" * 80)
            
            sorted_stable = sorted(stable_strategies, key=lambda x: x['stability_score'], reverse=True)
            
            for strat in sorted_stable[:5]:
                print(f"{strat['variation_id']:<30} "
                      f"{strat['train_pf']:>10.2f} "
                      f"{strat['test_pf']:>10.2f} "
                      f"{strat['stability_score']:>9.1f}%")
            
            print()
            
            # Calculate aggregate metrics
            avg_train_pf = sum(s['train_pf'] for s in stable_strategies) / len(stable_strategies)
            avg_test_pf = sum(s['test_pf'] for s in stable_strategies) / len(stable_strategies)
            avg_stability = sum(s['stability_score'] for s in stable_strategies) / len(stable_strategies)
            
            print(f"Average Train PF: {avg_train_pf:.2f}")
            print(f"Average Test PF:  {avg_test_pf:.2f}")
            print(f"Average Stability: {avg_stability:.1f}%")
        else:
            print("❌ No stable strategies found")
            print("   Recommendation: Revisit parameter grid or strategy logic")
        
        # Walk-forward results
        if wf_results:
            print("\n" + "="*80)
            print("WALK-FORWARD SUMMARY")
            print("="*80)
            print()
            
            for res in wf_results:
                consistency = "✅" if abs(res['train_pf'] - res['test_pf']) / res['train_pf'] < 0.3 else "❌"
                print(f"Window {res['window']}: Train PF={res['train_pf']:.2f}, "
                      f"Test PF={res['test_pf']:.2f} {consistency}")
        
        print("\n" + "="*80)
        
        return {
            'stable_strategies': stable_strategies,
            'walk_forward_results': wf_results
        }

def main():
    csv_path = "/app/trading_system/data/EURUSD_H1.csv"
    
    tester = RobustnessTester(csv_path)
    
    # 1. Train/Test Split
    train_path, test_path = tester.train_test_split(train_pct=0.70)
    
    # 2. Run optimization on train data
    train_results = tester.run_optimization(train_path, "TRAIN")
    if not train_results:
        print("❌ Train optimization failed")
        return
    
    # 3. Evaluate on test data
    test_results = tester.run_optimization(test_path, "TEST")
    if not test_results:
        print("❌ Test optimization failed")
        return
    
    # 4. Compare performance
    stable_strategies = tester.compare_performance(train_results, test_results)
    
    # 5. Generate report
    report = tester.generate_report(stable_strategies)
    
    # Save report
    report_path = "/app/trading_system/backend/robustness_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n💾 Report saved to: {report_path}")

if __name__ == "__main__":
    main()

