"""
Auto-Fetch Market Data Module
CRITICAL: Ensures real market data is ALWAYS used for backtests/validation.
Never falls back to mock data silently.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from market_data_models import Candle, DataTimeframe
from market_data_provider import AlphaVantageProvider

logger = logging.getLogger(__name__)

# Minimum candles required for a valid backtest
MIN_CANDLES_REQUIRED = 60

# Data providers in priority order
PROVIDERS = ["twelve_data", "alpha_vantage"]


class DataFetchResult:
    """Result of auto-fetch operation"""
    def __init__(self):
        self.success: bool = False
        self.candles: List[Candle] = []
        self.source: str = ""  # "cache", "twelve_data", "alpha_vantage"
        self.warning: Optional[str] = None
        self.error: Optional[str] = None
        self.is_mock: bool = False  # NEVER should be True
        self.candle_count: int = 0
        
    def to_dict(self):
        return {
            "success": self.success,
            "source": self.source,
            "candle_count": self.candle_count,
            "warning": self.warning,
            "error": self.error,
            "is_real_data": not self.is_mock,
        }


async def auto_fetch_candles(
    db,
    market_data_service,
    symbol: str,
    timeframe: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    min_candles: int = MIN_CANDLES_REQUIRED,
) -> DataFetchResult:
    """
    Auto-fetch real market data with multi-provider fallback.
    
    Flow:
    1. Check MongoDB cache first
    2. If insufficient, try Twelve Data API
    3. If Twelve Data fails, try Alpha Vantage API
    4. If ALL fail, return error (NEVER use mock data)
    
    Returns DataFetchResult with success/error status
    """
    result = DataFetchResult()
    symbol = symbol.upper()
    
    # Parse timeframe
    try:
        tf = DataTimeframe(timeframe)
    except ValueError:
        result.error = f"Invalid timeframe: {timeframe}"
        return result
    
    # Default date range (2 years back)
    if not start_date:
        start_date = datetime.now(timezone.utc) - timedelta(days=730)
    if not end_date:
        end_date = datetime.now(timezone.utc)
    
    # ============================================================
    # STEP 1: Check cache (includes Dukascopy processed candles)
    # ============================================================
    try:
        cached = await market_data_service.get_candles(
            symbol=symbol,
            timeframe=tf,
            start_date=start_date,
            end_date=end_date,
            limit=20000,
        )
        
        if cached and len(cached) >= min_candles:
            # Check if data is from Dukascopy (preferred source)
            source_type = "cache"
            if cached and hasattr(cached[0], 'source'):
                if cached[0].source == "dukascopy":
                    source_type = "dukascopy_cache"
            
            logger.info(f"Cache hit ({source_type}): {len(cached)} candles for {symbol} {timeframe}")
            result.success = True
            result.candles = cached
            result.source = source_type
            result.candle_count = len(cached)
            return result
        else:
            logger.info(f"Cache insufficient: {len(cached) if cached else 0} candles (need {min_candles})")
    except Exception as e:
        logger.warning(f"Cache check error: {e}")
    
    # ============================================================
    # STEP 2: Try Twelve Data API
    # ============================================================
    twelve_data_key = os.environ.get("TWELVE_DATA_KEY")
    if twelve_data_key:
        try:
            candles = await _fetch_from_twelvedata(
                twelve_data_key, symbol, timeframe, market_data_service
            )
            if candles and len(candles) >= min_candles:
                result.success = True
                result.candles = candles
                result.source = "twelve_data"
                result.candle_count = len(candles)
                logger.info(f"Twelve Data success: {len(candles)} candles for {symbol} {timeframe}")
                return result
            else:
                logger.warning(f"Twelve Data returned insufficient data: {len(candles) if candles else 0}")
        except Exception as e:
            logger.warning(f"Twelve Data fetch failed: {e}")
    else:
        logger.warning("TWELVE_DATA_KEY not configured")
    
    # ============================================================
    # STEP 3: Try Alpha Vantage API
    # ============================================================
    alpha_key = os.environ.get("ALPHA_VANTAGE_KEY")
    if alpha_key:
        try:
            candles = await _fetch_from_alphavantage(
                alpha_key, symbol, tf, start_date, end_date, market_data_service
            )
            if candles and len(candles) >= min_candles:
                result.success = True
                result.candles = candles
                result.source = "alpha_vantage"
                result.candle_count = len(candles)
                logger.info(f"Alpha Vantage success: {len(candles)} candles for {symbol} {timeframe}")
                return result
            else:
                logger.warning(f"Alpha Vantage returned insufficient data: {len(candles) if candles else 0}")
        except Exception as e:
            logger.warning(f"Alpha Vantage fetch failed: {e}")
    else:
        logger.warning("ALPHA_VANTAGE_KEY not configured")
    
    # ============================================================
    # STEP 4: ALL PROVIDERS FAILED - Return error
    # ============================================================
    result.success = False
    result.error = (
        f"Real market data unavailable for {symbol} {timeframe}. "
        f"All data providers failed or returned insufficient data. "
        f"Backtest results would NOT be reliable. "
        f"Please check API keys and try a supported symbol/timeframe."
    )
    result.warning = "REAL_DATA_UNAVAILABLE"
    result.is_mock = False  # We're NOT falling back to mock
    
    logger.error(result.error)
    return result


async def _fetch_from_twelvedata(
    api_key: str, 
    symbol: str, 
    timeframe: str,
    market_data_service
) -> List[Candle]:
    """Fetch candles from Twelve Data and cache them."""
    import httpx
    
    TWELVE_DATA_URL = "https://api.twelvedata.com/time_series"
    INTERVAL_MAP = {
        "1h": "1h", "4h": "4h", "1d": "1day",
        "15m": "15min", "30m": "30min", "1m": "1min", "5m": "5min",
    }
    FOREX_SYMBOLS = {
        "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY",
        "USDCHF": "USD/CHF", "AUDUSD": "AUD/USD", "USDCAD": "USD/CAD",
        "NZDUSD": "NZD/USD", "EURGBP": "EUR/GBP", "EURJPY": "EUR/JPY",
        "GBPJPY": "GBP/JPY",
    }
    
    td_symbol = FOREX_SYMBOLS.get(symbol)
    if not td_symbol:
        raise ValueError(f"Unsupported symbol for Twelve Data: {symbol}")
    
    td_interval = INTERVAL_MAP.get(timeframe)
    if not td_interval:
        raise ValueError(f"Unsupported timeframe for Twelve Data: {timeframe}")
    
    params = {
        "symbol": td_symbol,
        "interval": td_interval,
        "outputsize": 5000,
        "apikey": api_key,
        "format": "JSON",
        "timezone": "UTC",
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(TWELVE_DATA_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    
    if data.get("status") == "error" or "code" in data:
        raise ValueError(f"Twelve Data error: {data.get('message', data)}")
    
    values = data.get("values", [])
    if not values:
        return []
    
    try:
        tf_enum = DataTimeframe(timeframe)
    except ValueError:
        tf_enum = DataTimeframe.H1
    
    candles = []
    for v in values:
        try:
            ts = datetime.strptime(v["datetime"], "%Y-%m-%d %H:%M:%S")
            candles.append(Candle(
                timestamp=ts,
                open=float(v["open"]),
                high=float(v["high"]),
                low=float(v["low"]),
                close=float(v["close"]),
                volume=0.0,
                symbol=symbol,
                timeframe=tf_enum,
            ))
        except (ValueError, KeyError):
            continue
    
    candles.sort(key=lambda c: c.timestamp)
    
    # Store in cache for future use
    if candles and market_data_service:
        try:
            await market_data_service.store_candles(
                candles, provider="twelve_data", overwrite=True
            )
            logger.info(f"Cached {len(candles)} candles from Twelve Data")
        except Exception as e:
            logger.warning(f"Failed to cache Twelve Data candles: {e}")
    
    return candles


async def _fetch_from_alphavantage(
    api_key: str,
    symbol: str,
    tf: DataTimeframe,
    start_date: datetime,
    end_date: datetime,
    market_data_service
) -> List[Candle]:
    """Fetch candles from Alpha Vantage and cache them."""
    provider = AlphaVantageProvider(api_key)
    
    if not provider.validate_symbol(symbol):
        raise ValueError(f"Unsupported symbol for Alpha Vantage: {symbol}")
    
    candles = await provider.fetch_historical_data(
        symbol=symbol,
        timeframe=tf,
        start_date=start_date,
        end_date=end_date,
    )
    
    # Store in cache for future use
    if candles and market_data_service:
        try:
            await market_data_service.store_candles(
                candles, provider="alpha_vantage", overwrite=True
            )
            logger.info(f"Cached {len(candles)} candles from Alpha Vantage")
        except Exception as e:
            logger.warning(f"Failed to cache Alpha Vantage candles: {e}")
    
    return candles


def sync_auto_fetch_candles(
    symbol: str,
    timeframe: str,
    min_candles: int = MIN_CANDLES_REQUIRED,
) -> DataFetchResult:
    """
    Synchronous version for use in thread executors (factory_router).
    Returns DataFetchResult - NEVER returns mock data.
    """
    import os
    from pymongo import MongoClient
    import httpx
    
    result = DataFetchResult()
    symbol = symbol.upper()
    
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    
    client = MongoClient(mongo_url)
    db = client[db_name]
    
    # ============================================================
    # STEP 1: Check cache
    # ============================================================
    try:
        docs = list(
            db.market_candles.find(
                {"symbol": symbol, "timeframe": timeframe},
                {"_id": 0},
            ).sort("timestamp", 1)
        )
        
        if docs and len(docs) >= min_candles:
            logger.info(f"[SYNC] Cache hit: {len(docs)} candles for {symbol} {timeframe}")
            result.success = True
            result.source = "cache"
            result.candle_count = len(docs)
            
            # Convert to Candle objects
            from market_data_models import Candle, DataTimeframe
            candles = []
            for d in docs:
                try:
                    tf_enum = DataTimeframe(d["timeframe"])
                except (ValueError, KeyError):
                    tf_enum = DataTimeframe.H1
                candles.append(Candle(
                    timestamp=d["timestamp"],
                    open=d["open"],
                    high=d["high"],
                    low=d["low"],
                    close=d["close"],
                    volume=d.get("volume", 0),
                    symbol=d["symbol"],
                    timeframe=tf_enum,
                ))
            result.candles = candles
            client.close()
            return result
    except Exception as e:
        logger.warning(f"[SYNC] Cache check error: {e}")
    
    # ============================================================
    # STEP 2: Try Twelve Data API (sync)
    # ============================================================
    twelve_data_key = os.environ.get("TWELVE_DATA_KEY")
    if twelve_data_key:
        try:
            candles = _sync_fetch_twelvedata(twelve_data_key, symbol, timeframe, db)
            if candles and len(candles) >= min_candles:
                result.success = True
                result.candles = candles
                result.source = "twelve_data"
                result.candle_count = len(candles)
                client.close()
                return result
        except Exception as e:
            logger.warning(f"[SYNC] Twelve Data failed: {e}")
    
    # ============================================================
    # STEP 3: ALL FAILED - Return error (NO MOCK)
    # ============================================================
    result.success = False
    result.error = (
        f"Real market data unavailable for {symbol} {timeframe}. "
        f"Cannot proceed with backtest - results would NOT be reliable."
    )
    result.warning = "REAL_DATA_UNAVAILABLE"
    result.is_mock = False
    
    client.close()
    logger.error(f"[SYNC] {result.error}")
    return result


def _sync_fetch_twelvedata(api_key: str, symbol: str, timeframe: str, db) -> List[Candle]:
    """Synchronous Twelve Data fetch for thread executor."""
    import requests
    from market_data_models import Candle, DataTimeframe
    
    TWELVE_DATA_URL = "https://api.twelvedata.com/time_series"
    INTERVAL_MAP = {
        "1h": "1h", "4h": "4h", "1d": "1day",
        "15m": "15min", "30m": "30min",
    }
    FOREX_SYMBOLS = {
        "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY",
        "USDCHF": "USD/CHF", "AUDUSD": "AUD/USD", "USDCAD": "USD/CAD",
        "NZDUSD": "NZD/USD", "EURGBP": "EUR/GBP", "EURJPY": "EUR/JPY",
        "GBPJPY": "GBP/JPY",
    }
    
    td_symbol = FOREX_SYMBOLS.get(symbol)
    if not td_symbol:
        raise ValueError(f"Unsupported symbol: {symbol}")
    
    td_interval = INTERVAL_MAP.get(timeframe)
    if not td_interval:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    
    params = {
        "symbol": td_symbol,
        "interval": td_interval,
        "outputsize": 5000,
        "apikey": api_key,
        "format": "JSON",
        "timezone": "UTC",
    }
    
    resp = requests.get(TWELVE_DATA_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    
    if data.get("status") == "error" or "code" in data:
        raise ValueError(f"Twelve Data error: {data.get('message', data)}")
    
    values = data.get("values", [])
    if not values:
        return []
    
    try:
        tf_enum = DataTimeframe(timeframe)
    except (ValueError, KeyError):
        tf_enum = DataTimeframe.H1
    
    candles = []
    docs_to_store = []
    
    for v in values:
        try:
            ts = datetime.strptime(v["datetime"], "%Y-%m-%d %H:%M:%S")
            candle = Candle(
                timestamp=ts,
                open=float(v["open"]),
                high=float(v["high"]),
                low=float(v["low"]),
                close=float(v["close"]),
                volume=0.0,
                symbol=symbol,
                timeframe=tf_enum,
            )
            candles.append(candle)
            docs_to_store.append({
                "timestamp": ts,
                "open": float(v["open"]),
                "high": float(v["high"]),
                "low": float(v["low"]),
                "close": float(v["close"]),
                "volume": 0.0,
                "symbol": symbol,
                "timeframe": timeframe,
                "provider": "twelve_data",
            })
        except (ValueError, KeyError):
            continue
    
    candles.sort(key=lambda c: c.timestamp)
    
    # Store in MongoDB
    if docs_to_store:
        try:
            for doc in docs_to_store:
                db.market_candles.update_one(
                    {"symbol": doc["symbol"], "timeframe": doc["timeframe"], "timestamp": doc["timestamp"]},
                    {"$set": doc},
                    upsert=True
                )
            logger.info(f"[SYNC] Cached {len(docs_to_store)} candles from Twelve Data")
        except Exception as e:
            logger.warning(f"[SYNC] Failed to cache: {e}")
    
    return candles
