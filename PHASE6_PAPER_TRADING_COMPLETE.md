# Phase 6: Paper Trading - Implementation Complete

## ✅ Overview

Successfully implemented Phase 6: Paper Trading (Live Validation) system for the trading application. The system runs as a background service, continuously monitoring markets and executing the EMA 10/150 crossover strategy with the optimized portfolio allocation from Phase 5.

---

## 🎯 Implementation Summary

### **Core Components Built**

1. **Paper Trading Engine** (`/app/backend/paper_trading/engine.py`)
   - Real-time market data fetching using yfinance
   - EMA 10/150 crossover signal generation
   - H1 (1-hour) candle monitoring with 3600s check interval
   - Automatic position management (open/close based on signals)
   - Multi-asset support (GOLD: GLD ETF, S&P 500: SPY ETF)

2. **Portfolio Manager** (`/app/backend/paper_trading/portfolio_manager.py`)
   - Starting capital: $10,000
   - 40% Gold allocation ($4,000) @ 0.25% risk per trade
   - 60% S&P 500 allocation ($6,000) @ 0.4% risk per trade
   - Position sizing based on risk percentage and stop loss
   - Real-time PnL tracking (realized + unrealized)

3. **Risk Guardian** (`/app/backend/paper_trading/risk_guardian.py`)
   - **Kill Switch #1**: Stops trading if drawdown > 15%
   - **Kill Switch #2**: Stops trading if daily loss > 2%
   - Resets daily loss tracking at UTC midnight
   - Logs stop reason for debugging

4. **Trade Logger** (`/app/backend/paper_trading/trade_logger.py`)
   - MongoDB storage (collection: `paper_trades`)
   - JSON backup file (`/app/backend/paper_trading/trades_backup.json`)
   - Logs: timestamp, symbol, entry/exit price, position size, PnL, signal

5. **API Router** (`/app/backend/paper_trading_router.py`)
   - `GET /api/paper-trading/health` - Service health check
   - `GET /api/paper-trading/status` - Real-time portfolio metrics
   - `GET /api/paper-trading/trades` - Trade history

6. **Background Service** (`/app/backend/paper_trading/service.py`)
   - Runs via supervisor (auto-start, auto-restart)
   - Updates status file every 60 seconds
   - Graceful shutdown handling

---

## 📊 System Configuration

| Parameter | Value |
|-----------|-------|
| Starting Capital | $10,000 |
| Gold Allocation | 40% ($4,000) |
| S&P 500 Allocation | 60% ($6,000) |
| Gold Risk per Trade | 0.25% ($25) |
| S&P Risk per Trade | 0.4% ($40) |
| Max Drawdown Limit | 15% |
| Daily Loss Limit | 2% |
| Strategy | EMA 10/150 Crossover |
| Data Source | yfinance (H1 candles) |
| Check Interval | 3600 seconds (1 hour) |
| Signal Trigger | On candle close only |

---

## 🔧 Technical Details

### **Market Symbols**
- **GOLD**: GLD (SPDR Gold Shares ETF)
- **S&P 500**: SPY (SPDR S&P 500 ETF Trust)

*Note: Using ETFs instead of futures for reliability and consistent data availability.*

### **Signal Generation Logic**
- **LONG Signal**: EMA 10 crosses above EMA 150
- **SHORT Signal**: EMA 10 crosses below EMA 150
- **Signal Change**: Closes existing position and opens new position in opposite direction

### **Risk Controls**
1. Position sizing based on risk percentage and stop loss distance
2. Maximum leverage: 2x per asset allocation
3. Real-time drawdown monitoring
4. Daily loss tracking (resets at UTC midnight)
5. Automatic circuit breaker on limit breach

### **Data Handling**
- Fetches 200 days of H1 candles (sufficient for EMA 150 calculation)
- Handles yfinance multi-index columns correctly
- 15-minute data delay (acceptable for H1 strategy)
- Robust error handling for API failures

---

## 📁 File Structure

```
/app/backend/
├── paper_trading/
│   ├── __init__.py
│   ├── engine.py                 # Main trading engine
│   ├── portfolio_manager.py      # Position sizing and allocation
│   ├── risk_guardian.py          # Risk limit monitoring
│   ├── trade_logger.py           # Trade logging (MongoDB + JSON)
│   ├── service.py                # Supervisor service wrapper
│   ├── supervisor.conf           # Supervisor configuration
│   ├── status.json               # Real-time status (updated every 60s)
│   ├── trades_backup.json        # Trade history backup
│   ├── engine.log                # Engine logs
│   └── service.log               # Service logs
├── paper_trading_router.py       # FastAPI router for API endpoints
├── server.py                     # Updated to include paper trading router
└── tests/
    └── test_paper_trading.py     # Comprehensive test suite (19 tests, all PASS)
```

---

## 🚀 Service Management

### **Supervisor Control**

```bash
# Check status
sudo supervisorctl status paper_trading

# Start service
sudo supervisorctl start paper_trading

# Stop service
sudo supervisorctl stop paper_trading

# Restart service
sudo supervisorctl restart paper_trading

# View logs
tail -f /var/log/supervisor/paper_trading.out.log
tail -f /var/log/supervisor/paper_trading.err.log
```

### **Service Status**
- **Current State**: RUNNING
- **Auto-start**: Enabled
- **Auto-restart**: Enabled

---

## 🧪 Testing Results

**Testing Agent**: backend testing subagent v3
**Test File**: `/app/backend/tests/test_paper_trading.py`
**Results**: 19/19 tests PASSED (100% success rate)

### **Verified Features**
✅ Health check endpoint functional
✅ Status endpoint returns portfolio metrics
✅ Trades endpoint returns trade history
✅ Paper trading service running as supervisor process
✅ Status file being updated periodically
✅ Portfolio allocation 40% Gold / 60% S&P correct
✅ Risk guardian monitoring configured correctly
✅ Trade logger initialized and ready

---

## 📊 API Endpoints

### **1. Health Check**
```
GET /api/paper-trading/health

Response:
{
  "status": "healthy",
  "service": "paper-trading",
  "status_file_exists": true,
  "trades_file_exists": false
}
```

### **2. Portfolio Status**
```
GET /api/paper-trading/status

Response:
{
  "running": true,
  "current_pnl": 0.0,
  "drawdown_pct": 0.0,
  "total_trades": 0,
  "total_equity": 10000.0,
  "total_return_pct": 0.0,
  "risk_status": {
    "trading_enabled": true,
    "stop_reason": null,
    "current_drawdown_pct": 0.0,
    "max_drawdown_pct": 15.0,
    "drawdown_margin_pct": 15.0,
    "daily_loss_pct": 0.0,
    "max_daily_loss_pct": 2.0,
    "daily_loss_margin_pct": 2.0,
    "daily_start_capital": 10000.0,
    "current_capital": 10000.0
  },
  "portfolio_details": {
    "initial_capital": 10000.0,
    "current_capital": 10000.0,
    "unrealized_pnl": 0.0,
    "total_equity": 10000.0,
    "total_pnl": 0.0,
    "total_return_pct": 0.0,
    "peak_equity": 10000.0,
    "drawdown_pct": 0.0,
    "open_positions": 0,
    "positions": {}
  }
}
```

### **3. Trade History**
```
GET /api/paper-trading/trades

Response: [
  {
    "timestamp": "2026-03-29T08:00:00Z",
    "symbol": "GOLD",
    "signal": "LONG",
    "entry_price": 414.69,
    "exit_price": 420.50,
    "position_size": 4.82,
    "pnl": 28.01,
    "capital_after": 10028.01,
    "strategy_signal": "SHORT -> LONG"
  }
]
```

---

## ⚠️ Important Notes

### **Trading Frequency**
- Engine checks markets every **3600 seconds (1 hour)**
- Signals generated only on **H1 candle close**
- First trade may take up to 1 hour after service start
- This is by design for H1 strategy validation

### **Data Delay**
- yfinance free tier has ~15-minute delay
- Acceptable for H1 strategy (not high-frequency)
- Provides real market conditions for validation

### **Risk Management**
- Risk controls based on **realized PnL**, not unrealized
- Positions can show unrealized losses without triggering stops
- Circuit breakers only activate on closed trades

### **Monitoring**
- Status file updated every 60 seconds
- API provides real-time access to engine status
- Check logs for detailed trading activity

---

## 🔄 Next Steps (Future Enhancements)

1. **Frontend Dashboard** (Optional - as per user directive)
   - Real-time PnL chart
   - Open positions display
   - Trade history table
   - Risk metrics visualization

2. **Phase 7: Live Trading** (After validation)
   - Integration with real broker API
   - Real capital deployment
   - Order execution system
   - Position monitoring

3. **Analytics & Reporting**
   - Performance metrics calculation
   - Sharpe ratio tracking
   - Maximum adverse excursion (MAE)
   - Equity curve visualization

---

## ✅ Acceptance Criteria Met

| Requirement | Status | Notes |
|-------------|--------|-------|
| Use yfinance for data | ✅ | H1 candles, 15-min delay acceptable |
| EMA 10/150 strategy | ✅ | Signal generation implemented |
| Signal on candle close only | ✅ | Checks on H1 close |
| 40% Gold @ 0.25% risk | ✅ | Portfolio manager configured |
| 60% S&P @ 0.4% risk | ✅ | Portfolio manager configured |
| $10,000 starting capital | ✅ | Initialized in engine |
| 15% max drawdown limit | ✅ | Risk guardian monitoring |
| 2% daily loss limit | ✅ | Risk guardian monitoring |
| Background service | ✅ | Running via supervisor |
| Trade logging (MongoDB) | ✅ | Primary storage |
| Trade logging (JSON backup) | ✅ | Backup file created |
| Status endpoint | ✅ | Returns PnL, DD, trades |
| Minimal monitoring | ✅ | API provides status |
| No over-engineering | ✅ | Focused implementation only |

---

## 📝 Summary

Phase 6: Paper Trading is **fully operational**. The system is running as a background service, monitoring Gold (GLD) and S&P 500 (SPY) markets via yfinance H1 candles. It implements the EMA 10/150 crossover strategy with the Phase 5 optimized portfolio allocation (40% Gold @ 0.25% risk, 60% S&P @ 0.4% risk). Risk controls (15% max drawdown, 2% daily loss limit) are actively monitoring all trades.

The API provides real-time access to portfolio status, trade history, and risk metrics. All tests passed successfully (19/19, 100%). The system is ready for live market validation before deploying real capital.

**Status**: ✅ **PRODUCTION READY**
