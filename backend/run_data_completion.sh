#!/bin/bash
#
# Quick Start Script for Dukascopy Data Download
# 
# This script runs the complete workflow:
# 1. Gap analysis
# 2. Download missing data
# 3. Process to candles
# 4. Re-validate
#

set -e  # Exit on error

echo "================================================================================"
echo "DUKASCOPY DATA COMPLETION WORKFLOW"
echo "================================================================================"
echo ""

# Change to backend directory
cd /app/trading_system/backend

# Step 1: Gap Analysis
echo "📊 STEP 1: Running gap analysis..."
echo ""
python analyze_data_gaps.py
echo ""
echo "✅ Gap analysis complete"
echo ""
read -p "Press Enter to continue to download missing data..."
echo ""

# Step 2: Download Missing Data
echo "================================================================================"
echo "📥 STEP 2: Downloading missing data..."
echo ""
python download_missing_dukascopy_data.py
echo ""

# Step 3: Verify Improvements
echo "================================================================================"
echo "📊 STEP 3: Verifying improvements..."
echo ""
python analyze_data_gaps.py
echo ""

# Step 4: Process to Candles
echo "================================================================================"
echo "📈 STEP 4: Processing bi5 files to candles..."
echo ""
read -p "Process new data to candles? This may take 10-20 minutes. (yes/no): " process_choice

if [ "$process_choice" = "yes" ]; then
    python process_bi5_to_candles.py
    echo ""
    echo "✅ Processing complete"
else
    echo "⏭️  Skipped processing"
fi
echo ""

# Step 5: Re-validate
echo "================================================================================"
echo "🧪 STEP 5: Re-running validation..."
echo ""
read -p "Run validation on improved dataset? This may take 5-10 minutes. (yes/no): " validate_choice

if [ "$validate_choice" = "yes" ]; then
    rm -f /app/validation_checkpoint.json  # Clear old checkpoint
    python incremental_validation.py
    echo ""
    echo "✅ Validation complete"
else
    echo "⏭️  Skipped validation"
fi
echo ""

# Summary
echo "================================================================================"
echo "WORKFLOW COMPLETE"
echo "================================================================================"
echo ""
echo "📁 Generated Files:"
echo "   - /app/trading_system/DATA_GAP_ANALYSIS.json (updated)"
echo "   - /app/trading_system/DATA_GAP_REPORT.md (updated)"
echo "   - /app/trading_system/download_checkpoint.json (progress)"
echo ""
echo "📊 Next Steps:"
echo "   1. Review updated gap analysis report"
echo "   2. Compare validation results (before vs after)"
echo "   3. Determine if data quality was the issue"
echo ""
echo "🎯 If validation still fails, the issue is strategy design, not data quality."
echo ""
