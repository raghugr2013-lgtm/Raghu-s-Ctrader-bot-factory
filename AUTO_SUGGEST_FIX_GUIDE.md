# Auto Suggest Fix Feature - Testing Guide

## ✨ New Feature: Auto Suggest Fix

Automatically detect and fix common code issues with one click.

---

## 🎯 What It Does

**Auto Suggest Fix analyzes your code after validation or compilation and provides:**
1. **Detection** - Identifies common issues
2. **Suggestions** - Shows what needs fixing
3. **One-Click Fixes** - Apply fixes instantly
4. **Batch Fixes** - Fix all issues at once

---

## 🔍 What Gets Detected

### **1. Missing Stop Loss** 🛡️
**Detection:** ExecuteMarketOrder without stop loss parameter
**Fix:** Adds StopLossPips parameter and updates all order calls

### **2. Missing Take Profit** 🎯
**Detection:** ExecuteMarketOrder without take profit
**Fix:** Adds TakeProfitPips parameter (2:1 risk-reward)

### **3. Missing Using Statements** 📚
**Detection:** Types not found errors
**Fix:** Adds required namespaces (cAlgo.API.Internals, etc.)

### **4. Type Conversion Issues** 🔄
**Detection:** Cannot convert double to int errors
**Fix:** Adds explicit type casts

### **5. Missing Null Checks** ⚠️
**Detection:** Indicators used without null validation
**Fix:** Adds null checks for _rsi, _macd, _ema

### **6. Multiple Position Issues** 🔁
**Detection:** No check before opening positions
**Fix:** Adds position count validation

### **7. Hard-coded Values** 📝
**Detection:** Magic numbers in code (RSI 30/70, etc.)
**Fix:** Suggests converting to parameters (manual)

### **8. Deprecated API** ⏰
**Detection:** MarketSeries, Symbol.PipSize usage
**Fix:** Updates to Bars, Symbol.TickSize

---

## 🧪 How to Test

### **Test 1: Missing Stop Loss Detection**

**Steps:**
1. Go to Builder Pro
2. Generate bot with prompt:
   ```
   "RSI bot without stop loss"
   ```
3. Click "Run Validation"
4. Wait 2 seconds after validation completes

**Expected:**
- ✅ "Suggested Fixes" section appears
- ✅ Shows: "Add Stop Loss Parameter"
- ✅ Severity: Critical
- ✅ Fix Type: Risk (🛡️)
- ✅ "Apply Fix" button enabled

**Apply Fix:**
1. Click "Apply Fix"
2. Code updates in editor
3. Toast: "Fix 'add-stop-loss' applied successfully"
4. Suggestion disappears from list

**Verify:**
- Search code for `StopLossPips` - should exist
- Search for `ExecuteMarketOrder` - should have stop loss parameter

---

### **Test 2: Multiple Issues + Auto Fix All**

**Steps:**
1. Generate bot with minimal prompt:
   ```
   "Simple bot"
   ```
2. Click "Run Validation"
3. Wait for suggestions

**Expected:**
- ✅ Multiple suggestions appear (3-6)
- ✅ Each shows:
  - Title
  - Description
  - Severity badge
  - Fix type icon
  - "Apply Fix" button (if auto-fixable)
- ✅ "Auto Fix All (X)" button at bottom

**Apply All Fixes:**
1. Click "Auto Fix All"
2. Wait 1-2 seconds
3. Toast: "Applied X fix(es) successfully"
4. All suggestions disappear
5. Code updates with all fixes

**Verify:**
- Code has stop loss ✅
- Code has take profit ✅
- Code has null checks ✅
- Code has using statements ✅

---

### **Test 3: Compilation Errors Trigger**

**Steps:**
1. Generate a bot
2. Manually break the code:
   - Change `int period = 14;` to `int period = 14.5;`
3. Click "Compile Gate"
4. Wait for compilation to fail

**Expected:**
- ✅ Compile status: Failed
- ✅ "Suggested Fixes" appears automatically
- ✅ Shows: "Fix Type Conversion"
- ✅ Fix Type: Syntax (🔧)

**Apply Fix:**
1. Click "Apply Fix"
2. Code updates: `int period = (int)14.5;`
3. Click "Compile Gate" again
4. Compilation succeeds ✅

---

### **Test 4: Validation Warnings Trigger**

**Steps:**
1. Generate bot
2. Click "Run Validation"
3. If warnings exist, suggestions trigger

**Expected:**
- ✅ Even with warnings (not just errors), suggestions appear
- ✅ Shows medium/low severity issues
- ✅ Can apply fixes for warnings

---

### **Test 5: Manual Fix Required**

**Steps:**
1. Generate bot with hard-coded values:
   ```
   "RSI bot. Buy at 30, sell at 70"
   ```
2. Run validation
3. Check suggestions

**Expected:**
- ✅ Suggestion: "Convert Hard-coded Values to Parameters"
- ✅ Severity: Low
- ✅ auto_fixable: false
- ✅ Shows: "Manual fix required - review code manually"
- ✅ No "Apply Fix" button
- ✅ Not included in "Auto Fix All"

---

### **Test 6: Deprecated API Update**

**Steps:**
1. Generate bot
2. Manually add deprecated code:
   ```csharp
   var close = MarketSeries.Close;
   var pip = Symbol.PipSize;
   ```
3. Run validation

**Expected:**
- ✅ Suggestion: "Update Deprecated API Calls"
- ✅ Description mentions MarketSeries → Bars
- ✅ Fix Type: Syntax

**Apply Fix:**
1. Click "Apply Fix"
2. Code updates:
   ```csharp
   var close = Bars.ClosePrices;
   var pip = Symbol.TickSize;
   ```

---

### **Test 7: Hide/Show Suggestions**

**Steps:**
1. Generate bot with issues
2. Run validation
3. Suggestions appear

**Actions:**
- Click "Hide" button (top right)
- ✅ Suggestions panel disappears
- ✅ Panel stays hidden until next validation/compile

---

### **Test 8: Apply Fix Updates Code Editor**

**Steps:**
1. Get suggestions
2. Scroll to see current code
3. Click "Apply Fix"

**Expected:**
- ✅ Code editor updates immediately
- ✅ Can see the changes in textarea
- ✅ Changes persist
- ✅ Can continue editing

---

### **Test 9: Sequential Fix Application**

**Steps:**
1. Get 3-4 suggestions
2. Apply fixes one by one

**Expected:**
- ✅ First fix applies → suggestion disappears
- ✅ Second fix applies → suggestion disappears
- ✅ After all applied → panel auto-hides
- ✅ Each fix shows toast notification

---

### **Test 10: Integration with Full Pipeline**

**Complete Flow:**
1. Generate bot
2. Inject Safety ✅
3. Run Validation → Issues found
4. Suggestions appear automatically
5. Apply All Fixes
6. Run Validation again → Success ✅
7. Run Compile → Success ✅
8. Check Compliance → Success ✅
9. Deploy ✅

---

## 🎨 UI Elements

### **Suggested Fixes Panel**
- **Location:** Between "Inject Safety" and "Validate/Compile/Compliance"
- **Border:** Cyan glow (border-cyan-500/40)
- **Header:**
  - 💡 Icon
  - "Suggested Fixes (X)" title
  - "Hide" button

### **Fix Suggestion Card**
- **Border Color by Severity:**
  - Critical: Red (border-red-500/40)
  - High: Orange (border-orange-500/40)
  - Medium: Yellow (border-yellow-500/40)
  - Low: Blue (border-blue-500/40)

- **Icon by Type:**
  - Risk: 🛡️
  - Syntax: 🔧
  - Logic: 💡

- **Content:**
  - Title (bold)
  - Description (gray)
  - Severity badge (colored)
  - "Apply Fix" button (if auto-fixable)

### **Auto Fix All Button**
- **Appearance:** Gradient cyan to blue
- **Text:** "Auto Fix All (X)" where X = auto-fixable count
- **Position:** Bottom of suggestions panel
- **Only shows:** If 2+ auto-fixable suggestions exist

---

## 📊 Backend Endpoints

### **1. POST /api/code/suggest-fixes**

**Request:**
```json
{
  "code": "string",
  "validation_errors": ["error1", "error2"],
  "compile_errors": ["error1"]
}
```

**Response:**
```json
{
  "success": true,
  "suggestions": [
    {
      "id": "add-stop-loss",
      "title": "Add Stop Loss Parameter",
      "description": "ExecuteMarketOrder calls missing stop loss...",
      "fix_type": "risk",
      "severity": "critical",
      "auto_fixable": true,
      "code_patch": "...updated code..."
    }
  ],
  "total_count": 5,
  "auto_fixable_count": 4
}
```

### **2. POST /api/code/apply-fix**

**Request:**
```json
{
  "code": "string",
  "fix_id": "add-stop-loss",
  "code_patch": "...patched code..."
}
```

**Response:**
```json
{
  "success": true,
  "code": "...updated code...",
  "message": "Fix 'add-stop-loss' applied successfully"
}
```

### **3. POST /api/code/apply-all-fixes**

**Request:**
```json
{
  "code": "string",
  "suggestions": [/* array of suggestions */]
}
```

**Response:**
```json
{
  "success": true,
  "code": "...fully fixed code...",
  "applied_fixes": ["add-stop-loss", "add-take-profit", ...],
  "count": 4,
  "message": "Applied 4 fix(es) successfully"
}
```

---

## 🔧 Backend Testing (curl)

### **Test Suggest Fixes:**
```bash
curl -X POST http://localhost:8001/api/code/suggest-fixes \
  -H "Content-Type: application/json" \
  -d '{
    "code": "ExecuteMarketOrder(TradeType.Buy, Symbol, 1000, \"test\");",
    "validation_errors": [],
    "compile_errors": []
  }' | jq '.suggestions[].title'
```

**Expected Output:**
```
"Add Stop Loss Parameter"
"Add Take Profit Parameter"
```

### **Test Apply Fix:**
```bash
curl -X POST http://localhost:8001/api/code/apply-fix \
  -H "Content-Type: application/json" \
  -d '{
    "code": "...",
    "fix_id": "add-stop-loss",
    "code_patch": "..."
  }' | jq '.success'
```

**Expected:** `true`

---

## ✅ Feature Checklist

Before marking complete, verify:

### **Detection:**
- [ ] Detects missing stop loss
- [ ] Detects missing take profit
- [ ] Detects missing using statements
- [ ] Detects type conversion issues
- [ ] Detects missing null checks
- [ ] Detects multiple position issues
- [ ] Detects hard-coded values
- [ ] Detects deprecated API

### **UI:**
- [ ] Suggestions appear automatically after validation/compile errors
- [ ] Suggestions panel has cyan border
- [ ] Each suggestion shows icon, title, description, severity
- [ ] "Apply Fix" button works for auto-fixable
- [ ] "Auto Fix All" button appears when 2+ auto-fixable
- [ ] "Hide" button works
- [ ] Code editor updates after applying fix
- [ ] Toasts show for success/error

### **Behavior:**
- [ ] Triggers after validation errors
- [ ] Triggers after validation warnings
- [ ] Triggers after compilation errors
- [ ] Doesn't trigger on success (no errors/warnings)
- [ ] Can apply fixes sequentially
- [ ] Can apply all fixes at once
- [ ] Panel auto-hides when all fixes applied
- [ ] Applied fixes disappear from list

### **Integration:**
- [ ] Works with Single AI mode
- [ ] Works with Collaboration mode
- [ ] Works with Competition mode
- [ ] Doesn't break existing validation
- [ ] Doesn't break existing compilation
- [ ] Doesn't break compliance checking

---

## 🎓 User Instructions

### **How to Use Auto Suggest Fix:**

1. **Generate Your Bot**
   - Use any AI mode
   - Describe your strategy

2. **Run Validation or Compile**
   - Click "Run Validation" or "Compile Gate"
   - If errors/warnings found, suggestions appear automatically

3. **Review Suggestions**
   - Read each suggestion title and description
   - Check severity (critical issues first)
   - See if it's auto-fixable

4. **Apply Fixes**
   - **Individual:** Click "Apply Fix" on each suggestion
   - **Batch:** Click "Auto Fix All" to fix everything at once

5. **Verify and Continue**
   - Check updated code
   - Run validation/compile again
   - Continue with pipeline (Compliance → Deploy)

---

## 💡 Tips

1. **Always review fixes** - Check code after applying to understand changes
2. **Manual fixes** - Some suggestions require manual review (hard-coded values)
3. **Critical first** - Apply critical severity issues before low priority
4. **Re-validate** - After applying fixes, run validation again to confirm
5. **Learn patterns** - Repeated suggestions indicate patterns to avoid in prompts

---

## 🐛 Known Limitations

1. **Pattern-based** - Uses regex, not full AST parsing (may miss edge cases)
2. **Context-limited** - Doesn't understand full business logic
3. **Order matters** - Apply fixes in order suggested for best results
4. **Manual review** - Always review critical fixes before deployment

---

## 📈 Next Enhancements (Future)

- AI-powered fix suggestions (not just pattern-based)
- Preview before applying (show diff)
- Undo last fix
- Save/load fix preferences
- Custom fix rules
- Fix suggestion learning from user choices

---

**Feature Status: ✅ READY FOR TESTING**

Test at: `/builder-pro`
