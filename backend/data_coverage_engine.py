"""
Data Coverage Engine
Analyzes available market data and identifies gaps
"""

import os
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class DataCoverageEngine:
    """Analyze market data coverage and identify gaps"""
    
    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)
    
    async def get_full_coverage(self) -> Dict:
        """
        Get complete coverage report for all symbols and timeframes
        
        Returns:
            {
                'symbols': [
                    {
                        'symbol': 'EURUSD',
                        'timeframes': [
                            {
                                'timeframe': 'H1',
                                'status': 'complete|partial|missing',
                                'coverage_percent': 95.5,
                                'date_ranges': [
                                    {'start': '2024-01-01', 'end': '2024-01-31'}
                                ],
                                'missing_ranges': [
                                    {'start': '2024-02-01', 'end': '2024-02-05'}
                                ],
                                'total_candles': 720,
                                'files': ['2024.csv']
                            }
                        ]
                    }
                ]
            }
        """
        coverage = {'symbols': []}
        
        if not self.data_dir.exists():
            logger.warning(f"Data directory {self.data_dir} does not exist")
            return coverage
        
        # Scan directory structure
        symbol_data = defaultdict(dict)
        
        for symbol_dir in self.data_dir.iterdir():
            if not symbol_dir.is_dir():
                continue
            
            symbol = symbol_dir.name
            
            for timeframe_dir in symbol_dir.iterdir():
                if not timeframe_dir.is_dir():
                    continue
                
                timeframe = timeframe_dir.name
                
                # Analyze CSV files in this timeframe directory
                coverage_info = await self._analyze_timeframe_coverage(
                    symbol, timeframe, timeframe_dir
                )
                
                if coverage_info:
                    if symbol not in symbol_data:
                        symbol_data[symbol] = {'symbol': symbol, 'timeframes': []}
                    symbol_data[symbol]['timeframes'].append(coverage_info)
        
        # Convert to list
        coverage['symbols'] = list(symbol_data.values())
        coverage['total_symbols'] = len(symbol_data)
        
        return coverage
    
    async def _analyze_timeframe_coverage(
        self,
        symbol: str,
        timeframe: str,
        directory: Path
    ) -> Dict:
        """Analyze coverage for a specific symbol+timeframe combination"""
        
        csv_files = list(directory.glob("*.csv"))
        
        if not csv_files:
            return None
        
        all_dates = []
        total_candles = 0
        
        # Read all CSV files
        for csv_file in csv_files:
            try:
                with open(csv_file, 'r') as f:
                    lines = f.readlines()
                    
                    # Skip header
                    for line in lines[1:]:
                        if not line.strip():
                            continue
                        
                        parts = line.strip().split(',')
                        if len(parts) < 7:
                            continue
                        
                        timestamp_str = parts[0]
                        try:
                            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            all_dates.append(dt)
                            total_candles += 1
                        except:
                            continue
            
            except Exception as e:
                logger.error(f"Error reading {csv_file}: {str(e)}")
                continue
        
        if not all_dates:
            return None
        
        # Sort dates
        all_dates.sort()
        
        # Get min/max
        min_date = all_dates[0]
        max_date = all_dates[-1]
        
        # Find continuous ranges
        date_ranges = self._find_continuous_ranges(all_dates, timeframe)
        
        # Find missing ranges
        missing_ranges = self._find_missing_ranges(min_date, max_date, all_dates, timeframe)
        
        # Calculate coverage percentage
        total_expected = self._calculate_expected_candles(min_date, max_date, timeframe)
        coverage_percent = (total_candles / total_expected * 100) if total_expected > 0 else 100
        
        # Determine status
        if coverage_percent >= 98:
            status = 'complete'
        elif coverage_percent >= 70:
            status = 'partial'
        else:
            status = 'incomplete'
        
        return {
            'timeframe': timeframe,
            'status': status,
            'coverage_percent': round(coverage_percent, 1),
            'date_ranges': [
                {
                    'start': r[0].date().isoformat(),
                    'end': r[1].date().isoformat()
                }
                for r in date_ranges
            ],
            'missing_ranges': [
                {
                    'start': r[0].date().isoformat(),
                    'end': r[1].date().isoformat(),
                    'candles_missing': r[2]
                }
                for r in missing_ranges
            ],
            'total_candles': total_candles,
            'expected_candles': total_expected,
            'files': [f.name for f in csv_files]
        }
    
    def _find_continuous_ranges(self, dates: List[datetime], timeframe: str) -> List[tuple]:
        """Find continuous date ranges (no gaps > 3 candles)"""
        if not dates:
            return []
        
        # Get candle duration
        candle_minutes = self._timeframe_to_minutes(timeframe)
        max_gap = timedelta(minutes=candle_minutes * 4)  # Allow gap of 3 candles
        
        ranges = []
        range_start = dates[0]
        prev_date = dates[0]
        
        for date in dates[1:]:
            gap = date - prev_date
            
            if gap > max_gap:
                # End current range
                ranges.append((range_start, prev_date))
                range_start = date
            
            prev_date = date
        
        # Add final range
        ranges.append((range_start, prev_date))
        
        return ranges
    
    def _find_missing_ranges(
        self,
        min_date: datetime,
        max_date: datetime,
        existing_dates: List[datetime],
        timeframe: str
    ) -> List[tuple]:
        """Find missing date ranges"""
        
        candle_minutes = self._timeframe_to_minutes(timeframe)
        candle_delta = timedelta(minutes=candle_minutes)
        
        # Convert existing dates to set for fast lookup
        existing_set = set(existing_dates)
        
        missing_ranges = []
        current_missing_start = None
        current_missing_count = 0
        
        # Iterate through expected timeline
        current = min_date
        while current <= max_date:
            if current not in existing_set:
                if current_missing_start is None:
                    current_missing_start = current
                current_missing_count += 1
            else:
                # End of missing range
                if current_missing_start and current_missing_count > 3:
                    missing_ranges.append((
                        current_missing_start,
                        current - candle_delta,
                        current_missing_count
                    ))
                current_missing_start = None
                current_missing_count = 0
            
            current += candle_delta
        
        # Handle final missing range
        if current_missing_start and current_missing_count > 3:
            missing_ranges.append((
                current_missing_start,
                max_date,
                current_missing_count
            ))
        
        return missing_ranges
    
    def _calculate_expected_candles(
        self,
        start: datetime,
        end: datetime,
        timeframe: str
    ) -> int:
        """Calculate expected number of candles in date range"""
        candle_minutes = self._timeframe_to_minutes(timeframe)
        total_minutes = (end - start).total_seconds() / 60
        return int(total_minutes / candle_minutes) + 1
    
    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes"""
        mapping = {
            'M1': 1, '1m': 1,
            'M5': 5, '5m': 5,
            'M15': 15, '15m': 15,
            'M30': 30, '30m': 30,
            'H1': 60, '1h': 60,
            'H4': 240, '4h': 240,
            'D1': 1440, '1d': 1440
        }
        return mapping.get(timeframe, 60)
    
    async def get_missing_data_for_download(
        self,
        symbol: str,
        timeframe: str
    ) -> List[Dict]:
        """
        Get list of missing date ranges for a symbol+timeframe
        Ready to be used for retry downloads
        """
        coverage = await self.get_full_coverage()
        
        for symbol_data in coverage['symbols']:
            if symbol_data['symbol'] != symbol:
                continue
            
            for tf_data in symbol_data['timeframes']:
                if tf_data['timeframe'] != timeframe:
                    continue
                
                return tf_data.get('missing_ranges', [])
        
        return []
