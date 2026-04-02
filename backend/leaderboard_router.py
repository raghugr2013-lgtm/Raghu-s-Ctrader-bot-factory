"""
Strategy Leaderboard - API Router
Ranks top strategies across all optimization and factory runs.
"""

import logging
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

_db = None


def init_leaderboard_router(db):
    global _db
    _db = db


@router.get("/")
async def get_leaderboard(
    sort_by: str = "fitness",
    limit: int = 50,
    strategy_type: str = None,
    min_fitness: float = 0.0,
):
    """
    Global strategy leaderboard ranking top strategies across all runs.
    Aggregates from both GA optimizer results and factory runs.
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialised")

    valid_sort_fields = {
        "fitness", "sharpe_ratio", "max_drawdown_pct",
        "profit_factor", "win_rate", "challenge_pass_pct",
        "net_profit", "monte_carlo_score",
    }
    if sort_by not in valid_sort_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by: {sort_by}. Valid: {sorted(valid_sort_fields)}",
        )

    entries = []

    # 1) Pull from GA optimizer results
    opt_docs = await _db.optimizer_results.find(
        {"status": "completed"},
        {"_id": 0, "top_genomes": 1, "strategy_type": 1, "symbol": 1,
         "timeframe": 1, "id": 1, "created_at": 1},
    ).to_list(200)

    for doc in opt_docs:
        st_type = doc.get("strategy_type", "")
        if strategy_type and st_type != strategy_type:
            continue
        for genome in doc.get("top_genomes", []):
            if genome.get("fitness", 0) < min_fitness:
                continue
            entries.append({
                "source": "optimizer",
                "run_id": doc["id"],
                "strategy_type": st_type,
                "symbol": doc.get("symbol", ""),
                "timeframe": doc.get("timeframe", ""),
                "genes": genome.get("genes", {}),
                "fitness": genome.get("fitness", 0),
                "sharpe_ratio": genome.get("sharpe_ratio", 0),
                "max_drawdown_pct": genome.get("max_drawdown_pct", 0),
                "profit_factor": genome.get("profit_factor", 0),
                "win_rate": genome.get("win_rate", 0),
                "net_profit": genome.get("net_profit", 0),
                "total_trades": genome.get("total_trades", 0),
                "monte_carlo_score": genome.get("monte_carlo_score", 0),
                "challenge_pass_pct": genome.get("challenge_pass_pct", 0),
                "created_at": doc.get("created_at"),
            })

    # 2) Pull from factory runs
    factory_docs = await _db.factory_runs.find(
        {"status": "completed"},
        {"_id": 0, "strategies": 1, "symbol": 1, "timeframe": 1,
         "id": 1, "created_at": 1},
    ).to_list(200)

    for doc in factory_docs:
        for strat in doc.get("strategies", []):
            if strat.get("fitness", 0) < min_fitness:
                continue
            tmpl = strat.get("template_id", "")
            if strategy_type and tmpl != strategy_type:
                continue
            entries.append({
                "source": "factory",
                "run_id": doc["id"],
                "strategy_type": tmpl,
                "symbol": doc.get("symbol", ""),
                "timeframe": doc.get("timeframe", ""),
                "genes": strat.get("genes", {}),
                "fitness": strat.get("fitness", 0),
                "sharpe_ratio": strat.get("sharpe_ratio", 0),
                "max_drawdown_pct": strat.get("max_drawdown_pct", 0),
                "profit_factor": strat.get("profit_factor", 0),
                "win_rate": strat.get("win_rate", 0),
                "net_profit": strat.get("net_profit", 0),
                "total_trades": strat.get("total_trades", 0),
                "monte_carlo_score": strat.get("monte_carlo_score", 0),
                "challenge_pass_pct": strat.get("challenge_pass_pct", 0),
                "created_at": doc.get("created_at"),
            })

    # Sort: drawdown ascending (lower = better), everything else descending
    reverse = sort_by != "max_drawdown_pct"
    entries.sort(key=lambda e: e.get(sort_by, 0), reverse=reverse)

    # Assign rank
    ranked = entries[:limit]
    for i, e in enumerate(ranked):
        e["rank"] = i + 1

    return {
        "success": True,
        "sort_by": sort_by,
        "total_strategies": len(entries),
        "showing": len(ranked),
        "leaderboard": ranked,
    }


@router.get("/summary")
async def leaderboard_summary():
    """Quick summary stats across all strategies."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialised")

    opt_count = await _db.optimizer_results.count_documents({"status": "completed"})
    factory_count = await _db.factory_runs.count_documents({"status": "completed"})

    # Get top 1 by fitness across optimizers
    best = None
    opt_docs = await _db.optimizer_results.find(
        {"status": "completed"},
        {"_id": 0, "top_genomes": {"$slice": 1}, "strategy_type": 1},
    ).to_list(200)

    for doc in opt_docs:
        for g in doc.get("top_genomes", []):
            if best is None or g.get("fitness", 0) > best.get("fitness", 0):
                best = {**g, "strategy_type": doc["strategy_type"], "source": "optimizer"}

    factory_docs = await _db.factory_runs.find(
        {"status": "completed"},
        {"_id": 0, "best_strategy": 1},
    ).to_list(200)

    for doc in factory_docs:
        bs = doc.get("best_strategy")
        if bs and (best is None or bs.get("fitness", 0) > best.get("fitness", 0)):
            best = {**bs, "source": "factory"}

    return {
        "optimizer_runs": opt_count,
        "factory_runs": factory_count,
        "best_strategy": best,
    }
