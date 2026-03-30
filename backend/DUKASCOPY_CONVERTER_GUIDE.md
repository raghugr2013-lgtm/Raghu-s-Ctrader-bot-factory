# Dukascopy .bi5 to CSV Converter - Usage Guide

## Overview
Convert Dukascopy binary tick data (.bi5 files) to clean OHLC CSV format for backtesting.

## Installation

Required packages:
```bash
pip install pandas numpy
```

## File Structure

### Expected Input Structure:
```
input_folder/
├── 2024/
│   ├── 01/
│   │   ├── 01/
│   │   │   ├── 00h_ticks.bi5
│   │   │   ├── 01h_ticks.bi5
│   │   │   ├── ...
│   │   │   └── 23h_ticks.bi5
│   │   ├── 02/
│   │   └── ...
│   └── ...
└── ...
```

### Output Format:
```csv
time,open,high,low,close,volume
2024-01-01 00:00:00,1.10500,1.10550,1.10450,1.10520,1000
2024-01-01 01:00:00,1.10520,1.10600,1.10500,1.10580,1200
...
```

---

## Usage

### Method 1: Single Symbol Conversion

```bash
# Convert EURUSD to 1H candles
python dukascopy_bi5_converter.py \
  --input /data/EURUSD \
  --output eurusd_h1.csv \
  --symbol EURUSD \
  --timeframe 1H

# Convert XAUUSD to 4H candles
python dukascopy_bi5_converter.py \
  --input /data/XAUUSD \
  --output xauusd_h4.csv \
  --symbol XAUUSD \
  --timeframe 4H
```

### Method 2: Batch Conversion

Create a config file `conversion_config.json`:

```json
[
  {
    "symbol": "EURUSD",
    "input_folder": "EURUSD",
    "output_file": "eurusd_h1.csv",
    "timeframe": "1H"
  },
  {
    "symbol": "XAUUSD",
    "input_folder": "XAUUSD",
    "output_file": "xauusd_h1.csv",
    "timeframe": "1H"
  },
  {
    "symbol": "GBPUSD",
    "input_folder": "GBPUSD",
    "output_file": "gbpusd_h1.csv",
    "timeframe": "1H"
  }
]
```

Run batch conversion:
```bash
python batch_convert_bi5.py \
  --input-dir /data/dukascopy \
  --output-dir /output/csv \
  --config conversion_config.json
```

---

## Command-Line Options

### dukascopy_bi5_converter.py

| Option | Description | Example |
|--------|-------------|---------|
| `--input, -i` | Input folder with .bi5 files | `/data/EURUSD` |
| `--output, -o` | Output CSV file | `eurusd_h1.csv` |
| `--symbol, -s` | Trading symbol | `EURUSD` |
| `--timeframe, -t` | Target timeframe | `1H`, `4H`, `1D`, `15T` |
| `--point, -p` | Point value (optional) | `0.00001` |
| `--no-fill` | Don't fill missing candles | - |
| `--verbose, -v` | Verbose logging | - |

### Supported Timeframes

| Timeframe | Pandas Code | Description |
|-----------|-------------|-------------|
| 1 minute | `1T` | 1-minute candles |
| 5 minutes | `5T` | 5-minute candles |
| 15 minutes | `15T` | 15-minute candles |
| 30 minutes | `30T` | 30-minute candles |
| 1 hour | `1H` | 1-hour candles |
| 4 hours | `4H` | 4-hour candles |
| 1 day | `1D` | Daily candles |

---

## Point Values (Auto-Detected)

The script automatically detects point values based on symbol:

| Symbol Type | Point Value | Example Symbols |
|-------------|-------------|-----------------|
| Major Forex (5 decimals) | 0.00001 | EURUSD, GBPUSD, AUDUSD |
| JPY Pairs (3 decimals) | 0.001 | USDJPY, EURJPY, GBPJPY |
| Gold (2 decimals) | 0.01 | XAUUSD |

You can override with `--point` if needed.

---

## Features

### ✅ Missing Data Handling
- Automatically fills gaps in data using forward fill
- Ensures no missing timestamps
- Creates continuous time series

### ✅ Data Validation
- Removes NaN values
- Validates OHLC integrity (high ≥ low, etc.)
- Sorts by timestamp
- Checks for invalid candles

### ✅ Output Quality
- Clean CSV format
- Proper decimal precision
- Ready for backtesting
- No data gaps

---

## Examples

### Example 1: Standard EURUSD H1 Conversion
```bash
python dukascopy_bi5_converter.py \
  --input /data/dukascopy/EURUSD \
  --output /output/eurusd_h1.csv \
  --symbol EURUSD \
  --timeframe 1H
```

### Example 2: XAUUSD with Custom Point Value
```bash
python dukascopy_bi5_converter.py \
  --input /data/dukascopy/XAUUSD \
  --output /output/xauusd_h1.csv \
  --symbol XAUUSD \
  --timeframe 1H \
  --point 0.01
```

### Example 3: 15-Minute Candles with Verbose Output
```bash
python dukascopy_bi5_converter.py \
  --input /data/dukascopy/GBPUSD \
  --output /output/gbpusd_15m.csv \
  --symbol GBPUSD \
  --timeframe 15T \
  --verbose
```

### Example 4: Batch Convert Multiple Symbols
```bash
python batch_convert_bi5.py \
  --input-dir /data/dukascopy \
  --output-dir /output/csv
```

---

## Troubleshooting

### Issue: "No .bi5 files found"
**Solution**: Check that input folder contains proper Dukascopy structure (YYYY/MM/DD/HH/)

### Issue: "Failed to decompress .bi5 file"
**Solution**: File may be corrupted. Re-download from Dukascopy or try different date range.

### Issue: "Point value seems incorrect"
**Solution**: Use `--point` to manually specify point value for your symbol.

### Issue: "Too many NaN values"
**Solution**: Source data may have gaps. Script will forward-fill, but very large gaps may indicate data quality issues.

---

## Output Validation

After conversion, verify your CSV:

```bash
# Check file size
ls -lh eurusd_h1.csv

# View first 10 rows
head -n 10 eurusd_h1.csv

# Count candles
wc -l eurusd_h1.csv

# Check for NaN values
grep -i "nan" eurusd_h1.csv
```

Expected output:
- File size: Several MB for months of H1 data
- No "NaN" or empty values
- Continuous timestamps with no gaps

---

## Integration with Bot Factory

After generating CSV files, import them into the Bot Factory system:

### Option 1: API Upload
Use the market data import endpoint to upload CSV files programmatically.

### Option 2: Manual Import
Place CSV files in `/app/trading_system/backend/market_data/` and import via UI.

### Option 3: Direct MongoDB Insert
Use the provided import script to load data directly into MongoDB.

---

## Performance

### Typical Processing Times:
- 1 month of tick data → ~30 seconds
- 1 year of tick data → ~5-10 minutes
- Multiple symbols (batch) → Parallel processing available

### Memory Requirements:
- Processing 1 year of H1 candles: ~200MB RAM
- Large tick datasets: Up to 2GB RAM

---

## License & Attribution

This script is designed for use with Dukascopy historical data.
Data source: https://www.dukascopy.com/swiss/english/marketwatch/historical/

Ensure compliance with Dukascopy's terms of service when using their data.
