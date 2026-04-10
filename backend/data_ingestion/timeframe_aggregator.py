"""
Timeframe Aggregator - Dynamic M1 to Higher TF Conversion

Aggregates M1 candles to any higher timeframe ON-DEMAND.
NO storage of higher TF data - always computed from M1 source.

Features:
- Caching with configurable TTL
- Confidence propagation (minimum of source candles)
- Gap awareness and reporting
- Quality metrics for consumers
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
import asyncio

from .confidence_system import ConfidenceLevel, ConfidenceRules
from .candle_models import M1Candle, AggregatedCandle, GapInfo

logger = logging.getLogger(__name__)


@dataclass
class AggregatedCandlesResult:
    """Result of aggregation request"""
    candles: List[AggregatedCandle]
    timeframe: str
    symbol: str
    
    # Source data info
    source_m1_count: int
    expected_m1_count: int
    
    # Quality metrics
    gaps_detected: int
    gap_minutes: int
    confidence_distribution: Dict[str, int]
    quality_score: float  # 0-1, based on coverage and confidence
    
    # Usability flags
    usable_for_backtest: bool
    usable_for_research: bool
    
    # Issues
    warnings: List[str] = field(default_factory=list)


class SimpleCache:
    """
    Simple in-memory cache with TTL.
    For production, replace with Redis.
    """
    
    def __init__(self, default_ttl_seconds: int = 300):
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._default_ttl = default_ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        if key not in self._cache:
            return None
        
        value, expiry = self._cache[key]
        if datetime.now(timezone.utc) > expiry:
            del self._cache[key]
            return None
        
        return value
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Set value with TTL"""
        ttl = ttl_seconds or self._default_ttl
        expiry = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        self._cache[key] = (value, expiry)
    
    def invalidate(self, pattern: str):
        """Invalidate keys matching pattern (simple wildcard)"""
        if "*" in pattern:
            prefix = pattern.replace("*", "")
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
        else:
            keys_to_delete = [pattern] if pattern in self._cache else []
        
        for key in keys_to_delete:
            del self._cache[key]


class TimeframeAggregator:
    """
    Aggregate M1 candles to any higher timeframe on-demand.
    
    This is the ONLY way to get higher TF data in the M1 SSOT architecture.
    Data is NEVER stored - always computed from M1 source.
    """
    
    # Timeframe to minutes mapping
    TF_MINUTES = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "H1": 60,
        "H4": 240,
        "D1": 1440,
        "W1": 10080
    }
    
    def __init__(self, db, cache: Optional[SimpleCache] = None):
        """
        Initialize aggregator.
        
        Args:
            db: MongoDB database instance
            cache: Optional cache instance (in-memory or Redis)
        """
        self.db = db
        self.cache = cache or SimpleCache(default_ttl_seconds=300)
        self.collection_name = "market_candles_m1"
    
    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        min_confidence: str = "high",
        include_partial: bool = False,
        use_cache: bool = True
    ) -> AggregatedCandlesResult:
        """
        Get aggregated candles for requested timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Target timeframe (M1, M5, M15, M30, H1, H4, D1)
            start_date: Start datetime (UTC)
            end_date: End datetime (UTC)
            min_confidence: Minimum confidence filter ("high", "medium", "low")
            include_partial: Include incomplete current candle
            use_cache: Use caching
        
        Returns:
            AggregatedCandlesResult with candles and quality metrics
        """
        symbol = symbol.upper()
        
        # Validate timeframe
        if timeframe not in self.TF_MINUTES:
            raise ValueError(f"Unsupported timeframe: {timeframe}. Supported: {list(self.TF_MINUTES.keys())}")
        
        # Check cache
        cache_key = f"agg:{symbol}:{timeframe}:{start_date.date()}:{end_date.date()}:{min_confidence}"
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit: {cache_key}")
                return cached
        
        # Get M1 data
        m1_candles = await self._get_m1_data(symbol, start_date, end_date, min_confidence)
        
        # If requesting M1, return directly
        if timeframe == "M1":
            result = self._create_m1_result(m1_candles, symbol, start_date, end_date, min_confidence)
            if use_cache:
                self.cache.set(cache_key, result)
            return result
        
        # Aggregate to requested timeframe
        result = self._aggregate_to_timeframe(
            m1_candles=m1_candles,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            min_confidence=min_confidence,
            include_partial=include_partial
        )
        
        # Cache result
        if use_cache:
            self.cache.set(cache_key, result)
        
        return result
    
    async def _get_m1_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        min_confidence: str
    ) -> List[Dict[str, Any]]:
        """
        Get M1 data from database with confidence filtering.
        """
        # Build confidence filter
        if min_confidence == "high":
            confidence_filter = {"metadata.confidence": "high"}
        elif min_confidence == "medium":
            confidence_filter = {"metadata.confidence": {"$in": ["high", "medium"]}}
        else:
            confidence_filter = {}  # Accept all
        
        query = {
            "symbol": symbol,
            "timestamp": {
                "$gte": start_date,
                "$lte": end_date
            },
            **confidence_filter
        }
        
        cursor = self.db[self.collection_name].find(query).sort("timestamp", 1)
        candles = await cursor.to_list(length=None)
        
        return candles
    
    def _create_m1_result(
        self,
        candles: List[Dict[str, Any]],
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        min_confidence: str
    ) -> AggregatedCandlesResult:
        """
        Create result for M1 request (no aggregation needed).
        """
        # Count confidence distribution
        conf_dist = {"high": 0, "medium": 0, "low": 0}
        for c in candles:
            conf = c.get("metadata", {}).get("confidence", "low")
            conf_dist[conf] = conf_dist.get(conf, 0) + 1
        
        # Calculate expected candles (excluding weekends)
        expected = self._calculate_expected_m1_count(start_date, end_date)
        actual = len(candles)
        coverage = actual / expected if expected > 0 else 0
        
        # Detect gaps
        gaps, gap_minutes = self._detect_gaps(candles, start_date, end_date, 1)
        
        # Determine usability
        usable_backtest = coverage >= 0.95 and conf_dist.get("low", 0) == 0
        usable_research = coverage >= 0.80
        
        # Convert to AggregatedCandle format
        agg_candles = [
            AggregatedCandle(
                symbol=symbol,
                timeframe="M1",
                timestamp=c["timestamp"],
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c.get("volume", 0),
                source_m1_count=1,
                expected_m1_count=1,
                has_gaps=False,
                gap_count=0,
                confidence=c.get("metadata", {}).get("confidence", "low"),
                confidence_distribution={c.get("metadata", {}).get("confidence", "low"): 1}
            )
            for c in candles
        ]
        
        return AggregatedCandlesResult(
            candles=agg_candles,
            timeframe="M1",
            symbol=symbol,
            source_m1_count=actual,
            expected_m1_count=expected,
            gaps_detected=gaps,
            gap_minutes=gap_minutes,
            confidence_distribution=conf_dist,
            quality_score=coverage,
            usable_for_backtest=usable_backtest,
            usable_for_research=usable_research
        )
    
    def _aggregate_to_timeframe(
        self,
        m1_candles: List[Dict[str, Any]],
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        min_confidence: str,
        include_partial: bool
    ) -> AggregatedCandlesResult:
        """
        Aggregate M1 candles to target timeframe.
        """
        tf_minutes = self.TF_MINUTES[timeframe]
        
        # Group M1 candles by target candle period
        candle_groups: Dict[datetime, List[Dict[str, Any]]] = {}
        
        for m1 in m1_candles:
            ts = m1["timestamp"]
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            
            # Calculate candle period start
            period_start = self._round_to_period(ts, tf_minutes)
            
            if period_start not in candle_groups:
                candle_groups[period_start] = []
            candle_groups[period_start].append(m1)
        
        # Build aggregated candles
        aggregated = []
        total_gaps = 0
        total_gap_minutes = 0
        conf_dist = {"high": 0, "medium": 0, "low": 0}
        warnings = []
        
        for period_start in sorted(candle_groups.keys()):
            m1_list = candle_groups[period_start]
            
            if not m1_list:
                continue
            
            # Check completeness
            expected_m1 = tf_minutes
            actual_m1 = len(m1_list)
            has_gaps = actual_m1 < expected_m1
            gap_count = expected_m1 - actual_m1
            
            if has_gaps:
                total_gaps += 1
                total_gap_minutes += gap_count
            
            # Skip incomplete candles if not including partial
            if has_gaps and not include_partial:
                # Only skip if this is the current (most recent) candle
                if period_start == max(candle_groups.keys()):
                    continue
            
            # Aggregate OHLCV
            opens = [c["open"] for c in m1_list]
            highs = [c["high"] for c in m1_list]
            lows = [c["low"] for c in m1_list]
            closes = [c["close"] for c in m1_list]
            volumes = [c.get("volume", 0) for c in m1_list]
            
            # Get confidence distribution for this candle
            candle_conf_dist = {"high": 0, "medium": 0, "low": 0}
            for c in m1_list:
                conf = c.get("metadata", {}).get("confidence", "low")
                candle_conf_dist[conf] = candle_conf_dist.get(conf, 0) + 1
                conf_dist[conf] = conf_dist.get(conf, 0) + 1
            
            # Propagate minimum confidence
            confidences = [ConfidenceLevel.from_string(c.get("metadata", {}).get("confidence", "low")) for c in m1_list]
            propagated_confidence = ConfidenceRules.propagate_aggregation(confidences)
            
            # Sort M1 candles by timestamp for correct OHLC
            m1_sorted = sorted(m1_list, key=lambda x: x["timestamp"])
            
            agg_candle = AggregatedCandle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=period_start,
                open=m1_sorted[0]["open"],  # First M1's open
                high=max(highs),
                low=min(lows),
                close=m1_sorted[-1]["close"],  # Last M1's close
                volume=sum(volumes),
                source_m1_count=actual_m1,
                expected_m1_count=expected_m1,
                has_gaps=has_gaps,
                gap_count=gap_count,
                confidence=propagated_confidence.value,
                confidence_distribution=candle_conf_dist
            )
            
            aggregated.append(agg_candle)
        
        # Calculate quality metrics
        total_m1 = len(m1_candles)
        expected_total = self._calculate_expected_m1_count(start_date, end_date)
        coverage = total_m1 / expected_total if expected_total > 0 else 0
        
        # Quality score based on coverage and confidence
        low_ratio = conf_dist.get("low", 0) / total_m1 if total_m1 > 0 else 0
        quality_score = coverage * (1 - low_ratio * 0.5)  # Penalize low confidence
        
        # Usability flags
        usable_backtest = (
            quality_score >= 0.95 and 
            conf_dist.get("low", 0) == 0 and
            min_confidence == "high"
        )
        usable_research = quality_score >= 0.80
        
        if not usable_backtest and min_confidence == "high":
            warnings.append(
                f"Data quality ({quality_score:.1%}) insufficient for production backtest. "
                f"Gaps: {total_gaps}, Low confidence: {conf_dist.get('low', 0)}"
            )
        
        return AggregatedCandlesResult(
            candles=aggregated,
            timeframe=timeframe,
            symbol=symbol,
            source_m1_count=total_m1,
            expected_m1_count=expected_total,
            gaps_detected=total_gaps,
            gap_minutes=total_gap_minutes,
            confidence_distribution=conf_dist,
            quality_score=quality_score,
            usable_for_backtest=usable_backtest,
            usable_for_research=usable_research,
            warnings=warnings
        )
    
    def _round_to_period(self, dt: datetime, period_minutes: int) -> datetime:
        """
        Round datetime down to period start.
        """
        if period_minutes >= 1440:  # Daily or higher
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        
        minutes_since_midnight = dt.hour * 60 + dt.minute
        period_start_minutes = (minutes_since_midnight // period_minutes) * period_minutes
        
        return dt.replace(
            hour=period_start_minutes // 60,
            minute=period_start_minutes % 60,
            second=0,
            microsecond=0
        )
    
    def _calculate_expected_m1_count(self, start: datetime, end: datetime) -> int:
        """
        Calculate expected M1 candles, excluding weekends.
        Forex market: Sunday 5pm EST to Friday 5pm EST
        """
        total_minutes = int((end - start).total_seconds() / 60)
        
        # Rough estimate: subtract weekends (2 days per week)
        total_days = (end - start).days
        weekend_days = (total_days // 7) * 2
        
        # Adjust for forex market hours
        expected = total_minutes - (weekend_days * 1440)
        return max(0, expected)
    
    def _detect_gaps(
        self,
        candles: List[Dict[str, Any]],
        start: datetime,
        end: datetime,
        interval_minutes: int
    ) -> Tuple[int, int]:
        """
        Detect gaps in candle sequence.
        
        Returns:
            (gap_count, total_gap_minutes)
        """
        if len(candles) < 2:
            return 0, 0
        
        gaps = 0
        gap_minutes = 0
        expected_delta = timedelta(minutes=interval_minutes)
        
        for i in range(1, len(candles)):
            prev_ts = candles[i-1]["timestamp"]
            curr_ts = candles[i]["timestamp"]
            
            if isinstance(prev_ts, str):
                prev_ts = datetime.fromisoformat(prev_ts.replace("Z", "+00:00"))
            if isinstance(curr_ts, str):
                curr_ts = datetime.fromisoformat(curr_ts.replace("Z", "+00:00"))
            
            actual_delta = curr_ts - prev_ts
            
            # Gap if more than 2x expected interval (allow some tolerance)
            if actual_delta > expected_delta * 2:
                # Check if it's a weekend gap (expected)
                if not self._is_weekend_gap(prev_ts, curr_ts):
                    gaps += 1
                    gap_minutes += int(actual_delta.total_seconds() / 60) - interval_minutes
        
        return gaps, gap_minutes
    
    def _is_weekend_gap(self, start: datetime, end: datetime) -> bool:
        """
        Check if gap spans a weekend (expected for forex).
        """
        # Friday to Monday gap is expected
        if start.weekday() == 4 and end.weekday() == 0:  # Friday to Monday
            return True
        if start.weekday() == 4 and end.weekday() == 6:  # Friday to Sunday
            return True
        if start.weekday() == 5:  # Saturday
            return True
        return False
    
    def invalidate_cache(self, symbol: str):
        """
        Invalidate cache for a symbol (after new data upload).
        """
        self.cache.invalidate(f"agg:{symbol}:*")
