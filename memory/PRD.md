# cTrader Bot Factory - Product Requirements Document

**Created:** January 2026  
**Last Updated:** January 2026  
**Version:** 1.0  

---

## Original Problem Statement
Complete system audit of AI Trading System + cTrader Bot Factory repository to identify:
- All existing components
- What is implemented and working
- What is partially implemented
- What is missing (critical gaps)
- Code quality assessment
- System flow analysis
- Recommended next steps

---

## System Architecture

```
Data Pipeline → Strategy Generation → Backtesting → Risk Analysis → Output
     │                   │                │              │            │
     ▼                   ▼                ▼              ▼            ▼
 Dukascopy/CSV    Multi-AI Engine   Real Backtester  Prop Firm    C# cBot
   BI5 Decoder       GPT/Claude      Walk-Forward    Compliance   .algo file
   Aggregator       Competition      Monte Carlo    Challenge Sim
```

---

## User Personas

### Primary Users
1. **Algorithmic Traders** - Want to generate and test trading strategies
2. **Prop Firm Traders** - Need strategies compliant with FTMO, FundedNext, etc.
3. **Strategy Developers** - Want to optimize existing strategies

### Secondary Users
1. **Trading Educators** - Use for teaching backtesting concepts
2. **Quant Researchers** - Validate strategy ideas before deployment

---

## Core Requirements (Static)

### Must Have
- [ ] AI-powered strategy generation (GPT, Claude, DeepSeek)
- [ ] Backtesting on historical data
- [ ] Real C# code compilation and validation
- [ ] Prop firm compliance checking
- [ ] Downloadable cBot code

### Should Have
- [ ] Portfolio management
- [ ] Strategy optimization
- [ ] Walk-forward testing
- [ ] Monte Carlo simulation

### Nice to Have
- [ ] Live trading integration
- [ ] Paper trading mode
- [ ] Strategy marketplace

---

## Implementation Status

### Completed (January 2026)
| Feature | Status | Files |
|---------|--------|-------|
| Dukascopy Data Pipeline | ✅ Done | dukascopy_downloader.py, bi5_decoder.py, tick_aggregator.py |
| Multi-AI Strategy Generation | ✅ Done | multi_ai_engine.py, server.py |
| Real Candle Backtesting | ✅ Done | backtest_real_engine.py, backtest_calculator.py |
| C# Compilation | ✅ Done | real_csharp_compiler.py, compile_gate.py |
| Prop Firm Compliance | ✅ Done | compliance_engine.py, challenge_engine.py |
| Portfolio Management | ✅ Done | portfolio_engine.py, portfolio_router.py |
| Strategy Optimization (GA) | ✅ Done | optimizer_engine.py, factory_engine.py |
| Walk-Forward Testing | ✅ Done | walkforward_engine.py |
| Monte Carlo Simulation | ✅ Done | montecarlo_engine.py |
| Trade Logging | ✅ Done | execution/trade_logging.py |
| Discovery Pipeline | ✅ Done | discovery/pipeline.py |
| Frontend UI | ✅ Done | All page components |

### Not Started
| Feature | Priority |
|---------|----------|
| User Authentication | P0 - Critical |
| Paper Trading Mode | P1 - High |
| Live Trading Integration | P1 - High |
| Strategy Versioning | P2 - Medium |
| Multi-Symbol Backtesting | P2 - Medium |

---

## Prioritized Backlog

### P0 - Critical (Blockers)
1. Add JWT authentication system
2. Implement user-strategy relationship

### P1 - High (Important)
3. Create paper trading environment
4. Research cTrader Open API integration
5. Add multi-symbol backtesting support

### P2 - Medium (Enhancements)
6. Strategy versioning system
7. Scheduled re-optimization
8. API rate limiting

### P3 - Low (Nice to Have)
9. News event calendar integration
10. Strategy marketplace
11. Advanced analytics dashboard

---

## Next Tasks List

1. **This Session**: System audit completed, report generated
2. **Next Session**: Implement authentication if requested
3. **Future**: Paper trading → Live trading integration

---

## Technical Notes

### Stack
- **Backend**: FastAPI, Motor (MongoDB), Pydantic
- **Frontend**: React, React Router, Tailwind CSS, shadcn/ui
- **AI**: emergentintegrations library (GPT-5.2, Claude Sonnet)
- **Compilation**: .NET 6.0 SDK with cTrader.Automate NuGet

### Data Locations
- CSV Data: `/data/{SYMBOL}/{TIMEFRAME}/{YEAR}.csv`
- Database: MongoDB (MONGO_URL from env)
- Tests: `/backend/tests/`

### Key APIs
- `/api/bot/generate` - Generate cBot from prompt
- `/api/backtest/simulate` - Run backtest
- `/api/strategy/auto-generate` - Auto-generate strategies
- `/api/portfolio/*` - Portfolio management
- `/api/challenge/*` - Prop firm simulation
