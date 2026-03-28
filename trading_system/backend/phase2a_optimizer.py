"""
Phase 2A Optimizer - Controlled Rollout

Single strategy (trend following) with small parameter grid.
Focus: Validation, not discovery.
"""

import pandas as pd
import json
import os
import sys
import argparse
import itertools
from datetime import datetime
from typing import List, Dict


class Phase2AOptimizer:
    """Minimal viable optimizer for validation"""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        
        # Load CSV
        try:
            self.candles = pd.read_csv(csv_path)
            self.candles['timestamp'] = pd.to_datetime(self.candles['timestamp'])
            print(f"✅ Loaded {len(self.candles)} candles")
            print(f"   Period: {self.candles['timestamp'].min()} to {self.candles['timestamp'].max()}")
        except Exception as e:
            print(f"❌ Error loading CSV: {e}")
            sys.exit(1)
    
    def get_parameter_space(self) -> Dict:
        """Phase 2A: Small parameter space (8 variations)"""
        return {
            "ema_fast": [20, 50],
            "ema_slow": [100, 200],
            "adx_threshold": [20, 25],
            "risk_pct": [1.0],
            "stop_loss_atr": [2.0],
            "take_profit_atr": [3.0]
        }
    
    def generate_combinations(self, params: Dict) -> List[Dict]:
        """Generate all valid parameter combinations"""
        keys = params.keys()
        values = params.values()
        
        combinations = []
        for combo in itertools.product(*values):
            param_set = dict(zip(keys, combo))
            
            # Validate: ema_fast < ema_slow
            if param_set["ema_fast"] >= param_set["ema_slow"]:
                continue
            
            combinations.append(param_set)
        
        return combinations
    
    def run_trend_strategy(self, parameters: Dict) -> List[Dict]:
        """
        Real EMA-based trend following strategy
        
        Entry Rules:
        - BUY: EMA_fast > EMA_slow
        - SELL: EMA_fast < EMA_slow
        
        Uses shift(1) to avoid lookahead bias
        """
        # Extract parameters
        ema_fast = parameters['ema_fast']
        ema_slow = parameters['ema_slow']
        risk_pct = parameters['risk_pct']
        stop_loss_atr = parameters.get('stop_loss_atr', 2.0)
        
        # Work on a copy of candles
        df = self.candles.copy()
        
        # Calculate EMAs
        df['ema_fast'] = df['close'].ewm(span=ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=ema_slow, adjust=False).mean()
        
        # Calculate ATR for position sizing (simplified)
        df['high_low'] = df['high'] - df['low']
        df['atr'] = df['high_low'].rolling(window=14).mean()
        
        # Generate signals (avoiding lookahead bias)
        df['signal'] = 0
        df.loc[df['ema_fast'] > df['ema_slow'], 'signal'] = 1   # Long
        df.loc[df['ema_fast'] < df['ema_slow'], 'signal'] = -1  # Short
        
        # Shift signal to avoid lookahead bias
        df['position'] = df['signal'].shift(1)
        
        # Calculate returns
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['returns'] * df['position']
        
        # Drop NaN values
        df = df.dropna()
        
        # Simulate trades based on position changes
        trades = []
        position = None
        
        for i in range(1, len(df)):
            current_position = df.iloc[i]['position']
            prev_position = df.iloc[i-1]['position']
            
            # Position change detected
            if current_position != prev_position:
                # Close existing position if any
                if position is not None:
                    exit_price = df.iloc[i]['close']
                    exit_time = df.iloc[i]['timestamp']
                    
                    # Calculate P&L
                    if position['direction'] == 'LONG':
                        price_change = exit_price - position['entry_price']
                        pnl = (price_change / position['entry_price']) * 10000 * risk_pct
                    else:  # SHORT
                        price_change = position['entry_price'] - exit_price
                        pnl = (price_change / position['entry_price']) * 10000 * risk_pct
                    
                    trades.append({
                        'entry_time': str(position['entry_time']),
                        'exit_time': str(exit_time),
                        'direction': position['direction'],
                        'entry_price': float(position['entry_price']),
                        'exit_price': float(exit_price),
                        'pnl': round(pnl, 2)
                    })
                    
                    position = None
                
                # Open new position if signal is not neutral
                if current_position != 0:
                    position = {
                        'direction': 'LONG' if current_position > 0 else 'SHORT',
                        'entry_time': df.iloc[i]['timestamp'],
                        'entry_price': df.iloc[i]['close']
                    }
        
        # Close final position if still open
        if position is not None:
            exit_price = df.iloc[-1]['close']
            exit_time = df.iloc[-1]['timestamp']
            
            if position['direction'] == 'LONG':
                price_change = exit_price - position['entry_price']
                pnl = (price_change / position['entry_price']) * 10000 * risk_pct
            else:
                price_change = position['entry_price'] - exit_price
                pnl = (price_change / position['entry_price']) * 10000 * risk_pct
            
            trades.append({
                'entry_time': str(position['entry_time']),
                'exit_time': str(exit_time),
                'direction': position['direction'],
                'entry_price': float(position['entry_price']),
                'exit_price': float(exit_price),
                'pnl': round(pnl, 2)
            })
        
        return trades
    
    def calculate_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate performance metrics"""
        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "net_pnl": 0,
                "return_pct": 0,
                "max_drawdown_pct": 0,
                "average_win": 0,
                "average_loss": 0
            }
        
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] < 0]
        
        total_wins = sum(t['pnl'] for t in wins) if wins else 0
        total_losses = abs(sum(t['pnl'] for t in losses)) if losses else 0
        
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        
        # Calculate return and drawdown
        initial_balance = 10000
        balance = initial_balance
        peak = initial_balance
        max_dd = 0
        
        for trade in trades:
            balance += trade['pnl']
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        return_pct = (balance - initial_balance) / initial_balance * 100
        
        return {
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "net_pnl": round(balance - initial_balance, 2),
            "return_pct": round(return_pct, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "average_win": round(total_wins / len(wins), 2) if wins else 0,
            "average_loss": round(total_losses / len(losses), 2) if losses else 0
        }
    
    def calculate_ranking_score(self, performance: Dict) -> Dict:
        """Calculate composite ranking score"""
        # PF: 1.0 = 0, 2.0+ = 100
        pf_score = min((performance['profit_factor'] - 1.0) * 100, 100)
        pf_score = max(pf_score, 0)
        
        # Return: 0% = 0, 15%+ = 100
        return_score = min(performance['return_pct'] * 6.67, 100)
        return_score = max(return_score, 0)
        
        # Drawdown: 10% = 0, 0% = 100
        dd_score = max(100 - (performance['max_drawdown_pct'] * 10), 0)
        
        # Trade count: 10 = 0, 60+ = 100
        trade_score = min((performance['total_trades'] - 10) * 2, 100)
        trade_score = max(trade_score, 0)
        
        # Weighted average
        weights = {
            "profit_factor": 0.30,
            "return": 0.25,
            "drawdown": 0.25,
            "trade_count": 0.20
        }
        
        composite_score = (
            pf_score * weights["profit_factor"] +
            return_score * weights["return"] +
            dd_score * weights["drawdown"] +
            trade_score * weights["trade_count"]
        )
        
        return {
            "ranking_score": round(composite_score, 1),
            "score_breakdown": {
                "pf_score": round(pf_score, 1),
                "return_score": round(return_score, 1),
                "drawdown_score": round(dd_score, 1),
                "trade_count_score": round(trade_score, 1)
            }
        }
    
    def assess_viability(self, performance: Dict) -> Dict:
        """Assess if strategy is viable (Phase 2A: relaxed criteria)"""
        pf_pass = performance['profit_factor'] >= 1.1
        dd_pass = performance['max_drawdown_pct'] < 15.0
        trades_pass = performance['total_trades'] >= 20
        return_pass = performance['return_pct'] > 0
        
        is_viable = all([pf_pass, dd_pass, trades_pass, return_pass])
        
        if is_viable and performance['profit_factor'] >= 1.5:
            recommendation = "Excellent - Ready for Phase 2B"
        elif is_viable and performance['profit_factor'] >= 1.3:
            recommendation = "Very Good - Proceed to Phase 2B"
        elif is_viable:
            recommendation = "Good - Monitor in Phase 2B"
        else:
            recommendation = "Not Viable - Review strategy"
        
        return {
            "is_viable": bool(is_viable),
            "passes_pf_threshold": bool(pf_pass),
            "passes_dd_threshold": bool(dd_pass),
            "passes_trade_count": bool(trades_pass),
            "passes_return": bool(return_pass),
            "recommendation": recommendation
        }
    
    def run_optimization(self) -> Dict:
        """Main optimization function"""
        print()
        print("="*80)
        print("PHASE 2A: CONTROLLED OPTIMIZATION")
        print("="*80)
        print()
        
        start_time = datetime.utcnow()
        
        # Get parameter space
        param_space = self.get_parameter_space()
        combinations = self.generate_combinations(param_space)
        
        print(f"Strategy: Trend Following (ONLY)")
        print(f"Parameter combinations: {len(combinations)}")
        print(f"Expected runtime: ~{len(combinations)}s")
        print()
        
        all_results = []
        
        # Run each combination
        for idx, params in enumerate(combinations, 1):
            param_str = f"EMA {params['ema_fast']}/{params['ema_slow']}, ADX {params['adx_threshold']}"
            print(f"[{idx}/{len(combinations)}] Testing {param_str}...", end=" ", flush=True)
            
            # Run backtest
            trades = self.run_trend_strategy(params)
            
            # Calculate metrics
            metrics = self.calculate_metrics(trades)
            
            # Calculate ranking
            scores = self.calculate_ranking_score(metrics)
            
            # Assess viability
            viability = self.assess_viability(metrics)
            
            # Create variation ID
            variation_id = f"trend_ema{params['ema_fast']}_{params['ema_slow']}_adx{params['adx_threshold']}"
            
            all_results.append({
                "variation_id": variation_id,
                "strategy_name": "trend_following",
                "parameters": params,
                "performance": metrics,
                "ranking_score": scores['ranking_score'],
                "score_breakdown": scores['score_breakdown'],
                "viability": viability
            })
            
            print(f"PF: {metrics['profit_factor']:.2f}, Trades: {metrics['total_trades']}, Score: {scores['ranking_score']:.1f}")
        
        print()
        
        # Sort by ranking score
        all_results.sort(key=lambda x: x['ranking_score'], reverse=True)
        
        # Add ranks
        for idx, result in enumerate(all_results, 1):
            result['rank'] = idx
        
        # Get viable strategies
        viable_strategies = [r for r in all_results if r['viability']['is_viable']]
        
        # Summary
        summary = {
            "total_strategies_tested": len(all_results),
            "viable_strategies": len(viable_strategies),
            "viability_rate": round(len(viable_strategies) / len(all_results) * 100, 1) if all_results else 0,
            "best_profit_factor": max(r['performance']['profit_factor'] for r in all_results) if all_results else 0,
            "best_return": max(r['performance']['return_pct'] for r in all_results) if all_results else 0,
            "lowest_drawdown": min(r['performance']['max_drawdown_pct'] for r in all_results) if all_results else 0
        }
        
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Compile results
        optimization_results = {
            "optimization_run": {
                "run_id": start_time.isoformat(),
                "run_type": "phase_2a_controlled",
                "phase": "2A",
                "data_info": {
                    "source": self.csv_path,
                    "candles": len(self.candles),
                    "start_date": str(self.candles['timestamp'].min()),
                    "end_date": str(self.candles['timestamp'].max())
                },
                "optimization_config": {
                    "strategies_tested": 1,
                    "total_variations": len(all_results),
                    "execution_time_seconds": round(execution_time, 1)
                }
            },
            "top_strategies": all_results[:5],
            "summary_statistics": summary,
            "all_results": all_results
        }
        
        print("="*80)
        print("OPTIMIZATION COMPLETE")
        print("="*80)
        print(f"Total variations: {len(all_results)}")
        print(f"Viable strategies: {len(viable_strategies)} ({summary['viability_rate']}%)")
        print(f"Best PF: {summary['best_profit_factor']:.2f}")
        print(f"Execution time: {execution_time:.1f}s")
        print()
        
        if len(all_results) > 0:
            print("Top 3 Strategies:")
            for i, strategy in enumerate(all_results[:3], 1):
                print(f"  {i}. {strategy['variation_id']}: PF={strategy['performance']['profit_factor']:.2f}, Score={strategy['ranking_score']:.1f}")
        
        print()
        return optimization_results


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Phase 2A Optimizer - Controlled Rollout')
    parser.add_argument(
        '--csv',
        type=str,
        required=False,
        default='/app/trading_system/data/EURUSD_H1.csv',
        help='Path to CSV file with H1 candle data'
    )
    return parser.parse_args()


if __name__ == "__main__":
    # Parse arguments
    args = parse_args()
    CSV_PATH = args.csv
    
    print()
    print("╔" + "="*78 + "╗")
    print("║" + " "*25 + "PHASE 2A OPTIMIZER" + " "*35 + "║")
    print("║" + " "*15 + "Controlled Rollout - Validation Phase" + " "*24 + "║")
    print("╚" + "="*78 + "╝")
    print()
    print(f"CSV Path: {CSV_PATH}")
    print()
    
    # Validate CSV exists
    if not os.path.exists(CSV_PATH):
        print(f"❌ ERROR: CSV file not found: {CSV_PATH}")
        sys.exit(1)
    
    # Run optimization
    optimizer = Phase2AOptimizer(CSV_PATH)
    results = optimizer.run_optimization()
    
    # Save to results.json (fixed name for API)
    output_file = "results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Results saved to {output_file}")
    print()
