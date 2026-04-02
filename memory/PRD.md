# cTrader Bot Factory - Product Requirements Document

**Last Updated:** January 2026

## Original Problem Statement
Build AI Trading System + cTrader Bot Factory with:
- Data pipeline (Dukascopy/CSV)
- AI strategy generation (GPT-5.2, Claude, DeepSeek)
- Backtesting engine
- cBot export (C#)
- Portfolio management

## Implementation Status

### Completed (Jan 2026)
| Feature | Files |
|---------|-------|
| Dukascopy Data Pipeline | dukascopy_downloader.py, bi5_decoder.py |
| Multi-AI Strategy Generation | multi_ai_engine.py, server.py |
| Real Candle Backtesting | backtest_real_engine.py |
| C# Compilation | real_csharp_compiler.py, compile_gate.py |
| Prop Firm Compliance | compliance_engine.py, challenge_engine.py |
| Portfolio Management | portfolio_engine.py |
| **DELETE Data Functionality** | server.py (endpoint), MarketDataPage.jsx (UI) |
| **All Timeframes (M1-W1)** | market_data_models.py, MarketDataPage.jsx |

### API Endpoints
- `DELETE /api/marketdata/{symbol}/{timeframe}` - Delete dataset
- `POST /api/marketdata/import/csv` - Upload CSV
- `GET /api/marketdata/available` - List datasets
- `POST /api/factory/generate` - Generate strategies

### Prioritized Backlog
- P0: User Authentication
- P1: Live Trading Integration
- P2: Paper Trading Mode
- P3: Multi-symbol backtesting
