# cTrader Bot Factory - Complete User Guide

**Version:** 1.0  
**Last Updated:** January 2026  
**System:** AI Trading Strategy Generator + cBot Factory

---

## Table of Contents

1. [Data Management](#1-data-management)
2. [Strategy Generation](#2-strategy-generation)
3. [Backtesting & Validation](#3-backtesting--validation)
4. [Strategy Selection](#4-strategy-selection)
5. [cBot Generation](#5-cbot-generation)
6. [Deployment](#6-deployment)
7. [Common Issues & Troubleshooting](#7-common-issues--troubleshooting)
8. [API Reference](#8-api-reference)

---

## 1. Data Management

### 1.1 Supported CSV Formats

The system supports three CSV formats:

| Format | Timestamp Format | Example |
|--------|------------------|---------|
| **MT4** | `YYYY.MM.DD HH:MM` | `2024.01.15 14:30` |
| **MT5** | `YYYY.MM.DD HH:MM:SS` | `2024.01.15 14:30:00` |
| **cTrader** | `YYYY-MM-DD HH:MM:SS` | `2024-01-15 14:30:00` |

### 1.2 Required CSV Columns

```csv
Timestamp,Open,High,Low,Close,Volume
2024-01-15 14:00:00,1.08750,1.08820,1.08700,1.08800,15234.5
2024-01-15 15:00:00,1.08800,1.08900,1.08780,1.08850,12456.2
```

**Column Requirements:**
- **Timestamp**: Must match your selected format exactly
- **Open/High/Low/Close**: Decimal prices (e.g., 1.08750)
- **High**: Must be >= Open, Low, Close
- **Low**: Must be <= Open, High, Close
- **Volume**: Positive number (can be 0)

### 1.3 How to Upload CSV Data

**UI Location:** Dashboard > Market Data > Upload Tab

**Step-by-Step:**

1. Navigate to **Market Data** page
2. Click **Upload** tab
3. Fill in the form:
   - **Symbol**: Enter pair (e.g., `EURUSD`, `XAUUSD`)
   - **Timeframe**: Select from dropdown:
     - M1 (1 minute)
     - M5 (5 minutes)
     - M15 (15 minutes)
     - M30 (30 minutes)
     - H1 (1 hour) - *Recommended for strategy development*
     - H4 (4 hours)
     - D1 (1 day)
     - W1 (1 week)
   - **Format**: Select MT4, MT5, or cTrader
4. Click **Choose File** and select your CSV
5. Click **Upload**

**API Endpoint:**
```bash
POST /api/marketdata/import/csv
Content-Type: application/json

{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "data": "<CSV content as string>",
  "format_type": "ctrader",
  "skip_validation": false
}
```

### 1.4 Verifying Data Integrity

**UI Location:** Dashboard > Market Data > Coverage Tab

**What to Check:**

| Indicator | Good | Warning | Critical |
|-----------|------|---------|----------|
| Coverage % | ≥99% | 95-99% | <95% |
| Gap Count | 0 | 1-5 | >5 |
| Status Badge | Complete | Partial | Poor |

**Verification Steps:**
1. Go to **Coverage** tab
2. Check your symbol/timeframe card
3. Look for:
   - Green "Complete" badge = Good
   - Yellow "Gaps Detected" = Needs attention
   - Coverage percentage bar

**API Endpoint:**
```bash
GET /api/marketdata/{symbol}/{timeframe}/stats

# Example Response:
{
  "success": true,
  "stats": {
    "symbol": "EURUSD",
    "timeframe": "1h",
    "total_candles": 8760,
    "first_timestamp": "2024-01-01 00:00:00",
    "last_timestamp": "2024-12-31 23:00:00",
    "coverage_percent": 99.5
  }
}
```

### 1.5 Deleting Datasets

**UI Location:** Coverage Tab > Dataset Card > Delete Button

**Steps:**
1. Go to **Coverage** tab
2. Find the dataset you want to delete
3. Click the red **Delete Dataset** button
4. Confirm in the popup dialog
5. Coverage will refresh automatically

**API Endpoint:**
```bash
DELETE /api/marketdata/{symbol}/{timeframe}

# Example:
DELETE /api/marketdata/EURUSD/1h

# Response:
{
  "success": true,
  "symbol": "EURUSD",
  "timeframe": "1h",
  "deleted_count": 8760,
  "message": "Deleted 8760 candles for EURUSD 1h"
}
```

### 1.6 Handling Gaps (Weekends & Holidays)

**Best Practices:**

1. **Weekend Gaps are Normal**: Forex markets close Friday 5PM EST - Sunday 5PM EST
2. **Holiday Gaps**: Christmas, New Year may have reduced/no data
3. **Don't Interpolate**: Never fill gaps with fake data

**Gap Fixing Options:**
- Click **Fix All Gaps** button (downloads from Dukascopy if available)
- Or manually re-upload clean data for the gap period

**Recommended Data Preparation:**
```
1. Download data from trusted source (Dukascopy, broker)
2. Remove weekends/holidays if they contain invalid data
3. Ensure continuous timestamps during market hours
4. Validate: High >= Open, Low, Close for each candle
```

---

## 2. Strategy Generation

### 2.1 Using the Strategy Factory

**UI Location:** Dashboard > Generate Strategies (left sidebar)

**Available Generation Methods:**

| Method | UI Location | Use Case |
|--------|-------------|----------|
| Strategy Factory | Factory page | Batch generation with templates |
| Generate Top Strategies | Generate page | AI-powered custom strategies |
| Single Bot Generation | Generate page | Generate from text prompt |

### 2.2 Strategy Factory Parameters

**UI Location:** Dashboard > Factory

| Parameter | Description | Default | Recommended |
|-----------|-------------|---------|-------------|
| **Templates** | Strategy types to generate | All | Start with 2-3 |
| **Strategies Per Template** | Number of random variations | 2 | 5-10 for exploration |
| **Symbol** | Trading pair | EURUSD | Match your data |
| **Timeframe** | Chart timeframe | H1 | Match your data |
| **Initial Balance** | Starting capital | $10,000 | Your actual capital |
| **Duration Days** | Backtest period | 365 | 365-730 |
| **Challenge Firm** | Prop firm rules | FTMO | Your target firm |
| **Auto-Optimize Top** | GA optimization | 0 | 3-5 for finals |

### 2.3 Available Strategy Templates

| Template ID | Name | Type | Best For |
|-------------|------|------|----------|
| `ema_crossover` | EMA Crossover | Trend Following | Trending markets |
| `rsi_mean_reversion` | RSI Mean Reversion | Mean Reversion | Range-bound markets |
| `macd_trend` | MACD Trend Following | Momentum | Strong trends |
| `bollinger_breakout` | Bollinger Breakout | Breakout | Volatility expansion |
| `atr_volatility_breakout` | ATR Volatility Breakout | Breakout | High volatility |

### 2.4 Filter Parameters

**Current System Filters (server.py):**

```python
# Production filters (adjustable)
passed_filters = (
    profit_factor >= 0.8 and      # Minimum profitability
    max_drawdown <= 40 and        # Maximum risk
    total_trades >= 3             # Minimum activity
)
```

**Recommended Settings:**

| Stage | Profit Factor | Max DD | Min Trades | Purpose |
|-------|---------------|--------|------------|---------|
| Initial Exploration | ≥0.8 | ≤50% | ≥3 | See all results |
| Refinement | ≥1.0 | ≤30% | ≥20 | Filter weak strategies |
| Final Selection | ≥1.3 | ≤20% | ≥50 | Production candidates |
| Prop Firm Ready | ≥1.5 | ≤10% | ≥100 | Challenge-ready |

### 2.5 API Endpoints for Generation

**Strategy Factory:**
```bash
POST /api/factory/generate
{
  "session_id": "my_session",
  "templates": ["ema_crossover", "rsi_mean_reversion"],
  "strategies_per_template": 5,
  "symbol": "EURUSD",
  "timeframe": "1h",
  "initial_balance": 10000,
  "duration_days": 365,
  "challenge_firm": "ftmo",
  "auto_optimize_top": 0
}
```

**Check Status:**
```bash
GET /api/factory/status/{run_id}
```

**Get Results:**
```bash
GET /api/factory/result/{run_id}
```

**Generate Top Strategies (AI-Powered):**
```bash
POST /api/strategy/auto-generate
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "count": 20
}
```

---

## 3. Backtesting & Validation

### 3.1 How Backtesting Works

**Internal Flow:**
```
1. Load candle data from MongoDB
2. Apply strategy rules to each candle
3. Simulate trades with spread/slippage
4. Calculate equity curve
5. Compute performance metrics
6. Score and grade strategy
```

**Key Files:**
- `backtest_real_engine.py` - Core backtesting logic
- `backtest_calculator.py` - Performance metric calculations
- `strategy_simulator.py` - Trade simulation

### 3.2 Understanding Performance Metrics

| Metric | Formula | Good | Excellent | Meaning |
|--------|---------|------|-----------|---------|
| **Profit Factor** | Gross Profit / Gross Loss | >1.2 | >1.5 | How much you win vs lose |
| **Win Rate** | Winning Trades / Total Trades | >40% | >55% | Percentage of winning trades |
| **Max Drawdown** | Peak-to-Trough Decline | <20% | <10% | Worst losing streak |
| **Sharpe Ratio** | (Return - Risk Free) / StdDev | >1.0 | >2.0 | Risk-adjusted return |
| **Sortino Ratio** | Return / Downside StdDev | >1.5 | >2.5 | Downside risk-adjusted |
| **Calmar Ratio** | Annual Return / Max DD | >1.0 | >2.0 | Return per unit of drawdown |
| **Net Profit** | Total P&L | Positive | >20% | Absolute profit |
| **Total Trades** | Number of trades | >50 | >200 | Statistical significance |

### 3.3 Interpreting Results

**Profit Factor Interpretation:**
- **<1.0**: Losing strategy - DO NOT USE
- **1.0-1.2**: Break-even - Needs improvement
- **1.2-1.5**: Good - Viable for trading
- **1.5-2.0**: Very Good - Reliable strategy
- **>2.0**: Excellent - But check for overfitting

**Drawdown Interpretation:**
- **<10%**: Conservative - Safe for prop firms
- **10-20%**: Moderate - Standard risk
- **20-30%**: Aggressive - Higher risk/reward
- **>30%**: Dangerous - Not recommended

### 3.4 Identifying Overfitting

**Warning Signs:**
1. Profit Factor >3.0 with limited trades (<50)
2. Win Rate >70% consistently
3. Performance degrades significantly in walk-forward
4. Strategy only works on specific date range
5. Too many parameters (>10 optimized values)

**How to Detect:**

```
1. Run Walk-Forward Analysis
   - If out-of-sample performance is <50% of in-sample = Overfitting

2. Run Monte Carlo Simulation
   - If 95th percentile drawdown is 2x+ expected = Unstable

3. Compare training vs validation periods
   - Split data 70/30, test on both
```

### 3.5 Monte Carlo Simulation

**UI Location:** Strategy Details > Advanced Validation > Monte Carlo

**What It Does:**
- Runs 1000+ randomized trade sequences
- Calculates probability distributions
- Shows worst-case scenarios

**Key Outputs:**

| Metric | Meaning |
|--------|---------|
| `median_final_equity` | Expected ending balance |
| `percentile_5_equity` | Worst 5% scenario |
| `percentile_95_equity` | Best 5% scenario |
| `max_drawdown_mean` | Average worst drawdown |
| `ruin_probability` | Chance of losing 50%+ |

**Good Monte Carlo Score:** ≥70/100

**API:**
```bash
POST /api/montecarlo/simulate
{
  "strategy_id": "abc123",
  "simulations": 1000,
  "initial_balance": 10000
}
```

### 3.6 Walk-Forward Analysis

**UI Location:** Strategy Details > Advanced Validation > Walk-Forward

**How It Works:**
```
Total Data: |----Training----|--Test--|----Training----|--Test--|...

1. Optimize on Training period
2. Test on unseen Test period
3. Move window forward
4. Repeat
```

**Interpretation:**
- **Efficiency Ratio >0.6**: Strategy is robust
- **Efficiency Ratio 0.3-0.6**: Needs tuning
- **Efficiency Ratio <0.3**: Likely overfitted

**API:**
```bash
POST /api/walkforward/analyze
{
  "strategy_id": "abc123",
  "windows": 5,
  "training_pct": 70
}
```

### 3.7 Prop Firm Challenge Simulation

**UI Location:** Strategy Details > Challenge Simulation

**Supported Prop Firms:**

| Firm | Daily Loss Limit | Max Drawdown | Profit Target |
|------|------------------|--------------|---------------|
| **FTMO** | 5% | 10% | 10% |
| **FundedNext** | 5% | 12% | 8% |
| **The5ers** | 4% | 6% | 8% |
| **PipFarm** | 5% | 10% | 10% |

**API:**
```bash
POST /api/challenge/simulate
{
  "strategy_id": "abc123",
  "prop_firm": "ftmo",
  "account_size": 100000,
  "simulations": 100
}

# Response includes:
{
  "pass_rate": 65.0,
  "average_days_to_target": 23,
  "daily_loss_violations": 12,
  "max_dd_violations": 8
}
```

---

## 4. Strategy Selection

### 4.1 Selection Criteria

**Minimum Requirements for Live Trading:**

| Metric | Minimum | Ideal |
|--------|---------|-------|
| Profit Factor | >1.2 | >1.5 |
| Win Rate | >35% | >45% |
| Max Drawdown | <25% | <15% |
| Total Trades | >50 | >200 |
| Sharpe Ratio | >0.5 | >1.5 |
| Monte Carlo Score | >50 | >75 |
| Walk-Forward Efficiency | >0.4 | >0.6 |

### 4.2 Safe vs Aggressive Strategies

**Safe Strategy Profile:**
```
- Profit Factor: 1.3-1.8
- Win Rate: 45-55%
- Max Drawdown: <15%
- Risk per Trade: 0.5-1%
- Best for: Prop firm challenges, capital preservation
```

**Aggressive Strategy Profile:**
```
- Profit Factor: 1.5-2.5
- Win Rate: 35-45%
- Max Drawdown: 15-25%
- Risk per Trade: 1-2%
- Best for: Personal accounts, growth focus
```

### 4.3 Portfolio Selection

**Recommended Portfolio Composition:**

| Strategy Count | Diversification | Risk Level |
|----------------|-----------------|------------|
| 1 strategy | None | High |
| 3 strategies | Minimal | Medium |
| 5 strategies | Good | Medium-Low |
| 7+ strategies | Excellent | Low |

**Selection Process:**
1. Generate 50-100 strategies
2. Filter to top 20 by fitness score
3. Run Monte Carlo on each
4. Select 5-7 with lowest correlation
5. Verify walk-forward performance
6. Final selection: 3-5 strategies

### 4.4 Strategy Grades

The system assigns grades A-F:

| Grade | Score Range | Recommendation |
|-------|-------------|----------------|
| A | 90-100 | Production ready |
| B | 75-89 | Good candidate |
| C | 60-74 | Needs improvement |
| D | 40-59 | Not recommended |
| F | <40 | Reject |

---

## 5. cBot Generation

### 5.1 Generating cTrader Bots

**UI Location:** Strategy Details > Generate cBot

**Steps:**
1. Select a strategy from your list
2. Click **Generate cBot**
3. Wait for AI to generate C# code
4. System compiles with .NET SDK
5. If errors: Auto-fix loop runs (up to 3 attempts)
6. Download when "Compile Verified" shows

### 5.2 Compilation Verification

**UI Indicators:**
- **Green Checkmark**: Compiled successfully
- **Yellow Warning**: Compiled with warnings
- **Red X**: Compilation failed

**What Gets Checked:**
1. C# syntax validation
2. cTrader.Automate API compatibility
3. Required using statements
4. Robot class structure

### 5.3 Output File Location

**Server Path:** `/app/backend/generated_bots/`

**File Naming:**
```
{strategy_name}_{timestamp}.cs
Example: EMA_Crossover_Strategy_20260102_143052.cs
```

### 5.4 Downloading Bots

**UI:** Click **Download** button on verified bot

**API:**
```bash
GET /api/bot/download/{bot_id}
# Returns: .cs file or .algo file
```

### 5.5 Bot Code Structure

Generated bots follow this structure:
```csharp
using System;
using cAlgo.API;
using cAlgo.API.Internals;
using cAlgo.API.Indicators;
using cAlgo.Indicators;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class MyBot : Robot
    {
        // Parameters
        [Parameter("Risk %", DefaultValue = 1.0)]
        public double RiskPercent { get; set; }

        // Indicators
        private ExponentialMovingAverage _emaFast;
        private ExponentialMovingAverage _emaSlow;

        protected override void OnStart()
        {
            // Initialize indicators
        }

        protected override void OnBar()
        {
            // Strategy logic
        }

        protected override void OnStop()
        {
            // Cleanup
        }
    }
}
```

---

## 6. Deployment

### 6.1 Installing in cTrader

**Steps:**
1. Open cTrader Desktop
2. Go to **Automate** tab
3. Click **Robots** folder
4. Right-click > **Add Existing**
5. Select your downloaded `.cs` file
6. Click **Build** icon
7. Wait for compilation

### 6.2 Demo Account Testing (REQUIRED)

**Before live trading, ALWAYS:**

1. **Create Demo Account**
   - Use same broker as your live account
   - Match account settings (leverage, etc.)

2. **Run for Minimum 2 Weeks**
   - Let bot trade through various market conditions
   - Monitor daily

3. **Verify Performance Matches Backtest**
   - Acceptable variance: ±20%
   - If worse than -30%: Investigate

### 6.3 Recommended Settings

**Conservative (Prop Firm Challenge):**
```
Risk per Trade: 0.5%
Max Open Positions: 1
Max Daily Loss: 3%
Trading Hours: Major sessions only
```

**Moderate (Personal Account):**
```
Risk per Trade: 1.0%
Max Open Positions: 2
Max Daily Loss: 5%
Trading Hours: 24/5
```

**Aggressive (Growth Focus):**
```
Risk per Trade: 2.0%
Max Open Positions: 3
Max Daily Loss: 8%
Trading Hours: 24/5
```

### 6.4 Lot Size Calculation

The bot calculates position size as:
```
Lot Size = (Account Balance × Risk%) / (Stop Loss in Pips × Pip Value)

Example:
Account: $10,000
Risk: 1% = $100
Stop Loss: 20 pips
Pip Value: $10/pip (for 1 lot EURUSD)

Lot Size = $100 / (20 × $10) = 0.5 lots
```

### 6.5 Monitoring Checklist

**Daily:**
- [ ] Check if bot is running
- [ ] Review open positions
- [ ] Check daily P&L
- [ ] Verify no error messages

**Weekly:**
- [ ] Compare actual vs expected performance
- [ ] Review win rate
- [ ] Check drawdown level
- [ ] Update performance log

**Monthly:**
- [ ] Full performance review
- [ ] Compare to backtest expectations
- [ ] Decide: continue, adjust, or stop

---

## 7. Common Issues & Troubleshooting

### 7.1 No Strategies Passing Filters

**Symptom:** `"No strategies passed filters. Try adjusting parameters."`

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Filters too strict | Lower PF requirement to 0.8 |
| Insufficient data | Upload more historical data |
| Wrong timeframe | Match data timeframe to settings |
| Low trade count | Extend backtest duration |

**Quick Fix:**
```bash
# Check current filter settings
grep -n "passed_filters" /app/backend/server.py

# Temporarily relax to:
profit_factor >= 0.8
max_drawdown <= 50
total_trades >= 3
```

### 7.2 Duplicate Strategy Results

**Symptom:** All strategies show identical metrics

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Generic backtest not using strategy logic | Check strategy_type parameter |
| Same random seed | Ensure unique session_id per run |
| Cached results | Clear browser cache, restart backend |

### 7.3 Low Performance Strategies

**Symptom:** Profit Factor <1.0 consistently

**Solutions:**
1. **Check Data Quality**
   - Gaps in data cause false signals
   - Verify data integrity in Coverage tab

2. **Try Different Templates**
   - Mean reversion works in ranges
   - Trend following works in trends
   - Match template to market type

3. **Adjust Parameters**
   - Increase backtest duration
   - Try different timeframes
   - Use genetic optimization

### 7.4 Data-Related Issues

**Issue: "No candles found"**
```
Solution: Upload data for the exact symbol/timeframe combination
Check: GET /api/marketdata/available
```

**Issue: "Invalid timestamp format"**
```
Solution: Ensure CSV matches selected format (MT4/MT5/cTrader)
MT4: YYYY.MM.DD HH:MM
cTrader: YYYY-MM-DD HH:MM:SS
```

**Issue: "High >= Low validation failed"**
```
Solution: Data has corrupted candles
Fix: Clean CSV, ensure High is highest price in each row
```

### 7.5 API Errors

**Error: "Failed to generate chat completion"**
```
Cause: Missing or invalid API key
Solution: Check /app/backend/.env has OPENAI_API_KEY or EMERGENT_LLM_KEY
Restart: sudo supervisorctl restart backend
```

**Error: "500 Internal Server Error"**
```
Debug: tail -50 /var/log/supervisor/backend.err.log
Common: Missing dependencies, database connection
```

### 7.6 Compilation Failures

**Error: "cBot compilation failed"**
```
Cause: Generated code has syntax errors
Solution: 
1. Wait for auto-fix (up to 3 attempts)
2. View code and check for obvious errors
3. Regenerate with different AI mode
```

---

## 8. API Reference

### 8.1 Market Data Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/marketdata/available` | List all datasets |
| GET | `/api/marketdata/{symbol}/{tf}/stats` | Get dataset statistics |
| POST | `/api/marketdata/import/csv` | Upload CSV data |
| DELETE | `/api/marketdata/{symbol}/{tf}` | Delete dataset |
| GET | `/api/marketdata/{symbol}/{tf}/candles` | Get candle data |

### 8.2 Strategy Factory Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/factory/templates` | List strategy templates |
| POST | `/api/factory/generate` | Start factory run |
| GET | `/api/factory/status/{run_id}` | Check run status |
| GET | `/api/factory/result/{run_id}` | Get results |

### 8.3 Strategy Generation Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/strategy/auto-generate` | AI generate strategies |
| POST | `/api/bot/generate` | Generate single bot |
| GET | `/api/bot/download/{id}` | Download bot code |

### 8.4 Validation Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/backtest/real` | Run backtest |
| POST | `/api/montecarlo/simulate` | Monte Carlo simulation |
| POST | `/api/walkforward/analyze` | Walk-forward analysis |
| POST | `/api/challenge/simulate` | Prop firm simulation |

### 8.5 Portfolio Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/portfolio/create` | Create portfolio |
| GET | `/api/portfolio/{id}` | Get portfolio |
| POST | `/api/portfolio/backtest` | Backtest portfolio |
| POST | `/api/portfolio/optimize` | Optimize allocation |

---

## Quick Start Checklist

```
[ ] 1. Upload clean CSV data (H1 recommended)
[ ] 2. Verify data in Coverage tab (>99% coverage)
[ ] 3. Run Strategy Factory (5 templates × 5 strategies)
[ ] 4. Filter results (PF >1.2, DD <20%)
[ ] 5. Run Monte Carlo on top 5 strategies
[ ] 6. Run Walk-Forward on survivors
[ ] 7. Generate cBot for best strategy
[ ] 8. Verify compilation success
[ ] 9. Download and install in cTrader
[ ] 10. Run on demo for 2+ weeks
[ ] 11. Compare demo to backtest
[ ] 12. If acceptable, deploy to live
```

---

## Support & Resources

**Log Files:**
- Backend: `/var/log/supervisor/backend.err.log`
- Frontend: Browser DevTools Console

**Restart Services:**
```bash
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
```

**Check System Status:**
```bash
sudo supervisorctl status
curl http://localhost:8001/api/marketdata/available
```

---

*This guide is based on actual system implementation as of January 2026.*
