# LOCAL PYTHON ENGINE INTEGRATION - ARCHITECTURE PROPOSAL

**Goal:** Connect local Python strategy engine (on laptop) with backend system (cloud/server)

---

## 🏗️ ARCHITECTURE OPTIONS

### **Option 1: PULL Model (Backend Calls Local API)**

```
┌─────────────────────────────────┐
│   Your Laptop (Local)           │
│                                 │
│  ┌──────────────────────────┐  │
│  │  CSV Data (H1 Candles)   │  │
│  └──────────────────────────┘  │
│             ↓                   │
│  ┌──────────────────────────┐  │
│  │  Python Strategy Engine  │  │
│  │  - Load CSV              │  │
│  │  - Run strategies        │  │
│  │  - Generate results      │  │
│  └──────────────────────────┘  │
│             ↓                   │
│  ┌──────────────────────────┐  │
│  │  Local FastAPI Server    │  │
│  │  POST /run-backtest      │  │
│  │  GET  /results/{id}      │  │
│  │  Port: 8000              │  │
│  └──────────────────────────┘  │
│             ↑                   │
└─────────────┼───────────────────┘
              │ HTTP Request
              │ (ngrok tunnel or VPN)
              ↓
┌─────────────┼───────────────────┐
│   Backend (Cloud/Server)        │
│             ↓                   │
│  ┌──────────────────────────┐  │
│  │  Backend API             │  │
│  │  /api/trigger-analysis   │  │
│  │  /api/get-results        │  │
│  └──────────────────────────┘  │
│             ↓                   │
│  ┌──────────────────────────┐  │
│  │  Frontend UI             │  │
│  │  - Trigger button        │  │
│  │  - Results display       │  │
│  └──────────────────────────┘  │
└─────────────────────────────────┘
```

**Pros:**
- Backend controls when to run analysis
- Real-time trigger from UI
- Follows request-response pattern

**Cons:**
- Requires laptop to be accessible from internet (ngrok/VPN)
- Laptop must be running 24/7 for on-demand access
- Network complexity

---

### **Option 2: PUSH Model (Local Script Pushes Results)** ⭐ **RECOMMENDED**

```
┌─────────────────────────────────┐
│   Your Laptop (Local)           │
│                                 │
│  ┌──────────────────────────┐  │
│  │  CSV Data (H1 Candles)   │  │
│  └──────────────────────────┘  │
│             ↓                   │
│  ┌──────────────────────────┐  │
│  │  Python Strategy Engine  │  │
│  │  - Load CSV              │  │
│  │  - Run strategies        │  │
│  │  - Generate results      │  │
│  └──────────────────────────┘  │
│             ↓                   │
│  ┌──────────────────────────┐  │
│  │  Upload Script           │  │
│  │  - Package results       │  │
│  │  - POST to backend       │  │
│  └──────────────────────────┘  │
│             │                   │
└─────────────┼───────────────────┘
              │ HTTPS POST
              │ (simple, secure)
              ↓
┌─────────────┼───────────────────┐
│   Backend (Cloud/Server)        │
│             ↓                   │
│  ┌──────────────────────────┐  │
│  │  Backend API             │  │
│  │  POST /api/upload-results│  │
│  │  GET  /api/results       │  │
│  │  Store in MongoDB        │  │
│  └──────────────────────────┘  │
│             ↓                   │
│  ┌──────────────────────────┐  │
│  │  Frontend UI             │  │
│  │  - View results          │  │
│  │  - Compare runs          │  │
│  │  - Export reports        │  │
│  └──────────────────────────┘  │
└─────────────────────────────────┘
```

**Pros:** ✅
- Simple: No need for laptop to be publicly accessible
- Secure: Only outgoing HTTPS calls
- Flexible: Run analysis when you want
- No 24/7 requirement

**Cons:**
- Manual trigger (run script on laptop)
- Results available after upload (slight delay)

---

## 📋 RECOMMENDED ARCHITECTURE (Option 2: PUSH Model)

### **Phase 1: Local Integration (Current)**

```
Component Locations:
├── Laptop (Local)
│   ├── Data: CSV files (H1 candles)
│   ├── Engine: Python strategy scripts
│   └── Upload: Simple script to POST results
│
└── Backend (Server)
    ├── API: Receive and store results
    ├── Database: MongoDB (store analysis runs)
    └── UI: Display results
```

### **Phase 2: Hybrid (Future - Optional)**

```
├── Laptop (Local)
│   ├── Data: CSV files (still local)
│   └── Trigger: Simple script
│
└── Backend (Server)
    ├── Engine: Python strategy scripts (moved)
    ├── Data: CSV uploaded once
    └── API + UI: Full processing
```

### **Phase 3: Full Cloud (Future)**

```
└── Backend (Server)
    ├── Data Download: Automated Dukascopy fetch
    ├── Engine: Python strategies
    ├── Scheduler: Automatic runs
    └── API + UI: Complete system
```

---

## 🔧 IMPLEMENTATION PLAN (PUSH Model)

### **1. Local Python Engine Wrapper**

**File: `local_engine_api.py` (on your laptop)**

```python
"""
Local Strategy Engine - Simple wrapper
Runs on your laptop, processes CSV, outputs JSON
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime

def load_csv_data(csv_path: str) -> pd.DataFrame:
    """Load H1 candle data from CSV"""
    df = pd.read_csv(csv_path)
    # Standardize column names
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def run_strategy_engine(csv_path: str, strategies: list) -> dict:
    """
    Run your existing Python strategy engine
    
    Args:
        csv_path: Path to CSV file
        strategies: List of strategy names to run
    
    Returns:
        dict: Results in standard format
    """
    
    # Load data
    candles = load_csv_data(csv_path)
    
    results = {
        "run_id": datetime.utcnow().isoformat(),
        "data_info": {
            "source": csv_path,
            "candles": len(candles),
            "start_date": str(candles['timestamp'].min()),
            "end_date": str(candles['timestamp'].max()),
        },
        "strategies": []
    }
    
    # Run each strategy
    for strategy_name in strategies:
        # YOUR EXISTING STRATEGY CODE HERE
        # Example:
        if strategy_name == "mean_reversion":
            trades = run_mean_reversion(candles)  # Your function
            metrics = calculate_metrics(trades)   # Your function
        elif strategy_name == "trend_following":
            trades = run_trend_following(candles)
            metrics = calculate_metrics(trades)
        
        results["strategies"].append({
            "name": strategy_name,
            "trades": len(trades),
            "metrics": metrics,  # PF, WR, DD, etc.
            "trades_detail": trades  # Optional: full trade list
        })
    
    return results

# Example usage
if __name__ == "__main__":
    results = run_strategy_engine(
        csv_path="/path/to/EURUSD_H1.csv",
        strategies=["mean_reversion", "trend_following"]
    )
    
    # Save locally
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("✅ Analysis complete!")
```

---

### **2. Upload Script (on your laptop)**

**File: `upload_results.py` (on your laptop)**

```python
"""
Upload local strategy results to backend
"""

import requests
import json
import sys
from pathlib import Path

# Backend configuration
BACKEND_URL = "https://your-backend.emergentagent.com"  # Or your deployment URL
API_ENDPOINT = f"{BACKEND_URL}/api/strategy-results/upload"

def upload_results(results_file: str, api_key: str = None):
    """Upload results JSON to backend"""
    
    # Load results
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    # Prepare request
    headers = {
        "Content-Type": "application/json"
    }
    
    if api_key:
        headers["X-API-Key"] = api_key  # Simple auth
    
    # Upload
    print(f"📤 Uploading to {API_ENDPOINT}...")
    
    try:
        response = requests.post(
            API_ENDPOINT,
            json=results,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Upload successful!")
            print(f"   Run ID: {data.get('run_id')}")
            print(f"   View: {BACKEND_URL}/results/{data.get('run_id')}")
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"   {response.text}")
    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python upload_results.py <results.json>")
        sys.exit(1)
    
    results_file = sys.argv[1]
    upload_results(results_file)
```

---

### **3. Backend API Endpoints**

**File: `/app/backend/strategy_results_router.py` (backend)**

```python
"""
Backend API to receive and store strategy results
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import os

router = APIRouter(prefix="/api/strategy-results", tags=["Strategy Results"])

# MongoDB connection (assuming already set up)
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get('MONGO_URL')
client = AsyncIOMotorClient(MONGO_URL)
db = client['ctrader_bot_factory']
results_collection = db['strategy_results']

# Simple API key authentication (optional)
API_KEY = os.environ.get('STRATEGY_API_KEY', 'your-secret-key')


class StrategyResult(BaseModel):
    name: str
    trades: int
    metrics: Dict
    trades_detail: Optional[List] = None


class StrategyRunResult(BaseModel):
    run_id: str
    data_info: Dict
    strategies: List[StrategyResult]


@router.post("/upload")
async def upload_strategy_results(
    results: StrategyRunResult,
    x_api_key: Optional[str] = Header(None)
):
    """
    Upload strategy results from local engine
    
    Accepts JSON with:
    - run_id: timestamp of run
    - data_info: source file, date range, candle count
    - strategies: list of strategy results with metrics
    """
    
    # Simple authentication (optional)
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Add server metadata
    result_doc = results.dict()
    result_doc['uploaded_at'] = datetime.utcnow()
    result_doc['source'] = 'local_engine'
    
    # Store in MongoDB
    insert_result = await results_collection.insert_one(result_doc)
    
    return {
        "status": "success",
        "run_id": results.run_id,
        "mongo_id": str(insert_result.inserted_id),
        "message": "Results uploaded successfully"
    }


@router.get("/list")
async def list_results(limit: int = 20):
    """List recent strategy runs"""
    
    cursor = results_collection.find().sort("uploaded_at", -1).limit(limit)
    results = await cursor.to_list(length=limit)
    
    # Convert ObjectId to string
    for r in results:
        r['_id'] = str(r['_id'])
    
    return results


@router.get("/{run_id}")
async def get_result(run_id: str):
    """Get specific run result"""
    
    result = await results_collection.find_one({"run_id": run_id})
    
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    
    result['_id'] = str(result['_id'])
    return result


@router.delete("/{run_id}")
async def delete_result(run_id: str, x_api_key: Optional[str] = Header(None)):
    """Delete a result"""
    
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    delete_result = await results_collection.delete_one({"run_id": run_id})
    
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Result not found")
    
    return {"status": "success", "message": "Result deleted"}
```

---

### **4. Add Router to Backend Server**

**File: `/app/backend/server.py` (modify)**

```python
# Add at the top
from strategy_results_router import router as strategy_results_router

# Add to app
app.include_router(strategy_results_router)
```

---

### **5. Frontend UI Component**

**File: `/app/frontend/src/components/StrategyResults.js`**

```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function StrategyResults() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedResult, setSelectedResult] = useState(null);

  useEffect(() => {
    fetchResults();
  }, []);

  const fetchResults = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/strategy-results/list`);
      setResults(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching results:', error);
      setLoading(false);
    }
  };

  const viewDetails = async (runId) => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/strategy-results/${runId}`);
      setSelectedResult(response.data);
    } catch (error) {
      console.error('Error fetching details:', error);
    }
  };

  if (loading) return <div>Loading results...</div>;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Strategy Results</h1>
      
      {/* Results List */}
      <div className="grid gap-4">
        {results.map((result) => (
          <div 
            key={result._id} 
            className="border p-4 rounded cursor-pointer hover:bg-gray-50"
            onClick={() => viewDetails(result.run_id)}
          >
            <div className="flex justify-between">
              <div>
                <h3 className="font-semibold">Run: {result.run_id}</h3>
                <p className="text-sm text-gray-600">
                  {result.data_info.candles} candles | 
                  {result.strategies.length} strategies
                </p>
              </div>
              <div className="text-sm text-gray-500">
                {new Date(result.uploaded_at).toLocaleString()}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Details Modal */}
      {selectedResult && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <div className="bg-white p-6 rounded-lg max-w-4xl max-h-screen overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">Results: {selectedResult.run_id}</h2>
            
            {/* Data Info */}
            <div className="mb-4">
              <h3 className="font-semibold">Data</h3>
              <p>Source: {selectedResult.data_info.source}</p>
              <p>Period: {selectedResult.data_info.start_date} to {selectedResult.data_info.end_date}</p>
              <p>Candles: {selectedResult.data_info.candles}</p>
            </div>

            {/* Strategies */}
            {selectedResult.strategies.map((strategy, idx) => (
              <div key={idx} className="mb-4 border-t pt-4">
                <h3 className="font-semibold text-lg">{strategy.name}</h3>
                <div className="grid grid-cols-3 gap-4 mt-2">
                  <div>
                    <p className="text-sm text-gray-600">Trades</p>
                    <p className="font-semibold">{strategy.trades}</p>
                  </div>
                  {Object.entries(strategy.metrics).map(([key, value]) => (
                    <div key={key}>
                      <p className="text-sm text-gray-600">{key}</p>
                      <p className="font-semibold">{value}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}

            <button 
              onClick={() => setSelectedResult(null)}
              className="mt-4 bg-blue-500 text-white px-4 py-2 rounded"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default StrategyResults;
```

---

## 📊 DATA FORMAT SPECIFICATION

### **JSON Structure (from local engine → backend)**

```json
{
  "run_id": "2026-03-26T17:00:00.000Z",
  "data_info": {
    "source": "/Users/you/data/EURUSD_H1.csv",
    "candles": 6513,
    "start_date": "2025-01-02 22:00:00",
    "end_date": "2026-02-25 17:00:00"
  },
  "strategies": [
    {
      "name": "mean_reversion",
      "trades": 45,
      "metrics": {
        "profit_factor": 1.35,
        "win_rate": 48.5,
        "max_drawdown": 3.2,
        "net_pnl": 450.25,
        "return_pct": 4.5
      },
      "trades_detail": [
        {
          "entry_time": "2025-01-15 10:00:00",
          "exit_time": "2025-01-15 14:00:00",
          "direction": "LONG",
          "entry_price": 1.0850,
          "exit_price": 1.0875,
          "pnl": 25.0
        }
      ]
    },
    {
      "name": "trend_following",
      "trades": 32,
      "metrics": {
        "profit_factor": 1.58,
        "win_rate": 42.0,
        "max_drawdown": 2.8,
        "net_pnl": 380.50,
        "return_pct": 3.8
      }
    }
  ]
}
```

---

## 🚀 WORKFLOW

### **Step-by-Step Process:**

**1. On Your Laptop:**
```bash
# Run your strategy engine
python local_engine_api.py
# Output: results.json

# Upload to backend
python upload_results.py results.json
# Output: "✅ Upload successful! View: https://your-app.com/results/..."
```

**2. On Backend:**
```
- Receives POST request
- Stores in MongoDB
- Returns success + run_id
```

**3. On Frontend:**
```
- User clicks "Results" page
- Fetches list of runs
- Displays metrics
- Can drill down into details
```

---

## 🔐 SECURITY

### **Simple API Key (Phase 1)**

**Backend .env:**
```
STRATEGY_API_KEY=your-secret-key-change-this
```

**Upload script:**
```python
upload_results("results.json", api_key="your-secret-key-change-this")
```

### **Future (Phase 2+):**
- JWT authentication
- User-specific results
- Role-based access

---

## 📈 MIGRATION PATH

### **Current (Phase 1):**
```
✅ CSV on laptop
✅ Engine on laptop
✅ Results pushed to backend
✅ UI displays results
```

### **Phase 2 (Later):**
```
- CSV uploaded to backend once
- Engine still on laptop (triggers backend)
- Backend processes and stores
```

### **Phase 3 (Future):**
```
- All data on backend
- All processing on backend
- Scheduler for automatic runs
- Full cloud solution
```

---

## ✅ ADVANTAGES OF THIS APPROACH

1. **Simple:** No complex networking (ngrok, VPN)
2. **Secure:** Only HTTPS POST from laptop
3. **Flexible:** Run analysis when you want
4. **Modular:** Easy to migrate later
5. **Fast:** No need to refactor existing engine
6. **Testable:** Can validate before moving data

---

## 📋 NEXT STEPS

1. **Choose Architecture:** Push vs Pull model
2. **Implement Backend:** Add router to receive results
3. **Create Upload Script:** Simple Python script on laptop
4. **Test Integration:** Upload sample results
5. **Build UI:** Display results in frontend
6. **Iterate:** Add features as needed

---

Would you like me to implement any of these components?
