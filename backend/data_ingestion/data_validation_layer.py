"""
Data Validation Layer - Quality Control for All Ingestion

Strict validation with NO synthetic data generation.
Invalid data is REJECTED, not fixed.
"""

import logging
import math
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta, timezone

from .confidence_system import ConfidenceLevel, ConfidenceRules, DataSource
from .candle_models import M1Candle, CandleMetadata

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of a validation check"""
    
    def __init__(self):
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.score = 1.0
    
    def add_error(self, message: str):
        self.errors.append(message)
        self.is_valid = False
        self.score = 0.0
    
    def add_warning(self, message: str):
        self.warnings.append(message)
        self.score = max(0.0, self.score - 0.1)
    
    def merge(self, other: "ValidationResult"):
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.is_valid:
            self.is_valid = False
        self.score = min(self.score, other.score)


class DataValidator:
    """
    Validate incoming data for quality and consistency.
    STRICT MODE: Invalid data is rejected, not fixed.
    """
    
    # Validation thresholds
    MAX_PRICE_JUMP_PERCENT = 5.0  # Max allowed price jump between candles
    MIN_PRICE = 0.00001  # Minimum valid price (for forex)
    MAX_PRICE = 1000000  # Maximum valid price
    
    def validate_ohlcv(self, candle: Dict[str, Any]) -> ValidationResult:
        """
        Validate single candle OHLCV data.
        
        Rules (STRICT - failure = rejection):
        - High >= Open, Close, Low
        - Low <= Open, Close, High
        - All prices > 0
        - No NaN/Inf values
        - Volume >= 0
        """
        result = ValidationResult()
        
        try:
            o = float(candle.get("open", 0))
            h = float(candle.get("high", 0))
            l = float(candle.get("low", 0))
            c = float(candle.get("close", 0))
            v = float(candle.get("volume", 0))
            
            # Check for NaN/Inf
            for name, val in [("open", o), ("high", h), ("low", l), ("close", c), ("volume", v)]:
                if math.isnan(val) or math.isinf(val):
                    result.add_error(f"invalid_{name}_nan_inf")
            
            # Check price validity
            for name, val in [("open", o), ("high", h), ("low", l), ("close", c)]:
                if val <= 0:
                    result.add_error(f"invalid_{name}_not_positive")
                if val < self.MIN_PRICE:
                    result.add_error(f"{name}_below_minimum")
                if val > self.MAX_PRICE:
                    result.add_error(f"{name}_above_maximum")
            
            # Check OHLC relationships
            if result.is_valid:  # Only check if basic validation passed
                if h < o or h < c or h < l:
                    result.add_error("ohlc_violation_high_not_highest")
                if l > o or l > c or l > h:
                    result.add_error("ohlc_violation_low_not_lowest")
            
            # Check volume
            if v < 0:
                result.add_error("negative_volume")
            elif v == 0:
                result.add_warning("missing_volume")
        
        except (TypeError, ValueError) as e:
            result.add_error(f"invalid_price_format: {str(e)}")
        
        return result
    
    def validate_sequence(self, candles: List[Dict[str, Any]], expected_interval_minutes: int = 1) -> ValidationResult:
        """
        Validate candle sequence for consistency.
        
        Rules:
        - Timestamps in ascending order
        - No duplicate timestamps
        - Consistent time intervals (M1 = 60 seconds)
        - Price continuity (flag large jumps)
        """
        result = ValidationResult()
        
        if not candles:
            result.add_error("empty_candle_list")
            return result
        
        if len(candles) < 2:
            return result  # Single candle, no sequence validation needed
        
        expected_delta = timedelta(minutes=expected_interval_minutes)
        seen_timestamps = set()
        
        for i in range(len(candles)):
            candle = candles[i]
            ts = candle.get("timestamp")
            
            if ts is None:
                result.add_error(f"missing_timestamp_at_index_{i}")
                continue
            
            # Check for duplicates
            ts_key = ts.isoformat() if isinstance(ts, datetime) else str(ts)
            if ts_key in seen_timestamps:
                result.add_warning(f"duplicate_timestamp_{ts_key}")
            seen_timestamps.add(ts_key)
            
            # Check order and intervals
            if i > 0:
                prev_ts = candles[i - 1].get("timestamp")
                if prev_ts and ts:
                    if isinstance(prev_ts, str):
                        prev_ts = datetime.fromisoformat(prev_ts.replace("Z", "+00:00"))
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    
                    if ts <= prev_ts:
                        result.add_error(f"timestamps_not_ascending_at_index_{i}")
                    
                    # Check interval (allow some tolerance)
                    actual_delta = ts - prev_ts
                    if actual_delta > expected_delta * 2:
                        # Gap detected - this is a warning, not error
                        result.add_warning(f"gap_detected_at_{ts_key}")
                
                # Check price continuity
                prev_close = candles[i - 1].get("close", 0)
                curr_open = candle.get("open", 0)
                
                if prev_close > 0 and curr_open > 0:
                    jump_pct = abs(curr_open - prev_close) / prev_close * 100
                    if jump_pct > self.MAX_PRICE_JUMP_PERCENT:
                        result.add_warning(f"price_jump_{jump_pct:.1f}%_at_{ts_key}")
        
        return result
    
    def validate_timezone(self, candles: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate and detect timezone.
        All data should be in UTC.
        """
        result = ValidationResult()
        
        if not candles:
            return result
        
        # Check if timestamps have timezone info
        for i, candle in enumerate(candles[:10]):  # Check first 10
            ts = candle.get("timestamp")
            if ts is None:
                continue
            
            if isinstance(ts, datetime):
                if ts.tzinfo is None:
                    result.add_warning("timezone_naive_timestamps")
                    break
            elif isinstance(ts, str):
                if "Z" not in ts and "+" not in ts and "-" not in ts[10:]:
                    result.add_warning("timezone_naive_timestamps")
                    break
        
        return result


class ConfidenceScorer:
    """
    Assign confidence scores to data based on source and quality.
    
    STRICT: No interpolation means no LOW confidence from conversion.
    LOW confidence only from validation issues.
    """
    
    def score(
        self,
        source: str,
        validation_result: ValidationResult
    ) -> Tuple[ConfidenceLevel, float]:
        """
        Calculate confidence score.
        
        Returns:
            (ConfidenceLevel, validation_score)
        """
        # Get base confidence from source
        base_confidence = ConfidenceRules.get_confidence_for_source(source)
        
        # Apply validation penalties
        final_confidence = ConfidenceRules.apply_validation_penalty(
            base_confidence,
            validation_result.errors + validation_result.warnings
        )
        
        return final_confidence, validation_result.score


class MetadataTagger:
    """
    Tag candles with complete metadata for traceability.
    """
    
    def tag(
        self,
        candles: List[Dict[str, Any]],
        source: str,
        confidence: ConfidenceLevel,
        upload_batch_id: str,
        validation_score: float = 1.0,
        tick_count: Optional[int] = None,
        additional_tags: Optional[Dict[str, Any]] = None
    ) -> List[M1Candle]:
        """
        Add metadata to each candle and convert to M1Candle objects.
        """
        tagged_candles = []
        
        for candle in candles:
            metadata = CandleMetadata(
                source=source,
                confidence=confidence.value,
                original_timeframe="M1",  # Always M1 for stored data
                upload_batch_id=upload_batch_id,
                ingested_at=datetime.now(timezone.utc),
                validation_score=validation_score,
                tick_count=tick_count,
                tags=additional_tags or {}
            )
            
            # Parse timestamp
            ts = candle.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            
            m1_candle = M1Candle(
                symbol=candle.get("symbol", "").upper(),
                timestamp=ts,
                open=float(candle["open"]),
                high=float(candle["high"]),
                low=float(candle["low"]),
                close=float(candle["close"]),
                volume=float(candle.get("volume", 0)),
                metadata=metadata
            )
            
            tagged_candles.append(m1_candle)
        
        return tagged_candles


class TimeframeDetector:
    """
    Detect timeframe from candle data.
    Used to REJECT non-M1 CSV uploads.
    """
    
    # Timeframe to seconds mapping
    TF_SECONDS = {
        "M1": 60,
        "M5": 300,
        "M15": 900,
        "M30": 1800,
        "H1": 3600,
        "H4": 14400,
        "D1": 86400
    }
    
    def detect(self, candles: List[Dict[str, Any]]) -> Tuple[str, float]:
        """
        Detect timeframe from candle timestamps.
        
        Returns:
            (detected_timeframe, confidence_score)
        """
        if len(candles) < 2:
            return "M1", 0.5  # Assume M1 with low confidence if can't detect
        
        # Calculate time deltas
        deltas = []
        for i in range(1, min(len(candles), 100)):  # Check up to 100 candles
            ts1 = candles[i - 1].get("timestamp")
            ts2 = candles[i].get("timestamp")
            
            if ts1 is None or ts2 is None:
                continue
            
            if isinstance(ts1, str):
                ts1 = datetime.fromisoformat(ts1.replace("Z", "+00:00"))
            if isinstance(ts2, str):
                ts2 = datetime.fromisoformat(ts2.replace("Z", "+00:00"))
            
            delta_seconds = (ts2 - ts1).total_seconds()
            if delta_seconds > 0:
                deltas.append(delta_seconds)
        
        if not deltas:
            return "M1", 0.5
        
        # Find most common delta (mode)
        from collections import Counter
        delta_counts = Counter(int(d) for d in deltas)
        most_common_delta = delta_counts.most_common(1)[0][0]
        confidence = delta_counts.most_common(1)[0][1] / len(deltas)
        
        # Map to timeframe with tolerance
        for tf, expected_seconds in self.TF_SECONDS.items():
            tolerance = expected_seconds * 0.1  # 10% tolerance
            if abs(most_common_delta - expected_seconds) <= tolerance:
                return tf, confidence
        
        # Unknown timeframe
        return f"UNKNOWN_{most_common_delta}s", confidence
