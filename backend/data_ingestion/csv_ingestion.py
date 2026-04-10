"""
CSV Ingestion Engine - M1 SSOT Compliant

STRICT RULES:
- M1 CSV → ACCEPT with HIGH confidence
- Higher TF CSV (M5, H1, D1) → REJECT by default
- Optional research override (marked LOW, never for backtest)

NO INTERPOLATION - Higher TF data cannot be converted to M1.
"""

import logging
import uuid
import pandas as pd
from io import StringIO, BytesIO
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from collections import Counter

from .confidence_system import ConfidenceLevel, DataSource, ConfidenceRules
from .candle_models import M1Candle, CandleMetadata, IngestionResult
from .data_validation_layer import (
    DataValidator, 
    ConfidenceScorer, 
    MetadataTagger, 
    ValidationResult,
    TimeframeDetector
)

logger = logging.getLogger(__name__)


class CSVTimeframeDetector:
    """
    Auto-detect timeframe from CSV data.
    Used to REJECT non-M1 data.
    """
    
    # Timeframe to seconds mapping with tolerance
    TF_DEFINITIONS = {
        "M1": (60, 10),       # 60s ± 10s
        "M5": (300, 30),      # 5min ± 30s
        "M15": (900, 60),     # 15min ± 60s
        "M30": (1800, 120),   # 30min ± 120s
        "H1": (3600, 300),    # 1h ± 5min
        "H4": (14400, 600),   # 4h ± 10min
        "D1": (86400, 3600),  # 1d ± 1h
    }
    
    def detect(self, df: pd.DataFrame) -> Tuple[str, float, List[str]]:
        """
        Detect timeframe from CSV data.
        
        Args:
            df: DataFrame with timestamp column
        
        Returns:
            (detected_timeframe, confidence, warnings)
        """
        warnings = []
        
        if len(df) < 2:
            return "M1", 0.5, ["Insufficient data for timeframe detection"]
        
        # Find timestamp column
        ts_col = None
        for col in ["timestamp", "time", "datetime", "date", "Date", "Time", "Timestamp"]:
            if col in df.columns:
                ts_col = col
                break
        
        if ts_col is None:
            # Try first column
            ts_col = df.columns[0]
            warnings.append(f"Using first column '{ts_col}' as timestamp")
        
        # Parse timestamps
        try:
            timestamps = pd.to_datetime(df[ts_col])
        except Exception as e:
            return "UNKNOWN", 0.0, [f"Failed to parse timestamps: {str(e)}"]
        
        # Calculate deltas
        deltas = []
        for i in range(1, min(len(timestamps), 500)):
            delta = (timestamps.iloc[i] - timestamps.iloc[i-1]).total_seconds()
            if delta > 0:  # Ignore zero or negative deltas
                deltas.append(delta)
        
        if not deltas:
            return "UNKNOWN", 0.0, ["No valid time deltas found"]
        
        # Find most common delta
        delta_counts = Counter(int(d) for d in deltas)
        most_common = delta_counts.most_common(1)[0]
        most_common_delta = most_common[0]
        occurrence_ratio = most_common[1] / len(deltas)
        
        # Match to known timeframe
        for tf, (expected, tolerance) in self.TF_DEFINITIONS.items():
            if abs(most_common_delta - expected) <= tolerance:
                confidence = min(0.99, occurrence_ratio)
                return tf, confidence, warnings
        
        # Unknown timeframe
        warnings.append(f"Unknown interval: {most_common_delta} seconds")
        return f"UNKNOWN_{most_common_delta}s", occurrence_ratio, warnings


class CSVParser:
    """
    Parse CSV files into standardized candle format.
    """
    
    # Common column name mappings
    COLUMN_MAPPINGS = {
        "timestamp": ["timestamp", "time", "datetime", "date", "Date", "Time", "Gmt time", "Local time"],
        "open": ["open", "Open", "o", "OPEN"],
        "high": ["high", "High", "h", "HIGH"],
        "low": ["low", "Low", "l", "LOW"],
        "close": ["close", "Close", "c", "CLOSE"],
        "volume": ["volume", "Volume", "vol", "Vol", "v", "VOLUME"]
    }
    
    def parse(self, content: bytes, symbol: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Parse CSV content to candle dictionaries.
        
        Returns:
            (candles, warnings)
        """
        warnings = []
        
        try:
            # Try different encodings
            for encoding in ["utf-8", "latin1", "cp1252"]:
                try:
                    text = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                return [], ["Failed to decode CSV with any known encoding"]
            
            # Parse CSV
            df = pd.read_csv(StringIO(text))
            
            if df.empty:
                return [], ["CSV file is empty"]
            
            # Map columns
            column_map = {}
            for target, candidates in self.COLUMN_MAPPINGS.items():
                for candidate in candidates:
                    if candidate in df.columns:
                        column_map[target] = candidate
                        break
                
                if target not in column_map and target != "volume":
                    return [], [f"Missing required column: {target}"]
            
            # Convert to candles
            candles = []
            for _, row in df.iterrows():
                try:
                    # Parse timestamp
                    ts = row[column_map["timestamp"]]
                    if isinstance(ts, str):
                        # Try various formats
                        for fmt in [
                            "%Y-%m-%d %H:%M:%S",
                            "%Y.%m.%d %H:%M:%S",
                            "%d.%m.%Y %H:%M:%S",
                            "%Y-%m-%dT%H:%M:%S",
                            "%Y/%m/%d %H:%M",
                        ]:
                            try:
                                ts = datetime.strptime(ts, fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            ts = pd.to_datetime(ts)
                    elif isinstance(ts, pd.Timestamp):
                        ts = ts.to_pydatetime()
                    
                    # Ensure UTC
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    
                    candle = {
                        "symbol": symbol.upper(),
                        "timestamp": ts,
                        "open": float(row[column_map["open"]]),
                        "high": float(row[column_map["high"]]),
                        "low": float(row[column_map["low"]]),
                        "close": float(row[column_map["close"]]),
                        "volume": float(row.get(column_map.get("volume", "volume"), 0)) if "volume" in column_map else 0
                    }
                    candles.append(candle)
                    
                except Exception as e:
                    warnings.append(f"Skipped row: {str(e)}")
            
            return candles, warnings
            
        except Exception as e:
            return [], [f"CSV parsing error: {str(e)}"]


class CSVIngestionEngine:
    """
    Process CSV uploads with STRICT M1 enforcement.
    
    POLICY:
    - M1 CSV → ACCEPT with HIGH confidence
    - Higher TF CSV → REJECT (default)
    - research_override=True → Store higher TF as separate data (NOT as M1)
    
    NO INTERPOLATION - we do NOT convert H1 to M1.
    """
    
    def __init__(self):
        self.detector = CSVTimeframeDetector()
        self.parser = CSVParser()
        self.validator = DataValidator()
        self.scorer = ConfidenceScorer()
        self.tagger = MetadataTagger()
    
    async def ingest(
        self,
        file_content: bytes,
        symbol: str,
        declared_timeframe: Optional[str] = None,
        research_override: bool = False,  # Allow higher TF for research ONLY
        upload_batch_id: Optional[str] = None
    ) -> IngestionResult:
        """
        Process CSV upload.
        
        STRICT RULES:
        - Detects timeframe automatically
        - REJECTS non-M1 data by default
        - research_override allows storing but marks as LOW confidence
        
        Args:
            file_content: Raw CSV bytes
            symbol: Trading symbol
            declared_timeframe: User-declared TF (optional)
            research_override: Allow non-M1 for research (NEVER for backtest)
            upload_batch_id: Batch tracking ID
        
        Returns:
            IngestionResult
        """
        batch_id = upload_batch_id or str(uuid.uuid4())
        
        result = IngestionResult(
            success=False,
            upload_batch_id=batch_id,
            symbol=symbol.upper()
        )
        
        try:
            # Step 1: Parse CSV
            candles, parse_warnings = self.parser.parse(file_content, symbol)
            result.warnings.extend(parse_warnings)
            
            if not candles:
                result.errors.append("No valid candles parsed from CSV")
                return result
            
            # Step 2: Detect timeframe
            df = pd.DataFrame(candles)
            detected_tf, tf_confidence, tf_warnings = self.detector.detect(df)
            result.warnings.extend(tf_warnings)
            result.detected_timeframe = detected_tf
            
            logger.info(f"CSV timeframe detection: {detected_tf} (confidence: {tf_confidence:.2%})")
            
            # Step 3: Check if M1
            is_m1 = detected_tf == "M1"
            
            # If user declared different TF, use that with warning
            if declared_timeframe and declared_timeframe != detected_tf:
                if declared_timeframe == "M1" and detected_tf != "M1":
                    # User says M1 but we detected higher TF - REJECT
                    result.errors.append(
                        f"REJECTED: Declared as M1 but detected as {detected_tf}. "
                        f"Please upload actual M1 data or BI5 tick files."
                    )
                    result.rejected_reason = f"Timeframe mismatch: declared M1, detected {detected_tf}"
                    return result
                elif declared_timeframe != "M1" and detected_tf == "M1":
                    # User says higher TF but we got M1 - ACCEPT (better than expected)
                    result.warnings.append(
                        f"Detected M1 data (better than declared {declared_timeframe}). Accepting as M1."
                    )
                    is_m1 = True
            
            # Step 4: Handle non-M1 data
            if not is_m1:
                if research_override:
                    # Allow but mark as LOW confidence and warn
                    result.warnings.append(
                        f"\u26a0\ufe0f RESEARCH ONLY: {detected_tf} data stored with LOW confidence. "
                        f"This data CANNOT be used for production backtesting. "
                        f"Upload M1 data or BI5 tick files for reliable results."
                    )
                    result.confidence_assigned = ConfidenceLevel.LOW.value
                    result.source = f"csv_{detected_tf.lower()}_research"
                else:
                    # REJECT - Default behavior
                    result.errors.append(
                        f"REJECTED: CSV contains {detected_tf} data, not M1. "
                        f"The M1 SSOT architecture requires minute-level data. "
                        f"Please upload: (1) M1 CSV data, or (2) BI5 tick files from Dukascopy. "
                        f"Higher timeframe data cannot be converted to M1 without losing accuracy."
                    )
                    result.rejected_reason = f"Higher timeframe data: {detected_tf}"
                    result.candles_rejected = len(candles)
                    return result
            else:
                result.source = DataSource.CSV_M1.value
                result.confidence_assigned = ConfidenceLevel.HIGH.value
            
            # Step 5: Validate candles
            validation = ValidationResult()
            valid_candles = []
            
            for candle in candles:
                candle_val = self.validator.validate_ohlcv(candle)
                if candle_val.is_valid:
                    valid_candles.append(candle)
                else:
                    result.candles_rejected += 1
                validation.merge(candle_val)
            
            if not valid_candles:
                result.errors.append("All candles failed validation")
                return result
            
            # Validate sequence
            seq_val = self.validator.validate_sequence(valid_candles)
            validation.merge(seq_val)
            
            # Step 6: Score confidence
            source = result.source or DataSource.CSV_M1.value
            confidence, val_score = self.scorer.score(source, validation)
            
            # Override confidence if research override used
            if not is_m1 and research_override:
                confidence = ConfidenceLevel.LOW
            
            # Step 7: Tag with metadata
            result.candles = self.tagger.tag(
                candles=valid_candles,
                source=source,
                confidence=confidence,
                upload_batch_id=batch_id,
                validation_score=val_score,
                additional_tags={
                    "detected_timeframe": detected_tf,
                    "declared_timeframe": declared_timeframe,
                    "tf_detection_confidence": tf_confidence
                }
            )
            
            # Step 8: Update result
            result.success = True
            result.candles_processed = len(candles)
            result.candles_stored = len(result.candles)
            result.confidence_assigned = confidence.value
            result.validation_score = val_score
            result.warnings.extend(validation.warnings)
            
            if valid_candles:
                result.start_timestamp = valid_candles[0]["timestamp"]
                result.end_timestamp = valid_candles[-1]["timestamp"]
            
            logger.info(
                f"CSV ingestion complete: {symbol} {detected_tf} - "
                f"{result.candles_stored} candles stored, "
                f"{result.candles_rejected} rejected, "
                f"confidence: {confidence.value}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"CSV ingestion error: {str(e)}", exc_info=True)
            result.errors.append(f"Ingestion error: {str(e)}")
            return result
