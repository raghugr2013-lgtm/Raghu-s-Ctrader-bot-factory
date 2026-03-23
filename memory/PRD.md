# AI cTrader Bot Factory - PRD

## Original Problem Statement
Setup and run existing AI cTrader Bot Factory system from GitHub repository.

## Architecture
- **Backend**: FastAPI with 89 Python files, 12 routers
- **Frontend**: React with 11 pages
- **Database**: MongoDB
- **AI**: Multi-AI engine using emergentintegrations (OpenAI, Claude, DeepSeek)

## Core Requirements
1. Bot generation with AI (Single, Collaboration, Competition modes)
2. Code validation with Roslyn compiler
3. Prop firm compliance checking (FTMO, PipFarm, FundedNext, The5ers)
4. Backtesting with Monte Carlo and Walk-Forward analysis
5. Portfolio management
6. Live trading dashboard

## What's Been Implemented (Existing System)
- ✅ Complete bot factory system from GitHub (Mar 22, 2026)
- ✅ All routers registered and working
- ✅ AI integration configured with EMERGENT_LLM_KEY
- ✅ Full pipeline validation working

## Key Modules
- multi_ai_engine.py - AI orchestration
- backtest_real_engine.py - Backtesting
- montecarlo_engine.py - Monte Carlo simulation
- walkforward_engine.py - Walk-forward validation
- compile_gate.py - Compilation verification

## API Endpoints Verified
- POST /api/validation/full-pipeline
- POST /api/bot/generate
- GET /api/compliance/profiles

## Backlog / Future
- P1: Configure TwelveData/AlphaVantage for real market data
- P2: Add more prop firm profiles
- P3: Enhanced live trading features
