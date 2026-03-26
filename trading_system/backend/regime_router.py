"""
Market Regime Detection Engine - API Router
Endpoints for regime detection and per-regime strategy analysis.
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import logging
import time

from regime_models import (
    MarketRegime,
    RegimeDetectRequest,
    RegimeBacktestRequest,
    RegimeAnalysisResult,
)
from regime_engine import RegimeClassifier, RegimeAnalyser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/regime")

db = None


def init_regime_router(database):
    global db
    db = database


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

async def _load_candles_from_db(symbol: str, timeframe: str, start: str = None, end: str = None):
    """Load candle data from market_candles collection."""
    query = {"symbol": symbol.upper(), "timeframe": timeframe}
    if start or end:
        ts_filter = {}
        if start:
            ts_filter["$gte"] = start
        if end:
            ts_filter["$lte"] = end
        query["timestamp"] = ts_filter

    docs = await db.market_candles.find(query, {"_id": 0}).sort("timestamp", 1).to_list(50000)
    return docs


async def _load_backtest_candles_and_trades(backtest_id: str):
    """Load equity/trade data from a backtest plus its candle data."""
    bt = await db.backtests.find_one({"id": backtest_id}, {"_id": 0})
    if not bt:
        raise HTTPException(status_code=404, detail=f"Backtest {backtest_id} not found")
    return bt


def _extract_ohlcv(candle_docs):
    """Extract parallel arrays from candle documents."""
    ts, opens, highs, lows, closes, volumes = [], [], [], [], [], []
    for c in candle_docs:
        t = c.get("timestamp", "")
        ts.append(t.isoformat() if hasattr(t, "isoformat") else str(t))
        opens.append(c["open"])
        highs.append(c["high"])
        lows.append(c["low"])
        closes.append(c["close"])
        volumes.append(c.get("volume", 0))
    return ts, opens, highs, lows, closes, volumes


# -----------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------

@router.post("/detect")
async def detect_regimes(req: RegimeDetectRequest):
    """
    Detect market regimes on stored candle data.
    Each candle is labeled with a regime and indicator values.
    """
    t0 = time.time()

    candle_docs = await _load_candles_from_db(req.symbol, req.timeframe, req.start_date, req.end_date)
    if not candle_docs:
        raise HTTPException(
            status_code=404,
            detail=f"No candle data found for {req.symbol}/{req.timeframe}. Import data first via /api/marketdata/import/csv.",
        )

    ts, opens, highs, lows, closes, volumes = _extract_ohlcv(candle_docs)

    classifier = RegimeClassifier(
        adx_period=req.adx_period, atr_period=req.atr_period,
        bb_period=req.bb_period, bb_std=req.bb_std, ma_period=req.ma_period,
        adx_trend_threshold=req.adx_trend_threshold,
        atr_high_vol_pct=req.atr_high_vol_percentile,
        atr_low_vol_pct=req.atr_low_vol_percentile,
    )
    regime_candles = classifier.classify(ts, opens, highs, lows, closes, volumes)

    analyser = RegimeAnalyser
    dist = analyser.distribution(regime_candles)
    segs = analyser.segments(regime_candles)
    dominant = dist[0].regime if dist else MarketRegime.RANGING
    insights, recs = analyser.generate_insights(dist, [])

    exec_time = time.time() - t0

    result = RegimeAnalysisResult(
        session_id=req.session_id,
        symbol=req.symbol,
        timeframe=req.timeframe,
        total_candles=len(regime_candles),
        adx_period=req.adx_period,
        atr_period=req.atr_period,
        bb_period=req.bb_period,
        bb_std=req.bb_std,
        ma_period=req.ma_period,
        adx_trend_threshold=req.adx_trend_threshold,
        atr_high_vol_percentile=req.atr_high_vol_percentile,
        atr_low_vol_percentile=req.atr_low_vol_percentile,
        distribution=dist,
        segments=segs,
        dominant_regime=dominant,
        insights=insights,
        recommendations=recs,
        execution_time_seconds=round(exec_time, 3),
    )

    # Persist
    doc = result.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.regime_results.insert_one(doc)

    return {
        "success": True,
        "regime_id": result.id,
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "total_candles": len(regime_candles),
        "dominant_regime": dominant.value,
        "distribution": [{"regime": d.regime.value, "candle_count": d.candle_count, "percent": d.percent} for d in dist],
        "segment_count": len(segs),
        "insights": insights,
        "recommendations": recs,
        "candles_sample": [
            {"timestamp": c.timestamp, "close": c.close, "regime": c.regime.value, "adx": c.adx, "atr_pct": c.atr_pct, "bb_width": c.bb_width, "ma_slope": c.ma_slope}
            for c in regime_candles[-20:]
        ],
        "execution_time_seconds": round(exec_time, 3),
    }


@router.post("/analyze-backtest")
async def analyze_backtest_by_regime(req: RegimeBacktestRequest):
    """
    Run regime detection on a backtest's candle data and compute
    strategy performance metrics per regime.
    """
    t0 = time.time()

    bt = await _load_backtest_candles_and_trades(req.backtest_id)
    config = bt.get("config", {})
    trades = bt.get("trades", [])
    equity = bt.get("equity_curve", [])
    initial_balance = config.get("initial_balance", 10000)

    # Build candle data from equity curve (balance over time)
    # For mock backtests, we synthesise OHLCV from equity points
    candle_docs = await _load_candles_from_db(
        config.get("symbol", "UNKNOWN"), config.get("timeframe", "1h"),
    )

    # If no stored candle data, synthesise from equity curve
    if not candle_docs and equity:
        candle_docs = _synthesise_candles_from_equity(equity, config)

    if not candle_docs:
        raise HTTPException(
            status_code=400,
            detail="No candle data available. Import market data or use a backtest with equity data.",
        )

    ts, opens, highs, lows, closes, volumes = _extract_ohlcv(candle_docs)

    classifier = RegimeClassifier(
        adx_period=req.adx_period, atr_period=req.atr_period,
        bb_period=req.bb_period, bb_std=req.bb_std, ma_period=req.ma_period,
        adx_trend_threshold=req.adx_trend_threshold,
        atr_high_vol_pct=req.atr_high_vol_percentile,
        atr_low_vol_pct=req.atr_low_vol_percentile,
    )
    regime_candles = classifier.classify(ts, opens, highs, lows, closes, volumes)

    analyser = RegimeAnalyser
    dist = analyser.distribution(regime_candles)
    segs = analyser.segments(regime_candles)
    dominant = dist[0].regime if dist else MarketRegime.RANGING

    # Map trades to regimes
    mapped = analyser.map_trades_to_regimes(regime_candles, trades)
    perf = analyser.compute_regime_metrics(mapped, initial_balance)
    best = perf[0].regime if perf else None
    worst = perf[-1].regime if perf and perf[-1].net_profit < 0 else None

    insights, recs = analyser.generate_insights(dist, perf)

    exec_time = time.time() - t0

    result = RegimeAnalysisResult(
        session_id=req.session_id,
        backtest_id=req.backtest_id,
        symbol=config.get("symbol", "UNKNOWN"),
        timeframe=config.get("timeframe", "1h"),
        total_candles=len(regime_candles),
        adx_period=req.adx_period,
        atr_period=req.atr_period,
        bb_period=req.bb_period,
        bb_std=req.bb_std,
        ma_period=req.ma_period,
        adx_trend_threshold=req.adx_trend_threshold,
        atr_high_vol_percentile=req.atr_high_vol_percentile,
        atr_low_vol_percentile=req.atr_low_vol_percentile,
        distribution=dist,
        segments=segs,
        dominant_regime=dominant,
        regime_performance=perf,
        best_regime=best,
        worst_regime=worst,
        insights=insights,
        recommendations=recs,
        execution_time_seconds=round(exec_time, 3),
    )

    doc = result.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.regime_results.insert_one(doc)

    return {
        "success": True,
        "regime_id": result.id,
        "backtest_id": req.backtest_id,
        "symbol": result.symbol,
        "timeframe": result.timeframe,
        "total_candles": len(regime_candles),
        "dominant_regime": dominant.value,
        "distribution": [{"regime": d.regime.value, "candle_count": d.candle_count, "percent": d.percent} for d in dist],
        "regime_performance": [
            {
                "regime": m.regime.value,
                "trade_count": m.trade_count,
                "win_rate": m.win_rate,
                "net_profit": m.net_profit,
                "profit_factor": m.profit_factor,
                "sharpe_ratio": m.sharpe_ratio,
                "avg_trade": m.avg_trade,
                "best_trade": m.best_trade,
                "worst_trade": m.worst_trade,
            }
            for m in perf
        ],
        "best_regime": best.value if best else None,
        "worst_regime": worst.value if worst else None,
        "insights": insights,
        "recommendations": recs,
        "execution_time_seconds": round(exec_time, 3),
    }


@router.get("/result/{regime_id}")
async def get_regime_result(regime_id: str):
    """Retrieve a saved regime analysis result."""
    doc = await db.regime_results.find_one({"id": regime_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Regime result not found")
    return {"success": True, "result": doc}


@router.get("/regimes")
async def list_regimes():
    """List all supported regime types."""
    return {
        "success": True,
        "regimes": [
            {"value": r.value, "label": r.value.replace("_", " ").title()}
            for r in MarketRegime
        ],
    }


# -----------------------------------------------------------------------
# Candle synthesis for mock backtests
# -----------------------------------------------------------------------

def _synthesise_candles_from_equity(equity_curve: list, config: dict) -> list:
    """
    Generate synthetic OHLCV candles from equity curve for regime detection.
    Uses random walk around the equity to create price-like data.
    """
    import random
    if not equity_curve:
        return []

    symbol = config.get("symbol", "EURUSD")
    base_price = 1.1000  # default for forex
    if "JPY" in symbol.upper():
        base_price = 145.0
    elif "XAU" in symbol.upper() or "GOLD" in symbol.upper():
        base_price = 1950.0
    elif "GBP" in symbol.upper():
        base_price = 1.2700

    random.seed(42)
    candles = []
    price = base_price
    volatility = price * 0.001  # 0.1% base volatility

    for pt in equity_curve:
        ts = pt.get("timestamp", "")
        # Price walks with slight correlation to equity direction
        drift = random.gauss(0, volatility)
        price += drift
        hi = price + abs(random.gauss(0, volatility * 0.5))
        lo = price - abs(random.gauss(0, volatility * 0.5))
        op = price + random.gauss(0, volatility * 0.2)
        cl = price
        vol = abs(random.gauss(1000, 300))

        candles.append({
            "timestamp": ts,
            "open": round(max(op, lo), 5),
            "high": round(hi, 5),
            "low": round(lo, 5),
            "close": round(cl, 5),
            "volume": round(vol, 0),
            "symbol": symbol,
            "timeframe": config.get("timeframe", "1h"),
        })

    return candles
