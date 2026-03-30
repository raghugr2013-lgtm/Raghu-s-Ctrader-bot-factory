"""
Local Dukascopy Data Provider
Loads historical tick data from local JSON files and converts to OHLC candles.
NO external API calls - uses only local data.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

# Data directory paths
DATA_ROOT = "/app/trading_strategy/data/dukascopy"
BACKUP_DATA_ROOT = "/app/data/dukascopy"


class LocalDataProvider:
    """
    Local market data provider using Dukascopy tick data stored in JSON files.
    Converts tick data to OHLC candles for backtesting.
    """
    
    SUPPORTED_SYMBOLS = ["EURUSD", "XAUUSD", "GBPUSD", "USDJPY"]
    
    def __init__(self, data_root: str = None):
        """Initialize with data directory path"""
        self.data_root = data_root or DATA_ROOT
        if not os.path.exists(self.data_root):
            self.data_root = BACKUP_DATA_ROOT
        
        self._cache = {}  # Cache loaded data
        logger.info(f"LocalDataProvider initialized with data root: {self.data_root}")
    
    def get_available_data(self) -> Dict[str, List[str]]:
        """Get list of available symbols and date ranges"""
        available = {}
        
        if not os.path.exists(self.data_root):
            logger.warning(f"Data root does not exist: {self.data_root}")
            return available
        
        for symbol in os.listdir(self.data_root):
            symbol_path = os.path.join(self.data_root, symbol)
            if os.path.isdir(symbol_path):
                dates = self._get_available_dates(symbol_path)
                if dates:
                    available[symbol] = dates
        
        return available
    
    def _get_available_dates(self, symbol_path: str) -> List[str]:
        """Get list of available dates for a symbol"""
        dates = []
        
        for year in os.listdir(symbol_path):
            year_path = os.path.join(symbol_path, year)
            if not os.path.isdir(year_path):
                continue
            
            for month in os.listdir(year_path):
                month_path = os.path.join(year_path, month)
                if not os.path.isdir(month_path):
                    continue
                
                for day in os.listdir(month_path):
                    day_path = os.path.join(month_path, day)
                    if os.path.isdir(day_path):
                        dates.append(f"{year}-{month}-{day}")
        
        return sorted(dates)
    
    def load_tick_data(
        self, 
        symbol: str, 
        start_date: datetime = None, 
        end_date: datetime = None
    ) -> pd.DataFrame:
        """
        Load tick data from local JSON files.
        
        Returns DataFrame with columns: timestamp, ask, bid, ask_volume, bid_volume
        """
        symbol = symbol.upper()
        symbol_path = os.path.join(self.data_root, symbol)
        
        if not os.path.exists(symbol_path):
            logger.warning(f"No data found for symbol: {symbol}")
            return pd.DataFrame()
        
        all_ticks = []
        
        # Walk through directory structure
        for year in sorted(os.listdir(symbol_path)):
            year_path = os.path.join(symbol_path, year)
            if not os.path.isdir(year_path):
                continue
            
            for month in sorted(os.listdir(year_path)):
                month_path = os.path.join(year_path, month)
                if not os.path.isdir(month_path):
                    continue
                
                for day in sorted(os.listdir(month_path)):
                    day_path = os.path.join(month_path, day)
                    if not os.path.isdir(day_path):
                        continue
                    
                    # Check date filter
                    date_str = f"{year}-{month}-{day}"
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    if start_date and file_date < start_date.replace(hour=0, minute=0, second=0, microsecond=0):
                        continue
                    if end_date and file_date > end_date.replace(hour=23, minute=59, second=59):
                        continue
                    
                    # Load all hour files
                    for hour_file in sorted(os.listdir(day_path)):
                        if hour_file.endswith('.json'):
                            file_path = os.path.join(day_path, hour_file)
                            ticks = self._load_json_file(file_path)
                            all_ticks.extend(ticks)
        
        if not all_ticks:
            logger.warning(f"No tick data found for {symbol}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(all_ticks)
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Apply time filter if specified
        if start_date:
            df = df[df['timestamp'] >= start_date]
        if end_date:
            df = df[df['timestamp'] <= end_date]
        
        logger.info(f"Loaded {len(df)} ticks for {symbol}")
        return df
    
    def _load_json_file(self, file_path: str) -> List[dict]:
        """Load tick data from a single JSON file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return []
    
    def ticks_to_ohlc(
        self, 
        tick_df: pd.DataFrame, 
        timeframe: str = "H1"
    ) -> pd.DataFrame:
        """
        Convert tick data to OHLC candles.
        
        Args:
            tick_df: DataFrame with tick data
            timeframe: Candle timeframe (M1, M5, M15, M30, H1, H4, D1)
        
        Returns:
            DataFrame with OHLC candles
        """
        if tick_df.empty:
            return pd.DataFrame()
        
        # Map timeframe to pandas frequency
        tf_map = {
            "M1": "1min",
            "M5": "5min",
            "M15": "15min",
            "M30": "30min",
            "H1": "1h",
            "H4": "4h",
            "D1": "1D",
            "W1": "1W"
        }
        
        freq = tf_map.get(timeframe, "1h")
        
        # Calculate mid price for OHLC
        tick_df = tick_df.copy()
        tick_df['mid'] = (tick_df['ask'] + tick_df['bid']) / 2
        tick_df.set_index('timestamp', inplace=True)
        
        # Resample to OHLC
        ohlc = tick_df['mid'].resample(freq).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        })
        
        # Calculate volume from tick count
        volume = tick_df['mid'].resample(freq).count()
        ohlc['volume'] = volume
        
        # Drop rows with no data
        ohlc = ohlc.dropna()
        ohlc = ohlc.reset_index()
        ohlc.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
        
        logger.info(f"Converted to {len(ohlc)} {timeframe} candles")
        return ohlc
    
    def get_ohlc_data(
        self,
        symbol: str,
        timeframe: str = "H1",
        start_date: datetime = None,
        end_date: datetime = None
    ) -> pd.DataFrame:
        """
        Get OHLC candle data for a symbol.
        This is the main method to use for backtesting.
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD", "XAUUSD")
            timeframe: Candle timeframe (M1, M5, M15, M30, H1, H4, D1)
            start_date: Start date for data
            end_date: End date for data
        
        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        # Load tick data
        tick_df = self.load_tick_data(symbol, start_date, end_date)
        
        if tick_df.empty:
            logger.warning(f"No data available for {symbol}")
            return pd.DataFrame()
        
        # Convert to OHLC
        ohlc_df = self.ticks_to_ohlc(tick_df, timeframe)
        
        return ohlc_df
    
    def validate_symbol(self, symbol: str) -> bool:
        """Check if symbol data is available locally"""
        symbol = symbol.upper()
        symbol_path = os.path.join(self.data_root, symbol)
        return os.path.exists(symbol_path)
    
    def get_data_summary(self) -> Dict:
        """Get summary of available local data"""
        available = self.get_available_data()
        
        summary = {
            "data_root": self.data_root,
            "exists": os.path.exists(self.data_root),
            "symbols": list(available.keys()),
            "symbol_details": {}
        }
        
        for symbol, dates in available.items():
            if dates:
                summary["symbol_details"][symbol] = {
                    "first_date": dates[0],
                    "last_date": dates[-1],
                    "total_days": len(dates)
                }
        
        return summary


# Singleton instance
_local_provider = None

def get_local_provider() -> LocalDataProvider:
    """Get singleton LocalDataProvider instance"""
    global _local_provider
    if _local_provider is None:
        _local_provider = LocalDataProvider()
    return _local_provider


# Export for easy import
__all__ = ['LocalDataProvider', 'get_local_provider']
