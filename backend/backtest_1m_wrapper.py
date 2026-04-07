"""
1M Architecture Backtest Wrapper
Fetches 1m candles and aggregates to requested timeframe for backtesting.

CRITICAL: This enforces the 1m architecture for all backtesting.
"""

import logging
from datetime import datetime
from typing import List, Tuple, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from market_data_models import Candle
from backtest_models import TradeRecord, EquityPoint, BacktestConfig
from backtest_real_engine import run_backtest_on_real_candles
from timeframe_aggregator import get_aggregator

logger = logging.getLogger(__name__)


async def run_backtest_with_1m_source(
    db: AsyncIOMotorDatabase,
    bot_name: str,
    symbol: str,
    timeframe: str,
    duration_days: int,
    initial_balance: float,
    strategy_type: str = "trend_following",
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None
) -> Tuple[List[TradeRecord], List[EquityPoint], BacktestConfig]:
    """
    Run backtest using 1m source data with dynamic aggregation.
    
    CRITICAL: 1m Architecture Enforcement
    - Fetches ONLY 1m candles from database
    - Aggregates to requested timeframe on-demand
    - NO reliance on stored higher timeframes
    
    Args:
        db: Database instance
        bot_name: Strategy name
        symbol: Trading symbol
        timeframe: Requested timeframe (will be aggregated from 1m)
        duration_days: Backtest duration
        initial_balance: Starting balance
        strategy_type: Strategy type
        from_date: Custom start date
        to_date: Custom end date
        
    Returns:
        Tuple of (trades, equity_curve, config)
    """
    logger.info(f"[1M ARCHITECTURE] Backtest requested for {symbol} {timeframe}")
    logger.info(f"[1M ARCHITECTURE] Fetching 1m source data for aggregation")
    
    # STEP 1: Fetch ONLY 1m candles from database
    query = {
        "symbol": symbol,
        "timeframe": "1m"  # ALWAYS fetch 1m
    }
    
    # Add date range filter if provided
    if from_date or to_date:
        query["timestamp"] = {}
        if from_date:
            query["timestamp"]["$gte"] = from_date
        if to_date:
            query["timestamp"]["$lte"] = to_date
    elif duration_days:
        # Fetch extra 1m data to ensure enough after aggregation
        # Extra buffer for indicator warm-up
        if to_date:
            end = to_date
        else:
            # Get latest candle timestamp
            latest = await db.market_candles.find_one(
                {"symbol": symbol, "timeframe": "1m"},
                sort=[("timestamp", -1)]
            )
            end = latest["timestamp"] if latest else datetime.now()
        
        from datetime import timedelta
        start = end - timedelta(days=duration_days + 30)  # Extra buffer
        query["timestamp"] = {"$gte": start, "$lte": end}
    
    # Fetch 1m candles
    cursor = db.market_candles.find(
        query,
        {"_id": 0}
    ).sort("timestamp", 1)
    
    candles_1m_docs = await cursor.to_list(None)
    
    if not candles_1m_docs:
        raise ValueError(f"No 1m data found for {symbol}")
    
    logger.info(f"[1M ARCHITECTURE] Fetched {len(candles_1m_docs)} 1m candles from database")
    
    # Convert to Candle objects
    from market_data_models import DataTimeframe
    candles_1m = []
    for doc in candles_1m_docs:
        candle = Candle(
            timestamp=doc['timestamp'],
            open=doc['open'],
            high=doc['high'],
            low=doc['low'],
            close=doc['close'],
            volume=doc['volume'],
            symbol=doc['symbol'],
            timeframe=DataTimeframe.M1
        )
        candles_1m.append(candle)
    
    # STEP 2: Aggregate to requested timeframe (if not 1m)
    if timeframe == "1m":
        logger.info(f"[1M ARCHITECTURE] Using 1m candles directly (no aggregation needed)")
        aggregated_candles = candles_1m
    else:
        logger.info(f"[1M ARCHITECTURE] Aggregating 1m → {timeframe}")
        
        aggregator = get_aggregator()
        
        # Convert Candle objects to dicts for aggregation
        candles_1m_dicts = [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
                "symbol": c.symbol
            }
            for c in candles_1m
        ]
        
        # Aggregate
        aggregated_dicts = aggregator.aggregate(candles_1m_dicts, timeframe)
        
        logger.info(f"[1M ARCHITECTURE] Aggregated to {len(aggregated_dicts)} {timeframe} candles")
        
        # Convert back to Candle objects
        timeframe_map = {
            "5m": DataTimeframe.M5,
            "15m": DataTimeframe.M15,
            "30m": DataTimeframe.M30,
            "1h": DataTimeframe.H1,
            "4h": DataTimeframe.H4,
            "1d": DataTimeframe.D1
        }
        
        aggregated_candles = []
        for agg_dict in aggregated_dicts:
            candle = Candle(
                timestamp=agg_dict['timestamp'],
                open=agg_dict['open'],
                high=agg_dict['high'],
                low=agg_dict['low'],
                close=agg_dict['close'],
                volume=agg_dict['volume'],
                symbol=agg_dict['symbol'],
                timeframe=timeframe_map.get(timeframe, DataTimeframe.H1)
            )
            aggregated_candles.append(candle)
    
    # STEP 3: Run backtest on aggregated candles
    logger.info(f"[1M ARCHITECTURE] Running backtest on {len(aggregated_candles)} {timeframe} candles")
    
    trades, equity_curve, config = run_backtest_on_real_candles(
        candles=aggregated_candles,
        bot_name=bot_name,
        symbol=symbol,
        timeframe=timeframe,
        duration_days=duration_days,
        initial_balance=initial_balance,
        strategy_type=strategy_type,
        from_date=from_date,
        to_date=to_date
    )
    
    logger.info(f"[1M ARCHITECTURE] Backtest complete: {len(trades)} trades generated")
    
    return trades, equity_curve, config
