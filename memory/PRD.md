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
- **Strategy Factory + Bot Engine Integration**
- **Guided 5-Step Pipeline Flow**

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
| Strategy-to-Bot Pipeline | server.py | ✅ Working |
| **Pipeline Tracker UI** | PipelineTracker.jsx | ✅ **NEW** |

### Guided Pipeline Flow (5 Steps)
```
STEP 1: Generate Strategies → Factory creates 10 validated strategies
STEP 2: View Top Strategies → Ranked by fitness score
STEP 3: Select Strategy → User chooses best performer
STEP 4: Generate cBot → Convert to C# executable
STEP 5: Run Pipeline → Safety → Compile → Backtest → MC → WF
```

### Bot Status Progression
```
Strategy Factory → [fitness >= 25] → Bot Generation
                                          ↓
                   ┌─────────────────────────────────────┐
                   │ PIPELINE STAGES:                    │
                   │ 1. Safety Injection (20 pts)        │
                   │ 2. Compile Check (20 pts)           │
                   │ 3. Backtest Validation (20 pts)     │
                   │ 4. Monte Carlo (20 pts)             │
                   │ 5. Walk-Forward (20 pts)            │
                   └─────────────────────────────────────┘
                                          ↓
                   Bot Status: draft → validated → robust → ready
```

### Data Status (Apr 9, 2026)
- EURUSD: 2,272,057 candles (1m), available 1m, 5m, 15m, 30m, 1h
- XAUUSD: Present with M1 and H1 data

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
- [x] Strategy-to-Bot Conversion Pipeline
- [x] Bot Status System (draft/validated/robust/ready)
- [x] **Guided 5-Step Pipeline Flow**
- [x] **Quick Start Flow (10 strategies → top 5)**
- [x] **Advanced Mode Toggle for Debug**
- [x] **Strategy Fitness Breakdown UI**
- [x] **Pipeline Visual Tracker**
- [x] **Real-time Pipeline Logs**

## API Endpoints

### Core Endpoints
- `POST /api/factory/generate` - Generate strategies from templates
- `GET /api/factory/status/{run_id}` - Check factory run status
- `GET /api/factory/result/{run_id}` - Get factory results

### Pipeline Endpoints
- `POST /api/bot/generate-from-strategy` - Generate cBot from validated strategy
- `GET /api/bot/pipeline-status/{session_id}` - Check pipeline bot status
- `GET /api/bot/pipeline-list` - List all pipeline bots

## Frontend Components

### New Pipeline Components (PipelineTracker.jsx)
- `PipelineTracker` - 5-step visual flow indicator
- `BotPipelineStatus` - Stage-by-stage progress tracker
- `StrategyFitnessCard` - Fitness component breakdown
- `QuickStartFlow` - One-click strategy generation
- `AdvancedModeToggle` - Debug mode switch

## Prioritized Backlog

### P0 - Critical
- [x] Guided Pipeline Flow UI
- [x] Quick Start Flow
- [ ] Import more historical data (2021-2026)

### P1 - High
- [ ] Strategy comparison view
- [ ] Multi-symbol validation
- [ ] Prop firm compliance integration

### P2 - Medium
- [ ] Paper trading mode
- [ ] Performance analytics dashboard
- [ ] Strategy export to cBot C#

### P3 - Future
- [ ] 1m aggregation architecture
- [ ] Real-time market data integration
- [ ] Portfolio optimization
