"""
Telegram Alert Service for Trading Bot Notifications
Handles risk alerts, profit alerts, and bot status notifications
"""
import os
import httpx
from datetime import datetime, timezone
from typing import Optional, Literal, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# MongoDB client (lazy initialization)
_client = None
_db = None

def get_db():
    global _client, _db
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URL)
        _db = _client[DB_NAME]
    return _db


# ========== MODELS ==========

class AlertConfig(BaseModel):
    """User alert configuration"""
    enabled: bool = True
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    # Thresholds
    drawdown_warning_percent: float = Field(default=80.0, description="DD % of limit to trigger warning")
    daily_profit_target_percent: float = Field(default=2.0, description="Daily profit % to celebrate")
    milestone_profits: List[float] = Field(default=[2.0, 5.0, 10.0], description="Profit milestones %")
    # Alert types
    alert_on_drawdown_warning: bool = True
    alert_on_drawdown_breach: bool = True
    alert_on_profit_target: bool = True
    alert_on_milestone: bool = True
    alert_on_bot_start: bool = True
    alert_on_bot_stop: bool = True
    alert_on_trade: bool = False  # Can be noisy


class AlertConfigUpdate(BaseModel):
    """Update alert configuration"""
    enabled: Optional[bool] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    drawdown_warning_percent: Optional[float] = None
    daily_profit_target_percent: Optional[float] = None
    milestone_profits: Optional[List[float]] = None
    alert_on_drawdown_warning: Optional[bool] = None
    alert_on_drawdown_breach: Optional[bool] = None
    alert_on_profit_target: Optional[bool] = None
    alert_on_milestone: Optional[bool] = None
    alert_on_bot_start: Optional[bool] = None
    alert_on_bot_stop: Optional[bool] = None
    alert_on_trade: Optional[bool] = None


class SendAlertRequest(BaseModel):
    """Manual alert send request"""
    alert_type: Literal["risk", "profit", "bot_event", "custom"]
    title: str
    message: str
    bot_id: Optional[str] = None
    bot_name: Optional[str] = None
    severity: Literal["info", "warning", "critical"] = "info"


class TelegramTestRequest(BaseModel):
    """Test Telegram configuration"""
    bot_token: str
    chat_id: str


# ========== TELEGRAM HELPER ==========

async def send_telegram_message(bot_token: str, chat_id: str, message: str) -> dict:
    """Send a message via Telegram Bot API"""
    if not bot_token or not chat_id:
        return {"success": False, "error": "Missing bot_token or chat_id"}
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            result = response.json()
            
            if result.get("ok"):
                return {"success": True, "message_id": result["result"]["message_id"]}
            else:
                return {"success": False, "error": result.get("description", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========== ALERT FORMATTERS ==========

def format_risk_alert(bot_name: str, drawdown: float, status: str, dd_limit: float) -> str:
    """Format a risk/drawdown alert message"""
    emoji = "🚨" if status == "STOPPED" else "⚠️"
    status_text = "BREACHED - BOT STOPPED" if status == "STOPPED" else "WARNING"
    
    return f"""
{emoji} <b>RISK ALERT</b> {emoji}

<b>Bot:</b> {bot_name}
<b>Drawdown:</b> {drawdown:.2f}% / {dd_limit:.1f}%
<b>Status:</b> {status_text}

{'🛑 Trading halted to protect capital!' if status == "STOPPED" else '⚡ Approaching limit - monitor closely!'}

<i>Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>
"""


def format_profit_alert(bot_name: str, profit_type: str, profit_pct: float, profit_usd: float) -> str:
    """Format a profit milestone alert"""
    if profit_type == "daily_target":
        emoji = "🎯"
        title = "DAILY TARGET REACHED"
    elif profit_type == "milestone":
        emoji = "🏆"
        title = f"MILESTONE: +{profit_pct:.1f}%"
    else:
        emoji = "💰"
        title = "PROFIT UPDATE"
    
    return f"""
{emoji} <b>{title}</b> {emoji}

<b>Bot:</b> {bot_name}
<b>Profit:</b> +{profit_pct:.2f}% (${profit_usd:,.2f})

🔥 Keep the momentum going!

<i>Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>
"""


def format_bot_event_alert(bot_name: str, event: str, details: str = "") -> str:
    """Format a bot event alert"""
    events = {
        "started": ("🟢", "BOT STARTED"),
        "stopped": ("🔴", "BOT STOPPED"),
        "error": ("❌", "BOT ERROR"),
        "warning": ("⚠️", "BOT WARNING"),
    }
    
    emoji, title = events.get(event, ("📌", event.upper()))
    
    msg = f"""
{emoji} <b>{title}</b>

<b>Bot:</b> {bot_name}
"""
    if details:
        msg += f"<b>Details:</b> {details}\n"
    
    msg += f"\n<i>Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>"
    return msg


def format_trade_alert(bot_name: str, direction: str, symbol: str, result: str, pnl: float) -> str:
    """Format a trade notification"""
    if result == "OPEN":
        emoji = "📈" if direction == "BUY" else "📉"
        title = f"NEW {direction}"
    elif result == "WIN":
        emoji = "✅"
        title = "TRADE WIN"
    else:
        emoji = "❌"
        title = "TRADE LOSS"
    
    return f"""
{emoji} <b>{title}</b>

<b>Bot:</b> {bot_name}
<b>Symbol:</b> {symbol}
<b>Direction:</b> {direction}
{f'<b>P&L:</b> ${pnl:+,.2f}' if result != "OPEN" else ''}

<i>Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>
"""


# ========== CORE ALERT FUNCTION ==========

async def trigger_alert(
    alert_type: str,
    bot_id: str = None,
    bot_name: str = None,
    **kwargs
) -> dict:
    """
    Core function to trigger alerts based on configuration.
    Called by bot_status and trade_logging modules.
    """
    db = get_db()
    
    # Get alert configuration
    config_doc = await db.alert_config.find_one({"_id": "global"})
    if not config_doc:
        return {"success": False, "reason": "No alert configuration"}
    
    config = AlertConfig(**{k: v for k, v in config_doc.items() if k != "_id"})
    
    if not config.enabled:
        return {"success": False, "reason": "Alerts disabled"}
    
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return {"success": False, "reason": "Telegram not configured"}
    
    # Check if this alert type is enabled
    alert_checks = {
        "drawdown_warning": config.alert_on_drawdown_warning,
        "drawdown_breach": config.alert_on_drawdown_breach,
        "profit_target": config.alert_on_profit_target,
        "milestone": config.alert_on_milestone,
        "bot_start": config.alert_on_bot_start,
        "bot_stop": config.alert_on_bot_stop,
        "trade": config.alert_on_trade,
    }
    
    if not alert_checks.get(alert_type, True):
        return {"success": False, "reason": f"Alert type {alert_type} disabled"}
    
    # Format message based on alert type
    message = ""
    if alert_type == "drawdown_warning":
        message = format_risk_alert(
            bot_name or "Unknown",
            kwargs.get("drawdown", 0),
            "WARNING",
            kwargs.get("dd_limit", 10)
        )
    elif alert_type == "drawdown_breach":
        message = format_risk_alert(
            bot_name or "Unknown",
            kwargs.get("drawdown", 0),
            "STOPPED",
            kwargs.get("dd_limit", 10)
        )
    elif alert_type in ["profit_target", "milestone"]:
        message = format_profit_alert(
            bot_name or "Unknown",
            alert_type,
            kwargs.get("profit_pct", 0),
            kwargs.get("profit_usd", 0)
        )
    elif alert_type in ["bot_start", "bot_stop"]:
        event = "started" if alert_type == "bot_start" else "stopped"
        message = format_bot_event_alert(
            bot_name or "Unknown",
            event,
            kwargs.get("details", "")
        )
    elif alert_type == "trade":
        message = format_trade_alert(
            bot_name or "Unknown",
            kwargs.get("direction", "BUY"),
            kwargs.get("symbol", "UNKNOWN"),
            kwargs.get("result", "OPEN"),
            kwargs.get("pnl", 0)
        )
    else:
        message = f"📌 <b>Alert</b>\n\nBot: {bot_name}\nType: {alert_type}\n\n{kwargs.get('message', '')}"
    
    # Send the alert
    result = await send_telegram_message(
        config.telegram_bot_token,
        config.telegram_chat_id,
        message
    )
    
    # Log the alert
    await db.alert_log.insert_one({
        "alert_type": alert_type,
        "bot_id": bot_id,
        "bot_name": bot_name,
        "message": message,
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    
    return result


# ========== API ENDPOINTS ==========

@router.get("/config")
async def get_alert_config():
    """Get current alert configuration"""
    db = get_db()
    config = await db.alert_config.find_one({"_id": "global"})
    
    if not config:
        # Return default config
        default = AlertConfig()
        return {"success": True, "config": default.model_dump()}
    
    # Mask the bot token for security
    config_dict = {k: v for k, v in config.items() if k != "_id"}
    if config_dict.get("telegram_bot_token"):
        token = config_dict["telegram_bot_token"]
        config_dict["telegram_bot_token_masked"] = f"{token[:10]}...{token[-5:]}" if len(token) > 15 else "***"
    
    return {"success": True, "config": config_dict}


@router.post("/config")
async def update_alert_config(update: AlertConfigUpdate):
    """Update alert configuration"""
    db = get_db()
    
    # Get existing config or create default
    existing = await db.alert_config.find_one({"_id": "global"})
    if existing:
        config_dict = {k: v for k, v in existing.items() if k != "_id"}
    else:
        config_dict = AlertConfig().model_dump()
    
    # Update only provided fields
    update_dict = update.model_dump(exclude_unset=True)
    config_dict.update(update_dict)
    
    # Save to database
    await db.alert_config.update_one(
        {"_id": "global"},
        {"$set": config_dict},
        upsert=True
    )
    
    return {"success": True, "message": "Alert configuration updated"}


@router.post("/test-telegram")
async def test_telegram_connection(request: TelegramTestRequest):
    """Test Telegram bot configuration"""
    db = get_db()
    
    bot_token = request.bot_token
    chat_id = request.chat_id
    
    # If "USE_SAVED" is passed, get the saved token
    if bot_token == "USE_SAVED":
        config = await db.alert_config.find_one({"_id": "global"})
        if not config or not config.get("telegram_bot_token"):
            raise HTTPException(status_code=400, detail="No saved Telegram token found")
        bot_token = config["telegram_bot_token"]
    
    test_message = """
🧪 <b>TEST ALERT</b>

✅ Telegram integration working!
Your trading alerts will appear here.

<i>Prop Firm Bot Factory</i>
"""
    
    result = await send_telegram_message(
        bot_token,
        chat_id,
        test_message
    )
    
    if result["success"]:
        return {"success": True, "message": "Test message sent successfully!"}
    else:
        raise HTTPException(status_code=400, detail=f"Failed to send: {result['error']}")


@router.post("/send")
async def send_manual_alert(request: SendAlertRequest):
    """Send a manual/custom alert"""
    db = get_db()
    config = await db.alert_config.find_one({"_id": "global"})
    
    if not config or not config.get("telegram_bot_token") or not config.get("telegram_chat_id"):
        raise HTTPException(status_code=400, detail="Telegram not configured")
    
    # Format based on alert type
    severity_emoji = {
        "info": "ℹ️",
        "warning": "⚠️",
        "critical": "🚨"
    }
    
    emoji = severity_emoji.get(request.severity, "📌")
    message = f"""
{emoji} <b>{request.title}</b>

{f'<b>Bot:</b> {request.bot_name}' if request.bot_name else ''}
{request.message}

<i>Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>
"""
    
    result = await send_telegram_message(
        config["telegram_bot_token"],
        config["telegram_chat_id"],
        message
    )
    
    if result["success"]:
        return {"success": True, "message": "Alert sent"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed: {result['error']}")


@router.get("/history")
async def get_alert_history(limit: int = 50):
    """Get recent alert history"""
    db = get_db()
    
    cursor = db.alert_log.find().sort("timestamp", -1).limit(limit)
    alerts = await cursor.to_list(length=limit)
    
    # Convert ObjectId to string
    for alert in alerts:
        alert["id"] = str(alert.pop("_id"))
    
    return {"success": True, "alerts": alerts}


# ========== INTEGRATION HOOKS ==========
# These functions are called by bot_status and trade_logging modules

async def check_and_alert_drawdown(bot_id: str, bot_name: str, current_dd: float, dd_limit: float):
    """Check drawdown and trigger alerts if needed"""
    db = get_db()
    config_doc = await db.alert_config.find_one({"_id": "global"})
    
    if not config_doc:
        return
    
    warning_threshold = config_doc.get("drawdown_warning_percent", 80.0)
    
    # Calculate what % of limit we've reached
    dd_percent_of_limit = (current_dd / dd_limit) * 100 if dd_limit > 0 else 0
    
    if dd_percent_of_limit >= 100:
        # DD breach - bot should be stopped
        await trigger_alert(
            "drawdown_breach",
            bot_id=bot_id,
            bot_name=bot_name,
            drawdown=current_dd,
            dd_limit=dd_limit
        )
    elif dd_percent_of_limit >= warning_threshold:
        # Warning threshold reached
        # Check if we already sent a warning today
        today = datetime.now(timezone.utc).date().isoformat()
        existing = await db.alert_log.find_one({
            "alert_type": "drawdown_warning",
            "bot_id": bot_id,
            "timestamp": {"$regex": f"^{today}"}
        })
        
        if not existing:
            await trigger_alert(
                "drawdown_warning",
                bot_id=bot_id,
                bot_name=bot_name,
                drawdown=current_dd,
                dd_limit=dd_limit
            )


async def check_and_alert_profit(bot_id: str, bot_name: str, daily_pnl_pct: float, total_pnl_pct: float, pnl_usd: float):
    """Check profit milestones and trigger alerts"""
    db = get_db()
    config_doc = await db.alert_config.find_one({"_id": "global"})
    
    if not config_doc:
        return
    
    today = datetime.now(timezone.utc).date().isoformat()
    
    # Check daily target
    daily_target = config_doc.get("daily_profit_target_percent", 2.0)
    if daily_pnl_pct >= daily_target:
        existing = await db.alert_log.find_one({
            "alert_type": "profit_target",
            "bot_id": bot_id,
            "timestamp": {"$regex": f"^{today}"}
        })
        if not existing:
            await trigger_alert(
                "profit_target",
                bot_id=bot_id,
                bot_name=bot_name,
                profit_pct=daily_pnl_pct,
                profit_usd=pnl_usd
            )
    
    # Check milestones
    milestones = config_doc.get("milestone_profits", [2.0, 5.0, 10.0])
    for milestone in milestones:
        if total_pnl_pct >= milestone:
            existing = await db.alert_log.find_one({
                "alert_type": "milestone",
                "bot_id": bot_id,
                "kwargs.profit_pct": {"$gte": milestone}
            })
            if not existing:
                await trigger_alert(
                    "milestone",
                    bot_id=bot_id,
                    bot_name=bot_name,
                    profit_pct=total_pnl_pct,
                    profit_usd=pnl_usd
                )
                break  # Only alert highest milestone


async def alert_bot_event(bot_id: str, bot_name: str, event: str, details: str = ""):
    """Alert on bot start/stop events"""
    alert_type = f"bot_{event}" if event in ["start", "stop"] else event
    await trigger_alert(
        alert_type,
        bot_id=bot_id,
        bot_name=bot_name,
        details=details
    )


async def alert_trade(bot_id: str, bot_name: str, direction: str, symbol: str, result: str, pnl: float = 0):
    """Alert on trade events (if enabled)"""
    await trigger_alert(
        "trade",
        bot_id=bot_id,
        bot_name=bot_name,
        direction=direction,
        symbol=symbol,
        result=result,
        pnl=pnl
    )
