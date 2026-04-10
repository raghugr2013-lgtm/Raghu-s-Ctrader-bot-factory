"""
Backtest Data Integration - M1 SSOT Adapter

This module provides integration between the backtest engine
and the new M1 SSOT data architecture.

Key changes:
1. Backtest engine now uses DataServiceV2 for all data
2. Only HIGH confidence data allowed for production backtest
3. Data quality checks before backtest execution
4. Gap detection and warnings
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class BacktestDataAdapter:
    """
    Adapter to provide data to backtest engine from M1 SSOT.
    
    Ensures:
    - Only HIGH confidence data used for production
    - Quality checks before backtest
    - Proper error messages for data issues
    """
    
    def __init__(self, data_service):
        """
        Initialize adapter.
        
        Args:
            data_service: DataServiceV2 instance
        """
        self.data_service = data_service
    
    async def get_backtest_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        min_quality_score: float = 0.95
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Get data for backtesting with quality validation.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            start_date: Backtest start
            end_date: Backtest end
            min_quality_score: Minimum data quality required
        
        Returns:
            (candles, quality_info)
        
        Raises:
            DataQualityError: If data doesn't meet quality requirements
        """
        # Get data with HIGH confidence filter (production requirement)
        result = await self.data_service.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            min_confidence="high",
            use_case="production_backtest"
        )
        
        # Quality check
        if not result.usable_for_backtest:
            raise DataQualityError(
                f"Data quality insufficient for backtest. "
                f"Score: {result.quality_score:.1%}, Required: {min_quality_score:.1%}. "
                f"Gaps: {result.gaps_detected}. "
                f"Please upload more M1/BI5 data or fix gaps."
            )
        
        if result.quality_score < min_quality_score:
            raise DataQualityError(
                f"Data quality {result.quality_score:.1%} below required {min_quality_score:.1%}"
            )
        
        # Convert to legacy format for backtest engine compatibility
        candles = [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume
            }
            for c in result.candles
        ]
        
        quality_info = {
            "source_m1_count": result.source_m1_count,
            "gaps_detected": result.gaps_detected,
            "quality_score": result.quality_score,
            "confidence_distribution": result.confidence_distribution,
            "warnings": result.warnings
        }
        
        logger.info(
            f"Backtest data loaded: {symbol} {timeframe} - "
            f"{len(candles)} candles, quality: {result.quality_score:.1%}"
        )
        
        return candles, quality_info
    
    async def validate_data_for_backtest(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Pre-validate data before running backtest.
        
        Call this before starting a long backtest to check data quality.
        """
        report = await self.data_service.get_quality_report(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "is_valid": report.usable_for_backtest,
            "quality_score": report.quality_score,
            "total_candles": report.total_candles,
            "gaps_detected": report.gaps_detected,
            "confidence_distribution": report.confidence_distribution,
            "issues": report.issues,
            "recommendations": report.recommendations
        }


class DataQualityError(Exception):
    """Raised when data quality is insufficient for backtest"""
    pass


# Integration function for existing backtest engine
async def get_candles_for_backtest(
    db,
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    data_service=None
) -> List[Dict[str, Any]]:
    """
    Compatibility function for existing backtest engine.
    
    This function can be used as a drop-in replacement for direct DB queries.
    """
    if data_service is None:
        # Import here to avoid circular imports
        from data_ingestion import DataServiceV2
        data_service = DataServiceV2(db)
    
    adapter = BacktestDataAdapter(data_service)
    
    try:
        candles, _ = await adapter.get_backtest_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date
        )
        return candles
    except DataQualityError as e:
        logger.error(f"Data quality error: {e}")
        raise


# Quality gate decorator for backtest functions
def require_high_quality_data(func):
    """
    Decorator to ensure HIGH confidence data for backtest functions.
    
    Usage:
        @require_high_quality_data
        async def run_backtest(...):
            ...
    """
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Check for data service in kwargs or args
        data_service = kwargs.get('data_service')
        symbol = kwargs.get('symbol')
        timeframe = kwargs.get('timeframe')
        
        if data_service and symbol and timeframe:
            # Quick quality check
            coverage = await data_service.get_coverage(symbol)
            if coverage.low_confidence_count > 0:
                logger.warning(
                    f"Low confidence data present for {symbol}. "
                    f"Consider purging before production backtest."
                )
        
        return await func(*args, **kwargs)
    
    return wrapper
