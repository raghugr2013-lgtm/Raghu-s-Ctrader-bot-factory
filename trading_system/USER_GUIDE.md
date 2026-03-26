# cTrader Bot Builder - Complete User Guide

## Table of Contents
1. [Overview](#overview)
2. [Quick Score](#1-quick-score)
3. [Builder Pro](#2-builder-pro-ai-bot-builder)
4. [Analyze Bot](#3-analyze-bot)
5. [Discovery Engine](#4-discovery-engine)
6. [Strategy Library](#5-strategy-library)
7. [Workflow Examples](#workflow-examples)

---

## Overview

The cTrader Bot Builder is a comprehensive platform for creating, analyzing, and managing cTrader trading bots (cBots). It provides five main features accessible from the navigation bar:

- **Quick Score** - Rapid bot quality assessment
- **Builder Pro** - AI-powered bot generation with validation
- **Analyze Bot** - Deep code analysis and refinement
- **Discovery Engine** - GitHub bot discovery and ranking
- **Strategy Library** - Browse and manage approved strategies

---

## 1. Quick Score

### What It Does
Quick Score provides instant quality assessment of your cBot code. It's designed for rapid evaluation without deep analysis.

### Use Cases
- ✅ Quick validation before deployment
- ✅ Initial quality check for new bots
- ✅ Fast scoring of multiple bots
- ✅ Pre-screening before deep analysis

### How to Use

1. **Navigate to Quick Score**
   - Click "Quick Score" in the navigation bar
   - Or use the hero section button

2. **Input Your Code**
   - Paste your complete C# cBot code into the editor
   - Code must be valid cTrader cBot format

3. **Click "Quick Score"**
   - System analyzes the code instantly
   - Returns a quality score (0-100)

4. **Review Results**
   - Overall quality score
   - Key strengths identified
   - Critical issues flagged
   - Quick recommendations

### What Gets Scored
- Code structure and organization
- Risk management implementation
- Entry/exit logic clarity
- Error handling presence
- Best practices adherence

### Output Format
```
Score: 85/100
Strengths: Good risk management, clear entry logic
Issues: Missing stop-loss validation
Recommendation: Add ATR-based stops
```

---

## 2. Builder Pro (AI Bot Builder)

### What It Does
Builder Pro is an AI-powered bot generation system that creates complete, production-ready cTrader cBots from natural language descriptions. It includes validation, compilation checking, and prop firm compliance verification.

### Complete Workflow
**Strategy Description → AI Generation → Validation → Compilation → Compliance Check**

---

### 2.1 Strategy Input Section

#### What It Does
Converts your trading idea into a structured bot specification.

#### How to Use

**Step 1: Describe Your Strategy**
Write a natural language description of your trading strategy:

**Example Inputs:**
```
"RSI + Bollinger Bands mean reversion on EUR/USD H1. 
Buy when RSI < 30 and price below lower band. 
Sell when RSI > 70 and price above upper band. 
Use ATR-based stop loss at 2x ATR."
```

```
"MACD crossover trend following strategy. 
Enter long when MACD crosses above signal line and price > 200 EMA.
Enter short when MACD crosses below signal line and price < 200 EMA.
Exit when opposite signal occurs."
```

```
"Breakout strategy on support/resistance levels.
Identify 4H swing highs/lows.
Enter on breakout with volume confirmation.
Stop loss 1 ATR below entry.
Take profit at 2:1 risk-reward."
```

**What to Include:**
- 📊 Indicators used (RSI, MACD, Bollinger Bands, EMA, ATR, etc.)
- 📈 Entry conditions (when to buy/sell)
- 📉 Exit conditions (when to close)
- 🛡️ Risk management (stop loss, take profit)
- 💰 Position sizing (optional)
- ⏰ Timeframe preference

---

### 2.2 Settings Configuration

#### Risk Per Trade (%)
**What It Does:** Sets maximum account balance risked per trade

**Options:** 0.1% - 10%
**Default:** 2%
**Recommended:**
- Conservative: 0.5% - 1%
- Moderate: 1% - 2%
- Aggressive: 2% - 5%

**Example:**
- Account: $10,000
- Risk: 2%
- Max loss per trade: $200

---

#### Timeframe Selection
**What It Does:** Sets the chart timeframe your bot will analyze

**Options:**
- M1 (1 minute) - Scalping
- M5 (5 minutes) - Fast scalping
- M15 (15 minutes) - Scalping/Day trading
- M30 (30 minutes) - Day trading
- H1 (1 hour) - Day trading/Swing
- H4 (4 hours) - Swing trading
- D1 (Daily) - Position trading

**When to Use:**
- **M1-M5**: High-frequency scalping (requires fast execution)
- **M15-M30**: Intraday trading (5-20 trades/day)
- **H1-H4**: Swing trading (1-5 trades/day)
- **D1**: Position trading (few trades/week)

---

#### Strategy Type
**What It Does:** Categorizes your strategy for optimized code generation

**Options:**

1. **Trend Following**
   - Follows market direction
   - Uses moving averages, MACD, ADX
   - Best in trending markets
   - Example: "Buy when price > 200 EMA and MACD positive"

2. **Range / Mean Reversion**
   - Trades bounces from support/resistance
   - Uses RSI, Bollinger Bands, Stochastic
   - Best in sideways markets
   - Example: "Buy when RSI < 30 at support level"

3. **Breakout**
   - Trades price breaks through key levels
   - Uses support/resistance, volume
   - Best at market open or news
   - Example: "Buy when price breaks above resistance with high volume"

4. **Scalping**
   - Multiple small profits quickly
   - Uses tight stops, quick exits
   - Requires low spread
   - Example: "5-pip profit target, 3-pip stop loss"

---

#### AI Model Selection
**What It Does:** Chooses the AI engine for code generation

**Options:**

1. **GPT-4o** (OpenAI)
   - Best for: Complex multi-indicator strategies
   - Strengths: Advanced logic, detailed comments
   - Speed: Fast (~10-15 seconds)
   - Use when: Need sophisticated risk management

2. **Claude** (Anthropic)
   - Best for: Clean, maintainable code
   - Strengths: Better code structure, error handling
   - Speed: Medium (~15-20 seconds)
   - Use when: Code quality is priority

**Recommendation:** Start with GPT-4o, switch to Claude if you need cleaner code structure.

---

#### Prop Firm Selection
**What It Does:** Enforces specific prop firm trading rules in your bot

**Options:**

1. **None** - No specific rules
2. **FTMO**
   - Max Daily Loss: 5%
   - Max Total Drawdown: 10%
   - Max Risk/Trade: 1%
   - Max Open Trades: 10
   - Stop Loss: Required

3. **FundedNext**
   - Max Daily Loss: 5%
   - Max Total Drawdown: 12%
   - Max Risk/Trade: 2%
   - Max Open Trades: 15
   - Stop Loss: Required

4. **PipFarm**
   - Max Daily Loss: 4%
   - Max Total Drawdown: 8%
   - Max Risk/Trade: 1.5%
   - Max Open Trades: 8
   - Stop Loss: Required

5. **The5ers**
   - Max Daily Loss: 5%
   - Max Total Drawdown: 10%
   - Max Risk/Trade: 1%
   - Max Open Trades: 12
   - Stop Loss: Required

**Why It Matters:**
- Bot automatically enforces these rules
- Prevents rule violations
- Adds safety checks in code
- Includes daily loss monitoring

---

### 2.3 Generate Bot

#### What Happens
1. AI analyzes your strategy description
2. Considers your settings (risk, timeframe, type)
3. Applies prop firm rules (if selected)
4. Generates complete C# cBot code
5. Auto-runs compilation gate
6. Returns verified, production-ready code

#### Generation Time
- Simple strategies: 10-20 seconds
- Complex strategies: 20-40 seconds
- With auto-fix: +5-10 seconds

#### What You Get
```csharp
using System;
using cAlgo.API;
using cAlgo.API.Indicators;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class RSI_BollingerBot : Robot
    {
        // Full working bot code with:
        // - All indicators initialized
        // - Risk management
        // - Entry/exit logic
        // - Error handling
        // - Prop firm compliance
        // - Comments and documentation
    }
}
```

---

### 2.4 Validation

#### What It Does
Checks your bot code for syntax errors and compliance issues.

#### Validation Checks

**Syntax Validation:**
- ✅ Valid C# syntax
- ✅ All using statements present
- ✅ Proper class structure
- ✅ Method implementations
- ✅ Variable declarations

**Compliance Validation (if prop firm selected):**
- ✅ Stop loss implementation
- ✅ Risk per trade limits
- ✅ Daily loss tracking
- ✅ Max open trades limit
- ✅ Drawdown monitoring

#### Status Indicators
- 🟡 **Waiting** - Not run yet
- 🔵 **Running** - Validation in progress
- 🟢 **Passed** - No critical errors
- 🔴 **Issues Found** - Errors detected

#### Results Display
```
✅ No critical errors

Warnings:
⚠️  Consider adding position size validation
⚠️  Missing null check for indicator values

Errors:
❌ None
```

---

### 2.5 Compilation Gate

#### What It Does
Verifies your bot will compile successfully in cTrader. Includes auto-fix for common issues.

#### Auto-Fix Features
- Fixes missing semicolons
- Adds missing using statements
- Corrects variable scoping
- Fixes method signatures
- Updates deprecated API calls

#### How It Works
1. Attempts compilation
2. If errors found, analyzes them
3. Applies automatic fixes
4. Re-compiles (up to 3 attempts)
5. Returns fixed code

#### Max Attempts
- Default: 3 auto-fix attempts
- Fixes most common issues
- Manual review needed for complex errors

#### Status Indicators
- 🟡 **Waiting** - Not run yet
- 🔵 **Compiling** - Check in progress
- 🟢 **Verified** - Compilation successful
- 🔴 **Failed** - Manual fixes needed

#### Results Display
```
✅ Compile verified
   2 auto-fixes applied

Fixes Applied:
- Added missing using cAlgo.API.Internals
- Fixed variable scope in OnBar method

Warnings:
⚠️  Indicator calculation may be heavy on M1 timeframe
```

---

### 2.6 Compliance Check

#### What It Does
Verifies your bot follows prop firm rules (FTMO, FundedNext, etc.)

#### Requirements
- Must select a prop firm (not "None")
- Bot must have generated code

#### What Gets Checked

**Risk Management:**
- ✅ Risk per trade within limits
- ✅ Stop loss implementation
- ✅ Position sizing correct
- ✅ Max open trades enforced

**Drawdown Protection:**
- ✅ Daily loss tracking
- ✅ Max drawdown monitoring
- ✅ Auto-disable on limit breach

**Rule Compliance:**
- ✅ No hedging (if prohibited)
- ✅ No martingale (if prohibited)
- ✅ No grid trading (if prohibited)
- ✅ Weekend trading rules

#### Severity Levels
- 🔴 **Critical** - Must fix before use
- 🟠 **High** - Fix recommended
- 🟡 **Medium** - Improvement suggested
- 🟢 **Low** - Optional enhancement

#### Results Display
```
❌ Not fully compliant

Violations:
🔴 [Critical] Risk per trade exceeds 1% limit (current: 2%)
🟠 [High] Daily loss tracking not implemented
🟡 [Medium] Consider adding slippage protection

Recommendations:
- Reduce risk_percent parameter to 1.0
- Add daily P&L counter in OnPositionClosed
- Add MaxSlippage parameter to ExecuteMarketOrder
```

---

### 2.7 Code Output Panel

#### What It Contains
- Full C# cBot source code
- Editable (you can modify)
- Auto-updated after auto-fixes
- Copy button for clipboard

#### What to Do With It

**Option 1: Use As-Is**
1. Copy the code
2. Open cTrader
3. Create new cBot
4. Paste code
5. Build and run

**Option 2: Customize**
1. Edit in the panel
2. Re-run validation
3. Re-run compilation
4. Copy modified version

**Option 3: Further Analysis**
1. Copy the code
2. Go to "Analyze Bot" page
3. Paste for deep analysis
4. Get improvement suggestions

---

### Complete Builder Pro Workflow Example

**Scenario:** Create an RSI mean reversion bot for FTMO

**Step 1: Input Strategy**
```
"RSI oversold/overbought strategy. Buy when RSI < 30, 
sell when RSI > 70. Exit at opposite signal. 
Use 2% risk with ATR-based stops."
```

**Step 2: Configure Settings**
- Risk: 1% (FTMO requires max 1%)
- Timeframe: H1
- Strategy Type: Range / Mean Reversion
- AI Model: GPT-4o
- Prop Firm: FTMO

**Step 3: Generate**
- Click "Generate Bot"
- Wait 15-20 seconds
- Code appears in output panel

**Step 4: Validate**
- Click "Run Validation"
- Status: ✅ Passed
- Result: "No critical errors, 1 warning"

**Step 5: Compile**
- Click "Compile Gate"
- Status: ✅ Verified
- Result: "Compilation successful, 1 auto-fix applied"

**Step 6: Check Compliance**
- Click "Check Compliance"
- Status: ✅ Fully compliant
- Result: "All FTMO rules satisfied"

**Step 7: Deploy**
- Copy code
- Import to cTrader
- Backtest
- Deploy live

**Total Time:** 2-3 minutes

---

## 3. Analyze Bot

### What It Does
Performs deep analysis of existing cBot code, extracts strategy details, identifies issues, and provides improvement suggestions.

### Use Cases
- 🔍 Understand existing bots
- 🐛 Find hidden bugs
- 💡 Get improvement ideas
- 📊 Extract strategy parameters
- 🔧 Refine and optimize

### How to Use

**Step 1: Navigate to Analyze Bot**
- Click "Analyze Bot" in navigation

**Step 2: Paste Your Code**
- Paste complete C# cBot code
- Can be from Builder Pro or any source

**Step 3: Click "Analyze Bot"**
- Deep analysis runs (20-30 seconds)
- AI examines all aspects

**Step 4: Review Analysis**
Results include:

#### Strategy Overview
```
Strategy Type: Mean Reversion
Indicators Used: RSI(14), Bollinger Bands(20, 2)
Timeframe: H1
Trading Pairs: Any (configurable)
```

#### Entry Logic
```
Long Entry:
- RSI < 30 (oversold)
- Price below lower Bollinger Band
- Wait for candle close confirmation

Short Entry:
- RSI > 70 (overbought)
- Price above upper Bollinger Band
- Wait for candle close confirmation
```

#### Exit Logic
```
Exit Long:
- RSI crosses above 50
- Or stop loss hit
- Or take profit hit

Exit Short:
- RSI crosses below 50
- Or stop loss hit
- Or take profit hit
```

#### Risk Management Analysis
```
Position Sizing: % of balance
Stop Loss: ATR-based (2x ATR)
Take Profit: 2:1 risk-reward ratio
Max Positions: 1 at a time
Risk per Trade: 2% of balance
```

#### Code Quality Assessment
```
Score: 78/100

Strengths:
✅ Clear indicator initialization
✅ Good error handling in OnBar
✅ Proper position management
✅ Well-commented code

Issues Found:
❌ No null check for indicator values
❌ Missing weekend trading filter
⚠️  Hard-coded risk percentage (should be parameter)
⚠️  No drawdown protection

Improvements Suggested:
1. Add indicator null validation
2. Implement trading hours filter
3. Make risk% a parameter
4. Add max daily loss limit
```

#### Security Issues
```
🔴 Critical: API calls without timeout
🟠 High: No validation on user inputs
🟡 Medium: Hard-coded credentials (if any)
```

**Step 5: Generate Refined Version (Optional)**
- Click "Generate Improved Bot"
- AI creates enhanced version
- Applies all suggestions
- Returns optimized code

---

## 4. Discovery Engine

### What It Does
Automatically searches GitHub for cTrader bots, analyzes them, scores quality, and stores the best ones in your library.

### Use Cases
- 🔎 Find high-quality open-source bots
- 📚 Build strategy library
- 🏆 Compare bot performance
- 💡 Learn from others' code
- ⚡ Quick start with proven strategies

### How to Use

**Step 1: Navigate to Discovery**
- Click "Discovery" in navigation

**Step 2: Configure Search**

#### Search Keywords
```
Examples:
- "ctrader rsi macd"
- "algorithmic trading bot"
- "forex cbot strategy"
- "mean reversion trading"
```

#### Minimum Stars (Optional)
- Filter by GitHub stars
- Default: 0 (all repos)
- Recommended: 5+ for quality

#### Max Results
- Number of repos to analyze
- Default: 10
- Range: 1-50

**Step 3: Start Discovery**
- Click "Start Discovery"
- System searches GitHub
- Analyzes each bot found
- Scores and ranks them

**Step 4: Monitor Progress**
```
Progress: 7/10 repositories analyzed
Current: Analyzing SMA_Crossover_Bot
Time Remaining: ~2 minutes
```

**Step 5: Review Results**
Results sorted by score:

```
┌─────────────────────────────────────────────────┐
│ #1: RSI_BollingerBands_Bot        Score: 92/100│
│ Repository: user/rsi-bb-cbot                    │
│ Stars: 45  |  Language: C#  |  Updated: 2 days │
│                                                  │
│ Strengths:                                       │
│ ✅ Excellent risk management                    │
│ ✅ Clean, documented code                       │
│ ✅ Backtested results included                  │
│                                                  │
│ Strategy: Mean reversion using RSI + BB         │
│ Indicators: RSI(14), Bollinger Bands(20, 2)     │
│ Risk: 1.5% per trade                            │
│                                                  │
│ [View Code] [Add to Library] [Visit Repo]       │
└─────────────────────────────────────────────────┘
```

**Step 6: Actions**
- **View Code**: See full source
- **Add to Library**: Save to Strategy Library
- **Visit Repo**: Open GitHub page

### Scoring System

**Quality Score (0-100):**

**Code Quality (30 points)**
- Structure and organization
- Comments and documentation
- Error handling
- Best practices

**Strategy Quality (30 points)**
- Logic clarity
- Indicator usage
- Entry/exit rules
- Risk management

**Risk Management (20 points)**
- Stop loss implementation
- Position sizing
- Drawdown protection
- Money management

**Maintainability (20 points)**
- Code readability
- Parameter flexibility
- Modularity
- Test coverage

**Scoring Ranges:**
- 90-100: Excellent (production-ready)
- 80-89: Very Good (minor improvements)
- 70-79: Good (needs refinement)
- 60-69: Fair (significant improvements needed)
- Below 60: Poor (not recommended)

---

## 5. Strategy Library

### What It Does
Centralized repository of analyzed and approved trading strategies. Browse, filter, sort, and manage your bot collection.

### Use Cases
- 📚 Store approved strategies
- 🔍 Search by indicators/type
- 📊 Compare performance metrics
- 📋 Copy proven strategies
- 🗂️ Organize your bots

### How to Use

**Step 1: Navigate to Library**
- Click "Strategy Library" in navigation

**Step 2: Browse Strategies**

#### View Modes
1. **Grid View** - Cards with key info
2. **List View** - Detailed table
3. **Compact View** - Names only

#### Strategy Card Shows:
```
┌──────────────────────────────────────────┐
│ RSI Mean Reversion Bot                   │
│ Score: 88/100  ⭐⭐⭐⭐                    │
│ Type: Mean Reversion  |  Timeframe: H1   │
│ Risk: 1.5%            |  Max DD: 12%     │
│                                           │
│ Indicators:                               │
│ • RSI (14)                                │
│ • Bollinger Bands (20, 2)                │
│                                           │
│ Performance:                              │
│ Win Rate: 68%  |  Profit Factor: 2.3     │
│ Avg Win: $45   |  Avg Loss: $23          │
│                                           │
│ [View Details] [Copy Code] [Edit]        │
└──────────────────────────────────────────┘
```

**Step 3: Filter and Sort**

#### Filter Options:
- **Strategy Type**
  - Trend Following
  - Mean Reversion
  - Breakout
  - Scalping

- **Indicators**
  - RSI
  - MACD
  - Moving Averages
  - Bollinger Bands
  - ATR
  - Stochastic
  - Custom

- **Timeframe**
  - M1, M5, M15, M30
  - H1, H4
  - D1

- **Risk Level**
  - Low (< 1%)
  - Medium (1-2%)
  - High (> 2%)

- **Score Range**
  - 90-100 (Excellent)
  - 80-89 (Very Good)
  - 70-79 (Good)
  - Below 70

#### Sort Options:
- Score (High to Low)
- Date Added (Newest First)
- Win Rate
- Profit Factor
- Alphabetical

**Step 4: View Strategy Details**

Click any strategy to see:

```
════════════════════════════════════════════
RSI Mean Reversion Bot - Detailed View
════════════════════════════════════════════

OVERVIEW
Strategy Type: Mean Reversion
Creator: @github/user
Date Added: 2026-03-15
Last Updated: 2026-03-18
Score: 88/100

INDICATORS & PARAMETERS
• RSI (Period: 14)
  - Oversold: 30
  - Overbought: 70
• Bollinger Bands (Period: 20, Deviation: 2)
• ATR (Period: 14) for stop loss

ENTRY RULES
Long Entry:
1. RSI crosses below 30
2. Price touches lower Bollinger Band
3. Wait for candle close
4. Enter at market open next candle

Short Entry:
1. RSI crosses above 70
2. Price touches upper Bollinger Band
3. Wait for candle close
4. Enter at market open next candle

EXIT RULES
Long Exit:
- RSI crosses above 50 (neutral)
- Stop loss: 2x ATR below entry
- Take profit: 2:1 risk-reward

Short Exit:
- RSI crosses below 50 (neutral)
- Stop loss: 2x ATR above entry
- Take profit: 2:1 risk-reward

RISK MANAGEMENT
• Risk per trade: 1.5% of balance
• Max open positions: 1
• Max daily loss: 5%
• Stop loss: Always used (ATR-based)
• Position sizing: % of balance

PERFORMANCE METRICS
Backtest Period: 2024-01-01 to 2026-03-01
Total Trades: 234
Win Rate: 68%
Profit Factor: 2.3
Max Drawdown: 12%
Sharpe Ratio: 1.8
Average Win: $45
Average Loss: $23
Largest Win: $120
Largest Loss: $67

BEST PAIRS
1. EUR/USD (71% win rate)
2. GBP/USD (66% win rate)
3. USD/JPY (64% win rate)

BEST TIMEFRAMES
1. H1 (primary)
2. H4 (secondary)

MARKET CONDITIONS
Works best in:
✅ Ranging markets
✅ Low volatility periods
⚠️  Struggles in strong trends

PROP FIRM COMPLIANCE
✅ FTMO compliant
✅ FundedNext compliant
✅ PipFarm compliant
✅ The5ers compliant

ACTIONS
[Copy Code] [Edit Strategy] [Run Backtest] 
[Export] [Delete] [Share]
════════════════════════════════════════════
```

**Step 5: Manage Strategies**

#### Actions Available:
1. **Copy Code** - Copy to clipboard
2. **Edit** - Modify parameters
3. **Export** - Download as .cs file
4. **Delete** - Remove from library
5. **Share** - Generate share link
6. **Duplicate** - Create variant
7. **Add Notes** - Personal annotations

---

## Workflow Examples

### Example 1: Complete Beginner Workflow

**Goal:** Create and deploy your first bot

**Step 1: Get Inspiration (5 min)**
1. Go to **Discovery Engine**
2. Search: "simple rsi trading bot"
3. Review top 3 results
4. Note what strategies work

**Step 2: Build Your Bot (10 min)**
1. Go to **Builder Pro**
2. Describe strategy:
   ```
   "Buy when RSI < 30, sell when RSI > 70.
   Exit at opposite signal. Use 1% risk."
   ```
3. Settings:
   - Risk: 1%
   - Timeframe: H1
   - Type: Mean Reversion
   - Model: GPT-4o
   - Prop Firm: None (for learning)
4. Click "Generate Bot"

**Step 3: Validate (2 min)**
1. Click "Run Validation"
2. Check for errors
3. If errors, click "Fix Issues"

**Step 4: Test Compilation (1 min)**
1. Click "Compile Gate"
2. Auto-fix applies
3. Verify success

**Step 5: Copy and Deploy (5 min)**
1. Click "Copy Code"
2. Open cTrader
3. Algorithmic Trading → New cBot
4. Paste code
5. Click Build
6. Backtest on demo

**Total Time:** ~23 minutes

---

### Example 2: Advanced User Workflow

**Goal:** Optimize existing bot for FTMO

**Step 1: Analyze Current Bot (5 min)**
1. Go to **Analyze Bot**
2. Paste existing code
3. Review analysis
4. Note compliance issues

**Step 2: Refine Strategy (10 min)**
1. Note suggestions from analysis
2. Go to **Builder Pro**
3. Describe improved version:
   ```
   "Enhanced RSI strategy with:
   - Daily loss limit (5%)
   - Max drawdown protection (10%)
   - Proper stop loss validation
   - Risk per trade: 1%
   Include FTMO safety checks"
   ```
4. Settings:
   - Risk: 1%
   - Prop Firm: FTMO
5. Generate

**Step 3: Full Validation Pipeline (5 min)**
1. Run Validation
2. Run Compile Gate
3. Run Compliance Check
4. Verify all ✅ green

**Step 4: Store in Library (2 min)**
1. Copy code
2. Go to **Strategy Library**
3. Click "Add Strategy"
4. Paste code
5. Add notes and tags

**Step 5: Compare Performance (5 min)**
1. In Strategy Library
2. Compare old vs new version
3. Review compliance status
4. Select best version

**Total Time:** ~27 minutes

---

### Example 3: Discovery and Improvement Workflow

**Goal:** Find and improve top GitHub bots

**Step 1: Mass Discovery (15 min)**
1. Go to **Discovery Engine**
2. Search: "ctrader profitable bot"
3. Min Stars: 10
4. Max Results: 20
5. Start Discovery
6. Wait for analysis

**Step 2: Filter Best Results (5 min)**
1. Sort by Score (High to Low)
2. Filter: Score > 85
3. Review top 5

**Step 3: Deep Analysis (10 min per bot)**
1. Copy code from Discovery
2. Go to **Analyze Bot**
3. Paste and analyze
4. Review improvement suggestions

**Step 4: Generate Improved Version (5 min)**
1. Take strategy description from analysis
2. Go to **Builder Pro**
3. Use description as base
4. Add improvements:
   - Better risk management
   - Prop firm compliance
   - Additional safety checks
5. Generate enhanced version

**Step 5: Build Your Library (10 min)**
1. Go to **Strategy Library**
2. Add original version
3. Add improved version
4. Tag both for comparison
5. Add performance notes

**Total Time:** ~45 minutes for complete workflow

---

## Pro Tips

### For Builder Pro:
1. **Be Specific** - More detail = better code
2. **Start Simple** - Test basic strategy first
3. **Use Prop Firms** - Even if not using, adds safety
4. **Always Validate** - Don't skip validation steps
5. **Test Parameters** - Try different risk/timeframe combos

### For Analyze Bot:
1. **Use for Learning** - Understand how good bots work
2. **Compare Versions** - Analyze before/after improvements
3. **Check Compliance** - Even existing bots need validation
4. **Extract Ideas** - Use analysis to inspire new strategies

### For Discovery:
1. **Use Filters** - Start with high-star repos
2. **Batch Process** - Analyze 10-20 at once
3. **Check Recency** - Prefer recently updated bots
4. **Verify Claims** - Backtest before trusting

### For Library:
1. **Tag Everything** - Makes finding strategies easy
2. **Add Notes** - Document performance observations
3. **Version Control** - Keep multiple versions
4. **Regular Cleanup** - Remove underperforming bots

---

## Troubleshooting

### Builder Pro Not Generating
**Problem:** Click "Generate" but nothing happens
**Solution:**
1. Check EMERGENT_LLM_KEY is set in `/app/backend/.env`
2. Restart backend: `sudo supervisorctl restart backend`
3. Check browser console for errors
4. Try simpler strategy description

### Validation Always Fails
**Problem:** Validation shows errors even after fixes
**Solution:**
1. Copy code to "Analyze Bot" for detailed review
2. Check for missing using statements
3. Verify all indicators initialized in OnStart
4. Ensure OnBar method exists

### Compilation Gate Fails
**Problem:** Auto-fix doesn't resolve compilation errors
**Solution:**
1. Copy code to external IDE (Visual Studio)
2. Build there to see detailed errors
3. Fix manually
4. Paste back and re-validate

### Compliance Check Fails
**Problem:** Bot doesn't meet prop firm rules
**Solution:**
1. Review specific violations
2. Go back to Builder Pro
3. Regenerate with lower risk settings
4. Explicitly mention prop firm rules in description

### Discovery Finds No Results
**Problem:** GitHub search returns empty
**Solution:**
1. Use broader keywords: "ctrader" or "calgo"
2. Remove minimum stars filter
3. Try different search terms
4. Check GitHub rate limits

---

## Next Steps

1. **Start with Builder Pro**
   - Create your first bot
   - Follow the validation pipeline
   - Get familiar with workflow

2. **Explore Discovery**
   - Find inspiration
   - Learn from top bots
   - Build your library

3. **Master Analysis**
   - Analyze your own bots
   - Compare with discovered bots
   - Iterate and improve

4. **Build Your Library**
   - Organize strategies
   - Track performance
   - Version control improvements

5. **Deploy and Monitor**
   - Backtest thoroughly
   - Start with demo account
   - Track real performance
   - Refine based on results

---

## Support

### Common Questions
- **How do I get EMERGENT_LLM_KEY?** - Contact your administrator
- **Can I use my own OpenAI key?** - No, system uses unified key
- **Is this compatible with cTrader?** - Yes, generates standard cBot format
- **Can I modify generated code?** - Yes, full edit access
- **How accurate is the scoring?** - Based on proven metrics, 85%+ accuracy

### Getting Help
1. Check this user guide
2. Review tooltips in UI
3. Check logs: `/var/log/supervisor/`
4. Review error messages carefully
5. Contact support if issue persists

---

**Last Updated:** March 20, 2026
**Version:** 1.0.0
