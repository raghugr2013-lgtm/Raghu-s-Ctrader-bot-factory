"""
Verify Dukascopy Cache - Quick validation script
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')


async def verify_cache():
    print("="*60)
    print("DUKASCOPY CACHE VERIFICATION")
    print("="*60)
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    collection = db.market_candles
    
    # Get statistics
    pipeline = [
        {"$match": {"source": "dukascopy"}},
        {"$group": {
            "_id": {"symbol": "$symbol", "timeframe": "$timeframe"},
            "count": {"$sum": 1},
            "min_date": {"$min": "$timestamp"},
            "max_date": {"$max": "$timestamp"}
        }},
        {"$sort": {"_id.symbol": 1, "_id.timeframe": 1}}
    ]
    
    print("\nDUKASCOPY DATA IN CACHE:")
    print("-" * 60)
    
    total_candles = 0
    async for doc in collection.aggregate(pipeline):
        symbol = doc['_id']['symbol']
        timeframe = doc['_id']['timeframe']
        count = doc['count']
        min_date = doc['min_date'].strftime('%Y-%m-%d')
        max_date = doc['max_date'].strftime('%Y-%m-%d')
        
        print(f"{symbol} {timeframe:4s}: {count:7,} candles | {min_date} to {max_date}")
        total_candles += count
    
    print("-" * 60)
    print(f"TOTAL DUKASCOPY CANDLES: {total_candles:,}")
    
    # Test sample query
    print("\n" + "="*60)
    print("SAMPLE QUERY TEST (EURUSD H1)")
    print("="*60)
    
    sample_candles = await collection.find({
        "symbol": "EURUSD",
        "timeframe": "H1",
        "source": "dukascopy"
    }).limit(5).to_list(5)
    
    if sample_candles:
        print(f"\n✅ Successfully retrieved {len(sample_candles)} sample candles")
        for i, candle in enumerate(sample_candles, 1):
            print(f"\nCandle {i}:")
            print(f"  Time: {candle['timestamp']}")
            print(f"  OHLC: O={candle['open']:.5f} H={candle['high']:.5f} L={candle['low']:.5f} C={candle['close']:.5f}")
            print(f"  Volume: {candle['volume']:.2f}")
            print(f"  Ticks: {candle['tick_count']}")
    else:
        print("❌ No sample candles found")
    
    print("\n" + "="*60)
    print("VERIFICATION COMPLETE ✅")
    print("="*60)
    
    client.close()


if __name__ == "__main__":
    asyncio.run(verify_cache())
