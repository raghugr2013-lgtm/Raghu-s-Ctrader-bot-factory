"""
Candle Models - Pydantic Models for M1 SSOT Architecture

All candle data uses these standardized models.
Metadata is REQUIRED for every candle to ensure traceability.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid

from .confidence_system import ConfidenceLevel, DataSource


class CandleMetadata(BaseModel):
    """
    Metadata attached to every M1 candle.
    Critical for traceability and quality control.
    """
    model_config = ConfigDict(extra="ignore")
    
    source: str = Field(..., description="Data source: bi5, csv_m1, dukascopy, gap_fill")
    confidence: str = Field(..., description="Confidence level: high, medium, low")
    original_timeframe: str = Field(default="M1", description="Original timeframe of source data")
    upload_batch_id: str = Field(..., description="Batch ID for upload tracking")
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    validation_score: float = Field(default=1.0, ge=0.0, le=1.0)
    tick_count: Optional[int] = Field(default=None, description="Tick count for BI5 source")
    tags: Dict[str, Any] = Field(default_factory=dict)
    
    # IMPORTANT: No is_interpolated field - interpolation is NOT allowed


class M1Candle(BaseModel):
    """
    Single M1 candle with full metadata.
    This is the ONLY candle type stored in the database.
    """
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = Field(..., min_length=1, max_length=20)
    timestamp: datetime = Field(..., description="Candle open time in UTC")
    
    # OHLCV data
    open: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: float = Field(default=0.0, ge=0)
    
    # Required metadata
    metadata: CandleMetadata
    
    # Database timestamp
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        return {
            "id": self.id,
            "symbol": self.symbol.upper(),
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "metadata": {
                "source": self.metadata.source,
                "confidence": self.metadata.confidence,
                "original_timeframe": self.metadata.original_timeframe,
                "upload_batch_id": self.metadata.upload_batch_id,
                "ingested_at": self.metadata.ingested_at,
                "validation_score": self.metadata.validation_score,
                "tick_count": self.metadata.tick_count,
                "tags": self.metadata.tags
            },
            "created_at": self.created_at
        }
    
    @classmethod
    def from_db_dict(cls, data: Dict[str, Any]) -> "M1Candle":
        """Create from MongoDB document"""
        metadata = CandleMetadata(
            source=data["metadata"]["source"],
            confidence=data["metadata"]["confidence"],
            original_timeframe=data["metadata"].get("original_timeframe", "M1"),
            upload_batch_id=data["metadata"]["upload_batch_id"],
            ingested_at=data["metadata"].get("ingested_at", datetime.now(timezone.utc)),
            validation_score=data["metadata"].get("validation_score", 1.0),
            tick_count=data["metadata"].get("tick_count"),
            tags=data["metadata"].get("tags", {})
        )
        return cls(
            id=data["id"],
            symbol=data["symbol"],
            timestamp=data["timestamp"],
            open=data["open"],
            high=data["high"],
            low=data["low"],
            close=data["close"],
            volume=data.get("volume", 0),
            metadata=metadata,
            created_at=data.get("created_at", datetime.now(timezone.utc))
        )


class AggregatedCandle(BaseModel):
    """
    Candle aggregated from M1 data on-demand.
    NOT stored in database - computed each time.
    """
    model_config = ConfigDict(extra="ignore")
    
    symbol: str
    timeframe: str  # M5, M15, M30, H1, H4, D1, etc.
    timestamp: datetime
    
    # OHLCV
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    # Aggregation metadata
    source_m1_count: int = Field(..., description="Number of M1 candles used")
    expected_m1_count: int = Field(..., description="Expected M1 candles for this TF")
    has_gaps: bool = Field(default=False, description="True if any M1 candles missing")
    gap_count: int = Field(default=0, description="Number of missing M1 candles")
    
    # Propagated confidence (minimum of all source M1 candles)
    confidence: str = Field(..., description="Minimum confidence from source M1 candles")
    confidence_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of each confidence level in source candles"
    )


class IngestionResult(BaseModel):
    """Result of a data ingestion operation"""
    model_config = ConfigDict(extra="ignore")
    
    success: bool
    upload_batch_id: str
    symbol: str
    
    # The actual M1 candles (for passing to storage)
    candles: List[Any] = Field(default_factory=list)
    
    # Counts
    candles_processed: int = 0
    candles_stored: int = 0
    candles_rejected: int = 0
    duplicates_skipped: int = 0
    
    # Time range
    start_timestamp: Optional[datetime] = None
    end_timestamp: Optional[datetime] = None
    
    # Quality
    source: str = ""
    confidence_assigned: str = "high"
    validation_score: float = 1.0
    
    # Messages
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    
    # Rejected data info (for higher TF CSVs)
    rejected_reason: Optional[str] = None
    detected_timeframe: Optional[str] = None


class GapInfo(BaseModel):
    """Information about a gap in M1 data"""
    model_config = ConfigDict(extra="ignore")
    
    symbol: str
    start: datetime
    end: datetime
    missing_minutes: int
    is_market_closed: bool = False  # Weekend/holiday gaps
    
    def __str__(self) -> str:
        return f"Gap: {self.symbol} from {self.start} to {self.end} ({self.missing_minutes} minutes)"


class CoverageReport(BaseModel):
    """Data coverage report for a symbol"""
    model_config = ConfigDict(extra="ignore")
    
    symbol: str
    total_m1_candles: int
    first_timestamp: Optional[datetime]
    last_timestamp: Optional[datetime]
    
    # Coverage stats
    expected_candles: int = 0
    coverage_percentage: float = 0.0
    gap_count: int = 0
    total_gap_minutes: int = 0
    
    # Confidence breakdown
    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    low_confidence_count: int = 0
    
    # Source breakdown
    source_breakdown: Dict[str, int] = Field(default_factory=dict)
    
    # Gaps list (limited)
    largest_gaps: List[GapInfo] = Field(default_factory=list)


class QualityReport(BaseModel):
    """Detailed quality report for a date range"""
    model_config = ConfigDict(extra="ignore")
    
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    
    # Quality metrics
    quality_score: float = Field(ge=0.0, le=1.0)
    usable_for_backtest: bool
    usable_for_research: bool
    
    # Detailed breakdown
    total_candles: int
    gaps_detected: int
    confidence_distribution: Dict[str, int]
    
    # Issues found
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
