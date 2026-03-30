#!/usr/bin/env python3
"""
Import CSV to MongoDB for Bot Factory
Imports clean OHLC CSV files into the Bot Factory market_candles collection

Usage:
    python import_csv_to_mongodb.py --csv eurusd_h1.csv --symbol EURUSD --timeframe 1h
"""

import argparse
import pandas as pd
from pymongo import MongoClient
from datetime import datetime, timezone
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def import_csv_to_mongodb(
    csv_file: str,
    symbol: str,
    timeframe: str,
    mongo_url: str = None,
    db_name: str = None,
    overwrite: bool = False
):
    """
    Import CSV file to MongoDB
    
    Args:
        csv_file: Path to CSV file (format: time,open,high,low,close,volume)
        symbol: Trading symbol (e.g., EURUSD)
        timeframe: Timeframe code (e.g., 1h, 4h, 1d)
        mongo_url: MongoDB connection URL
        db_name: Database name
        overwrite: Overwrite existing candles
    """
    # Get MongoDB config from environment
    if mongo_url is None:
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    if db_name is None:
        db_name = os.environ.get('DB_NAME', 'trading_db')
    
    logger.info(f"Importing {csv_file} to MongoDB")
    logger.info(f"Symbol: {symbol}, Timeframe: {timeframe}")
    logger.info(f"MongoDB: {mongo_url}/{db_name}")
    
    # Read CSV
    try:
        df = pd.read_csv(csv_file)
        logger.info(f"✅ Loaded {len(df)} candles from CSV")
    except Exception as e:
        logger.error(f"❌ Failed to read CSV: {e}")
        return
    
    # Validate CSV format
    required_columns = ['time', 'open', 'high', 'low', 'close', 'volume']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        logger.error(f"❌ CSV missing required columns: {missing_columns}")
        return
    
    # Connect to MongoDB
    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        db = client[db_name]
        collection = db.market_candles
        logger.info("✅ Connected to MongoDB")
    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        return
    
    # Import candles
    inserted = 0
    updated = 0
    skipped = 0
    errors = 0
    
    logger.info("Importing candles...")
    
    for idx, row in df.iterrows():
        try:
            # Parse timestamp
            timestamp = pd.to_datetime(row['time'])
            
            # Ensure timezone-aware
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            # Create candle document
            candle = {
                'symbol': symbol.upper(),
                'timeframe': timeframe.lower(),
                'timestamp': timestamp,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']),
                'provider': 'csv_import',
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Insert or update
            if overwrite:
                result = collection.update_one(
                    {
                        'symbol': candle['symbol'],
                        'timeframe': candle['timeframe'],
                        'timestamp': candle['timestamp']
                    },
                    {'$set': candle},
                    upsert=True
                )
                
                if result.upserted_id:
                    inserted += 1
                elif result.modified_count > 0:
                    updated += 1
                else:
                    skipped += 1
            else:
                # Check if exists
                exists = collection.find_one({
                    'symbol': candle['symbol'],
                    'timeframe': candle['timeframe'],
                    'timestamp': candle['timestamp']
                })
                
                if exists:
                    skipped += 1
                else:
                    collection.insert_one(candle)
                    inserted += 1
            
            # Progress logging
            if (idx + 1) % 100 == 0:
                logger.info(f"Progress: {idx + 1}/{len(df)} candles processed")
                
        except Exception as e:
            logger.error(f"Error importing row {idx}: {e}")
            errors += 1
    
    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("IMPORT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total candles: {len(df)}")
    logger.info(f"✅ Inserted: {inserted}")
    logger.info(f"🔄 Updated: {updated}")
    logger.info(f"⏭️  Skipped: {skipped}")
    logger.info(f"❌ Errors: {errors}")
    logger.info("=" * 60)
    
    # Verify import
    count = collection.count_documents({
        'symbol': symbol.upper(),
        'timeframe': timeframe.lower()
    })
    logger.info(f"Verification: {count} candles in database for {symbol} {timeframe}")
    
    # Get date range
    first = collection.find_one(
        {'symbol': symbol.upper(), 'timeframe': timeframe.lower()},
        sort=[('timestamp', 1)]
    )
    last = collection.find_one(
        {'symbol': symbol.upper(), 'timeframe': timeframe.lower()},
        sort=[('timestamp', -1)]
    )
    
    if first and last:
        logger.info(f"Date range: {first['timestamp']} to {last['timestamp']}")
    
    client.close()
    logger.info("✅ Import complete!")


def main():
    parser = argparse.ArgumentParser(
        description='Import OHLC CSV to MongoDB for Bot Factory'
    )
    
    parser.add_argument(
        '--csv', '-c',
        type=str,
        required=True,
        help='Path to CSV file (format: time,open,high,low,close,volume)'
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
        required=True,
        help='Timeframe code (e.g., 1h, 4h, 1d)'
    )
    
    parser.add_argument(
        '--mongo-url',
        type=str,
        help='MongoDB connection URL (default: from MONGO_URL env)'
    )
    
    parser.add_argument(
        '--db-name',
        type=str,
        help='Database name (default: from DB_NAME env)'
    )
    
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing candles'
    )
    
    args = parser.parse_args()
    
    import_csv_to_mongodb(
        csv_file=args.csv,
        symbol=args.symbol,
        timeframe=args.timeframe,
        mongo_url=args.mongo_url,
        db_name=args.db_name,
        overwrite=args.overwrite
    )


if __name__ == '__main__':
    main()
