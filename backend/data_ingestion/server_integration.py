"""
Server Integration - Add M1 SSOT Data Architecture to Main Server

This file provides the integration code to add to server.py.

INTEGRATION STEPS:
1. Add imports at top of server.py
2. Initialize DataServiceV2 after db connection
3. Include data_ingestion_router
4. Update existing data consumers to use new service
"""

# ==============================================================================
# ADD TO TOP OF server.py (imports section)
# ==============================================================================

SERVER_IMPORTS = """
# M1 SSOT Data Architecture
from data_ingestion import (
    DataServiceV2,
    data_ingestion_router,
    init_data_ingestion_router,
    BacktestDataAdapter,
    DataQualityError,
    ConfidenceLevel,
    ConfidenceRules
)
"""

# ==============================================================================
# ADD AFTER db CONNECTION (after market_data_service init)
# ==============================================================================

SERVICE_INITIALIZATION = """
# Initialize M1 SSOT Data Service
data_service_v2 = DataServiceV2(db)
init_data_ingestion_router(data_service_v2)
"""

# ==============================================================================
# ADD IN ROUTER REGISTRATION SECTION
# ==============================================================================

ROUTER_REGISTRATION = """
# M1 SSOT Data Ingestion Router (v2)
app.include_router(data_ingestion_router)
"""

# ==============================================================================
# MIGRATION NOTES
# ==============================================================================

MIGRATION_NOTES = """
MIGRATION GUIDE: Moving to M1 SSOT Architecture
================================================

1. DATA STORAGE:
   - OLD: Multiple collections (market_candles_m1, market_candles_h1, etc.)
   - NEW: Single collection (market_candles_m1 only)

2. DATA RETRIEVAL:
   - OLD: Direct query for each timeframe
   - NEW: Use data_service_v2.get_candles() for ALL timeframes
   
   Example:
   ```python
   # OLD
   candles = await db.market_candles_h1.find({...}).to_list()
   
   # NEW
   result = await data_service_v2.get_candles(
       symbol="EURUSD",
       timeframe="H1",
       start_date=start,
       end_date=end,
       min_confidence="high"
   )
   candles = result.candles
   ```

3. DATA INGESTION:
   - OLD: Direct CSV upload to any timeframe collection
   - NEW: Only M1/BI5 accepted, use /api/v2/data/upload/* endpoints

4. BACKTEST INTEGRATION:
   - OLD: Query any timeframe directly
   - NEW: Use BacktestDataAdapter for quality-controlled data
   
   Example:
   ```python
   adapter = BacktestDataAdapter(data_service_v2)
   candles, quality = await adapter.get_backtest_data(
       symbol="EURUSD",
       timeframe="H1",
       start_date=start,
       end_date=end
   )
   ```

5. CONFIDENCE CHECKING:
   - Production backtest: min_confidence="high" (enforced)
   - Research/exploration: min_confidence="medium" or "low"
   
6. GAP HANDLING:
   - OLD: Gap fill could use synthetic data
   - NEW: Gaps only filled with real Dukascopy data
   - Use: POST /api/v2/data/gaps/{symbol}/fix

7. ENDPOINTS DEPRECATED (use v2):
   - /api/data/upload → /api/v2/data/upload/csv or /api/v2/data/upload/bi5
   - /api/data/{symbol}/{timeframe} → /api/v2/data/candles/{symbol}/{timeframe}

8. NEW ENDPOINTS:
   - GET  /api/v2/data/candles/{symbol}/{timeframe} - Get aggregated candles
   - POST /api/v2/data/upload/bi5 - Upload BI5 tick files
   - POST /api/v2/data/upload/csv - Upload M1 CSV (higher TF rejected)
   - GET  /api/v2/data/coverage/{symbol} - Get coverage report
   - GET  /api/v2/data/quality/{symbol} - Get quality report
   - GET  /api/v2/data/gaps/{symbol}/detect - Detect gaps
   - POST /api/v2/data/gaps/{symbol}/fix - Fix gaps with real data
   - DELETE /api/v2/data/purge/{symbol}/low-confidence - Remove low quality data
   - GET  /api/v2/data/health - Health check
"""

def print_integration_guide():
    """Print full integration guide"""
    print("=" * 70)
    print("M1 SSOT DATA ARCHITECTURE - SERVER INTEGRATION GUIDE")
    print("=" * 70)
    print("\n1. ADD IMPORTS:\n")
    print(SERVER_IMPORTS)
    print("\n2. ADD SERVICE INITIALIZATION:\n")
    print(SERVICE_INITIALIZATION)
    print("\n3. ADD ROUTER REGISTRATION:\n")
    print(ROUTER_REGISTRATION)
    print("\n4. MIGRATION NOTES:")
    print(MIGRATION_NOTES)
    print("=" * 70)


if __name__ == "__main__":
    print_integration_guide()
