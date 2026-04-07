"""
Market Data Service
Handles storage, retrieval, and management of historical candle data
"""

from typing import List, Optional, Dict
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import logging

from market_data_models import (
    Candle,
    DataTimeframe,
    StoredCandle,
    MarketDataStats,
    SymbolInfo
)

logger = logging.getLogger(__name__)


class MarketDataService:
    """Service for managing historical market data"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.market_candles
    
    async def ensure_indexes(self):
        """Create indexes for efficient querying"""
        try:
            # Compound index for symbol + timeframe + timestamp (unique)
            await self.collection.create_index(
                [("symbol", 1), ("timeframe", 1), ("timestamp", 1)],
                unique=True,
                name="symbol_timeframe_timestamp"
            )
            
            # Index for querying by date range
            await self.collection.create_index(
                [("timestamp", 1)],
                name="timestamp"
            )
            
            # Index for provider filtering
            await self.collection.create_index(
                [("provider", 1)],
                name="provider"
            )
            
            logger.info("Market data indexes created successfully")
        
        except Exception as e:
            logger.error(f"Failed to create indexes: {str(e)}")
    
    async def store_candles(
        self,
        candles: List[Candle],
        provider: str = "csv_import",
        overwrite: bool = False
    ) -> Dict[str, int]:
        """
        Store candles in database
        Returns: {inserted: count, skipped: count, updated: count}
        """
        if not candles:
            return {"inserted": 0, "skipped": 0, "updated": 0}
        
        inserted = 0
        skipped = 0
        updated = 0
        
        for candle in candles:
            try:
                stored_candle = StoredCandle(
                    symbol=candle.symbol,
                    timeframe=candle.timeframe.value,
                    timestamp=candle.timestamp,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                    provider=provider
                )
                
                doc = stored_candle.model_dump()
                doc['timestamp'] = doc['timestamp'].replace(tzinfo=timezone.utc) if doc['timestamp'].tzinfo is None else doc['timestamp']
                doc['created_at'] = doc['created_at'].isoformat()
                
                if overwrite:
                    # Update or insert
                    result = await self.collection.update_one(
                        {
                            "symbol": candle.symbol,
                            "timeframe": candle.timeframe.value,
                            "timestamp": doc['timestamp']
                        },
                        {"$set": doc},
                        upsert=True
                    )
                    
                    if result.upserted_id:
                        inserted += 1
                    elif result.modified_count > 0:
                        updated += 1
                    else:
                        skipped += 1
                else:
                    # Insert only if doesn't exist
                    try:
                        await self.collection.insert_one(doc)
                        inserted += 1
                    except Exception:
                        # Duplicate key - skip
                        skipped += 1
            
            except Exception as e:
                logger.warning(f"Failed to store candle: {str(e)}")
                skipped += 1
        
        logger.info(f"Stored candles: {inserted} inserted, {updated} updated, {skipped} skipped")
        
        return {
            "inserted": inserted,
            "skipped": skipped,
            "updated": updated
        }
    
    async def get_candles(
        self,
        symbol: str,
        timeframe: DataTimeframe,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 10000
    ) -> List[Candle]:
        """
        Retrieve candles from database
        """
        query = {
            "symbol": symbol,
            "timeframe": timeframe.value
        }
        
        # Add date range filter
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date.replace(tzinfo=timezone.utc) if start_date.tzinfo is None else start_date
            if end_date:
                date_filter["$lte"] = end_date.replace(tzinfo=timezone.utc) if end_date.tzinfo is None else end_date
            query["timestamp"] = date_filter
        
        try:
            cursor = self.collection.find(
                query,
                {"_id": 0}
            ).sort("timestamp", 1).limit(limit)
            
            candles = []
            async for doc in cursor:
                candle = Candle(
                    timestamp=doc['timestamp'],
                    open=doc['open'],
                    high=doc['high'],
                    low=doc['low'],
                    close=doc['close'],
                    volume=doc['volume'],
                    symbol=doc['symbol'],
                    timeframe=DataTimeframe(doc['timeframe'])
                )
                candles.append(candle)
            
            return candles
        
        except Exception as e:
            logger.error(f"Failed to retrieve candles: {str(e)}")
            return []
    
    async def get_stats(
        self,
        symbol: str,
        timeframe: DataTimeframe
    ) -> Optional[MarketDataStats]:
        """
        Get statistics about stored data
        """
        try:
            # Count total candles
            count = await self.collection.count_documents({
                "symbol": symbol,
                "timeframe": timeframe.value
            })
            
            if count == 0:
                return None
            
            # Get first and last timestamp
            first_doc = await self.collection.find_one(
                {"symbol": symbol, "timeframe": timeframe.value},
                {"timestamp": 1, "_id": 0},
                sort=[("timestamp", 1)]
            )
            
            last_doc = await self.collection.find_one(
                {"symbol": symbol, "timeframe": timeframe.value},
                {"timestamp": 1, "provider": 1, "created_at": 1, "_id": 0},
                sort=[("timestamp", -1)]
            )
            
            if not first_doc or not last_doc:
                return None
            
            first_ts = first_doc['timestamp']
            last_ts = last_doc['timestamp']
            date_range = (last_ts - first_ts).days
            
            return MarketDataStats(
                symbol=symbol,
                timeframe=timeframe.value,
                total_candles=count,
                first_timestamp=first_ts,
                last_timestamp=last_ts,
                date_range_days=date_range,
                provider=last_doc.get('provider', 'unknown'),
                last_updated=datetime.fromisoformat(last_doc['created_at']) if isinstance(last_doc.get('created_at'), str) else last_doc.get('created_at', datetime.now(timezone.utc))
            )
        
        except Exception as e:
            logger.error(f"Failed to get stats: {str(e)}")
            return None
    
    async def get_available_symbols(self) -> List[str]:
        """Get list of symbols with data available"""
        try:
            symbols = await self.collection.distinct("symbol")
            return sorted(symbols)
        except Exception as e:
            logger.error(f"Failed to get symbols: {str(e)}")
            return []
    
    async def get_available_timeframes(self, symbol: str) -> List[str]:
        """Get list of timeframes available for a symbol"""
        try:
            timeframes = await self.collection.distinct("timeframe", {"symbol": symbol})
            return sorted(timeframes)
        except Exception as e:
            logger.error(f"Failed to get timeframes: {str(e)}")
            return []
    
    async def delete_candles(
        self,
        symbol: str,
        timeframe: Optional[DataTimeframe] = None
    ) -> int:
        """
        Delete candles
        Returns: Number of deleted documents
        """
        query = {"symbol": symbol}
        if timeframe:
            query["timeframe"] = timeframe.value
        
        try:
            result = await self.collection.delete_many(query)
            logger.info(f"Deleted {result.deleted_count} candles for {symbol}")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Failed to delete candles: {str(e)}")
            return 0
    
    async def check_data_gaps(
        self,
        symbol: str,
        timeframe: DataTimeframe,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        Check for gaps in data coverage
        Returns list of gaps with start/end timestamps
        """
        candles = await self.get_candles(symbol, timeframe, start_date, end_date)
        
        if not candles:
            return [{"start": start_date, "end": end_date, "missing_candles": "all"}]
        
        from market_data_models import get_timeframe_minutes
        timeframe_minutes = get_timeframe_minutes(timeframe)
        expected_interval = timedelta(minutes=timeframe_minutes)
        
        gaps = []
        for i in range(len(candles) - 1):
            current_time = candles[i].timestamp
            next_time = candles[i + 1].timestamp
            expected_next = current_time + expected_interval
            
            if next_time > expected_next + expected_interval:
                # Gap detected
                missing_candles = int((next_time - expected_next).total_seconds() / (timeframe_minutes * 60))
                gaps.append({
                    "start": expected_next,
                    "end": next_time,
                    "missing_candles": missing_candles
                })
        
        return gaps


# Create singleton instance (will be initialized with db in server.py)
market_data_service = None


def init_market_data_service(db: AsyncIOMotorDatabase):
    """Initialize market data service with database"""
    global market_data_service
    market_data_service = MarketDataService(db)
    return market_data_service
