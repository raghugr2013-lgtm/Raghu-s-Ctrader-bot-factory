"""
Confidence System - Data Quality Classification

Strict Rules:
- HIGH: Usable everywhere (production backtest, live trading)
- MEDIUM: Research only (exploration, testing)
- LOW: NEVER used in backtest (rejected data marked for reference)

NO INTERPOLATION - Higher TF data is REJECTED, not converted.
"""

from enum import Enum
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ConfidenceLevel(str, Enum):
    """Data confidence levels - determines where data can be used"""
    HIGH = "high"      # Tick-derived M1, verified CSV M1 - usable everywhere
    MEDIUM = "medium"  # API-sourced with minor issues - research only
    LOW = "low"        # Flagged data - NEVER used in backtest
    
    @classmethod
    def from_string(cls, value: str) -> "ConfidenceLevel":
        """Parse confidence level from string"""
        mapping = {
            "high": cls.HIGH,
            "medium": cls.MEDIUM,
            "low": cls.LOW
        }
        return mapping.get(value.lower(), cls.LOW)
    
    def __ge__(self, other: "ConfidenceLevel") -> bool:
        order = {self.HIGH: 3, self.MEDIUM: 2, self.LOW: 1}
        return order[self] >= order[other]
    
    def __gt__(self, other: "ConfidenceLevel") -> bool:
        order = {self.HIGH: 3, self.MEDIUM: 2, self.LOW: 1}
        return order[self] > order[other]
    
    def __le__(self, other: "ConfidenceLevel") -> bool:
        order = {self.HIGH: 3, self.MEDIUM: 2, self.LOW: 1}
        return order[self] <= order[other]
    
    def __lt__(self, other: "ConfidenceLevel") -> bool:
        order = {self.HIGH: 3, self.MEDIUM: 2, self.LOW: 1}
        return order[self] < order[other]


class DataSource(str, Enum):
    """Data source types"""
    BI5 = "bi5"              # Dukascopy tick data file
    CSV_M1 = "csv_m1"        # Verified M1 CSV upload
    DUKASCOPY = "dukascopy"  # Direct Dukascopy API download
    GAP_FILL = "gap_fill"    # Gap filled with real Dukascopy data
    # Note: NO csv_derived or interpolated sources - they are REJECTED


class ConfidenceRules:
    """
    Rules for confidence assignment and propagation.
    
    CRITICAL: No interpolation or synthetic data allowed.
    Higher TF CSV uploads are REJECTED, not converted.
    """
    
    # Source-based initial confidence (only valid sources)
    SOURCE_CONFIDENCE: Dict[str, ConfidenceLevel] = {
        DataSource.BI5.value: ConfidenceLevel.HIGH,
        DataSource.CSV_M1.value: ConfidenceLevel.HIGH,
        DataSource.DUKASCOPY.value: ConfidenceLevel.HIGH,
        DataSource.GAP_FILL.value: ConfidenceLevel.HIGH,  # Only real data used for gap fill
    }
    
    # Use case requirements
    USE_CASE_MINIMUM: Dict[str, ConfidenceLevel] = {
        "production_backtest": ConfidenceLevel.HIGH,
        "walkforward_validation": ConfidenceLevel.HIGH,
        "monte_carlo": ConfidenceLevel.HIGH,
        "live_trading": ConfidenceLevel.HIGH,
        "research_backtest": ConfidenceLevel.MEDIUM,
        "exploration": ConfidenceLevel.LOW,
    }
    
    @classmethod
    def get_confidence_for_source(cls, source: str) -> ConfidenceLevel:
        """
        Get confidence level for a data source.
        Unknown sources default to LOW.
        """
        return cls.SOURCE_CONFIDENCE.get(source, ConfidenceLevel.LOW)
    
    @classmethod
    def propagate_aggregation(cls, confidences: List[ConfidenceLevel]) -> ConfidenceLevel:
        """
        When aggregating M1 → higher TF, use MINIMUM confidence.
        
        Conservative approach:
        - 59 HIGH + 1 MEDIUM = MEDIUM
        - 59 HIGH + 1 LOW = LOW
        - All HIGH = HIGH
        
        This ensures consumers know the weakest link in aggregated data.
        """
        if not confidences:
            return ConfidenceLevel.LOW
        
        if ConfidenceLevel.LOW in confidences:
            return ConfidenceLevel.LOW
        if ConfidenceLevel.MEDIUM in confidences:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.HIGH
    
    @classmethod
    def apply_validation_penalty(
        cls,
        base_confidence: ConfidenceLevel,
        issues: List[str]
    ) -> ConfidenceLevel:
        """
        Downgrade confidence based on validation issues.
        
        Critical issues that downgrade:
        - Price discontinuity > 5% → downgrade one level
        - Missing volume data → downgrade to MEDIUM max
        - Timezone uncertainty → downgrade one level
        - OHLC violations → downgrade to LOW
        """
        if not issues:
            return base_confidence
        
        current = base_confidence
        
        for issue in issues:
            issue_lower = issue.lower()
            
            # Critical issues → LOW immediately
            if any(x in issue_lower for x in ["ohlc_violation", "invalid_price", "negative_volume"]):
                return ConfidenceLevel.LOW
            
            # Moderate issues → downgrade one level
            if any(x in issue_lower for x in ["price_jump", "timezone", "missing_volume"]):
                if current == ConfidenceLevel.HIGH:
                    current = ConfidenceLevel.MEDIUM
                elif current == ConfidenceLevel.MEDIUM:
                    current = ConfidenceLevel.LOW
        
        return current
    
    @classmethod
    def get_minimum_for_use_case(cls, use_case: str) -> ConfidenceLevel:
        """
        Get minimum confidence required for a specific use case.
        
        Production use cases require HIGH confidence.
        Research can use MEDIUM.
        Exploration can use anything.
        """
        return cls.USE_CASE_MINIMUM.get(use_case, ConfidenceLevel.HIGH)
    
    @classmethod
    def can_use_for_backtest(cls, confidence: ConfidenceLevel) -> bool:
        """
        Check if data with given confidence can be used for production backtest.
        
        STRICT RULE: Only HIGH confidence data allowed.
        """
        return confidence == ConfidenceLevel.HIGH
    
    @classmethod
    def can_use_for_research(cls, confidence: ConfidenceLevel) -> bool:
        """
        Check if data can be used for research/exploration.
        
        MEDIUM or higher allowed for research.
        """
        return confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]
