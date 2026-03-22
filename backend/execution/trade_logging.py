"""
Trade Logging System - Real Trade Storage
Handles all trade logging, retrieval, and analytics
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os

router = APIRouter(prefix="/api/trades", tags=["trades"])

# MongoDB connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
trades_collection = db["trades"]


class TradeLogRequest(BaseModel):
    """Request model for logging a trade"""
    bot_id: str = Field(..., description="Unique bot identifier")
    bot_name: str = Field(..., description="Human-readable bot name")
    symbol: str = Field(..., description="Trading symbol (e.g., EURUSD)")
    direction: Literal["BUY", "SELL"] = Field(..., description="Trade direction")
    lot_size: float = Field(..., gt=0, description="Position size in lots")
    entry_price: float = Field(..., description="Entry price")
    exit_price: Optional[float] = Field(None, description="Exit price (null if still open)")
    stop_loss: Optional[float] = Field(0, description="Stop loss price")
    take_profit: Optional[float] = Field(0, description="Take profit price")
    pnl: Optional[float] = Field(None, description="Profit/loss in account currency")
    pips: Optional[float] = Field(None, description="Profit/loss in pips")
    result: Optional[Literal["WIN", "LOSS", "BREAKEVEN", "OPEN"]] = Field("OPEN", description="Trade result")
    reason: Optional[str] = Field("Signal", description="Entry reason/signal")
    close_reason: Optional[str] = Field(None, description="Exit reason")
    mode: Literal["backtest", "forward_test", "live"] = Field(..., description="Execution mode")
    timestamp_entry: Optional[datetime] = Field(None, description="Entry timestamp")
    timestamp_exit: Optional[datetime] = Field(None, description="Exit timestamp")


class TradeLogResponse(BaseModel):
    """Response model for trade operations"""
    success: bool
    trade_id: str
    message: str


class TradeRecord(BaseModel):
    """Full trade record model"""
    id: str
    bot_id: str
    bot_name: str
    symbol: str
    direction: str
    lot_size: float
    entry_price: float
    exit_price: Optional[float]
    stop_loss: float
    take_profit: float
    pnl: Optional[float]
    pips: Optional[float]
    result: str
    reason: str
    close_reason: Optional[str]
    mode: str
    timestamp_entry: str
    timestamp_exit: Optional[str]
    created_at: str


class TradeListResponse(BaseModel):
    """Response model for trade list"""
    success: bool
    total: int
    trades: List[dict]
    summary: dict


@router.post("/log", response_model=TradeLogResponse)
async def log_trade(trade: TradeLogRequest):
    """
    Log a new trade or update existing trade
    Called by bots when entering/exiting positions
    """
    try:
        now = datetime.now(timezone.utc)
        
        trade_doc = {
            "bot_id": trade.bot_id,
            "bot_name": trade.bot_name,
            "symbol": trade.symbol,
            "direction": trade.direction,
            "lot_size": trade.lot_size,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "stop_loss": trade.stop_loss,
            "take_profit": trade.take_profit,
            "pnl": trade.pnl,
            "pips": trade.pips,
            "result": trade.result or "OPEN",
            "reason": trade.reason,
            "close_reason": trade.close_reason,
            "mode": trade.mode,
            "timestamp_entry": (trade.timestamp_entry or now).isoformat(),
            "timestamp_exit": trade.timestamp_exit.isoformat() if trade.timestamp_exit else None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        
        result = await trades_collection.insert_one(trade_doc)
        trade_id = str(result.inserted_id)
        
        return TradeLogResponse(
            success=True,
            trade_id=trade_id,
            message=f"Trade logged successfully: {trade.direction} {trade.symbol}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log trade: {str(e)}")


@router.put("/close/{trade_id}")
async def close_trade(
    trade_id: str,
    exit_price: float,
    pnl: float,
    pips: float,
    result: Literal["WIN", "LOSS", "BREAKEVEN"],
    close_reason: str
):
    """
    Close an open trade with exit details
    """
    try:
        from bson import ObjectId
        
        now = datetime.now(timezone.utc)
        
        update_result = await trades_collection.update_one(
            {"_id": ObjectId(trade_id)},
            {
                "$set": {
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "pips": pips,
                    "result": result,
                    "close_reason": close_reason,
                    "timestamp_exit": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            }
        )
        
        if update_result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Trade not found")
        
        return {
            "success": True,
            "message": f"Trade {trade_id} closed with {result}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to close trade: {str(e)}")


@router.get("", response_model=TradeListResponse)
async def get_trades(
    bot_id: Optional[str] = None,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    result: Optional[str] = None,
    mode: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get trade history with optional filters
    """
    try:
        # Build query filter
        query = {}
        if bot_id:
            query["bot_id"] = bot_id
        if symbol:
            query["symbol"] = symbol
        if direction:
            query["direction"] = direction.upper()
        if result:
            if result.lower() == "profit":
                query["result"] = "WIN"
            elif result.lower() == "loss":
                query["result"] = "LOSS"
            else:
                query["result"] = result.upper()
        if mode:
            query["mode"] = mode
        
        # Get total count
        total = await trades_collection.count_documents(query)
        
        # Get trades with pagination
        cursor = trades_collection.find(query, {"_id": 0}).sort("timestamp_entry", -1).skip(offset).limit(limit)
        trades = await cursor.to_list(length=limit)
        
        # Calculate summary stats
        all_trades_cursor = trades_collection.find(query, {"pnl": 1, "result": 1, "_id": 0})
        all_trades = await all_trades_cursor.to_list(length=10000)
        
        total_pnl = sum(t.get("pnl", 0) or 0 for t in all_trades)
        wins = sum(1 for t in all_trades if t.get("result") == "WIN")
        losses = sum(1 for t in all_trades if t.get("result") == "LOSS")
        total_closed = wins + losses
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        
        # Calculate profit factor
        gross_profit = sum(t.get("pnl", 0) for t in all_trades if (t.get("pnl") or 0) > 0)
        gross_loss = abs(sum(t.get("pnl", 0) for t in all_trades if (t.get("pnl") or 0) < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit if gross_profit > 0 else 0
        
        summary = {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(gross_profit / wins, 2) if wins > 0 else 0,
            "avg_loss": round(gross_loss / losses, 2) if losses > 0 else 0,
        }
        
        return TradeListResponse(
            success=True,
            total=total,
            trades=trades,
            summary=summary
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch trades: {str(e)}")


@router.get("/stats/{bot_id}")
async def get_bot_trade_stats(bot_id: str, days: int = 30):
    """
    Get trading statistics for a specific bot
    """
    try:
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = {
            "bot_id": bot_id,
            "timestamp_entry": {"$gte": cutoff.isoformat()}
        }
        
        cursor = trades_collection.find(query, {"_id": 0})
        trades = await cursor.to_list(length=10000)
        
        if not trades:
            return {
                "success": True,
                "bot_id": bot_id,
                "period_days": days,
                "stats": {
                    "total_trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0,
                    "total_pnl": 0,
                    "max_drawdown": 0,
                    "profit_factor": 0,
                }
            }
        
        # Calculate stats
        total_pnl = sum(t.get("pnl", 0) or 0 for t in trades)
        wins = sum(1 for t in trades if t.get("result") == "WIN")
        losses = sum(1 for t in trades if t.get("result") == "LOSS")
        total_closed = wins + losses
        
        # Calculate max drawdown from equity curve
        equity_curve = []
        running_balance = 0
        peak = 0
        max_dd = 0
        
        for trade in sorted(trades, key=lambda x: x.get("timestamp_entry", "")):
            pnl = trade.get("pnl", 0) or 0
            running_balance += pnl
            equity_curve.append(running_balance)
            if running_balance > peak:
                peak = running_balance
            dd = peak - running_balance
            if dd > max_dd:
                max_dd = dd
        
        gross_profit = sum(t.get("pnl", 0) for t in trades if (t.get("pnl") or 0) > 0)
        gross_loss = abs(sum(t.get("pnl", 0) for t in trades if (t.get("pnl") or 0) < 0))
        
        return {
            "success": True,
            "bot_id": bot_id,
            "period_days": days,
            "stats": {
                "total_trades": len(trades),
                "wins": wins,
                "losses": losses,
                "win_rate": round((wins / total_closed * 100) if total_closed > 0 else 0, 1),
                "total_pnl": round(total_pnl, 2),
                "max_drawdown": round(max_dd, 2),
                "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0,
                "avg_pnl_per_trade": round(total_pnl / len(trades), 2) if trades else 0,
            },
            "equity_curve": equity_curve[-50:],  # Last 50 points
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bot stats: {str(e)}")


@router.delete("/{trade_id}")
async def delete_trade(trade_id: str):
    """
    Delete a trade record (admin only)
    """
    try:
        from bson import ObjectId
        
        result = await trades_collection.delete_one({"_id": ObjectId(trade_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Trade not found")
        
        return {"success": True, "message": f"Trade {trade_id} deleted"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete trade: {str(e)}")
