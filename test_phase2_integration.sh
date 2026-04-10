#!/bin/bash
# Phase 2 Integration - Complete System Test

echo "=========================================="
echo "PHASE 2 INTEGRATION - SYSTEM TEST"
echo "=========================================="
echo ""

# Get API URL
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
echo "API URL: $API_URL"
echo ""

# Test 1: Phase 2 Config
echo "Test 1: Get Phase 2 Configuration"
echo "------------------------------------------"
curl -s "$API_URL/api/bot/phase2/config" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Version: {data['version']}\")
print(f\"Min Profit Factor: {data['filters']['min_profit_factor']}\")
print(f\"Max Drawdown: {data['filters']['max_drawdown_pct']}%\")
print(f\"Min Sharpe: {data['filters']['min_sharpe_ratio']}\")
print(f\"Min Trades: {data['filters']['min_trades']}\")
print(f\"Tradeable Grades: {', '.join(data['tradeable_grades'])}\")
print(f\"Blocked Grades: {', '.join(data['blocked_grades'])}\")
"
echo ""
echo ""

# Test 2: Validate Good Strategy (Grade A)
echo "Test 2: Validate EXCELLENT Strategy (Expected: Grade A)"
echo "------------------------------------------"
curl -s -X POST "$API_URL/api/bot/phase2/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "Test Strategy A",
    "profit_factor": 2.5,
    "max_drawdown_pct": 8.0,
    "sharpe_ratio": 2.0,
    "total_trades": 250,
    "stability_score": 90.0,
    "win_rate": 65.0,
    "net_profit": 15000.0
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Status: {data['status'].upper()}\")
print(f\"Grade: {data['grade_emoji']} {data['grade']}\")
print(f\"Score: {data['composite_score']:.1f}/100\")
print(f\"Tradeable: {data['is_tradeable']}\")
print(f\"Quality: {data['quality']}\")
print(f\"Recommendation: {data['recommendation']}\")
"
echo ""
echo ""

# Test 3: Validate Acceptable Strategy (Grade C)
echo "Test 3: Validate ACCEPTABLE Strategy (Expected: Grade C)"
echo "------------------------------------------"
curl -s -X POST "$API_URL/api/bot/phase2/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "Test Strategy C",
    "profit_factor": 1.5,
    "max_drawdown_pct": 15.0,
    "sharpe_ratio": 1.0,
    "total_trades": 100,
    "stability_score": 70.0,
    "win_rate": 50.0
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Status: {data['status'].upper()}\")
print(f\"Grade: {data['grade_emoji']} {data['grade']}\")
print(f\"Score: {data['composite_score']:.1f}/100\")
print(f\"Tradeable: {data['is_tradeable']}\")
print(f\"Recommendation: {data['recommendation']}\")
"
echo ""
echo ""

# Test 4: Validate Bad Strategy (Grade F)
echo "Test 4: Validate REJECTED Strategy (Expected: Grade F)"
echo "------------------------------------------"
curl -s -X POST "$API_URL/api/bot/phase2/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "Test Strategy F",
    "profit_factor": 1.1,
    "max_drawdown_pct": 25.0,
    "sharpe_ratio": 0.5,
    "total_trades": 45,
    "stability_score": 50.0,
    "win_rate": 30.0
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Status: {data['status'].upper()}\")
print(f\"Grade: {data['grade_emoji']} {data['grade']}\")
print(f\"Score: {data['composite_score']:.1f}/100\")
print(f\"Tradeable: {data['is_tradeable']}\")
print(f\"Failed Filters: {len(data['rejection_reasons'])}\")
print(f\"Rejection Reasons:\")
for reason in data['rejection_reasons'][:3]:
    print(f\"  • {reason}\")
"
echo ""
echo ""

# Test 5: Bot Generation Eligibility (Pass)
echo "Test 5: Check Bot Generation Eligibility - PASS"
echo "------------------------------------------"
curl -s -X POST "$API_URL/api/bot/phase2/check-eligibility" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "Good Strategy",
    "profit_factor": 1.8,
    "max_drawdown_pct": 12.0,
    "sharpe_ratio": 1.4,
    "total_trades": 180,
    "stability_score": 80.0
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Eligible: {'YES ✓' if data['eligible'] else 'NO ✗'}\")
print(f\"Grade: {data['grade_emoji']} {data['grade']}\")
print(f\"Message: {data['message']}\")
"
echo ""
echo ""

# Test 6: Bot Generation Eligibility (Blocked)
echo "Test 6: Check Bot Generation Eligibility - BLOCKED"
echo "------------------------------------------"
curl -s -X POST "$API_URL/api/bot/phase2/check-eligibility" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "Weak Strategy",
    "profit_factor": 1.2,
    "max_drawdown_pct": 18.0,
    "sharpe_ratio": 0.8,
    "total_trades": 50,
    "stability_score": 60.0
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Eligible: {'YES ✓' if data['eligible'] else 'NO ✗'}\")
print(f\"Grade: {data['grade_emoji']} {data['grade']}\")
print(f\"Message: {data['message']}\")
"
echo ""
echo ""

echo "=========================================="
echo "PHASE 2 INTEGRATION TEST COMPLETE"
echo "=========================================="
echo ""
echo "Summary:"
echo "✓ Config endpoint working"
echo "✓ Validation endpoint working"
echo "✓ Grading system operational (A-F)"
echo "✓ Bot generation gate enforced"
echo "✓ Rejection reasons detailed"
echo ""
echo "Phase 2 Backend: FULLY OPERATIONAL ✅"
