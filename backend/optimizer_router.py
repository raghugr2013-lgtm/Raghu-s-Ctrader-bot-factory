"""
Genetic Algorithm Strategy Optimizer - API Router
Endpoints for running, monitoring, and retrieving optimization jobs.
"""

import logging
import uuid
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from optimizer_models import (
    OptimizerRunRequest,
    OptimizationResult,
    OptimizationStatus,
    DEFAULT_PARAMS,
    StrategyGenome,
)
from optimizer_engine import GeneticOptimizer, FitnessEvaluator, GenomeFactory
from backtest_calculator import performance_calculator, strategy_scorer
from backtest_mock_data import mock_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/optimizer", tags=["optimizer"])

# Module-level state
_db = None
_running_jobs: dict = {}  # job_id -> OptimizationResult (in-memory status cache)


def init_optimizer_router(db):
    global _db
    _db = db


@router.get("/strategies")
async def list_strategy_types():
    """List available strategy types with their default parameter definitions."""
    return {
        "strategies": {
            name: [p.model_dump() for p in params]
            for name, params in DEFAULT_PARAMS.items()
        }
    }


@router.post("/run")
async def run_optimization(request: OptimizerRunRequest):
    """Start a genetic algorithm optimization job (runs in background)."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialised")

    # Resolve parameter definitions
    param_defs = request.custom_params or DEFAULT_PARAMS.get(request.strategy_type)
    if not param_defs:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy type: {request.strategy_type}. "
                   f"Available: {list(DEFAULT_PARAMS.keys())}",
        )

    job_id = str(uuid.uuid4())

    # Build fitness weights dict
    weights = {
        "sharpe": request.sharpe_weight,
        "drawdown": request.drawdown_weight,
        "monte_carlo": request.monte_carlo_weight,
        "challenge": request.challenge_weight,
        "regime": request.regime_weight,
        "profit_factor": request.profit_factor_weight,
    }

    # Build initial result object
    result = OptimizationResult(
        id=job_id,
        session_id=request.session_id,
        status=OptimizationStatus.PENDING,
        strategy_type=request.strategy_type,
        symbol=request.symbol,
        timeframe=request.timeframe,
        population_size=request.population_size,
        num_generations=request.num_generations,
        initial_balance=request.initial_balance,
        param_definitions=param_defs,
        crossover_rate=request.crossover_rate,
        mutation_rate=request.mutation_rate,
        mutation_strength=request.mutation_strength,
        elite_count=request.elite_count,
        tournament_size=request.tournament_size,
        fitness_weights=weights,
    )

    # Cache the pending result
    _running_jobs[job_id] = result

    # Launch optimization in background
    asyncio.get_event_loop().run_in_executor(
        None,
        _run_optimization_sync,
        job_id,
        param_defs,
        request,
        weights,
        result,
    )

    return {
        "success": True,
        "job_id": job_id,
        "status": "pending",
        "message": f"Optimization started: {request.population_size} individuals x {request.num_generations} generations",
    }


def _run_optimization_sync(job_id, param_defs, request, weights, result):
    """Synchronous optimisation function that runs in a thread."""
    try:
        # Load real candles from DB if available
        candles = _load_candles_sync(request.symbol, request.timeframe)

        evaluator = FitnessEvaluator(
            strategy_type=request.strategy_type,
            symbol=request.symbol,
            timeframe=request.timeframe,
            duration_days=request.duration_days,
            initial_balance=request.initial_balance,
            challenge_firm=request.challenge_firm,
            weights=weights,
            mock_generator=mock_generator,
            perf_calculator=performance_calculator,
            strategy_scorer=strategy_scorer,
            candles=candles,
            template_id=request.template_id or request.strategy_type,
        )

        optimizer = GeneticOptimizer(
            param_defs=param_defs,
            evaluator=evaluator,
            population_size=request.population_size,
            num_generations=request.num_generations,
            crossover_rate=request.crossover_rate,
            mutation_rate=request.mutation_rate,
            mutation_strength=request.mutation_strength,
            elite_count=request.elite_count,
            tournament_size=request.tournament_size,
        )

        final_result = optimizer.run(result)
        final_result.data_source = "real_candles" if candles else "mock"

        # Serialize and persist to MongoDB
        _persist_result(final_result)

        logger.info(
            f"Optimization {job_id} completed: "
            f"best fitness={final_result.best_genome.fitness if final_result.best_genome else 'N/A'}"
        )
    except Exception as e:
        logger.error(f"Optimization {job_id} crashed: {e}")
        result.status = OptimizationStatus.FAILED
        result.error_message = str(e)
        _persist_result(result)



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

    logger.info(f"Optimizer loaded {len(candles)} cached candles for {symbol} {timeframe}")
    return candles if len(candles) >= 60 else None


def _persist_result(result: OptimizationResult):
    """Store result in MongoDB (called from thread, uses sync client)."""
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

    # Upsert by id
    db.optimizer_results.replace_one({"id": result.id}, doc, upsert=True)
    client.close()

    # Update in-memory cache
    _running_jobs[result.id] = result


@router.get("/status/{job_id}")
async def get_optimization_status(job_id: str):
    """Get the status / progress of an optimization job."""
    # Check in-memory cache first
    if job_id in _running_jobs:
        r = _running_jobs[job_id]
        return {
            "job_id": job_id,
            "status": r.status.value,
            "current_generation": r.current_generation,
            "total_generations": r.num_generations,
            "total_evaluations": r.total_evaluations,
            "execution_time_seconds": r.execution_time_seconds,
            "best_fitness": r.best_genome.fitness if r.best_genome else (
                r.generation_history[-1].best_fitness if r.generation_history else 0
            ),
            "error_message": r.error_message,
        }

    # Fall back to DB
    doc = await _db.optimizer_results.find_one({"id": job_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Optimization job not found")

    return {
        "job_id": job_id,
        "status": doc["status"],
        "current_generation": doc.get("current_generation", 0),
        "total_generations": doc.get("num_generations", 0),
        "total_evaluations": doc.get("total_evaluations", 0),
        "execution_time_seconds": doc.get("execution_time_seconds", 0),
        "best_fitness": doc.get("best_genome", {}).get("fitness", 0) if doc.get("best_genome") else 0,
        "error_message": doc.get("error_message"),
    }


@router.get("/result/{job_id}")
async def get_optimization_result(job_id: str):
    """Get the full result of a completed optimization job."""
    doc = await _db.optimizer_results.find_one({"id": job_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Optimization job not found")

    if doc["status"] == OptimizationStatus.RUNNING.value:
        raise HTTPException(status_code=409, detail="Optimization still running")

    return {
        "success": True,
        "result": doc,
    }


@router.get("/list/{session_id}")
async def list_optimizations(session_id: str):
    """List all optimization jobs for a session."""
    docs = await _db.optimizer_results.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    return {
        "success": True,
        "optimizations": [
            {
                "id": d["id"],
                "status": d["status"],
                "strategy_type": d["strategy_type"],
                "symbol": d["symbol"],
                "timeframe": d["timeframe"],
                "population_size": d["population_size"],
                "num_generations": d["num_generations"],
                "best_fitness": d.get("best_genome", {}).get("fitness") if d.get("best_genome") else None,
                "execution_time_seconds": d.get("execution_time_seconds", 0),
                "created_at": d.get("created_at"),
            }
            for d in docs
        ],
        "count": len(docs),
    }
