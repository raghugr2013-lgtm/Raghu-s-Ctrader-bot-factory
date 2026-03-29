# 📘 COMPLETE USER GUIDE - Bot Factory Trading Platform

## Welcome to Your Automated Trading System

This guide will help you understand and operate your complete trading platform with confidence.

---

## 🎯 WHAT IS THIS SYSTEM?

Your platform is an **AI-powered trading bot factory** that:
1. **Generates** cTrader trading bots using AI (GPT-5.2, Claude 4.5, DeepSeek)
2. **Validates** bots for quality and prop firm compliance
3. **Monitors** live paper trading with real market data
4. **Protects** your capital with automatic risk management

**Think of it as**: A smart assistant that creates, tests, and monitors trading strategies for you.

---

## 🏗️ SYSTEM COMPONENTS

### 1. **Bot Factory** (Strategy Generation)
- **What it does**: Creates custom cTrader trading bots using AI
- **Access**: Main page at https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com
- **Purpose**: Build new trading strategies

### 2. **Paper Trading Engine** (Live Execution)
- **What it does**: Trades automatically with $10,000 virtual money using real market data
- **Strategy**: EMA 10/150 crossover (buys when fast EMA crosses above slow EMA)
- **Markets**: GOLD (GLD) and S&P 500 (SPY)
- **Purpose**: Test strategies without risking real money

### 3. **Live Monitoring Dashboard** (Performance Tracking)
- **What it does**: Shows real-time trading performance and statistics
- **Access**: Click "LIVE TRADING" button or go to `/live`
- **Purpose**: Monitor your trading performance daily

---

## 🚀 DAILY USAGE FLOW

### Morning Routine (5 minutes)

#### Step 1: Open Live Dashboard
```
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/live
```

#### Step 2: Check System Status (Top Right)
- **Green "ONLINE"** = ✅ System working
- **Red "OFFLINE"** = ❌ System stopped (contact support)

#### Step 3: Review Paper Trading Panel
Look at these numbers:

**Equity**: Your current account balance
- Started with: $10,000
- Current: Should be close to $10,000 (small gains/losses are normal)

**Total P&L** (Profit & Loss): How much you've made or lost
- Green = Profit
- Red = Loss
- **Normal daily range**: -$100 to +$100

**Drawdown**: Largest drop from peak
- **Safe**: 0-5%
- **Warning**: 5-10%
- **Danger**: 10-15%
- **Auto-stop**: 15%+ (system stops automatically)

**Total Trades**: Number of completed trades
- **Normal**: 0-5 trades per day
- **High activity**: 5-10 trades per day

**Risk Status**: Trading enabled or disabled
- **ENABLED** (green) = Trading allowed
- **DISABLED** (red) = Trading stopped due to risk limits

#### Step 4: Check Open Positions
- Shows current active trades
- **Normal**: 0-2 positions
- **Symbol**: GOLD or SPY
- **Signal**: LONG (buy) or SHORT (sell)

#### Step 5: Review Recent Trades
- Last 10 completed trades
- Look for patterns: Are most trades profitable?

### **Daily Monitoring Frequency**
- **Morning**: Check once (10-15 minutes after market open)
- **Midday**: Optional quick check
- **Evening**: Check once before market close
- **Total time**: 10-15 minutes per day

---

## 🤖 STRATEGY WORKFLOW

### How the Bot Factory Works

#### Option 1: AI-Generated Bots (Recommended for beginners)

**Step 1: Access Bot Builder**
- Click "BACKTEST" button on main page
- You'll see "Builder Pro" panel

**Step 2: Choose AI Model**
- **GPT-5.2**: Balanced, good all-around
- **Claude 4.5**: Creative, explores unique strategies
- **DeepSeek**: Fast, efficient coding

**Step 3: Configure Strategy**
- **Strategy Type**: Start with "Trend Following" (easiest)
- **Timeframe**: "1 Hour" or "4 Hours" (less noisy)
- **Asset**: "EURUSD" or "GOLD" (most liquid)

**Step 4: Set Prop Firm Compliance** (If trading for prop firm)
- Choose: FTMO, FundedNext, PipFarm, or The5ers
- System ensures your bot follows their rules

**Step 5: Generate Bot**
- Click "Generate Bot"
- Wait 30-60 seconds
- AI creates custom cBot code

**Step 6: Review Validation**
Three quality gates:
1. **Compilation**: Does code work? (Must pass)
2. **Risk Check**: Are risk controls safe? (Must pass)
3. **Compliance**: Does it follow prop firm rules? (Optional)

**Step 7: Download Code**
- Click "Download Code"
- Save .cs file
- Upload to cTrader platform

#### Option 2: Analyze Existing Bot

**Step 1: Navigate to Analyze**
- Click "ANALYZE" in top navigation

**Step 2: Paste Code**
- Copy your existing cBot code
- Paste into editor

**Step 3: Run Analysis**
- System checks for errors
- Suggests improvements
- Validates risk controls

---

## 📊 LIVE MONITORING GUIDE

### Understanding the Dashboard

#### **Paper Trading Engine Panel** (Top Section)

**1. Equity: $10,000.00**
- **What it means**: Your current account value
- **Starting value**: $10,000
- **Good**: $9,800 - $10,500
- **Concerning**: Below $9,500
- **Critical**: Below $9,000

**2. Total P&L: +$0.00 (+0.00%)**
- **What it means**: Total profit or loss
- **Calculation**: Current Equity - Starting Balance
- **Example**: $10,150 equity = +$150 (+1.5%)

**3. Drawdown: 0.00%**
- **What it means**: Biggest drop from highest point
- **Formula**: (Peak - Current) / Peak × 100
- **Example**: 
  - Peak was $10,200
  - Now at $10,000
  - Drawdown = 1.96%

**Drawdown Levels**:
- **0-2%**: ✅ Excellent (no action needed)
- **2-5%**: 🟡 Good (normal market volatility)
- **5-10%**: 🟠 Warning (monitor closely)
- **10-15%**: 🔴 Danger (check strategy)
- **15%+**: 🛑 Auto-stop (system halts trading)

**4. Total Trades: 0**
- **What it means**: Number of completed trades
- **Daily average**: 1-3 trades
- **Weekly average**: 5-10 trades

**5. Risk Status: ENABLED**
- **ENABLED**: System can take new trades
- **DISABLED**: System stopped trading (reason shown)

#### **Open Positions** (Middle Section)

Shows currently active trades:

**GOLD - SHORT**
- Entry: $414.69
- Current: $414.69
- Size: 3.01 shares

**What to watch**:
- **Current vs Entry**: Is trade profitable?
- **Size**: Should be reasonable (2-5 shares typical)
- **Duration**: How long has position been open?

#### **Recent Trades** (Table)

Shows last 10 completed trades:

| Time | Symbol | Signal | Entry | Exit | P&L |
|------|--------|--------|-------|------|-----|
| 08:18 AM | GOLD | SHORT | $454.69 | $420.50 | -$9.61 |

**How to read**:
- **Signal**: LONG (bought) or SHORT (sold)
- **Entry/Exit**: Prices when trade opened/closed
- **P&L**: Profit (green) or Loss (red)

**Good pattern**: Mix of wins and losses, more green than red
**Bad pattern**: Consecutive large losses

#### **Aggregate Statistics** (Bottom Section)

**Running: 1**
- Number of active trading systems
- Includes paper trading engine

**Balance: $10k**
- Total equity across all systems
- Should match Paper Trading equity

**Daily P&L: +$0**
- Combined daily profit/loss

**Avg DD: 0.0%**
- Average drawdown across systems

**Max DD: 0.0%**
- Highest drawdown today

---

## 🛡️ RISK MANAGEMENT

### Automatic Safety Features

#### **1. Maximum Drawdown Limit: 15%**

**What happens**:
- System monitors drawdown constantly
- If drawdown reaches 15%, trading stops automatically
- You'll see "DISABLED" status with reason: "Max drawdown reached"

**Example**:
- Starting balance: $10,000
- Peak reached: $10,300
- Drawdown limit: $10,300 × 15% = $1,545
- Stop trading at: $10,300 - $1,545 = $8,755

**Recovery**:
- System requires manual restart after stop
- Contact support to review and restart

#### **2. Daily Loss Limit: 2%**

**What happens**:
- Maximum loss allowed per day: $200 (2% of $10,000)
- If exceeded, no new trades until next day
- Existing positions may be closed

**Purpose**: Prevents one bad day from wiping out weeks of gains

#### **3. Position Sizing**

**Rules**:
- Maximum position size: ~3% of equity per trade
- Example: $10,000 × 3% = $300 per position
- Prevents over-concentration in single trade

#### **4. Per-Trade Stop Loss**

**Strategy uses**:
- Stop loss based on ATR (Average True Range)
- Adapts to market volatility
- Typical stop: 1-2% of position value

### When System Stops Trading

**Reasons system may stop**:
1. **Drawdown exceeded 15%**
2. **Daily loss limit hit (2%)**
3. **Technical error** (API failure, data loss)
4. **Risk guardian disabled**

**What to do**:
1. Check Live Dashboard for stop reason
2. Review recent trades for patterns
3. Don't restart immediately - analyze first
4. Contact support if unclear

---

## 🔧 TROUBLESHOOTING

### Common Issues & Solutions

#### **Issue 1: Dashboard Shows "OFFLINE"**

**Symptoms**:
- Red "OFFLINE" badge in header
- Paper Trading shows "STOPPED"

**Possible Causes**:
1. System manually stopped
2. Risk limit triggered
3. Backend service down

**How to Fix**:
1. Check Paper Trading status badge
2. Look for stop reason message
3. Check backend service:
   ```bash
   supervisorctl status backend
   ```
4. If stopped, restart:
   ```bash
   supervisorctl restart backend
   ```

#### **Issue 2: Balance Shows $0 or Incorrect Value**

**Symptoms**:
- Equity shows $0.00
- Aggregate balance shows $0k

**Possible Causes**:
1. API not loading
2. Frontend not connected to backend

**How to Fix**:
1. Hard refresh browser (Ctrl+Shift+R)
2. Check API endpoint:
   ```
   https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/api/paper-trading/status
   ```
3. Should return JSON with `total_equity: 10000`

#### **Issue 3: No Trades Executing**

**Symptoms**:
- System shows RUNNING
- But no trades for 24+ hours

**Possible Causes**:
1. Market conditions don't meet strategy criteria
2. Risk status disabled
3. Market data not updating

**How to Fix**:
1. Check "Risk Status" - should be ENABLED
2. Verify markets are open (trading hours)
3. Check backend logs:
   ```bash
   tail -f /var/log/supervisor/backend.err.log
   ```

#### **Issue 4: Dashboard Not Loading**

**Symptoms**:
- Blank page
- Loading forever
- Error messages

**Possible Causes**:
1. Frontend service down
2. Browser cache issue
3. Network problem

**How to Fix**:
1. Check frontend service:
   ```bash
   supervisorctl status frontend
   ```
2. Clear browser cache
3. Try incognito/private window
4. Check browser console for errors (F12)

#### **Issue 5: Drawdown Shows -Infinity%**

**Symptoms**:
- Weird values like -Infinity or NaN

**Cause**: Frontend calculation error

**How to Fix**:
1. This should be fixed in current version
2. If still occurring, hard refresh browser
3. Check frontend logs for JavaScript errors

---

## ⚠️ CURRENT LIMITATIONS

### What's NOT Implemented Yet

#### **1. Live Trading (Real Money)**
- **Status**: Not implemented
- **Current**: Paper trading only ($10,000 virtual)
- **Impact**: You cannot trade real money yet
- **Workaround**: Use paper trading to validate strategies first

#### **2. Multiple Strategies**
- **Status**: Single strategy only (EMA 10/150 crossover)
- **Current**: Cannot switch or add strategies
- **Impact**: Limited to one approach
- **Workaround**: Generate and test multiple bots offline in cTrader

#### **3. Historical Backtesting**
- **Status**: No built-in backtesting
- **Current**: Bot Factory generates code, but doesn't backtest automatically
- **Impact**: Must manually backtest in cTrader
- **Workaround**: Use cTrader's backtesting feature

#### **4. Strategy Performance Analytics**
- **Status**: Basic metrics only
- **Current**: No Sharpe ratio, win rate, profit factor
- **Impact**: Limited performance analysis
- **Workaround**: Export trades to Excel for analysis

#### **5. Multi-Asset Support**
- **Status**: Limited to 2 assets (GOLD, SPY)
- **Current**: Cannot add more symbols
- **Impact**: No diversification
- **Workaround**: Generate separate bots for different assets

#### **6. User Authentication**
- **Status**: No login system
- **Current**: Anyone with URL can access
- **Impact**: No user accounts or saved settings
- **Workaround**: Keep URL private

#### **7. Notifications/Alerts**
- **Status**: No push notifications
- **Current**: Must manually check dashboard
- **Impact**: Won't know about issues immediately
- **Workaround**: Check dashboard 2-3 times daily

#### **8. Trade Export**
- **Status**: No CSV/Excel export
- **Current**: Trades visible only in dashboard
- **Impact**: Cannot analyze in external tools
- **Workaround**: Manually copy data if needed

#### **9. Position Management Controls**
- **Status**: No manual close/edit positions
- **Current**: System manages all trades automatically
- **Impact**: Cannot intervene in trades
- **Workaround**: Stop system if major concern

#### **10. Strategy Optimization**
- **Status**: No parameter optimization
- **Current**: Fixed EMA periods (10/150)
- **Impact**: Cannot tune for better performance
- **Workaround**: Generate new bots with different parameters

---

## 🎯 WHAT TO EXPECT (Normal Behavior)

### Daily Activity

**Trading Frequency**:
- **Low activity days**: 0-1 trades (normal during ranging markets)
- **Normal days**: 1-3 trades
- **High activity days**: 3-5 trades
- **Unusual**: 5+ trades (check for errors)

**P&L Volatility**:
- **Daily swings**: -$50 to +$50 (normal)
- **Good day**: +$50 to +$150
- **Bad day**: -$50 to -$150
- **Very bad day**: -$150 to -$200 (triggers daily limit)

**Position Duration**:
- **Scalp trades**: Minutes to hours
- **Swing trades**: Hours to days
- **Typical**: 4-12 hours

### Weekly Performance

**Expected Results** (rough estimates):
- **Week 1**: -$100 to +$100 (system learning)
- **Average week**: +$50 to +$200
- **Good week**: +$200 to +$500
- **Bad week**: -$100 to -$300

**Important**: Past performance doesn't guarantee future results!

### What's Abnormal

**Red Flags** 🚩:
1. **No trades for 3+ days** (when markets are open)
2. **5+ consecutive losing trades**
3. **Drawdown exceeding 10%**
4. **Single trade loss over $200**
5. **System showing OFFLINE for hours**
6. **Rapid equity swings** (±$500 in minutes)

**If you see red flags**:
1. Stop trading immediately
2. Review recent trades
3. Check for technical issues
4. Contact support before restarting

---

## 📈 NEXT IMPROVEMENTS (Roadmap)

### High Priority (Should add next)

#### **1. Email/Telegram Alerts**
- **Why**: Know immediately when issues occur
- **Features**:
  - Trade notifications
  - Drawdown warnings
  - System offline alerts
- **Impact**: Peace of mind, faster response

#### **2. Performance Analytics**
- **Why**: Better understand strategy performance
- **Features**:
  - Win rate calculation
  - Profit factor
  - Sharpe ratio
  - Maximum adverse excursion
- **Impact**: Make informed decisions

#### **3. Historical Backtesting**
- **Why**: Validate strategies before deploying
- **Features**:
  - Test on years of data
  - Monte Carlo simulation
  - Walk-forward analysis
- **Impact**: Higher confidence in strategies

#### **4. Trade Export/Reporting**
- **Why**: Analyze in Excel, tax reporting
- **Features**:
  - CSV export
  - PDF reports
  - Tax summaries
- **Impact**: Better record keeping

#### **5. Multi-Strategy Support**
- **Why**: Diversification reduces risk
- **Features**:
  - Run 3-5 strategies simultaneously
  - Different timeframes
  - Different assets
- **Impact**: More stable returns

### Medium Priority

#### **6. Position Management**
- Manual close/edit positions
- Adjust stop loss/take profit
- Partial position closes

#### **7. Advanced Risk Controls**
- Correlation limits
- Exposure limits per asset
- Time-based trading hours

#### **8. Strategy Marketplace**
- Share/discover strategies
- Community ratings
- Pre-tested bots

#### **9. Paper Trading History**
- View past 30/60/90 days
- Equity curves
- Trade journals

#### **10. User Accounts**
- Save preferences
- Multiple portfolios
- Custom settings

### Low Priority (Nice to have)

- Mobile app
- Social trading features
- Advanced charting
- News integration
- Economic calendar

---

## 📋 QUICK REFERENCE CHEAT SHEET

### Daily Checklist

**Morning (5 min)**
- [ ] Check ONLINE status (top right)
- [ ] Review equity (should be near $10k)
- [ ] Check drawdown (should be under 5%)
- [ ] Review overnight trades
- [ ] Verify risk status is ENABLED

**Evening (5 min)**
- [ ] Check daily P&L
- [ ] Review all trades for the day
- [ ] Check open positions
- [ ] Note any unusual activity

### Key Metrics Summary

| Metric | Safe | Warning | Critical |
|--------|------|---------|----------|
| **Equity** | $9,500-$10,500 | $9,000-$9,500 | <$9,000 |
| **Drawdown** | 0-5% | 5-10% | >10% |
| **Daily P&L** | -$100 to +$200 | -$200 to -$300 | <-$300 |
| **Trades/Day** | 1-3 | 4-5 | >5 or 0 for 3 days |

### URLs to Bookmark

```
Main App:
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com

Live Dashboard:
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/live

API Status:
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/api/paper-trading/status

API Docs:
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/docs
```

### Emergency Actions

**If equity drops below $9,000**:
1. System should auto-stop (15% drawdown)
2. Do NOT restart immediately
3. Review all trades
4. Contact support

**If system shows OFFLINE**:
1. Check backend: `supervisorctl status backend`
2. Check for stop reason in UI
3. Review logs: `tail -f /var/log/supervisor/backend.err.log`
4. Only restart if no errors found

**If suspicious activity**:
1. Stop trading immediately
2. Screenshot all data
3. Export trade history
4. Contact support before restarting

---

## 🎓 LEARNING PATH

### Week 1: Familiarization
- [ ] Read this guide completely
- [ ] Explore Live Dashboard
- [ ] Understand each metric
- [ ] Watch paper trading for 5-7 days
- [ ] Take notes on patterns

### Week 2: Active Monitoring
- [ ] Check dashboard 2x daily
- [ ] Start tracking trades manually
- [ ] Calculate your own statistics
- [ ] Identify winning vs losing patterns

### Week 3: Strategy Understanding
- [ ] Generate first AI bot
- [ ] Analyze the code
- [ ] Understand entry/exit logic
- [ ] Compare with EMA strategy

### Week 4: Risk Management
- [ ] Understand all safety features
- [ ] Calculate maximum loss scenarios
- [ ] Practice risk calculations
- [ ] Plan for different market conditions

### Month 2+: Advanced
- [ ] Test multiple bot configurations
- [ ] Analyze long-term performance
- [ ] Optimize parameters
- [ ] Consider transitioning to live trading (when available)

---

## 💡 TIPS FOR SUCCESS

### 1. **Patience is Key**
- Don't expect profits immediately
- First 2-4 weeks are learning period
- Focus on understanding, not profit

### 2. **Daily Monitoring (Not Obsessive)**
- Check 2-3 times daily is enough
- Don't check every hour
- Prevents emotional decisions

### 3. **Trust the System**
- Don't intervene unless critical
- Let strategy run its course
- Manual interference often makes things worse

### 4. **Keep Records**
- Screenshot interesting patterns
- Note market conditions
- Track weekly performance manually

### 5. **Understand Limitations**
- This is paper trading (practice)
- Real trading will be different
- Use this to learn and validate

### 6. **Risk First, Profit Second**
- Always check drawdown first
- Protect capital above all
- Consistent small gains > risky big wins

### 7. **Learn Continuously**
- Understand why trades win/lose
- Study market conditions
- Read about EMA strategies
- Join trading communities

---

## 📞 SUPPORT & RESOURCES

### Getting Help

**For Technical Issues**:
1. Check Troubleshooting section first
2. Review logs for errors
3. Try basic fixes (restart, refresh)
4. Contact support with details

**For Strategy Questions**:
1. Review strategy workflow section
2. Check Bot Factory documentation
3. Test in paper trading first

**For Performance Concerns**:
1. Check if behavior is "normal" (see section)
2. Review risk management rules
3. Calculate metrics manually to verify

### System Health Commands

```bash
# Check all services
supervisorctl status

# View backend logs
tail -f /var/log/supervisor/backend.err.log

# View frontend logs
tail -f /var/log/supervisor/frontend.err.log

# Restart services
supervisorctl restart backend
supervisorctl restart frontend

# Test API
curl https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/api/paper-trading/status
```

---

## ✅ FINAL CHECKLIST

Before you start trading, make sure you:

- [ ] Read this entire guide
- [ ] Understand all components (Factory, Engine, Dashboard)
- [ ] Bookmarked all important URLs
- [ ] Know how to check system status
- [ ] Understand what each metric means
- [ ] Know the risk management rules
- [ ] Can identify normal vs abnormal behavior
- [ ] Know when to stop trading
- [ ] Understand current limitations
- [ ] Have realistic expectations

**Remember**: This is paper trading (virtual money). Use it to learn, test, and gain confidence before considering live trading.

---

## 📝 GLOSSARY

**Bot Factory**: AI-powered tool that generates cTrader trading bot code

**Paper Trading**: Simulated trading with virtual money using real market data

**Equity**: Current account value (cash + open positions)

**P&L (Profit & Loss)**: Total profit or loss (Equity - Starting Balance)

**Drawdown**: Percentage drop from peak equity to current value

**Open Position**: Currently active trade (not yet closed)

**EMA (Exponential Moving Average)**: Technical indicator that smooths price data

**Crossover**: When one indicator crosses above/below another (trading signal)

**Stop Loss**: Automatic exit price to limit losses

**LONG**: Buying position (profit when price goes up)

**SHORT**: Selling position (profit when price goes down)

**Risk Guardian**: System that monitors and enforces risk limits

**Kill Switch**: Automatic stop when risk limits exceeded

**Prop Firm**: Proprietary trading firm that provides capital to traders

---

**Document Version**: 1.0  
**Last Updated**: March 29, 2026  
**System Status**: Fully Operational  
**For**: Bot Factory Trading Platform v1.0

---

🎉 **Congratulations!** You now have a complete guide to operating your trading platform. Start with paper trading, learn the system, and build confidence before moving to live trading. Happy trading! 📈
