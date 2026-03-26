# DUKASCOPY MISSING DATA DOWNLOAD - INSTRUCTIONS

**Script:** `download_missing_dukascopy_data.py`  
**Purpose:** Download ONLY missing Dukascopy data identified in gap analysis  
**Date:** March 26, 2026

---

## 📋 PREREQUISITES

### 1. Gap Analysis Must Be Complete
```bash
# Verify gap analysis file exists
ls -lh /app/trading_system/DATA_GAP_ANALYSIS.json
```

If not found, run:
```bash
cd /app/trading_system/backend
python analyze_data_gaps.py
```

### 2. Python Dependencies
Required libraries (should already be installed):
- `requests` (for HTTP downloads)
- `lzma` (for bi5 decompression)
- `json`, `pathlib`, `datetime` (standard library)

---

## 🚀 RUNNING THE SCRIPT

### Step 1: Navigate to Directory
```bash
cd /app/trading_system/backend
```

### Step 2: Run the Downloader
```bash
python download_missing_dukascopy_data.py
```

### Step 3: Review Summary & Confirm
The script will display:
```
================================================================================
DUKASCOPY MISSING DATA DOWNLOADER
================================================================================

📊 Gap Analysis Summary:
   Total missing files: 659
   Date range: 2025-01-07 22:00:00 to 2026-02-24 21:00:00
   Output directory: /app/trading_system/dukascopy_data/EURUSD

📁 Checkpoint loaded: 0 files already processed

================================================================================
Start downloading? (yes/no):
```

Type `yes` and press Enter to start.

---

## 📊 WHAT THE SCRIPT DOES

### 1. **Reads Gap Analysis**
- Loads `/app/trading_system/DATA_GAP_ANALYSIS.json`
- Extracts all missing timestamps
- Total: 659 missing hourly files

### 2. **Checks Existing Files**
For each missing timestamp:
- ✅ Checks if file already exists
- ✅ Validates file size (> 100 bytes)
- ✅ Tests decompression (LZMA)
- ✅ Verifies tick data structure
- ⏭️  Skips if valid file exists

### 3. **Downloads Missing Files**
- Constructs Dukascopy URL
- Downloads with retry logic (3 attempts)
- Validates downloaded file
- Saves with correct naming: `YYYY_MM_DD_HH.bi5`

### 4. **Saves Progress**
- Checkpoint saved every 10 files
- Resume capability if interrupted
- Checkpoint file: `/app/trading_system/download_checkpoint.json`

---

## 📁 FILE LOCATIONS

### Input:
```
/app/trading_system/DATA_GAP_ANALYSIS.json
```

### Output:
```
/app/trading_system/dukascopy_data/EURUSD/
├── 2025_01_08_00.bi5
├── 2025_01_08_01.bi5
├── 2025_01_08_02.bi5
└── ... (659 files)
```

### Checkpoint:
```
/app/trading_system/download_checkpoint.json
```

---

## ⏱️ ESTIMATED TIME

### Download Speed:
- Dukascopy server: ~2-5 files/second
- With 3-retry logic: ~1-3 files/second average

### Total Time:
```
659 files ÷ 2 files/sec = ~5.5 minutes (best case)
659 files ÷ 1 file/sec = ~11 minutes (worst case)
```

**Actual time:** 5-15 minutes depending on network conditions

---

## 🔍 VALIDATION FEATURES

### File Size Check:
- ❌ Rejects files < 100 bytes
- ✅ Valid bi5 files are typically 1-50 KB

### Decompression Test:
- ✅ Uses `lzma.decompress()` to verify file integrity
- ❌ Rejects corrupted files

### Structure Validation:
- ✅ Checks if decompressed size is multiple of 20 bytes
- ✅ Verifies tick data can be parsed (struct format: '>IIIII')

### Retry Logic:
- 🔄 3 attempts per file
- ⏱️ 2-second delay between retries
- ⏱️ 30-second timeout per request

---

## 📊 PROGRESS TRACKING

### Real-Time Display:
```
[1/659] 2025-01-08 00:00 - Downloading...
      Attempt 1/3... ✅ Success (12,345 bytes)

[10/659] 2025-01-08 09:00 - ✅ Already exists (valid)
   Progress: 10/659 (1.5%) | Rate: 2.1 files/sec | ETA: 5.2 min
```

### Every 10 Files:
- Checkpoint saved
- Progress percentage
- Download rate (files/sec)
- ETA (estimated time remaining)

---

## ⚠️ HANDLING INTERRUPTIONS

### If Script is Interrupted:
1. **Progress is saved** in checkpoint file
2. **Re-run the script:**
   ```bash
   python download_missing_dukascopy_data.py
   ```
3. It will **resume from where it left off**

### Manual Checkpoint Reset:
If you want to start fresh:
```bash
rm /app/trading_system/download_checkpoint.json
```

---

## 📈 EXPECTED OUTPUT

### Success Case:
```
================================================================================
DOWNLOAD COMPLETE
================================================================================

📊 Statistics:
   Total files to download: 659
   Successfully downloaded:  650
   Skipped (already exist):  5
   Failed:                   4
   Validated:                650
   Invalid:                  0

⏱️  Time elapsed: 8.3 minutes
📈 Download rate: 78.3 files/min
```

### With Failures:
```
⚠️  4 files failed to download.
   You can re-run this script to retry failed downloads.
```

---

## 🔧 TROUBLESHOOTING

### Problem: "Gap analysis file not found"
**Solution:**
```bash
cd /app/trading_system/backend
python analyze_data_gaps.py
```

### Problem: "Connection timeout"
**Cause:** Slow network or Dukascopy server issues  
**Solution:**
- Script will auto-retry (3 attempts)
- If persists, wait and re-run script

### Problem: "HTTP 404 - Not found"
**Cause:** Data doesn't exist on Dukascopy server  
**Impact:** Some historical data may be unavailable  
**Solution:** These gaps will remain (not a script issue)

### Problem: "Validation failed"
**Cause:** Downloaded file is corrupted  
**Solution:** Script will retry; if persists, that file may be corrupted on server

### Problem: "Permission denied"
**Solution:**
```bash
chmod +x /app/trading_system/backend/download_missing_dukascopy_data.py
```

---

## ✅ VERIFICATION AFTER DOWNLOAD

### Step 1: Re-run Gap Analysis
```bash
cd /app/trading_system/backend
python analyze_data_gaps.py
```

**Expected Output:**
```
Missing hours: 9 (down from 659)
Data completeness: 99.87% (up from 90.81%)
```

Some files may still be missing (404 from Dukascopy).

### Step 2: Process New Data
```bash
python process_bi5_to_candles.py
```

This converts new bi5 files to OHLC candles in MongoDB.

### Step 3: Re-run Validation
```bash
python incremental_validation.py
```

Test strategies on the now-complete dataset.

---

## 📋 NEXT STEPS

### After Successful Download:

1. **Verify Data Quality:**
   ```bash
   python analyze_data_gaps.py
   ```
   Check if missing data percentage improved.

2. **Process to Candles:**
   ```bash
   python process_bi5_to_candles.py
   ```
   Convert bi5 → H1 candles in MongoDB.

3. **Re-validate Strategies:**
   ```bash
   python incremental_validation.py
   ```
   Test strategies on complete data.

4. **Compare Results:**
   - Before: 90.81% complete, -69% return
   - After: ~99%+ complete, ??? return
   - Determine if data quality was the issue

---

## 🎯 EXPECTED IMPROVEMENTS

### Data Completeness:
```
Before: 90.81% (659 missing hours)
After:  99%+   (~10-50 missing hours from 404s)
```

### Gap Impact:
```
Before: 57 gaps, largest = 574 hours
After:  ~5-10 gaps, largest = ~24 hours
```

### Backtest Reliability:
- More continuous data
- Fewer artificial discontinuities
- Better statistical significance
- More representative of live trading

---

## ⚡ QUICK START

**Full command sequence:**
```bash
cd /app/trading_system/backend

# Run gap analysis (if not done)
python analyze_data_gaps.py

# Download missing data
python download_missing_dukascopy_data.py
# (type 'yes' when prompted)

# Wait 5-15 minutes for download...

# Verify improvements
python analyze_data_gaps.py

# Process new data
python process_bi5_to_candles.py

# Re-run validation
python incremental_validation.py
```

---

## 📞 SUPPORT

### Issues?
1. Check `/tmp/` for error logs
2. Verify internet connection
3. Check Dukascopy server status: https://www.dukascopy.com
4. Re-run with `--verbose` flag (if added)

---

**Script Location:** `/app/trading_system/backend/download_missing_dukascopy_data.py`  
**Documentation:** `/app/trading_system/DOWNLOAD_INSTRUCTIONS.md`  
**Gap Analysis:** `/app/trading_system/DATA_GAP_ANALYSIS.json`
