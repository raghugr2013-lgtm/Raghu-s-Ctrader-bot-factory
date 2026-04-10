"""
Dukascopy Downloader - Direct tick data acquisition

Downloads historical BI5 tick data from Dukascopy's public datafeed.
Maintains M1 SSOT compliance - only tick data is downloaded and converted to M1.

URL Structure:
https://datafeed.dukascopy.com/datafeed/{SYMBOL}/{YEAR}/{MONTH_0_INDEXED}/{DAY}/{HOUR}h_ticks.bi5

Example:
https://datafeed.dukascopy.com/datafeed/EURUSD/2025/00/15/10h_ticks.bi5
(January = 00, February = 01, etc.)
"""

import logging
import asyncio
import aiohttp
from typing import Optional, Callable, List
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DownloadProgress:
    """Progress information for download operation"""
    current_hour: datetime
    hours_completed: int
    hours_total: int
    hours_successful: int
    hours_failed: int
    candles_stored: int
    current_status: str
    errors: List[str]
    
    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage"""
        if self.hours_total == 0:
            return 0.0
        return (self.hours_completed / self.hours_total) * 100


class DukascopyDownloader:
    """
    Download historical tick data from Dukascopy.
    
    Features:
    - Async downloads with retry logic
    - Error handling for missing/corrupted files
    - Progress tracking
    - Timeout management
    - Rate limiting (optional)
    
    NO SYNTHETIC DATA - only downloads real tick data.
    """
    
    BASE_URL = "https://datafeed.dukascopy.com/datafeed"
    
    def __init__(
        self,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        retry_delay_seconds: float = 2.0
    ):
        """
        Initialize Dukascopy downloader.
        
        Args:
            timeout_seconds: HTTP request timeout
            max_retries: Number of retry attempts for failed downloads
            retry_delay_seconds: Delay between retries
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.max_retries = max_retries
        self.retry_delay = retry_delay_seconds
    
    def build_url(self, symbol: str, dt: datetime) -> str:
        """
        Build Dukascopy BI5 URL for specific hour.
        
        Args:
            symbol: Trading pair (e.g., "EURUSD")
            dt: Datetime (hour precision)
        
        Returns:
            Full URL to BI5 file
        
        Example:
            2025-01-15 10:00:00 UTC
            → https://datafeed.dukascopy.com/datafeed/EURUSD/2025/00/15/10h_ticks.bi5
        """
        symbol = symbol.upper()
        year = dt.year
        month = dt.month - 1  # 0-indexed (January = 00)
        day = dt.day
        hour = dt.hour
        
        url = f"{self.BASE_URL}/{symbol}/{year}/{month:02d}/{day:02d}/{hour:02d}h_ticks.bi5"
        return url
    
    async def download_hour(
        self,
        symbol: str,
        hour: datetime,
        retry_count: int = 0
    ) -> Optional[bytes]:
        """
        Download single hour of tick data.
        
        Args:
            symbol: Trading pair
            hour: Hour to download
            retry_count: Current retry attempt
        
        Returns:
            Raw BI5 file bytes, or None if failed
        """
        url = self.build_url(symbol, hour)
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        
                        if len(data) == 0:
                            logger.warning(f"Empty BI5 file: {symbol} {hour}")
                            return None
                        
                        logger.info(f"Downloaded: {symbol} {hour.date()} {hour.hour:02d}:00 ({len(data)} bytes)")
                        return data
                    
                    elif response.status == 404:
                        # No data available for this hour (normal for weekends, holidays)
                        logger.debug(f"No data available: {symbol} {hour} (404)")
                        return None
                    
                    else:
                        logger.warning(f"Download failed: {symbol} {hour} (HTTP {response.status})")
                        
                        # Retry on server errors
                        if response.status >= 500 and retry_count < self.max_retries:
                            await asyncio.sleep(self.retry_delay)
                            return await self.download_hour(symbol, hour, retry_count + 1)
                        
                        return None
        
        except asyncio.TimeoutError:
            logger.warning(f"Download timeout: {symbol} {hour}")
            
            # Retry on timeout
            if retry_count < self.max_retries:
                await asyncio.sleep(self.retry_delay)
                return await self.download_hour(symbol, hour, retry_count + 1)
            
            return None
        
        except Exception as e:
            logger.error(f"Download error: {symbol} {hour} - {str(e)}")
            
            # Retry on network errors
            if retry_count < self.max_retries:
                await asyncio.sleep(self.retry_delay)
                return await self.download_hour(symbol, hour, retry_count + 1)
            
            return None
    
    async def download_range(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ) -> List[tuple[datetime, bytes]]:
        """
        Download tick data for date range.
        
        Args:
            symbol: Trading pair
            start_date: Start datetime
            end_date: End datetime
            progress_callback: Optional callback receiving DownloadProgress
        
        Returns:
            List of (hour, bi5_bytes) tuples
        """
        # Generate list of hours
        hours = []
        current = start_date.replace(minute=0, second=0, microsecond=0)
        
        # Ensure UTC timezone
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        
        end = end_date.replace(minute=0, second=0, microsecond=0)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        
        while current <= end:
            hours.append(current)
            current += timedelta(hours=1)
        
        total_hours = len(hours)
        successful_downloads = []
        
        # Progress tracker
        progress = DownloadProgress(
            current_hour=hours[0] if hours else datetime.now(timezone.utc),
            hours_completed=0,
            hours_total=total_hours,
            hours_successful=0,
            hours_failed=0,
            candles_stored=0,
            current_status="Starting download...",
            errors=[]
        )
        
        logger.info(f"Starting download: {symbol} from {start_date.date()} to {end_date.date()} ({total_hours} hours)")
        
        for i, hour in enumerate(hours):
            progress.current_hour = hour
            progress.hours_completed = i
            progress.current_status = f"Downloading {hour.date()} {hour.hour:02d}:00"
            
            if progress_callback:
                await progress_callback(progress)
            
            try:
                # Download hour
                bi5_data = await self.download_hour(symbol, hour)
                
                if bi5_data:
                    successful_downloads.append((hour, bi5_data))
                    progress.hours_successful += 1
                else:
                    progress.hours_failed += 1
                    # 404 is normal (weekends, holidays), don't log as error
                    logger.debug(f"Skipped: {symbol} {hour} (no data available)")
            
            except Exception as e:
                progress.hours_failed += 1
                error_msg = f"Failed to download {hour}: {str(e)}"
                progress.errors.append(error_msg)
                logger.error(error_msg)
        
        # Final progress update
        progress.hours_completed = total_hours
        progress.current_status = f"Download complete: {progress.hours_successful}/{total_hours} files"
        
        if progress_callback:
            await progress_callback(progress)
        
        logger.info(
            f"Download complete: {symbol} - {progress.hours_successful} successful, "
            f"{progress.hours_failed} failed/skipped"
        )
        
        return successful_downloads
    
    async def estimate_data_size(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> dict:
        """
        Estimate data size and timeframe for download.
        
        Args:
            symbol: Trading pair
            start_date: Start datetime
            end_date: End datetime
        
        Returns:
            Dictionary with estimates
        """
        hours = []
        current = start_date.replace(minute=0, second=0, microsecond=0)
        end = end_date.replace(minute=0, second=0, microsecond=0)
        
        while current <= end:
            hours.append(current)
            current += timedelta(hours=1)
        
        total_hours = len(hours)
        
        # Average BI5 file size: ~50-200KB per hour (varies by liquidity)
        # Assume 100KB average
        avg_file_size_kb = 100
        estimated_size_mb = (total_hours * avg_file_size_kb) / 1024
        
        # Estimate download time (assume 1 second per file on average)
        estimated_time_minutes = total_hours / 60
        
        return {
            "symbol": symbol,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_hours": total_hours,
            "total_days": total_hours / 24,
            "estimated_size_mb": round(estimated_size_mb, 2),
            "estimated_time_minutes": round(estimated_time_minutes, 1),
            "estimated_m1_candles": total_hours * 60,  # 60 M1 candles per hour
            "warnings": [
                "Actual size may vary based on market activity",
                "Weekends and holidays will have no data (expected)",
                "Download time depends on network speed and Dukascopy server load"
            ]
        }
