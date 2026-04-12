"""
Execution Engine

Converts strategy signals into executable orders with safety checks.
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass

from execution.broker_interface import (
    BrokerInterface,
    Order,
    OrderSide,
    OrderType,
)
from execution.order_manager import OrderManager
from execution.position_manager import PositionManager

logger = logging.getLogger(__name__)


@dataclass
class SignalConfig:
    """Signal configuration"""
    default_position_size: float = 0.01  # Default lot size
    max_position_size: float = 0.1       # Maximum lot size
    use_dynamic_sizing: bool = False     # Dynamic position sizing based on signal strength
    require_confirmation: bool = False   # Require manual confirmation before execution


@dataclass
class SafetyRules:
    """Trading safety rules"""
    max_positions: int = 5                    # Max concurrent positions
    max_trades_per_day: int = 20             # Max trades per day
    max_loss_per_day: float = 1000.0        # Max loss per day (₹)
    max_loss_per_trade: float = 200.0       # Max loss per trade (₹)
    allow_hedging: bool = False              # Allow opposing positions on same symbol
    block_duplicate_signals: bool = True      # Block duplicate signals for same symbol


class TradingSignal:
    """Trading signal representation"""
    
    def __init__(
        self,
        symbol: str,
        direction: str,  # "BUY" or "SELL"
        strength: float = 1.0,  # Signal strength 0.0-1.0
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        strategy_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        self.symbol = symbol
        self.direction = direction.upper()
        self.strength = max(0.0, min(1.0, strength))  # Clamp to 0-1
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.strategy_id = strategy_id
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
    
    def to_order_side(self) -> OrderSide:
        """Convert signal direction to OrderSide"""
        return OrderSide.BUY if self.direction == "BUY" else OrderSide.SELL


class ExecutionEngine:
    """
    Execution Engine
    
    Converts validated strategy signals into executable orders.
    
    Flow:
    1. Receive signal from strategy
    2. Apply safety checks
    3. Calculate position size
    4. Convert to order
    5. Submit via order manager
    6. Track execution
    """
    
    def __init__(
        self,
        broker: BrokerInterface,
        order_manager: OrderManager,
        position_manager: PositionManager,
        signal_config: SignalConfig = None,
        safety_rules: SafetyRules = None
    ):
        self.broker = broker
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.signal_config = signal_config or SignalConfig()
        self.safety_rules = safety_rules or SafetyRules()
        
        # Tracking
        self.signals_received = 0
        self.signals_executed = 0
        self.signals_rejected = 0
        self.daily_trade_count = 0
        self.daily_loss = 0.0
        self.last_reset_date = datetime.utcnow().date()
        
        # Signal deduplication
        self.recent_signals: Dict[str, TradingSignal] = {}
        
        logger.info("Execution Engine initialized")
        logger.info(f"  Max positions: {self.safety_rules.max_positions}")
        logger.info(f"  Max trades/day: {self.safety_rules.max_trades_per_day}")
    
    async def process_signal(
        self,
        signal: TradingSignal,
        auto_execute: bool = True
    ) -> Optional[Order]:
        """
        Process a trading signal.
        
        Args:
            signal: Trading signal to process
            auto_execute: Execute automatically (vs. queue for manual confirmation)
            
        Returns:
            Order if executed, None if rejected/queued
        """
        self.signals_received += 1
        
        logger.info("="*80)
        logger.info(f"📡 SIGNAL RECEIVED")
        logger.info(f"   Symbol: {signal.symbol}")
        logger.info(f"   Direction: {signal.direction}")
        logger.info(f"   Strength: {signal.strength:.2f}")
        logger.info(f"   Strategy: {signal.strategy_id}")
        logger.info("="*80)
        
        # Reset daily counters if new day
        self._check_daily_reset()
        
        # Safety checks
        if not await self._safety_checks(signal):
            self.signals_rejected += 1
            logger.warning("❌ Signal rejected by safety checks")
            return None
        
        if not auto_execute:
            logger.info("⏸️  Signal queued for manual confirmation")
            return None
        
        # Execute signal
        try:
            order = await self._execute_signal(signal)
            self.signals_executed += 1
            self.daily_trade_count += 1
            
            logger.info(f"✅ Signal executed successfully")
            return order
            
        except Exception as e:
            self.signals_rejected += 1
            logger.error(f"❌ Signal execution failed: {e}")
            return None
    
    async def _safety_checks(self, signal: TradingSignal) -> bool:
        """
        Apply safety checks to signal.
        
        Returns:
            True if signal passes all checks
        """
        
        # Check 1: Max positions
        if not self.position_manager.can_open_position():
            logger.warning(f"❌ Max positions reached ({self.safety_rules.max_positions})")
            return False
        
        # Check 2: Max trades per day
        if self.daily_trade_count >= self.safety_rules.max_trades_per_day:
            logger.warning(f"❌ Max daily trades reached ({self.safety_rules.max_trades_per_day})")
            return False
        
        # Check 3: Max daily loss
        if self.daily_loss >= self.safety_rules.max_loss_per_day:
            logger.warning(f"❌ Max daily loss reached (₹{self.safety_rules.max_loss_per_day})")
            return False
        
        # Check 4: Duplicate signal blocking
        if self.safety_rules.block_duplicate_signals:
            if signal.symbol in self.recent_signals:
                last_signal = self.recent_signals[signal.symbol]
                time_diff = (signal.timestamp - last_signal.timestamp).total_seconds()
                
                if time_diff < 60:  # Block signals within 60 seconds
                    logger.warning(f"❌ Duplicate signal blocked (last: {time_diff:.0f}s ago)")
                    return False
        
        # Check 5: Hedging check
        if not self.safety_rules.allow_hedging:
            if self.position_manager.has_position(signal.symbol):
                existing_pos = self.position_manager.get_position(signal.symbol)
                
                # Check if signal is opposite direction
                if signal.direction == "BUY" and existing_pos.position_type.value == "short":
                    logger.warning("❌ Opposing position exists (hedging disabled)")
                    return False
                elif signal.direction == "SELL" and existing_pos.position_type.value == "long":
                    logger.warning("❌ Opposing position exists (hedging disabled)")
                    return False
        
        # Check 6: One position per symbol (basic safety)
        if self.position_manager.has_position(signal.symbol):
            logger.warning(f"❌ Position already exists for {signal.symbol}")
            return False
        
        logger.info("✅ All safety checks passed")
        return True
    
    async def _execute_signal(self, signal: TradingSignal) -> Order:
        """
        Execute a validated signal.
        
        Converts signal → order and submits via order manager.
        """
        
        # Calculate position size
        position_size = self._calculate_position_size(signal)
        
        logger.info(f"📊 Calculated position size: {position_size}")
        
        # Get current market price for logging
        try:
            market_price = await self.broker.get_market_price(signal.symbol)
            logger.info(f"💰 Current market price: ₹{market_price:.2f}")
        except:
            market_price = None
        
        # Submit order
        order = await self.order_manager.submit_order(
            symbol=signal.symbol,
            side=signal.to_order_side(),
            quantity=position_size,
            order_type=OrderType.MARKET,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            auto_retry=True
        )
        
        # Track signal
        self.recent_signals[signal.symbol] = signal
        
        return order
    
    def _calculate_position_size(self, signal: TradingSignal) -> float:
        """
        Calculate position size for signal.
        
        Args:
            signal: Trading signal
            
        Returns:
            Position size (lot size)
        """
        if self.signal_config.use_dynamic_sizing:
            # Dynamic sizing based on signal strength
            base_size = self.signal_config.default_position_size
            position_size = base_size * signal.strength
            
            # Cap at max
            position_size = min(position_size, self.signal_config.max_position_size)
        else:
            # Fixed sizing
            position_size = self.signal_config.default_position_size
        
        return position_size
    
    def _check_daily_reset(self):
        """Reset daily counters if new day"""
        today = datetime.utcnow().date()
        
        if today > self.last_reset_date:
            logger.info("📅 New trading day - resetting counters")
            self.daily_trade_count = 0
            self.daily_loss = 0.0
            self.last_reset_date = today
    
    def get_statistics(self) -> Dict:
        """Get execution statistics"""
        success_rate = (
            (self.signals_executed / self.signals_received * 100)
            if self.signals_received > 0 else 0
        )
        
        return {
            "signals_received": self.signals_received,
            "signals_executed": self.signals_executed,
            "signals_rejected": self.signals_rejected,
            "success_rate": success_rate,
            "daily_trade_count": self.daily_trade_count,
            "daily_loss": self.daily_loss,
            "positions_open": self.position_manager.get_position_count()
        }
