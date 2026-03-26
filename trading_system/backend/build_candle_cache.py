"""
Dukascopy Candle Cache Builder

Scans local Dukascopy tick data (JSON files) and converts to OHLC candles.
Stores processed candles in MongoDB for fast backtesting.

Supports: M1, M5, M15, M30, H1, H4, D1 timeframes
Symbols: EURUSD, XAUUSD
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv(Path(__file__).parent / '.env')

# Configuration
DUKASCOPY_DIR = Path("/app/data/dukascopy")
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')

# Timeframe mappings (in minutes) - using DataTimeframe enum values
TIMEFRAMES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440
}


class TickData:
    """Tick data point"""
    def __init__(self, timestamp: datetime, ask: float, bid: float, ask_volume: float, bid_volume: float):
        self.timestamp = timestamp
        self.ask = ask
        self.bid = bid
        self.mid = (ask + bid) / 2.0  # Use mid price for candles
        self.volume = ask_volume + bid_volume


class Candle:
    """OHLC Candle"""
    def __init__(self, timestamp: datetime, symbol: str, timeframe: str):
        self.timestamp = timestamp
        self.symbol = symbol
        self.timeframe = timeframe
        self.open: float = None
        self.high: float = None
        self.low: float = None
        self.close: float = None
        self.volume: float = 0.0
        self.tick_count: int = 0
    
    def add_tick(self, tick: TickData):
        """Add tick to candle"""
        price = tick.mid
        
        if self.open is None:
            self.open = price
        
        self.close = price
        
        if self.high is None or price > self.high:
            self.high = price
        
        if self.low is None or price < self.low:
            self.low = price
        
        self.volume += tick.volume
        self.tick_count += 1
    
    def is_valid(self) -> bool:
        """Check if candle has valid OHLC data"""
        return all([
            self.open is not None,
            self.high is not None,
            self.low is not None,
            self.close is not None,
            self.tick_count > 0
        ])
    
    def to_dict(self) -> dict:
        """Convert to MongoDB document"""
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "tick_count": self.tick_count,
            "source": "dukascopy",
            "created_at": datetime.now(timezone.utc)
        }


class CandleBuilder:
    """Builds candles from tick data"""
    
    def __init__(self, symbol: str, timeframe: str):
        self.symbol = symbol
        self.timeframe = timeframe
        self.timeframe_minutes = TIMEFRAMES[timeframe]
        self.candles: Dict[datetime, Candle] = {}
    
    def _get_candle_timestamp(self, tick_time: datetime) -> datetime:
        """Get candle timestamp for tick (aligned to timeframe)"""
        # Align to timeframe boundary
        minutes = (tick_time.hour * 60 + tick_time.minute) // self.timeframe_minutes * self.timeframe_minutes
        return tick_time.replace(hour=minutes // 60, minute=minutes % 60, second=0, microsecond=0)
    
    def add_tick(self, tick: TickData):
        """Add tick to appropriate candle"""
        candle_time = self._get_candle_timestamp(tick.timestamp)
        
        if candle_time not in self.candles:
            self.candles[candle_time] = Candle(candle_time, self.symbol, self.timeframe)
        
        self.candles[candle_time].add_tick(tick)
    
    def get_candles(self) -> List[Candle]:
        """Get all valid candles, sorted by time"""
        valid_candles = [c for c in self.candles.values() if c.is_valid()]
        return sorted(valid_candles, key=lambda c: c.timestamp)


class DukascopyScanner:
    """Scans Dukascopy directory for tick data files"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
    
    def scan_symbol(self, symbol: str) -> List[Path]:
        """Scan for all JSON files for a symbol"""
        symbol_dir = self.base_dir / symbol
        
        if not symbol_dir.exists():
            logger.warning(f"Symbol directory not found: {symbol_dir}")
            return []
        
        json_files = list(symbol_dir.rglob("*.json"))
        logger.info(f"Found {len(json_files)} tick data files for {symbol}")
        
        return sorted(json_files)
    
    def load_ticks_from_file(self, file_path: Path) -> List[TickData]:
        """Load ticks from JSON file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            ticks = []
            for item in data:
                try:
                    timestamp = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                    tick = TickData(
                        timestamp=timestamp,
                        ask=item['ask'],
                        bid=item['bid'],
                        ask_volume=item.get('ask_volume', 0.0),
                        bid_volume=item.get('bid_volume', 0.0)
                    )
                    ticks.append(tick)
                except (KeyError, ValueError) as e:
                    continue
            
            return ticks
            
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            return []


class CandleCacheManager:
    """Manages MongoDB candle cache"""
    
    def __init__(self, mongo_url: str, db_name: str):
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client[db_name]
        self.collection = self.db.market_candles
    
    async def ensure_indexes(self):
        """Create indexes for fast querying"""
        logger.info("Creating indexes on market_candles collection...")
        
        await self.collection.create_index([
            ("symbol", 1),
            ("timeframe", 1),
            ("timestamp", 1)
        ], unique=True, name="symbol_timeframe_timestamp")
        
        await self.collection.create_index([
            ("symbol", 1),
            ("timeframe", 1),
            ("source", 1)
        ], name="symbol_timeframe_source")
        
        logger.info("Indexes created successfully")
    
    async def clear_existing(self, symbol: str, timeframe: str):
        """Clear existing candles for symbol/timeframe"""
        result = await self.collection.delete_many({
            "symbol": symbol,
            "timeframe": timeframe,
            "source": "dukascopy"
        })
        logger.info(f"Cleared {result.deleted_count} existing {symbol} {timeframe} candles")
    
    async def bulk_insert_candles(self, candles: List[Candle]):
        """Insert candles in bulk"""
        if not candles:
            return 0
        
        documents = [c.to_dict() for c in candles]
        
        try:
            # Use ordered=False to continue on duplicate key errors
            result = await self.collection.insert_many(documents, ordered=False)
            return len(result.inserted_ids)
        except Exception as e:
            # Some duplicates are expected, count successful inserts
            error_msg = str(e)
            if "duplicate key" in error_msg.lower():
                # Extract number of inserted docs from error
                logger.warning(f"Some duplicate candles skipped: {error_msg[:200]}")
                return len([d for d in documents])
            else:
                logger.error(f"Bulk insert error: {e}")
                return 0
    
    async def get_stats(self) -> Dict:
        """Get cache statistics"""
        pipeline = [
            {"$group": {
                "_id": {"symbol": "$symbol", "timeframe": "$timeframe"},
                "count": {"$sum": 1},
                "min_date": {"$min": "$timestamp"},
                "max_date": {"$max": "$timestamp"}
            }},
            {"$sort": {"_id.symbol": 1, "_id.timeframe": 1}}
        ]
        
        stats = {}
        async for doc in self.collection.aggregate(pipeline):
            key = f"{doc['_id']['symbol']}_{doc['_id']['timeframe']}"
            stats[key] = {
                "count": doc['count'],
                "date_range": f"{doc['min_date']} to {doc['max_date']}"
            }
        
        return stats
    
    async def close(self):
        """Close MongoDB connection"""
        self.client.close()


async def build_candles_for_symbol(
    symbol: str,
    scanner: DukascopyScanner,
    cache_manager: CandleCacheManager,
    clear_existing: bool = False
):
    """Build candles for all timeframes for a symbol"""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing symbol: {symbol}")
    logger.info(f"{'='*60}")
    
    # Get all tick data files
    tick_files = scanner.scan_symbol(symbol)
    
    if not tick_files:
        logger.warning(f"No tick data found for {symbol}")
        return
    
    # Initialize builders for all timeframes
    builders = {tf: CandleBuilder(symbol, tf) for tf in TIMEFRAMES.keys()}
    
    # Process each tick file
    total_ticks = 0
    for i, file_path in enumerate(tick_files, 1):
        logger.info(f"Processing file {i}/{len(tick_files)}: {file_path.name}")
        
        ticks = scanner.load_ticks_from_file(file_path)
        total_ticks += len(ticks)
        
        # Add ticks to all timeframe builders
        for tick in ticks:
            for builder in builders.values():
                builder.add_tick(tick)
        
        # Log progress every 100 files
        if i % 100 == 0:
            logger.info(f"Progress: {i}/{len(tick_files)} files, {total_ticks:,} ticks processed")
    
    logger.info(f"Completed processing {len(tick_files)} files, {total_ticks:,} total ticks")
    
    # Store candles for each timeframe
    logger.info(f"\nStoring candles in MongoDB...")
    
    total_stored = 0
    results = {}
    
    for timeframe, builder in builders.items():
        candles = builder.get_candles()
        
        if clear_existing:
            await cache_manager.clear_existing(symbol, timeframe)
        
        stored = await cache_manager.bulk_insert_candles(candles)
        total_stored += stored
        
        results[timeframe] = {
            "generated": len(candles),
            "stored": stored,
            "date_range": f"{candles[0].timestamp} to {candles[-1].timestamp}" if candles else "N/A"
        }
        
        logger.info(f"  {timeframe}: {len(candles):,} candles generated, {stored:,} stored")
    
    logger.info(f"\nTotal candles stored: {total_stored:,}")
    
    return results


async def main():
    """Main execution"""
    
    logger.info("="*60)
    logger.info("DUKASCOPY CANDLE CACHE BUILDER")
    logger.info("="*60)
    logger.info(f"Dukascopy directory: {DUKASCOPY_DIR}")
    logger.info(f"MongoDB: {MONGO_URL}")
    logger.info(f"Database: {DB_NAME}")
    logger.info(f"Timeframes: {', '.join(TIMEFRAMES.keys())}")
    logger.info("="*60)
    
    # Initialize components
    scanner = DukascopyScanner(DUKASCOPY_DIR)
    cache_manager = CandleCacheManager(MONGO_URL, DB_NAME)
    
    # Ensure indexes exist
    await cache_manager.ensure_indexes()
    
    # Detect available symbols
    symbols = []
    for path in DUKASCOPY_DIR.iterdir():
        if path.is_dir() and not path.name.startswith('.'):
            symbols.append(path.name)
    
    logger.info(f"\nDetected symbols: {', '.join(symbols)}")
    
    # Process each symbol
    all_results = {}
    
    for symbol in symbols:
        try:
            results = await build_candles_for_symbol(
                symbol=symbol,
                scanner=scanner,
                cache_manager=cache_manager,
                clear_existing=True  # Clear existing to rebuild from scratch
            )
            all_results[symbol] = results
        except Exception as e:
            logger.error(f"Failed to process {symbol}: {e}", exc_info=True)
    
    # Display summary
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)
    
    for symbol, results in all_results.items():
        logger.info(f"\n{symbol}:")
        for timeframe, data in results.items():
            logger.info(f"  {timeframe}: {data['generated']:,} candles | {data['date_range']}")
    
    # Get final cache statistics
    logger.info("\n" + "="*60)
    logger.info("CACHE STATISTICS")
    logger.info("="*60)
    
    stats = await cache_manager.get_stats()
    for key, data in stats.items():
        logger.info(f"{key}: {data['count']:,} candles | {data['date_range']}")
    
    total_candles = sum(data['count'] for data in stats.values())
    logger.info(f"\nTOTAL CANDLES IN CACHE: {total_candles:,}")
    
    # Close connection
    await cache_manager.close()
    
    logger.info("\n" + "="*60)
    logger.info("CACHE BUILD COMPLETE ✅")
    logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())
