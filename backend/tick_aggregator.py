"""
Tick Data Aggregator
Converts tick data to OHLC candles with configurable timeframes
"""

from typing import List, Dict
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)


class TickAggregator:
    """Aggregate tick data into OHLC candles"""
    
    # Timeframe to minutes mapping
    TIMEFRAME_MINUTES = {
        'M1': 1,
        'M5': 5,
        'M15': 15,
        'M30': 30,
        'H1': 60,
        'H4': 240,
        'D1': 1440
    }
    
    @staticmethod
    def aggregate_ticks_to_candles(
        ticks: List[Dict],
        base_timestamp: datetime,
        timeframe: str
    ) -> List[Dict]:
        """
        Aggregate ticks into OHLC candles
        
        Args:
            ticks: List of tick dictionaries with timestamp_ms, mid price
            base_timestamp: Base datetime for the hour (ticks have ms offset from this)
            timeframe: Timeframe string (M1, M5, M15, H1, etc.)
        
        Returns:
            List of OHLC candles
        """
        if not ticks:
            return []
        
        if timeframe not in TickAggregator.TIMEFRAME_MINUTES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        
        candle_minutes = TickAggregator.TIMEFRAME_MINUTES[timeframe]
        candle_seconds = candle_minutes * 60
        
        # Group ticks by candle period
        candle_groups = {}
        
        for tick in ticks:
            # Calculate absolute timestamp
            tick_time = base_timestamp + timedelta(milliseconds=tick['timestamp_ms'])
            
            # Round down to candle start time
            candle_start = TickAggregator._round_to_candle(tick_time, candle_minutes)
            
            if candle_start not in candle_groups:
                candle_groups[candle_start] = []
            
            candle_groups[candle_start].append(tick)
        
        # Build OHLC candles
        candles = []
        for candle_start in sorted(candle_groups.keys()):
            candle_ticks = candle_groups[candle_start]
            
            if not candle_ticks:
                continue
            
            # Get OHLC from ticks
            prices = [t['mid'] for t in candle_ticks]
            volumes = [t.get('ask_volume', 0) + t.get('bid_volume', 0) for t in candle_ticks]
            
            candle = {
                'timestamp': candle_start,
                'open': prices[0],
                'high': max(prices),
                'low': min(prices),
                'close': prices[-1],
                'volume': sum(volumes),
                'tick_count': len(candle_ticks),
                'is_filled': False  # Original data, not filled
            }
            
            candles.append(candle)
        
        return candles
    
    @staticmethod
    def _round_to_candle(dt: datetime, candle_minutes: int) -> datetime:
        """Round datetime down to candle start time"""
        # Get total minutes since midnight
        minutes_since_midnight = dt.hour * 60 + dt.minute
        
        # Round down to nearest candle boundary
        candle_boundary = (minutes_since_midnight // candle_minutes) * candle_minutes
        
        # Create new datetime at candle start
        candle_hour = candle_boundary // 60
        candle_minute = candle_boundary % 60
        
        return dt.replace(
            hour=candle_hour,
            minute=candle_minute,
            second=0,
            microsecond=0
        )
    
    @staticmethod
    def fill_missing_candles(
        candles: List[Dict],
        timeframe: str,
        max_fill_gap: int = 3
    ) -> List[Dict]:
        """
        Fill missing candles with intelligent gap handling
        
        Rules:
        - Small gaps (≤ max_fill_gap): Fill with previous close
        - Large gaps (> max_fill_gap): Leave empty, flag as data issue
        
        Args:
            candles: List of existing candles
            timeframe: Timeframe string
            max_fill_gap: Maximum number of candles to fill
        
        Returns:
            List of candles with small gaps filled
        """
        if not candles or len(candles) < 2:
            return candles
        
        candle_minutes = TickAggregator.TIMEFRAME_MINUTES[timeframe]
        candle_delta = timedelta(minutes=candle_minutes)
        
        filled_candles = []
        
        for i in range(len(candles)):
            current_candle = candles[i]
            filled_candles.append(current_candle)
            
            # Check if there's a next candle
            if i < len(candles) - 1:
                next_candle = candles[i + 1]
                current_time = current_candle['timestamp']
                next_time = next_candle['timestamp']
                
                # Calculate expected next time
                expected_next = current_time + candle_delta
                
                # If there's a gap
                if next_time > expected_next:
                    # Calculate gap size in candles
                    time_diff = next_time - expected_next
                    gap_candles = int(time_diff.total_seconds() / (candle_minutes * 60))
                    
                    # Only fill small gaps
                    if gap_candles <= max_fill_gap:
                        # Fill with previous close
                        prev_close = current_candle['close']
                        
                        fill_time = expected_next
                        for _ in range(gap_candles):
                            filled_candle = {
                                'timestamp': fill_time,
                                'open': prev_close,
                                'high': prev_close,
                                'low': prev_close,
                                'close': prev_close,
                                'volume': 0,
                                'tick_count': 0,
                                'is_filled': True  # Mark as filled
                            }
                            filled_candles.append(filled_candle)
                            fill_time += candle_delta
                    else:
                        # Large gap - log warning but don't fill
                        logger.warning(
                            f"Large data gap detected: {gap_candles} candles "
                            f"from {current_time} to {next_time}"
                        )
        
        return filled_candles
