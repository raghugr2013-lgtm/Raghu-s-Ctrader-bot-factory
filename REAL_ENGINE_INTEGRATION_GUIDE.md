# 🔧 REAL ENGINE INTEGRATION GUIDE

## Connecting Actual Validation Engines to Pipeline

This document shows how to integrate real backtest, Monte Carlo, and walk-forward engines into the unified pipeline.

---

## 📊 STAGE 3: BACKTEST - REAL IMPLEMENTATION

### Import Real Backtest Engine
```python
from backtest_real_engine import RealBacktester
from backtest_calculator import BacktestCalculator
```

### Updated `_backtest` Method
```python
async def _backtest(self, strategy: Strategy) -> PipelineResult:
    """
    Stage 3: Backtest strategy with REAL Dukascopy data.
    """
    strategy.current_stage = PipelineStage.BACKTESTING
    strategy.logs.append("Running backtest on Dukascopy data...")
    
    try:
        # Initialize real backtester
        backtester = RealBacktester()
        calculator = BacktestCalculator()
        
        # Run backtest with real data
        # Default: EURUSD, 2 years, 1H timeframe
        backtest_result = await backtester.run(
            strategy_code=strategy.code,
            symbol="EURUSD",
            timeframe="1H",
            start_date="2024-01-01",
            end_date="2026-01-01",
            initial_balance=10000
        )
        
        # Calculate real metrics
        metrics = calculator.calculate_metrics(backtest_result.trades)
        
        # Store real metrics
        strategy.metrics.total_return = metrics.total_return_pct
        strategy.metrics.sharpe_ratio = metrics.sharpe_ratio
        strategy.metrics.max_drawdown = metrics.max_drawdown_pct
        strategy.metrics.win_rate = metrics.win_rate_pct
        strategy.metrics.profit_factor = metrics.profit_factor
        strategy.metrics.total_trades = len(backtest_result.trades)
        
        strategy.backtest_completed = True
        strategy.logs.append(
            f"✓ Backtest completed: {strategy.metrics.total_trades} trades, "
            f"{strategy.metrics.total_return:.1f}% return"
        )
        
        result = PipelineResult(
            success=True,
            message="Backtest completed with real data",
            data={
                "total_return": strategy.metrics.total_return,
                "sharpe_ratio": strategy.metrics.sharpe_ratio,
                "max_drawdown": strategy.metrics.max_drawdown,
                "trades": strategy.metrics.total_trades
            }
        )
        strategy.backtest_result = result
        
        return result
        
    except Exception as e:
        strategy.errors.append(f"Backtest failed: {str(e)}")
        raise
```

---

## 🎲 STAGE 4: MONTE CARLO - REAL IMPLEMENTATION

### Import Monte Carlo Engine
```python
from montecarlo_engine import MonteCarloEngine
```

### Updated `_monte_carlo` Method
```python
async def _monte_carlo(self, strategy: Strategy) -> PipelineResult:
    """
    Stage 4: Run REAL Monte Carlo simulation.
    """
    strategy.current_stage = PipelineStage.MONTE_CARLO
    strategy.logs.append("Running Monte Carlo simulation...")
    
    try:
        # Get trades from backtest
        if not strategy.backtest_result:
            raise ValueError("Must complete backtest before Monte Carlo")
        
        trades = strategy.backtest_result.data.get("trades_data", [])
        
        # Initialize Monte Carlo engine
        mc_engine = MonteCarloEngine()
        
        # Run 1000 simulations
        mc_result = await mc_engine.run_simulation(
            trades=trades,
            initial_balance=10000,
            num_simulations=1000
        )
        
        # Extract real metrics
        strategy.metrics.mc_confidence_95 = mc_result.confidence_95_pct
        strategy.metrics.mc_worst_case = mc_result.worst_case_pct
        strategy.metrics.mc_best_case = mc_result.best_case_pct
        
        strategy.monte_carlo_completed = True
        strategy.logs.append(
            f"✓ Monte Carlo completed: 1000 runs, "
            f"95% confidence: {strategy.metrics.mc_confidence_95:.1f}%"
        )
        
        result = PipelineResult(
            success=True,
            message="Monte Carlo simulation completed",
            data={
                "confidence_95": strategy.metrics.mc_confidence_95,
                "worst_case": strategy.metrics.mc_worst_case,
                "best_case": strategy.metrics.mc_best_case,
                "simulations": 1000
            }
        )
        strategy.monte_carlo_result = result
        
        return result
        
    except Exception as e:
        strategy.errors.append(f"Monte Carlo failed: {str(e)}")
        raise
```

---

## ➡️ STAGE 5: FORWARD TEST - REAL IMPLEMENTATION

### Import Walk-Forward Engine
```python
from walkforward_engine import WalkForwardEngine
```

### Updated `_forward_test` Method
```python
async def _forward_test(self, strategy: Strategy) -> PipelineResult:
    """
    Stage 5: Run REAL walk-forward test.
    """
    strategy.current_stage = PipelineStage.FORWARD_TEST
    strategy.logs.append("Running walk-forward test...")
    
    try:
        # Initialize walk-forward engine
        wf_engine = WalkForwardEngine()
        
        # Run walk-forward analysis
        # 12 periods, 80% train / 20% test split
        wf_result = await wf_engine.run_analysis(
            strategy_code=strategy.code,
            symbol="EURUSD",
            timeframe="1H",
            start_date="2024-01-01",
            end_date="2026-01-01",
            num_windows=12,
            train_pct=0.8
        )
        
        # Calculate forward metrics
        strategy.metrics.forward_return = wf_result.avg_return_pct
        strategy.metrics.forward_sharpe = wf_result.avg_sharpe
        strategy.metrics.forward_consistency = wf_result.consistency_score
        
        strategy.forward_test_completed = True
        strategy.logs.append(
            f"✓ Walk-forward completed: 12 windows, "
            f"{strategy.metrics.forward_return:.1f}% avg return"
        )
        
        result = PipelineResult(
            success=True,
            message="Forward test completed",
            data={
                "forward_return": strategy.metrics.forward_return,
                "forward_sharpe": strategy.metrics.forward_sharpe,
                "consistency": strategy.metrics.forward_consistency,
                "windows": 12
            }
        )
        strategy.forward_test_result = result
        
        return result
        
    except Exception as e:
        strategy.errors.append(f"Forward test failed: {str(e)}")
        raise
```

---

## 🔄 COMPLETE INTEGRATION

### Full Updated unified_pipeline.py Imports
```python
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import uuid

# Real engine imports
from backtest_real_engine import RealBacktester
from backtest_calculator import BacktestCalculator
from montecarlo_engine import MonteCarloEngine
from walkforward_engine import WalkForwardEngine
```

---

## ✅ VALIDATION CHECKLIST

After implementing real engines:

### Backtest Stage
- [ ] Returns actual trade data
- [ ] Metrics match Dukascopy data
- [ ] Drawdown calculation accurate
- [ ] Win rate reflects actual trades
- [ ] Sharpe ratio properly calculated

### Monte Carlo Stage
- [ ] Uses real trade sequences
- [ ] Runs 1000 simulations
- [ ] Confidence intervals valid
- [ ] Worst-case realistic
- [ ] Results reproducible

### Forward Test Stage
- [ ] Split data correctly (80/20)
- [ ] 12 optimization windows
- [ ] Out-of-sample performance measured
- [ ] Consistency score accurate
- [ ] Degradation tracked

---

## 🧪 TESTING PROCEDURE

### Test Real Pipeline
```python
# Submit strategy
strategy = await pipeline.process_strategy(
    code=test_strategy_code,
    name="Test Strategy",
    entry_point=EntryPoint.AI_GENERATION
)

# Verify real results
assert strategy.backtest_completed
assert strategy.metrics.total_trades > 0  # Real trades
assert 0 <= strategy.metrics.win_rate <= 100  # Valid percentage
assert strategy.metrics.sharpe_ratio != 0  # Not mock value

assert strategy.monte_carlo_completed
assert strategy.metrics.mc_confidence_95 != 12.0  # Not hardcoded

assert strategy.forward_test_completed
assert strategy.metrics.forward_return != 8.5  # Not hardcoded
```

---

## 📊 EXPECTED REALISTIC RANGES

### Backtest Metrics
- **Total Return**: -50% to +200% (varies widely)
- **Sharpe Ratio**: -2.0 to +4.0 (good: > 1.0)
- **Max Drawdown**: 5% to 50% (good: < 20%)
- **Win Rate**: 30% to 70% (typical: 50-60%)
- **Profit Factor**: 0.5 to 3.0 (good: > 1.5)
- **Total Trades**: 50 to 500 (2-year backtest)

### Monte Carlo Metrics
- **95% Confidence**: -20% to +100%
- **Worst Case**: -50% to +20%
- **Best Case**: +20% to +300%

### Forward Test Metrics
- **Forward Return**: -30% to +100%
- **Forward Sharpe**: -1.0 to +3.0
- **Consistency**: 0.4 to 0.95 (good: > 0.7)

---

## 🚨 ERROR HANDLING

### Common Issues

**Backtest Fails**:
```python
if not backtest_result.trades:
    strategy.warnings.append("No trades generated in backtest")
    # Use conservative estimates
    strategy.metrics.total_return = 0
    strategy.metrics.total_trades = 0
```

**Monte Carlo Insufficient Data**:
```python
if len(trades) < 30:
    strategy.warnings.append("Insufficient trades for Monte Carlo (need 30+)")
    # Skip Monte Carlo or use limited simulation
```

**Forward Test Data Issues**:
```python
if date_range < 365:  # Less than 1 year
    strategy.warnings.append("Insufficient data for walk-forward (need 1+ year)")
    # Use single train/test split instead
```

---

## 📈 PERFORMANCE OPTIMIZATION

### Parallel Processing
```python
# Run backtest, Monte Carlo, forward test in parallel (when possible)
results = await asyncio.gather(
    self._backtest(strategy),
    self._monte_carlo(strategy),  # After backtest
    self._forward_test(strategy)
)
```

### Caching
```python
# Cache historical data for repeated use
data_cache = {}

def get_market_data(symbol, timeframe, start, end):
    cache_key = f"{symbol}_{timeframe}_{start}_{end}"
    if cache_key not in data_cache:
        data_cache[cache_key] = load_dukascopy_data(...)
    return data_cache[cache_key]
```

---

## 🎯 NEXT STEPS

1. **Update unified_pipeline.py** with real engine imports
2. **Replace placeholder methods** with actual implementations
3. **Test each stage** independently
4. **Test complete pipeline** end-to-end
5. **Verify metrics** match expected ranges
6. **Add error handling** for edge cases
7. **Optimize performance** for speed

---

**Status**: Implementation Guide Complete  
**Timeline**: 1-2 days to integrate all real engines  
**Priority**: High - Core validation depends on this
