# STRATEGY DISCOVERY ENGINE - FRONTEND & WORKFLOW

**Part 2: UI Components and Complete Workflow**

---

## 🎨 FRONTEND UI COMPONENTS

### **1. Strategy Discovery Dashboard**

**File: `/app/frontend/src/components/StrategyDiscovery.js`**

```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  TrendingUp, 
  Filter, 
  Award, 
  BarChart3,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function StrategyDiscovery() {
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    minPF: 1.0,
    maxDD: 10.0,
    minTrades: 20,
    viableOnly: true
  });
  const [sortBy, setSortBy] = useState('ranking_score');
  const [selectedStrategy, setSelectedStrategy] = useState(null);

  useEffect(() => {
    fetchLeaderboard();
  }, [filters]);

  const fetchLeaderboard = async () => {
    setLoading(true);
    try {
      const response = await axios.get(
        `${BACKEND_URL}/api/optimization/leaderboard`,
        {
          params: {
            min_pf: filters.minPF,
            max_dd: filters.maxDD,
            min_trades: filters.minTrades,
            limit: 50
          }
        }
      );
      setLeaderboard(response.data);
    } catch (error) {
      console.error('Error fetching leaderboard:', error);
    }
    setLoading(false);
  };

  const getScoreColor = (score) => {
    if (score >= 85) return 'text-green-600 font-bold';
    if (score >= 70) return 'text-blue-600';
    if (score >= 50) return 'text-yellow-600';
    return 'text-gray-600';
  };

  const getRankBadge = (rank) => {
    if (rank === 1) return '🥇';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return `#${rank}`;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
          <Award className="text-yellow-500" />
          Strategy Discovery Engine
        </h1>
        <p className="text-gray-600 mt-2">
          AI-powered strategy optimization and ranking system
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-5 h-5" />
          <h2 className="font-semibold">Filters</h2>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Min Profit Factor
            </label>
            <input
              type="number"
              step="0.1"
              value={filters.minPF}
              onChange={(e) => setFilters({...filters, minPF: parseFloat(e.target.value)})}
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Drawdown %
            </label>
            <input
              type="number"
              step="1"
              value={filters.maxDD}
              onChange={(e) => setFilters({...filters, maxDD: parseFloat(e.target.value)})}
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Min Trades
            </label>
            <input
              type="number"
              value={filters.minTrades}
              onChange={(e) => setFilters({...filters, minTrades: parseInt(e.target.value)})}
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Show
            </label>
            <select
              value={filters.viableOnly}
              onChange={(e) => setFilters({...filters, viableOnly: e.target.value === 'true'})}
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="true">Viable Only</option>
              <option value="false">All Strategies</option>
            </select>
          </div>
        </div>
      </div>

      {/* Leaderboard */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="p-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <TrendingUp />
            Top Performing Strategies
          </h2>
          <p className="text-sm mt-1 opacity-90">
            {leaderboard.length} strategies ranked by composite score
          </p>
        </div>

        {loading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading strategies...</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rank</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Strategy</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Parameters</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">PF</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Return</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">DD</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Trades</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Score</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {leaderboard.map((strategy, index) => (
                  <tr 
                    key={strategy.variation_id}
                    className="hover:bg-gray-50 cursor-pointer transition"
                    onClick={() => setSelectedStrategy(strategy)}
                  >
                    <td className="px-4 py-3 text-sm font-semibold">
                      {getRankBadge(index + 1)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-gray-900">
                        {strategy.strategy_name.replace('_', ' ').toUpperCase()}
                      </div>
                      <div className="text-xs text-gray-500">{strategy.variation_id}</div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600">
                      {Object.entries(strategy.parameters).slice(0, 2).map(([key, value]) => (
                        <div key={key}>{key}: {value}</div>
                      ))}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`font-semibold ${
                        strategy.performance.profit_factor >= 1.5 ? 'text-green-600' : 'text-gray-900'
                      }`}>
                        {strategy.performance.profit_factor.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`font-semibold ${
                        strategy.performance.return_pct > 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {strategy.performance.return_pct.toFixed(2)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`font-semibold ${
                        strategy.performance.max_drawdown_pct < 5 ? 'text-green-600' : 'text-yellow-600'
                      }`}>
                        {strategy.performance.max_drawdown_pct.toFixed(2)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center text-sm">
                      {strategy.performance.total_trades}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className={`text-lg font-bold ${getScoreColor(strategy.ranking_score)}`}>
                        {strategy.ranking_score.toFixed(1)}
                      </div>
                      {strategy.ranking_score >= 85 && (
                        <span className="text-xs">⭐</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {strategy.viability.is_viable ? (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          ✓ Viable
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          Not Viable
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Strategy Detail Modal */}
      {selectedStrategy && (
        <StrategyDetailModal 
          strategy={selectedStrategy} 
          onClose={() => setSelectedStrategy(null)}
        />
      )}
    </div>
  );
}


function StrategyDetailModal({ strategy, onClose }) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white p-6">
          <h2 className="text-2xl font-bold">
            {strategy.strategy_name.replace('_', ' ').toUpperCase()}
          </h2>
          <p className="text-sm mt-1 opacity-90">{strategy.variation_id}</p>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Score Breakdown */}
          <div>
            <h3 className="font-semibold text-lg mb-3">Ranking Score Breakdown</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-4 bg-blue-50 rounded-lg">
                <div className="text-sm text-gray-600">Composite Score</div>
                <div className="text-3xl font-bold text-blue-600">
                  {strategy.ranking_score.toFixed(1)}
                </div>
              </div>
              <div className="text-center p-4 bg-green-50 rounded-lg">
                <div className="text-sm text-gray-600">PF Score</div>
                <div className="text-2xl font-bold text-green-600">
                  {strategy.score_breakdown.pf_score.toFixed(1)}
                </div>
              </div>
              <div className="text-center p-4 bg-purple-50 rounded-lg">
                <div className="text-sm text-gray-600">Return Score</div>
                <div className="text-2xl font-bold text-purple-600">
                  {strategy.score_breakdown.return_score.toFixed(1)}
                </div>
              </div>
              <div className="text-center p-4 bg-yellow-50 rounded-lg">
                <div className="text-sm text-gray-600">DD Score</div>
                <div className="text-2xl font-bold text-yellow-600">
                  {strategy.score_breakdown.drawdown_score.toFixed(1)}
                </div>
              </div>
            </div>
          </div>

          {/* Parameters */}
          <div>
            <h3 className="font-semibold text-lg mb-3">Parameters</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {Object.entries(strategy.parameters).map(([key, value]) => (
                <div key={key} className="flex justify-between p-3 bg-gray-50 rounded">
                  <span className="text-sm text-gray-600">{key}:</span>
                  <span className="text-sm font-semibold">{value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Performance Metrics */}
          <div>
            <h3 className="font-semibold text-lg mb-3">Performance Metrics</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard
                label="Profit Factor"
                value={strategy.performance.profit_factor.toFixed(2)}
                good={strategy.performance.profit_factor >= 1.5}
              />
              <MetricCard
                label="Win Rate"
                value={`${strategy.performance.win_rate.toFixed(1)}%`}
                good={strategy.performance.win_rate >= 45}
              />
              <MetricCard
                label="Max Drawdown"
                value={`${strategy.performance.max_drawdown_pct.toFixed(2)}%`}
                good={strategy.performance.max_drawdown_pct < 5}
              />
              <MetricCard
                label="Total Trades"
                value={strategy.performance.total_trades}
                good={strategy.performance.total_trades >= 30}
              />
              <MetricCard
                label="Net P&L"
                value={`$${strategy.performance.net_pnl.toFixed(2)}`}
                good={strategy.performance.net_pnl > 0}
              />
              <MetricCard
                label="Return %"
                value={`${strategy.performance.return_pct.toFixed(2)}%`}
                good={strategy.performance.return_pct > 5}
              />
              <MetricCard
                label="Avg Win"
                value={`$${strategy.performance.average_win.toFixed(2)}`}
              />
              <MetricCard
                label="Avg Loss"
                value={`$${strategy.performance.average_loss.toFixed(2)}`}
              />
            </div>
          </div>

          {/* Viability */}
          <div>
            <h3 className="font-semibold text-lg mb-3">Viability Assessment</h3>
            <div className={`p-4 rounded-lg ${
              strategy.viability.is_viable ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-lg ${strategy.viability.is_viable ? 'text-green-600' : 'text-red-600'}`}>
                  {strategy.viability.is_viable ? '✅' : '❌'}
                </span>
                <span className="font-semibold">
                  {strategy.viability.recommendation}
                </span>
              </div>
              <div className="text-sm space-y-1">
                <div>✓ PF Threshold: {strategy.viability.passes_pf_threshold ? 'Pass' : 'Fail'}</div>
                <div>✓ DD Threshold: {strategy.viability.passes_dd_threshold ? 'Pass' : 'Fail'}</div>
                <div>✓ Trade Count: {strategy.viability.passes_trade_count ? 'Pass' : 'Fail'}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t p-4 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
          >
            Close
          </button>
          <button className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
            Export to cBot
          </button>
        </div>
      </div>
    </div>
  );
}


function MetricCard({ label, value, good }) {
  return (
    <div className="p-3 bg-gray-50 rounded">
      <div className="text-xs text-gray-600 mb-1">{label}</div>
      <div className={`text-lg font-bold ${
        good === true ? 'text-green-600' : 
        good === false ? 'text-red-600' : 
        'text-gray-900'
      }`}>
        {value}
      </div>
    </div>
  );
}


export default StrategyDiscovery;
```

---

## 📋 COMPLETE WORKFLOW

### **Step 1: Run Optimization (Your Laptop)**

```bash
# Navigate to your strategy folder
cd /path/to/your/strategies

# Run optimization engine
python optimization_engine.py

# Output:
# ================================================================================
# STRATEGY OPTIMIZATION ENGINE
# ================================================================================
# 
# Strategy: trend_following
#   Parameter combinations: 108
#   [1/108] Testing trend_following... PF: 1.45, Score: 75.2
#   [2/108] Testing trend_following... PF: 1.82, Score: 91.5
#   ...
# 
# Strategy: mean_reversion
#   Parameter combinations: 72
#   [1/72] Testing mean_reversion... PF: 1.68, Score: 85.3
#   ...
# 
# ================================================================================
# OPTIMIZATION COMPLETE
# ================================================================================
# Total variations tested: 230
# Viable strategies: 18 (7.8%)
# Best PF: 1.85
# Best Return: 12.35%
# Execution time: 145.2s
# 
# ✅ Results saved to optimization_results.json
```

---

### **Step 2: Upload Results (Your Laptop)**

```bash
# Upload to backend
python upload_optimization_results.py optimization_results.json

# Output:
# 📤 Uploading to https://your-backend.com/api/optimization/upload...
# ✅ Upload successful!
#    Run ID: 2026-03-26T18:00:00.000Z
#    Top Strategies: 10
#    Total Variations: 230
#    View: https://your-backend.com/discovery
```

---

### **Step 3: View in UI (Browser)**

**Navigate to:** `https://your-backend.com/discovery`

**You'll see:**
1. **Filter Panel** - Adjust PF, DD, trade count thresholds
2. **Leaderboard Table** - All strategies ranked by score
3. **Click on strategy** - See full details
4. **Compare strategies** - Side-by-side comparison

---

## 🎯 KEY FEATURES

### **1. Intelligent Ranking**

**Composite Score Formula:**
```
Score = (PF_score × 0.30) + 
        (Return_score × 0.25) + 
        (DD_score × 0.25) + 
        (Trade_score × 0.20)

Where:
- PF_score = (PF - 1.0) × 100 (capped at 100)
- Return_score = Return% × 6.67 (15% = 100)
- DD_score = 100 - (DD% × 10) (0% = 100, 10% = 0)
- Trade_score = (Trades - 10) × 2 (60+ = 100)
```

**Result:** Strategies with balanced performance rank highest

---

### **2. Viability Assessment**

**Criteria for "Viable" Strategy:**
- ✅ Profit Factor ≥ 1.3
- ✅ Max Drawdown < 10%
- ✅ Total Trades ≥ 20
- ✅ Return > 0%

**Recommendations:**
- **Excellent** (PF ≥ 1.8): Ready for paper trading
- **Very Good** (PF ≥ 1.5): Consider for deployment
- **Good** (PF ≥ 1.3): Needs monitoring
- **Not Viable**: Needs improvement

---

### **3. Parameter Insights**

**Automatically identifies:**
- Most profitable EMA combinations
- Optimal RSI levels
- Best risk percentage
- Sweet spot parameters

**Example:**
```
Parameter Insights:
- Most profitable EMA: 50/200 (PF: 1.85)
- Most profitable RSI: 40/60 (PF: 1.72)
- Optimal risk: 1.0% (PF: 1.68 avg)
```

---

### **4. Multi-Run Comparison**

**Track performance across:**
- Different time periods
- Different instruments
- Different market conditions

**Example:**
```
Strategy: trend_ema50_200
- Jan-Mar 2025: PF 1.92, Return 14.2%
- Apr-Jun 2025: PF 1.45, Return 8.1%
- Jul-Sep 2025: PF 1.28, Return 3.5%

→ Performance degrades over time
→ Needs re-optimization
```

---

## 📈 EXPECTED OUTCOMES

### **Before (Phase 1):**
```
- Upload 1 strategy result
- View metrics
- Manual analysis
```

### **After (Phase 2):**
```
- Upload 230+ strategy variations
- Automatic ranking
- Top 10 highlighted
- Viable strategies filtered
- Parameter insights
- Cross-run comparison
```

---

## ⏱️ EXECUTION TIME

### **Local Optimization:**
```
230 variations × ~0.6s per variation = ~2-3 minutes
```

### **Upload:**
```
~5 seconds (JSON POST)
```

### **UI Load:**
```
~1-2 seconds (query + render)
```

**Total:** 3-5 minutes from run → view

---

## 📊 SAMPLE OUTPUT

### **Console (Local Engine):**
```
Strategy: trend_following
  [108/108] Testing... PF: 1.85, Score: 92.5 ⭐

Top 3 Strategies:
  1. trend_following: PF=1.85, Score=92.5
  2. mean_reversion: PF=1.72, Score=88.3
  3. breakout: PF=1.58, Score=82.1
```

### **UI (Leaderboard):**
```
╔════╦═════════════════╦══════╦════════╦═══════╦═══════╦════════╗
║ #  ║ Strategy        ║  PF  ║ Return ║  DD   ║ Trades║ Score  ║
╠════╬═════════════════╬══════╬════════╬═══════╬═══════╬════════╣
║ 🥇 ║ Trend (50/200)  ║ 1.85 ║ 12.3%  ║ 2.1%  ║  45   ║ 92.5 ⭐║
║ 🥈 ║ MeanRev (40/60) ║ 1.72 ║ 10.8%  ║ 3.4%  ║  52   ║ 88.3   ║
║ 🥉 ║ Breakout (20)   ║ 1.58 ║  9.2%  ║ 4.1%  ║  38   ║ 82.1   ║
╚════╩═════════════════╩══════╩════════╩═══════╩═══════╩════════╝
```

---

**Continue to Part 3 for implementation checklist and migration path...**
