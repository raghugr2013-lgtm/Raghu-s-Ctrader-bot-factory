# Bot Refinement Guide - How to Improve Generated Bots

## 📋 Understanding Pipeline Results

Each step in the pipeline (Safety → Validate → Compile → Compliance) provides feedback that helps you refine your bot.

---

## 🛡️ Safety Injection Step

### **What It Shows:**
After clicking "Inject Safety Rules", you'll see a list of changes applied.

### **Example Output:**
```
✓ 8 safety enhancement(s) injected

Changes Applied:
• Added default stop loss (25 pips)
• Added take profit target (2:1 risk-reward)
• Added risk management (1% per trade)
• Added daily loss limit (5% max)
• Added max drawdown protection (10%)
• Added spread filter (max 3 pips)
• Added trading session filter (8:00-17:00 UTC)
• Applied FTMO max risk limit: 1.0%
```

### **How to Refine:**

#### **If TOO MANY changes applied (7-8):**
**Problem:** Your original bot was missing critical safety features

**Solution:**
1. Add safety requirements to your initial prompt:
   ```
   BEFORE:
   "RSI bot. Buy when RSI < 30."
   
   AFTER:
   "RSI bot. Buy when RSI < 30. Include stop loss at 2x ATR,
   take profit at 2:1 risk-reward, max 1% risk per trade,
   daily loss limit 5%, spread filter max 2 pips."
   ```

2. Regenerate with better prompt
3. Safety injection will add fewer items

#### **If FEW changes applied (0-2):**
**Good:** Your bot already has most safety features

**Optional Refinement:**
- Review the changes that were added
- Decide if you want them or prefer manual control
- If you don't want them, regenerate without safety injection

#### **Specific Safety Parameters:**

**Stop Loss Too Large/Small:**
- Default: 25 pips
- Refinement: In your prompt, specify:
  ```
  "Use 15 pip stop loss" (tighter)
  "Use 50 pip stop loss" (wider)
  "Use 2x ATR stop loss" (dynamic)
  ```

**Take Profit Ratio:**
- Default: 2:1 risk-reward
- Refinement: Specify in prompt:
  ```
  "Take profit at 1.5:1 risk-reward" (conservative)
  "Take profit at 3:1 risk-reward" (aggressive)
  "Exit when RSI crosses 50" (strategy-based)
  ```

**Risk Per Trade:**
- Default: Uses your setting (1-2%)
- Refinement: Adjust in Builder Pro settings before generating

**Trading Hours:**
- Default: 8:00-17:00 UTC
- Refinement: In prompt:
  ```
  "Trade only during London session (8:00-16:00 UTC)"
  "Trade 24/7 except weekends"
  "Trade during high volume hours (7:00-20:00 UTC)"
  ```

---

## ✓ Validation Step

### **What It Shows:**
Code syntax errors, missing imports, logic issues, potential problems.

### **Common Issues & Fixes:**

#### **1. "No critical errors" ✅**
**Meaning:** Code is syntactically correct

**Next Steps:**
- Proceed to Compile step
- No refinement needed

---

#### **2. Missing Using Statements**
**Example Error:**
```
❌ Type 'Symbol' not found
⚠️ Consider adding: using cAlgo.API.Internals;
```

**How to Fix:**
**Option A - Manual:** Add to code:
```csharp
using System;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;  // ← Add this
```

**Option B - Regenerate:** Add to prompt:
```
"Ensure all required using statements are included"
```

---

#### **3. Undefined Variables**
**Example Error:**
```
❌ Variable 'stopLossPips' not defined
```

**How to Fix:**
**Manual Fix:**
```csharp
// Add parameter or constant
[Parameter("Stop Loss Pips", DefaultValue = 25)]
public double StopLossPips { get; set; }
```

**Regenerate:** In prompt:
```
"Define all parameters clearly including stop loss in pips"
```

---

#### **4. Logic Warnings**
**Example Warning:**
```
⚠️ Position may be opened multiple times per bar
⚠️ No validation for indicator null values
⚠️ Hard-coded risk percentage should be parameter
```

**How to Fix:**

**Multiple Positions Warning:**
```csharp
// BEFORE
if (rsi < 30)
    ExecuteMarketOrder(TradeType.Buy, ...);

// AFTER - Add check
if (rsi < 30 && Positions.Find("MyBot") == null)
    ExecuteMarketOrder(TradeType.Buy, ...);
```

**Null Value Validation:**
```csharp
// BEFORE
double rsiValue = _rsi.Result.LastValue;

// AFTER - Add null check
if (_rsi == null || _rsi.Result.LastValue == double.NaN)
    return;
double rsiValue = _rsi.Result.LastValue;
```

**Hard-coded Values:**
```csharp
// BEFORE
const double RiskPercent = 2.0;

// AFTER - Make it parameter
[Parameter("Risk %", DefaultValue = 2.0, MinValue = 0.1, MaxValue = 5.0)]
public double RiskPercent { get; set; }
```

---

## 🔨 Compilation Step

### **What It Shows:**
Whether code will actually compile in cTrader. Auto-fixes applied.

### **Common Issues & Fixes:**

#### **1. "Compile verified" + "2 auto-fixes applied" ✅**
**Meaning:** Code had minor issues but they were fixed automatically

**Example Fixes:**
```
✓ Compile verified
  2 auto-fixes applied

Fixes Applied:
- Added missing semicolon on line 45
- Fixed variable scope in OnBar method
```

**Next Steps:**
- Check the updated code
- Proceed to Compliance step
- No manual refinement needed

---

#### **2. Compilation Failed After 3 Attempts ❌**
**Example Error:**
```
❌ Compilation failed
Status: Failed after 3 auto-fix attempts

Errors:
❌ Cannot convert type 'double' to 'int' on line 67
❌ Method 'CalculateVolume' expects 1 argument but 0 provided
```

**How to Fix:**

**Type Conversion Error:**
```csharp
// BEFORE - Wrong
int period = 14.5;  // ❌ double to int

// AFTER - Fixed
int period = 14;  // ✅ Correct type
// OR
int period = (int)Math.Round(14.5);  // ✅ Explicit conversion
```

**Method Argument Error:**
```csharp
// BEFORE - Wrong
double volume = CalculateVolume();  // ❌ Missing argument

// AFTER - Fixed
double volume = CalculateVolume(stopLossPips);  // ✅ Argument provided
```

**Refinement Strategy:**
1. Copy error message
2. Manually fix in code editor
3. Click "Compile Gate" again
4. If still fails, regenerate with better prompt:
   ```
   "Generate RSI bot with proper type conversions and method signatures"
   ```

---

#### **3. API Deprecation Warnings**
**Example Warning:**
```
⚠️ 'MarketSeries' is deprecated, use 'Bars' instead
⚠️ 'Symbol.PipSize' should be 'Symbol.TickSize'
```

**How to Fix:**
```csharp
// BEFORE - Deprecated
_rsi = Indicators.RelativeStrengthIndex(MarketSeries.Close, 14);
double pipSize = Symbol.PipSize;

// AFTER - Updated
_rsi = Indicators.RelativeStrengthIndex(Bars.ClosePrices, 14);
double tickSize = Symbol.TickSize;
```

**Regenerate:** Add to prompt:
```
"Use latest cTrader API (Bars instead of MarketSeries)"
```

---

## 📋 Compliance Step

### **What It Shows:**
Violations of prop firm rules (FTMO, FundedNext, etc.)

### **Common Issues & Fixes:**

#### **1. "Fully compliant" ✅**
**Meaning:** Bot follows all prop firm rules

**Next Steps:**
- Copy code
- Deploy to cTrader
- Backtest
- Go live!

---

#### **2. Risk Per Trade Violation ❌**
**Example Error:**
```
❌ Not fully compliant

Violations:
🔴 [Critical] Risk per trade exceeds 1% limit (current: 2%)
```

**How to Fix:**

**Option A - Adjust Settings:**
1. Go back to settings
2. Change Risk: 2% → 1%
3. Regenerate bot

**Option B - Manual Fix:**
```csharp
// BEFORE
[Parameter("Risk %", DefaultValue = 2.0)]
public double RiskPercent { get; set; }

// AFTER
[Parameter("Risk %", DefaultValue = 1.0, MaxValue = 1.0)]  // ← Enforce limit
public double RiskPercent { get; set; }
```

---

#### **3. Missing Stop Loss ❌**
**Example Error:**
```
🔴 [Critical] Stop loss not implemented or not enforced
```

**How to Fix:**

**Manual Fix:**
```csharp
// BEFORE - No stop loss
ExecuteMarketOrder(TradeType.Buy, Symbol, volume, "MyBot");

// AFTER - With stop loss
ExecuteMarketOrder(TradeType.Buy, Symbol, volume, "MyBot", 
    StopLossPips, TakeProfitPips);
```

**Or use Safety Injection:**
1. Click "Inject Safety Rules"
2. Stop loss will be added automatically

---

#### **4. Daily Loss Tracking Missing ❌**
**Example Error:**
```
🟠 [High] Daily loss tracking not implemented
```

**How to Fix:**

**Manual Fix:**
```csharp
// Add fields
private double _dailyLoss;
private DateTime _lastDayCheck;
private const double MAX_DAILY_LOSS = 5.0; // FTMO limit

// In OnStart()
_dailyLoss = 0;
_lastDayCheck = Server.Time.Date;

// In OnBar()
if (Server.Time.Date != _lastDayCheck)
{
    _dailyLoss = 0;
    _lastDayCheck = Server.Time.Date;
}

if (_dailyLoss >= Account.Balance * (MAX_DAILY_LOSS / 100.0))
{
    Print("Daily loss limit reached");
    return;  // Stop trading
}

// In OnPositionClosed()
protected override void OnPositionClosed(PositionClosedEventArgs args)
{
    if (args.Position.NetProfit < 0)
        _dailyLoss += Math.Abs(args.Position.NetProfit);
}
```

**Or use Safety Injection:**
1. Click "Inject Safety Rules"
2. Daily loss tracking added automatically

---

#### **5. Max Drawdown Protection Missing ❌**
**Example Error:**
```
🟡 [Medium] Max drawdown protection not implemented
```

**How to Fix:**

**Manual Fix:**
```csharp
// Add fields
private double _peakBalance;
private const double MAX_DRAWDOWN = 10.0; // FTMO limit

// In OnStart()
_peakBalance = Account.Balance;

// In OnBar()
if (Account.Balance > _peakBalance)
    _peakBalance = Account.Balance;

double drawdown = (_peakBalance - Account.Balance) / _peakBalance * 100.0;
if (drawdown >= MAX_DRAWDOWN)
{
    Print($"Max drawdown reached: {drawdown}%");
    Stop();  // Halt bot
    return;
}
```

**Or use Safety Injection:** Automatically added

---

## 🔄 Complete Refinement Workflow

### **Scenario 1: Perfect Generation**
```
Generate → ✅ Success
  ↓
Inject Safety → ✅ 2 changes (minimal)
  ↓
Validate → ✅ No critical errors
  ↓
Compile → ✅ Verified (0 fixes)
  ↓
Compliance → ✅ Fully compliant
  ↓
DEPLOY! 🚀
```
**No refinement needed!**

---

### **Scenario 2: Minor Issues**
```
Generate → ✅ Success
  ↓
Inject Safety → ✅ 5 changes
  ↓
Validate → ⚠️ 2 warnings
  ↓
Manual: Review warnings, decide if important
  ↓
Compile → ✅ Verified (1 auto-fix)
  ↓
Compliance → ✅ Fully compliant
  ↓
DEPLOY! 🚀
```
**Minimal refinement - warnings are optional**

---

### **Scenario 3: Moderate Issues**
```
Generate → ✅ Success
  ↓
Inject Safety → ✅ 8 changes (many missing)
  ↓
Validate → ❌ 3 errors
  ↓
Manual: Fix errors in code editor
  ↓
Validate Again → ✅ Passed
  ↓
Compile → ❌ Failed (type error)
  ↓
Manual: Fix type conversion
  ↓
Compile Again → ✅ Verified
  ↓
Compliance → ⚠️ 1 medium violation
  ↓
Manual: Fix violation or accept risk
  ↓
DEPLOY or REFINE
```
**Moderate refinement - manual fixes needed**

---

### **Scenario 4: Major Issues - Regenerate**
```
Generate → ✅ Success
  ↓
Inject Safety → ✅ 8 changes (all missing)
  ↓
Validate → ❌ 5+ errors
  ↓
Compile → ❌ Failed after 3 attempts
  ↓
Compliance → ❌ Multiple critical violations
  ↓
DECISION: Don't fix manually, REGENERATE with better prompt
  ↓
New Prompt: More detailed, include safety requirements
  ↓
Generate Again → ✅ Much better
  ↓
Pipeline → ✅ All steps pass
  ↓
DEPLOY! 🚀
```
**Major refinement - start over with better prompt**

---

## 💡 Refinement Best Practices

### **1. Improve Your Prompt First**
**Instead of manual fixes, refine your initial description:**

**Bad Prompt:**
```
"RSI bot"
```

**Good Prompt:**
```
"RSI mean reversion bot for H1 timeframe.
Entry: Buy when RSI < 30, Sell when RSI > 70
Exit: Close when RSI crosses 50
Risk Management: 1% risk per trade, ATR-based stops (2x ATR)
Filters: Max spread 2 pips, trade only 8:00-17:00 UTC
Safety: Daily loss limit 5%, max drawdown 10%
FTMO compliant"
```

**Result:** Fewer validation/compile/compliance issues

---

### **2. Use Safety Injection Wisely**

**Always use it IF:**
- You forgot safety features in prompt
- You want standard protection quickly
- You're testing and want safe defaults

**Skip it IF:**
- Your prompt already includes comprehensive safety
- You want custom safety logic
- Safety injection changes your strategy too much

---

### **3. Iterate Strategically**

**Quick fixes (do in editor):**
- Adding missing semicolons
- Fixing typos
- Adding null checks
- Adjusting parameter defaults

**Major fixes (regenerate):**
- Complete logic rewrite
- Different strategy approach
- Multiple compilation errors
- Fundamental design issues

---

### **4. Use Competition Mode for Comparison**

**Strategy:**
1. Generate with Competition mode
2. Review both GPT-4o and Claude variants
3. Check which has fewer validation errors
4. Check which has better code structure
5. Select best one
6. Minor refinements only

**Benefits:**
- See different approaches
- Learn what works better
- Less manual refinement needed

---

### **5. Learn from Warnings**

**Don't ignore warnings - they teach you:**

**Example:**
```
⚠️ Hard-coded risk percentage should be parameter
```

**Lesson:** Next time, include in prompt:
```
"Make all values configurable as parameters"
```

**Result:** Future bots are better

---

## 🎯 Refinement Checklist

Before deploying, ensure:

### **Safety Checklist:**
- [ ] Stop loss implemented
- [ ] Take profit or exit strategy defined
- [ ] Risk per trade ≤ 1-2%
- [ ] Daily loss limit enabled
- [ ] Max drawdown protection enabled
- [ ] Spread filter active
- [ ] Trading hours defined (optional)

### **Code Quality Checklist:**
- [ ] No critical validation errors
- [ ] Compiles successfully
- [ ] No type conversion errors
- [ ] All indicators initialized in OnStart
- [ ] Null checks for indicator values
- [ ] Position tracking prevents duplicates
- [ ] All variables properly scoped

### **Compliance Checklist (if using prop firm):**
- [ ] Risk per trade within limit
- [ ] Daily loss tracking implemented
- [ ] Max drawdown monitoring active
- [ ] Stop loss always used
- [ ] Max positions limit enforced
- [ ] No prohibited strategies (martingale, grid, hedging)

### **Logic Checklist:**
- [ ] Entry conditions clear and correct
- [ ] Exit conditions defined
- [ ] Position management included
- [ ] Error handling present
- [ ] Edge cases covered (weekend, high spread, etc.)

---

## 🔧 Quick Fix Reference

| Issue | Quick Fix |
|-------|-----------|
| Missing stop loss | Click "Inject Safety" |
| Type error | Cast explicitly: `(int)value` |
| Undefined variable | Add parameter or field |
| Multiple positions | Add: `if (Positions.Find(...) == null)` |
| Null indicator | Add: `if (_rsi == null) return;` |
| Deprecated API | Replace `MarketSeries` with `Bars` |
| Risk too high | Lower in settings, regenerate |
| Hard-coded value | Convert to `[Parameter]` |
| Missing using | Add: `using cAlgo.API.Internals;` |
| Compliance fail | Click "Inject Safety" first |

---

## 📚 Advanced Refinement Techniques

### **1. Combine Multiple Bots**
**Use Collaboration mode + manual merge:**
1. Generate with Collaboration mode
2. Get 2 variants
3. Manually combine best parts of each
4. Validate and compile merged version

### **2. Iterative Improvement**
**Progressive refinement:**
```
Round 1: Basic strategy → Test → Note issues
Round 2: Add filters → Test → Note issues
Round 3: Add safety → Test → Deploy
```

### **3. A/B Testing Approach**
**Generate variations:**
1. Version A: Conservative (tight stops, low risk)
2. Version B: Aggressive (wide stops, higher risk)
3. Backtest both
4. Choose best performer
5. Refine winner

---

## 🎓 Learning from Logs

**Check logs for patterns:**
```bash
# Backend logs
tail -f /var/log/supervisor/backend.err.log

# Look for:
- Repeated validation errors → Improve prompt
- Same compile error → Learn the fix
- Common compliance issue → Add to default prompt
```

---

## 📞 When to Ask for Help

**Regenerate if:**
- 5+ validation errors
- 3+ compilation attempts failed
- Multiple critical compliance violations
- Code logic fundamentally wrong

**Manual fix if:**
- 1-2 minor errors
- Simple type conversions
- Parameter adjustments
- Adding null checks

**Ask community/support if:**
- Stuck after 3 regeneration attempts
- Unclear error messages
- Platform-specific cTrader issues
- Advanced strategy logic questions

---

**Remember: The goal is production-ready bots, not perfect first attempts. Iteration is normal and expected!**
