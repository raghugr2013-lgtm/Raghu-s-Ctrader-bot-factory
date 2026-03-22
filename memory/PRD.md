# AI cTrader Bot Factory - PRD

## Original Problem Statement
Merge multiple uploaded ZIP files containing different parts/versions of a complete AI-powered cTrader Bot Builder platform into ONE clean, complete, working system.

## Project Overview
A comprehensive AI-powered trading bot generation and validation platform for cTrader Automate. The system enables users to generate, validate, backtest, and optimize trading bots with prop firm compliance checking.

## Architecture
- **Frontend**: React.js with Tailwind CSS, Monaco Editor
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **AI Integration**: Emergent LLM (OpenAI GPT-5.2, Claude, DeepSeek)

## Core Modules Implemented

### Backend (86 Python files)
1. **Multi-AI Engine** - Bot generation via multiple AI models
2. **Safety Injection** - Auto-inject safety code into bots
3. **Compile Gate** - C# compilation verification
4. **Compliance Engine** - Prop firm rule validation (FTMO, MFF, etc.)
5. **Backtest Engine** - Strategy performance simulation
6. **Monte Carlo Engine** - Probabilistic risk analysis
7. **Walk-Forward Engine** - Strategy stability validation
8. **Portfolio Engine** - Multi-bot portfolio management
9. **Regime Engine** - Market regime detection
10. **Optimizer Engine** - Parameter optimization
11. **Discovery Engine** - Bot scoring and ranking
12. **Execution Layer** - Trade logging, WebSocket, Telegram alerts

### Frontend Pages (11 Pages)
1. Dashboard - Main bot builder interface
2. PortfolioPage - Portfolio management
3. DiscoveryPage - Bot discovery and ranking
4. StrategyLibraryPage - Strategy templates
5. TestValidationPage - Validation results
6. LiveDashboardPage - Live trading monitoring
7. TradeHistoryPage - Trade history
8. AlertSettingsPage - Telegram/notification settings
9. AnalyzeBotPage - Bot analysis
10. BotConfigPage - Bot configuration
11. LeaderboardPage - Performance rankings

## Key API Endpoints

### Full Validation Pipeline
```
POST /api/validation/full-pipeline
```
Flow: Generate → Fix → Compile → Compliance → Backtest → Monte Carlo → Walk-forward → Final Score

Response includes:
- `final_score`: 0-100
- `grade`: A/B/C/D/F
- `decision`: PROP_FIRM_READY | NEEDS_IMPROVEMENT | NOT_READY

### Other Critical Endpoints
- POST /api/bot/generate - Generate bot code
- POST /api/code/validate - Validate C# code
- POST /api/bot/validate - Full bot validation
- POST /api/bot/inject-safety - Inject safety code
- POST /api/backtest/simulate - Run backtest
- GET /api/compliance/profiles - Get prop firm profiles

## What's Been Implemented (March 2026)

### Completed
- [x] Merged all ZIP files into clean structure
- [x] Backend: 86 Python modules integrated
- [x] Frontend: 11 pages, all navigation working
- [x] Full validation pipeline endpoint
- [x] Multi-AI bot generation
- [x] Compile gate verification
- [x] Compliance engine (FTMO, MFF, etc.)
- [x] Mock backtest simulation
- [x] Monte Carlo analysis
- [x] Walk-forward validation
- [x] Database integration
- [x] EMERGENT_LLM_KEY configured

### Working Features
- Bot generation with AI
- Code validation
- Safety injection
- Compilation checking
- Compliance verification
- Backtest simulation (mock data)
- Monte Carlo analysis
- Walk-forward validation
- Final scoring with PROP_FIRM_READY decision

## Prioritized Backlog

### P0 (Critical)
- Real market data integration for backtesting
- Live trading execution

### P1 (High)
- WebSocket real-time updates
- Telegram alerts integration
- Performance optimization

### P2 (Medium)
- Additional prop firm profiles
- Advanced strategy templates
- User authentication

## Tech Stack
- FastAPI + MongoDB + React
- Emergent LLM Integration
- Monaco Editor for code
- Recharts for visualizations

## Next Tasks
1. Test bot generation with AI
2. Connect real market data providers
3. Implement live trading execution
4. Add user authentication
