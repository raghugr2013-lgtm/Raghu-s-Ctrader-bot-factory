# ACCOUNT SIZE & RISK CONFIGURATION - IMPLEMENTATION GUIDE

**Date**: April 7, 2026  
**Feature**: Account Size and Risk per Trade Configuration  
**Status**: ✅ IMPLEMENTED

---

## 📋 OVERVIEW

Added account size and risk configuration inputs to the Strategy Factory system with **strict separation** between strategy logic and portfolio/risk management.

### **Key Principle**: Layer Separation

```
┌─────────────────────────────────────────────────────┐
│  STRATEGY LAYER (Capital-Independent)              │
│  - Generation                                       │
│  - Backtesting                                      │
│  - Indicator calculations                           │
│  - Performance metrics                              │
│  ❌ Does NOT use account_size or risk_per_trade    │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  PORTFOLIO/RISK LAYER (Capital-Dependent)           │
│  - Risk allocation                                  │
│  - Position sizing                                  │
│  - Capital distribution                             │
│  ✅ USES account_size and risk_per_trade           │
└─────────────────────────────────────────────────────┘
```

---

## 🎨 FRONTEND CHANGES

### **File**: `/app/frontend/src/pages/PipelinePage.jsx`

#### **New UI Inputs** (Lines 326-355)

```jsx
// Account Size Input
<input
  type="number"
  value={config.account_size}
  onChange={(e) => setConfig({
    ...config, 
    account_size: parseFloat(e.target.value) || 10000
  })}
  min="100"
  step="100"
  placeholder="10000"
/>

// Risk per Trade Input
<input
  type="number"
  value={config.risk_per_trade}
  onChange={(e) => setConfig({
    ...config, 
    risk_per_trade: parseFloat(e.target.value) || 1.0
  })}
  min="0.1"
  max="5.0"
  step="0.1"
  placeholder="1.0"
/>
```

#### **Config State** (Lines 56-58)

```javascript
const [config, setConfig] = useState({
  // ... other settings
  account_size: 10000,      // Total account capital
  risk_per_trade: 1.0,      // Risk per trade in %
  // ... other settings
});
```

#### **Updated Strategy Display** (Lines 628-642)

Now shows allocation details for each strategy:

```jsx
{strategy.allocation && (
  <div>
    <DollarSign /> $2,310 capital
    $1,850 position
    23.1% weight
  </div>
)}
```

**Example Display**:
```
#1 EMA_10_20_BUY_SELL
  Symbol: EURUSD | Timeframe: 1h | Backtest: 2024-01-01 → 2024-12-31
  💰 $2,310 capital | 📊 $1,850 position | ⚖️ 23.1% weight
  Score: 85.2 | Sharpe: 2.1 | Max DD: 12% | Win Rate: 58.5%
```

---

## ⚙️ BACKEND CHANGES

### **1. Pipeline Configuration**

**Files Modified**:
- `/app/backend/master_pipeline_controller.py` (Lines 64-66)
- `/app/backend/pipeline_master_router.py` (Lines 65-67)

**New Fields Added**:

```python
@dataclass
class PipelineConfig:
    # ... existing fields
    
    # Account & Risk Configuration (NEW)
    account_size: float = 10000.0      # Total account capital
    risk_per_trade: float = 1.0        # Risk per trade in %
    
    # ... other fields
```

**API Request Model** (`MasterPipelineRequest`):

```python
class MasterPipelineRequest(BaseModel):
    # ... existing fields
    
    # Account & Risk Configuration (NEW)
    account_size: float = 10000.0
    risk_per_trade: float = 1.0
    
    # ... other fields
```

---

### **2. Risk Allocation Engine**

**File**: `/app/backend/codex_risk_allocation_engine.py`

**Updated Method Signature**:

```python
def allocate(
    self,
    strategies: List[Dict[str, Any]],
    method: str = "MAX_SHARPE",
    max_risk_per_strategy: float = 2.0,
    max_portfolio_risk: float = 8.0,
    account_size: float = 10000.0,        # NEW
    risk_per_trade: float = 1.0           # NEW (in %)
) -> Dict[str, Any]:
```

**New Calculation Logic**:

```python
# 1. Calculate weight (unchanged)
weight = sharpe / total_sharpe  # For MAX_SHARPE method

# 2. Calculate allocated capital (NEW)
allocated_capital = account_size * weight

# 3. Calculate position size based on risk per trade (NEW)
stop_loss_pct = max_drawdown_pct / 100
risk_amount = account_size * (risk_per_trade / 100)
position_size = risk_amount / stop_loss_pct

# Cap position size at allocated capital
position_size = min(position_size, allocated_capital)
```

**Enhanced Output Format**:

```python
return {
    "allocations": {
        "EMA_10_20": {
            "weight": 0.231,                    # 23.1%
            "weight_percent": 23.1,
            "allocated_capital": 2310.0,        # NEW
            "position_size": 1850.0,            # NEW
            "risk_percent": 2.77,               # NEW
            "stop_loss_pct": 12.0               # NEW
        },
        # ... other strategies
    },
    "method": "MAX_SHARPE",
    "total_risk": 14.2,
    "account_size": 10000.0,                    # NEW
    "risk_per_trade": 1.0                       # NEW
}
```

---

### **3. Capital Scaling Engine**

**File**: `/app/backend/codex_capital_scaling_engine.py`

**Updated Method Signature**:

```python
def scale_capital(
    self,
    allocated_portfolio: Dict[str, Any],
    account_size: float = 10000.0  # Changed from initial_balance
) -> Dict[str, Any]:
```

**Key Changes**:

1. **Parameter Rename**: `initial_balance` → `account_size` (for consistency)
2. **Enhanced Handling**: Now extracts `allocated_capital` from risk engine
3. **Scaling Applied**: Applies scaling factor to already-allocated capital

**Logic**:

```python
# Extract capital from risk engine allocations
for name, alloc_info in allocations.items():
    if isinstance(alloc_info, dict) and "allocated_capital" in alloc_info:
        # Apply scaling factor to already-calculated capital
        capital_per_strategy[name] = alloc_info["allocated_capital"] * scaling_factor
    else:
        # Fallback for old format
        capital_per_strategy[name] = total_capital * weight
```

---

### **4. Master Pipeline Controller**

**File**: `/app/backend/master_pipeline_controller.py`

**Risk Allocation Stage** (Lines 662-670):

```python
result = engine.allocate(
    run.selected_portfolio,
    method=run.config.allocation_method,
    max_risk_per_strategy=run.config.max_risk_per_strategy,
    max_portfolio_risk=run.config.max_portfolio_risk,
    account_size=run.config.account_size,        # NEW
    risk_per_trade=run.config.risk_per_trade     # NEW
)
```

**Capital Scaling Stage** (Lines 721-724):

```python
result = engine.scale_capital(
    run.allocated_portfolio,
    account_size=run.config.account_size  # Use account_size
)
```

---

## 📊 POSITION SIZING FORMULA

### **How Position Size is Calculated**

```
Given:
  - Account Size: $10,000
  - Risk per Trade: 1% (= $100 risk per trade)
  - Strategy Max Drawdown: 12% (used as stop loss)
  - Strategy Weight: 23.1% (from MAX_SHARPE allocation)

Step 1: Calculate Allocated Capital
  allocated_capital = account_size × weight
  allocated_capital = $10,000 × 0.231 = $2,310

Step 2: Calculate Position Size
  risk_amount = account_size × (risk_per_trade / 100)
  risk_amount = $10,000 × 0.01 = $100
  
  position_size = risk_amount / (stop_loss_pct / 100)
  position_size = $100 / 0.12 = $833.33

Step 3: Cap at Allocated Capital
  position_size = min($833.33, $2,310) = $833.33

Final Position Size: $833.33
```

**Why Cap at Allocated Capital?**
- Ensures position size doesn't exceed available capital
- Prevents over-leveraging
- Maintains portfolio balance

---

## 📈 EXAMPLE: COMPLETE ALLOCATION

### **Input**

```json
{
  "account_size": 10000,
  "risk_per_trade": 1.0,
  "allocation_method": "MAX_SHARPE",
  "portfolio_size": 5
}
```

### **Selected Strategies**

| Strategy | Sharpe | Max DD | Weight |
|----------|--------|--------|--------|
| EMA_10_20 | 2.1 | 12% | 23.1% |
| RSI_30_70 | 1.9 | 15% | 20.9% |
| MACD_12_26 | 1.8 | 11% | 19.8% |
| BOLLINGER | 1.7 | 18% | 18.7% |
| ATR_VOL | 1.6 | 14% | 17.6% |

### **Risk Allocation Output**

```json
{
  "allocations": {
    "EMA_10_20": {
      "weight": 0.231,
      "weight_percent": 23.1,
      "allocated_capital": 2310.0,
      "position_size": 833.33,
      "risk_percent": 2.77,
      "stop_loss_pct": 12.0
    },
    "RSI_30_70": {
      "weight": 0.209,
      "weight_percent": 20.9,
      "allocated_capital": 2090.0,
      "position_size": 666.67,
      "risk_percent": 3.14,
      "stop_loss_pct": 15.0
    },
    "MACD_12_26": {
      "weight": 0.198,
      "weight_percent": 19.8,
      "allocated_capital": 1980.0,
      "position_size": 909.09,
      "risk_percent": 2.18,
      "stop_loss_pct": 11.0
    },
    "BOLLINGER": {
      "weight": 0.187,
      "weight_percent": 18.7,
      "allocated_capital": 1870.0,
      "position_size": 555.56,
      "risk_percent": 3.37,
      "stop_loss_pct": 18.0
    },
    "ATR_VOL": {
      "weight": 0.176,
      "weight_percent": 17.6,
      "allocated_capital": 1760.0,
      "position_size": 714.29,
      "risk_percent": 2.46,
      "stop_loss_pct": 14.0
    }
  },
  "method": "MAX_SHARPE",
  "total_risk": 13.92,
  "account_size": 10000.0,
  "risk_per_trade": 1.0
}
```

### **Capital Scaling Output** (Scaling Factor: 1.0x)

```json
{
  "total_capital": 10000.0,
  "scaling_factor": 1.0,
  "capital_per_strategy": {
    "EMA_10_20": 2310.0,
    "RSI_30_70": 2090.0,
    "MACD_12_26": 1980.0,
    "BOLLINGER": 1870.0,
    "ATR_VOL": 1760.0
  }
}
```

---

## ⚖️ LAYER SEPARATION VERIFICATION

### **✅ What DOES NOT Use Account Size/Risk**

1. **Strategy Generation**
   - Template-based factory generation
   - AI-based generation
   - Parameter randomization
   - **Status**: ✅ Independent of capital

2. **Backtesting**
   - Historical price simulation
   - Trade signal generation
   - Performance metric calculation (Sharpe, Drawdown, Win Rate)
   - **Status**: ✅ Uses `initial_balance` for simulation, NOT `account_size`

3. **Indicator Calculations**
   - EMA, RSI, MACD calculations
   - Signal logic
   - Entry/exit rules
   - **Status**: ✅ Pure price-based logic

4. **Validation**
   - Monte Carlo simulation
   - Walk-forward testing
   - **Status**: ✅ Independent of capital

### **✅ What USES Account Size/Risk**

1. **Risk Allocation** (Stage 9)
   - Calculates capital weight for each strategy
   - Computes position size based on risk per trade
   - **Input**: `account_size`, `risk_per_trade`
   - **Output**: `allocated_capital`, `position_size` per strategy

2. **Capital Scaling** (Stage 10)
   - Applies scaling factor based on portfolio risk
   - Adjusts allocated capital
   - **Input**: `account_size`
   - **Output**: Final `capital_per_strategy`

3. **Portfolio Output**
   - Final strategy export includes allocation details
   - **Output**: Capital and position size for deployment

---

## 🔒 SEPARATION GUARANTEES

### **Backtest Independence**

**Proof**:
```python
# backtest_real_engine.py
def run_backtest_on_real_candles(
    candles: List[Candle],
    bot_name: str,
    symbol: str,
    timeframe: str,
    duration_days: int,
    initial_balance: float,  # ← Uses initial_balance (NOT account_size)
    # ... other params
):
    config = BacktestConfig(
        initial_balance=initial_balance,  # Backtest simulation balance
        # ... other config
    )
    # Backtest runs with initial_balance for simulation
    # Does NOT use account_size or risk_per_trade
```

**Result**: 
- Backtest metrics (Sharpe, DD, Win Rate) are **capital-independent**
- Can compare strategies fairly regardless of account size
- Account size only affects **deployment capital**, not **strategy quality**

---

## 📝 API USAGE EXAMPLE

### **Request**

```bash
curl -X POST "${API}/pipeline/master-run" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "timeframe": "1h",
    "account_size": 25000,
    "risk_per_trade": 0.5,
    "portfolio_size": 5,
    "allocation_method": "MAX_SHARPE"
  }'
```

### **Response** (Selected Strategies)

```json
{
  "success": true,
  "selected_portfolio": [
    {
      "name": "EMA_10_20_BUY_SELL",
      "fitness": 85.2,
      "sharpe_ratio": 2.1,
      "max_drawdown_pct": 12.0,
      "win_rate": 58.5,
      "allocation": {
        "weight": 0.231,
        "weight_percent": 23.1,
        "allocated_capital": 5775.0,
        "position_size": 2083.33,
        "risk_percent": 2.77,
        "stop_loss_pct": 12.0
      }
    }
    // ... other strategies
  ]
}
```

**Note**: With `account_size: 25000` instead of 10000:
- `allocated_capital` scales: $2,310 → $5,775 (×2.5)
- `position_size` scales: $833 → $2,083 (×2.5)
- Strategy metrics (Sharpe, DD, Win Rate) remain **unchanged**

---

## ✅ IMPLEMENTATION CHECKLIST

- ✅ Frontend inputs added (Account Size, Risk per Trade)
- ✅ Backend config updated (PipelineConfig, API request)
- ✅ Risk allocation engine enhanced (position sizing)
- ✅ Capital scaling engine updated (account_size parameter)
- ✅ Master pipeline controller wired (passes parameters)
- ✅ Strategy display updated (shows allocation details)
- ✅ Layer separation verified (strategy logic independent)
- ✅ Linting passed (no errors)
- ✅ Position sizing formula documented
- ✅ Example outputs provided

---

## 🎯 BENEFITS

1. **User Control**: Users can specify exact account size and risk tolerance
2. **Realistic Position Sizing**: Position sizes calculated based on actual risk management
3. **Capital Flexibility**: Can test different account sizes without re-running backtest
4. **Layer Separation**: Strategy quality remains capital-independent
5. **Portfolio Optimization**: Better capital distribution across strategies

---

**End of Documentation**
