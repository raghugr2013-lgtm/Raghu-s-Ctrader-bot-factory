# 🏗️ UNIFIED PIPELINE ARCHITECTURE

## System Design: Single Strategy Lifecycle

**Version**: 1.0  
**Date**: March 29, 2026  
**Status**: Core Implementation Complete

---

## 🎯 DESIGN PRINCIPLE

**ONE PIPELINE FOR ALL STRATEGIES**

No matter how a strategy enters the system, it goes through the same rigorous process:

```
Entry Point → Unified Pipeline → Live Trading
```

---

## 📥 ENTRY POINTS (3 Ways In)

### 1. **AI Bot Generation** (Backtest Page)
- **What**: Generate new strategies using AI (GPT-5.2, Claude 4.5, DeepSeek)
- **Input**: User configuration (strategy type, timeframe, asset)
- **Output**: C# cBot code
- **Entry**: `/api/multi-ai/generate`

### 2. **Existing Bot Analysis** (Analyzer Page)
- **What**: Analyze and validate existing cBot code
- **Input**: User-provided C# code
- **Output**: Validated and improved code
- **Entry**: `/api/analyze/validate`

### 3. **Discovery from GitHub** (Discovery Page)
- **What**: Import strategies from GitHub repositories
- **Input**: GitHub URL or search query
- **Output**: Imported cBot code
- **Entry**: `/api/discovery/import`

---

## 🔄 UNIFIED PIPELINE (10 Stages)

All strategies go through the SAME process:

### **Stage 1: Inject Safety** ⚙️
**Purpose**: Add risk controls to strategy code

**Adds**:
- Stop loss logic
- Position sizing rules
- Max drawdown limits
- Daily loss limits
- Risk guardian integration

**Output**: Safety-enhanced code

**Validation**: Code compiles with safety features

---

### **Stage 2: Validate** ✅
**Purpose**: Ensure code quality and compliance

**Checks**:
- ✓ C# syntax correctness
- ✓ cTrader API compliance
- ✓ Compilation success
- ✓ Risk controls present
- ✓ Prop firm rules (if applicable)

**Output**: Validation report

**Pass Criteria**: All checks pass

---

### **Stage 3: Backtest** 📊
**Purpose**: Test on historical data

**Data Source**: Dukascopy (tick data)  
**Period**: 2-3 years historical data  
**Metrics Calculated**:
- Total return (%)
- Sharpe ratio
- Maximum drawdown (%)
- Win rate (%)
- Profit factor
- Total trades

**Output**: Backtest performance report

**Pass Criteria**: 
- Return > 10%
- Sharpe > 1.0
- Drawdown < 20%
- Win rate > 50%

---

### **Stage 4: Monte Carlo** 🎲
**Purpose**: Test robustness across random scenarios

**Simulations**: 1,000 randomized runs  
**Method**: Resample trades with replacement  
**Metrics Calculated**:
- 95% confidence interval
- Worst-case scenario
- Best-case scenario
- Probability of profit

**Output**: Monte Carlo distribution

**Pass Criteria**: 
- 95% confidence > 5%
- Worst-case > -10%

---

### **Stage 5: Forward Test** ➡️
**Purpose**: Validate on out-of-sample data

**Method**: Walk-forward analysis  
**Windows**: 12 optimization periods  
**Metrics Calculated**:
- Forward return (%)
- Forward Sharpe ratio
- Consistency score
- Degradation from backtest

**Output**: Forward test report

**Pass Criteria**:
- Forward return > 5%
- Degradation < 30%

---

### **Stage 6: Score & Metrics** 🏆
**Purpose**: Calculate overall performance score

**Scoring Formula**:
```
Overall Score = 
  Backtest Performance (30%) +
  Monte Carlo Robustness (20%) +
  Forward Test Consistency (30%) +
  Risk-Adjusted Returns (20%)
```

**Components**:
- **Backtest**: Return × 0.4 + Sharpe × 10 × 0.3 + (100 - Drawdown) × 0.3
- **Monte Carlo**: Confidence95 × 0.6 + |WorstCase| × 0.4
- **Forward**: Return × 0.5 + Sharpe × 10 × 0.3 + Consistency × 20 × 0.2
- **Risk**: ProfitFactor × 10

**Output**: Score 0-100

**Rankings**:
- 90-100: Excellent
- 80-89: Very Good
- 70-79: Good
- 60-69: Acceptable
- <60: Poor (not deployed)

---

### **Stage 7: Store in Library** 💾
**Purpose**: Save strategy to permanent database

**Database**: MongoDB collection `strategies`  
**Stored Data**:
- Strategy code
- All metrics
- Test results
- Entry point
- Creation date
- Author/version

**Output**: Strategy ID in library

**Searchable By**:
- Score
- Return
- Sharpe ratio
- Entry point
- Date

---

### **Stage 8: Select Best** 🥇
**Purpose**: Rank against existing strategies

**Selection Criteria**:
1. Overall score (primary)
2. Sharpe ratio (tie-breaker)
3. Forward consistency (stability)

**Ranking**:
- All strategies ranked 1-N
- Rank #1 = Best strategy
- Only Rank #1 deploys automatically

**Output**: Strategy rank

**Decision**:
- Rank #1: Deploy to live
- Rank #2-10: Store in library
- Rank >10: Archive

---

### **Stage 9: Deploy to Live** 🚀
**Purpose**: Activate strategy in paper trading

**Deployment Process**:
1. Stop current live strategy (if any)
2. Load new strategy code
3. Initialize risk guardian
4. Start paper trading with $10,000
5. Begin monitoring

**Validation**:
- Strategy compiles in live environment
- Risk controls active
- Data feed connected
- First trade executes correctly

**Output**: Deployment ID

**Rollback**: Previous strategy stored for 24h

---

### **Stage 10: Monitor Performance** 📈
**Purpose**: Track live performance continuously

**Monitoring**:
- Real-time equity tracking
- Drawdown monitoring
- Trade execution logging
- Risk guardian status
- Performance vs expectations

**Alerts**:
- Drawdown > 10% (warning)
- Drawdown > 15% (auto-stop)
- Daily loss > 2% (pause)
- No trades for 3 days (investigate)

**Output**: Live performance dashboard

**Feedback Loop**: Live data feeds back to scoring model

---

## 📊 DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────┐
│         ENTRY POINTS (Choose One)           │
├─────────────────────────────────────────────┤
│  [AI Generation]  [Analyzer]  [Discovery]   │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│          UNIFIED PIPELINE (Same for All)     │
├─────────────────────────────────────────────┤
│  1. Inject Safety      ⚙️                   │
│  2. Validate          ✅                   │
│  3. Backtest          📊                   │
│  4. Monte Carlo       🎲                   │
│  5. Forward Test      ➡️                   │
│  6. Score & Metrics   🏆                   │
│  7. Store in Library  💾                   │
│  8. Select Best       🥇                   │
│  9. Deploy to Live    🚀 (if #1)           │
│  10. Monitor          📈 (if deployed)      │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│         OUTCOMES (3 Possibilities)           │
├─────────────────────────────────────────────┤
│  🚀 Deployed (Rank #1, Score ≥70)           │
│  💾 Stored (Rank #2-10, Score ≥60)          │
│  ❌ Rejected (Score <60)                    │
└─────────────────────────────────────────────┘
```

---

## 🔌 API ENDPOINTS

### **Submit Strategy**
```http
POST /api/pipeline/submit
{
  "name": "EMA Crossover v2",
  "code": "using cAlgo.API; ...",
  "entry_point": "ai_generation",  // or "analyzer" or "discovery"
  "description": "10/150 EMA crossover with ATR stop",
  "metadata": {}
}

Response:
{
  "id": "uuid",
  "name": "EMA Crossover v2",
  "current_stage": "received",
  "logs": ["Strategy received via ai_generation"]
}
```

### **Get Strategy Status**
```http
GET /api/pipeline/strategy/{strategy_id}

Response:
{
  "id": "uuid",
  "name": "EMA Crossover v2",
  "current_stage": "backtesting",
  "safety_injected": true,
  "validated": true,
  "backtest_completed": false,
  "overall_score": null,
  "logs": [
    "Strategy received",
    "✓ Safety injected",
    "✓ Validation passed",
    "Running backtest..."
  ]
}
```

### **Get All Strategies**
```http
GET /api/pipeline/strategies

Response: [
  {
    "id": "uuid1",
    "name": "EMA Crossover v2",
    "current_stage": "completed",
    "overall_score": 85.5,
    "rank": 1,
    "deployed": true
  },
  {
    "id": "uuid2",
    "name": "RSI Mean Reversion",
    "current_stage": "forward_test",
    "overall_score": null,
    "deployed": false
  }
]
```

### **Get Strategy Library**
```http
GET /api/pipeline/library?sort_by=score&limit=10

Response: [
  {
    "id": "uuid1",
    "name": "EMA Crossover v2",
    "entry_point": "ai_generation",
    "overall_score": 85.5,
    "rank": 1,
    "total_return": 18.5,
    "sharpe_ratio": 2.1,
    "max_drawdown": 7.2,
    "win_rate": 65.0,
    "deployed": true,
    "created_at": "2026-03-29T10:00:00Z"
  }
]
```

### **Get Deployed Strategy**
```http
GET /api/pipeline/deployed

Response:
{
  "id": "uuid1",
  "name": "EMA Crossover v2",
  "deployed": true,
  "deployment_id": "deploy-uuid",
  "overall_score": 85.5
}
```

### **Get Best Strategy**
```http
GET /api/pipeline/best

Response:
{
  "id": "uuid1",
  "name": "EMA Crossover v2",
  "overall_score": 85.5,
  "total_return": 18.5,
  "sharpe_ratio": 2.1
}
```

### **Get Pipeline Stats**
```http
GET /api/pipeline/stats

Response:
{
  "total_strategies": 25,
  "by_stage": {
    "completed": 15,
    "backtesting": 3,
    "validation": 2,
    "failed": 5
  },
  "by_entry_point": {
    "ai_generation": 12,
    "analyzer": 8,
    "discovery": 5
  },
  "completed": 15,
  "deployed": 1,
  "average_score": 72.5,
  "average_return": 14.2,
  "average_sharpe": 1.6
}
```

---

## 💾 DATABASE SCHEMA

### **MongoDB Collection: `strategies`**

```javascript
{
  "_id": ObjectId,
  "id": "uuid",
  "name": "EMA Crossover v2",
  "code": "using cAlgo.API; ...",
  "entry_point": "ai_generation",
  "description": "10/150 EMA crossover",
  "author": "System",
  "version": "1.0.0",
  
  // Pipeline state
  "current_stage": "completed",
  "created_at": ISODate,
  "updated_at": ISODate,
  
  // Progress flags
  "safety_injected": true,
  "validated": true,
  "backtest_completed": true,
  "monte_carlo_completed": true,
  "forward_test_completed": true,
  
  // Metrics
  "metrics": {
    "total_return": 18.5,
    "sharpe_ratio": 2.1,
    "max_drawdown": 7.2,
    "win_rate": 65.0,
    "profit_factor": 2.3,
    "total_trades": 180,
    "mc_confidence_95": 15.0,
    "mc_worst_case": -3.5,
    "mc_best_case": 42.0,
    "forward_return": 12.0,
    "forward_sharpe": 1.8,
    "forward_consistency": 0.88,
    "overall_score": 85.5,
    "rank": 1
  },
  
  // Deployment
  "deployed": true,
  "deployment_id": "deploy-uuid",
  "deployed_at": ISODate,
  
  // Logs
  "errors": [],
  "warnings": [],
  "logs": [
    "Strategy received",
    "✓ Safety injected",
    "✓ Validation passed",
    ...
  ]
}
```

---

## 🎯 IMPLEMENTATION STATUS

### ✅ **Phase 1: Core Pipeline** (COMPLETED)
- [x] Unified pipeline class
- [x] 10 pipeline stages defined
- [x] Entry point abstraction
- [x] Strategy data model
- [x] Pipeline orchestrator
- [x] Error handling
- [x] Logging system

### ✅ **Phase 2: API Layer** (COMPLETED)
- [x] Pipeline router
- [x] Submit strategy endpoint
- [x] Get status endpoint
- [x] Library endpoints
- [x] Deployment endpoints
- [x] Statistics endpoint

### ⏳ **Phase 3: Integration** (IN PROGRESS)
- [ ] Connect to existing validator
- [ ] Connect to backtest engine
- [ ] Connect to Monte Carlo module
- [ ] Connect to walk-forward analyzer
- [ ] Connect to paper trading engine
- [ ] Database persistence

### ⏳ **Phase 4: UI Integration** (PENDING)
- [ ] Pipeline progress indicator
- [ ] Strategy library page
- [ ] Deployed strategy dashboard
- [ ] Performance comparison charts
- [ ] Entry point integration

### ⏳ **Phase 5: Advanced Features** (PENDING)
- [ ] Multi-strategy deployment
- [ ] Portfolio optimization
- [ ] Strategy ensemble
- [ ] A/B testing
- [ ] Auto-rebalancing

---

## 🚧 NEXT STEPS

### **Immediate (This Week)**
1. ✅ Create unified pipeline module
2. ✅ Create API router
3. ✅ Integrate with server
4. ⏳ Connect to existing modules:
   - Validator (from analyzer)
   - Backtest engine
   - Risk calculator
   - Paper trading engine

### **Short-term (Next 2 Weeks)**
5. ⏳ Build UI components:
   - Pipeline progress tracker
   - Strategy library table
   - Performance comparison
6. ⏳ Implement database persistence
7. ⏳ Add real Monte Carlo simulation
8. ⏳ Add real walk-forward testing

### **Medium-term (Next Month)**
9. ⏳ Multi-strategy support
10. ⏳ Auto-deployment logic
11. ⏳ Performance monitoring
12. ⏳ Alert system integration

---

## 📝 USAGE EXAMPLES

### **Example 1: AI-Generated Strategy**

```python
# User generates strategy via AI
ai_code = generate_with_gpt("EMA crossover strategy")

# Submit to pipeline
response = await submit_strategy(
    name="AI EMA Strategy",
    code=ai_code,
    entry_point="ai_generation"
)

# Pipeline automatically:
# 1. Injects safety
# 2. Validates
# 3. Backtests
# 4. Runs Monte Carlo
# 5. Forward tests
# 6. Scores
# 7. Stores in library
# 8. Ranks
# 9. Deploys if #1
# 10. Monitors
```

### **Example 2: Analyzed Existing Strategy**

```python
# User pastes existing code
existing_code = load_from_file("my_strategy.cs")

# Submit to pipeline
response = await submit_strategy(
    name="My Existing Strategy",
    code=existing_code,
    entry_point="analyzer"
)

# Same pipeline process
# Result: Validated, tested, and potentially deployed
```

### **Example 3: Discovered GitHub Strategy**

```python
# User imports from GitHub
github_code = discover_from_github("https://github.com/...")

# Submit to pipeline
response = await submit_strategy(
    name="GitHub Discovery",
    code=github_code,
    entry_point="discovery"
)

# Same pipeline process
# Result: Community strategy tested and ranked
```

---

## ✅ BENEFITS OF UNIFIED PIPELINE

### **1. Consistency**
- All strategies validated the same way
- No shortcuts or bypasses
- Quality guaranteed

### **2. Fairness**
- AI, manual, and discovered strategies compete equally
- Best strategy wins based on performance
- No bias toward entry method

### **3. Quality Control**
- Multi-stage validation
- Comprehensive testing
- Only best strategies deployed

### **4. Traceability**
- Full audit trail
- Every stage logged
- Easy debugging

### **5. Scalability**
- Process 100s of strategies
- Parallel processing
- Queue management

### **6. Safety**
- Mandatory risk controls
- Validation before deployment
- Monitoring after deployment

---

## 🎓 DEVELOPER NOTES

### **Adding New Pipeline Stage**

```python
async def _new_stage(self, strategy: Strategy) -> PipelineResult:
    """New pipeline stage"""
    strategy.current_stage = PipelineStage.NEW_STAGE
    strategy.logs.append("Running new stage...")
    
    try:
        # Your logic here
        result = do_something(strategy.code)
        
        strategy.logs.append("✓ New stage completed")
        return PipelineResult(success=True, message="Done")
        
    except Exception as e:
        strategy.errors.append(f"New stage failed: {e}")
        raise
```

### **Connecting Existing Module**

```python
from existing_module import validator

async def _validate(self, strategy: Strategy):
    # Call existing validator
    result = await validator.validate(strategy.code)
    
    if result.success:
        strategy.validated = True
    else:
        strategy.errors.extend(result.errors)
        raise ValidationError(result.message)
```

---

**Status**: ✅ CORE IMPLEMENTATION COMPLETE  
**Next**: Integration with existing modules  
**Timeline**: 2-4 weeks for full production readiness
