"""
BI5 Processor - Tick Data to M1 Conversion

Converts Dukascopy BI5 tick files to M1 candles.
All output is HIGH confidence data.

NO interpolation - missing minutes are left as gaps.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from .confidence_system import ConfidenceLevel, DataSource
from .candle_models import M1Candle, CandleMetadata, IngestionResult
from .data_validation_layer import DataValidator, ConfidenceScorer, MetadataTagger, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class TickData:
    """Single tick from BI5 file"""
    timestamp_ms: int  # Milliseconds offset from base hour
    ask: float
    bid: float
    ask_volume: float
    bid_volume: float
    
    @property
    def mid(self) -> float:
        """Mid price"""
        return (self.ask + self.bid) / 2
    
    @property
    def volume(self) -> float:
        """Total volume"""
        return self.ask_volume + self.bid_volume


class TickToM1Aggregator:
    """
    Aggregate raw ticks to M1 candles.
    
    Rules:
    - Group ticks by minute boundary
    - OHLC from mid price ((ask + bid) / 2)
    - Volume = sum of ask_vol + bid_vol
    - Missing minutes are LEFT AS GAPS (no filling)
    """
    
    def aggregate(
        self,
        ticks: List[TickData],
        base_hour: datetime
    ) -> List[Dict[str, Any]]:
        """
        Aggregate ticks to M1 candles.
        
        Args:
            ticks: List of tick data
            base_hour: Base datetime (hour start)
        
        Returns:
            List of M1 candle dictionaries
        """
        if not ticks:
            return []
        
        # Group ticks by minute
        minute_groups: Dict[int, List[TickData]] = {}
        
        for tick in ticks:
            # Calculate absolute timestamp
            tick_time = base_hour + timedelta(milliseconds=tick.timestamp_ms)
            minute_key = tick_time.minute
            
            if minute_key not in minute_groups:
                minute_groups[minute_key] = []
            minute_groups[minute_key].append(tick)
        
        # Build M1 candles for each minute with data
        candles = []
        
        for minute, minute_ticks in sorted(minute_groups.items()):
            if not minute_ticks:
                continue
            
            # Get OHLC from mid prices
            prices = [t.mid for t in minute_ticks]
            volumes = [t.volume for t in minute_ticks]
            
            candle_time = base_hour.replace(minute=minute, second=0, microsecond=0)
            
            candle = {
                "timestamp": candle_time,
                "open": prices[0],
                "high": max(prices),
                "low": min(prices),
                "close": prices[-1],
                "volume": sum(volumes),
                "tick_count": len(minute_ticks)
            }
            
            candles.append(candle)
        
        return candles


class BI5Processor:
    """
    Process BI5 files and convert to M1 candles.
    
    Flow:
    1. Decode LZMA-compressed BI5 file (handled by bi5_decoder)
    2. Parse tick data
    3. Aggregate ticks to M1 candles
    4. Validate and tag with HIGH confidence
    5. Return M1 candles with metadata
    
    NO interpolation - gaps are preserved.
    """
    
    def __init__(self, bi5_decoder=None):
        """
        Initialize BI5 processor.
        
        Args:
            bi5_decoder: BI5 decoder instance (will be imported if not provided)
        """
        if bi5_decoder is None:
            try:
                from bi5_decoder import BI5Decoder
                self.decoder = BI5Decoder()
            except ImportError:
                logger.warning("BI5Decoder not available, will need to be provided")
                self.decoder = None
        else:
            self.decoder = bi5_decoder
        
        self.aggregator = TickToM1Aggregator()
        self.validator = DataValidator()
        self.scorer = ConfidenceScorer()
        self.tagger = MetadataTagger()
    
    async def process_upload(
        self,
        file_bytes: bytes,
        symbol: str,
        base_datetime: datetime,
        upload_batch_id: Optional[str] = None
    ) -> IngestionResult:
        """
        Process single BI5 file upload.
        
        Args:
            file_bytes: Raw BI5 file content
            symbol: Trading symbol (e.g., "EURUSD")
            base_datetime: Hour being processed
            upload_batch_id: Batch ID for tracking
        
        Returns:
            IngestionResult with M1 candles
        """
        batch_id = upload_batch_id or str(uuid.uuid4())
        
        result = IngestionResult(
            success=False,
            upload_batch_id=batch_id,
            symbol=symbol.upper(),
            source=DataSource.BI5.value,
            confidence_assigned=ConfidenceLevel.HIGH.value
        )
        
        try:
            # Step 1: Decode BI5 file
            if self.decoder is None:
                result.errors.append("BI5 decoder not available")
                return result
            
            ticks = self.decoder.decode(file_bytes)
            
            if not ticks:
                result.warnings.append(f"No ticks found in BI5 file for {base_datetime}")
                result.success = True  # Empty file is not an error
                return result
            
            # Step 2: Convert ticks to TickData objects
            tick_data = [
                TickData(
                    timestamp_ms=t.get("timestamp_ms", t.get("time_offset", 0)),
                    ask=t.get("ask", t.get("ask_price", 0)),
                    bid=t.get("bid", t.get("bid_price", 0)),
                    ask_volume=t.get("ask_volume", t.get("ask_vol", 0)),
                    bid_volume=t.get("bid_volume", t.get("bid_vol", 0))
                )
                for t in ticks
            ]
            
            # Step 3: Aggregate to M1
            raw_candles = self.aggregator.aggregate(tick_data, base_datetime)
            
            if not raw_candles:
                result.warnings.append(f"No M1 candles generated from {len(ticks)} ticks")
                result.success = True
                return result
            
            # Step 4: Add symbol to candles
            for candle in raw_candles:
                candle["symbol"] = symbol.upper()
            
            # Step 5: Validate
            validation = ValidationResult()
            for candle in raw_candles:
                candle_val = self.validator.validate_ohlcv(candle)
                validation.merge(candle_val)
            
            seq_val = self.validator.validate_sequence(raw_candles)
            validation.merge(seq_val)
            
            if not validation.is_valid:
                result.errors.extend(validation.errors)
                result.candles_rejected = len(raw_candles)
                return result
            
            # Step 6: Score confidence
            confidence, val_score = self.scorer.score(
                DataSource.BI5.value,
                validation
            )
            
            # Step 7: Tag with metadata
            tick_count = len(tick_data)
            result.candles = self.tagger.tag(
                candles=raw_candles,
                source=DataSource.BI5.value,
                confidence=confidence,
                upload_batch_id=batch_id,
                validation_score=val_score,
                tick_count=tick_count,
                additional_tags={
                    "base_hour": base_datetime.isoformat(),
                    "total_ticks": tick_count
                }
            )
            
            # Update result
            result.success = True
            result.candles_processed = len(raw_candles)
            result.candles_stored = len(result.candles)
            result.confidence_assigned = confidence.value
            result.validation_score = val_score
            result.warnings.extend(validation.warnings)
            
            if raw_candles:
                result.start_timestamp = raw_candles[0]["timestamp"]
                result.end_timestamp = raw_candles[-1]["timestamp"]
            
            # Check for gaps (missing minutes)
            expected_minutes = 60
            actual_minutes = len(raw_candles)
            if actual_minutes < expected_minutes:
                gap_count = expected_minutes - actual_minutes
                result.warnings.append(
                    f"Gap detected: {gap_count} missing minutes in hour (expected 60, got {actual_minutes})"
                )
            
            logger.info(
                f"BI5 processed: {symbol} {base_datetime.date()} {base_datetime.hour:02d}:00 - "
                f"{len(result.candles)} M1 candles from {tick_count} ticks"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"BI5 processing error: {str(e)}", exc_info=True)
            result.errors.append(f"Processing error: {str(e)}")
            return result
    
    async def process_range(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        downloader=None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> IngestionResult:
        """
        Download and process date range.
        Creates M1 candles for entire range.
        
        Args:
            symbol: Trading symbol
            start_date: Start datetime
            end_date: End datetime
            downloader: Dukascopy downloader instance
            progress_callback: Optional callback (progress_pct, message)
        
        Returns:
            Combined IngestionResult for entire range
        """
        batch_id = str(uuid.uuid4())
        
        result = IngestionResult(
            success=False,
            upload_batch_id=batch_id,
            symbol=symbol.upper(),
            source=DataSource.DUKASCOPY.value,
            confidence_assigned=ConfidenceLevel.HIGH.value
        )
        
        if downloader is None:
            result.errors.append("Dukascopy downloader not provided")
            return result
        
        try:
            # Generate list of hours to download
            hours = []
            current = start_date.replace(minute=0, second=0, microsecond=0)
            while current <= end_date:
                hours.append(current)
                current += timedelta(hours=1)
            
            total_hours = len(hours)
            all_candles = []
            
            for i, hour in enumerate(hours):
                # Progress callback
                if progress_callback:
                    progress = (i / total_hours) * 100
                    await progress_callback(progress, f"Processing {hour}")
                
                try:
                    # Download hour data
                    hour_result = await downloader.download_hour(symbol, hour)
                    
                    if hour_result and hour_result.get("ticks"):
                        # Process this hour
                        hour_ingestion = await self.process_upload(
                            file_bytes=hour_result["raw_data"],
                            symbol=symbol,
                            base_datetime=hour,
                            upload_batch_id=batch_id
                        )
                        
                        if hasattr(hour_ingestion, 'candles') and hour_ingestion.candles:
                            all_candles.extend(hour_ingestion.candles)
                        
                        result.warnings.extend(hour_ingestion.warnings)
                
                except Exception as e:
                    result.warnings.append(f"Failed to download {hour}: {str(e)}")
            
            # Combine results
            result.candles = all_candles
            result.candles_processed = len(all_candles)
            result.candles_stored = len(all_candles)
            result.success = True
            
            if all_candles:
                result.start_timestamp = all_candles[0].timestamp
                result.end_timestamp = all_candles[-1].timestamp
            
            logger.info(
                f"Range download complete: {symbol} {start_date.date()} to {end_date.date()} - "
                f"{len(all_candles)} M1 candles"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Range processing error: {str(e)}", exc_info=True)
            result.errors.append(f"Range processing error: {str(e)}")
            return result
