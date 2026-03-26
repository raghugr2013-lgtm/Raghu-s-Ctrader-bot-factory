#!/bin/bash
# Dukascopy Cache Management Script
# Quick commands for cache operations

echo "================================================"
echo "DUKASCOPY CACHE MANAGEMENT"
echo "================================================"

show_menu() {
    echo ""
    echo "Available Commands:"
    echo "1. Rebuild cache (scan all Dukascopy data)"
    echo "2. Verify cache (show statistics)"
    echo "3. Test pipeline (integration test)"
    echo "4. Test complete backtest (end-to-end)"
    echo "5. Show cache size"
    echo "6. Exit"
    echo ""
    read -p "Select option (1-6): " choice
    
    case $choice in
        1)
            echo ""
            echo "Rebuilding cache from Dukascopy data..."
            cd /app/backend && python3 build_candle_cache.py
            ;;
        2)
            echo ""
            echo "Verifying cache..."
            cd /app/backend && python3 verify_cache.py
            ;;
        3)
            echo ""
            echo "Testing pipeline integration..."
            cd /app/backend && python3 test_dukascopy_pipeline.py
            ;;
        4)
            echo ""
            echo "Running complete backtest test..."
            cd /app/backend && python3 test_complete_backtest.py
            ;;
        5)
            echo ""
            echo "Cache size in MongoDB..."
            cd /app/backend && python3 -c "
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path('.env'))

async def get_size():
    client = AsyncIOMotorClient(os.environ.get('MONGO_URL'))
    db = client[os.environ.get('DB_NAME')]
    
    stats = await db.command('collstats', 'market_candles')
    
    print(f'Collection: market_candles')
    print(f'Total documents: {stats[\"count\"]:,}')
    print(f'Storage size: {stats.get(\"storageSize\", 0) / 1024 / 1024:.2f} MB')
    print(f'Total size: {stats.get(\"size\", 0) / 1024 / 1024:.2f} MB')
    
    # Count by source
    dukascopy_count = await db.market_candles.count_documents({'source': 'dukascopy'})
    print(f'Dukascopy candles: {dukascopy_count:,}')
    
    client.close()

asyncio.run(get_size())
"
            ;;
        6)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid option!"
            ;;
    esac
    
    show_menu
}

show_menu
