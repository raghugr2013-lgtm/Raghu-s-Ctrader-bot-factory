"""
Auto-Fetch Market Data Module
PRIORITY: Local Dukascopy data FIRST, then cache, NO external APIs.

Data Source Priority:
1. Local Dukascopy JSON files (PREFERRED - no API limits)
2. MongoDB cache
3. ERROR if no data found (no external API fallback)
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from market_data_models import Candle, DataTimeframe

logger = logging.getLogger(__name__)

# Minimum candles required for a valid backtest
MIN_CANDLES_REQUIRED = 60

# LOCAL DATA ONLY - NO EXTERNAL APIs
USE_LOCAL_DATA_ONLY = True


class DataFetchResult:
    """Result of auto-fetch operation"""
    def __init__(self):
        self.success: bool = False
        self.candles: List[Candle] = []
        self.source: str = ""  # "local_dukascopy", "cache"
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
    Auto-fetch real market data from LOCAL sources only.
    
    Flow:
    1. Check LOCAL Dukascopy JSON files FIRST (preferred)
    2. Check MongoDB cache second
    3. Return error if no data found (NO external API calls)
    
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
    
    # ============================================================
    # STEP 1: Check LOCAL Dukascopy data FIRST (PREFERRED)
    # ============================================================
    try:
        from local_data_provider import get_local_provider
        local_provider = get_local_provider()
        
        if local_provider.validate_symbol(symbol):
            logger.info(f"Loading local Dukascopy data for {symbol} {timeframe}...")
            ohlc_df = local_provider.get_ohlc_data(symbol, timeframe, start_date, end_date)
            
            if not ohlc_df.empty and len(ohlc_df) >= min_candles:
                # Convert DataFrame to Candle objects
                candles = []
                for _, row in ohlc_df.iterrows():
                    candle = Candle(
                        timestamp=row['time'].to_pydatetime() if hasattr(row['time'], 'to_pydatetime') else row['time'],
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=float(row['volume']),
                        symbol=symbol,
                        timeframe=tf,
                    )
                    candles.append(candle)
                
                result.success = True
                result.candles = candles
                result.source = "local_dukascopy"
                result.candle_count = len(candles)
                logger.info(f"✅ Local Dukascopy data loaded: {len(candles)} {timeframe} candles for {symbol}")
                return result
            else:
                logger.info(f"Local Dukascopy: insufficient data ({len(ohlc_df) if not ohlc_df.empty else 0} candles)")
        else:
            logger.info(f"Local Dukascopy: symbol {symbol} not available locally")
    except ImportError:
        logger.warning("local_data_provider not available")
    except Exception as e:
        logger.warning(f"Local Dukascopy fetch error: {e}")
    
    # ============================================================
    # STEP 2: Check MongoDB cache
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
            logger.info(f"Cache hit: {len(cached)} candles for {symbol} {timeframe}")
            result.success = True
            result.candles = cached
            result.source = "cache"
            result.candle_count = len(cached)
            return result
        else:
            logger.info(f"Cache insufficient: {len(cached) if cached else 0} candles (need {min_candles})")
    except Exception as e:
        logger.warning(f"Cache check error: {e}")
    
    # ============================================================
    # STEP 3: NO DATA FOUND - Return error (NO external APIs)
    # ============================================================
    result.success = False
    result.error = (
        f"No local data available for {symbol} {timeframe}. "
        f"Please ensure Dukascopy data is available in /app/trading_strategy/data/dukascopy/{symbol}/"
    )
    result.warning = "LOCAL_DATA_UNAVAILABLE"
    result.is_mock = False
    
    logger.error(result.error)
    return result


