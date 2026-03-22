# Quick Reference Card - cTrader Bot Builder

## 🚀 Quick Navigation

| Feature | Route | Primary Use | Time Required |
|---------|-------|-------------|---------------|
| **Quick Score** | `/quick-score` | Fast quality check | 30 seconds |
| **Builder Pro** | `/builder-pro` | Create new bots | 2-5 minutes |
| **Analyze Bot** | `/analyze-bot` | Deep code analysis | 1-2 minutes |
| **Discovery** | `/discovery` | Find GitHub bots | 5-15 minutes |
| **Library** | `/library` | Manage strategies | Variable |

---

## ⚡ Builder Pro Cheat Sheet

### 1. Strategy Description Template
```
"[Strategy Type] using [Indicators].
Entry: [When to buy/sell]
Exit: [When to close]
Risk: [Stop loss method]
Timeframe: [Preferred timeframe]"
```

### 2. Settings Quick Guide
- **Risk:** 0.5-1% (conservative), 1-2% (moderate), 2-5% (aggressive)
- **Timeframe:** M1-M5 (scalping), H1-H4 (swing), D1 (position)
- **Type:** Trend/Range/Breakout/Scalping
- **AI Model:** GPT-4o (complex), Claude (clean code)
- **Prop Firm:** Select if trading with funded account

### 3. Validation Pipeline
```
Generate → Validate → Compile → Compliance → Copy
   ↓          ↓          ↓           ↓         ↓
 15-30s    10-20s     10-30s      5-10s    Instant
```

### 4. Status Indicators
- 🟡 **Waiting** = Not started
- 🔵 **Running** = In progress  
- 🟢 **Passed** = Success
- 🔴 **Failed** = Needs attention

---

## 📊 Feature Comparison

| What You Need | Use This Feature | Why |
|---------------|------------------|-----|
| Create new bot from scratch | **Builder Pro** | AI generates complete code |
| Check existing bot quality | **Quick Score** | Fast assessment |
| Understand existing bot | **Analyze Bot** | Detailed breakdown |
| Find proven strategies | **Discovery** | GitHub search + analysis |
| Organize your bots | **Library** | Central repository |
| Improve existing bot | **Analyze Bot** → **Builder Pro** | Analysis + regeneration |
| Ensure prop firm rules | **Builder Pro** (with firm selected) | Auto-compliance |
| Learn from others | **Discovery** → **Analyze Bot** | Find + study |

---

## 🎯 Common Workflows

### Workflow 1: Complete Beginner
```
Discovery (find inspiration) 
    ↓
Builder Pro (create your version)
    ↓
Validate → Compile → Copy
    ↓
Deploy in cTrader
```

### Workflow 2: Improve Existing
```
Analyze Bot (understand current)
    ↓
Note suggestions
    ↓
Builder Pro (generate improved)
    ↓
Compare in Library
```

### Workflow 3: Research & Build Library
```
Discovery (mass search)
    ↓
Filter by score (>85)
    ↓
Add best to Library
    ↓
Analyze top performers
    ↓
Build custom versions
```

---

## ⚙️ Prop Firm Rules Quick Reference

| Firm | Max Daily Loss | Max Drawdown | Max Risk/Trade | Stop Loss |
|------|----------------|--------------|----------------|-----------|
| **FTMO** | 5% | 10% | 1% | Required |
| **FundedNext** | 5% | 12% | 2% | Required |
| **PipFarm** | 4% | 8% | 1.5% | Required |
| **The5ers** | 5% | 10% | 1% | Required |

---

## 🔧 Troubleshooting Quick Fixes

| Problem | Quick Fix |
|---------|-----------|
| Generate button not working | Check EMERGENT_LLM_KEY in backend .env |
| Validation fails | Copy to Analyze Bot for details |
| Compilation errors | Enable auto-fix (up to 3 attempts) |
| Compliance issues | Regenerate with lower risk % |
| Discovery empty | Use broader keywords like "ctrader" |
| Frontend not loading | Check browser console, restart frontend |
| Backend API errors | Check `/var/log/supervisor/backend.err.log` |

---

## 📝 Strategy Description Examples

### Mean Reversion
```
"RSI mean reversion on H1. Buy when RSI < 30 and price 
below lower Bollinger Band. Sell when RSI > 70 and price 
above upper BB. Exit when RSI crosses 50. Use 2x ATR 
stop loss and 2:1 risk-reward."
```

### Trend Following
```
"MACD crossover with 200 EMA filter on H4. Enter long when 
MACD crosses above signal line and price > 200 EMA. Enter 
short when MACD crosses below and price < 200 EMA. 
Stop loss 1.5x ATR, trail stop after 1:1."
```

### Breakout
```
"Support/resistance breakout on M15. Identify swing highs/lows 
from H1. Enter on breakout with volume confirmation. 
Stop loss just inside S/R level. Target 2x stop distance."
```

### Scalping
```
"Fast EMA crossover scalping on M5. Enter when 9 EMA crosses 
21 EMA. Exit after 10 pips profit or 5 pips loss. 
Max 1 position open. Trade only during London/NY sessions."
```

---

## 🎓 Best Practices

### Do's ✅
- ✅ Always run full validation pipeline
- ✅ Test on demo before live
- ✅ Use prop firm rules even if not funded (adds safety)
- ✅ Start with simple strategies
- ✅ Keep risk low (0.5-1% per trade)
- ✅ Backtest for at least 6 months
- ✅ Monitor first week closely
- ✅ Version control in Library
- ✅ Add notes to saved strategies
- ✅ Compare multiple timeframes

### Don'ts ❌
- ❌ Skip validation steps
- ❌ Use untested bots on live account
- ❌ Set risk above 2% per trade
- ❌ Trade without stop loss
- ❌ Ignore compliance warnings
- ❌ Copy code without understanding
- ❌ Use overly complex strategies first
- ❌ Deploy without backtesting
- ❌ Modify generated code without re-validating
- ❌ Trust backtests alone (forward test too)

---

## 📞 Quick Support

### Check These First
1. **Browser Console** - F12, check for JavaScript errors
2. **Backend Logs** - `tail -f /var/log/supervisor/backend.err.log`
3. **Frontend Logs** - `tail -f /var/log/supervisor/frontend.out.log`
4. **Service Status** - `sudo supervisorctl status`

### Restart Services
```bash
# Restart all
sudo supervisorctl restart all

# Restart specific
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
```

### Environment Check
```bash
# Check backend env
cat /app/backend/.env

# Check if EMERGENT_LLM_KEY is set
grep EMERGENT_LLM_KEY /app/backend/.env
```

---

## 🔑 Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+/` | Toggle comments in code editor |
| `Ctrl+C` | Copy selected code |
| `Ctrl+A` | Select all code |
| `Ctrl+F` | Find in code |
| `Ctrl+Z` | Undo in editor |
| `Ctrl+Shift+F` | Format code |

---

## 📊 Scoring System

### Quality Score Breakdown
- **90-100** = Excellent (deploy with confidence)
- **80-89** = Very Good (minor tweaks)
- **70-79** = Good (needs refinement)
- **60-69** = Fair (significant work needed)
- **0-59** = Poor (start over)

### What Affects Score
- Code structure (30%)
- Strategy logic (30%)
- Risk management (20%)
- Maintainability (20%)

---

## 🚨 Common Errors & Solutions

### "EMERGENT_LLM_KEY not set"
**Solution:** Add key to `/app/backend/.env` and restart backend

### "Compilation failed after 3 attempts"
**Solution:** Copy code to IDE, fix manually, paste back

### "Prop firm compliance not met"
**Solution:** Lower risk %, ensure stop loss, add daily loss tracking

### "Module not found: @monaco-editor/react"
**Solution:** `cd /app/frontend && yarn add @monaco-editor/react`

### "Cannot connect to backend"
**Solution:** Check `REACT_APP_BACKEND_URL` in frontend .env

---

## 📈 Performance Metrics Guide

### Key Metrics to Track
- **Win Rate:** >55% is good, >65% is excellent
- **Profit Factor:** >1.5 acceptable, >2.0 good
- **Max Drawdown:** <15% good, <10% excellent
- **Sharpe Ratio:** >1.0 acceptable, >1.5 good
- **Risk-Reward:** Aim for 1.5:1 or better

### Red Flags
- 🚩 Win rate <45%
- 🚩 Max drawdown >25%
- 🚩 Profit factor <1.2
- 🚩 Average loss > Average win
- 🚩 Long losing streaks (>10 trades)

---

## 🎯 Strategy Selection Guide

### Choose By Market Condition

**Trending Markets (ADX > 25)**
- Use: Trend Following strategies
- Indicators: MACD, Moving Averages, ADX
- Timeframe: H1-H4

**Ranging Markets (ADX < 20)**
- Use: Mean Reversion strategies
- Indicators: RSI, Bollinger Bands, Stochastic
- Timeframe: M15-H1

**Volatile Markets (High ATR)**
- Use: Breakout strategies
- Indicators: Support/Resistance, Volume, ATR
- Timeframe: M15-H1

**Low Volatility Markets**
- Use: Scalping strategies
- Indicators: Fast EMAs, Momentum
- Timeframe: M1-M15

---

## 💡 Pro Tips

1. **Start Small:** Test with minimum lot size first
2. **Diversify:** Use 2-3 uncorrelated strategies
3. **Time-Based Rules:** Avoid trading during news
4. **Weekend Protection:** Disable over weekends
5. **Version Everything:** Save each iteration
6. **Monitor First Week:** Check every trade manually
7. **Set Alerts:** For max daily loss, drawdown limits
8. **Regular Reviews:** Weekly performance analysis
9. **Keep Learning:** Analyze both wins and losses
10. **Stay Disciplined:** Don't override bot decisions

---

**Print This Page for Quick Reference!**

Last Updated: March 20, 2026
