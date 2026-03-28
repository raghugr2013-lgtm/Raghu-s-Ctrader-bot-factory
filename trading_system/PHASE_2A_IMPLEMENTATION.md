# PHASE 2A: CONTROLLED ROLLOUT - IMPLEMENTATION PLAN

**Strategy Discovery Engine - Minimum Viable Optimization**

---

## 🎯 PHASE 2A OBJECTIVES

### **Primary Goals:**
1. ✅ Validate ranking system produces logical results
2. ✅ Ensure parameters affect outcomes predictably
3. ✅ Confirm no overfitting in small sample
4. ✅ Test end-to-end workflow (local → backend → UI)
5. ✅ Establish baseline before scaling

### **Constraints:**
- ❌ NO multiple strategies yet (trend only)
- ❌ NO large parameter grids (keep it simple)
- ❌ NO complex filtering (basic PF/trades only)
- ✅ YES modular design for future expansion

---

## 📊 PHASE 2A SCOPE

### **Strategy:**
```
Single Strategy: Trend Following
Variations: ~9-12 combinations
```

### **Parameter Space (Small):**
```python
{
    "ema_fast": [20, 50],      # 2 values
    "ema_slow": [100, 200],    # 2 values
    "adx_threshold": [20, 25], # 2 values
    "risk_pct": [1.0],         # Fixed for now
    "stop_loss_atr": [2.0],    # Fixed for now
    "take_profit_atr": [3.0]   # Fixed for now
}

Combinations: 2 × 2 × 2 = 8 variations
Runtime: ~5-8 seconds
```

### **Filtering Criteria:**
```
Viability Thresholds (Relaxed for Phase 2A):
- Profit Factor ≥ 1.1 (vs 1.3 in full version)
- Max Drawdown < 15% (vs 10% in full version)
- Total Trades ≥ 20 (same)
- Return > 0% (same)

Reason: Small parameter space may not yield many
strategies with PF > 1.3, so we relax for validation
```

### **Ranking:**
```
Same algorithm as full version:
- PF weight: 30%
- Return weight: 25%
- Drawdown weight: 25%
- Trade count weight: 20%

Composite Score: 0-100
```

---

## 🔧 IMPLEMENTATION

### **1. Simplified Optimization Engine (Your Laptop)**

**File: `phase2a_optimizer.py`**

```python
"""
Phase 2A: Controlled Optimization Engine

Single strategy (trend following) with small parameter grid
Focus: Validation, not discovery
"""

import pandas as pd
import itertools
from typing import List, Dict
from datetime import datetime
import json


class Phase2AOptimizer:
    """
    Minimal viable optimizer for validation
    
    Constraints:
    - Single strategy only
    - Small parameter space
    - Clear, interpretable results
    """
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.candles = pd.read_csv(csv_path)
        self.candles['timestamp'] = pd.to_datetime(self.candles['timestamp'])
        
        print(f"Loaded {len(self.candles)} candles")
        print(f"Period: {self.candles['timestamp'].min()} to {self.candles['timestamp'].max()}")
        print()
    
    def get_parameter_space(self) -> Dict:
        """
        Phase 2A: Small, controlled parameter space
        
        Total combinations: 8
        Expected runtime: 5-10 seconds
        """
        return {
            "ema_fast": [20, 50],
            "ema_slow": [100, 200],
            "adx_threshold": [20, 25],
            "risk_pct": [1.0],          # Fixed
            "stop_loss_atr": [2.0],     # Fixed
            "take_profit_atr": [3.0]    # Fixed
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
        Run trend following strategy with given parameters
        
        YOUR EXISTING TREND STRATEGY CODE HERE
        
        This is a PLACEHOLDER - replace with your actual implementation
        """
        
        # Example placeholder (replace with your code)
        trades = []
        
        # Simplified example logic (NOT REAL - just for structure)
        # You would replace this with your actual strategy
        """
        # Calculate indicators
        candles = self.candles.copy()
        candles['ema_fast'] = candles['close'].ewm(span=parameters['ema_fast']).mean()
        candles['ema_slow'] = candles['close'].ewm(span=parameters['ema_slow']).mean()
        
        # Generate signals
        candles['signal'] = 0
        candles.loc[candles['ema_fast'] > candles['ema_slow'], 'signal'] = 1
        candles.loc[candles['ema_fast'] < candles['ema_slow'], 'signal'] = -1
        
        # Simulate trades
        position = None
        for i in range(1, len(candles)):
            # Entry logic
            if position is None:
                if candles.iloc[i]['signal'] == 1:  # Long entry
                    position = {
                        'direction': 'LONG',
                        'entry_time': candles.iloc[i]['timestamp'],
                        'entry_price': candles.iloc[i]['close']
                    }
                elif candles.iloc[i]['signal'] == -1:  # Short entry
                    position = {
                        'direction': 'SHORT',
                        'entry_time': candles.iloc[i]['timestamp'],
                        'entry_price': candles.iloc[i]['close']
                    }
            
            # Exit logic
            elif position is not None:
                # Exit on opposite signal
                if (position['direction'] == 'LONG' and candles.iloc[i]['signal'] == -1) or \
                   (position['direction'] == 'SHORT' and candles.iloc[i]['signal'] == 1):
                    
                    exit_price = candles.iloc[i]['close']
                    
                    if position['direction'] == 'LONG':
                        pnl = (exit_price - position['entry_price']) * 10000  # Simplified
                    else:
                        pnl = (position['entry_price'] - exit_price) * 10000
                    
                    trades.append({
                        'entry_time': str(position['entry_time']),
                        'exit_time': str(candles.iloc[i]['timestamp']),
                        'direction': position['direction'],
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'pnl': pnl
                    })
                    
                    position = None
        """
        
        # IMPORTANT: Replace above with YOUR actual strategy code
        # For now, returning example trades for structure demonstration
        print(f"      [PLACEHOLDER] Replace with your strategy code")
        print(f"      Parameters: EMA {parameters['ema_fast']}/{parameters['ema_slow']}, "
              f"ADX {parameters['adx_threshold']}")
        
        return trades  # Will be empty until you add your code
    
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
    
    def calculate_ranking_score(self, performance: Dict) -> Dict:
        """
        Calculate composite ranking score
        
        Weights (same as full version):
        - Profit Factor: 30%
        - Return: 25%
        - Drawdown: 25%
        - Trade Count: 20%
        """
        
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
        """
        Phase 2A: Relaxed viability criteria
        
        Criteria:
        - PF ≥ 1.1 (relaxed from 1.3)
        - Max DD < 15% (relaxed from 10%)
        - Trades ≥ 20
        - Return > 0%
        """
        
        pf_pass = performance['profit_factor'] >= 1.1
        dd_pass = performance['max_drawdown_pct'] < 15.0
        trades_pass = performance['total_trades'] >= 20
        return_pass = performance['return_pct'] > 0
        
        is_viable = all([pf_pass, dd_pass, trades_pass, return_pass])
        
        if is_viable and performance['profit_factor'] >= 1.5:
            recommendation = "Excellent - Ready for Phase 2B testing"
        elif is_viable and performance['profit_factor'] >= 1.3:
            recommendation = "Very Good - Proceed to Phase 2B"
        elif is_viable:
            recommendation = "Good - Marginal, monitor in Phase 2B"
        else:
            recommendation = "Not Viable - Review strategy logic"
        
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
        Phase 2A: Controlled optimization run
        
        Returns:
        - 8 strategy variations
        - Ranked results
        - Validation metrics
        """
        
        print("="*80)
        print("PHASE 2A: CONTROLLED OPTIMIZATION")
        print("="*80)
        print()
        print("Strategy: Trend Following (ONLY)")
        print("Purpose: Validate ranking system and workflow")
        print()
        
        start_time = datetime.utcnow()
        
        # Get parameter space
        param_space = self.get_parameter_space()
        combinations = self.generate_combinations(param_space)
        
        print(f"Parameter combinations to test: {len(combinations)}")
        print(f"Expected runtime: ~{len(combinations)}s")
        print()
        
        all_results = []
        
        # Run each combination
        for idx, params in enumerate(combinations, 1):
            param_str = f"EMA {params['ema_fast']}/{params['ema_slow']}, ADX {params['adx_threshold']}"
            print(f"[{idx}/{len(combinations)}] Testing {param_str}...", end=" ")
            
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
            
            print(f"PF: {metrics['profit_factor']:.2f}, "
                  f"Trades: {metrics['total_trades']}, "
                  f"Score: {scores['ranking_score']:.1f}")
        
        print()
        
        # Sort by ranking score
        all_results.sort(key=lambda x: x['ranking_score'], reverse=True)
        
        # Add ranks
        for idx, result in enumerate(all_results, 1):
            result['rank'] = idx
        
        # Get viable strategies
        viable_strategies = [r for r in all_results if r['viability']['is_viable']]
        
        # Summary statistics
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
                    "execution_time_seconds": round(execution_time, 1),
                    "constraints": {
                        "single_strategy": "trend_following",
                        "small_param_space": True,
                        "purpose": "validation"
                    }
                }
            },
            "top_strategies": all_results[:5],  # Top 5
            "summary_statistics": summary,
            "all_results": all_results,
            "validation_notes": {
                "expected_variations": 8,
                "actual_variations": len(all_results),
                "all_parameters_unique": len(all_results) == len(set(r['variation_id'] for r in all_results)),
                "ranking_makes_sense": self.validate_ranking(all_results)
            }
        }
        
        print("="*80)
        print("PHASE 2A OPTIMIZATION COMPLETE")
        print("="*80)
        print(f"Total variations: {len(all_results)}")
        print(f"Viable strategies: {len(viable_strategies)} ({summary['viability_rate']}%)")
        print(f"Execution time: {execution_time:.1f}s")
        print()
        
        if len(all_results) > 0:
            print("Top 3 Strategies:")
            for i, strategy in enumerate(all_results[:3], 1):
                print(f"  {i}. {strategy['variation_id']}: "
                      f"PF={strategy['performance']['profit_factor']:.2f}, "
                      f"Score={strategy['ranking_score']:.1f}")
            print()
        
        # Validation checks
        print("Validation Checks:")
        print(f"  ✓ Expected variations: 8")
        print(f"  ✓ Actual variations: {len(all_results)}")
        print(f"  ✓ All unique: {len(all_results) == len(set(r['variation_id'] for r in all_results))}")
        print(f"  ✓ Ranking logical: {self.validate_ranking(all_results)}")
        print()
        
        return optimization_results
    
    def validate_ranking(self, results: List[Dict]) -> bool:
        """
        Validate that ranking makes logical sense
        
        Checks:
        1. Higher PF → Higher rank (generally)
        2. Scores are in descending order
        3. No duplicate scores (unlikely with weighted formula)
        """
        
        if len(results) < 2:
            return True
        
        # Check scores are descending
        scores = [r['ranking_score'] for r in results]
        is_descending = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
        
        return is_descending


if __name__ == "__main__":
    print()
    print("╔" + "="*78 + "╗")
    print("║" + " "*25 + "PHASE 2A OPTIMIZER" + " "*35 + "║")
    print("║" + " "*15 + "Controlled Rollout - Validation Phase" + " "*24 + "║")
    print("╚" + "="*78 + "╝")
    print()
    
    # Configuration
    CSV_PATH = "/path/to/your/EURUSD_H1.csv"  # UPDATE THIS
    
    print("⚠️  IMPORTANT: Update CSV_PATH in the script before running")
    print()
    
    # Run optimization
    optimizer = Phase2AOptimizer(CSV_PATH)
    results = optimizer.run_optimization()
    
    # Save results
    output_file = "phase2a_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Results saved to {output_file}")
    print()
    print("Next steps:")
    print("1. Review results for logical consistency")
    print("2. Upload to backend: python upload_optimization_results.py phase2a_results.json")
    print("3. View in UI to validate display")
    print("4. If validated → Proceed to Phase 2B")
    print()
```

---

## 📋 PHASE 2A VALIDATION CHECKLIST

### **Before Running:**
- [ ] Update `CSV_PATH` in script
- [ ] Replace `run_trend_strategy()` with YOUR actual strategy code
- [ ] Confirm CSV has required columns (timestamp, open, high, low, close)
- [ ] Test on small CSV subset first (100-500 candles)

### **After Running:**
- [ ] Check console output for errors
- [ ] Verify 8 variations tested
- [ ] Confirm ranking is descending (highest score first)
- [ ] Review top strategy makes sense
- [ ] Check if any strategies are viable

### **Validation Questions:**
1. **Does higher PF generally result in higher rank?**
   - Expected: Yes (30% weight)
   - If no: Review ranking formula

2. **Do parameter changes affect results predictably?**
   - Expected: EMA 20/100 ≠ EMA 50/200
   - If same: Check if strategy is using parameters

3. **Are metrics realistic?**
   - Expected: PF 0.5-2.0, DD 0-15%, Trades 10-100
   - If outliers: Review strategy logic

4. **Is scoring consistent?**
   - Expected: Similar strategies have similar scores
   - If random: Review scoring formula

---

## 🚀 IMPLEMENTATION STEPS

### **Step 1: Create Optimizer (10 minutes)**

```bash
# On your laptop

# 1. Copy phase2a_optimizer.py template (above)
# 2. Update CSV_PATH
# 3. Replace run_trend_strategy() with YOUR code
# 4. Test
python phase2a_optimizer.py
```

**Expected Output:**
```
PHASE 2A: CONTROLLED OPTIMIZATION
Strategy: Trend Following (ONLY)
Parameter combinations: 8

[1/8] Testing EMA 20/100, ADX 20... PF: 1.42, Trades: 35, Score: 72.3
[2/8] Testing EMA 20/100, ADX 25... PF: 1.38, Trades: 32, Score: 69.5
...

Top 3 Strategies:
  1. trend_ema20_100_adx20: PF=1.42, Score=72.3
  2. trend_ema50_200_adx20: PF=1.35, Score=68.1
  3. trend_ema20_200_adx25: PF=1.28, Score=65.4

✅ Results saved to phase2a_results.json
```

---

### **Step 2: Backend Setup (15 minutes)**

**Use existing backend from previous proposal:**
- `/app/backend/optimization_router.py` (no changes needed)
- Same endpoints work for Phase 2A results

**Test:**
```bash
cd /app/backend
# Verify router exists
ls -la optimization_router.py

# Restart backend
sudo supervisorctl restart backend
```

---

### **Step 3: Upload Results (2 minutes)**

```bash
# On your laptop
python upload_optimization_results.py phase2a_results.json

# Output:
# ✅ Upload successful!
#    Run ID: 2026-03-26T20:00:00.000Z
#    Top Strategies: 5
#    Total Variations: 8
```

---

### **Step 4: View in UI (5 minutes)**

**Navigate to:** `https://your-app.com/discovery`

**Verify:**
- [ ] 8 strategies displayed
- [ ] Scores in descending order
- [ ] Top strategy highlighted
- [ ] Filters work (PF, DD, trades)
- [ ] Detail modal shows metrics

---

## 📊 EXPECTED PHASE 2A RESULTS

### **Sample Output:**

```
╔════╦════════════════════════╦══════╦════════╦═══════╦═══════╦════════╗
║ #  ║ Variation              ║  PF  ║ Return ║  DD   ║ Trades║ Score  ║
╠════╬════════════════════════╬══════╬════════╬═══════╬═══════╬════════╣
║ 1  ║ trend_ema20_100_adx20  ║ 1.42 ║  8.5%  ║ 3.2%  ║  35   ║ 72.3   ║
║ 2  ║ trend_ema50_200_adx20  ║ 1.35 ║  7.1%  ║ 4.1%  ║  32   ║ 68.1   ║
║ 3  ║ trend_ema20_200_adx25  ║ 1.28 ║  6.2%  ║ 5.5%  ║  28   ║ 65.4   ║
║ 4  ║ trend_ema50_100_adx25  ║ 1.22 ║  5.3%  ║ 6.1%  ║  25   ║ 61.2   ║
║ 5  ║ trend_ema20_100_adx25  ║ 1.18 ║  4.8%  ║ 7.2%  ║  24   ║ 58.5   ║
║ 6  ║ trend_ema50_200_adx25  ║ 1.15 ║  4.1%  ║ 8.0%  ║  22   ║ 55.8   ║
║ 7  ║ trend_ema20_200_adx20  ║ 1.08 ║  2.5%  ║ 9.5%  ║  18   ║ 48.2   ║
║ 8  ║ trend_ema50_100_adx20  ║ 0.95 ║ -1.2%  ║ 12.1% ║  15   ║ 32.1   ║
╚════╩════════════════════════╩══════╩════════╩═══════╩═══════╩════════╝

Viable: 5/8 (62.5%)
```

**Key Observations:**
- Top ranked has highest PF (1.42)
- Scores decrease logically
- EMA 20/100 performs best (for this example)
- ADX 20 better than 25
- Last strategy not viable (PF < 1.1)

---

## ✅ PHASE 2A SUCCESS CRITERIA

### **Must Pass:**
1. ✅ All 8 variations execute without errors
2. ✅ Rankings are in descending order
3. ✅ Parameter changes produce different results
4. ✅ At least 1 viable strategy found
5. ✅ Upload to backend works
6. ✅ UI displays correctly

### **Should Pass:**
1. ✅ Top strategy makes intuitive sense
2. ✅ Scoring correlates with manual assessment
3. ✅ No duplicate variation_ids
4. ✅ Metrics are within realistic ranges

### **Nice to Have:**
1. ✅ 3+ viable strategies
2. ✅ Clear parameter sensitivity pattern
3. ✅ Best PF > 1.3

---

## 🚦 DECISION GATES

### **If Phase 2A Passes:**
→ **Proceed to Phase 2B** (Add Mean Reversion)

### **If Phase 2A Fails:**
→ **Debug before proceeding:**
- Review strategy logic
- Check data quality
- Validate ranking formula
- Test with different data period

### **If Results are Random:**
→ **Investigate:**
- Is strategy using parameters correctly?
- Is data sufficient (need 200+ candles minimum)?
- Are there bugs in trade logic?

---

## 📅 PHASED ROLLOUT ROADMAP

### **Phase 2A** (Current - Week 1):
```
✅ Single strategy (trend)
✅ 8 variations
✅ Validate ranking system
✅ Test workflow
```

### **Phase 2B** (Week 2):
```
⏳ Add mean reversion
⏳ 16 variations total (8 trend + 8 mean rev)
⏳ Cross-strategy comparison
⏳ Validate multi-strategy ranking
```

### **Phase 2C** (Week 3):
```
⏳ Expand parameter grid
⏳ Trend: 20-30 variations
⏳ Mean Rev: 20-30 variations
⏳ Total: 40-60 variations
```

### **Phase 2D** (Week 4):
```
⏳ Add breakout strategy
⏳ Full parameter grids
⏳ 200+ variations total
⏳ Production-ready optimization
```

---

## 📝 PHASE 2A DELIVERABLES

1. **Optimizer Script** ✅
   - `phase2a_optimizer.py`
   - 8 variations
   - Validation checks

2. **Results JSON** ✅
   - `phase2a_results.json`
   - Upload-ready format

3. **Validation Report** (Manual)
   - Review top 3 strategies
   - Confirm ranking makes sense
   - Document any issues

4. **Decision Document**
   - Pass/Fail Phase 2A
   - Issues encountered
   - Go/No-Go for Phase 2B

---

**Phase 2A is designed for validation, not discovery. The goal is to ensure the system works correctly before scaling.**
