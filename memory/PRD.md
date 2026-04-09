# cTrader Bot Factory - Product Requirements Document

**Last Updated:** April 9, 2026

## Original Problem Statement
Build AI Trading Strategy Validation & Backtesting System with:
- Data pipeline (Dukascopy/CSV import)
- Strategy generation (Template-based + AI-powered)
- Backtesting engine with real market data
- Walk-forward validation (70/30 split, multi-period)
- Filtering (PF, DD, WR, trades)
- Stability scoring and overfitting detection
- Job-based execution system with progress tracking

## Architecture Summary

### Core Components
| Component | File | Status |
|-----------|------|--------|
| Strategy Factory | factory_engine.py | ✅ Working |
| Backtesting Engine | backtest_real_engine.py | ✅ Working |
| Walk-Forward Validation | walkforward_validator.py | ✅ Working |
| Job Tracker | strategy_job_tracker.py | ✅ Working |
| Data Service | market_data_service.py | ✅ Working |
| Scoring Engine | scoring_engine.py | ✅ Working |

### Data Status (Apr 9, 2026)
- EURUSD H1: 946 candles (2020-2024)
- EURUSD M1: 8,819 candles
- XAUUSD H1: 386 candles
- XAUUSD M1: 8,400 candles

## Implementation Status

### Completed Features
- [x] CSV Data Import Pipeline
- [x] Data Integrity Check (blocks synthetic data)
- [x] Template-based Strategy Generation (5 templates)
- [x] Parameterized Backtesting
- [x] Walk-Forward Validation (single + multi-period)
- [x] Fitness Scoring (Sharpe, PF, DD, Monte Carlo)
- [x] Job Progress Tracking
- [x] Factory Pipeline (generate → evaluate → rank)

### Branches Analysis
- **main** (current): Full walkforward_validator.py, strategy_job_tracker.py
- **conflict_080426_2112**: Experimental 1m aggregation architecture (NOT merged)

## Prioritized Backlog

### P0 - Critical
- [ ] Import more EURUSD data (2021-2026)
- [ ] LLM budget top-up for AI strategy generation

### P1 - High
- [ ] Multi-symbol validation
- [ ] Prop firm compliance integration
- [ ] Live trading signal generation

### P2 - Medium
- [ ] Paper trading mode
- [ ] Performance analytics dashboard
- [ ] Strategy export to cBot C#

### P3 - Future
- [ ] 1m aggregation architecture (from conflict branch)
- [ ] Real-time market data integration
- [ ] Portfolio optimization

## API Endpoints

### Core Endpoints
- `POST /api/factory/generate` - Generate strategies from templates
- `GET /api/factory/status/{run_id}` - Check factory run status
- `GET /api/factory/result/{run_id}` - Get factory results
- `POST /api/strategy/generate-job` - Create AI strategy job
- `GET /api/strategy/job-status/{job_id}` - Track job progress
- `GET /api/data-integrity/check` - Verify data quality
- `GET /api/marketdata/available` - List available datasets

## Configuration

### Environment Variables
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
EMERGENT_LLM_KEY=<required for AI generation>
```

### Strategy Templates
1. EMA Crossover
2. RSI Mean Reversion
3. MACD Trend Following
4. Bollinger Breakout
5. ATR Volatility Breakout
