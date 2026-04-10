"""
Legacy Data Service Adapter
Bridges old market_data_service calls to new M1 SSOT architecture.

This allows gradual migration without breaking existing code.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from market_data_models import Candle, DataTimeframe

logger = logging.getLogger(__name__)


class LegacyDataAdapter:
    """
    Adapter that wraps DataServiceV2 to provide legacy interface.
    
    This allows existing code using market_data_service to transparently
    use the new M1 SSOT architecture.
    """
    
    def __init__(self, data_service_v2, legacy_service=None):
        """
        Initialize adapter.
        
        Args:
            data_service_v2: The new M1 SSOT DataServiceV2
            legacy_service: Optional legacy MarketDataService for fallback
        """
        self.v2 = data_service_v2
        self.legacy = legacy_service
    
    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get candles using new M1 SSOT architecture.
        
        This method provides backwards compatibility with the old interface
        while using the new aggregation system under the hood.
        """
        try:
            # Try new system first
            result = await self.v2.get_candles(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                min_confidence="high",  # Production default
                use_case="production_backtest"
            )
            
            if result.candles:
                # Convert to legacy format
                candles = []
                for c in result.candles:
                    candles.append({
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "timestamp": c.timestamp,
                        "open": c.open,
                        "high": c.high,
                        "low": c.low,
                        "close": c.close,
                        "volume": c.volume
                    })
                
                logger.debug(f"Retrieved {len(candles)} candles from M1 SSOT for {symbol} {timeframe}")
                return candles
            
        except Exception as e:
            logger.warning(f"M1 SSOT retrieval failed: {e}, falling back to legacy")
        
        # Fallback to legacy system if available
        if self.legacy:
            try:
                return await self.legacy.get_candles(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit
                )
            except Exception as e:
                logger.error(f"Legacy retrieval also failed: {e}")
        
        return []
    
    async def get_candles_for_backtest(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        require_high_confidence: bool = True
    ) -> tuple:
        """
        Get candles specifically for backtesting with quality check.
        
        Returns:
            (candles, quality_info) tuple
        """
        result = await self.v2.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            min_confidence="high" if require_high_confidence else "medium",
            use_case="production_backtest" if require_high_confidence else "research_backtest"
        )
        
        candles = []
        for c in result.candles:
            candles.append({
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume
            })
        
        quality_info = {
            "quality_score": result.quality_score,
            "usable_for_backtest": result.usable_for_backtest,
            "gaps_detected": result.gaps_detected,
            "source_m1_count": result.source_m1_count,
            "confidence_distribution": result.confidence_distribution,
            "warnings": result.warnings
        }
        
        return candles, quality_info
    
    async def validate_data_quality(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Validate data quality before running backtest.
        """
        report = await self.v2.get_quality_report(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "is_valid": report.usable_for_backtest,
            "quality_score": report.quality_score,
            "total_candles": report.total_candles,
            "gaps_detected": report.gaps_detected,
            "issues": report.issues,
            "recommendations": report.recommendations
        }


def create_legacy_adapter(data_service_v2, market_data_service=None):
    """
    Factory function to create legacy adapter.
    
    Usage in server.py:
        legacy_adapter = create_legacy_adapter(data_service_v2, market_data_service)
        # Use legacy_adapter.get_candles() instead of market_data_service.get_candles()
    """
    return LegacyDataAdapter(data_service_v2, market_data_service)
