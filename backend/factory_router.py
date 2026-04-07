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
        "message": (
            f"Factory started: {len(request.templates)} templates x "
            f"{request.strategies_per_template} strategies each"
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
async def get_factory_result(run_id: str):
    """Get the full result of a completed factory run."""
    doc = await _db.factory_runs.find_one({"id": run_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Factory run not found")

    if doc["status"] == FactoryStatus.RUNNING.value:
        raise HTTPException(status_code=409, detail="Factory run still in progress")

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



@router.post("/optimize-ai/{run_id}")
async def optimize_strategies_with_ai(run_id: str):
    """
    Run AI optimization on top strategies from a factory run
    Uses OpenAI + Claude to improve strategy parameters
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Get the factory run
    doc = await _db.factory_runs.find_one({"id": run_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Factory run {run_id} not found")
    
    run = FactoryRun(**doc)
    
    if run.status != FactoryStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Factory run not completed yet")
    
    if len(run.strategies) == 0:
        raise HTTPException(status_code=400, detail="No strategies to optimize")
    
    # Import AI optimizer
    from ai_strategy_optimizer import optimize_portfolio_strategies
    import os
    
    api_key = os.environ.get('EMERGENT_LLM_KEY')
    if not api_key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY not configured")
    
    logger.info(f"[AI OPTIMIZER] Starting optimization for run {run_id}")
    
    # Convert top strategies to dict format
    strategy_dicts = []
    for strat in run.strategies[:5]:  # Top 5 max
        strategy_dicts.append({
            "id": strat.id,
            "template_id": strat.template_id.value,
            "genes": strat.genes,
            "fitness": strat.fitness,
            "sharpe_ratio": strat.sharpe_ratio,
            "max_drawdown_pct": strat.max_drawdown_pct,
            "profit_factor": strat.profit_factor,
            "win_rate": strat.win_rate,
            "total_trades": strat.total_trades,
        })
    
    try:
        # Run AI optimization (max 3 strategies to avoid long wait)
        optimization_results = await optimize_portfolio_strategies(
            strategies=strategy_dicts,
            api_key=api_key,
            max_strategies=min(3, len(strategy_dicts))
        )
        
        # Update factory run with AI results
        await _db.factory_runs.update_one(
            {"id": run_id},
            {
                "$set": {
                    "ai_optimization_count": len(optimization_results),
                    "ai_optimization_results": optimization_results,
                    "ai_optimization_completed_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        logger.info(f"[AI OPTIMIZER] Completed optimization for {len(optimization_results)} strategies")
        
        return {
            "success": True,
            "run_id": run_id,
            "optimized_count": len(optimization_results),
            "results": optimization_results
        }
        
    except Exception as e:
        logger.error(f"[AI OPTIMIZER] Failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI optimization failed: {str(e)}")
