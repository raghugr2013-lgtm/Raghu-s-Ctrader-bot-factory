"""
Market Data Provider Interface and Implementations
Abstract base class + concrete provider implementations
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import logging
import csv
import io
from market_data_models import (
    Candle,
    DataTimeframe,
    MarketDataRequest,
    MarketDataResponse,
    DataProvider,
    CSV_FORMATS
)

logger = logging.getLogger(__name__)


class BaseMarketDataProvider(ABC):
    """Abstract base class for market data providers"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.provider_name = "base"
    
    @abstractmethod
    async def fetch_historical_data(
        self,
        symbol: str,
        timeframe: DataTimeframe,
        start_date: datetime,
        end_date: datetime
    ) -> List[Candle]:
        """Fetch historical OHLCV data"""
        pass
    
    @abstractmethod
    def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol is supported"""
        pass
    
    @abstractmethod
    def get_supported_timeframes(self) -> List[DataTimeframe]:
        """Get list of supported timeframes"""
        pass
    
    def get_latest_candle(self, symbol: str, timeframe: DataTimeframe) -> Optional[Candle]:
        """Get most recent candle (default implementation)"""
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=1)
        candles = self.fetch_historical_data(symbol, timeframe, start_date, end_date)
        return candles[-1] if candles else None


class CSVMarketDataProvider(BaseMarketDataProvider):
    """Provider for CSV file imports"""
    
    def __init__(self):
        super().__init__()
        self.provider_name = "csv_import"
    
    async def fetch_historical_data(
        self,
        symbol: str,
        timeframe: DataTimeframe,
        start_date: datetime,
        end_date: datetime
    ) -> List[Candle]:
        """Not used for CSV provider - data is imported directly"""
        return []
    
    def validate_symbol(self, symbol: str) -> bool:
        """CSV provider accepts any symbol"""
        return True
    
    def get_supported_timeframes(self) -> List[DataTimeframe]:
        """CSV provider supports all timeframes"""
        return list(DataTimeframe)
    
    def parse_csv_data(
        self,
        csv_content: str,
        symbol: str,
        timeframe: DataTimeframe,
        format_type: str = "dukascopy"
    ) -> List[Candle]:
        """
        Parse CSV content into Candle objects
        
        Supported formats:
        - dukascopy: Dukascopy format (default)
        - mt4: MetaTrader 4 format
        - mt5: MetaTrader 5 format
        - ctrader: cTrader format
        - custom: Custom CSV format
        """
        if format_type not in CSV_FORMATS:
            raise ValueError(f"Unsupported format: {format_type}. Supported: {list(CSV_FORMATS.keys())}")
        
        format_config = CSV_FORMATS[format_type]
        candles = []
        validation_errors = []
        skipped_rows = 0
        
        try:
            # Detect delimiter
            delimiter = format_config.get("delimiter", ",")
            csv_reader = csv.reader(io.StringIO(csv_content), delimiter=delimiter)
            
            # Skip header if present
            if format_config.get("has_header", True):
                header = next(csv_reader, None)
                logger.info(f"CSV header: {header}")
            
            # Get timestamp formats to try
            timestamp_formats = format_config.get("timestamp_formats", [format_config["timestamp_format"]])
            
            for row_num, row in enumerate(csv_reader, start=1):
                if not row or len(row) < 5:
                    skipped_rows += 1
                    continue
                
                # Skip empty rows
                if all(cell.strip() == '' for cell in row):
                    skipped_rows += 1
                    continue
                
                try:
                    # Extract data based on format
                    timestamp_str = row[0].strip()
                    
                    # Handle different column layouts
                    if format_type == "mt5" and len(row) >= 8:
                        open_price = float(row[1])
                        high_price = float(row[2])
                        low_price = float(row[3])
                        close_price = float(row[4])
                        volume = float(row[7]) if row[7].strip() else float(row[5])
                    else:
                        open_price = float(row[1])
                        high_price = float(row[2])
                        low_price = float(row[3])
                        close_price = float(row[4])
                        volume = float(row[5]) if len(row) > 5 and row[5].strip() else 0
                    
                    # Try multiple timestamp formats
                    timestamp = None
                    for ts_format in timestamp_formats:
                        try:
                            timestamp = datetime.strptime(timestamp_str, ts_format)
                            break
                        except ValueError:
                            continue
                    
                    if timestamp is None:
                        skipped_rows += 1
                        if row_num <= 10:
                            validation_errors.append(f"Row {row_num}: Invalid timestamp format '{timestamp_str}'")
                        continue
                    
                    # Validate OHLC data
                    if high_price < low_price:
                        # Auto-fix swapped high/low
                        high_price, low_price = low_price, high_price
                    
                    if high_price < open_price or high_price < close_price:
                        high_price = max(open_price, high_price, close_price)
                    
                    if low_price > open_price or low_price > close_price:
                        low_price = min(open_price, low_price, close_price)
                    
                    # Create candle
                    candle = Candle(
                        timestamp=timestamp,
                        open=open_price,
                        high=high_price,
                        low=low_price,
                        close=close_price,
                        volume=abs(volume),
                        symbol=symbol.upper(),
                        timeframe=timeframe
                    )
                    
                    candles.append(candle)
                
                except (ValueError, IndexError) as e:
                    skipped_rows += 1
                    if row_num <= 10:
                        validation_errors.append(f"Row {row_num}: {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"CSV parsing error: {str(e)}")
            raise ValueError(f"Failed to parse CSV: {str(e)}")
        
        if not candles:
            raise ValueError(f"No valid candles parsed. Errors: {validation_errors[:5]}")
        
        # Sort by timestamp
        candles.sort(key=lambda c: c.timestamp)
        
        # Validate continuity
        gaps = self._detect_gaps(candles, timeframe)
        
        logger.info(f"Parsed {len(candles)} candles, skipped {skipped_rows}, gaps detected: {len(gaps)}")
        
        return candles
    
    def _detect_gaps(self, candles: List[Candle], timeframe: DataTimeframe) -> List[dict]:
        """Detect gaps in candle data for validation"""
        from market_data_models import TIMEFRAME_TO_MINUTES
        
        if len(candles) < 2:
            return []
        
        expected_minutes = TIMEFRAME_TO_MINUTES.get(timeframe, 60)
        gaps = []
        
        for i in range(1, min(len(candles), 1000)):  # Check first 1000 candles
            prev = candles[i - 1]
            curr = candles[i]
            diff_minutes = (curr.timestamp - prev.timestamp).total_seconds() / 60
            
            # Allow some tolerance for weekends/holidays
            if diff_minutes > expected_minutes * 10:
                gaps.append({
                    "from": prev.timestamp.isoformat(),
                    "to": curr.timestamp.isoformat(),
                    "missing_candles": int(diff_minutes / expected_minutes) - 1
                })
        
        return gaps


class AlphaVantageProvider(BaseMarketDataProvider):
    """Alpha Vantage market data provider - Forex OHLCV data."""

    # Timeframe -> AlphaVantage interval string
    _INTRADAY_MAP = {
        DataTimeframe.M1: "1min",
        DataTimeframe.M5: "5min",
        DataTimeframe.M15: "15min",
        DataTimeframe.M30: "30min",
        DataTimeframe.H1: "60min",
    }

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.provider_name = "alpha_vantage"
        self.base_url = "https://www.alphavantage.co/query"

    async def fetch_historical_data(
        self,
        symbol: str,
        timeframe: DataTimeframe,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Candle]:
        """Fetch Forex OHLCV data from AlphaVantage."""
        import httpx

        # Split symbol into from/to (e.g. EURUSD -> EUR, USD)
        from_sym, to_sym = self._split_forex_pair(symbol)

        if timeframe in self._INTRADAY_MAP:
            candles = await self._fetch_intraday(from_sym, to_sym, timeframe, symbol)
        elif timeframe == DataTimeframe.D1:
            candles = await self._fetch_daily(from_sym, to_sym, symbol)
        elif timeframe == DataTimeframe.W1:
            candles = await self._fetch_weekly(from_sym, to_sym, symbol)
        else:
            logger.warning(f"Unsupported timeframe {timeframe} for AlphaVantage, falling back to daily")
            candles = await self._fetch_daily(from_sym, to_sym, symbol)

        # Filter by date range (normalize timezone)
        filtered = []
        for c in candles:
            ts = c.timestamp.replace(tzinfo=None)
            sd = start_date.replace(tzinfo=None) if start_date else None
            ed = end_date.replace(tzinfo=None) if end_date else None
            if (sd is None or ts >= sd) and (ed is None or ts <= ed):
                filtered.append(c)
        filtered.sort(key=lambda c: c.timestamp)
        return filtered

    async def _fetch_intraday(
        self, from_sym: str, to_sym: str, timeframe: DataTimeframe, symbol: str
    ) -> List[Candle]:
        import httpx

        interval = self._INTRADAY_MAP[timeframe]
        params = {
            "function": "FX_INTRADAY",
            "from_symbol": from_sym,
            "to_symbol": to_sym,
            "interval": interval,
            "outputsize": "full",
            "apikey": self.api_key,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(self.base_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        series_key = f"Time Series FX (Intraday)"
        return self._parse_series(data, series_key, symbol, timeframe)

    async def _fetch_daily(self, from_sym: str, to_sym: str, symbol: str) -> List[Candle]:
        import httpx

        params = {
            "function": "FX_DAILY",
            "from_symbol": from_sym,
            "to_symbol": to_sym,
            "outputsize": "full",
            "apikey": self.api_key,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(self.base_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        series_key = "Time Series FX (Daily)"
        return self._parse_series(data, series_key, symbol, DataTimeframe.D1)

    async def _fetch_weekly(self, from_sym: str, to_sym: str, symbol: str) -> List[Candle]:
        import httpx

        params = {
            "function": "FX_WEEKLY",
            "from_symbol": from_sym,
            "to_symbol": to_sym,
            "apikey": self.api_key,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(self.base_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        series_key = "Time Series FX (Weekly)"
        return self._parse_series(data, series_key, symbol, DataTimeframe.W1)

    def _parse_series(
        self, data: dict, series_key: str, symbol: str, timeframe: DataTimeframe
    ) -> List[Candle]:
        """Parse AlphaVantage time series JSON into Candle objects."""
        if "Error Message" in data:
            raise ValueError(f"AlphaVantage error: {data['Error Message']}")
        if "Note" in data:
            raise ValueError(f"AlphaVantage rate limit: {data['Note']}")
        if "Information" in data:
            raise ValueError(f"AlphaVantage: {data['Information']}")

        series = data.get(series_key, {})
        if not series:
            # Try alternate keys
            for key in data:
                if "Time Series" in key:
                    series = data[key]
                    break

        candles = []
        for ts_str, ohlc in series.items():
            try:
                # Parse timestamp
                if " " in ts_str:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                else:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d")

                candle = Candle(
                    timestamp=ts,
                    open=float(ohlc["1. open"]),
                    high=float(ohlc["2. high"]),
                    low=float(ohlc["3. low"]),
                    close=float(ohlc["4. close"]),
                    volume=0.0,  # Forex volume not provided by AV
                    symbol=symbol,
                    timeframe=timeframe,
                )
                candles.append(candle)
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping candle {ts_str}: {e}")
                continue

        return candles

    @staticmethod
    def _split_forex_pair(symbol: str):
        """Split 'EURUSD' into ('EUR', 'USD')."""
        symbol = symbol.upper().replace("/", "").replace("_", "")
        if len(symbol) == 6:
            return symbol[:3], symbol[3:]
        raise ValueError(f"Invalid forex pair: {symbol}. Expected format: EURUSD")

    def validate_symbol(self, symbol: str) -> bool:
        try:
            self._split_forex_pair(symbol)
            return True
        except ValueError:
            return False

    def get_supported_timeframes(self) -> List[DataTimeframe]:
        return [
            DataTimeframe.M1,
            DataTimeframe.M5,
            DataTimeframe.M15,
            DataTimeframe.M30,
            DataTimeframe.H1,
            DataTimeframe.D1,
            DataTimeframe.W1,
        ]


class PolygonProvider(BaseMarketDataProvider):
    """Polygon.io market data provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.provider_name = "polygon"
        self.base_url = "https://api.polygon.io/v2"
    
    async def fetch_historical_data(
        self,
        symbol: str,
        timeframe: DataTimeframe,
        start_date: datetime,
        end_date: datetime
    ) -> List[Candle]:
        """
        Fetch historical data from Polygon.io
        Placeholder implementation
        """
        logger.info(f"Polygon: Would fetch {symbol} {timeframe} from {start_date} to {end_date}")
        return []
    
    def validate_symbol(self, symbol: str) -> bool:
        """Validate symbol format"""
        return len(symbol) > 0
    
    def get_supported_timeframes(self) -> List[DataTimeframe]:
        """Polygon supported timeframes"""
        return [
            DataTimeframe.M1,
            DataTimeframe.M5,
            DataTimeframe.M15,
            DataTimeframe.H1,
            DataTimeframe.D1
        ]


class TwelveDataProvider(BaseMarketDataProvider):
    """TwelveData market data provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.provider_name = "twelve_data"
        self.base_url = "https://api.twelvedata.com"
    
    async def fetch_historical_data(
        self,
        symbol: str,
        timeframe: DataTimeframe,
        start_date: datetime,
        end_date: datetime
    ) -> List[Candle]:
        """
        Fetch historical data from TwelveData
        Placeholder implementation
        """
        logger.info(f"TwelveData: Would fetch {symbol} {timeframe} from {start_date} to {end_date}")
        return []
    
    def validate_symbol(self, symbol: str) -> bool:
        """Validate symbol format"""
        return len(symbol) > 0
    
    def get_supported_timeframes(self) -> List[DataTimeframe]:
        """TwelveData supported timeframes"""
        return [
            DataTimeframe.M1,
            DataTimeframe.M5,
            DataTimeframe.M15,
            DataTimeframe.M30,
            DataTimeframe.H1,
            DataTimeframe.H4,
            DataTimeframe.D1,
            DataTimeframe.W1
        ]


# Provider Factory
class MarketDataProviderFactory:
    """Factory for creating market data providers"""
    
    @staticmethod
    def create_provider(
        provider_type: DataProvider,
        api_key: Optional[str] = None
    ) -> BaseMarketDataProvider:
        """Create provider instance"""
        
        if provider_type == DataProvider.CSV_IMPORT:
            return CSVMarketDataProvider()
        
        elif provider_type == DataProvider.ALPHA_VANTAGE:
            if not api_key:
                raise ValueError("Alpha Vantage requires API key")
            return AlphaVantageProvider(api_key)
        
        elif provider_type == DataProvider.POLYGON:
            if not api_key:
                raise ValueError("Polygon requires API key")
            return PolygonProvider(api_key)
        
        elif provider_type == DataProvider.TWELVE_DATA:
            if not api_key:
                raise ValueError("TwelveData requires API key")
            return TwelveDataProvider(api_key)
        
        else:
            raise ValueError(f"Unsupported provider: {provider_type}")
    
    @staticmethod
    def get_available_providers() -> Dict[str, Dict]:
        """Get list of available providers and their capabilities"""
        from market_data_models import PROVIDER_CONFIGS
        return PROVIDER_CONFIGS


# Singleton instances
csv_provider = CSVMarketDataProvider()
provider_factory = MarketDataProviderFactory()
