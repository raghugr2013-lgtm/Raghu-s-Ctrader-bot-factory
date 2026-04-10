"""
Data Ingestion Module - M1 SSOT Architecture

Strict Rules:
- ONLY M1 data stored in database
- NO interpolation or synthetic data generation
- Higher TF CSV uploads are REJECTED (default)
- All timeframes derived via on-demand aggregation
- Gaps filled ONLY with real data (Dukascopy)

This module implements a Single Source of Truth (SSOT) architecture
where M1 (1-minute) candles are the only stored timeframe.
All higher timeframes are derived on-demand via aggregation.
"""

from .confidence_system import ConfidenceLevel, ConfidenceRules, DataSource
from .candle_models import (
    M1Candle, 
    CandleMetadata, 
    IngestionResult, 
    AggregatedCandle,
    GapInfo,
    CoverageReport,
    QualityReport
)
from .data_validation_layer import (
    DataValidator, 
    ConfidenceScorer, 
    MetadataTagger,
    ValidationResult,
    TimeframeDetector
)
from .bi5_processor import BI5Processor, TickToM1Aggregator
from .csv_ingestion import CSVIngestionEngine, CSVTimeframeDetector, CSVParser
from .timeframe_aggregator import TimeframeAggregator, AggregatedCandlesResult
from .data_service_v2 import DataServiceV2
from .data_ingestion_router import router as data_ingestion_router, init_data_ingestion_router
from .backtest_data_adapter import BacktestDataAdapter, DataQualityError, get_candles_for_backtest
from .legacy_adapter import LegacyDataAdapter, create_legacy_adapter

__all__ = [
    # Confidence System
    "ConfidenceLevel",
    "ConfidenceRules",
    "DataSource",
    
    # Models
    "M1Candle",
    "CandleMetadata",
    "IngestionResult",
    "AggregatedCandle",
    "GapInfo",
    "CoverageReport",
    "QualityReport",
    
    # Validation
    "DataValidator",
    "ConfidenceScorer",
    "MetadataTagger",
    "ValidationResult",
    "TimeframeDetector",
    
    # BI5 Processing
    "BI5Processor",
    "TickToM1Aggregator",
    
    # CSV Processing
    "CSVIngestionEngine",
    "CSVTimeframeDetector",
    "CSVParser",
    
    # Aggregation
    "TimeframeAggregator",
    "AggregatedCandlesResult",
    
    # Service
    "DataServiceV2",
    
    # Router
    "data_ingestion_router",
    "init_data_ingestion_router",
    
    # Backtest Integration
    "BacktestDataAdapter",
    "DataQualityError",
    "get_candles_for_backtest",
    
    # Legacy Compatibility
    "LegacyDataAdapter",
    "create_legacy_adapter",
]

# Module version
__version__ = "2.0.0"

# Architecture description
ARCHITECTURE_SUMMARY = """
M1 SSOT (Single Source of Truth) Data Architecture
===================================================

STORAGE:
- ONLY M1 (1-minute) candles stored in database
- Collection: market_candles_m1
- Every candle has metadata: source, confidence, original_timeframe

INGESTION:
- BI5 tick files → M1 candles (HIGH confidence)
- M1 CSV files → Direct storage (HIGH confidence)
- Higher TF CSV (M5, H1, D1) → REJECTED by default

RETRIEVAL:
- M1 requests → Direct from database
- Higher TF requests → Aggregated on-demand from M1
- Confidence filtering applied to all requests

CONFIDENCE LEVELS:
- HIGH: Production backtest, live trading
- MEDIUM: Research only
- LOW: Never used in backtest

GAPS:
- Detected automatically
- Filled ONLY with real Dukascopy data
- NO interpolation or synthetic data
"""
