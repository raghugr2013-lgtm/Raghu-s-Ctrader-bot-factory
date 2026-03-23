"""
Dukascopy Historical Data Provider
Provides tick data conversion to OHLC candles for backtesting.

Supports:
- EURUSD, XAUUSD, US100, ETHUSD
- M1, M15, H1, H4, D1 timeframes
- Local caching for performance
"""

import os
import logging
import struct
import lzma
import httpx
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Tuple
from pathlib import Path
from pydantic import BaseModel
import json

logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = Path("/app/data/dukascopy")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Dukascopy symbol mapping
DUKASCOPY_SYMBOLS = {
    "EURUSD": "EURUSD",
    "XAUUSD": "XAUUSD",
    "US100": "USA100IDXUSD",
    "ETHUSD": "ETHUSD"
}

# Timeframe mappings
TIMEFRAME_MINUTES = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "1h": 60,
    "H4": 240,
    "4h": 240,
    "D1": 1440,
    "1d": 1440
}


class DukascopyCandle(BaseModel):
    """OHLC Candle from Dukascopy data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "time": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume
        }


class TickData(BaseModel):
    """Raw tick data from Dukascopy"""
    timestamp: datetime
    ask: float
    bid: float
    ask_volume: float
    bid_volume: float


class DukascopyProvider:
    """
    Dukascopy Historical Data Provider
    Downloads and caches tick data, converts to OHLC candles
    """
    
    BASE_URL = "https://datafeed.dukascopy.com/datafeed"
    
    def __init__(self):
        self.cache_dir = CACHE_DIR
        self._http_client: Optional[httpx.AsyncClient] = None
        
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
        return self._http_client
    
    def _get_dukascopy_symbol(self, symbol: str) -> str:
        """Map symbol to Dukascopy format"""
        symbol_upper = symbol.upper().replace("/", "")
        return DUKASCOPY_SYMBOLS.get(symbol_upper, symbol_upper)
    
    def _get_cache_path(self, symbol: str, date: datetime) -> Path:
        """Get cache file path for a specific hour"""
        dk_symbol = self._get_dukascopy_symbol(symbol)
        return self.cache_dir / dk_symbol / f"{date.year}" / f"{date.month:02d}" / f"{date.day:02d}" / f"{date.hour:02d}.json"
    
    def _is_cached(self, symbol: str, date: datetime) -> bool:
        """Check if data is cached"""
        cache_path = self._get_cache_path(symbol, date)
        return cache_path.exists()
    
    def _load_from_cache(self, symbol: str, date: datetime) -> List[TickData]:
        """Load tick data from cache"""
        cache_path = self._get_cache_path(symbol, date)
        if not cache_path.exists():
            return []
        
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
                return [TickData(**tick) for tick in data]
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            return []
    
    def _save_to_cache(self, symbol: str, date: datetime, ticks: List[TickData]):
        """Save tick data to cache"""
        cache_path = self._get_cache_path(symbol, date)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = [{
                "timestamp": tick.timestamp.isoformat(),
                "ask": tick.ask,
                "bid": tick.bid,
                "ask_volume": tick.ask_volume,
                "bid_volume": tick.bid_volume
            } for tick in ticks]
            
            with open(cache_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def _build_url(self, symbol: str, date: datetime) -> str:
        """Build Dukascopy data URL for a specific hour"""
        dk_symbol = self._get_dukascopy_symbol(symbol)
        # Dukascopy uses 0-indexed months
        month = date.month - 1
        return f"{self.BASE_URL}/{dk_symbol}/{date.year}/{month:02d}/{date.day:02d}/{date.hour:02d}h_ticks.bi5"
    
    def _parse_bi5_data(self, data: bytes, base_timestamp: datetime) -> List[TickData]:
        """
        Parse Dukascopy bi5 compressed tick data
        
        Format: LZMA compressed, each tick is 20 bytes:
        - 4 bytes: milliseconds offset from hour start (uint32)
        - 4 bytes: ask price (uint32, needs point adjustment)
        - 4 bytes: bid price (uint32, needs point adjustment)
        - 4 bytes: ask volume (float32)
        - 4 bytes: bid volume (float32)
        """
        ticks = []
        
        try:
            # Decompress LZMA
            decompressed = lzma.decompress(data)
            
            # Parse ticks (20 bytes each)
            tick_size = 20
            num_ticks = len(decompressed) // tick_size
            
            # Determine point value based on symbol (simplified)
            # Most forex pairs use 100000 (5 decimal places)
            point_divider = 100000.0
            
            for i in range(num_ticks):
                offset = i * tick_size
                tick_data = decompressed[offset:offset + tick_size]
                
                if len(tick_data) < tick_size:
                    break
                
                # Unpack: milliseconds, ask, bid, ask_vol, bid_vol
                ms_offset, ask_int, bid_int, ask_vol, bid_vol = struct.unpack(
                    '>IIIff', tick_data
                )
                
                timestamp = base_timestamp + timedelta(milliseconds=ms_offset)
                ask = ask_int / point_divider
                bid = bid_int / point_divider
                
                ticks.append(TickData(
                    timestamp=timestamp,
                    ask=ask,
                    bid=bid,
                    ask_volume=ask_vol,
                    bid_volume=bid_vol
                ))
                
        except lzma.LZMAError as e:
            logger.warning(f"LZMA decompression failed: {e}")
        except Exception as e:
            logger.error(f"Error parsing bi5 data: {e}")
        
        return ticks
    
    async def download_hour_data(self, symbol: str, date: datetime) -> List[TickData]:
        """
        Download tick data for a specific hour
        
        Args:
            symbol: Trading symbol
            date: Hour to download (only hour component used)
        
        Returns:
            List of tick data for the hour
        """
        # Round to hour
        hour_start = date.replace(minute=0, second=0, microsecond=0)
        
        # Check cache first
        if self._is_cached(symbol, hour_start):
            logger.debug(f"Loading {symbol} {hour_start} from cache")
            return self._load_from_cache(symbol, hour_start)
        
        # Download from Dukascopy
        url = self._build_url(symbol, hour_start)
        logger.info(f"Downloading {symbol} data from {url}")
        
        try:
            client = await self._get_client()
            response = await client.get(url)
            
            if response.status_code == 404:
                # No data for this hour (weekend, holiday, etc.)
                logger.debug(f"No data available for {symbol} {hour_start}")
                return []
            
            response.raise_for_status()
            
            # Parse the data
            ticks = self._parse_bi5_data(response.content, hour_start)
            
            # Cache it
            if ticks:
                self._save_to_cache(symbol, hour_start, ticks)
            
            logger.info(f"Downloaded {len(ticks)} ticks for {symbol} {hour_start}")
            return ticks
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading {symbol}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error downloading {symbol}: {e}")
            return []
    
    async def download_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        max_concurrent: int = 5
    ) -> List[TickData]:
        """
        Download tick data for a date range
        
        Args:
            symbol: Trading symbol
            start_date: Start of range
            end_date: End of range
            max_concurrent: Max concurrent downloads
        
        Returns:
            Combined list of tick data
        """
        all_ticks = []
        
        # Generate list of hours to download
        current = start_date.replace(minute=0, second=0, microsecond=0)
        hours_to_download = []
        
        while current <= end_date:
            hours_to_download.append(current)
            current += timedelta(hours=1)
        
        logger.info(f"Downloading {len(hours_to_download)} hours of {symbol} data")
        
        # Download in batches
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def download_with_semaphore(hour: datetime):
            async with semaphore:
                return await self.download_hour_data(symbol, hour)
        
        # Download all hours
        tasks = [download_with_semaphore(hour) for hour in hours_to_download]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        for result in results:
            if isinstance(result, list):
                all_ticks.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Download error: {result}")
        
        # Sort by timestamp
        all_ticks.sort(key=lambda t: t.timestamp)
        
        logger.info(f"Total ticks downloaded: {len(all_ticks)}")
        return all_ticks
    
    def convert_to_ohlc(
        self,
        ticks: List[TickData],
        timeframe: str = "M15"
    ) -> List[DukascopyCandle]:
        """
        Convert tick data to OHLC candles
        
        Args:
            ticks: List of tick data
            timeframe: Target timeframe (M1, M5, M15, M30, H1, H4, D1)
        
        Returns:
            List of OHLC candles
        """
        if not ticks:
            return []
        
        # Get timeframe in minutes
        tf_minutes = TIMEFRAME_MINUTES.get(timeframe, 15)
        
        candles = []
        current_candle_start = None
        current_candle = None
        
        for tick in ticks:
            # Use mid price
            price = (tick.ask + tick.bid) / 2
            volume = tick.ask_volume + tick.bid_volume
            
            # Calculate candle start time
            minutes_since_midnight = tick.timestamp.hour * 60 + tick.timestamp.minute
            candle_minutes = (minutes_since_midnight // tf_minutes) * tf_minutes
            candle_start = tick.timestamp.replace(
                hour=candle_minutes // 60,
                minute=candle_minutes % 60,
                second=0,
                microsecond=0
            )
            
            if current_candle is None or candle_start != current_candle_start:
                # Save previous candle
                if current_candle is not None:
                    candles.append(current_candle)
                
                # Start new candle
                current_candle_start = candle_start
                current_candle = DukascopyCandle(
                    timestamp=candle_start,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=volume
                )
            else:
                # Update current candle
                current_candle.high = max(current_candle.high, price)
                current_candle.low = min(current_candle.low, price)
                current_candle.close = price
                current_candle.volume += volume
        
        # Don't forget last candle
        if current_candle is not None:
            candles.append(current_candle)
        
        logger.info(f"Converted {len(ticks)} ticks to {len(candles)} {timeframe} candles")
        return candles
    
    async def get_ohlc(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[DukascopyCandle]:
        """
        Main interface: Get OHLC candles for symbol/timeframe/range
        
        Args:
            symbol: Trading symbol (EURUSD, XAUUSD, US100, ETHUSD)
            timeframe: Candle timeframe (M1, M15, H1, etc.)
            start_date: Start of range
            end_date: End of range
        
        Returns:
            List of OHLC candles
        """
        # Download tick data
        ticks = await self.download_data(symbol, start_date, end_date)
        
        if not ticks:
            logger.warning(f"No tick data available for {symbol} {start_date} to {end_date}")
            return []
        
        # Convert to OHLC
        candles = self.convert_to_ohlc(ticks, timeframe)
        
        return candles
    
    def get_cached_data_info(self, symbol: str) -> dict:
        """Get information about cached data for a symbol"""
        dk_symbol = self._get_dukascopy_symbol(symbol)
        symbol_dir = self.cache_dir / dk_symbol
        
        if not symbol_dir.exists():
            return {
                "symbol": symbol,
                "cached": False,
                "hours_cached": 0,
                "date_range": None
            }
        
        # Count cached hours
        cache_files = list(symbol_dir.rglob("*.json"))
        
        if not cache_files:
            return {
                "symbol": symbol,
                "cached": False,
                "hours_cached": 0,
                "date_range": None
            }
        
        return {
            "symbol": symbol,
            "cached": True,
            "hours_cached": len(cache_files),
            "cache_size_mb": sum(f.stat().st_size for f in cache_files) / (1024 * 1024)
        }
    
    async def close(self):
        """Close HTTP client"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# Singleton instance
_provider_instance: Optional[DukascopyProvider] = None


def get_dukascopy_provider() -> DukascopyProvider:
    """Get singleton Dukascopy provider instance"""
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = DukascopyProvider()
    return _provider_instance
