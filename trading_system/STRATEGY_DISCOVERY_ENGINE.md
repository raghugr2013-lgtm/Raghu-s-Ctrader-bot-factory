# STRATEGY DISCOVERY ENGINE - ARCHITECTURE & IMPLEMENTATION

**Phase 2: From Result Viewer → Strategy Discovery Engine**

---

## 🎯 SYSTEM TRANSFORMATION

### **Before (Phase 1):**
```
Local Engine → Upload Results → Backend Stores → UI Displays
```

### **After (Phase 2):**
```
Local Engine (Multi-Strategy + Optimization)
    ↓
Upload Results (with Rankings)
    ↓
Backend (Store + Rank + Compare)
    ↓
UI (Filter + Highlight + Discover Best)
```

---

## 🏗️ ENHANCED ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│  LOCAL ENGINE (Your Laptop)                                 │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Parameter Optimization Engine                      │    │
│  │  ┌──────────────────────────────────────────────┐  │    │
│  │  │  Strategy 1: Trend Following                  │  │    │
│  │  │  - EMA combinations: [20/50, 50/200, ...]    │  │    │
│  │  │  - ADX levels: [15, 20, 25, 30]              │  │    │
│  │  │  - Risk: [0.5%, 1%, 2%]                      │  │    │
│  │  │  → 100+ parameter combinations               │  │    │
│  │  └──────────────────────────────────────────────┘  │    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────────┐  │    │
│  │  │  Strategy 2: Mean Reversion                   │  │    │
│  │  │  - RSI levels: [30/70, 35/65, 40/60, ...]    │  │    │
│  │  │  - BB periods: [14, 20, 28]                   │  │    │
│  │  │  - BB std: [1.5, 2.0, 2.5]                    │  │    │
│  │  │  → 80+ parameter combinations                 │  │    │
│  │  └──────────────────────────────────────────────┘  │    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────────┐  │    │
│  │  │  Strategy 3: Breakout                         │  │    │
│  │  │  - Lookback periods: [10, 20, 50]            │  │    │
│  │  │  - Buffer: [0.1%, 0.2%, 0.5%]                │  │    │
│  │  │  → 50+ parameter combinations                 │  │    │
│  │  └──────────────────────────────────────────────┘  │    │
│  │                                                      │    │
│  │  Total: 230+ strategy variations tested            │    │
│  └────────────────────────────────────────────────────┘    │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Ranking Engine                                     │    │
│  │  - Calculate composite score                        │    │
│  │  - Rank by PF, Return, DD, Trades                   │    │
│  │  - Filter viable strategies (PF > 1.0, DD < 10%)   │    │
│  └────────────────────────────────────────────────────┘    │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Enhanced Results JSON                              │    │
│  │  {                                                   │    │
│  │    "optimization_run": {...},                       │    │
│  │    "top_strategies": [...],                         │    │
│  │    "all_results": [...],                            │    │
│  │    "rankings": {...}                                │    │
│  │  }                                                   │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS POST
                               ↓
┌──────────────────────────────┴──────────────────────────────┐
│  BACKEND (Cloud/Server)                                     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  API: /api/optimization-results                     │    │
│  │  - Receive optimization runs                        │    │
│  │  - Store in MongoDB                                 │    │
│  │  - Cross-run comparison                             │    │
│  │  - Historical tracking                              │    │
│  └────────────────────────────────────────────────────┘    │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  MongoDB Collections                                │    │
│  │  - optimization_runs                                │    │
│  │  - strategy_variations                              │    │
│  │  - best_strategies (leaderboard)                    │    │
│  └────────────────────────────────────────────────────┘    │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Analysis & Comparison APIs                         │    │
│  │  - GET /api/top-strategies                          │    │
│  │  - GET /api/compare-runs                            │    │
│  │  - GET /api/parameter-sensitivity                   │    │
│  │  - GET /api/strategy-leaderboard                    │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌──────────────────────────────┴──────────────────────────────┐
│  FRONTEND UI                                                │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Strategy Discovery Dashboard                       │    │
│  │  ┌────────────┬────────────┬────────────────────┐  │    │
│  │  │ Filter     │ Rank By    │ Show               │  │    │
│  │  │ PF > 1.3   │ ● Return   │ ☑ Top 10 only      │  │    │
│  │  │ DD < 6%    │ ○ PF       │ ☑ Viable only      │  │    │
│  │  │ Trades>30  │ ○ Drawdown │                    │  │    │
│  │  └────────────┴────────────┴────────────────────┘  │    │
│  └────────────────────────────────────────────────────┘    │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Top Strategies Table                               │    │
│  │  ┌──┬───────────┬────┬─────┬────┬──────┬────────┐  │    │
│  │  │# │ Strategy  │ PF │ Ret │ DD │Trade │ Score  │  │    │
│  │  ├──┼───────────┼────┼─────┼────┼──────┼────────┤  │    │
│  │  │1 │Trend(50/2)│1.85│12.3%│2.1%│ 45   │ 92.5 ⭐│  │    │
│  │  │2 │MeanRev(40)│1.72│10.8%│3.4%│ 52   │ 88.3   │  │    │
│  │  │3 │Breakout20 │1.58│ 9.2%│4.1%│ 38   │ 82.1   │  │    │
│  │  └──┴───────────┴────┴─────┴────┴──────┴────────┘  │    │
│  └────────────────────────────────────────────────────┘    │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Strategy Detail View                               │    │
│  │  - Parameter combination                            │    │
│  │  - Full metrics breakdown                           │    │
│  │  - Trade distribution                               │    │
│  │  - Equity curve (chart)                             │    │
│  │  - Export to cBot button                            │    │
│  └────────────────────────────────────────────────────┘    │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Comparison View                                    │    │
│  │  - Compare top 3 strategies side-by-side           │    │
│  │  - Parameter sensitivity analysis                   │    │
│  │  - Cross-run performance                            │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 ENHANCED DATA FORMAT

### **New JSON Structure:**

```json
{
  "optimization_run": {
    "run_id": "2026-03-26T18:00:00.000Z",
    "run_type": "multi_strategy_optimization",
    "data_info": {
      "source": "EURUSD_H1.csv",
      "candles": 6513,
      "start_date": "2025-01-02",
      "end_date": "2026-02-25",
      "duration_days": 418
    },
    "optimization_config": {
      "strategies_tested": 3,
      "total_variations": 230,
      "execution_time_seconds": 145.2,
      "ranking_criteria": {
        "profit_factor_weight": 0.30,
        "return_weight": 0.25,
        "drawdown_weight": 0.25,
        "trade_count_weight": 0.20
      }
    }
  },
  
  "top_strategies": [
    {
      "rank": 1,
      "strategy_name": "trend_following",
      "variation_id": "trend_ema50_200_adx20",
      "parameters": {
        "ema_fast": 50,
        "ema_slow": 200,
        "adx_threshold": 20,
        "risk_pct": 1.0,
        "stop_loss_atr": 2.0,
        "take_profit_atr": 3.0
      },
      "performance": {
        "total_trades": 45,
        "winning_trades": 24,
        "losing_trades": 21,
        "win_rate": 53.3,
        "profit_factor": 1.85,
        "net_pnl": 1234.50,
        "return_pct": 12.35,
        "max_drawdown": 2.15,
        "max_drawdown_pct": 2.15,
        "sharpe_ratio": 1.82,
        "average_win": 95.50,
        "average_loss": -45.20,
        "largest_win": 285.00,
        "largest_loss": -98.50,
        "consecutive_wins": 6,
        "consecutive_losses": 4
      },
      "ranking_score": 92.5,
      "score_breakdown": {
        "pf_score": 95.0,
        "return_score": 88.0,
        "drawdown_score": 94.0,
        "trade_count_score": 93.0
      },
      "viability": {
        "is_viable": true,
        "passes_pf_threshold": true,
        "passes_dd_threshold": true,
        "passes_trade_count": true,
        "recommendation": "Excellent - Ready for paper trading"
      }
    },
    {
      "rank": 2,
      "strategy_name": "mean_reversion",
      "variation_id": "meanrev_rsi40_60_bb20",
      "parameters": {
        "rsi_period": 14,
        "rsi_oversold": 40,
        "rsi_overbought": 60,
        "bb_period": 20,
        "bb_std": 2.0,
        "risk_pct": 1.0
      },
      "performance": {
        "total_trades": 52,
        "win_rate": 51.9,
        "profit_factor": 1.72,
        "return_pct": 10.80,
        "max_drawdown_pct": 3.42
      },
      "ranking_score": 88.3,
      "viability": {
        "is_viable": true,
        "recommendation": "Very Good - Consider for deployment"
      }
    },
    {
      "rank": 3,
      "strategy_name": "breakout",
      "variation_id": "breakout_lookback20_buf02",
      "parameters": {
        "lookback_period": 20,
        "breakout_buffer": 0.002,
        "risk_pct": 0.8
      },
      "performance": {
        "total_trades": 38,
        "win_rate": 47.4,
        "profit_factor": 1.58,
        "return_pct": 9.20,
        "max_drawdown_pct": 4.15
      },
      "ranking_score": 82.1,
      "viability": {
        "is_viable": true,
        "recommendation": "Good - Needs monitoring"
      }
    }
  ],
  
  "summary_statistics": {
    "total_strategies_tested": 230,
    "viable_strategies": 18,
    "viability_rate": 7.8,
    "best_profit_factor": 1.85,
    "best_return": 12.35,
    "lowest_drawdown": 1.82,
    "average_pf_viable": 1.42,
    "parameter_insights": {
      "most_profitable_ema": "50/200",
      "most_profitable_rsi": "40/60",
      "optimal_risk": 1.0
    }
  },
  
  "all_results": [
    {
      "variation_id": "trend_ema20_50_adx25",
      "strategy_name": "trend_following",
      "parameters": {...},
      "performance": {...},
      "ranking_score": 75.2,
      "rank": 4
    }
    // ... all 230 variations
  ]
}
```

---

## 🔧 LOCAL ENGINE IMPLEMENTATION

### **1. Parameter Optimization Framework**

**File: `optimization_engine.py` (Your Laptop)**

```python
"""
Multi-Strategy Parameter Optimization Engine

Runs multiple strategies with parameter sweeps
Ranks results by composite score
"""

import pandas as pd
import itertools
from typing import List, Dict
from datetime import datetime
import json

class StrategyOptimizer:
    """Optimize multiple strategies with parameter sweeps"""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.candles = pd.read_csv(csv_path)
        self.candles['timestamp'] = pd.to_datetime(self.candles['timestamp'])
        
        self.results = []
        
    def define_parameter_space(self) -> Dict:
        """
        Define parameter combinations to test
        
        Returns dict of strategy -> parameter combinations
        """
        return {
            "trend_following": {
                "ema_fast": [20, 50, 100],
                "ema_slow": [50, 100, 200],
                "adx_threshold": [15, 20, 25, 30],
                "risk_pct": [0.5, 1.0, 1.5],
                "stop_loss_atr": [1.5, 2.0, 2.5],
                "take_profit_atr": [2.5, 3.0, 4.0]
            },
            "mean_reversion": {
                "rsi_period": [14],
                "rsi_oversold": [30, 35, 40, 45],
                "rsi_overbought": [55, 60, 65, 70],
                "bb_period": [14, 20, 28],
                "bb_std": [1.5, 2.0, 2.5],
                "risk_pct": [0.5, 1.0, 1.5]
            },
            "breakout": {
                "lookback_period": [10, 20, 30, 50],
                "breakout_buffer": [0.001, 0.002, 0.005],
                "risk_pct": [0.5, 0.8, 1.0]
            }
        }
    
    def generate_combinations(self, strategy_name: str, params: Dict) -> List[Dict]:
        """Generate all parameter combinations for a strategy"""
        
        keys = params.keys()
        values = params.values()
        
        combinations = []
        for combo in itertools.product(*values):
            param_set = dict(zip(keys, combo))
            
            # Add validation (e.g., ema_fast < ema_slow)
            if strategy_name == "trend_following":
                if param_set["ema_fast"] >= param_set["ema_slow"]:
                    continue  # Invalid combination
            
            combinations.append(param_set)
        
        return combinations
    
    def run_single_variation(
        self, 
        strategy_name: str, 
        parameters: Dict
    ) -> Dict:
        """
        Run a single strategy variation
        
        Returns performance metrics
        """
        
        # YOUR EXISTING STRATEGY CODE HERE
        # Example:
        if strategy_name == "trend_following":
            trades = self.run_trend_strategy(parameters)
        elif strategy_name == "mean_reversion":
            trades = self.run_mean_reversion(parameters)
        elif strategy_name == "breakout":
            trades = self.run_breakout(parameters)
        
        # Calculate metrics
        metrics = self.calculate_metrics(trades)
        
        return {
            "parameters": parameters,
            "performance": metrics,
            "trades": trades  # Optional: full trade list
        }
    
    def calculate_metrics(self, trades: List) -> Dict:
        """Calculate performance metrics from trade list"""
        
        if not trades:
            return {
                "total_trades": 0,
                "profit_factor": 0,
                "return_pct": 0,
                "max_drawdown_pct": 0,
                "win_rate": 0
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
            dd = (peak - balance) / peak * 100
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
    
    def calculate_ranking_score(
        self, 
        performance: Dict,
        weights: Dict = None
    ) -> Dict:
        """
        Calculate composite ranking score
        
        Default weights:
        - Profit Factor: 30%
        - Return: 25%
        - Drawdown: 25%
        - Trade Count: 20%
        """
        
        if weights is None:
            weights = {
                "profit_factor": 0.30,
                "return": 0.25,
                "drawdown": 0.25,
                "trade_count": 0.20
            }
        
        # Normalize metrics to 0-100 scale
        # PF: 1.0 = 0, 2.0+ = 100
        pf_score = min((performance['profit_factor'] - 1.0) * 100, 100)
        pf_score = max(pf_score, 0)
        
        # Return: 0% = 0, 15%+ = 100
        return_score = min(performance['return_pct'] * 6.67, 100)
        return_score = max(return_score, 0)
        
        # Drawdown: 10% = 0, 0% = 100 (inverted)
        dd_score = max(100 - (performance['max_drawdown_pct'] * 10), 0)
        
        # Trade count: 10 = 0, 60+ = 100
        trade_score = min((performance['total_trades'] - 10) * 2, 100)
        trade_score = max(trade_score, 0)
        
        # Weighted average
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
        """
        Assess if strategy is viable for deployment
        
        Criteria:
        - PF > 1.3
        - Max DD < 10%
        - Trades > 20
        - Return > 0%
        """
        
        pf_pass = performance['profit_factor'] >= 1.3
        dd_pass = performance['max_drawdown_pct'] < 10.0
        trades_pass = performance['total_trades'] >= 20
        return_pass = performance['return_pct'] > 0
        
        is_viable = all([pf_pass, dd_pass, trades_pass, return_pass])
        
        if is_viable and performance['profit_factor'] >= 1.8:
            recommendation = "Excellent - Ready for paper trading"
        elif is_viable and performance['profit_factor'] >= 1.5:
            recommendation = "Very Good - Consider for deployment"
        elif is_viable:
            recommendation = "Good - Needs monitoring"
        else:
            recommendation = "Not Viable - Needs improvement"
        
        return {
            "is_viable": is_viable,
            "passes_pf_threshold": pf_pass,
            "passes_dd_threshold": dd_pass,
            "passes_trade_count": trades_pass,
            "passes_return": return_pass,
            "recommendation": recommendation
        }
    
    def run_optimization(self) -> Dict:
        """
        Main optimization function
        
        Returns complete optimization results
        """
        
        print("="*80)
        print("STRATEGY OPTIMIZATION ENGINE")
        print("="*80)
        print()
        
        start_time = datetime.utcnow()
        
        # Get parameter space
        param_space = self.define_parameter_space()
        
        all_results = []
        strategy_count = 0
        
        # Run each strategy with all parameter combinations
        for strategy_name, params in param_space.items():
            combinations = self.generate_combinations(strategy_name, params)
            
            print(f"Strategy: {strategy_name}")
            print(f"  Parameter combinations: {len(combinations)}")
            print()
            
            for idx, param_set in enumerate(combinations, 1):
                print(f"  [{idx}/{len(combinations)}] Testing {strategy_name}...", end=" ")
                
                # Run backtest
                result = self.run_single_variation(strategy_name, param_set)
                
                # Calculate ranking
                scores = self.calculate_ranking_score(result['performance'])
                
                # Assess viability
                viability = self.assess_viability(result['performance'])
                
                # Create variation ID
                variation_id = f"{strategy_name}_var{strategy_count}"
                
                all_results.append({
                    "variation_id": variation_id,
                    "strategy_name": strategy_name,
                    "parameters": param_set,
                    "performance": result['performance'],
                    "ranking_score": scores['ranking_score'],
                    "score_breakdown": scores['score_breakdown'],
                    "viability": viability
                })
                
                print(f"PF: {result['performance']['profit_factor']:.2f}, "
                      f"Score: {scores['ranking_score']:.1f}")
                
                strategy_count += 1
            
            print()
        
        # Sort by ranking score
        all_results.sort(key=lambda x: x['ranking_score'], reverse=True)
        
        # Add ranks
        for idx, result in enumerate(all_results, 1):
            result['rank'] = idx
        
        # Get top strategies
        top_strategies = all_results[:10]
        
        # Calculate summary statistics
        viable_strategies = [r for r in all_results if r['viability']['is_viable']]
        
        summary = {
            "total_strategies_tested": len(all_results),
            "viable_strategies": len(viable_strategies),
            "viability_rate": round(len(viable_strategies) / len(all_results) * 100, 1),
            "best_profit_factor": max(r['performance']['profit_factor'] for r in all_results),
            "best_return": max(r['performance']['return_pct'] for r in all_results),
            "lowest_drawdown": min(r['performance']['max_drawdown_pct'] for r in all_results),
            "average_pf_viable": round(
                sum(r['performance']['profit_factor'] for r in viable_strategies) / len(viable_strategies), 2
            ) if viable_strategies else 0
        }
        
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Compile final results
        optimization_results = {
            "optimization_run": {
                "run_id": start_time.isoformat(),
                "run_type": "multi_strategy_optimization",
                "data_info": {
                    "source": self.csv_path,
                    "candles": len(self.candles),
                    "start_date": str(self.candles['timestamp'].min()),
                    "end_date": str(self.candles['timestamp'].max())
                },
                "optimization_config": {
                    "strategies_tested": len(param_space),
                    "total_variations": len(all_results),
                    "execution_time_seconds": round(execution_time, 1)
                }
            },
            "top_strategies": top_strategies,
            "summary_statistics": summary,
            "all_results": all_results
        }
        
        print("="*80)
        print("OPTIMIZATION COMPLETE")
        print("="*80)
        print(f"Total variations tested: {len(all_results)}")
        print(f"Viable strategies: {len(viable_strategies)} ({summary['viability_rate']}%)")
        print(f"Best PF: {summary['best_profit_factor']:.2f}")
        print(f"Best Return: {summary['best_return']:.2f}%")
        print(f"Execution time: {execution_time:.1f}s")
        print()
        
        return optimization_results
    
    # YOUR EXISTING STRATEGY FUNCTIONS HERE
    def run_trend_strategy(self, params):
        """Your existing trend following code"""
        pass
    
    def run_mean_reversion(self, params):
        """Your existing mean reversion code"""
        pass
    
    def run_breakout(self, params):
        """Your existing breakout code"""
        pass


if __name__ == "__main__":
    # Run optimization
    optimizer = StrategyOptimizer("/path/to/EURUSD_H1.csv")
    results = optimizer.run_optimization()
    
    # Save to file
    with open("optimization_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("✅ Results saved to optimization_results.json")
    print()
    print("Top 3 Strategies:")
    for strategy in results['top_strategies'][:3]:
        print(f"  {strategy['rank']}. {strategy['strategy_name']}: "
              f"PF={strategy['performance']['profit_factor']:.2f}, "
              f"Score={strategy['ranking_score']:.1f}")
```

---

## 🚀 BACKEND ENHANCEMENTS

### **1. Optimization Results Router**

**File: `/app/backend/optimization_router.py`**

```python
"""
Backend API for optimization results
Enhanced version with ranking and comparison
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import os

router = APIRouter(prefix="/api/optimization", tags=["Strategy Optimization"])

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get('MONGO_URL')
client = AsyncIOMotorClient(MONGO_URL)
db = client['ctrader_bot_factory']

# Collections
optimization_runs = db['optimization_runs']
strategy_leaderboard = db['strategy_leaderboard']


class StrategyVariation(BaseModel):
    variation_id: str
    strategy_name: str
    rank: int
    parameters: Dict
    performance: Dict
    ranking_score: float
    score_breakdown: Dict
    viability: Dict


class OptimizationRun(BaseModel):
    optimization_run: Dict
    top_strategies: List[StrategyVariation]
    summary_statistics: Dict
    all_results: List[StrategyVariation]


@router.post("/upload")
async def upload_optimization_results(results: OptimizationRun):
    """Upload complete optimization run"""
    
    result_doc = results.dict()
    result_doc['uploaded_at'] = datetime.utcnow()
    
    # Store full run
    insert_result = await optimization_runs.insert_one(result_doc)
    
    # Update leaderboard with top strategies
    for strategy in results.top_strategies:
        await update_leaderboard(strategy.dict(), results.optimization_run['run_id'])
    
    return {
        "status": "success",
        "run_id": results.optimization_run['run_id'],
        "mongo_id": str(insert_result.inserted_id),
        "top_strategies_count": len(results.top_strategies),
        "total_variations": len(results.all_results)
    }


async def update_leaderboard(strategy: Dict, run_id: str):
    """Update global strategy leaderboard"""
    
    # Check if strategy already exists
    existing = await strategy_leaderboard.find_one({
        "strategy_name": strategy['strategy_name'],
        "variation_id": strategy['variation_id']
    })
    
    if existing:
        # Update if better score
        if strategy['ranking_score'] > existing.get('ranking_score', 0):
            await strategy_leaderboard.update_one(
                {"_id": existing['_id']},
                {
                    "$set": {
                        **strategy,
                        "run_id": run_id,
                        "last_updated": datetime.utcnow()
                    }
                }
            )
    else:
        # Insert new
        await strategy_leaderboard.insert_one({
            **strategy,
            "run_id": run_id,
            "first_seen": datetime.utcnow(),
            "last_updated": datetime.utcnow()
        })


@router.get("/runs/list")
async def list_optimization_runs(limit: int = 20):
    """List recent optimization runs"""
    
    cursor = optimization_runs.find().sort("uploaded_at", -1).limit(limit)
    runs = await cursor.to_list(length=limit)
    
    for r in runs:
        r['_id'] = str(r['_id'])
        # Return summary only
        r.pop('all_results', None)  # Don't return all results in list
    
    return runs


@router.get("/runs/{run_id}")
async def get_optimization_run(run_id: str):
    """Get specific optimization run"""
    
    result = await optimization_runs.find_one({"optimization_run.run_id": run_id})
    
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    
    result['_id'] = str(result['_id'])
    return result


@router.get("/leaderboard")
async def get_leaderboard(
    min_pf: float = Query(default=1.0),
    max_dd: float = Query(default=100.0),
    min_trades: int = Query(default=0),
    limit: int = Query(default=50)
):
    """
    Get global strategy leaderboard with filters
    
    Filters:
    - min_pf: Minimum profit factor
    - max_dd: Maximum drawdown %
    - min_trades: Minimum trade count
    """
    
    query = {
        "performance.profit_factor": {"$gte": min_pf},
        "performance.max_drawdown_pct": {"$lte": max_dd},
        "performance.total_trades": {"$gte": min_trades}
    }
    
    cursor = strategy_leaderboard.find(query).sort("ranking_score", -1).limit(limit)
    strategies = await cursor.to_list(length=limit)
    
    for s in strategies:
        s['_id'] = str(s['_id'])
    
    return strategies


@router.get("/top-strategies")
async def get_top_strategies(
    strategy_type: Optional[str] = None,
    viable_only: bool = True,
    limit: int = 10
):
    """Get top performing strategies"""
    
    query = {}
    
    if strategy_type:
        query["strategy_name"] = strategy_type
    
    if viable_only:
        query["viability.is_viable"] = True
    
    cursor = strategy_leaderboard.find(query).sort("ranking_score", -1).limit(limit)
    strategies = await cursor.to_list(length=limit)
    
    for s in strategies:
        s['_id'] = str(s['_id'])
    
    return strategies


@router.get("/compare")
async def compare_strategies(variation_ids: str = Query(...)):
    """
    Compare multiple strategies
    
    variation_ids: Comma-separated list of variation IDs
    """
    
    ids = variation_ids.split(',')
    
    strategies = []
    for var_id in ids:
        strategy = await strategy_leaderboard.find_one({"variation_id": var_id})
        if strategy:
            strategy['_id'] = str(strategy['_id'])
            strategies.append(strategy)
    
    if not strategies:
        raise HTTPException(status_code=404, detail="No strategies found")
    
    return {
        "strategies": strategies,
        "comparison": {
            "best_pf": max(s['performance']['profit_factor'] for s in strategies),
            "best_return": max(s['performance']['return_pct'] for s in strategies),
            "lowest_dd": min(s['performance']['max_drawdown_pct'] for s in strategies)
        }
    }


@router.delete("/runs/{run_id}")
async def delete_optimization_run(run_id: str):
    """Delete optimization run"""
    
    delete_result = await optimization_runs.delete_one({"optimization_run.run_id": run_id})
    
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return {"status": "success"}
```

---

### **2. Add Router to Server**

**File: `/app/backend/server.py` (modify)**

```python
# Add import
from optimization_router import router as optimization_router

# Add router
app.include_router(optimization_router)
```

---

**Continue in next message for UI implementation and complete workflow...**
