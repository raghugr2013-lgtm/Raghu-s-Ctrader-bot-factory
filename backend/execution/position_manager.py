"""
Position Manager

Tracks open positions, calculates PnL, syncs with broker, and manages position limits.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from execution.broker_interface import (
    BrokerInterface,
    Position,
    PositionType,
)

logger = logging.getLogger(__name__)


class PositionManager:
    """
    Manages trading positions.
    
    Responsibilities:
    - Track all open positions
    - Update position prices
    - Calculate unrealized/realized PnL
    - Sync with broker positions
    - Enforce position limits
    """
    
    def __init__(self, broker: BrokerInterface, max_positions: int = 10):
        self.broker = broker
        self.max_positions = max_positions
        
        # Position tracking (local state)
        self.positions: Dict[str, Position] = {}
        
        # PnL tracking
        self.total_realized_pnl: float = 0.0
        self.total_unrealized_pnl: float = 0.0
        
        logger.info(f"Position Manager initialized (max_positions={max_positions})")
    
    async def sync_positions(self):
        """
        Synchronize local positions with broker.
        
        Fetches positions from broker and updates local state.
        """
        try:
            broker_positions = await self.broker.get_positions()
            
            # Clear local positions
            self.positions.clear()
            
            # Update with broker positions
            for pos in broker_positions:
                self.positions[pos.symbol] = pos
            
            # Recalculate PnL
            self._recalculate_pnl()
            
            logger.info(f"✅ Positions synced: {len(self.positions)} open")
            
        except Exception as e:
            logger.error(f"❌ Failed to sync positions: {e}")
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol"""
        return self.positions.get(symbol)
    
    def has_position(self, symbol: str) -> bool:
        """Check if we have an open position for symbol"""
        return symbol in self.positions
    
    def get_all_positions(self) -> List[Position]:
        """Get all open positions"""
        return list(self.positions.values())
    
    def get_position_count(self) -> int:
        """Get count of open positions"""
        return len(self.positions)
    
    def can_open_position(self) -> bool:
        """Check if we can open a new position (not at limit)"""
        return len(self.positions) < self.max_positions
    
    async def update_position_price(self, symbol: str, current_price: float):
        """Update position with current market price"""
        if symbol in self.positions:
            position = self.positions[symbol]
            position.update_price(current_price)
            
            # Recalculate total unrealized PnL
            self._recalculate_pnl()
    
    async def update_all_prices(self):
        """Update all positions with current market prices"""
        for symbol in self.positions.keys():
            try:
                current_price = await self.broker.get_market_price(symbol)
                await self.update_position_price(symbol, current_price)
            except Exception as e:
                logger.error(f"❌ Failed to update price for {symbol}: {e}")
    
    async def close_position(self, symbol: str) -> bool:
        """
        Close a position.
        
        Args:
            symbol: Symbol to close
            
        Returns:
            True if position closed successfully
        """
        if symbol not in self.positions:
            logger.warning(f"No position to close for {symbol}")
            return False
        
        try:
            position = self.positions[symbol]
            
            # Close via broker
            success = await self.broker.close_position(symbol)
            
            if success:
                # Update realized PnL
                self.total_realized_pnl += position.unrealized_pnl
                
                # Remove from positions
                del self.positions[symbol]
                
                logger.info(f"✅ Position closed: {symbol}")
                logger.info(f"   PnL: ₹{position.unrealized_pnl:.2f}")
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to close position {symbol}: {e}")
            return False
    
    async def close_all_positions(self):
        """Close all open positions"""
        symbols = list(self.positions.keys())
        
        for symbol in symbols:
            await self.close_position(symbol)
    
    def get_pnl_summary(self) -> Dict:
        """Get PnL summary"""
        return {
            "realized_pnl": self.total_realized_pnl,
            "unrealized_pnl": self.total_unrealized_pnl,
            "total_pnl": self.total_realized_pnl + self.total_unrealized_pnl,
            "open_positions": len(self.positions)
        }
    
    def get_position_details(self) -> List[Dict]:
        """Get detailed position information"""
        details = []
        
        for symbol, pos in self.positions.items():
            details.append({
                "symbol": symbol,
                "type": pos.position_type.value,
                "quantity": pos.quantity,
                "entry_price": pos.entry_price,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "unrealized_pnl_pct": (pos.unrealized_pnl / (pos.entry_price * pos.quantity)) * 100,
                "opened_at": pos.opened_at.isoformat() if pos.opened_at else None
            })
        
        return details
    
    def _recalculate_pnl(self):
        """Recalculate total unrealized PnL"""
        self.total_unrealized_pnl = sum(
            pos.unrealized_pnl for pos in self.positions.values()
        )
    
    def check_stop_loss_hit(self) -> List[str]:
        """
        Check if any positions have hit stop loss.
        
        Returns:
            List of symbols that hit stop loss
        """
        hit_symbols = []
        
        for symbol, pos in self.positions.items():
            if pos.stop_loss is None:
                continue
            
            if pos.position_type == PositionType.LONG:
                # Long position: stop loss below entry
                if pos.current_price <= pos.stop_loss:
                    hit_symbols.append(symbol)
            else:
                # Short position: stop loss above entry
                if pos.current_price >= pos.stop_loss:
                    hit_symbols.append(symbol)
        
        return hit_symbols
    
    def check_take_profit_hit(self) -> List[str]:
        """
        Check if any positions have hit take profit.
        
        Returns:
            List of symbols that hit take profit
        """
        hit_symbols = []
        
        for symbol, pos in self.positions.items():
            if pos.take_profit is None:
                continue
            
            if pos.position_type == PositionType.LONG:
                # Long position: take profit above entry
                if pos.current_price >= pos.take_profit:
                    hit_symbols.append(symbol)
            else:
                # Short position: take profit below entry
                if pos.current_price <= pos.take_profit:
                    hit_symbols.append(symbol)
        
        return hit_symbols
