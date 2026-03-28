# AUTOMATED OPTIMIZATION TRIGGER - ARCHITECTURE

**Goal:** Run optimization from UI button, no manual Python execution

---

## 🏗️ ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND (Browser)                                         │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Optimization Control Panel                        │    │
│  │  ┌──────────────────────────────────────────────┐  │    │
│  │  │  [▶ Run Optimization]  [⏸ Cancel]           │  │    │
│  │  │                                               │  │    │
│  │  │  Status: Running... ⏳                        │  │    │
│  │  │  Progress: 5/8 variations complete           │  │    │
│  │  └──────────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────┘    │
│                      │                                       │
│                      │ POST /api/optimization/run           │
│                      ↓                                       │
└──────────────────────┼──────────────────────────────────────┘
                       │
                       ↓
┌──────────────────────┼──────────────────────────────────────┐
│  BACKEND (Server)    │                                      │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  FastAPI Endpoint: /run-optimization               │    │
│  │  1. Validate request                               │    │
│  │  2. Execute Python script via subprocess           │    │
│  │  3. Monitor execution                              │    │
│  │  4. Read results JSON                              │    │
│  │  5. Store in MongoDB                               │    │
│  │  6. Return results                                 │    │
│  └────────────────────────────────────────────────────┘    │
│                      │                                       │
│                      │ subprocess.run()                     │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Local Python Script Execution                     │    │
│  │  python /path/to/phase2a_optimizer.py              │    │
│  │                                                     │    │
│  │  Output: /path/to/phase2a_results.json            │    │
│  └────────────────────────────────────────────────────┘    │
│                      │                                       │
└──────────────────────┼──────────────────────────────────────┘
                       │
                       ↓ Read JSON
                       
                  Results JSON
                  ┌──────────────┐
                  │ optimization │
                  │ run results  │
                  └──────────────┘
```

---

## 🔧 IMPLEMENTATION

### **1. Backend API Endpoint**

**File: `/app/backend/optimization_executor.py` (NEW)**

```python
"""
Optimization Executor

Runs local Python optimization scripts from API calls
"""

import os
import subprocess
import json
import asyncio
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

router = APIRouter(prefix="/api/optimization", tags=["Optimization Execution"])

# Configuration
SCRIPT_DIR = os.environ.get('OPTIMIZATION_SCRIPT_DIR', '/app/trading_system/backend')
SCRIPT_NAME = "phase2a_optimizer.py"
RESULTS_FILE = "phase2a_results.json"
PYTHON_CMD = "python3"

# Execution state (in-memory for now, could use Redis for production)
execution_state = {
    "running": False,
    "run_id": None,
    "progress": None,
    "error": None
}


class OptimizationRunRequest(BaseModel):
    csv_path: str
    strategy: str = "trend_following"
    phase: str = "2A"


class OptimizationStatus(BaseModel):
    running: bool
    run_id: Optional[str]
    progress: Optional[str]
    error: Optional[str]


@router.post("/run")
async def run_optimization(
    request: OptimizationRunRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger optimization script execution
    
    Flow:
    1. Validate not already running
    2. Execute Python script via subprocess
    3. Wait for completion
    4. Read results JSON
    5. Store in MongoDB
    6. Return results
    """
    
    # Check if already running
    if execution_state["running"]:
        raise HTTPException(
            status_code=409,
            detail=f"Optimization already running. Run ID: {execution_state['run_id']}"
        )
    
    # Validate script exists
    script_path = Path(SCRIPT_DIR) / SCRIPT_NAME
    if not script_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Optimization script not found: {script_path}"
        )
    
    # Validate CSV exists
    csv_path = Path(request.csv_path)
    if not csv_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"CSV file not found: {request.csv_path}"
        )
    
    # Generate run ID
    run_id = datetime.utcnow().isoformat()
    
    # Update state
    execution_state["running"] = True
    execution_state["run_id"] = run_id
    execution_state["progress"] = "Starting..."
    execution_state["error"] = None
    
    try:
        # Execute script
        print(f"[{run_id}] Starting optimization...")
        print(f"  Script: {script_path}")
        print(f"  CSV: {request.csv_path}")
        
        # Run subprocess
        result = subprocess.run(
            [PYTHON_CMD, str(script_path), "--csv", request.csv_path],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        # Check for errors
        if result.returncode != 0:
            error_msg = result.stderr or "Script execution failed"
            execution_state["error"] = error_msg
            execution_state["running"] = False
            raise HTTPException(
                status_code=500,
                detail=f"Script execution failed: {error_msg}"
            )
        
        # Read results JSON
        results_path = Path(SCRIPT_DIR) / RESULTS_FILE
        if not results_path.exists():
            execution_state["error"] = "Results file not generated"
            execution_state["running"] = False
            raise HTTPException(
                status_code=500,
                detail="Results file not generated by script"
            )
        
        with open(results_path, 'r') as f:
            results = json.load(f)
        
        # Store in MongoDB (using existing optimization_runs collection)
        from motor.motor_asyncio import AsyncIOMotorClient
        
        MONGO_URL = os.environ.get('MONGO_URL')
        client = AsyncIOMotorClient(MONGO_URL)
        db = client['ctrader_bot_factory']
        
        result_doc = results.copy()
        result_doc['uploaded_at'] = datetime.utcnow()
        result_doc['executed_via'] = 'api'
        result_doc['csv_path'] = request.csv_path
        
        await db.optimization_runs.insert_one(result_doc)
        
        client.close()
        
        # Update state
        execution_state["running"] = False
        execution_state["progress"] = "Complete"
        
        print(f"[{run_id}] Optimization complete!")
        print(f"  Variations: {len(results.get('all_results', []))}")
        print(f"  Viable: {results.get('summary_statistics', {}).get('viable_strategies', 0)}")
        
        return {
            "status": "success",
            "run_id": run_id,
            "results": results,
            "execution_time": results.get('optimization_run', {}).get('optimization_config', {}).get('execution_time_seconds', 0)
        }
    
    except subprocess.TimeoutExpired:
        execution_state["error"] = "Script execution timed out (>5 minutes)"
        execution_state["running"] = False
        raise HTTPException(
            status_code=504,
            detail="Script execution timed out"
        )
    
    except Exception as e:
        execution_state["error"] = str(e)
        execution_state["running"] = False
        raise HTTPException(
            status_code=500,
            detail=f"Execution error: {str(e)}"
        )


@router.get("/status")
async def get_execution_status() -> OptimizationStatus:
    """Get current execution status"""
    return OptimizationStatus(**execution_state)


@router.post("/cancel")
async def cancel_optimization():
    """Cancel running optimization (if possible)"""
    
    if not execution_state["running"]:
        raise HTTPException(
            status_code=400,
            detail="No optimization is currently running"
        )
    
    # Note: This is a simplified implementation
    # Production would need process tracking and killing
    execution_state["running"] = False
    execution_state["error"] = "Cancelled by user"
    
    return {"status": "cancelled"}
```

---

### **2. Update Phase 2A Script to Accept Arguments**

**File: `/app/trading_system/backend/phase2a_optimizer.py` (MODIFY)**

Add argument parsing at the top:

```python
import argparse

# ... (existing imports)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Phase 2A Optimizer')
    parser.add_argument(
        '--csv',
        type=str,
        required=False,
        default='/path/to/default/EURUSD_H1.csv',
        help='Path to CSV file'
    )
    return parser.parse_args()


if __name__ == "__main__":
    # Parse arguments
    args = parse_args()
    
    print()
    print("╔" + "="*78 + "╗")
    print("║" + " "*25 + "PHASE 2A OPTIMIZER" + " "*35 + "║")
    print("║" + " "*15 + "Controlled Rollout - Validation Phase" + " "*24 + "║")
    print("╚" + "="*78 + "╝")
    print()
    
    # Use CSV path from args
    CSV_PATH = args.csv
    
    print(f"CSV Path: {CSV_PATH}")
    print()
    
    # Run optimization
    optimizer = Phase2AOptimizer(CSV_PATH)
    results = optimizer.run_optimization()
    
    # Save results
    output_file = "phase2a_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Results saved to {output_file}")
```

---

### **3. Add Router to Backend Server**

**File: `/app/backend/server.py` (MODIFY)**

```python
# Add import
from optimization_executor import router as optimization_executor_router

# Add router
app.include_router(optimization_executor_router)

# Add environment variable for script directory
import os
os.environ.setdefault('OPTIMIZATION_SCRIPT_DIR', '/app/trading_system/backend')
```

---

### **4. Frontend Component**

**File: `/app/frontend/src/components/OptimizationTrigger.js` (NEW)**

```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Play, StopCircle, Loader, CheckCircle, AlertCircle } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function OptimizationTrigger() {
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [csvPath, setCsvPath] = useState('/app/trading_system/data/EURUSD_H1.csv');

  // Poll status while running
  useEffect(() => {
    if (!running) return;

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${BACKEND_URL}/api/optimization/status`);
        setStatus(response.data);

        if (!response.data.running) {
          setRunning(false);
          clearInterval(interval);
        }
      } catch (err) {
        console.error('Status poll error:', err);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [running]);

  const handleRunOptimization = async () => {
    setError(null);
    setResults(null);
    setRunning(true);

    try {
      const response = await axios.post(
        `${BACKEND_URL}/api/optimization/run`,
        {
          csv_path: csvPath,
          strategy: 'trend_following',
          phase: '2A'
        }
      );

      setResults(response.data.results);
      setRunning(false);
      
      // Refresh results page (if on that page)
      window.location.reload();
      
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      setRunning(false);
    }
  };

  const handleCancel = async () => {
    try {
      await axios.post(`${BACKEND_URL}/api/optimization/cancel`);
      setRunning(false);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
        <Play className="w-6 h-6 text-blue-600" />
        Optimization Control
      </h2>

      {/* CSV Path Input */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          CSV Data Path
        </label>
        <input
          type="text"
          value={csvPath}
          onChange={(e) => setCsvPath(e.target.value)}
          disabled={running}
          className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="/path/to/EURUSD_H1.csv"
        />
        <p className="text-xs text-gray-500 mt-1">
          Path to CSV file on server (backend accessible)
        </p>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3 mb-4">
        <button
          onClick={handleRunOptimization}
          disabled={running}
          className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium ${
            running
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-700'
          }`}
        >
          {running ? (
            <>
              <Loader className="w-5 h-5 animate-spin" />
              Running...
            </>
          ) : (
            <>
              <Play className="w-5 h-5" />
              Run Optimization
            </>
          )}
        </button>

        {running && (
          <button
            onClick={handleCancel}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
          >
            <StopCircle className="w-5 h-5" />
            Cancel
          </button>
        )}
      </div>

      {/* Status Display */}
      {running && status && (
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mb-4">
          <div className="flex items-center gap-2 mb-2">
            <Loader className="w-5 h-5 animate-spin text-blue-600" />
            <span className="font-medium text-blue-900">
              Optimization in Progress
            </span>
          </div>
          <p className="text-sm text-blue-700">
            {status.progress || 'Processing...'}
          </p>
          <p className="text-xs text-blue-600 mt-1">
            Run ID: {status.run_id}
          </p>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-5 h-5 text-red-600" />
            <span className="font-medium text-red-900">Error</span>
          </div>
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Success Display */}
      {results && !running && (
        <div className="bg-green-50 border border-green-200 rounded-md p-4">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-5 h-5 text-green-600" />
            <span className="font-medium text-green-900">
              Optimization Complete!
            </span>
          </div>
          <div className="text-sm text-green-700 space-y-1">
            <p>
              ✓ Variations tested: {results.all_results?.length || 0}
            </p>
            <p>
              ✓ Viable strategies: {results.summary_statistics?.viable_strategies || 0}
            </p>
            <p>
              ✓ Best PF: {results.summary_statistics?.best_profit_factor?.toFixed(2) || 'N/A'}
            </p>
            <p>
              ✓ Execution time: {results.optimization_run?.optimization_config?.execution_time_seconds?.toFixed(1) || 0}s
            </p>
          </div>
          <div className="mt-3">
            <a
              href="/discovery"
              className="text-sm text-green-700 hover:text-green-900 underline"
            >
              → View detailed results
            </a>
          </div>
        </div>
      )}

      {/* Info */}
      <div className="mt-4 text-xs text-gray-500">
        <p className="font-medium mb-1">Phase 2A Configuration:</p>
        <ul className="list-disc list-inside space-y-1">
          <li>Strategy: Trend Following (only)</li>
          <li>Variations: 8 parameter combinations</li>
          <li>Expected runtime: 5-10 seconds</li>
          <li>Purpose: Validation phase</li>
        </ul>
      </div>
    </div>
  );
}

export default OptimizationTrigger;
```

---

### **5. Add to Main UI**

**File: `/app/frontend/src/App.js` (MODIFY)**

```jsx
import OptimizationTrigger from './components/OptimizationTrigger';
import StrategyDiscovery from './components/StrategyDiscovery';

// In your routing or main dashboard:
function Dashboard() {
  return (
    <div className="container mx-auto p-6">
      {/* Optimization Trigger */}
      <OptimizationTrigger />
      
      {/* Results Display */}
      <StrategyDiscovery />
    </div>
  );
}
```

---

## 🔒 SECURITY CONSIDERATIONS

### **1. Path Validation**

**In backend:**
```python
def validate_csv_path(csv_path: str) -> bool:
    """Validate CSV path to prevent directory traversal"""
    
    # Convert to Path object
    path = Path(csv_path)
    
    # Check if absolute path
    if not path.is_absolute():
        return False
    
    # Check if file exists
    if not path.exists():
        return False
    
    # Check if it's a file (not directory)
    if not path.is_file():
        return False
    
    # Check extension
    if path.suffix.lower() != '.csv':
        return False
    
    # Optional: Check if within allowed directories
    allowed_dirs = [
        Path('/app/trading_system/data'),
        Path('/app/data')
    ]
    
    if not any(str(path).startswith(str(allowed)) for allowed in allowed_dirs):
        return False
    
    return True
```

---

### **2. Command Injection Prevention**

```python
# GOOD: Use list arguments
subprocess.run([PYTHON_CMD, script_path, "--csv", csv_path])

# BAD: Never use shell=True with user input
# subprocess.run(f"python {script_path} --csv {csv_path}", shell=True)  # DANGER!
```

---

### **3. Timeout Protection**

```python
# Always set timeout to prevent hanging
subprocess.run(..., timeout=300)  # 5 minutes max
```

---

## 📊 ERROR HANDLING

### **Common Errors & Solutions:**

| Error | Cause | Solution |
|-------|-------|----------|
| **404: Script not found** | Wrong path | Check OPTIMIZATION_SCRIPT_DIR env var |
| **404: CSV not found** | Invalid CSV path | Verify CSV path on backend |
| **409: Already running** | Concurrent execution | Wait for current run to finish |
| **500: Script failed** | Python error | Check script logs |
| **504: Timeout** | Took > 5 min | Check if data is too large |

---

## 🧪 TESTING

### **1. Test Script Manually First:**

```bash
cd /app/trading_system/backend
python phase2a_optimizer.py --csv /path/to/test.csv

# Should output:
# ✅ Results saved to phase2a_results.json
```

---

### **2. Test API Endpoint:**

```bash
curl -X POST http://localhost:8001/api/optimization/run \
  -H "Content-Type: application/json" \
  -d '{
    "csv_path": "/app/trading_system/data/EURUSD_H1.csv",
    "strategy": "trend_following",
    "phase": "2A"
  }'
```

---

### **3. Test from UI:**

1. Click "Run Optimization" button
2. Watch loading indicator
3. Verify results appear
4. Check MongoDB for stored results

---

## 📁 FILE STRUCTURE

```
/app/
├── backend/
│   ├── server.py (modified - add router)
│   ├── optimization_executor.py (NEW - execution logic)
│   └── optimization_router.py (existing - results display)
│
├── frontend/
│   └── src/
│       └── components/
│           ├── OptimizationTrigger.js (NEW - trigger UI)
│           └── StrategyDiscovery.js (existing - results UI)
│
└── trading_system/
    └── backend/
        ├── phase2a_optimizer.py (modified - add args)
        └── phase2a_results.json (generated)
```

---

## 🔄 WORKFLOW

### **Before (Manual):**
```
1. Open terminal
2. cd to script directory
3. Run: python phase2a_optimizer.py
4. Wait for completion
5. Run: python upload_results.py results.json
6. Open browser
7. View results
```

### **After (Automated):**
```
1. Open browser
2. Click "Run Optimization"
3. Wait (see progress)
4. View results (auto-displayed)
```

**Time saved:** 90% (from ~2 minutes → ~10 seconds of user interaction)

---

**Continue in next message for deployment guide...**
