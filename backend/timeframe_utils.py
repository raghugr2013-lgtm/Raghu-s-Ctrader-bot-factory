"""
Timeframe Utilities
Handles timeframe conversions and validations across the system.
"""

from typing import Optional
from enum import Enum


class Timeframe(str, Enum):
    """Supported timeframes"""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAILY = "1d"


class TimeframeConverter:
    """
    Converts timeframe formats between different representations.
    Supports: Pipeline format (1m, 5m, 1h) ↔ cTrader format (TimeFrame.Minute, TimeFrame.Hour)
    """
    
    # Mapping from pipeline timeframe to cTrader TimeFrame enum
    CTRADER_MAP = {
        "1m": "TimeFrame.Minute",
        "5m": "TimeFrame.Minute5",
        "15m": "TimeFrame.Minute15",
        "30m": "TimeFrame.Minute30",
        "1h": "TimeFrame.Hour",
        "4h": "TimeFrame.Hour4",
        "1d": "TimeFrame.Daily",
    }
    
    # Reverse mapping for completeness
    PIPELINE_MAP = {v: k for k, v in CTRADER_MAP.items()}
    
    # Human-readable descriptions
    DESCRIPTIONS = {
        "1m": "1 Minute",
        "5m": "5 Minutes",
        "15m": "15 Minutes",
        "30m": "30 Minutes",
        "1h": "1 Hour",
        "4h": "4 Hours",
        "1d": "1 Day (Daily)",
    }
    
    @classmethod
    def validate(cls, timeframe: str) -> bool:
        """
        Check if timeframe is valid.
        
        Args:
            timeframe: Timeframe string (e.g., "1h", "5m")
            
        Returns:
            True if valid, False otherwise
        """
        return timeframe.lower() in cls.CTRADER_MAP
    
    @classmethod
    def to_ctrader(cls, timeframe: str) -> str:
        """
        Convert pipeline timeframe to cTrader TimeFrame enum.
        
        Args:
            timeframe: Pipeline timeframe (e.g., "1h", "5m")
            
        Returns:
            cTrader TimeFrame string (e.g., "TimeFrame.Hour", "TimeFrame.Minute5")
            
        Examples:
            >>> TimeframeConverter.to_ctrader("1h")
            'TimeFrame.Hour'
            >>> TimeframeConverter.to_ctrader("5m")
            'TimeFrame.Minute5'
        """
        tf_lower = timeframe.lower()
        if tf_lower not in cls.CTRADER_MAP:
            raise ValueError(f"Invalid timeframe: {timeframe}. Supported: {list(cls.CTRADER_MAP.keys())}")
        return cls.CTRADER_MAP[tf_lower]
    
    @classmethod
    def to_pipeline(cls, ctrader_timeframe: str) -> str:
        """
        Convert cTrader TimeFrame enum to pipeline format.
        
        Args:
            ctrader_timeframe: cTrader TimeFrame (e.g., "TimeFrame.Hour")
            
        Returns:
            Pipeline timeframe (e.g., "1h")
        """
        if ctrader_timeframe not in cls.PIPELINE_MAP:
            raise ValueError(f"Invalid cTrader timeframe: {ctrader_timeframe}")
        return cls.PIPELINE_MAP[ctrader_timeframe]
    
    @classmethod
    def get_description(cls, timeframe: str) -> str:
        """
        Get human-readable description of timeframe.
        
        Args:
            timeframe: Pipeline timeframe
            
        Returns:
            Human-readable description
        """
        return cls.DESCRIPTIONS.get(timeframe.lower(), timeframe)
    
    @classmethod
    def get_all_supported(cls) -> list:
        """Get list of all supported timeframes"""
        return list(cls.CTRADER_MAP.keys())
    
    @classmethod
    def normalize(cls, timeframe: Optional[str], default: str = "1h") -> str:
        """
        Normalize timeframe, returning default if invalid.
        
        Args:
            timeframe: Input timeframe (can be None or invalid)
            default: Default timeframe to use
            
        Returns:
            Valid normalized timeframe
        """
        if not timeframe:
            return default
        
        tf_lower = timeframe.lower()
        if cls.validate(tf_lower):
            return tf_lower
        else:
            return default
