"""
Strategy Factory - API Router
Endpoints for listing templates, generating strategies, and retrieving runs.
"""

import logging
import asyncio
from fastapi import APIRouter, HTTPException

from factory_models import (
    FactoryRunRequest,
    FactoryRun,
    FactoryStatus,
    TemplateId,
)
from factory_engine import get_all_templates, FactoryRunner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/factory", tags=["factory"])

_db = None
_running_jobs: dict = {}


def init_factory_router(db):
    global _db
    _db = db


@router.get("/templates")
async def list_templates():
    """List all available strategy templates with parameter definitions."""
    templates = get_all_templates()
    return {
        "templates": [
            {
                "id": t.id.value,
                "name": t.name,
                "description": t.description,
                "backtest_strategy_type": t.backtest_strategy_type,
                "param_count": len(t.param_definitions),
                "params": [p.model_dump() for p in t.param_definitions],
            }
            for t in templates.values()
        ],
        "count": len(templates),
    }


@router.post("/generate")
async def generate_strategies(request: FactoryRunRequest):
    """Generate and evaluate strategies from selected templates."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialised")

    # DATA SUFFICIENCY CHECK - Warn if less than 2 years of data
    MIN_CANDLES_2_YEARS = {
        "1h": 12_000,   # ~252 trading days * 24 hours * 2 years
        "4h": 3_000,    # ~252 * 6 * 2
        "1d": 500,      # ~252 * 2
        "15m": 48_000,  # ~252 * 24 * 4 * 2
        "30m": 24_000,  # ~252 * 24 * 2 * 2
        "1m": 720_000,  # ~252 * 24 * 60 * 2
        "5m": 144_000,  # ~252 * 24 * 12 * 2
    }
    
    candle_count = await _db.market_candles.count_documents({
        "symbol": request.symbol.upper(),
        "timeframe": request.timeframe
    })
    
    min_required = MIN_CANDLES_2_YEARS.get(request.timeframe, 12_000)
    data_years = candle_count / (min_required / 2)  # Estimate years of data
    
    data_warning = None
    if candle_count < min_required:
        data_warning = {
            "type": "INSUFFICIENT_DATA",
            "message": f"⚠️ Only {candle_count:,} candles available ({data_years:.1f} years). Recommended: {min_required:,}+ candles (2+ years) for reliable strategy generation.",
            "candle_count": candle_count,
            "recommended_minimum": min_required,
            "data_years_estimate": round(data_years, 1)
        }
        logger.warning(f"[DATA] Insufficient data for {request.symbol} {request.timeframe}: {candle_count:,} candles ({data_years:.1f} years)")

    # DATA INTEGRITY CHECK - Block if synthetic data exists
    synthetic_count = await _db.market_candles.count_documents({
        "provider": "gap_fill",
        "symbol": request.symbol.upper()
    })
    
    if synthetic_count > 0:
        return {
            "success": False,
            "error": "SYNTHETIC_DATA_DETECTED",
            "message": f"⚠️ {synthetic_count:,} synthetic candles detected for {request.symbol}. Results would be unreliable. Please clean dataset before running strategies.",
            "action_required": "Use /api/data-integrity/purge-synthetic to remove synthetic data"
        }

    # Validate templates
    valid_ids = {t.value for t in TemplateId}
    for tmpl in request.templates:
        if tmpl.value not in valid_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown template: {tmpl.value}. Available: {list(valid_ids)}",
            )

    run = FactoryRun(
        session_id=request.session_id,
        templates_used=[t.value for t in request.templates],
        strategies_per_template=request.strategies_per_template,
        symbol=request.symbol,
        timeframe=request.timeframe,
        initial_balance=request.initial_balance,
        duration_days=request.duration_days,
        challenge_firm=request.challenge_firm,
        auto_optimized=request.auto_optimize_top > 0,
    )

    _running_jobs[run.id] = run

    # Run in background thread
    asyncio.get_event_loop().run_in_executor(
        None,
        _run_factory_sync,
        run,
        request.auto_optimize_top,
    )

    return {
        "success": True,
        "run_id": run.id,
        "status": "pending",
        "data_warning": data_warning,
        "candle_count": candle_count,
        "data_years_estimate": round(data_years, 1),
        "message": (
            f"Factory started: {len(request.templates)} templates x "
            f"{request.strategies_per_template} strategies each"
            + (f" (⚠️ Limited data: {data_years:.1f} years)" if data_warning else f" ({candle_count:,} candles)")
        ),
    }


def _run_factory_sync(run: FactoryRun, auto_optimize_top: int):
    """Synchronous factory execution in a thread."""
    try:
        # CRITICAL: Auto-fetch real candles - NEVER use mock data
        from auto_fetch_candles import sync_auto_fetch_candles
        
        fetch_result = sync_auto_fetch_candles(
            symbol=run.symbol,
            timeframe=run.timeframe,
            min_candles=60,
        )
        
        if not fetch_result.success:
            # FAIL the run if real data is unavailable - DO NOT use mock
            run.status = FactoryStatus.FAILED
            run.error_message = fetch_result.error or "Real market data unavailable. Cannot proceed with backtest."
            run.data_source = "FAILED_NO_REAL_DATA"
            _persist_run(run)
            logger.error(f"Factory run {run.id} BLOCKED: {run.error_message}")
            return
        
        candles = fetch_result.candles
        run.data_source = fetch_result.source  # "cache", "twelve_data", or "alpha_vantage"
        
        runner = FactoryRunner()
        runner.run(run, candles=candles)

        # Auto-optimize top N candidates if requested
        if auto_optimize_top > 0 and run.strategies:
            _auto_optimize(run, auto_optimize_top, candles=candles)

        _persist_run(run)
        logger.info(
            f"Factory run {run.id} completed (source: {run.data_source}): "
            f"{run.total_generated} generated, {run.total_evaluated} evaluated"
        )
    except Exception as e:
        logger.error(f"Factory run {run.id} crashed: {e}")
        run.status = FactoryStatus.FAILED
        run.error_message = str(e)
        _persist_run(run)


def _load_candles_sync(symbol: str, timeframe: str):
    """Load cached candles from MongoDB (sync, for thread use)."""
    import os
    from pymongo import MongoClient
    from market_data_models import Candle, DataTimeframe

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = MongoClient(mongo_url)
    db = client[db_name]

    docs = list(
        db.market_candles.find(
            {"symbol": symbol.upper(), "timeframe": timeframe},
            {"_id": 0},
        ).sort("timestamp", 1)
    )
    client.close()

    if not docs:
        return None

    candles = []
    for d in docs:
        candles.append(Candle(
            timestamp=d["timestamp"],
            open=d["open"],
            high=d["high"],
            low=d["low"],
            close=d["close"],
            volume=d.get("volume", 0),
            symbol=d["symbol"],
            timeframe=DataTimeframe(d["timeframe"]),
        ))

    logger.info(f"Loaded {len(candles)} cached candles for {symbol} {timeframe}")
    return candles if len(candles) >= 60 else None


def _auto_optimize(run: FactoryRun, top_n: int, candles=None):
    """Kick off GA optimization for the top N strategies."""
    from factory_engine import STRATEGY_TEMPLATES
    from factory_models import TemplateId
    from optimizer_models import OptimizerRunRequest
    from optimizer_engine import GeneticOptimizer, FitnessEvaluator
    from backtest_calculator import performance_calculator, strategy_scorer
    from backtest_mock_data import mock_generator
    from optimizer_models import OptimizationResult, OptimizationStatus
    import uuid

    top_strategies = run.strategies[:top_n]

    for strat in top_strategies:
        tmpl = STRATEGY_TEMPLATES[TemplateId(strat.template_id)]

        weights = {
            "sharpe": 0.30, "drawdown": 0.20, "monte_carlo": 0.15,
            "challenge": 0.15, "regime": 0.10, "profit_factor": 0.10,
        }

        evaluator = FitnessEvaluator(
            strategy_type=tmpl.backtest_strategy_type,
            symbol=run.symbol,
            timeframe=run.timeframe,
            duration_days=run.duration_days,
            initial_balance=run.initial_balance,
            challenge_firm=run.challenge_firm,
            weights=weights,
            mock_generator=mock_generator,
            perf_calculator=performance_calculator,
            strategy_scorer=strategy_scorer,
            candles=candles,
            template_id=tmpl.id.value,
        )

        job_id = str(uuid.uuid4())
        result = OptimizationResult(
            id=job_id,
            session_id=run.session_id,
            strategy_type=tmpl.backtest_strategy_type,
            symbol=run.symbol,
            timeframe=run.timeframe,
            population_size=20,
            num_generations=10,
            initial_balance=run.initial_balance,
            param_definitions=tmpl.param_definitions,
            crossover_rate=0.8,
            mutation_rate=0.15,
            mutation_strength=0.2,
            elite_count=2,
            tournament_size=3,
            fitness_weights=weights,
        )

        optimizer = GeneticOptimizer(
            param_defs=tmpl.param_definitions,
            evaluator=evaluator,
            population_size=20,
            num_generations=10,
            elite_count=2,
        )
        optimizer.run(result)

        # Persist optimizer result
        import os
        from pymongo import MongoClient

        mongo_url = os.environ["MONGO_URL"]
        db_name = os.environ["DB_NAME"]
        client = MongoClient(mongo_url)
        db = client[db_name]
        doc = result.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        if doc.get("completed_at"):
            doc["completed_at"] = doc["completed_at"].isoformat()
        db.optimizer_results.replace_one({"id": result.id}, doc, upsert=True)
        client.close()

        run.optimization_job_ids.append(job_id)
        logger.info(f"Auto-optimized {strat.template_id}: job {job_id}, best fitness {result.best_genome.fitness if result.best_genome else 'N/A'}")


def _persist_run(run: FactoryRun):
    """Store factory run in MongoDB."""
    import os
    from pymongo import MongoClient

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = MongoClient(mongo_url)
    db = client[db_name]

    doc = run.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()

    db.factory_runs.replace_one({"id": run.id}, doc, upsert=True)
    client.close()

    _running_jobs[run.id] = run


@router.get("/status/{run_id}")
async def get_factory_status(run_id: str):
    """Get status of a factory run."""
    if run_id in _running_jobs:
        r = _running_jobs[run_id]
        return {
            "run_id": run_id,
            "status": r.status.value,
            "total_generated": r.total_generated,
            "total_evaluated": r.total_evaluated,
            "best_fitness": r.best_strategy.fitness if r.best_strategy else 0,
            "execution_time_seconds": r.execution_time_seconds,
            "error_message": r.error_message,
        }

    doc = await _db.factory_runs.find_one({"id": run_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Factory run not found")

    return {
        "run_id": run_id,
        "status": doc["status"],
        "total_generated": doc.get("total_generated", 0),
        "total_evaluated": doc.get("total_evaluated", 0),
        "best_fitness": doc.get("best_strategy", {}).get("fitness", 0) if doc.get("best_strategy") else 0,
        "execution_time_seconds": doc.get("execution_time_seconds", 0),
        "error_message": doc.get("error_message"),
    }


@router.get("/result/{run_id}")
async def get_factory_result(run_id: str, apply_filters: bool = True):
    """
    Get the full result of a completed factory run.
    Applies quality filters and adds quality labels.
    """
    from scoring_engine import QualityFilters
    
    doc = await _db.factory_runs.find_one({"id": run_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Factory run not found")

    if doc["status"] == FactoryStatus.RUNNING.value:
        raise HTTPException(status_code=409, detail="Factory run still in progress")

    # Apply quality filtering and labeling to strategies
    strategies = doc.get("strategies", [])
    filtered_strategies = []
    rejected_count = 0
    
    for strat in strategies:
        # Add quality label
        label, color, emoji = QualityFilters.get_quality_label(strat)
        strat["quality_label"] = label
        strat["quality_color"] = color
        strat["quality_emoji"] = emoji
        
        # Check if passes filters
        passes, reasons = QualityFilters.passes_all(strat)
        strat["passes_quality_filter"] = passes
        strat["filter_rejection_reasons"] = reasons
        
        if apply_filters:
            if passes:
                filtered_strategies.append(strat)
            else:
                rejected_count += 1
        else:
            filtered_strategies.append(strat)
    
    # Sort by fitness (highest first)
    filtered_strategies.sort(key=lambda x: x.get("fitness", 0), reverse=True)
    
    # Update doc with filtered strategies
    doc["strategies"] = filtered_strategies
    doc["total_passed_filters"] = len([s for s in filtered_strategies if s.get("passes_quality_filter", False)])
    doc["total_rejected"] = rejected_count
    doc["quality_filter_applied"] = apply_filters
    
    # Update best_strategy to be highest fitness that passes filters
    passing = [s for s in filtered_strategies if s.get("passes_quality_filter", False)]
    if passing:
        doc["best_strategy"] = passing[0]
    elif filtered_strategies:
        doc["best_strategy"] = filtered_strategies[0]
        doc["best_strategy"]["warning"] = "No strategies passed quality filters"

    return {"success": True, "result": doc}


@router.get("/runs/{session_id}")
async def list_factory_runs(session_id: str):
    """List all factory runs for a session."""
    docs = await _db.factory_runs.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    return {
        "success": True,
        "runs": [
            {
                "id": d["id"],
                "status": d["status"],
                "templates_used": d["templates_used"],
                "total_generated": d.get("total_generated", 0),
                "total_evaluated": d.get("total_evaluated", 0),
                "best_fitness": d.get("best_strategy", {}).get("fitness") if d.get("best_strategy") else None,
                "auto_optimized": d.get("auto_optimized", False),
                "optimization_job_ids": d.get("optimization_job_ids", []),
                "execution_time_seconds": d.get("execution_time_seconds", 0),
                "created_at": d.get("created_at"),
            }
            for d in docs
        ],
        "count": len(docs),
    }
