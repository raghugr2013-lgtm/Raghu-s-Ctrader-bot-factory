"""
Order Manager

Manages order lifecycle, tracks status, handles retries, and maintains order history.
"""

import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from execution.broker_interface import (
    BrokerInterface,
    Order,
    OrderStatus,
    OrderSide,
    OrderType,
)

logger = logging.getLogger(__name__)


@dataclass
class OrderConfig:
    """Order manager configuration"""
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    timeout_seconds: float = 60.0


class OrderManager:
    """
    Manages order execution lifecycle.
    
    Responsibilities:
    - Track all orders
    - Monitor order status
    - Retry failed orders
    - Handle partial fills
    - Maintain order history
    """
    
    def __init__(self, broker: BrokerInterface, config: OrderConfig = None):
        self.broker = broker
        self.config = config or OrderConfig()
        
        # Order tracking
        self.active_orders: Dict[str, Order] = {}
        self.completed_orders: Dict[str, Order] = {}
        self.failed_orders: Dict[str, Order] = {}
        
        # Retry tracking
        self.retry_counts: Dict[str, int] = {}
        
        logger.info("Order Manager initialized")
    
    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        auto_retry: bool = True
    ) -> Order:
        """
        Submit an order with automatic retry logic.
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Order quantity
            order_type: MARKET, LIMIT, etc.
            price: Limit price (for LIMIT orders)
            stop_loss: Stop loss price
            take_profit: Take profit price
            auto_retry: Enable automatic retries on failure
            
        Returns:
            Order object
        """
        retry_count = 0
        last_error = None
        
        while retry_count <= self.config.max_retries:
            try:
                logger.info(f"📤 Submitting order: {symbol} {side.value.upper()} {quantity}")
                
                order = await self.broker.place_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    order_type=order_type,
                    price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                )
                
                # Track order
                self.active_orders[order.order_id] = order
                
                logger.info(f"✅ Order submitted successfully: {order.order_id}")
                logger.info(f"   Status: {order.status.value}")
                logger.info(f"   Broker ID: {order.broker_order_id}")
                
                return order
                
            except Exception as e:
                last_error = e
                retry_count += 1
                
                logger.error(f"❌ Order submission failed (attempt {retry_count}/{self.config.max_retries + 1}): {e}")
                
                if not auto_retry or retry_count > self.config.max_retries:
                    # Create failed order record
                    failed_order = Order(
                        order_id=f"FAILED-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        quantity=quantity,
                        price=price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        status=OrderStatus.FAILED,
                        error_message=str(last_error)
                    )
                    self.failed_orders[failed_order.order_id] = failed_order
                    raise
                
                # Wait before retry
                logger.info(f"⏳ Retrying in {self.config.retry_delay_seconds}s...")
                await asyncio.sleep(self.config.retry_delay_seconds)
        
        raise Exception(f"Order submission failed after {self.config.max_retries} retries: {last_error}")
    
    async def monitor_order(self, order_id: str) -> Order:
        """
        Monitor an order until completion or timeout.
        
        Args:
            order_id: Order ID to monitor
            
        Returns:
            Updated order
        """
        if order_id not in self.active_orders:
            raise Exception(f"Order not found: {order_id}")
        
        order = self.active_orders[order_id]
        start_time = datetime.utcnow()
        
        while True:
            try:
                # Update order status
                updated_order = await self.broker.get_order_status(order_id)
                self.active_orders[order_id] = updated_order
                
                # Check if order is complete
                if updated_order.status in [OrderStatus.COMPLETE, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                    logger.info(f"✅ Order {order_id} reached terminal state: {updated_order.status.value}")
                    
                    # Move to completed
                    del self.active_orders[order_id]
                    self.completed_orders[order_id] = updated_order
                    
                    return updated_order
                
                # Check timeout
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed > self.config.timeout_seconds:
                    logger.warning(f"⏰ Order {order_id} monitoring timeout ({self.config.timeout_seconds}s)")
                    return updated_order
                
                # Wait before next check
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error(f"❌ Error monitoring order {order_id}: {e}")
                return self.active_orders[order_id]
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an active order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancellation successful
        """
        if order_id not in self.active_orders:
            logger.warning(f"Order {order_id} not found in active orders")
            return False
        
        try:
            success = await self.broker.cancel_order(order_id)
            
            if success:
                order = self.active_orders[order_id]
                order.status = OrderStatus.CANCELLED
                
                # Move to completed
                del self.active_orders[order_id]
                self.completed_orders[order_id] = order
                
                logger.info(f"✅ Order cancelled: {order_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel order {order_id}: {e}")
            return False
    
    def get_active_orders(self) -> List[Order]:
        """Get all active orders"""
        return list(self.active_orders.values())
    
    def get_completed_orders(self) -> List[Order]:
        """Get all completed orders"""
        return list(self.completed_orders.values())
    
    def get_failed_orders(self) -> List[Order]:
        """Get all failed orders"""
        return list(self.failed_orders.values())
    
    def get_order_by_symbol(self, symbol: str) -> List[Order]:
        """Get all orders for a specific symbol"""
        all_orders = list(self.active_orders.values()) + list(self.completed_orders.values())
        return [o for o in all_orders if o.symbol == symbol]
    
    def get_order_history(self, limit: int = 100) -> List[Order]:
        """Get recent order history"""
        completed = list(self.completed_orders.values())
        failed = list(self.failed_orders.values())
        
        all_orders = completed + failed
        all_orders.sort(key=lambda x: x.timestamp, reverse=True)
        
        return all_orders[:limit]
    
    def get_statistics(self) -> Dict:
        """Get order execution statistics"""
        total_orders = len(self.completed_orders) + len(self.failed_orders)
        completed_count = len(self.completed_orders)
        failed_count = len(self.failed_orders)
        
        success_rate = (completed_count / total_orders * 100) if total_orders > 0 else 0
        
        return {
            "total_orders": total_orders,
            "active_orders": len(self.active_orders),
            "completed_orders": completed_count,
            "failed_orders": failed_count,
            "success_rate": success_rate
        }
