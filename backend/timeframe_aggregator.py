"""
Timeframe Aggregator Service
Dynamically aggregates 1-minute candles to higher timeframes.

ARCHITECTURE PRINCIPLE:
- 1m candles are the SINGLE SOURCE OF TRUTH
- All higher timeframes (5m, 15m, 30m, 1h, 4h, 1d) are DERIVED ON-DEMAND
- NO storage of aggregated timeframes in database
- Perfect consistency guaranteed across all timeframes
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class TimeframeAggregator:
    """
    Aggregates 1-minute candles to any higher timeframe.
    
    Supports: 5m, 15m, 30m, 1h, 4h, 1d
    """
    
    # Timeframe definitions (in minutes)
    TIMEFRAME_MINUTES = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440
    }
    
    def __init__(self):
        logger.info("[TIMEFRAME AGGREGATOR] Initialized")
    
    def aggregate(
        self,
        candles_1m: List[Dict[str, Any]],
        target_timeframe: str
    ) -> List[Dict[str, Any]]:
        """
        Aggregate 1-minute candles to target timeframe.
        
        Args:
            candles_1m: List of 1-minute candles (MUST be sorted by timestamp)
            target_timeframe: Target timeframe (5m, 15m, 30m, 1h, 4h, 1d)
            
        Returns:
            List of aggregated candles
        """
        if target_timeframe == "1m":
            # No aggregation needed
            return candles_1m
        
        if target_timeframe not in self.TIMEFRAME_MINUTES:
            raise ValueError(f"Unsupported timeframe: {target_timeframe}")
        
        if not candles_1m:
            return []
        
        interval_minutes = self.TIMEFRAME_MINUTES[target_timeframe]
        
        logger.info(
            f"[AGGREGATOR] Aggregating {len(candles_1m)} 1m candles → {target_timeframe} "
            f"(interval: {interval_minutes} minutes)"
        )
        
        # Group candles by timeframe bucket
        buckets = defaultdict(list)
        
        for candle in candles_1m:
            timestamp = candle["timestamp"]
            
            # Calculate bucket start time
            bucket_start = self._get_bucket_start(timestamp, interval_minutes)
            buckets[bucket_start].append(candle)
        
        # Aggregate each bucket
        aggregated = []
        for bucket_start in sorted(buckets.keys()):
            bucket_candles = buckets[bucket_start]
            
            # Aggregate OHLCV
            aggregated_candle = self._aggregate_bucket(
                bucket_candles,
                bucket_start,
                target_timeframe
            )
            
            aggregated.append(aggregated_candle)
        
        logger.info(f"[AGGREGATOR] Produced {len(aggregated)} {target_timeframe} candles")
        
        return aggregated
    
    def _get_bucket_start(self, timestamp: datetime, interval_minutes: int) -> datetime:
        """
        Calculate the start time of the timeframe bucket for a given timestamp.
        
        Examples:
            timestamp: 2024-01-01 10:37:00, interval: 5m → 2024-01-01 10:35:00
            timestamp: 2024-01-01 10:37:00, interval: 1h → 2024-01-01 10:00:00
        """
        # Floor to interval boundary
        total_minutes = timestamp.hour * 60 + timestamp.minute
        bucket_minutes = (total_minutes // interval_minutes) * interval_minutes
        
        bucket_start = timestamp.replace(
            hour=bucket_minutes // 60,
            minute=bucket_minutes % 60,
            second=0,
            microsecond=0
        )
        
        return bucket_start
    
    def _aggregate_bucket(
        self,
        bucket_candles: List[Dict[str, Any]],
        bucket_start: datetime,
        timeframe: str
    ) -> Dict[str, Any]:
        """
        Aggregate a bucket of 1m candles into a single higher-timeframe candle.
        
        OHLCV Aggregation Rules:
        - Open: First candle's open
        - High: Maximum of all highs
        - Low: Minimum of all lows
        - Close: Last candle's close
        - Volume: Sum of all volumes
        """
        if not bucket_candles:
            raise ValueError("Cannot aggregate empty bucket")
        
        # Sort by timestamp (should already be sorted, but ensure it)
        sorted_candles = sorted(bucket_candles, key=lambda c: c["timestamp"])
        
        # Aggregate
        aggregated = {
            "timestamp": bucket_start,
            "open": sorted_candles[0]["open"],
            "high": max(c["high"] for c in sorted_candles),
            "low": min(c["low"] for c in sorted_candles),
            "close": sorted_candles[-1]["close"],
            "volume": sum(c.get("volume", 0) for c in sorted_candles),
            "timeframe": timeframe,
            "symbol": sorted_candles[0].get("symbol", "UNKNOWN"),
            "provider": "dukascopy",  # Inherited from source
            "is_aggregated": True,  # Mark as derived from 1m
            "source_candles": len(sorted_candles),  # How many 1m candles were aggregated
            "is_filled": False  # Real data, not synthetic
        }
        
        return aggregated
    
    async def aggregate_from_db(
        self,
        db,
        symbol: str,
        target_timeframe: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch 1m candles from database and aggregate to target timeframe.
        
        Args:
            db: MongoDB database instance
            symbol: Trading symbol
            target_timeframe: Target timeframe
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of aggregated candles
        """
        # Build query
        query = {
            "symbol": symbol,
            "timeframe": "1m"  # ALWAYS fetch 1m as source
        }
        
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date
        
        # Fetch 1m candles
        logger.info(f"[AGGREGATOR] Fetching 1m candles from DB for {symbol}")
        candles_1m = await db.market_candles.find(
            query,
            {"_id": 0}  # Exclude MongoDB _id
        ).sort("timestamp", 1).to_list(None)
        
        logger.info(f"[AGGREGATOR] Fetched {len(candles_1m)} 1m candles")
        
        if not candles_1m:
            logger.warning(f"[AGGREGATOR] No 1m data found for {symbol}")
            return []
        
        # Aggregate to target timeframe
        return self.aggregate(candles_1m, target_timeframe)
    
    def validate_coverage(
        self,
        candles: List[Dict[str, Any]],
        timeframe: str
    ) -> Dict[str, Any]:
        """
        Validate timeframe coverage and detect gaps.
        
        Args:
            candles: List of candles (any timeframe)
            timeframe: Timeframe of the candles
            
        Returns:
            {
                "total_candles": int,
                "expected_candles": int,
                "coverage_percent": float,
                "gap_count": int,
                "gaps": List of gap ranges
            }
        """
        if not candles:
            return {
                "total_candles": 0,
                "expected_candles": 0,
                "coverage_percent": 0.0,
                "gap_count": 0,
                "gaps": []
            }
        
        sorted_candles = sorted(candles, key=lambda c: c["timestamp"])
        start = sorted_candles[0]["timestamp"]
        end = sorted_candles[-1]["timestamp"]
        
        interval_minutes = self.TIMEFRAME_MINUTES.get(timeframe, 1)
        interval_delta = timedelta(minutes=interval_minutes)
        
        # Calculate expected candles
        expected_candles = 0
        current = start
        while current <= end:
            # Skip weekends for forex (Saturday/Sunday)
            if current.weekday() < 5:  # Monday-Friday
                expected_candles += 1
            current += interval_delta
        
        # Detect gaps
        gaps = []
        gap_count = 0
        
        for i in range(len(sorted_candles) - 1):
            current_candle = sorted_candles[i]
            next_candle = sorted_candles[i + 1]
            
            expected_next = current_candle["timestamp"] + interval_delta
            actual_next = next_candle["timestamp"]
            
            # Gap detected if next candle is more than 1 interval away
            if actual_next > expected_next + interval_delta:
                gap_count += 1
                gaps.append({
                    "start": current_candle["timestamp"].isoformat(),
                    "end": next_candle["timestamp"].isoformat(),
                    "missing_candles": int((actual_next - expected_next).total_seconds() / 60 / interval_minutes)
                })
        
        coverage_percent = (len(candles) / expected_candles * 100) if expected_candles > 0 else 0
        
        return {
            "total_candles": len(candles),
            "expected_candles": expected_candles,
            "coverage_percent": round(coverage_percent, 2),
            "gap_count": gap_count,
            "gaps": gaps[:10]  # Return first 10 gaps
        }


# Global singleton
_aggregator = TimeframeAggregator()


def get_aggregator() -> TimeframeAggregator:
    """Get global aggregator instance."""
    return _aggregator
