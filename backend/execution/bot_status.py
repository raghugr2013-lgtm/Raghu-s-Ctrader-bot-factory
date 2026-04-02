"""
Bot Status Management System
Handles bot registration, status updates, and real-time monitoring
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import os
import asyncio
import json

router = APIRouter(prefix="/api/bots", tags=["bots"])

# MongoDB connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
bots_collection = db["bots"]
bot_history_collection = db["bot_history"]

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
    
    async def broadcast(self, message: dict):
        disconnected = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(client_id)
        for client_id in disconnected:
            self.disconnect(client_id)
    
    async def send_to_client(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception:
                self.disconnect(client_id)

manager = ConnectionManager()


class BotRegistration(BaseModel):
    """Request model for registering a new bot"""
    bot_id: str = Field(..., description="Unique bot identifier")
    bot_name: str = Field(..., description="Human-readable name")
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Trading timeframe (e.g., H4, M15)")
    strategy_type: str = Field(..., description="Strategy type (e.g., EMA Crossover)")
    initial_balance: float = Field(..., description="Starting balance")
    risk_config: dict = Field(..., description="Risk configuration from /bot-config")
    mode: Literal["backtest", "forward_test", "live"] = Field(..., description="Execution mode")


class BotStatusUpdate(BaseModel):
    """Request model for bot status update (heartbeat)"""
    bot_id: str = Field(..., description="Bot identifier")
    status: Literal["RUNNING", "WARNING", "STOPPED", "PAUSED", "ERROR"] = Field(..., description="Current status")
    current_balance: float = Field(..., description="Current balance")
    daily_pnl: float = Field(0, description="Today's P&L")
    daily_pnl_percent: float = Field(0, description="Today's P&L percentage")
    total_pnl: float = Field(0, description="Total P&L since start")
    total_pnl_percent: float = Field(0, description="Total P&L percentage")
    current_drawdown: float = Field(0, description="Current drawdown percentage")
    max_drawdown_reached: float = Field(0, description="Maximum drawdown reached")
    trades_today: int = Field(0, description="Number of trades today")
    open_trades: int = Field(0, description="Currently open trades")
    win_rate: float = Field(0, description="Win rate percentage")
    stop_reason: Optional[str] = Field(None, description="Reason if stopped")
    last_trade_time: Optional[str] = Field(None, description="Last trade timestamp")


class BotStatusResponse(BaseModel):
    """Response model for bot status"""
    bot_id: str
    bot_name: str
    symbol: str
    timeframe: str
    status: str
    mode: str
    initial_balance: float
    current_balance: float
    daily_pnl: float
    daily_pnl_percent: float
    total_pnl: float
    total_pnl_percent: float
    current_drawdown: float
    max_drawdown_limit: float
    max_drawdown_reached: float
    trades_today: int
    max_trades_per_day: int
    open_trades: int
    win_rate: float
    stop_reason: Optional[str]
    last_trade_time: Optional[str]
    last_heartbeat: str
    uptime_seconds: int


@router.post("/register")
async def register_bot(bot: BotRegistration):
    """
    Register a new bot in the system
    """
    try:
        now = datetime.now(timezone.utc)
        
        # Check if bot already exists
        existing = await bots_collection.find_one({"bot_id": bot.bot_id})
        if existing:
            # Update existing bot
            await bots_collection.update_one(
                {"bot_id": bot.bot_id},
                {"$set": {
                    "bot_name": bot.bot_name,
                    "symbol": bot.symbol,
                    "timeframe": bot.timeframe,
                    "strategy_type": bot.strategy_type,
                    "initial_balance": bot.initial_balance,
                    "current_balance": bot.initial_balance,
                    "risk_config": bot.risk_config,
                    "mode": bot.mode,
                    "status": "RUNNING",
                    "updated_at": now.isoformat(),
                    "last_heartbeat": now.isoformat(),
                }}
            )
            return {"success": True, "message": f"Bot {bot.bot_id} updated", "bot_id": bot.bot_id}
        
        # Create new bot document
        bot_doc = {
            "bot_id": bot.bot_id,
            "bot_name": bot.bot_name,
            "symbol": bot.symbol,
            "timeframe": bot.timeframe,
            "strategy_type": bot.strategy_type,
            "initial_balance": bot.initial_balance,
            "current_balance": bot.initial_balance,
            "daily_pnl": 0,
            "daily_pnl_percent": 0,
            "total_pnl": 0,
            "total_pnl_percent": 0,
            "current_drawdown": 0,
            "max_drawdown_reached": 0,
            "trades_today": 0,
            "open_trades": 0,
            "win_rate": 0,
            "risk_config": bot.risk_config,
            "mode": bot.mode,
            "status": "RUNNING",
            "stop_reason": None,
            "last_trade_time": None,
            "last_heartbeat": now.isoformat(),
            "start_time": now.isoformat(),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        
        await bots_collection.insert_one(bot_doc)
        
        # Broadcast new bot to all connected clients
        await manager.broadcast({
            "type": "BOT_REGISTERED",
            "bot_id": bot.bot_id,
            "bot_name": bot.bot_name,
            "timestamp": now.isoformat()
        })
        
        return {"success": True, "message": f"Bot {bot.bot_id} registered", "bot_id": bot.bot_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register bot: {str(e)}")


@router.post("/heartbeat")
async def update_bot_status(update: BotStatusUpdate):
    """
    Update bot status (called periodically by running bots)
    Also used to detect DD breaches and auto-stop
    """
    try:
        now = datetime.now(timezone.utc)
        
        # Get bot configuration
        bot = await bots_collection.find_one({"bot_id": update.bot_id}, {"_id": 0})
        if not bot:
            raise HTTPException(status_code=404, detail=f"Bot {update.bot_id} not found")
        
        risk_config = bot.get("risk_config", {})
        max_daily_dd = risk_config.get("maxDailyDrawdown", 5)
        max_total_dd = risk_config.get("maxTotalDrawdown", 10)
        max_trades = risk_config.get("maxTradesPerDay", 5)
        
        # Check for DD breach
        auto_stop = False
        stop_reason = update.stop_reason
        new_status = update.status
        
        if update.current_drawdown >= max_daily_dd:
            auto_stop = True
            stop_reason = f"Daily DD limit breached ({update.current_drawdown:.1f}% >= {max_daily_dd}%)"
            new_status = "STOPPED"
        elif update.max_drawdown_reached >= max_total_dd:
            auto_stop = True
            stop_reason = f"Total DD limit breached ({update.max_drawdown_reached:.1f}% >= {max_total_dd}%)"
            new_status = "STOPPED"
        elif update.trades_today >= max_trades and update.status == "RUNNING":
            new_status = "WARNING"
            stop_reason = f"Max trades per day reached ({update.trades_today}/{max_trades})"
        
        # Calculate uptime
        start_time = datetime.fromisoformat(bot.get("start_time", now.isoformat()).replace("Z", "+00:00"))
        uptime = int((now - start_time).total_seconds())
        
        # Update bot document
        update_doc = {
            "status": new_status,
            "current_balance": update.current_balance,
            "daily_pnl": update.daily_pnl,
            "daily_pnl_percent": update.daily_pnl_percent,
            "total_pnl": update.total_pnl,
            "total_pnl_percent": update.total_pnl_percent,
            "current_drawdown": update.current_drawdown,
            "max_drawdown_reached": max(update.max_drawdown_reached, bot.get("max_drawdown_reached", 0)),
            "trades_today": update.trades_today,
            "open_trades": update.open_trades,
            "win_rate": update.win_rate,
            "stop_reason": stop_reason,
            "last_trade_time": update.last_trade_time,
            "last_heartbeat": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        
        await bots_collection.update_one(
            {"bot_id": update.bot_id},
            {"$set": update_doc}
        )
        
        # Store history point
        history_doc = {
            "bot_id": update.bot_id,
            "timestamp": now.isoformat(),
            "balance": update.current_balance,
            "daily_pnl": update.daily_pnl,
            "drawdown": update.current_drawdown,
            "trades_today": update.trades_today,
            "status": new_status,
        }
        await bot_history_collection.insert_one(history_doc)
        
        # Trigger alerts if needed
        try:
            from execution.telegram_alerts import check_and_alert_drawdown, check_and_alert_profit
            
            # Check drawdown alerts
            await check_and_alert_drawdown(
                update.bot_id,
                bot.get("bot_name", "Unknown"),
                update.current_drawdown,
                max_total_dd
            )
            
            # Check profit alerts
            if update.daily_pnl_percent > 0 or update.total_pnl_percent > 0:
                await check_and_alert_profit(
                    update.bot_id,
                    bot.get("bot_name", "Unknown"),
                    update.daily_pnl_percent or 0,
                    update.total_pnl_percent or 0,
                    update.daily_pnl or 0
                )
        except Exception as alert_err:
            # Don't fail heartbeat if alerts fail
            print(f"Alert error: {alert_err}")
        
        # Broadcast update to all connected clients
        await manager.broadcast({
            "type": "BOT_STATUS_UPDATE",
            "bot_id": update.bot_id,
            "status": new_status,
            "current_balance": update.current_balance,
            "daily_pnl": update.daily_pnl,
            "current_drawdown": update.current_drawdown,
            "trades_today": update.trades_today,
            "auto_stopped": auto_stop,
            "stop_reason": stop_reason,
            "timestamp": now.isoformat()
        })
        
        return {
            "success": True,
            "bot_id": update.bot_id,
            "status": new_status,
            "auto_stopped": auto_stop,
            "stop_reason": stop_reason,
            "uptime_seconds": uptime,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update bot status: {str(e)}")


@router.get("/status")
async def get_all_bots_status():
    """
    Get status of all registered bots
    """
    try:
        now = datetime.now(timezone.utc)
        
        cursor = bots_collection.find({}, {"_id": 0})
        bots = await cursor.to_list(length=100)
        
        # Enrich with calculated fields
        result = []
        for bot in bots:
            risk_config = bot.get("risk_config", {})
            start_time = datetime.fromisoformat(bot.get("start_time", now.isoformat()).replace("Z", "+00:00"))
            uptime = int((now - start_time).total_seconds())
            
            result.append({
                "bot_id": bot.get("bot_id"),
                "bot_name": bot.get("bot_name"),
                "symbol": bot.get("symbol"),
                "timeframe": bot.get("timeframe"),
                "status": bot.get("status"),
                "mode": bot.get("mode"),
                "initial_balance": bot.get("initial_balance"),
                "current_balance": bot.get("current_balance"),
                "daily_pnl": bot.get("daily_pnl", 0),
                "daily_pnl_percent": bot.get("daily_pnl_percent", 0),
                "total_pnl": bot.get("total_pnl", 0),
                "total_pnl_percent": bot.get("total_pnl_percent", 0),
                "current_drawdown": bot.get("current_drawdown", 0),
                "max_drawdown_limit": risk_config.get("maxTotalDrawdown", 10),
                "max_drawdown_reached": bot.get("max_drawdown_reached", 0),
                "trades_today": bot.get("trades_today", 0),
                "max_trades_per_day": risk_config.get("maxTradesPerDay", 5),
                "open_trades": bot.get("open_trades", 0),
                "win_rate": bot.get("win_rate", 0),
                "stop_reason": bot.get("stop_reason"),
                "last_trade_time": bot.get("last_trade_time"),
                "last_heartbeat": bot.get("last_heartbeat"),
                "uptime_seconds": uptime,
            })
        
        # Calculate aggregates
        total_balance = sum(b["current_balance"] for b in result)
        total_daily_pnl = sum(b["daily_pnl"] for b in result)
        avg_drawdown = sum(b["current_drawdown"] for b in result) / len(result) if result else 0
        running = sum(1 for b in result if b["status"] == "RUNNING")
        warning = sum(1 for b in result if b["status"] == "WARNING")
        stopped = sum(1 for b in result if b["status"] in ["STOPPED", "ERROR"])
        
        return {
            "success": True,
            "timestamp": now.isoformat(),
            "bots": result,
            "aggregate": {
                "total_bots": len(result),
                "running": running,
                "warning": warning,
                "stopped": stopped,
                "total_balance": total_balance,
                "total_daily_pnl": total_daily_pnl,
                "avg_drawdown": round(avg_drawdown, 2),
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bot status: {str(e)}")


@router.get("/status/{bot_id}")
async def get_bot_status(bot_id: str):
    """
    Get status of a specific bot
    """
    try:
        bot = await bots_collection.find_one({"bot_id": bot_id}, {"_id": 0})
        if not bot:
            raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
        
        now = datetime.now(timezone.utc)
        risk_config = bot.get("risk_config", {})
        start_time = datetime.fromisoformat(bot.get("start_time", now.isoformat()).replace("Z", "+00:00"))
        uptime = int((now - start_time).total_seconds())
        
        return {
            "success": True,
            "bot": {
                "bot_id": bot.get("bot_id"),
                "bot_name": bot.get("bot_name"),
                "symbol": bot.get("symbol"),
                "timeframe": bot.get("timeframe"),
                "status": bot.get("status"),
                "mode": bot.get("mode"),
                "initial_balance": bot.get("initial_balance"),
                "current_balance": bot.get("current_balance"),
                "daily_pnl": bot.get("daily_pnl", 0),
                "daily_pnl_percent": bot.get("daily_pnl_percent", 0),
                "total_pnl": bot.get("total_pnl", 0),
                "total_pnl_percent": bot.get("total_pnl_percent", 0),
                "current_drawdown": bot.get("current_drawdown", 0),
                "max_drawdown_limit": risk_config.get("maxTotalDrawdown", 10),
                "max_drawdown_reached": bot.get("max_drawdown_reached", 0),
                "trades_today": bot.get("trades_today", 0),
                "max_trades_per_day": risk_config.get("maxTradesPerDay", 5),
                "open_trades": bot.get("open_trades", 0),
                "win_rate": bot.get("win_rate", 0),
                "stop_reason": bot.get("stop_reason"),
                "last_trade_time": bot.get("last_trade_time"),
                "last_heartbeat": bot.get("last_heartbeat"),
                "uptime_seconds": uptime,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bot status: {str(e)}")


@router.post("/control/{bot_id}")
async def control_bot(bot_id: str, action: Literal["start", "pause", "stop"]):
    """
    Control a bot (start/pause/stop)
    """
    try:
        now = datetime.now(timezone.utc)
        
        bot = await bots_collection.find_one({"bot_id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
        
        status_map = {
            "start": "RUNNING",
            "pause": "PAUSED",
            "stop": "STOPPED"
        }
        
        new_status = status_map[action]
        stop_reason = f"Manually {action}ed by user" if action != "start" else None
        
        await bots_collection.update_one(
            {"bot_id": bot_id},
            {"$set": {
                "status": new_status,
                "stop_reason": stop_reason,
                "updated_at": now.isoformat(),
            }}
        )
        
        # Broadcast control action
        await manager.broadcast({
            "type": "BOT_CONTROL",
            "bot_id": bot_id,
            "action": action,
            "new_status": new_status,
            "timestamp": now.isoformat()
        })
        
        return {
            "success": True,
            "bot_id": bot_id,
            "action": action,
            "new_status": new_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to control bot: {str(e)}")


@router.get("/history/{bot_id}")
async def get_bot_history(bot_id: str, hours: int = 24):
    """
    Get historical data for a bot (for charts)
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        cursor = bot_history_collection.find(
            {"bot_id": bot_id, "timestamp": {"$gte": cutoff.isoformat()}},
            {"_id": 0}
        ).sort("timestamp", 1)
        
        history = await cursor.to_list(length=10000)
        
        return {
            "success": True,
            "bot_id": bot_id,
            "period_hours": hours,
            "data_points": len(history),
            "history": history
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bot history: {str(e)}")


@router.delete("/{bot_id}")
async def delete_bot(bot_id: str):
    """
    Delete a bot registration
    """
    try:
        result = await bots_collection.delete_one({"bot_id": bot_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
        
        # Also delete history
        await bot_history_collection.delete_many({"bot_id": bot_id})
        
        return {"success": True, "message": f"Bot {bot_id} deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete bot: {str(e)}")
