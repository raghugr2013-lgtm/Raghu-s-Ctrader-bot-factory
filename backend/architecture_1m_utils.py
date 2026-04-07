"""
1M Architecture Utilities
Helper functions for working with 1m source data architecture.

This module provides convenient wrappers and utilities to ensure
all data operations follow the 1m-first architecture.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from timeframe_aggregator import get_aggregator
from backtest_1m_wrapper import run_backtest_with_1m_source

logger = logging.getLogger(__name__)


async def fetch_and_aggregate(
    db: AsyncIOMotorDatabase,
    symbol: str,
    timeframe: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Fetch 1m candles and aggregate to requested timeframe.
    
    This is the recommended way to get candles for any analysis.
    
    Args:
        db: Database instance
        symbol: Trading symbol
        timeframe: Target timeframe (1m, 5m, 15m, 1h, etc.)
        start_date: Optional start date filter
        end_date: Optional end date filter
        limit: Optional limit on 1m candles to fetch
        
    Returns:
        List of aggregated candles
        
    Example:
        ```python
        # Get 1h candles (aggregated from 1m)
        candles = await fetch_and_aggregate(
            db=db,
            symbol="EURUSD",
            timeframe="1h",
            limit=10000
        )
        
        # Use for backtesting
        trades = run_backtest(candles, ...)
        ```
    """
    logger.info(f"[1M ARCHITECTURE] Fetching 1m data for {symbol}")
    
    # Build query
    query = {
        "symbol": symbol,
        "timeframe": "1m"  # ALWAYS fetch 1m
    }
    
    if start_date or end_date:
        query["timestamp"] = {}
        if start_date:
            query["timestamp"]["$gte"] = start_date
        if end_date:
            query["timestamp"]["$lte"] = end_date
    
    # Fetch 1m candles
    cursor = db.market_candles.find(query, {"_id": 0}).sort("timestamp", 1)
    
    if limit:
        cursor = cursor.limit(limit)
    
    candles_1m = await cursor.to_list(None)
    
    if not candles_1m:
        logger.warning(f"No 1m data found for {symbol}")
        return []
    
    logger.info(f"[1M ARCHITECTURE] Fetched {len(candles_1m)} 1m candles")
    
    # Aggregate if needed
    if timeframe == "1m":
        return candles_1m
    
    logger.info(f"[1M ARCHITECTURE] Aggregating 1m → {timeframe}")
    aggregator = get_aggregator()
    aggregated = aggregator.aggregate(candles_1m, timeframe)
    
    logger.info(f"[1M ARCHITECTURE] Produced {len(aggregated)} {timeframe} candles")
    
    return aggregated


async def get_coverage_info(
    db: AsyncIOMotorDatabase,
    symbol: str
) -> Dict[str, Any]:
    """
    Get data coverage information for a symbol (1m source only).
    
    Args:
        db: Database instance
        symbol: Trading symbol
        
    Returns:
        Coverage information dict
        
    Example:
        ```python
        coverage = await get_coverage_info(db, "EURUSD")
        print(f"Coverage: {coverage['coverage_percent']}%")
        print(f"Gaps: {coverage['gap_count']}")
        ```
    """
    logger.info(f"[1M ARCHITECTURE] Checking coverage for {symbol}")
    
    # Count 1m candles
    total_candles = await db.market_candles.count_documents({
        "symbol": symbol,
        "timeframe": "1m"
    })
    
    if total_candles == 0:
        return {
            "symbol": symbol,
            "timeframe": "1m",
            "total_candles": 0,
            "coverage_percent": 0,
            "note": "No 1m data available"
        }
    
    # Get date range
    first = await db.market_candles.find_one(
        {"symbol": symbol, "timeframe": "1m"},
        sort=[("timestamp", 1)]
    )
    
    last = await db.market_candles.find_one(
        {"symbol": symbol, "timeframe": "1m"},
        sort=[("timestamp", -1)]
    )
    
    # Use timeframe_aggregator for coverage validation
    aggregator = get_aggregator()
    candles = await db.market_candles.find(
        {"symbol": symbol, "timeframe": "1m"},
        {"_id": 0}
    ).sort("timestamp", 1).to_list(None)
    
    coverage = aggregator.validate_coverage(candles, "1m")
    
    return {
        "symbol": symbol,
        "timeframe": "1m",
        "total_candles": coverage["total_candles"],
        "expected_candles": coverage["expected_candles"],
        "coverage_percent": coverage["coverage_percent"],
        "gap_count": coverage["gap_count"],
        "first_candle": first["timestamp"].isoformat() if first else None,
        "last_candle": last["timestamp"].isoformat() if last else None,
        "note": "1m is source; higher timeframes derived on-demand"
    }


async def backtest_strategy(
    db: AsyncIOMotorDatabase,
    strategy_name: str,
    symbol: str,
    timeframe: str,
    duration_days: int = 365,
    initial_balance: float = 10000.0,
    strategy_type: str = "trend_following",
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None
):
    """
    Backtest a strategy using 1m source data.
    
    This is a convenient wrapper around run_backtest_with_1m_source.
    
    Args:
        db: Database instance
        strategy_name: Name of the strategy
        symbol: Trading symbol
        timeframe: Timeframe to backtest on (aggregated from 1m)
        duration_days: Backtest duration in days
        initial_balance: Starting balance
        strategy_type: Type of strategy
        from_date: Optional custom start date
        to_date: Optional custom end date
        
    Returns:
        Tuple of (trades, equity_curve, config)
        
    Example:
        ```python
        trades, equity, config = await backtest_strategy(
            db=db,
            strategy_name="EMA_CROSSOVER",
            symbol="EURUSD",
            timeframe="1h",
            duration_days=365
        )
        
        print(f"Total trades: {len(trades)}")
        print(f"Final balance: ${equity[-1].balance}")
        ```
    """
    return await run_backtest_with_1m_source(
        db=db,
        bot_name=strategy_name,
        symbol=symbol,
        timeframe=timeframe,
        duration_days=duration_days,
        initial_balance=initial_balance,
        strategy_type=strategy_type,
        from_date=from_date,
        to_date=to_date
    )


def is_1m_architecture_compliant(code_snippet: str) -> Dict[str, Any]:
    """
    Check if code follows 1m architecture best practices.
    
    This is a development helper to audit code compliance.
    
    Args:
        code_snippet: Python code to check
        
    Returns:
        Compliance report
        
    Example:
        ```python
        code = '''
        candles = await db.market_candles.find({
            "symbol": "EURUSD",
            "timeframe": "1h"  # ❌ Bad
        }).to_list(None)
        '''
        
        report = is_1m_architecture_compliant(code)
        if not report['compliant']:
            print(f"Issues: {report['issues']}")
        ```
    """
    issues = []
    warnings = []
    
    # Check for non-1m timeframe queries
    if '"timeframe": "' in code_snippet and '"timeframe": "1m"' not in code_snippet:
        issues.append("Direct query for non-1m timeframe detected")
    
    # Check for get_candles with timeframe
    if 'get_candles(' in code_snippet and 'timeframe=' in code_snippet:
        warnings.append("Consider using fetch_and_aggregate() instead of get_candles()")
    
    # Check for run_backtest_on_real_candles without wrapper
    if 'run_backtest_on_real_candles' in code_snippet:
        if 'run_backtest_with_1m_source' not in code_snippet:
            warnings.append("Consider using backtest_strategy() or run_backtest_with_1m_source()")
    
    # Check for good patterns
    good_patterns = []
    if 'run_backtest_with_1m_source' in code_snippet:
        good_patterns.append("Uses 1m wrapper for backtesting")
    if 'fetch_and_aggregate' in code_snippet:
        good_patterns.append("Uses fetch_and_aggregate utility")
    if '"timeframe": "1m"' in code_snippet:
        good_patterns.append("Queries 1m source data")
    
    compliant = len(issues) == 0
    
    return {
        "compliant": compliant,
        "issues": issues,
        "warnings": warnings,
        "good_patterns": good_patterns,
        "recommendation": (
            "Code follows 1m architecture" if compliant
            else "Update code to use 1m source data"
        )
    }


# Quick access exports
__all__ = [
    'fetch_and_aggregate',
    'get_coverage_info',
    'backtest_strategy',
    'is_1m_architecture_compliant'
]
