"""
Trade Logger for Paper Trading
Logs trades to MongoDB and JSON backup
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from motor.motor_asyncio import AsyncIOMotorClient
import os

logger = logging.getLogger(__name__)

# MongoDB configuration
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')

# JSON backup file
BACKUP_FILE = Path("/app/backend/paper_trading/trades_backup.json")


class TradeLogger:
    """
    Logs trades to MongoDB and JSON file
    """
    
    def __init__(self):
        """Initialize trade logger"""
        self.mongo_client = None
        self.db = None
        self.backup_trades = []
        
        # Ensure backup directory exists
        BACKUP_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing backup if available
        self._load_backup()
        
        logger.info("Trade logger initialized")
    
    def _load_backup(self):
        """Load existing trades from backup file"""
        if BACKUP_FILE.exists():
            try:
                with open(BACKUP_FILE, 'r') as f:
                    self.backup_trades = json.load(f)
                logger.info(f"Loaded {len(self.backup_trades)} trades from backup")
            except Exception as e:
                logger.error(f"Failed to load backup: {e}")
                self.backup_trades = []
    
    def _connect_mongo(self):
        """Connect to MongoDB"""
        if not self.mongo_client:
            self.mongo_client = AsyncIOMotorClient(MONGO_URL)
            self.db = self.mongo_client[DB_NAME]
            logger.info("Connected to MongoDB")
    
    async def log_trade(self, trade_data: Dict):
        """
        Log trade to MongoDB and JSON backup
        
        Args:
            trade_data: dict with trade information
                - timestamp
                - symbol
                - signal
                - entry_price
                - exit_price
                - position_size
                - pnl
                - capital_after
        """
        # Add timestamp if not present
        if 'timestamp' not in trade_data:
            trade_data['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        # Log to MongoDB
        try:
            self._connect_mongo()
            await self.db.paper_trades.insert_one(trade_data)
            logger.info(f"Trade logged to MongoDB: {trade_data['symbol']} PnL=${trade_data['pnl']:+.2f}")
        except Exception as e:
            logger.error(f"Failed to log trade to MongoDB: {e}")
        
        # Backup to JSON
        try:
            self.backup_trades.append(trade_data)
            with open(BACKUP_FILE, 'w') as f:
                json.dump(self.backup_trades, f, indent=2)
            logger.debug("Trade backed up to JSON")
        except Exception as e:
            logger.error(f"Failed to backup trade to JSON: {e}")
    
    def log_trade_sync(self, trade_data: Dict):
        """
        Synchronous version of log_trade for use in non-async contexts
        
        Args:
            trade_data: dict with trade information
        """
        # Add timestamp if not present
        if 'timestamp' not in trade_data:
            trade_data['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        # Backup to JSON (synchronous)
        try:
            self.backup_trades.append(trade_data)
            with open(BACKUP_FILE, 'w') as f:
                json.dump(self.backup_trades, f, indent=2)
            logger.info(f"Trade logged: {trade_data['symbol']} PnL=${trade_data['pnl']:+.2f}")
        except Exception as e:
            logger.error(f"Failed to backup trade to JSON: {e}")
    
    async def get_all_trades(self) -> List[Dict]:
        """
        Get all trades from MongoDB
        
        Returns:
            List of trade dictionaries
        """
        try:
            self._connect_mongo()
            trades = await self.db.paper_trades.find({}, {"_id": 0}).to_list(1000)
            return trades
        except Exception as e:
            logger.error(f"Failed to fetch trades from MongoDB: {e}")
            return self.backup_trades
    
    def get_trades_sync(self) -> List[Dict]:
        """
        Get all trades from backup file (synchronous)
        
        Returns:
            List of trade dictionaries
        """
        return self.backup_trades.copy()
    
    async def get_trade_stats(self) -> Dict:
        """
        Get trade statistics
        
        Returns:
            dict with trade statistics
        """
        trades = await self.get_all_trades()
        
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_pnl': 0.0,
                'win_rate': 0.0
            }
        
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        losing_trades = sum(1 for t in trades if t.get('pnl', 0) < 0)
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'total_pnl': total_pnl,
            'win_rate': win_rate
        }
    
    def close(self):
        """Close MongoDB connection"""
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("MongoDB connection closed")
