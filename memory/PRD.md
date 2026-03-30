# PRD: cTrader Bot Factory - XAUUSD Mean Reversion Strategy

## Project Overview
Automated trading bot factory for cTrader platform, currently focusing on XAUUSD Mean Reversion strategy optimization.

## Current Status: RISK OPTIMIZATION COMPLETE ✅

### Work Completed
- ✅ **Task 1:** Data cleaning and validation (EURUSD, XAUUSD)
- ✅ **Task 2:** Baseline backtests completed
- ✅ **Task 3:** Deep diagnostics (edge identified)
- ✅ **Task 4:** Strategy improvement (Filtering approach rejected)
- ✅ **Task 5:** Risk Optimization - COMPLETED

### Task 5 Results Summary

| Metric | Baseline | Risk-Optimized | Target |
|--------|----------|----------------|--------|
| Profit Factor | 2.46 | 2.09-2.15 | ≥ 2.0 ✅ |
| Max Drawdown | 54% | 5-13% | < 25% ✅ |
| Win Rate | 34% | 34-46% | Any |
| Trades | 107 | 107 | Any |

### Recommended Configuration
```json
{
  "risk_per_trade_pct": 0.75,
  "max_position_size_lots": 0.5,
  "equity_scaling": {
    "enabled": true,
    "reduce_at_10pct_dd": 0.5,
    "reduce_at_20pct_dd": 0.25
  },
  "max_concurrent_trades": 5,
  "daily_loss_cap_pct": 5.0,
  "weekly_loss_cap_pct": 10.0
}
```

## User Personas
1. **Retail Trader:** Wants automated profitable strategy with controlled risk
2. **Prop Firm Trader:** Needs strict DD limits for funded account rules

## Core Requirements (Static)
- Mean Reversion entry logic: Bollinger Bands + RSI
- Exit at middle BB (mean target)
- Stop loss: 1.5x ATR
- Risk-based position sizing

## What's Been Implemented
- [x] Data pipeline (Dukascopy provider)
- [x] Backtesting engine with risk-based sizing
- [x] Mean Reversion strategy module
- [x] Trend Following strategy module
- [x] cBot C# code generator
- [x] Risk optimization testing framework
- [x] Phase 1 & 2 optimization complete

## Prioritized Backlog

### P0 (Awaiting Approval)
- [ ] Generate production-ready cBot with optimized risk settings

### P1 (Next)
- [ ] Walk-forward validation
- [ ] Out-of-sample testing
- [ ] Monte Carlo simulation
- [ ] Compile gate verification

### P2 (Future)
- [ ] Multi-timeframe analysis
- [ ] Market regime detection integration
- [ ] EURUSD strategy optimization
- [ ] Portfolio allocation module

## Next Tasks
1. **Await user approval** for cBot generation
2. Generate C# cBot code with risk management
3. Validate compilation (no errors/warnings)
4. Provide download-ready .algo file

---
*Last Updated: March 30, 2026*
