# 🚀 BOT FACTORY ACCESS GUIDE

## ⚠️ IMPORTANT: This is NOT a Local Application

**This application runs in a CLOUD environment (Kubernetes cluster), not on your local machine.**

You CANNOT access it via `http://localhost:3000` or `http://localhost:8000`.

---

## ✅ CORRECT ACCESS URL

### 🌐 Main Application URL
```
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com
```

### 📊 Live Trading Dashboard (Paper Trading Monitor)
```
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/live
```

### 🔌 Backend API
```
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/api
```

### 📘 API Documentation
```
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/docs
```

---

## 🏗️ SYSTEM ARCHITECTURE

### Cloud Deployment
- **Environment**: Kubernetes Cluster
- **Provider**: Emergent Agent Cloud
- **Frontend Port**: 3000 (internal)
- **Backend Port**: 8001 (internal)
- **MongoDB Port**: 27017 (internal)
- **External Access**: Via Preview URL (HTTPS)

### Port Mapping
```
External HTTPS (443) → Nginx Ingress
  ├─ Frontend Routes → Port 3000
  └─ /api/* Routes → Port 8001
```

---

## 🔐 ENVIRONMENT CONFIGURATION

### Backend Configuration
**Location**: `/app/trading_system/backend/.env`
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=trading_db
EMERGENT_LLM_KEY=sk-emergent-55cD8B387EdD13239A
OPENAI_API_KEY=sk-emergent-55cD8B387EdD13239A
ANTHROPIC_API_KEY=sk-emergent-55cD8B387EdD13239A
DEEPSEEK_API_KEY=sk-emergent-55cD8B387EdD13239A
CORS_ORIGINS=*
```

### Frontend Configuration
**Location**: `/app/trading_system/frontend/.env`
```env
REACT_APP_BACKEND_URL=https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com
```

**⚠️ IMPORTANT**: Frontend MUST use the preview URL, NOT localhost!

---

## 📋 SERVICE STATUS

### Check Service Status
```bash
supervisorctl status
```

**Expected Output**:
```
backend      RUNNING   pid 1926, uptime 0:05:23
frontend     RUNNING   pid 1296, uptime 0:27:04
mongodb      RUNNING   pid 50, uptime 0:47:20
```

### Restart Services
```bash
# Restart backend
supervisorctl restart backend

# Restart frontend
supervisorctl restart frontend

# Restart all services
supervisorctl restart all
```

### View Logs
```bash
# Backend logs
tail -f /var/log/supervisor/backend.err.log
tail -f /var/log/supervisor/backend.out.log

# Frontend logs
tail -f /var/log/supervisor/frontend.err.log
tail -f /var/log/supervisor/frontend.out.log
```

---

## ✅ VERIFICATION CHECKLIST

### 1. Services Running ✅
```bash
supervisorctl status
```
All services should show RUNNING.

### 2. Backend API Accessible ✅
```bash
curl https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/api/
```
Should return: `{"message":"cTrader Bot Builder API"}`

### 3. Paper Trading API ✅
```bash
curl https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/api/paper-trading/status
```
Should return JSON with `running`, `total_equity`, etc.

### 4. Frontend Accessible ✅
Open in browser:
```
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com
```
Should load Bot Factory home page.

### 5. Live Dashboard Accessible ✅
Open in browser:
```
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/live
```
Should show:
- Paper Trading Engine panel
- Equity: $10,000.00
- Status: RUNNING
- Open Positions: 2 (GOLD, SPY)
- Recent Trades table

---

## 🎯 NAVIGATION

### From Home Page
1. Click **"LIVE TRADING"** button (green button in top nav)
2. OR click **"MONITOR"** button (green button on right side)
3. Both navigate to `/live` (Live Monitoring Dashboard)

### Direct Access
Simply open:
```
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/live
```

---

## 🔧 TROUBLESHOOTING

### Issue: "localhost refused to connect"
**Problem**: Trying to access localhost URLs
**Solution**: Use the preview URL instead:
```
❌ http://localhost:3000/live
✅ https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/live
```

### Issue: 502 Bad Gateway
**Problem**: Backend not responding on correct port
**Solution**: Ensure backend is on port 8001:
```bash
# Check supervisor config
cat /etc/supervisor/conf.d/supervisord.conf | grep port

# Should show: --port 8001

# Restart if needed
supervisorctl restart backend
```

### Issue: Paper Trading data not loading
**Problem**: Frontend pointing to wrong backend URL
**Solution**: Check `/app/trading_system/frontend/.env`:
```env
# Should be preview URL, NOT localhost
REACT_APP_BACKEND_URL=https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com
```

### Issue: Services not starting
**Problem**: Supervisor configuration issue
**Solution**:
```bash
# Reload supervisor config
supervisorctl reread
supervisorctl update

# Restart all
supervisorctl restart all
```

---

## 📊 EXPECTED DATA ON /live PAGE

### Paper Trading Panel Should Show:
- **Header**: "PAPER TRADING ENGINE" with green RUNNING badge
- **Stats Row**:
  - Equity: $10,000.00
  - Total P&L: +$0.00 (+0.00%)
  - Drawdown: 0.00% (Max: 15%)
  - Total Trades: 0
  - Risk Status: ENABLED
  
- **Open Positions (2)**:
  - GOLD: SHORT @ $414.69 (3.01 shares)
  - SPY: SHORT @ $634.08 (3.15 shares)
  
- **Recent Trades**:
  - Last 10 trades in table format
  - Currently showing 1 trade: GOLD SHORT

---

## 🚀 QUICK START

### Step 1: Open Browser
Navigate to:
```
https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com
```

### Step 2: Click LIVE TRADING
Click the green "LIVE TRADING" button in the top navigation bar.

### Step 3: View Paper Trading Dashboard
You should see:
- Paper Trading Engine panel
- Live stats updating every 30 seconds
- Open positions
- Recent trades

---

## 📱 BOOKMARKABLE LINKS

Save these for quick access:

### Main Pages
- **Home (Bot Builder)**: https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com
- **Live Trading Monitor**: https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/live
- **Analyze Bot**: https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/analyze-bot
- **Strategy Library**: https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/library
- **Portfolio**: https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/portfolio

### API Endpoints
- **API Docs**: https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/docs
- **Paper Trading Status**: https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/api/paper-trading/status
- **Paper Trading Trades**: https://bcc4190e-0a60-4cb9-90e6-4fdeca0495ba.preview.emergentagent.com/api/paper-trading/trades

---

## ✅ FINAL VERIFICATION

### Test Everything Works:

1. **Open main URL**: Should load Bot Factory
2. **Click LIVE TRADING**: Should navigate to /live
3. **Check Paper Trading panel**: Should show $10,000 equity
4. **Check status**: Should show RUNNING
5. **Check positions**: Should show 2 open positions (GOLD, SPY)
6. **Wait 30 seconds**: Data should auto-refresh

**If all checks pass**: ✅ System is fully operational!

---

## 📞 NEED HELP?

If you encounter issues:
1. Check supervisor status: `supervisorctl status`
2. Check logs: `tail -f /var/log/supervisor/*.log`
3. Verify you're using the PREVIEW URL (not localhost)
4. Restart services: `supervisorctl restart all`

---

**Last Updated**: March 29, 2026
**System Status**: ✅ FULLY OPERATIONAL
**Access Type**: Cloud-Hosted (Preview URL)
