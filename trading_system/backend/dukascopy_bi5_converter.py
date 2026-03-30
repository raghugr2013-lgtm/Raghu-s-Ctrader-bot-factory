#!/usr/bin/env python3
"""
Dukascopy .bi5 to OHLC CSV Converter
Converts binary tick data (.bi5 files) to clean OHLC candles for backtesting

Usage:
    python dukascopy_bi5_converter.py --input /path/to/bi5/files --output /path/to/output --symbol EURUSD --timeframe 1H

Features:
- Reads Dukascopy .bi5 binary tick data
- Converts to OHLC candles (configurable timeframe)
- Handles missing data with forward fill
- Produces clean CSV ready for backtesting
"""

import struct
import lzma
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import List, Tuple, Optional
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DukascopyBI5Converter:
    """Convert Dukascopy .bi5 binary tick files to OHLC CSV"""
    
    # Dukascopy .bi5 binary format:
    # Each tick = 20 bytes:
    #   - 4 bytes: timestamp offset (ms from hour start)
    #   - 4 bytes: ask price (point format)
    #   - 4 bytes: bid price (point format)
    #   - 4 bytes: ask volume
    #   - 4 bytes: bid volume
    TICK_SIZE = 20
    
    def __init__(self, symbol: str, point_value: float = None):
        """
        Initialize converter
        
        Args:
            symbol: Trading symbol (e.g., 'EURUSD', 'XAUUSD')
            point_value: Point value for price conversion (auto-detected if None)
        """
        self.symbol = symbol.upper()
        
        # Auto-detect point value based on symbol
        if point_value is None:
            if symbol.upper() in ['EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'EURGBP']:
                self.point_value = 0.00001  # 5 decimal places
            elif symbol.upper() in ['USDJPY', 'EURJPY', 'GBPJPY']:
                self.point_value = 0.001    # 3 decimal places
            elif symbol.upper() in ['XAUUSD', 'GOLD']:
                self.point_value = 0.01     # 2 decimal places
            else:
                self.point_value = 0.00001  # Default to 5 decimals
        else:
            self.point_value = point_value
        
        logger.info(f"Initialized converter for {self.symbol} with point value {self.point_value}")
    
    def read_bi5_file(self, file_path: Path) -> List[Tuple[datetime, float, float, float, float]]:
        """
        Read and decompress a single .bi5 file
        
        Args:
            file_path: Path to .bi5 file
            
        Returns:
            List of (timestamp, ask, bid, ask_volume, bid_volume) tuples
        """
        try:
            with lzma.open(file_path, 'rb') as f:
                data = f.read()
        except Exception as e:
            logger.error(f"Failed to decompress {file_path}: {e}")
            return []
        
        # Extract hour from filename (format: 00h_ticks.bi5, 01h_ticks.bi5, etc.)
        filename = file_path.name
        hour = 0
        if 'h_ticks' in filename:
            try:
                hour = int(filename.split('h_ticks')[0])
            except ValueError:
                pass
        
        # Extract date from parent directories (YYYY/MM/DD/HH)
        parts = file_path.parts
        try:
            year = int(parts[-4])
            month = int(parts[-3])
            day = int(parts[-2])
            hour_start = datetime(year, month, day, hour)
        except (ValueError, IndexError):
            logger.warning(f"Could not extract date from path: {file_path}")
            return []
        
        # Parse binary tick data
        ticks = []
        num_ticks = len(data) // self.TICK_SIZE
        
        for i in range(num_ticks):
            offset = i * self.TICK_SIZE
            
            try:
                # Unpack binary data (big-endian format)
                tick_data = struct.unpack('>5i', data[offset:offset + self.TICK_SIZE])
                
                time_offset_ms = tick_data[0]
                ask_points = tick_data[1]
                bid_points = tick_data[2]
                ask_volume = tick_data[3]
                bid_volume = tick_data[4]
                
                # Calculate timestamp
                timestamp = hour_start + timedelta(milliseconds=time_offset_ms)
                
                # Convert points to price
                ask_price = ask_points * self.point_value
                bid_price = bid_points * self.point_value
                
                ticks.append((timestamp, ask_price, bid_price, ask_volume, bid_volume))
                
            except struct.error as e:
                logger.warning(f"Failed to parse tick at offset {offset}: {e}")
                continue
        
        logger.debug(f"Read {len(ticks)} ticks from {file_path}")
        return ticks
    
    def read_bi5_folder(self, folder_path: Path) -> pd.DataFrame:
        """
        Read all .bi5 files from a folder structure
        
        Args:
            folder_path: Root folder containing .bi5 files in YYYY/MM/DD/HH structure
            
        Returns:
            DataFrame with columns: timestamp, ask, bid, ask_volume, bid_volume
        """
        logger.info(f"Reading .bi5 files from {folder_path}")
        
        all_ticks = []
        bi5_files = list(folder_path.rglob("*.bi5"))
        
        if not bi5_files:
            logger.error(f"No .bi5 files found in {folder_path}")
            return pd.DataFrame()
        
        logger.info(f"Found {len(bi5_files)} .bi5 files")
        
        for file_path in sorted(bi5_files):
            ticks = self.read_bi5_file(file_path)
            all_ticks.extend(ticks)
        
        if not all_ticks:
            logger.error("No ticks extracted from files")
            return pd.DataFrame()
        
        # Create DataFrame
        df = pd.DataFrame(
            all_ticks,
            columns=['timestamp', 'ask', 'bid', 'ask_volume', 'bid_volume']
        )
        
        # Calculate mid price (used for OHLC)
        df['price'] = (df['ask'] + df['bid']) / 2.0
        df['volume'] = df['ask_volume'] + df['bid_volume']
        
        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"Loaded {len(df)} ticks from {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
    
    def aggregate_to_ohlc(
        self,
        tick_df: pd.DataFrame,
        timeframe: str = '1H',
        fill_missing: bool = True
    ) -> pd.DataFrame:
        """
        Aggregate tick data to OHLC candles
        
        Args:
            tick_df: DataFrame with tick data (must have 'timestamp' and 'price' columns)
            timeframe: Pandas resample frequency (e.g., '1H', '4H', '1D', '15T')
            fill_missing: Fill missing candles with forward fill
            
        Returns:
            DataFrame with OHLC candles
        """
        if tick_df.empty:
            logger.error("Cannot aggregate empty DataFrame")
            return pd.DataFrame()
        
        logger.info(f"Aggregating to {timeframe} candles")
        
        # Set timestamp as index
        df = tick_df.set_index('timestamp')
        
        # Resample to OHLC
        ohlc = df['price'].resample(timeframe).ohlc()
        ohlc['volume'] = df['volume'].resample(timeframe).sum()
        
        # Fill missing candles if requested
        if fill_missing:
            # Create complete time range
            complete_range = pd.date_range(
                start=ohlc.index.min(),
                end=ohlc.index.max(),
                freq=timeframe
            )
            
            # Reindex and forward fill
            ohlc = ohlc.reindex(complete_range)
            ohlc = ohlc.fillna(method='ffill')
            
            # Fill volume NaN with 0
            ohlc['volume'] = ohlc['volume'].fillna(0)
            
            logger.info(f"Filled missing candles. Total candles: {len(ohlc)}")
        
        # Reset index to have time as column
        ohlc = ohlc.reset_index()
        ohlc.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
        
        # Remove any remaining NaN values
        ohlc = ohlc.dropna()
        
        logger.info(f"Generated {len(ohlc)} OHLC candles")
        logger.info(f"Date range: {ohlc['time'].min()} to {ohlc['time'].max()}")
        
        return ohlc
    
    def save_to_csv(
        self,
        ohlc_df: pd.DataFrame,
        output_path: Path,
        validate: bool = True
    ):
        """
        Save OHLC DataFrame to CSV
        
        Args:
            ohlc_df: DataFrame with OHLC data
            output_path: Output CSV file path
            validate: Perform validation checks before saving
        """
        if ohlc_df.empty:
            logger.error("Cannot save empty DataFrame")
            return
        
        # Validation
        if validate:
            logger.info("Validating OHLC data...")
            
            # Check for NaN values
            if ohlc_df.isnull().any().any():
                logger.warning("DataFrame contains NaN values. Dropping them.")
                ohlc_df = ohlc_df.dropna()
            
            # Check for gaps in time
            ohlc_df = ohlc_df.sort_values('time').reset_index(drop=True)
            
            # Verify OHLC integrity (high >= low, close/open between high/low)
            invalid_high_low = (ohlc_df['high'] < ohlc_df['low']).sum()
            invalid_open = ((ohlc_df['open'] > ohlc_df['high']) | (ohlc_df['open'] < ohlc_df['low'])).sum()
            invalid_close = ((ohlc_df['close'] > ohlc_df['high']) | (ohlc_df['close'] < ohlc_df['low'])).sum()
            
            if invalid_high_low > 0:
                logger.error(f"Found {invalid_high_low} candles with high < low")
            if invalid_open > 0:
                logger.error(f"Found {invalid_open} candles with invalid open")
            if invalid_close > 0:
                logger.error(f"Found {invalid_close} candles with invalid close")
            
            logger.info(f"Validation complete. {len(ohlc_df)} valid candles.")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to CSV
        ohlc_df.to_csv(output_path, index=False, float_format='%.5f')
        
        logger.info(f"✅ Saved {len(ohlc_df)} candles to {output_path}")
        logger.info(f"   File size: {output_path.stat().st_size / 1024:.2f} KB")
    
    def convert(
        self,
        input_folder: Path,
        output_path: Path,
        timeframe: str = '1H',
        fill_missing: bool = True
    ):
        """
        Complete conversion pipeline: .bi5 files → OHLC CSV
        
        Args:
            input_folder: Folder containing .bi5 files
            output_path: Output CSV file path
            timeframe: Target candle timeframe
            fill_missing: Fill missing candles
        """
        logger.info(f"Starting conversion for {self.symbol}")
        logger.info(f"Input: {input_folder}")
        logger.info(f"Output: {output_path}")
        logger.info(f"Timeframe: {timeframe}")
        
        # Step 1: Read tick data
        tick_df = self.read_bi5_folder(input_folder)
        
        if tick_df.empty:
            logger.error("Failed to read tick data")
            return
        
        # Step 2: Aggregate to OHLC
        ohlc_df = self.aggregate_to_ohlc(tick_df, timeframe, fill_missing)
        
        if ohlc_df.empty:
            logger.error("Failed to aggregate OHLC")
            return
        
        # Step 3: Save to CSV
        self.save_to_csv(ohlc_df, output_path)
        
        logger.info("✅ Conversion complete!")


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description='Convert Dukascopy .bi5 tick files to OHLC CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert EURUSD to 1H candles
  python dukascopy_bi5_converter.py --input /data/eurusd --output eurusd_h1.csv --symbol EURUSD

  # Convert XAUUSD to 4H candles
  python dukascopy_bi5_converter.py --input /data/xauusd --output xauusd_h4.csv --symbol XAUUSD --timeframe 4H

  # Convert with custom point value
  python dukascopy_bi5_converter.py --input /data/custom --output custom.csv --symbol CUSTOM --point 0.0001
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='Input folder containing .bi5 files (in YYYY/MM/DD/HH structure)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        required=True,
        help='Output CSV file path (e.g., eurusd_h1.csv)'
    )
    
    parser.add_argument(
        '--symbol', '-s',
        type=str,
        required=True,
        help='Trading symbol (e.g., EURUSD, XAUUSD)'
    )
    
    parser.add_argument(
        '--timeframe', '-t',
        type=str,
        default='1H',
        help='Target timeframe: 1H, 4H, 1D, 15T (default: 1H)'
    )
    
    parser.add_argument(
        '--point', '-p',
        type=float,
        default=None,
        help='Point value for price conversion (auto-detected if not specified)'
    )
    
    parser.add_argument(
        '--no-fill',
        action='store_true',
        help='Do not fill missing candles'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create converter
    converter = DukascopyBI5Converter(
        symbol=args.symbol,
        point_value=args.point
    )
    
    # Run conversion
    converter.convert(
        input_folder=Path(args.input),
        output_path=Path(args.output),
        timeframe=args.timeframe,
        fill_missing=not args.no_fill
    )


if __name__ == '__main__':
    main()
