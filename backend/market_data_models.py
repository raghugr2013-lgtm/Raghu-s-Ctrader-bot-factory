"""
Market Data Provider - Data Models and Types
Phase 3: Real Market Data Integration
"""

from pydantic import BaseModel, Field, ConfigDict, validator
from typing import List, Optional, Dict
from datetime import datetime, timezone
from enum import Enum
import uuid


# Enums
class DataTimeframe(str, Enum):
    """Supported timeframes"""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class DataProvider(str, Enum):
    """Supported data providers"""
    ALPHA_VANTAGE = "alpha_vantage"
    POLYGON = "polygon"
    TWELVE_DATA = "twelve_data"
    CTRADER = "ctrader"
    CSV_IMPORT = "csv_import"
    MANUAL = "manual"


# Core Data Models
class Candle(BaseModel):
    """OHLCV candle data point"""
    model_config = ConfigDict(extra="ignore")
    
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    # Metadata
    symbol: str
    timeframe: DataTimeframe
    
    @validator('high')
    def high_must_be_highest(cls, v, values):
        """Validate high is the highest price"""
        if 'open' in values and 'low' in values and 'close' in values:
            if v < values['low']:
                raise ValueError('High must be >= Low')
            if v < values['open']:
                raise ValueError('High must be >= Open')
            if v < values['close']:
                raise ValueError('High must be >= Close')
        return v
    
    @validator('low')
    def low_must_be_lowest(cls, v, values):
        """Validate low is the lowest price"""
        if 'open' in values:
            if v > values['open']:
                raise ValueError('Low must be <= Open')
        return v
    
    @validator('volume')
    def volume_must_be_positive(cls, v):
        """Validate volume is positive"""
        if v < 0:
            raise ValueError('Volume must be >= 0')
        return v


class MarketDataRequest(BaseModel):
    """Request for historical market data"""
    symbol: str
    timeframe: DataTimeframe
    start_date: datetime
    end_date: datetime
    provider: Optional[DataProvider] = DataProvider.CSV_IMPORT
    limit: Optional[int] = 10000  # Max candles to fetch


class MarketDataResponse(BaseModel):
    """Response with historical data"""
    success: bool
    symbol: str
    timeframe: str
    candles: List[Candle]
    count: int
    start_date: datetime
    end_date: datetime
    provider: str
    cached: bool = False
    message: Optional[str] = None


class MarketDataImportRequest(BaseModel):
    """Request to import data from CSV"""
    symbol: str
    timeframe: DataTimeframe
    data: str  # CSV content as string
    format_type: str = "mt4"  # mt4, mt5, ctrader, custom
    skip_validation: bool = False


class MarketDataStats(BaseModel):
    """Statistics about stored market data"""
    symbol: str
    timeframe: str
    total_candles: int
    first_timestamp: datetime
    last_timestamp: datetime
    date_range_days: int
    provider: str
    last_updated: datetime


class SymbolInfo(BaseModel):
    """Symbol information"""
    symbol: str
    description: str
    base_currency: str
    quote_currency: str
    pip_size: float
    tick_size: float
    lot_size: int = 100000
    available_timeframes: List[str]
    data_available_from: Optional[datetime] = None
    data_available_to: Optional[datetime] = None


# Storage Models
class StoredCandle(BaseModel):
    """Candle as stored in database"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    provider: str = "csv_import"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# CSV Format Definitions
CSV_FORMATS = {
    "dukascopy": {
        "columns": ["timestamp", "open", "high", "low", "close", "volume"],
        "timestamp_format": "%Y.%m.%d %H:%M:%S",
        "timestamp_formats": [
            "%Y.%m.%d %H:%M:%S",
            "%Y.%m.%d %H:%M:%S.%f",
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ],
        "has_header": True,
        "delimiter": ","
    },
    "mt4": {
        "columns": ["timestamp", "open", "high", "low", "close", "volume"],
        "timestamp_format": "%Y.%m.%d %H:%M",
        "timestamp_formats": ["%Y.%m.%d %H:%M", "%Y.%m.%d %H:%M:%S"],
        "has_header": True,
        "delimiter": ","
    },
    "mt5": {
        "columns": ["timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"],
        "timestamp_format": "%Y.%m.%d %H:%M:%S",
        "timestamp_formats": ["%Y.%m.%d %H:%M:%S"],
        "has_header": True,
        "delimiter": "\t"
    },
    "ctrader": {
        "columns": ["timestamp", "open", "high", "low", "close", "volume"],
        "timestamp_format": "%Y-%m-%d %H:%M:%S",
        "timestamp_formats": ["%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"],
        "has_header": True,
        "delimiter": ","
    },
    "custom": {
        "columns": ["timestamp", "open", "high", "low", "close", "volume"],
        "timestamp_format": "%Y-%m-%d %H:%M:%S",
        "timestamp_formats": [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%d-%m-%Y %H:%M:%S",
            "%Y.%m.%d %H:%M:%S",
        ],
        "has_header": False,
        "delimiter": ","
    }
}


# Provider Configuration
PROVIDER_CONFIGS = {
    "alpha_vantage": {
        "name": "Alpha Vantage",
        "requires_api_key": True,
        "rate_limit": "5 requests per minute (free tier)",
        "supported_timeframes": ["1m", "5m", "15m", "30m", "1h", "1d"],
        "max_candles_per_request": 1000
    },
    "polygon": {
        "name": "Polygon.io",
        "requires_api_key": True,
        "rate_limit": "5 requests per minute (free tier)",
        "supported_timeframes": ["1m", "5m", "15m", "1h", "1d"],
        "max_candles_per_request": 50000
    },
    "twelve_data": {
        "name": "TwelveData",
        "requires_api_key": True,
        "rate_limit": "8 requests per minute (free tier)",
        "supported_timeframes": ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
        "max_candles_per_request": 5000
    },
    "ctrader": {
        "name": "cTrader Open API",
        "requires_api_key": True,
        "rate_limit": "Varies by broker",
        "supported_timeframes": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
        "max_candles_per_request": 10000
    }
}


# Timeframe conversion utilities
TIMEFRAME_TO_MINUTES = {
    DataTimeframe.M1: 1,
    DataTimeframe.M5: 5,
    DataTimeframe.M15: 15,
    DataTimeframe.M30: 30,
    DataTimeframe.H1: 60,
    DataTimeframe.H4: 240,
    DataTimeframe.D1: 1440,
    DataTimeframe.W1: 10080
}


def get_timeframe_minutes(timeframe: DataTimeframe) -> int:
    """Get timeframe in minutes"""
    return TIMEFRAME_TO_MINUTES.get(timeframe, 60)


def validate_candle_data(candle: Candle) -> tuple[bool, Optional[str]]:
    """
    Validate candle data integrity
    Returns: (is_valid, error_message)
    """
    # Check OHLC relationship
    if candle.high < candle.low:
        return False, "High must be >= Low"
    
    if candle.high < candle.open or candle.high < candle.close:
        return False, "High must be >= Open and Close"
    
    if candle.low > candle.open or candle.low > candle.close:
        return False, "Low must be <= Open and Close"
    
    # Check for zero or negative prices
    if any(p <= 0 for p in [candle.open, candle.high, candle.low, candle.close]):
        return False, "Prices must be positive"
    
    # Check volume
    if candle.volume < 0:
        return False, "Volume must be >= 0"
    
    return True, None
