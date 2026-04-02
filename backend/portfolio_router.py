"""
Portfolio Strategy Engine - API Router
Phase 7: Portfolio management, correlation, backtesting, Monte Carlo, optimization
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import Optional
import logging

from backtest_models import TradeRecord, TradeDirection, TradeStatus, EquityPoint
from portfolio_models import (
    Portfolio,
    PortfolioStrategy,
    CreatePortfolioRequest,
    AddStrategyRequest,
    PortfolioBacktestRequest,
    PortfolioMonteCarloRequest,
    OptimizeAllocationRequest,
    AllocationMethod,
)
from portfolio_engine import (
    CorrelationAnalyzer,
    PortfolioBacktester,
    PortfolioMonteCarloEngine,
    AllocationOptimizer,
    extract_daily_returns,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio")

# Set during init
db = None


def init_portfolio_router(database):
    global db
    db = database


# -----------------------------------------------------------------------
# Helper: load trades from a backtest
# -----------------------------------------------------------------------

async def _load_backtest_trades(backtest_id: str):
    """Load backtest and its trades from DB."""
    bt = await db.backtests.find_one({"id": backtest_id}, {"_id": 0})
    if not bt:
        raise HTTPException(status_code=404, detail=f"Backtest {backtest_id} not found")

    trades_raw = bt.get("trades", [])
    trades = []
    for t in trades_raw:
        trades.append(TradeRecord(
            id=t["id"],
            backtest_id=t["backtest_id"],
            entry_time=datetime.fromisoformat(t["entry_time"]) if isinstance(t["entry_time"], str) else t["entry_time"],
            exit_time=datetime.fromisoformat(t["exit_time"]) if isinstance(t.get("exit_time"), str) else t.get("exit_time"),
            symbol=t["symbol"],
            direction=TradeDirection(t["direction"]),
            entry_price=t["entry_price"],
            exit_price=t.get("exit_price"),
            stop_loss=t.get("stop_loss"),
            take_profit=t.get("take_profit"),
            volume=t["volume"],
            position_size=t["position_size"],
            profit_loss=t.get("profit_loss"),
            profit_loss_pips=t.get("profit_loss_pips"),
            profit_loss_percent=t.get("profit_loss_percent"),
            duration_minutes=t.get("duration_minutes"),
            commission=t.get("commission", 0),
            status=TradeStatus(t["status"]),
            close_reason=t.get("close_reason"),
        ))

    equity_raw = bt.get("equity_curve", [])
    return bt, trades, equity_raw


# -----------------------------------------------------------------------
# CRUD
# -----------------------------------------------------------------------

@router.post("/create")
async def create_portfolio(req: CreatePortfolioRequest):
    """Create a new empty portfolio."""
    portfolio = Portfolio(
        session_id=req.session_id,
        name=req.name,
        description=req.description,
        initial_balance=req.initial_balance,
    )
    doc = portfolio.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.portfolios.insert_one(doc)

    return {
        "success": True,
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
    }


@router.get("/{portfolio_id}")
async def get_portfolio(portfolio_id: str):
    """Get portfolio by ID."""
    doc = await db.portfolios.find_one({"id": portfolio_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"success": True, "portfolio": doc}


@router.get("/list/{session_id}")
async def list_portfolios(session_id: str):
    """List all portfolios for a session."""
    docs = await db.portfolios.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"success": True, "portfolios": docs, "count": len(docs)}


# -----------------------------------------------------------------------
# Add / Remove Strategy
# -----------------------------------------------------------------------

@router.post("/{portfolio_id}/add-strategy")
async def add_strategy(portfolio_id: str, req: AddStrategyRequest):
    """Add a strategy (from a completed backtest) to a portfolio."""
    doc = await db.portfolios.find_one({"id": portfolio_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Load backtest to get metrics
    bt, trades, equity_raw = await _load_backtest_trades(req.backtest_id)
    metrics = bt.get("metrics", {})
    score = bt.get("strategy_score", {})
    config = bt.get("config", {})

    daily_returns = extract_daily_returns(equity_raw)

    strat = PortfolioStrategy(
        name=req.name,
        backtest_id=req.backtest_id,
        symbol=config.get("symbol", "UNKNOWN"),
        timeframe=config.get("timeframe", "1h"),
        net_profit=metrics.get("net_profit", 0),
        win_rate=metrics.get("win_rate", 0),
        profit_factor=metrics.get("profit_factor", 0),
        sharpe_ratio=metrics.get("sharpe_ratio", 0),
        max_drawdown_percent=metrics.get("max_drawdown_percent", 0),
        total_trades=metrics.get("total_trades", 0),
        strategy_score=score.get("total_score", 0),
        daily_returns=daily_returns,
    )

    strategies = doc.get("strategies", [])
    strategies.append(strat.model_dump())

    # Re-weight equally
    n = len(strategies)
    for s in strategies:
        s["weight"] = round(1.0 / n, 4)
        s["weight_percent"] = round(100.0 / n, 1)

    await db.portfolios.update_one(
        {"id": portfolio_id},
        {"$set": {
            "strategies": strategies,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    return {
        "success": True,
        "portfolio_id": portfolio_id,
        "strategy_added": strat.name,
        "total_strategies": n,
    }


@router.delete("/{portfolio_id}/strategy/{strategy_id}")
async def remove_strategy(portfolio_id: str, strategy_id: str):
    """Remove a strategy from portfolio."""
    doc = await db.portfolios.find_one({"id": portfolio_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    strategies = [s for s in doc.get("strategies", []) if s.get("strategy_id") != strategy_id]
    n = len(strategies)
    for s in strategies:
        s["weight"] = round(1.0 / n, 4) if n > 0 else 0
        s["weight_percent"] = round(100.0 / n, 1) if n > 0 else 0

    await db.portfolios.update_one(
        {"id": portfolio_id},
        {"$set": {
            "strategies": strategies,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"success": True, "remaining_strategies": n}


# -----------------------------------------------------------------------
# Correlation Analysis
# -----------------------------------------------------------------------

@router.post("/{portfolio_id}/analyze-correlation")
async def analyze_correlation(portfolio_id: str):
    """Run correlation analysis on portfolio strategies."""
    doc = await db.portfolios.find_one({"id": portfolio_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    strategies_raw = doc.get("strategies", [])
    if len(strategies_raw) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 strategies for correlation analysis")

    strategies = [PortfolioStrategy(**s) for s in strategies_raw]
    analyzer = CorrelationAnalyzer()
    result = analyzer.analyze(strategies)
    result.portfolio_id = portfolio_id

    result_doc = result.model_dump()
    result_doc["created_at"] = result_doc["created_at"].isoformat()

    await db.portfolios.update_one(
        {"id": portfolio_id},
        {"$set": {
            "correlation_result": result_doc,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    return {
        "success": True,
        "portfolio_id": portfolio_id,
        "average_correlation": result.average_correlation,
        "diversification_score": result.diversification_score,
        "pairs": [p.model_dump() for p in result.pairs],
        "recommendations": result.recommendations,
    }


# -----------------------------------------------------------------------
# Portfolio Backtest
# -----------------------------------------------------------------------

@router.post("/{portfolio_id}/backtest")
async def run_portfolio_backtest(portfolio_id: str, req: PortfolioBacktestRequest):
    """Run combined portfolio backtest."""
    doc = await db.portfolios.find_one({"id": portfolio_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    strategies_raw = doc.get("strategies", [])
    if not strategies_raw:
        raise HTTPException(status_code=400, detail="Portfolio has no strategies")

    strategies = [PortfolioStrategy(**s) for s in strategies_raw]
    initial_balance = req.initial_balance or doc.get("initial_balance", 100000.0)

    # Load all trades
    all_trades = {}
    all_equity = {}
    for strat in strategies:
        bt, trades, eq_raw = await _load_backtest_trades(strat.backtest_id)
        all_trades[strat.backtest_id] = trades
        equity = [EquityPoint(
            timestamp=datetime.fromisoformat(p["timestamp"]) if isinstance(p["timestamp"], str) else p["timestamp"],
            balance=p["balance"],
            equity=p.get("equity", p["balance"]),
            drawdown=p.get("drawdown", 0),
            drawdown_percent=p.get("drawdown_percent", 0),
        ) for p in eq_raw]
        all_equity[strat.backtest_id] = equity

    backtester = PortfolioBacktester()
    result = backtester.run(strategies, all_trades, all_equity, initial_balance)
    result.portfolio_id = portfolio_id
    result.session_id = req.session_id

    result_doc = result.model_dump()
    result_doc["created_at"] = result_doc["created_at"].isoformat()

    await db.portfolios.update_one(
        {"id": portfolio_id},
        {"$set": {
            "backtest_result": result_doc,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    return {
        "success": True,
        "portfolio_id": portfolio_id,
        "backtest_id": result.id,
        "summary": {
            "net_profit": result.metrics.net_profit,
            "total_return_percent": result.metrics.total_return_percent,
            "profit_factor": result.metrics.profit_factor,
            "max_drawdown_percent": result.metrics.max_drawdown_percent,
            "sharpe_ratio": result.metrics.sharpe_ratio,
            "win_rate": result.metrics.win_rate,
            "total_trades": result.metrics.total_trades,
            "diversification_ratio": result.metrics.diversification_ratio,
            "portfolio_score": result.metrics.portfolio_score,
            "grade": result.grade,
            "is_deployable": result.is_deployable,
        },
        "strategy_results": result.strategy_results,
    }


# -----------------------------------------------------------------------
# Portfolio Monte Carlo
# -----------------------------------------------------------------------

@router.post("/{portfolio_id}/monte-carlo")
async def run_portfolio_monte_carlo(portfolio_id: str, req: PortfolioMonteCarloRequest):
    """Run Monte Carlo simulation on the portfolio."""
    doc = await db.portfolios.find_one({"id": portfolio_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    strategies_raw = doc.get("strategies", [])
    if not strategies_raw:
        raise HTTPException(status_code=400, detail="Portfolio has no strategies")

    strategies = [PortfolioStrategy(**s) for s in strategies_raw]
    initial_balance = doc.get("initial_balance", 100000.0)

    all_trades = {}
    for strat in strategies:
        _, trades, _ = await _load_backtest_trades(strat.backtest_id)
        all_trades[strat.backtest_id] = trades

    mc = PortfolioMonteCarloEngine()
    result = mc.run(
        strategies, all_trades, initial_balance,
        num_simulations=req.num_simulations,
        ruin_threshold_pct=req.ruin_threshold_percent,
    )
    result.portfolio_id = portfolio_id
    result.session_id = req.session_id

    result_doc = result.model_dump()
    result_doc["created_at"] = result_doc["created_at"].isoformat()

    await db.portfolios.update_one(
        {"id": portfolio_id},
        {"$set": {
            "monte_carlo_result": result_doc,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    return {
        "success": True,
        "portfolio_id": portfolio_id,
        "summary": {
            "profit_probability": result.profit_probability,
            "ruin_probability": result.ruin_probability,
            "expected_return_percent": result.expected_return_percent,
            "worst_case_drawdown": result.worst_case_drawdown,
            "robustness_score": result.robustness_score,
            "grade": result.grade,
            "risk_level": result.risk_level,
        },
        "confidence_intervals": {
            "balance_95_ci": [result.balance_ci_lower, result.balance_ci_upper],
            "return_95_ci": [result.return_ci_lower, result.return_ci_upper],
        },
        "insights": {
            "strengths": result.strengths,
            "weaknesses": result.weaknesses,
            "recommendations": result.recommendations,
        },
    }


# -----------------------------------------------------------------------
# Allocation Optimization
# -----------------------------------------------------------------------

@router.post("/{portfolio_id}/optimize")
async def optimize_allocation(portfolio_id: str, req: OptimizeAllocationRequest):
    """Optimize portfolio allocation weights."""
    doc = await db.portfolios.find_one({"id": portfolio_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    strategies_raw = doc.get("strategies", [])
    if len(strategies_raw) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 strategies to optimize")

    strategies = [PortfolioStrategy(**s) for s in strategies_raw]
    initial_balance = doc.get("initial_balance", 100000.0)

    all_trades = {}
    for strat in strategies:
        _, trades, _ = await _load_backtest_trades(strat.backtest_id)
        all_trades[strat.backtest_id] = trades

    optimizer = AllocationOptimizer()
    result = optimizer.optimize(strategies, req.method, all_trades, initial_balance)
    result.portfolio_id = portfolio_id

    result_doc = result.model_dump()
    result_doc["created_at"] = result_doc["created_at"].isoformat()

    # Also update strategy weights in portfolio
    for s in strategies_raw:
        new_w = result.weights.get(s["name"], s.get("weight", 0))
        s["weight"] = round(new_w, 4)
        s["weight_percent"] = round(new_w * 100, 1)

    await db.portfolios.update_one(
        {"id": portfolio_id},
        {"$set": {
            "allocation_result": result_doc,
            "allocation_method": req.method.value,
            "strategies": strategies_raw,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    return {
        "success": True,
        "portfolio_id": portfolio_id,
        "method": req.method.value,
        "weights": result.weights,
        "expected_return": result.expected_return,
        "expected_volatility": result.expected_volatility,
        "expected_sharpe": result.expected_sharpe,
        "improvement_vs_equal": result.improvement_vs_equal,
        "recommendations": result.recommendations,
    }
