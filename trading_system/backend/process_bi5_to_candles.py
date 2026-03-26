"""
Process Dukascopy .bi5 files to OHLC candles

Converts tick data from .bi5 binary format to OHLC candles
and stores in MongoDB for backtesting.
"""

import struct
import lzma
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')


def parse_bi5_filename(filename: str) -> Tuple[datetime, int]:
    """
    Parse bi5 filename to get date and hour
    Format: YYYY_MM_DD_HH.bi5
    Example: 2025_01_02_22.bi5 -> Jan 2, 2025, 22:00
    """
    parts = filename.replace('.bi5', '').split('_')
    year = int(parts[0])
    month = int(parts[1])
    day = int(parts[2])
    hour = int(parts[3])
    
    return datetime(year, month, day, hour, tzinfo=timezone.utc), hour


def decompress_bi5(filepath: str) -> bytes:
    """Decompress .bi5 file (LZMA compressed)"""
    with open(filepath, 'rb') as f:
        compressed_data = f.read()
    
    try:
        return lzma.decompress(compressed_data)
    except Exception as e:
        logger.warning(f"Failed to decompress {filepath}: {e}")
        return b''


def parse_ticks(data: bytes, base_timestamp: datetime) -> List[dict]:
    """
    Parse tick data from decompressed .bi5 file
    
    Dukascopy tick format (20 bytes per tick):
    - 4 bytes: milliseconds from hour start (big-endian)
    - 4 bytes: ask price (big-endian, scaled by 100000)
    - 4 bytes: bid price (big-endian, scaled by 100000)
    - 4 bytes: ask volume (big-endian, scaled by 1000000)
    - 4 bytes: bid volume (big-endian, scaled by 1000000)
    """
    ticks = []
    tick_size = 20
    
    for i in range(0, len(data), tick_size):
        if i + tick_size > len(data):
            break
        
        try:
            tick_data = data[i:i+tick_size]
            
            # Unpack tick data (big-endian unsigned integers)
            millis, ask_int, bid_int, ask_vol_int, bid_vol_int = struct.unpack('>IIIII', tick_data)
            
            # Convert to actual values
            timestamp = base_timestamp + timedelta(milliseconds=millis)
            ask = ask_int / 100000.0
            bid = bid_int / 100000.0
            ask_vol = ask_vol_int / 1000000.0
            bid_vol = bid_vol_int / 1000000.0
            
            # Mid price
            mid = (ask + bid) / 2.0
            
            ticks.append({
                'timestamp': timestamp,
                'bid': bid,
                'ask': ask,
                'mid': mid,
                'bid_vol': bid_vol,
                'ask_vol': ask_vol,
            })
        except Exception as e:
            logger.warning(f"Failed to parse tick at offset {i}: {e}")
            continue
    
    return ticks


def ticks_to_ohlc_candles(ticks: List[dict], timeframe_minutes: int) -> List[dict]:
    """
    Convert ticks to OHLC candles
    
    Args:
        ticks: List of tick data
        timeframe_minutes: Candle timeframe in minutes (5, 15, 30, 60)
    
    Returns:
        List of OHLC candles
    """
    if not ticks:
        return []
    
    candles = []
    current_candle_start = None
    current_candle = None
    
    for tick in ticks:
        # Determine candle start time (aligned to timeframe)
        ts = tick['timestamp']
        candle_start = ts.replace(
            minute=(ts.minute // timeframe_minutes) * timeframe_minutes,
            second=0,
            microsecond=0
        )
        
        if current_candle_start is None or candle_start != current_candle_start:
            # New candle
            if current_candle is not None:
                candles.append(current_candle)
            
            current_candle_start = candle_start
            current_candle = {
                'timestamp': candle_start,
                'open': tick['mid'],
                'high': tick['mid'],
                'low': tick['mid'],
                'close': tick['mid'],
                'volume': tick['bid_vol'] + tick['ask_vol'],
                'tick_count': 1,
            }
        else:
            # Update current candle
            current_candle['high'] = max(current_candle['high'], tick['mid'])
            current_candle['low'] = min(current_candle['low'], tick['mid'])
            current_candle['close'] = tick['mid']
            current_candle['volume'] += tick['bid_vol'] + tick['ask_vol']
            current_candle['tick_count'] += 1
    
    # Add last candle
    if current_candle is not None:
        candles.append(current_candle)
    
    return candles


async def process_all_bi5_files():
    """Process all .bi5 files and store candles in MongoDB"""
    
    bi5_dir = Path('/app/trading_system/dukascopy_data/EURUSD')
    bi5_files = sorted(list(bi5_dir.glob('*.bi5')))
    
    logger.info(f"Found {len(bi5_files)} .bi5 files to process")
    
    if not bi5_files:
        logger.error("No .bi5 files found!")
        return
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Collections - use market_candles for all timeframes
    collection = db.market_candles
    
    # Clear existing data
    logger.info("Clearing existing EURUSD data...")
    result = await collection.delete_many({'symbol': 'EURUSD'})
    logger.info(f"  Cleared {result.deleted_count} existing candles")
    
    # Process files
    all_candles = {tf: [] for tf in [5, 15, 30, 60]}
    
    for idx, filepath in enumerate(bi5_files, 1):
        if idx % 100 == 0:
            logger.info(f"Processing file {idx}/{len(bi5_files)}: {filepath.name}")
        
        try:
            # Parse filename to get base timestamp
            base_timestamp, hour = parse_bi5_filename(filepath.name)
            
            # Decompress and parse ticks
            data = decompress_bi5(str(filepath))
            if not data:
                continue
            
            ticks = parse_ticks(data, base_timestamp)
            if not ticks:
                continue
            
            # Convert to OHLC for each timeframe
            for tf_minutes in [5, 15, 30, 60]:
                candles = ticks_to_ohlc_candles(ticks, tf_minutes)
                all_candles[tf_minutes].extend(candles)
        
        except Exception as e:
            logger.warning(f"Failed to process {filepath.name}: {e}")
            continue
    
    # Store candles in MongoDB
    logger.info("\nStoring candles in MongoDB...")
    
    for tf_minutes, candles in all_candles.items():
        if not candles:
            continue
        
        # Deduplicate by timestamp (keep last)
        unique_candles = {}
        for candle in candles:
            ts = candle['timestamp']
            unique_candles[ts] = candle
        
        candles_list = list(unique_candles.values())
        candles_list.sort(key=lambda x: x['timestamp'])
        
        # Add symbol and timeframe
        for candle in candles_list:
            candle['symbol'] = 'EURUSD'
            if tf_minutes == 60:
                candle['timeframe'] = '1h'
            else:
                candle['timeframe'] = f'{tf_minutes}m'
        
        # Bulk insert
        if candles_list:
            await collection.insert_many(candles_list)
            
            logger.info(f"  {tf_minutes}m: {len(candles_list)} candles | "
                       f"{candles_list[0]['timestamp']} to {candles_list[-1]['timestamp']}")
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("PROCESSING COMPLETE")
    logger.info("=" * 80)
    
    for tf_minutes in [5, 15, 30, 60]:
        tf_label = '1h' if tf_minutes == 60 else f'{tf_minutes}m'
        count = await collection.count_documents({'symbol': 'EURUSD', 'timeframe': tf_label})
        if count > 0:
            oldest = await collection.find_one(
                {'symbol': 'EURUSD', 'timeframe': tf_label},
                sort=[('timestamp', 1)]
            )
            newest = await collection.find_one(
                {'symbol': 'EURUSD', 'timeframe': tf_label},
                sort=[('timestamp', -1)]
            )
            
            logger.info(f"{tf_label}: {count} candles | "
                       f"{oldest['timestamp'].strftime('%Y-%m-%d %H:%M')} to "
                       f"{newest['timestamp'].strftime('%Y-%m-%d %H:%M')}")
    
    client.close()
    logger.info("\n✅ All data processed and stored in MongoDB")


if __name__ == "__main__":
    asyncio.run(process_all_bi5_files())
