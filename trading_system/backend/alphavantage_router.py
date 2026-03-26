"""
AlphaVantage Market Data Router
Endpoints for fetching and storing Forex data from AlphaVantage.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from market_data_models import DataTimeframe
from market_data_provider import AlphaVantageProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alphavantage", tags=["alphavantage"])

_db = None
_market_data_service = None


def init_alphavantage_router(db, market_data_service):
    global _db, _market_data_service
    _db = db
    _market_data_service = market_data_service


# Common forex pairs
FOREX_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD",
    "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY",
]


class FetchRequest(BaseModel):
    symbol: str = "EURUSD"
    timeframe: str = "1d"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    force_refresh: bool = False  # bypass cache and hit AlphaVantage API


@router.get("/pairs")
async def list_forex_pairs():
    """List supported forex pairs."""
    return {"pairs": FOREX_PAIRS}


@router.post("/fetch")
async def fetch_and_store(request: FetchRequest):
    """
    Fetch Forex data — cache-first.
    1. Check local DB for existing candles in the requested range.
    2. If sufficient data exists, return cached data (zero API calls).
    3. If not, fetch from AlphaVantage, store in DB, then return.
    """
    api_key = os.environ.get("ALPHA_VANTAGE_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ALPHA_VANTAGE_KEY not configured. Add it to backend/.env",
        )

    try:
        tf = DataTimeframe(request.timeframe)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {request.timeframe}. Valid: {[t.value for t in DataTimeframe]}",
        )

    provider = AlphaVantageProvider(api_key)

    if not provider.validate_symbol(request.symbol):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid forex pair: {request.symbol}. Expected format: EURUSD",
        )

    start_dt = datetime.fromisoformat(request.start_date) if request.start_date else datetime(2020, 1, 1)
    end_dt = datetime.fromisoformat(request.end_date) if request.end_date else datetime.now(timezone.utc)

    # --- Cache check ---
    if not request.force_refresh:
        cached = await _market_data_service.get_candles(
            symbol=request.symbol.upper(),
            timeframe=tf,
            start_date=start_dt,
            end_date=end_dt,
        )
        if cached:
            return {
                "success": True,
                "symbol": request.symbol.upper(),
                "timeframe": request.timeframe,
                "fetched": 0,
                "cached": len(cached),
                "stored": 0,
                "source": "cache",
                "date_range": {
                    "from": cached[0].timestamp.isoformat(),
                    "to": cached[-1].timestamp.isoformat(),
                },
                "message": f"Returned {len(cached)} cached candles (no API call used)",
            }

    # --- Live fetch (no cache hit) ---
    try:
        candles = await provider.fetch_historical_data(
            symbol=request.symbol.upper(),
            timeframe=tf,
            start_date=start_dt,
            end_date=end_dt,
        )
    except ValueError as e:
        raise HTTPException(status_code=429 if "rate limit" in str(e).lower() else 400, detail=str(e))
    except Exception as e:
        logger.error(f"AlphaVantage fetch error: {e}")
        raise HTTPException(status_code=502, detail=f"AlphaVantage API error: {e}")

    if not candles:
        return {
            "success": True,
            "symbol": request.symbol.upper(),
            "timeframe": request.timeframe,
            "fetched": 0,
            "cached": 0,
            "stored": 0,
            "source": "api",
            "message": "No data returned from AlphaVantage. Check symbol/timeframe or rate limits.",
        }

    result = await _market_data_service.store_candles(
        candles, provider="alpha_vantage", overwrite=True
    )

    return {
        "success": True,
        "symbol": request.symbol.upper(),
        "timeframe": request.timeframe,
        "fetched": len(candles),
        "cached": 0,
        "stored": result["inserted"] + result["updated"],
        "skipped": result["skipped"],
        "source": "api",
        "date_range": {
            "from": candles[0].timestamp.isoformat(),
            "to": candles[-1].timestamp.isoformat(),
        },
        "message": f"Fetched {len(candles)} candles from AlphaVantage and cached locally",
    }


@router.get("/status")
async def alphavantage_status():
    """Check AlphaVantage integration status."""
    api_key = os.environ.get("ALPHA_VANTAGE_KEY")
    configured = bool(api_key)

    # List what data we already have from AlphaVantage
    stored = []
    if _db is not None:
        pipeline = [
            {"$match": {"provider": "alpha_vantage"}},
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
        "configured": configured,
        "api_key_set": configured,
        "rate_limit": "25 requests/day, 5 requests/minute (free tier)",
        "supported_pairs": FOREX_PAIRS,
        "supported_timeframes": ["1m", "5m", "15m", "30m", "1h", "1d", "1w"],
        "stored_data": stored,
    }
