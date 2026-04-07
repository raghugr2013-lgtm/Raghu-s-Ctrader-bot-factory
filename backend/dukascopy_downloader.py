"""
Dukascopy Data Downloader
Downloads tick data from Dukascopy and converts to 1-minute candles ONLY.

ARCHITECTURE PRINCIPLE:
- Downloads ONLY tick data (.bi5 format)
- Converts ticks → 1-minute candles ONLY
- Stores ONLY 1m candles in database
- Higher timeframes are NEVER stored (generated on-demand via timeframe_aggregator)

DATA SOURCE POLICY:
- ONLY Dukascopy for all data ingestion
- NO mixing of providers
- NO synthetic data generation
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from pathlib import Path
import logging

from bi5_decoder import BI5Decoder
from tick_aggregator import TickAggregator

logger = logging.getLogger(__name__)


def map_timeframe_to_dukascopy(tf: str) -> str:
    """
    DEPRECATED: All timeframes now force tick download.
    Maintained for backward compatibility but always returns "TICK".
    
    System ONLY stores 1m candles. Higher timeframes derived on-demand.
    """
    logger.info(f"[1M ARCHITECTURE] Requested '{tf}' → forcing TICK download → will store as 1m")
    return "TICK"  # Always download ticks


def map_timeframe_from_dukascopy(tf: str) -> str:
    """
    Convert Dukascopy format back to internal format
    
    Args:
        tf: Dukascopy timeframe (e.g., "M1", "H1")
    
    Returns:
        Internal timeframe (e.g., "1m", "1h")
    """
    reverse_mapping = {
        "M1": "1m",
        "M5": "5m",
        "M15": "15m",
        "M30": "30m",
        "H1": "1h",
        "H4": "4h",
        "D1": "1d"
    }
    
    result = reverse_mapping.get(tf.upper() if tf else "", tf.lower() if tf else "1h")
    return result


class DukascopyDownloader:
    """Download and process data from Dukascopy"""
    
    # Base URL for Dukascopy data
    BASE_URL = "https://datafeed.dukascopy.com/datafeed"
    
    # Symbol mapping (Dukascopy uses different naming)
    SYMBOL_MAP = {
        'EURUSD': 'EURUSD',
        'GBPUSD': 'GBPUSD',
        'USDJPY': 'USDJPY',
        'XAUUSD': 'XAUUSD',  # Gold
        'NAS100': 'USA100IDXUSD',  # US100/NASDAQ
        'BTCUSD': 'BTCUSD',
        'ETHUSD': 'ETHUSD'
    }
    
    def __init__(self):
        self.decoder = BI5Decoder()
        self.aggregator = TickAggregator()
    
    async def download_range(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str,
        progress_callback=None
    ) -> Dict:
        """
        Download tick data and convert to 1-MINUTE candles ONLY.
        
        CRITICAL ARCHITECTURE CHANGE:
        - Regardless of timeframe parameter, ALWAYS produces 1m candles
        - Higher timeframes (5m, 15m, 1h, etc.) are NEVER stored
        - They are generated on-demand via timeframe_aggregator.py
        
        Args:
            symbol: Trading symbol
            start_date: Start datetime
            end_date: End datetime
            timeframe: IGNORED (kept for API compatibility)
            progress_callback: Optional callback for progress updates
        
        Returns:
            Dictionary with 1m candles and statistics
        """
        # FORCE 1m architecture - ignore requested timeframe
        logger.info(f"[1M ARCHITECTURE] Requested '{timeframe}' → will produce 1m candles only")
        logger.info(f"[1M ARCHITECTURE] Higher timeframes derived on-demand from 1m source")
        
        # Get Dukascopy symbol name
        duka_symbol = self.SYMBOL_MAP.get(symbol, symbol)
        
        logger.info(f"Downloading {symbol} from {start_date} to {end_date}")
        
        all_candles = []
        hours_to_download = []
        
        # Generate list of hours to download
        current = start_date.replace(minute=0, second=0, microsecond=0)
        while current <= end_date:
            hours_to_download.append(current)
            current += timedelta(hours=1)
        
        total_hours = len(hours_to_download)
        downloaded = 0
        failed = 0
        
        # Download each hour
        async with aiohttp.ClientSession() as session:
            for hour_dt in hours_to_download:
                try:
                    # Download hour data
                    ticks = await self._download_hour(session, duka_symbol, hour_dt)
                    
                    if ticks:
                        # Aggregate to 1m candles ONLY
                        candles = self.aggregator.aggregate_ticks_to_candles(
                            ticks, hour_dt, "1m"  # FORCE 1m
                        )
                        all_candles.extend(candles)
                        downloaded += 1
                    else:
                        failed += 1
                        logger.warning(f"No data for {hour_dt}")
                    
                    # Progress update
                    if progress_callback:
                        progress = (downloaded + failed) / total_hours * 100
                        await progress_callback(progress, f"Downloaded {downloaded}/{total_hours} hours")
                    
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to download {hour_dt}: {str(e)}")
        
        # Sort candles by timestamp
        all_candles.sort(key=lambda c: c['timestamp'])
        
        # DO NOT FILL GAPS - Use only real Dukascopy data
        filled_candles = all_candles  # No gap filling
        
        # Calculate statistics (force 1m timeframe)
        stats = self._calculate_statistics(all_candles, filled_candles, "1m")
        stats.update({
            'symbol': symbol,
            'timeframe': '1m',  # ALWAYS 1m
            'storage_timeframe': '1m',  # Architecture marker
            'start_date': start_date,
            'end_date': end_date,
            'hours_downloaded': downloaded,
            'hours_failed': failed,
            'total_hours': total_hours,
            'note': '1m is source of truth; higher TFs derived on-demand'
        })
        
        logger.info(f"[1M ARCHITECTURE] {len(filled_candles)} 1m candles ready for storage")
        
        return {
            'candles': filled_candles,
            'stats': stats
        }
    
    async def _download_hour(
        self,
        session: aiohttp.ClientSession,
        symbol: str,
        hour_dt: datetime
    ) -> Optional[List[Dict]]:
        """
        Download one hour of tick data
        
        URL format: {BASE_URL}/{symbol}/{year}/{month}/{day}/{hour}h_ticks.bi5
        """
        year = hour_dt.year
        # Month is 0-indexed in Dukascopy URLs
        month = hour_dt.month - 1
        day = hour_dt.day
        hour = hour_dt.hour
        
        url = (
            f"{self.BASE_URL}/{symbol}/{year}/"
            f"{month:02d}/{day:02d}/{hour:02d}h_ticks.bi5"
        )
        
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    compressed_data = await response.read()
                    
                    # Decode .bi5 file
                    ticks = self.decoder.decode_bi5(compressed_data)
                    
                    # Validate ticks
                    if self.decoder.validate_ticks(ticks):
                        return ticks
                    else:
                        logger.warning(f"Invalid tick data for {url}")
                        return None
                else:
                    logger.debug(f"No data at {url} (HTTP {response.status})")
                    return None
                    
        except asyncio.TimeoutError:
            logger.warning(f"Timeout downloading {url}")
            return None
        except Exception as e:
            logger.error(f"Error downloading {url}: {str(e)}")
            return None
    
    def _calculate_statistics(
        self,
        original_candles: List[Dict],
        filled_candles: List[Dict],
        timeframe: str
    ) -> Dict:
        """Calculate data quality statistics"""
        if not filled_candles:
            return {
                'total_candles': 0,
                'original_candles': 0,
                'filled_candles': 0,
                'data_quality_score': 0,
                'missing_candles': 0,
                'large_gaps': 0
            }
        
        original_count = len(original_candles)
        filled_count = len(filled_candles)
        filled_only = filled_count - original_count
        
        # Detect large gaps (not filled)
        large_gaps = self._detect_large_gaps(filled_candles, timeframe)
        
        # Calculate quality score (0-100)
        if filled_count > 0:
            # Higher score = less filling needed
            quality_score = max(0, 100 - (filled_only / filled_count * 100))
            quality_score = min(100, quality_score - (large_gaps * 5))  # Penalize large gaps
        else:
            quality_score = 0
        
        # Get date range
        start_dt = filled_candles[0]['timestamp']
        end_dt = filled_candles[-1]['timestamp']
        
        return {
            'total_candles': filled_count,
            'original_candles': original_count,
            'filled_candles': filled_only,
            'data_quality_score': round(quality_score, 1),
            'missing_candles': filled_only,
            'large_gaps': large_gaps,
            'date_range_start': start_dt.isoformat(),
            'date_range_end': end_dt.isoformat(),
            'coverage_percent': round((original_count / filled_count * 100), 1) if filled_count > 0 else 0
        }
    
    def _detect_large_gaps(self, candles: List[Dict], timeframe: str) -> int:
        """Detect large gaps (>3 candles) that weren't filled"""
        if len(candles) < 2:
            return 0
        
        candle_minutes = TickAggregator.TIMEFRAME_MINUTES[timeframe]
        expected_delta = timedelta(minutes=candle_minutes)
        large_gaps = 0
        
        for i in range(len(candles) - 1):
            current_time = candles[i]['timestamp']
            next_time = candles[i + 1]['timestamp']
            actual_delta = next_time - current_time
            
            # If gap is larger than expected
            if actual_delta > expected_delta:
                gap_candles = int(actual_delta.total_seconds() / (candle_minutes * 60))
                if gap_candles > 3:
                    large_gaps += 1
        
        return large_gaps
    
    async def save_to_csv(
        self,
        candles: List[Dict],
        symbol: str,
        timeframe: str,
        output_dir: str = "/app/data"
    ) -> str:
        """
        Save candles to CSV file
        
        Path structure: /data/{symbol}/{timeframe}/{year}.csv
        """
        if not candles:
            raise ValueError("No candles to save")
        
        # Get year from first candle
        year = candles[0]['timestamp'].year
        
        # Create directory structure
        symbol_dir = Path(output_dir) / symbol / timeframe
        symbol_dir.mkdir(parents=True, exist_ok=True)
        
        # CSV file path
        csv_file = symbol_dir / f"{year}.csv"
        
        # Write CSV
        with open(csv_file, 'w') as f:
            # Header
            f.write("Timestamp,Open,High,Low,Close,Volume,IsFilled\n")
            
            # Data rows
            for candle in candles:
                f.write(
                    f"{candle['timestamp'].isoformat()},"
                    f"{candle['open']},"
                    f"{candle['high']},"
                    f"{candle['low']},"
                    f"{candle['close']},"
                    f"{candle['volume']},"
                    f"{candle['is_filled']}\n"
                )
        
        logger.info(f"Saved {len(candles)} candles to {csv_file}")
        return str(csv_file)
