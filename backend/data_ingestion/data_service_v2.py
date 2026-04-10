"""
Data Service V2 - Unified M1 SSOT Data Access Layer

This is the SINGLE entry point for all data operations.
External components should NOT query the database directly.

Features:
- M1 ingestion (BI5, CSV M1)
- On-demand aggregation to any timeframe
- Gap detection and real-data filling
- Quality reporting
- Confidence enforcement
"""

import logging
import uuid
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta, timezone

from .confidence_system import ConfidenceLevel, ConfidenceRules, DataSource
from .candle_models import (
    M1Candle, 
    IngestionResult, 
    AggregatedCandle, 
    GapInfo, 
    CoverageReport,
    QualityReport
)
from .bi5_processor import BI5Processor
from .csv_ingestion import CSVIngestionEngine
from .timeframe_aggregator import TimeframeAggregator, AggregatedCandlesResult
from .data_validation_layer import DataValidator

logger = logging.getLogger(__name__)


class DataServiceV2:
    """
    Unified data service implementing strict M1 SSOT architecture.
    
    RULES:
    1. ONLY M1 data stored in database
    2. All higher TF computed on-demand via aggregation
    3. NO interpolation or synthetic data
    4. Confidence tagging on all data
    5. Quality gates for backtest usage
    """
    
    COLLECTION_NAME = "market_candles_m1"
    
    def __init__(self, db):
        """
        Initialize data service.
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection = db[self.COLLECTION_NAME]
        
        # Initialize components
        self.bi5_processor = BI5Processor()
        self.csv_engine = CSVIngestionEngine()
        self.aggregator = TimeframeAggregator(db)
        self.validator = DataValidator()
        
        # Ensure indexes
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create required indexes for performance"""
        try:
            # Main query index
            self.collection.create_index(
                [("symbol", 1), ("timestamp", 1)],
                unique=True,
                name="symbol_timestamp_unique"
            )
            # Confidence filter index
            self.collection.create_index(
                [("metadata.confidence", 1)],
                name="confidence_idx"
            )
            # Batch tracking index
            self.collection.create_index(
                [("metadata.upload_batch_id", 1)],
                name="batch_idx"
            )
            logger.info("Database indexes ensured")
        except Exception as e:
            logger.warning(f"Index creation warning: {e}")
    
    # ========== INGESTION METHODS ==========
    
    async def ingest_bi5(
        self,
        file_bytes: bytes,
        symbol: str,
        base_datetime: datetime,
        upload_batch_id: Optional[str] = None
    ) -> IngestionResult:
        """
        Ingest BI5 tick file → M1 candles.
        
        Args:
            file_bytes: Raw BI5 file content
            symbol: Trading symbol
            base_datetime: Hour being processed
            upload_batch_id: Batch tracking ID
        
        Returns:
            IngestionResult with stored candle count
        """
        # Process BI5 file
        result = await self.bi5_processor.process_upload(
            file_bytes=file_bytes,
            symbol=symbol,
            base_datetime=base_datetime,
            upload_batch_id=upload_batch_id
        )
        
        if not result.success or not hasattr(result, 'candles') or not result.candles:
            return result
        
        # Store M1 candles
        stored_count = await self._store_candles(result.candles)
        result.candles_stored = stored_count
        
        # Invalidate cache
        self.aggregator.invalidate_cache(symbol.upper())
        
        logger.info(f"BI5 ingestion: {symbol} {base_datetime} - {stored_count} M1 candles stored")
        
        return result
    
    async def ingest_csv(
        self,
        file_content: bytes,
        symbol: str,
        declared_timeframe: Optional[str] = None,
        research_override: bool = False,
        upload_batch_id: Optional[str] = None
    ) -> IngestionResult:
        """
        Ingest CSV file → M1 candles.
        
        STRICT: Only M1 CSV accepted. Higher TF REJECTED by default.
        
        Args:
            file_content: Raw CSV bytes
            symbol: Trading symbol
            declared_timeframe: User-declared TF
            research_override: Allow higher TF for research ONLY
            upload_batch_id: Batch tracking ID
        
        Returns:
            IngestionResult (rejected if not M1)
        """
        # Process CSV
        result = await self.csv_engine.ingest(
            file_content=file_content,
            symbol=symbol,
            declared_timeframe=declared_timeframe,
            research_override=research_override,
            upload_batch_id=upload_batch_id
        )
        
        if not result.success or not hasattr(result, 'candles') or not result.candles:
            return result
        
        # Store M1 candles
        stored_count = await self._store_candles(result.candles)
        result.candles_stored = stored_count
        
        # Invalidate cache
        self.aggregator.invalidate_cache(symbol.upper())
        
        logger.info(
            f"CSV ingestion: {symbol} - {stored_count} M1 candles stored "
            f"(detected TF: {result.detected_timeframe})"
        )
        
        return result
    
    async def _store_candles(self, candles: List[M1Candle]) -> int:
        """
        Store M1 candles in database with upsert.
        
        Returns:
            Number of candles stored/updated
        """
        if not candles:
            return 0
        
        stored = 0
        
        for candle in candles:
            try:
                doc = candle.to_db_dict()
                
                # Upsert by symbol + timestamp
                await self.collection.update_one(
                    {
                        "symbol": doc["symbol"],
                        "timestamp": doc["timestamp"]
                    },
                    {"$set": doc},
                    upsert=True
                )
                stored += 1
                
            except Exception as e:
                logger.warning(f"Failed to store candle: {e}")
        
        return stored
    
    # ========== RETRIEVAL METHODS ==========
    
    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        min_confidence: str = "high",
        use_case: str = "production_backtest"
    ) -> AggregatedCandlesResult:
        """
        Get candles for any timeframe.
        
        M1 = direct from SSOT
        Higher TF = aggregated on-demand
        
        Args:
            symbol: Trading symbol
            timeframe: M1, M5, M15, M30, H1, H4, D1
            start_date: Start datetime (UTC)
            end_date: End datetime (UTC)
            min_confidence: Minimum confidence filter
            use_case: What the data will be used for (affects validation)
        
        Returns:
            AggregatedCandlesResult with candles and quality metrics
        """
        # Validate use case requirements
        required_confidence = ConfidenceRules.get_minimum_for_use_case(use_case)
        
        # Ensure requested confidence meets use case minimum
        requested_conf = ConfidenceLevel.from_string(min_confidence)
        if requested_conf < required_confidence:
            logger.warning(
                f"Requested confidence '{min_confidence}' below requirement for {use_case}. "
                f"Upgrading to '{required_confidence.value}'"
            )
            min_confidence = required_confidence.value
        
        # Get aggregated data
        result = await self.aggregator.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            min_confidence=min_confidence
        )
        
        # Add use case validation warnings
        if use_case == "production_backtest" and not result.usable_for_backtest:
            result.warnings.append(
                f"\u26a0\ufe0f Data quality insufficient for production backtest. "
                f"Quality: {result.quality_score:.1%}, Gaps: {result.gaps_detected}"
            )
        
        return result
    
    async def get_m1_direct(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        min_confidence: str = "high"
    ) -> List[Dict[str, Any]]:
        """
        Get raw M1 data directly from database.
        
        For internal use - prefer get_candles() for consistency.
        """
        # Build confidence filter
        if min_confidence == "high":
            conf_filter = {"metadata.confidence": "high"}
        elif min_confidence == "medium":
            conf_filter = {"metadata.confidence": {"$in": ["high", "medium"]}}
        else:
            conf_filter = {}
        
        query = {
            "symbol": symbol.upper(),
            "timestamp": {"$gte": start_date, "$lte": end_date},
            **conf_filter
        }
        
        cursor = self.collection.find(query, {"_id": 0}).sort("timestamp", 1)
        return await cursor.to_list(length=None)
    
    # ========== COVERAGE & QUALITY ==========
    
    async def get_coverage(self, symbol: str) -> CoverageReport:
        """
        Get data coverage report for a symbol.
        """
        symbol = symbol.upper()
        
        # Total count
        total = await self.collection.count_documents({"symbol": symbol})
        
        if total == 0:
            return CoverageReport(
                symbol=symbol,
                total_m1_candles=0,
                first_timestamp=None,
                last_timestamp=None
            )
        
        # Get date range
        first = await self.collection.find_one(
            {"symbol": symbol},
            sort=[("timestamp", 1)]
        )
        last = await self.collection.find_one(
            {"symbol": symbol},
            sort=[("timestamp", -1)]
        )
        
        # Confidence breakdown
        pipeline = [
            {"$match": {"symbol": symbol}},
            {"$group": {
                "_id": "$metadata.confidence",
                "count": {"$sum": 1}
            }}
        ]
        conf_counts = await self.collection.aggregate(pipeline).to_list(length=None)
        
        conf_breakdown = {"high": 0, "medium": 0, "low": 0}
        for item in conf_counts:
            conf_breakdown[item["_id"]] = item["count"]
        
        # Source breakdown
        pipeline = [
            {"$match": {"symbol": symbol}},
            {"$group": {
                "_id": "$metadata.source",
                "count": {"$sum": 1}
            }}
        ]
        source_counts = await self.collection.aggregate(pipeline).to_list(length=None)
        source_breakdown = {item["_id"]: item["count"] for item in source_counts}
        
        # Calculate expected and coverage
        first_ts = first["timestamp"]
        last_ts = last["timestamp"]
        expected = int((last_ts - first_ts).total_seconds() / 60)
        coverage = total / expected if expected > 0 else 0
        
        return CoverageReport(
            symbol=symbol,
            total_m1_candles=total,
            first_timestamp=first_ts,
            last_timestamp=last_ts,
            expected_candles=expected,
            coverage_percentage=coverage * 100,
            high_confidence_count=conf_breakdown["high"],
            medium_confidence_count=conf_breakdown["medium"],
            low_confidence_count=conf_breakdown["low"],
            source_breakdown=source_breakdown
        )
    
    async def get_quality_report(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> QualityReport:
        """
        Get detailed quality report for a date range.
        """
        # Get aggregated data to analyze
        result = await self.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            min_confidence="low"  # Get all to see distribution
        )
        
        return QualityReport(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            quality_score=result.quality_score,
            usable_for_backtest=result.usable_for_backtest,
            usable_for_research=result.usable_for_research,
            total_candles=len(result.candles),
            gaps_detected=result.gaps_detected,
            confidence_distribution=result.confidence_distribution,
            issues=result.warnings,
            recommendations=self._generate_recommendations(result)
        )
    
    def _generate_recommendations(self, result: AggregatedCandlesResult) -> List[str]:
        """Generate recommendations based on data quality"""
        recs = []
        
        if result.gaps_detected > 0:
            recs.append(
                f"Fix {result.gaps_detected} gaps using /api/v2/data/gaps/{result.symbol}/fix"
            )
        
        if result.confidence_distribution.get("low", 0) > 0:
            recs.append(
                "Remove low confidence data or re-upload with proper M1/BI5 source"
            )
        
        if result.quality_score < 0.95:
            recs.append(
                f"Upload additional M1 data to improve coverage from {result.quality_score:.1%}"
            )
        
        if not recs:
            recs.append("✅ Data quality is excellent. Ready for production backtest.")
        
        return recs
    
    # ========== GAP MANAGEMENT ==========
    
    async def detect_gaps(self, symbol: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[GapInfo]:
        """
        Detect gaps in M1 data.
        
        Returns list of gap periods that need filling.
        """
        symbol = symbol.upper()
        
        # Get date range if not specified
        if not start_date or not end_date:
            coverage = await self.get_coverage(symbol)
            if not coverage.first_timestamp:
                return []
            start_date = start_date or coverage.first_timestamp
            end_date = end_date or coverage.last_timestamp
        
        # Get all M1 timestamps
        cursor = self.collection.find(
            {
                "symbol": symbol,
                "timestamp": {"$gte": start_date, "$lte": end_date}
            },
            {"timestamp": 1}
        ).sort("timestamp", 1)
        
        candles = await cursor.to_list(length=None)
        
        if len(candles) < 2:
            return []
        
        gaps = []
        expected_delta = timedelta(minutes=1)
        
        for i in range(1, len(candles)):
            prev_ts = candles[i-1]["timestamp"]
            curr_ts = candles[i]["timestamp"]
            
            delta = curr_ts - prev_ts
            
            # Gap if more than 2 minutes (allow 1 minute tolerance)
            if delta > timedelta(minutes=2):
                # Check if it's a weekend gap
                is_weekend = self._is_weekend_period(prev_ts, curr_ts)
                
                gap = GapInfo(
                    symbol=symbol,
                    start=prev_ts + timedelta(minutes=1),
                    end=curr_ts - timedelta(minutes=1),
                    missing_minutes=int(delta.total_seconds() / 60) - 1,
                    is_market_closed=is_weekend
                )
                
                # Only report non-weekend gaps
                if not is_weekend:
                    gaps.append(gap)
        
        logger.info(f"Gap detection: {symbol} - found {len(gaps)} gaps")
        
        return gaps
    
    def _is_weekend_period(self, start: datetime, end: datetime) -> bool:
        """Check if gap spans forex weekend closure"""
        # Forex closes Friday ~21:00 UTC, opens Sunday ~21:00 UTC
        if start.weekday() == 4 and end.weekday() in [0, 6]:  # Friday to Sunday/Monday
            return True
        if start.weekday() == 5 or start.weekday() == 6:  # Saturday or Sunday
            return True
        return False
    
    async def fix_gaps(
        self,
        symbol: str,
        gaps: List[GapInfo],
        downloader=None,
        progress_callback: Optional[Callable] = None
    ) -> IngestionResult:
        """
        Fix gaps by downloading REAL M1 data from Dukascopy.
        
        STRICT: Only real data used - NO interpolation.
        
        Args:
            symbol: Trading symbol
            gaps: List of gaps to fill
            downloader: Dukascopy downloader instance
            progress_callback: Progress callback
        
        Returns:
            IngestionResult with filled candle count
        """
        batch_id = str(uuid.uuid4())
        
        result = IngestionResult(
            success=False,
            upload_batch_id=batch_id,
            symbol=symbol.upper(),
            source=DataSource.GAP_FILL.value
        )
        
        if downloader is None:
            result.errors.append(
                "Dukascopy downloader required for gap filling. "
                "Gaps can only be filled with REAL data."
            )
            return result
        
        total_filled = 0
        
        for i, gap in enumerate(gaps):
            if gap.is_market_closed:
                result.warnings.append(f"Skipping weekend gap: {gap}")
                continue
            
            if progress_callback:
                await progress_callback(
                    (i / len(gaps)) * 100,
                    f"Filling gap {i+1}/{len(gaps)}: {gap.start} to {gap.end}"
                )
            
            try:
                # Download real M1 data for gap period
                gap_result = await self.bi5_processor.process_range(
                    symbol=symbol,
                    start_date=gap.start,
                    end_date=gap.end,
                    downloader=downloader
                )
                
                if gap_result.success and hasattr(gap_result, 'candles'):
                    # Update source to gap_fill
                    for candle in gap_result.candles:
                        candle.metadata.source = DataSource.GAP_FILL.value
                        candle.metadata.upload_batch_id = batch_id
                    
                    # Store candles
                    stored = await self._store_candles(gap_result.candles)
                    total_filled += stored
                    
                result.warnings.extend(gap_result.warnings)
                
            except Exception as e:
                result.warnings.append(f"Failed to fill gap {gap}: {str(e)}")
        
        result.success = True
        result.candles_stored = total_filled
        result.confidence_assigned = ConfidenceLevel.HIGH.value  # Real data = HIGH
        
        # Invalidate cache
        self.aggregator.invalidate_cache(symbol.upper())
        
        logger.info(f"Gap fix complete: {symbol} - {total_filled} M1 candles filled")
        
        return result
    
    # ========== MAINTENANCE ==========
    
    async def purge_low_confidence(self, symbol: str) -> int:
        """
        Remove LOW confidence data from database.
        
        Use this to clean up research-only data before production use.
        """
        result = await self.collection.delete_many({
            "symbol": symbol.upper(),
            "metadata.confidence": "low"
        })
        
        # Invalidate cache
        self.aggregator.invalidate_cache(symbol.upper())
        
        logger.info(f"Purged {result.deleted_count} low confidence candles for {symbol}")
        
        return result.deleted_count
    
    async def delete_symbol_data(self, symbol: str) -> int:
        """
        Delete all data for a symbol.
        """
        result = await self.collection.delete_many({"symbol": symbol.upper()})
        
        # Invalidate cache
        self.aggregator.invalidate_cache(symbol.upper())
        
        logger.info(f"Deleted {result.deleted_count} candles for {symbol}")
        
        return result.deleted_count
