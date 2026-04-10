# Dukascopy Auto-Download Feature

## Overview

The Dukascopy Auto-Download feature allows users to directly download historical tick data from Dukascopy's public datafeed and automatically convert it to M1 (1-minute) candles, maintaining strict M1 Single Source of Truth (SSOT) compliance.

## Features

### ✅ Data Acquisition
- **Source**: Dukascopy historical tick data (BI5 format)
- **Process**: Download BI5 files → Decode ticks → Aggregate to M1 → Store in database
- **Confidence**: HIGH (direct tick data, no interpolation)

### ✅ User Interface
- **Symbol Selection**: Choose from EURUSD, XAUUSD, GBPUSD, USDJPY, NAS100
- **Date Range**: Select start and end dates
- **Download Estimation**: Preview total hours, size, time, and expected M1 candles
- **Real-time Progress**: Live updates every 2 seconds showing:
  - Progress percentage
  - Hours completed/total
  - Successful/failed downloads
  - M1 candles stored
  - Error list

### ✅ Error Handling
- Automatic retry logic (up to 3 attempts per hour)
- Skip corrupted or missing files
- Continue processing on errors
- Graceful handling of weekends/holidays (404 responses expected)

## Architecture

### Backend Components

#### 1. `dukascopy_downloader.py`
**Location**: `/app/backend/data_ingestion/dukascopy_downloader.py`

**Key Classes**:
- `DukascopyDownloader`: Main downloader class
  - `download_hour(symbol, hour)`: Download single hour of tick data
  - `download_range(symbol, start_date, end_date)`: Download entire date range
  - `estimate_data_size(symbol, start_date, end_date)`: Calculate estimates

**URL Structure**:
```
https://datafeed.dukascopy.com/datafeed/{SYMBOL}/{YEAR}/{MONTH_0_INDEXED}/{DAY}/{HOUR}h_ticks.bi5
```

**Important**: Month is 0-indexed (January=00, February=01, ..., December=11)

**Example**:
```
EURUSD, 2025-01-15 10:00 UTC
→ https://datafeed.dukascopy.com/datafeed/EURUSD/2025/00/15/10h_ticks.bi5
```

#### 2. API Endpoints
**Location**: `/app/backend/data_ingestion/data_ingestion_router.py`

**New Endpoints**:

##### POST `/api/v2/data/download/dukascopy`
Start a background download job.

**Request Body**:
```json
{
  "symbol": "EURUSD",
  "start_date": "2024-01-15T00:00:00",
  "end_date": "2024-01-16T00:00:00"
}
```

**Response**:
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "symbol": "EURUSD",
  "start_date": "2024-01-15T00:00:00+00:00",
  "end_date": "2024-01-16T00:00:00+00:00",
  "estimated_hours": 25,
  "estimated_size_mb": 2.44,
  "message": "Download job started. Track progress at /download/status/{job_id}",
  "status": "queued"
}
```

##### GET `/api/v2/data/download/status/{job_id}`
Check progress of a download job.

**Response**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "symbol": "EURUSD",
  "status": "running",
  "progress_percent": 45.2,
  "current_hour": "2024-01-15T10:00:00+00:00",
  "hours_completed": 11,
  "hours_total": 25,
  "hours_successful": 9,
  "hours_failed": 2,
  "candles_stored": 540,
  "current_status": "Downloading 2024-01-15 10:00",
  "errors": [
    "2024-01-15T03:00:00: No data available"
  ],
  "completed": false
}
```

##### GET `/api/v2/data/download/estimate`
Estimate download size before starting.

**Query Parameters**:
- `symbol`: Trading symbol (e.g., EURUSD)
- `start_date`: Start date ISO format
- `end_date`: End date ISO format

**Response**:
```json
{
  "symbol": "EURUSD",
  "start_date": "2024-01-15T00:00:00+00:00",
  "end_date": "2024-01-16T00:00:00+00:00",
  "total_hours": 25,
  "total_days": 1.04,
  "estimated_size_mb": 2.44,
  "estimated_time_minutes": 0.4,
  "estimated_m1_candles": 1500,
  "warnings": [
    "Actual size may vary based on market activity",
    "Weekends and holidays will have no data (expected)",
    "Download time depends on network speed and Dukascopy server load"
  ]
}
```

#### 3. Background Processing
**Function**: `execute_dukascopy_download(job_id, symbol, start_date, end_date)`

**Flow**:
1. Initialize `DukascopyDownloader` and `BI5Processor`
2. Generate list of hours in date range
3. For each hour:
   - Download BI5 file from Dukascopy
   - Decode tick data
   - Aggregate ticks to M1 candles
   - Store in `market_candles_m1` collection
   - Update progress tracker
4. Mark job as completed

**Progress Tracking**: In-memory dictionary `download_jobs` stores real-time progress for each job.

### Frontend Components

#### Location
`/app/frontend/src/pages/MarketDataPage.jsx`

#### New Tab: "Dukascopy"
Added between "Upload" and "Coverage" tabs.

#### State Management
```javascript
// Download states
const [dukascopySymbol, setDukascopySymbol] = useState('EURUSD');
const [dukascopyStartDate, setDukascopyStartDate] = useState('');
const [dukascopyEndDate, setDukascopyEndDate] = useState('');
const [downloadJobId, setDownloadJobId] = useState(null);
const [downloadProgress, setDownloadProgress] = useState(null);
const [downloadingDukascopy, setDownloadingDukascopy] = useState(false);
const [showDownloadEstimate, setShowDownloadEstimate] = useState(null);
```

#### Key Functions

##### `estimateDukascopyDownload()`
Calls estimate endpoint and displays:
- Total hours
- Total days
- Estimated size (MB)
- Estimated time (minutes)
- Estimated M1 candles

##### `startDukascopyDownload()`
Initiates download job and starts progress polling.

##### Progress Polling
```javascript
useEffect(() => {
  if (downloadJobId && !downloadProgress?.completed) {
    const interval = setInterval(async () => {
      const response = await axios.get(`${API_V2}/download/status/${downloadJobId}`);
      setDownloadProgress(response.data);
      
      if (response.data.completed) {
        setDownloadingDukascopy(false);
        // Show completion toast
      }
    }, 2000); // Poll every 2 seconds
    
    return () => clearInterval(interval);
  }
}, [downloadJobId, downloadProgress?.completed]);
```

## Usage Example

### Via Frontend UI

1. Navigate to **Market Data** page
2. Click **Dukascopy** tab
3. Select:
   - Symbol: EURUSD
   - Start Date: 2024-01-15
   - End Date: 2024-01-16
4. Click **Estimate Download** to preview
5. Click **Start Download**
6. Monitor real-time progress
7. Download completes → M1 candles stored in database

### Via API

```bash
# 1. Start download
curl -X POST https://your-app.com/api/v2/data/download/dukascopy \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "start_date": "2024-01-15T00:00:00",
    "end_date": "2024-01-16T00:00:00"
  }'

# Response: {"success": true, "job_id": "abc-123-xyz", ...}

# 2. Check progress
curl https://your-app.com/api/v2/data/download/status/abc-123-xyz

# 3. Verify data stored
curl https://your-app.com/api/v2/data/coverage/EURUSD
```

## M1 SSOT Compliance

### ✅ Rules Enforced
- **ONLY M1 stored**: Tick data is aggregated to M1, never higher timeframes
- **NO interpolation**: Missing minutes are left as gaps
- **HIGH confidence**: All Dukascopy data tagged with HIGH confidence
- **Direct tick source**: No synthetic data generation

### Database Storage
Collection: `market_candles_m1`

Document structure:
```javascript
{
  "symbol": "EURUSD",
  "timestamp": ISODate("2024-01-15T10:00:00Z"),
  "open": 1.08923,
  "high": 1.08945,
  "low": 1.08915,
  "close": 1.08932,
  "volume": 1250.5,
  "metadata": {
    "source": "dukascopy",
    "confidence": "high",
    "original_timeframe": "tick",
    "upload_batch_id": "550e8400-e29b-41d4-a716-446655440000",
    "validation_score": 1.0,
    "tick_count": 342
  }
}
```

## Configuration

### Backend Settings
**File**: `/app/backend/data_ingestion/dukascopy_downloader.py`

```python
DukascopyDownloader(
    timeout_seconds=30,        # HTTP request timeout
    max_retries=3,            # Retry attempts per hour
    retry_delay_seconds=2.0   # Delay between retries
)
```

### Rate Limiting
- **Max date range**: 365 days (1 year)
- **Validation**: start_date must be before end_date

### Error Handling
- **404 responses**: Normal for weekends/holidays (not counted as errors)
- **5xx errors**: Trigger retry logic
- **Timeout errors**: Trigger retry logic
- **Corrupted files**: Skipped with warning

## Testing

### Test File
`/app/backend/tests/test_dukascopy_download.py`

### Test Coverage
- ✅ URL construction (all months, including edge cases)
- ✅ Symbol uppercase conversion
- ✅ Download estimate calculation
- ✅ Download job creation
- ✅ Status endpoint (valid/invalid job IDs)
- ✅ Date validation (invalid ranges rejected)
- ✅ Date range validation (>365 days rejected)
- ✅ Full integration flow with data storage

### Run Tests
```bash
cd /app/backend
python -m pytest tests/test_dukascopy_download.py -v
```

**Result**: 14/14 tests passed ✅

## Known Limitations

1. **Public data only**: No authentication required (Dukascopy public datafeed)
2. **Weekend/holiday gaps**: Expected behavior (forex markets closed)
3. **Network dependency**: Requires internet access to Dukascopy servers
4. **Processing time**: Large date ranges (months/years) take proportional time
5. **Max range**: 365 days per download job

## Future Enhancements

- [ ] Resume interrupted downloads
- [ ] Parallel hour downloads (currently sequential)
- [ ] Download queue management (multiple jobs)
- [ ] Scheduled automatic downloads
- [ ] Gap auto-fill using Dukascopy downloader
- [ ] WebSocket progress updates (instead of polling)
- [ ] Historical job logs

## Troubleshooting

### Issue: Download stuck at 0%
**Solution**: Check backend logs for BI5Decoder errors. Ensure `bi5_decoder.py` is available.

### Issue: All hours failing with 404
**Solution**: Verify date range isn't entirely on weekend. Check Dukascopy server availability.

### Issue: Progress not updating
**Solution**: Check frontend polling mechanism (2-second interval). Verify backend job_id exists in `download_jobs` dict.

### Issue: Low candles stored despite success
**Solution**: Check for market closures (weekends, holidays). This is expected behavior.

## References

- Dukascopy Historical Data: https://www.dukascopy.com/swiss/english/marketwatch/historical/
- BI5 File Format: https://limemojito.com/reading-dukascopy-bi5-tick-history-with-the-tradingdata-stream-library-for-java/
- M1 SSOT Architecture: `/app/FULL_SYSTEM_AUDIT_REPORT.md`

## Support

For issues or questions:
1. Check backend logs: `/var/log/supervisor/backend.*.log`
2. Check frontend console for API errors
3. Verify API health: `GET /api/v2/data/health`
4. Review test file for usage examples

---

**Last Updated**: April 10, 2026  
**Version**: 1.0  
**Status**: Production Ready ✅
