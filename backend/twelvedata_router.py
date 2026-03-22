"""
Twelve Data Market Data Router
Fetches forex H1/H4 OHLCV data with cache-first architecture.
"""

import os
import logging
import math
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

from market_data_models import Candle, DataTimeframe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/twelvedata", tags=["twelvedata"])

_db = None
_market_data_service = None

TWELVE_DATA_URL = "https://api.twelvedata.com/time_series"
MAX_OUTPUT = 5000  # free tier limit per request


def init_twelvedata_router(db, market_data_service):
    global _db, _market_data_service
    _db = db
    _market_data_service = market_data_service


INTERVAL_MAP = {
    "1h": "1h",
    "4h": "4h",
    "1d": "1day",
    "15m": "15min",
    "30m": "30min",
}

FOREX_SYMBOLS = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "USDCHF": "USD/CHF",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD",
    "NZDUSD": "NZD/USD",
    "EURGBP": "EUR/GBP",
    "EURJPY": "EUR/JPY",
    "GBPJPY": "GBP/JPY",
}


class TDFetchRequest(BaseModel):
    symbol: str = "EURUSD"
    timeframe: str = "1h"
    force_refresh: bool = False


@router.get("/status")
async def twelvedata_status():
    """Check Twelve Data integration status and cached data."""
    api_key = os.environ.get("TWELVE_DATA_KEY")
    stored = []
    if _db is not None:
        pipeline = [
            {"$match": {"provider": "twelve_data"}},
            {"$group": {
                "_id": {"symbol": "$symbol", "timeframe": "$timeframe"},
                "count": {"$sum": 1},
                "first": {"$min": "$timestamp"},
                "last": {"$max": "$timestamp"},
            }},
            {"$sort": {"_id.symbol": 1, "_id.timeframe": 1}},
        ]
        async for doc in _db.market_candles.aggregate(pipeline):
            stored.append({
                "symbol": doc["_id"]["symbol"],
                "timeframe": doc["_id"]["timeframe"],
                "candles": doc["count"],
                "from": doc["first"].isoformat() if doc["first"] else None,
                "to": doc["last"].isoformat() if doc["last"] else None,
            })

    return {
        "configured": bool(api_key),
        "rate_limit": "800 requests/day, 8 requests/minute (free tier)",
        "max_outputsize": MAX_OUTPUT,
        "supported_timeframes": list(INTERVAL_MAP.keys()),
        "supported_pairs": list(FOREX_SYMBOLS.keys()),
        "stored_data": stored,
    }


@router.post("/fetch")
async def fetch_and_store(request: TDFetchRequest):
    """Fetch forex data from Twelve Data with cache-first architecture."""
    api_key = os.environ.get("TWELVE_DATA_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="TWELVE_DATA_KEY not configured")

    symbol = request.symbol.upper()
    td_symbol = FOREX_SYMBOLS.get(symbol)
    if not td_symbol:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown symbol: {symbol}. Available: {list(FOREX_SYMBOLS.keys())}",
        )

    if request.timeframe not in INTERVAL_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {request.timeframe}. Valid: {list(INTERVAL_MAP.keys())}",
        )

    td_interval = INTERVAL_MAP[request.timeframe]

    # Cache check
    if not request.force_refresh:
        try:
            tf_enum = DataTimeframe(request.timeframe)
        except ValueError:
            tf_enum = None

        if tf_enum:
            cached = await _market_data_service.get_candles(
                symbol=symbol, timeframe=tf_enum,
            )
            if cached and len(cached) >= 100:
                return {
                    "success": True, "symbol": symbol,
                    "timeframe": request.timeframe,
                    "fetched": 0, "cached": len(cached), "stored": 0,
                    "source": "cache",
                    "date_range": {
                        "from": cached[0].timestamp.isoformat(),
                        "to": cached[-1].timestamp.isoformat(),
                    },
                    "message": f"Returned {len(cached)} cached candles (no API call used)",
                }

    # Fetch from Twelve Data
    try:
        candles = await _fetch_from_twelvedata(api_key, td_symbol, td_interval, symbol, request.timeframe)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Twelve Data fetch error: {e}")
        raise HTTPException(status_code=502, detail=f"Twelve Data API error: {e}")

    if not candles:
        return {
            "success": True, "symbol": symbol, "timeframe": request.timeframe,
            "fetched": 0, "cached": 0, "stored": 0, "source": "api",
            "message": "No data returned from Twelve Data",
        }

    result = await _market_data_service.store_candles(
        candles, provider="twelve_data", overwrite=True
    )

    return {
        "success": True, "symbol": symbol, "timeframe": request.timeframe,
        "fetched": len(candles), "cached": 0,
        "stored": result["inserted"] + result["updated"],
        "skipped": result["skipped"],
        "source": "api",
        "date_range": {
            "from": candles[0].timestamp.isoformat(),
            "to": candles[-1].timestamp.isoformat(),
        },
        "message": f"Fetched {len(candles)} candles from Twelve Data and cached locally",
    }


async def _fetch_from_twelvedata(api_key, td_symbol, td_interval, symbol, timeframe):
    """Fetch candles from Twelve Data REST API."""
    params = {
        "symbol": td_symbol,
        "interval": td_interval,
        "outputsize": MAX_OUTPUT,
        "apikey": api_key,
        "format": "JSON",
        "timezone": "UTC",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(TWELVE_DATA_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") == "error":
        raise ValueError(f"Twelve Data error: {data.get('message', 'Unknown error')}")

    if "code" in data and data["code"] != 200:
        raise ValueError(f"Twelve Data: {data.get('message', data)}")

    values = data.get("values", [])
    if not values:
        return []

    try:
        tf_enum = DataTimeframe(timeframe)
    except ValueError:
        tf_enum = DataTimeframe.H1

    candles = []
    for v in values:
        try:
            ts = datetime.strptime(v["datetime"], "%Y-%m-%d %H:%M:%S")
            candles.append(Candle(
                timestamp=ts,
                open=float(v["open"]),
                high=float(v["high"]),
                low=float(v["low"]),
                close=float(v["close"]),
                volume=0.0,  # forex volume not reliable
                symbol=symbol,
                timeframe=tf_enum,
            ))
        except (ValueError, KeyError) as e:
            logger.warning(f"Skipping candle {v.get('datetime', '?')}: {e}")
            continue

    candles.sort(key=lambda c: c.timestamp)
    return candles
