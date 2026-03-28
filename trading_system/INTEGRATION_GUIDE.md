# AUTOMATED OPTIMIZATION - INTEGRATION GUIDE

**Complete step-by-step instructions to integrate automated optimization**

---

## 📋 PREREQUISITES

Before starting:
- [ ] Backend is running (`sudo supervisorctl status backend`)
- [ ] Frontend is running (`cd /app/frontend && yarn start`)
- [ ] MongoDB is accessible
- [ ] You have a CSV file ready (e.g., `/app/trading_system/data/EURUSD_H1.csv`)

---

## 🔧 STEP 1: BACKEND INTEGRATION (10 minutes)

### 1.1 Add Optimization Executor

```bash
cd /app/backend

# File should already be created at:
# /app/backend/optimization_executor.py

# Verify it exists:
ls -la optimization_executor.py
```

**If missing, create it from the provided code in the previous response.**

---

### 1.2 Update server.py

```bash
nano server.py
```

**ADD these lines:**

```python
# Near the top with other imports
from optimization_executor import router as optimization_executor_router

# After other app.include_router() calls
app.include_router(optimization_executor_router)
```

**Full example of server.py modification:**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# ... other imports ...

# ADD THIS
from optimization_executor import router as optimization_executor_router

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... existing routes ...

# ADD THIS
app.include_router(optimization_executor_router)

# ... rest of file ...
```

---

### 1.3 Set Environment Variable

```bash
nano /app/backend/.env
```

**ADD this line:**

```env
OPTIMIZATION_SCRIPT_DIR=/app/trading_system/backend
```

**Save and exit** (Ctrl+X, Y, Enter)

---

### 1.4 Restart Backend

```bash
sudo supervisorctl restart backend

# Check logs
tail -f /var/log/supervisor/backend.out.log

# You should see:
# INFO:     Started server process
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
```

**Press Ctrl+C to exit logs**

---

### 1.5 Test Backend API

```bash
# Test status endpoint
curl http://localhost:8001/api/optimization/status

# Should return:
# {"running":false,"run_id":null,"elapsed_seconds":null,"error":null}
```

---

## 📝 STEP 2: MODIFY PYTHON SCRIPT (5 minutes)

### 2.1 Navigate to Script Directory

```bash
cd /app/trading_system/backend
```

---

### 2.2 Backup Original Script

```bash
cp phase2a_optimizer.py phase2a_optimizer.py.backup
```

---

### 2.3 Apply Modifications

Open the file:
```bash
nano phase2a_optimizer.py
```

**Follow the instructions in:**
`/app/trading_system/PHASE2A_OPTIMIZER_MODIFICATIONS.md`

**Key changes:**
1. Add `import argparse`, `import sys`, `import os` at top
2. Add `parse_args()` function
3. Modify `__main__` section to use `args.csv`
4. Change output filename to `results.json`

**Save and exit** (Ctrl+X, Y, Enter)

---

### 2.4 Test Script Manually

```bash
# Test with explicit path
python phase2a_optimizer.py --csv /app/trading_system/data/EURUSD_H1.csv

# Should output:
# PHASE 2A OPTIMIZER
# CSV Path: /app/trading_system/data/EURUSD_H1.csv
# ...
# ✅ Results saved to results.json

# Check results file was created
ls -la results.json
```

---

## 🎨 STEP 3: FRONTEND INTEGRATION (10 minutes)

### 3.1 Add Component

```bash
cd /app/frontend/src/components

# File should already be created at:
# /app/frontend/src/components/OptimizationTrigger.js

# Verify:
ls -la OptimizationTrigger.js
```

---

### 3.2 Update App.js

```bash
cd /app/frontend/src
nano App.js
```

**ADD import at top:**

```javascript
import OptimizationTrigger from './components/OptimizationTrigger';
```

**ADD component to your main page/dashboard:**

```javascript
function Dashboard() {
  return (
    <div className="container mx-auto p-6">
      {/* Add Optimization Trigger */}
      <OptimizationTrigger />
      
      {/* Your other components */}
    </div>
  );
}
```

**OR if you have routing, add a new route:**

```javascript
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import OptimizationTrigger from './components/OptimizationTrigger';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<OptimizationTrigger />} />
        {/* other routes */}
      </Routes>
    </BrowserRouter>
  );
}
```

**Save and exit**

---

### 3.3 Restart Frontend (if needed)

Frontend should hot-reload automatically, but if not:

```bash
cd /app/frontend

# Stop current process (Ctrl+C if running)

# Restart
yarn start
```

---

## ✅ STEP 4: TEST END-TO-END (5 minutes)

### 4.1 Access Frontend

Open browser:
```
http://localhost:3000
```

(Or your deployed URL)

---

### 4.2 Locate Optimization Panel

You should see:
- **Phase 2A Optimization** panel
- CSV path input field
- **Run Optimization** button

---

### 4.3 Configure CSV Path

Enter the path to your CSV file on the **backend server**:
```
/app/trading_system/data/EURUSD_H1.csv
```

**Important:** This must be a path accessible by the backend, not your laptop.

---

### 4.4 Run Optimization

1. Click **"Run Optimization"** button
2. You should see:
   - Button changes to "Running Optimization..."
   - Loading spinner appears
   - Status shows "Optimization in Progress"
   - Elapsed time counter

3. After 5-15 seconds:
   - Success message appears
   - Shows: Total Strategies, Viable, Best PF, Time
   - Lists top 3 strategies

---

### 4.5 Verify Backend Logs

```bash
tail -f /var/log/supervisor/backend.out.log

# You should see:
# [2026-03-26T...] Starting optimization...
#   Script: /app/trading_system/backend/phase2a_optimizer.py
#   CSV: /app/trading_system/data/EURUSD_H1.csv
# ...
# [2026-03-26T...] Optimization complete!
#   Total strategies: 8
#   Viable: 5
#   Best PF: 1.42
```

---

### 4.6 Check MongoDB

```bash
mongo

use ctrader_bot_factory

db.optimization_runs.find().limit(1).pretty()

# Should show the latest optimization run
```

---

## 🐛 TROUBLESHOOTING

### Issue: "Script not found"

**Check:**
```bash
ls -la /app/trading_system/backend/phase2a_optimizer.py

# Should exist
```

**Fix:**
```bash
# Verify OPTIMIZATION_SCRIPT_DIR in .env
cat /app/backend/.env | grep OPTIMIZATION_SCRIPT_DIR

# Should output:
# OPTIMIZATION_SCRIPT_DIR=/app/trading_system/backend
```

---

### Issue: "CSV file not found"

**Check:**
```bash
# Verify CSV exists on BACKEND server
ls -la /app/trading_system/data/EURUSD_H1.csv
```

**Fix:**
- Make sure CSV path in UI is the backend path, not local laptop path
- Create test CSV if needed

---

### Issue: "Optimization already running"

**Fix:**
```bash
curl -X POST http://localhost:8001/api/optimization/cancel

# Or restart backend:
sudo supervisorctl restart backend
```

---

### Issue: "Results file not generated"

**Check:**
```bash
cd /app/trading_system/backend

# Run script manually
python phase2a_optimizer.py --csv /app/trading_system/data/EURUSD_H1.csv

# Check if results.json created
ls -la results.json
```

**Fix:**
- Make sure script completes without errors
- Check script has write permissions in directory

---

### Issue: Frontend not showing component

**Check:**
```bash
# Verify component file exists
ls -la /app/frontend/src/components/OptimizationTrigger.js

# Check App.js has import
grep "OptimizationTrigger" /app/frontend/src/App.js
```

**Fix:**
- Ensure import is added
- Ensure component is rendered in JSX
- Check browser console for errors (F12)

---

## 📊 VERIFICATION CHECKLIST

After completing all steps, verify:

### Backend:
- [ ] `optimization_executor.py` exists in `/app/backend/`
- [ ] `server.py` imports and includes the router
- [ ] `.env` has `OPTIMIZATION_SCRIPT_DIR` set
- [ ] Backend restarts without errors
- [ ] `/api/optimization/status` returns JSON

### Script:
- [ ] `phase2a_optimizer.py` accepts `--csv` argument
- [ ] Script runs manually: `python phase2a_optimizer.py --csv <path>`
- [ ] Creates `results.json` file
- [ ] Returns exit code 0 on success

### Frontend:
- [ ] `OptimizationTrigger.js` exists in `/app/frontend/src/components/`
- [ ] `App.js` imports the component
- [ ] Component renders in UI
- [ ] No console errors (F12)

### Integration:
- [ ] Click button triggers API call
- [ ] Loading state appears
- [ ] Results display after completion
- [ ] MongoDB stores the run
- [ ] Can run multiple times

---

## 🎯 EXPECTED WORKFLOW

### User Experience:

1. **User opens UI** → Sees optimization panel
2. **User enters CSV path** → Backend server path
3. **User clicks "Run Optimization"** → Button shows loading
4. **Backend executes Python** → Script runs with CSV
5. **Script completes** → Results saved to JSON
6. **Backend reads JSON** → Stores in MongoDB
7. **API returns results** → Frontend displays
8. **User sees summary** → Total, viable, best PF
9. **User clicks link** → Views detailed results

**Total time:** 10-15 seconds from click to results

---

## 🚀 NEXT STEPS

After successful testing:

1. **Document CSV locations** - Where is your data?
2. **Test with real data** - Use actual EURUSD H1 CSV
3. **Validate results** - Check if strategies make sense
4. **Prepare for Phase 2B** - Add mean reversion strategy
5. **Consider data migration** - Move CSV to backend permanently

---

## 📝 SUMMARY

### Files Created:
```
/app/backend/optimization_executor.py (NEW)
/app/frontend/src/components/OptimizationTrigger.js (NEW)
```

### Files Modified:
```
/app/backend/server.py (add router)
/app/backend/.env (add OPTIMIZATION_SCRIPT_DIR)
/app/trading_system/backend/phase2a_optimizer.py (add argparse)
/app/frontend/src/App.js (add component)
```

### What Changed:
- ✅ Backend can now execute Python scripts via API
- ✅ Frontend has button to trigger optimization
- ✅ Results are automatically stored and displayed
- ✅ No manual command-line execution needed

### Time Saved:
- **Before:** ~2-3 minutes per run (manual)
- **After:** ~10 seconds per run (automated)
- **Efficiency:** 90% time reduction

---

**You are now ready to run automated optimization from the UI!**
