"""
Seed Demo Data Script
Creates sample bots and trades for testing the execution layer
"""
import asyncio
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import os
import random

# MongoDB connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

# Demo Bot Configurations
DEMO_BOTS = [
    {
        "bot_id": "bot_eurusd_ema_001",
        "bot_name": "EMA Crossover EURUSD",
        "symbol": "EURUSD",
        "timeframe": "H4",
        "strategy_type": "EMA Crossover",
        "initial_balance": 100000,
        "risk_config": {
            "maxDailyDrawdown": 5,
            "maxTotalDrawdown": 10,
            "maxTradesPerDay": 5,
            "riskPerTrade": 1.0
        },
        "mode": "forward_test"
    },
    {
        "bot_id": "bot_gbpusd_scalp_002",
        "bot_name": "Scalper GBPUSD",
        "symbol": "GBPUSD",
        "timeframe": "M15",
        "strategy_type": "RSI Scalping",
        "initial_balance": 50000,
        "risk_config": {
            "maxDailyDrawdown": 3,
            "maxTotalDrawdown": 6,
            "maxTradesPerDay": 10,
            "riskPerTrade": 0.5
        },
        "mode": "forward_test"
    },
    {
        "bot_id": "bot_usdjpy_swing_003",
        "bot_name": "Swing Trader USDJPY",
        "symbol": "USDJPY",
        "timeframe": "D1",
        "strategy_type": "Trend Following",
        "initial_balance": 200000,
        "risk_config": {
            "maxDailyDrawdown": 4,
            "maxTotalDrawdown": 8,
            "maxTradesPerDay": 3,
            "riskPerTrade": 2.0
        },
        "mode": "live"
    }
]

# Price ranges for realistic data
PRICE_RANGES = {
    "EURUSD": {"base": 1.0850, "pip_size": 0.0001, "spread": 1.2},
    "GBPUSD": {"base": 1.2650, "pip_size": 0.0001, "spread": 1.5},
    "USDJPY": {"base": 149.50, "pip_size": 0.01, "spread": 1.0},
}

# Trade reasons
ENTRY_REASONS = [
    "EMA crossover signal",
    "RSI oversold bounce",
    "Breakout above resistance",
    "Support level touch",
    "ADX trend confirmation",
    "BB lower band touch",
    "Momentum divergence",
    "Price action signal"
]

CLOSE_REASONS = [
    "Take profit hit",
    "Stop loss hit",
    "EMA cross reversal",
    "End of session",
    "Manual close",
    "Trailing stop hit"
]


async def seed_bots(db):
    """Insert demo bots"""
    now = datetime.now(timezone.utc)
    bots_collection = db["bots"]
    
    for bot_config in DEMO_BOTS:
        # Check if bot already exists
        existing = await bots_collection.find_one({"bot_id": bot_config["bot_id"]})
        if existing:
            print(f"Bot {bot_config['bot_id']} already exists, skipping...")
            continue
        
        # Generate performance data
        pnl_multiplier = random.uniform(-0.02, 0.05)  # -2% to +5%
        daily_pnl = bot_config["initial_balance"] * random.uniform(-0.01, 0.02)
        current_drawdown = random.uniform(0.5, 3.5)
        
        bot_doc = {
            "bot_id": bot_config["bot_id"],
            "bot_name": bot_config["bot_name"],
            "symbol": bot_config["symbol"],
            "timeframe": bot_config["timeframe"],
            "strategy_type": bot_config["strategy_type"],
            "initial_balance": bot_config["initial_balance"],
            "current_balance": bot_config["initial_balance"] * (1 + pnl_multiplier),
            "daily_pnl": round(daily_pnl, 2),
            "daily_pnl_percent": round(daily_pnl / bot_config["initial_balance"] * 100, 2),
            "total_pnl": round(bot_config["initial_balance"] * pnl_multiplier, 2),
            "total_pnl_percent": round(pnl_multiplier * 100, 2),
            "current_drawdown": round(current_drawdown, 2),
            "max_drawdown_reached": round(current_drawdown + random.uniform(0, 1), 2),
            "trades_today": random.randint(1, bot_config["risk_config"]["maxTradesPerDay"]),
            "open_trades": random.randint(0, 2),
            "win_rate": round(random.uniform(45, 65), 1),
            "risk_config": bot_config["risk_config"],
            "mode": bot_config["mode"],
            "status": random.choice(["RUNNING", "RUNNING", "RUNNING", "WARNING"]),
            "stop_reason": None,
            "last_trade_time": (now - timedelta(minutes=random.randint(5, 120))).isoformat(),
            "last_heartbeat": now.isoformat(),
            "start_time": (now - timedelta(days=random.randint(1, 7))).isoformat(),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        
        await bots_collection.insert_one(bot_doc)
        print(f"Created bot: {bot_config['bot_name']}")


async def seed_trades(db):
    """Generate demo trades for each bot"""
    now = datetime.now(timezone.utc)
    trades_collection = db["trades"]
    
    for bot_config in DEMO_BOTS:
        symbol = bot_config["symbol"]
        price_info = PRICE_RANGES[symbol]
        
        # Generate 10-15 trades per bot over the last 7 days
        num_trades = random.randint(10, 15)
        
        for i in range(num_trades):
            # Random time in last 7 days
            days_ago = random.randint(0, 6)
            hours_ago = random.randint(0, 23)
            entry_time = now - timedelta(days=days_ago, hours=hours_ago)
            
            # Trade duration: 15 mins to 8 hours
            duration_mins = random.randint(15, 480)
            exit_time = entry_time + timedelta(minutes=duration_mins)
            
            # Don't have exit times in the future
            if exit_time > now:
                exit_time = now - timedelta(minutes=random.randint(5, 60))
            
            direction = random.choice(["BUY", "SELL"])
            
            # Entry price with slight variation
            entry_price = price_info["base"] + random.uniform(-0.01, 0.01) * (10 if symbol == "USDJPY" else 1)
            
            # Lot size based on risk
            lot_size = round(random.uniform(0.1, 1.5), 2)
            
            # Calculate SL and TP
            sl_pips = random.randint(15, 40)
            tp_pips = random.randint(20, 60)
            
            if direction == "BUY":
                stop_loss = entry_price - sl_pips * price_info["pip_size"]
                take_profit = entry_price + tp_pips * price_info["pip_size"]
            else:
                stop_loss = entry_price + sl_pips * price_info["pip_size"]
                take_profit = entry_price - tp_pips * price_info["pip_size"]
            
            # Determine outcome (60% win rate)
            is_win = random.random() < 0.6
            
            if is_win:
                # Hit TP or partial profit
                pips_result = random.randint(10, tp_pips)
                result = "WIN"
                close_reason = "Take profit hit" if random.random() < 0.7 else "Manual close"
            else:
                # Hit SL or partial loss
                pips_result = -random.randint(10, sl_pips)
                result = "LOSS"
                close_reason = "Stop loss hit" if random.random() < 0.8 else "Manual close"
            
            # Calculate exit price
            if direction == "BUY":
                exit_price = entry_price + pips_result * price_info["pip_size"]
            else:
                exit_price = entry_price - pips_result * price_info["pip_size"]
            
            # Calculate P&L (simplified)
            pip_value = 10 if symbol != "USDJPY" else 100 / entry_price
            pnl = pips_result * pip_value * lot_size
            
            trade_doc = {
                "bot_id": bot_config["bot_id"],
                "bot_name": bot_config["bot_name"],
                "symbol": symbol,
                "direction": direction,
                "lot_size": lot_size,
                "entry_price": round(entry_price, 5 if symbol != "USDJPY" else 3),
                "exit_price": round(exit_price, 5 if symbol != "USDJPY" else 3),
                "stop_loss": round(stop_loss, 5 if symbol != "USDJPY" else 3),
                "take_profit": round(take_profit, 5 if symbol != "USDJPY" else 3),
                "pnl": round(pnl, 2),
                "pips": round(pips_result, 1),
                "result": result,
                "reason": random.choice(ENTRY_REASONS),
                "close_reason": close_reason,
                "mode": bot_config["mode"],
                "timestamp_entry": entry_time.isoformat(),
                "timestamp_exit": exit_time.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            
            await trades_collection.insert_one(trade_doc)
        
        print(f"Created {num_trades} trades for {bot_config['bot_name']}")


async def seed_bot_history(db):
    """Generate historical data points for charts"""
    now = datetime.now(timezone.utc)
    history_collection = db["bot_history"]
    
    for bot_config in DEMO_BOTS:
        # Generate 24 hours of history (every 15 mins = 96 points)
        for i in range(96):
            timestamp = now - timedelta(minutes=15 * i)
            
            # Simulate balance fluctuation
            balance_change = random.uniform(-200, 300)
            base_balance = bot_config["initial_balance"]
            current_balance = base_balance + balance_change * (96 - i) / 96
            
            history_doc = {
                "bot_id": bot_config["bot_id"],
                "timestamp": timestamp.isoformat(),
                "balance": round(current_balance, 2),
                "daily_pnl": round(random.uniform(-500, 800), 2),
                "drawdown": round(random.uniform(0, 4), 2),
                "trades_today": random.randint(0, 5),
                "status": "RUNNING",
            }
            
            await history_collection.insert_one(history_doc)
        
        print(f"Created history for {bot_config['bot_name']}")


async def clear_existing_data(db):
    """Clear existing demo data"""
    await db["bots"].delete_many({})
    await db["trades"].delete_many({})
    await db["bot_history"].delete_many({})
    print("Cleared existing data")


async def main():
    """Main seed function"""
    print("=" * 50)
    print("SEEDING DEMO DATA")
    print("=" * 50)
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Clear existing data first (optional - comment out to append)
    await clear_existing_data(db)
    
    # Seed data
    await seed_bots(db)
    await seed_trades(db)
    await seed_bot_history(db)
    
    # Verify counts
    bots_count = await db["bots"].count_documents({})
    trades_count = await db["trades"].count_documents({})
    history_count = await db["bot_history"].count_documents({})
    
    print("=" * 50)
    print(f"SEED COMPLETE")
    print(f"Bots: {bots_count}")
    print(f"Trades: {trades_count}")
    print(f"History Points: {history_count}")
    print("=" * 50)
    
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
