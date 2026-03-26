"""
Prop Firm Challenge Simulator - API Router
Endpoints for simulating prop firm challenges using backtest trade data.
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import logging

from backtest_models import TradeRecord, TradeDirection, TradeStatus
from challenge_models import (
    ChallengeFirm,
    ChallengeSimRequest,
)
from challenge_engine import (
    FullChallengeRunner,
    ChallengeSimulator,
    get_challenge_rules,
    CHALLENGE_RULES,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/challenge")

db = None


def init_challenge_router(database):
    global db
    db = database


# -----------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------

async def _load_trade_pnls(backtest_id: str, target_balance: float = None) -> list:
    """Load trade PnLs from a backtest, optionally scaled to target balance."""
    bt = await db.backtests.find_one({"id": backtest_id}, {"_id": 0, "trades": 1, "config": 1})
    if not bt:
        raise HTTPException(status_code=404, detail=f"Backtest {backtest_id} not found")

    pnls = []
    for t in bt.get("trades", []):
        if t.get("status") == "closed" and t.get("profit_loss") is not None:
            pnls.append(t["profit_loss"])

    if not pnls:
        raise HTTPException(status_code=400, detail="Backtest has no closed trades with P&L data")

    # Scale PnLs if challenge balance differs from backtest balance
    bt_balance = bt.get("config", {}).get("initial_balance", 10000)
    if target_balance and bt_balance > 0 and abs(target_balance - bt_balance) > 1:
        scale = target_balance / bt_balance
        pnls = [p * scale for p in pnls]

    return pnls


# -----------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------

@router.post("/simulate")
async def simulate_challenge(req: ChallengeSimRequest):
    """
    Simulate a full prop firm challenge (all phases) using backtest trade data.
    Returns pass probabilities, risk metrics, and scores for each phase.
    """
    pnls = await _load_trade_pnls(req.backtest_id, req.initial_balance)

    runner = FullChallengeRunner()
    result = runner.run(
        firm=req.firm,
        trade_pnls=pnls,
        initial_balance=req.initial_balance,
        num_simulations=req.num_simulations,
    )
    result.session_id = req.session_id
    result.backtest_id = req.backtest_id

    # Persist
    doc = result.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    for pr in doc["phase_results"]:
        pr["created_at"] = pr["created_at"].isoformat()
    await db.challenge_results.insert_one(doc)

    # Build response
    phases = []
    for pr in result.phase_results:
        phases.append({
            "phase": pr.phase.value,
            "label": pr.rules.label,
            "pass_probability": pr.pass_probability,
            "daily_loss_violation_probability": pr.daily_loss_violation_probability,
            "drawdown_violation_probability": pr.drawdown_violation_probability,
            "time_limit_violation_probability": pr.time_limit_violation_probability,
            "avg_days_to_target": pr.avg_days_to_target,
            "avg_max_drawdown": pr.avg_max_drawdown,
            "avg_max_daily_loss": pr.avg_max_daily_loss,
            "challenge_score": pr.challenge_score,
            "grade": pr.grade,
            "risk_level": pr.risk_level,
            "fail_reasons": pr.fail_reasons,
            "strengths": pr.strengths,
            "weaknesses": pr.weaknesses,
            "recommendations": pr.recommendations,
            "confidence_interval": [pr.pass_rate_ci_lower, pr.pass_rate_ci_upper],
        })

    return {
        "success": True,
        "challenge_id": result.id,
        "firm": result.firm.value,
        "backtest_id": req.backtest_id,
        "phases": phases,
        "combined_pass_probability": result.combined_pass_probability,
        "overall_score": result.overall_score,
        "overall_grade": result.overall_grade,
        "is_viable": result.is_viable,
        "recommendation": result.recommendation,
        "execution_time_seconds": result.execution_time_seconds,
    }


@router.post("/simulate-all-firms")
async def simulate_all_firms(req: ChallengeSimRequest):
    """
    Run challenge simulation against ALL supported firms.
    Returns a comparison of pass probabilities across firms.
    """
    pnls = await _load_trade_pnls(req.backtest_id, req.initial_balance)
    runner = FullChallengeRunner()

    results = {}
    for firm_key in CHALLENGE_RULES:
        firm_enum = ChallengeFirm(firm_key)
        res = runner.run(
            firm=firm_enum,
            trade_pnls=pnls,
            initial_balance=req.initial_balance,
            num_simulations=req.num_simulations,
        )
        res.session_id = req.session_id
        res.backtest_id = req.backtest_id

        # Persist
        doc = res.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        for pr in doc["phase_results"]:
            pr["created_at"] = pr["created_at"].isoformat()
        await db.challenge_results.insert_one(doc)

        results[firm_key] = {
            "firm": firm_key,
            "combined_pass_probability": res.combined_pass_probability,
            "overall_score": res.overall_score,
            "overall_grade": res.overall_grade,
            "is_viable": res.is_viable,
            "recommendation": res.recommendation,
            "phases": [
                {
                    "phase": pr.phase.value,
                    "label": pr.rules.label,
                    "pass_probability": pr.pass_probability,
                    "challenge_score": pr.challenge_score,
                    "grade": pr.grade,
                }
                for pr in res.phase_results
            ],
        }

    # Rank by combined pass probability
    ranked = sorted(results.values(), key=lambda x: x["combined_pass_probability"], reverse=True)

    return {
        "success": True,
        "backtest_id": req.backtest_id,
        "firms": results,
        "ranking": [{"rank": i + 1, "firm": r["firm"], "pass_probability": r["combined_pass_probability"], "grade": r["overall_grade"]} for i, r in enumerate(ranked)],
        "best_firm": ranked[0]["firm"] if ranked else None,
    }


@router.get("/rules")
async def get_all_rules():
    """Get challenge rules for all supported firms."""
    out = {}
    for firm_key, rules_list in CHALLENGE_RULES.items():
        out[firm_key] = [
            {
                "phase": r.phase.value,
                "label": r.label,
                "profit_target_pct": r.profit_target_pct,
                "daily_loss_limit_pct": r.daily_loss_limit_pct,
                "max_drawdown_pct": r.max_drawdown_pct,
                "min_trading_days": r.min_trading_days,
                "time_limit_days": r.time_limit_days,
                "trailing_drawdown": r.trailing_drawdown,
                "news_trading_allowed": r.news_trading_allowed,
                "weekend_holding_allowed": r.weekend_holding_allowed,
            }
            for r in rules_list
        ]
    return {"success": True, "rules": out}


@router.get("/rules/{firm}")
async def get_firm_rules(firm: str):
    """Get challenge rules for a specific firm."""
    try:
        rules_list = get_challenge_rules(firm)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "success": True,
        "firm": firm,
        "phases": [
            {
                "phase": r.phase.value,
                "label": r.label,
                "profit_target_pct": r.profit_target_pct,
                "daily_loss_limit_pct": r.daily_loss_limit_pct,
                "max_drawdown_pct": r.max_drawdown_pct,
                "min_trading_days": r.min_trading_days,
                "time_limit_days": r.time_limit_days,
                "trailing_drawdown": r.trailing_drawdown,
                "news_trading_allowed": r.news_trading_allowed,
                "weekend_holding_allowed": r.weekend_holding_allowed,
            }
            for r in rules_list
        ],
    }


@router.get("/result/{challenge_id}")
async def get_challenge_result(challenge_id: str):
    """Get a previously computed challenge simulation result."""
    doc = await db.challenge_results.find_one({"id": challenge_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Challenge result not found")
    return {"success": True, "result": doc}
