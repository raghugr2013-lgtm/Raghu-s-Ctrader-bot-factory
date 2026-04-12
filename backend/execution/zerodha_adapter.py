"""
Zerodha Kite API Adapter

Implements broker interface for Zerodha (India's leading broker).
Supports both live and paper trading modes.

Paper Mode: Simulates orders locally without hitting real API.
Live Mode: Connects to Zerodha Kite API for real order execution.
"""

import logging
import uuid
from typing import Dict, List, Optional
from datetime import datetime

from execution.broker_interface import (
    BrokerInterface,
    BrokerConfig,
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    Position,
    PositionType,
    AccountBalance,
    OrderPlacementException,
    InsufficientFundsException,
    ConnectionException,
)

logger = logging.getLogger(__name__)


class ZerodhaAdapter(BrokerInterface):
    """
    Zerodha Kite API implementation.
    
    Paper Mode Features:
    - Simulates order execution
    - Tracks virtual positions
    - Maintains virtual balance
    - No real API calls
    
    Live Mode Features:
    - Real Kite API integration
    - Actual order placement
    - Real position tracking
    - Live balance updates
    """
    
    def __init__(self, config: BrokerConfig):
        super().__init__(config)
        self.kite = None
        
        # Paper trading state
        self.paper_orders: Dict[str, Order] = {}
        self.paper_positions: Dict[str, Position] = {}
        self.paper_balance = AccountBalance(
            available_balance=100000.0,  # Start with 1 lakh
            used_margin=0.0,
            total_balance=100000.0
        )
        
        # Live trading (initialized on connect)
        self.session_token = None
        
        logger.info(f"Zerodha adapter initialized (paper_mode={self.paper_mode})")
    
    async def connect(self) -> bool:
        """
        Connect to Zerodha Kite API.
        
        Paper Mode: Always succeeds (no real connection)
        Live Mode: Authenticates with Kite API
        """
        try:
            if self.paper_mode:
                logger.info("✅ Paper mode: Simulated connection successful")
                self.is_connected = True
                return True
            
            # Live mode: Initialize Kite Connect
            try:
                from kiteconnect import KiteConnect
            except ImportError:
                raise ConnectionException(
                    "kiteconnect library not installed. Run: pip install kiteconnect"
                )
            
            self.kite = KiteConnect(api_key=self.config.api_key)
            
            # Check if we have access token
            if not self.config.access_token:
                logger.error("❌ No access_token provided for live mode")
                raise ConnectionException(
                    "Access token required for live mode. "
                    "Generate via Kite login flow: https://kite.trade/docs/connect/v3/"
                )
            
            self.kite.set_access_token(self.config.access_token)
            
            # Verify connection by fetching profile
            profile = self.kite.profile()
            logger.info(f"✅ Connected to Zerodha Kite API")
            logger.info(f"   User: {profile.get('user_name')}")
            logger.info(f"   Email: {profile.get('email')}")
            
            self.is_connected = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            self.is_connected = False
            raise ConnectionException(f"Failed to connect: {e}")
    
    async def disconnect(self) -> bool:
        """Disconnect from Kite API"""
        self.is_connected = False
        self.kite = None
        logger.info("Disconnected from Zerodha")
        return True
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Order:
        """
        Place order via Zerodha.
        
        Paper Mode: Simulates instant fill at current market price
        Live Mode: Places real order via Kite API
        """
        if not self.is_connected:
            raise ConnectionException("Not connected to broker")
        
        # Generate internal order ID
        order_id = str(uuid.uuid4())
        
        if self.paper_mode:
            return await self._place_paper_order(
                order_id, symbol, side, quantity, order_type, price, stop_loss, take_profit
            )
        else:
            return await self._place_live_order(
                order_id, symbol, side, quantity, order_type, price, stop_loss, take_profit
            )
    
    async def _place_paper_order(
        self,
        order_id: str,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType,
        price: Optional[float],
        stop_loss: Optional[float],
        take_profit: Optional[float]
    ) -> Order:
        """Simulate order execution in paper mode"""
        
        # Simulate market price (in real system, this would come from live feed)
        market_price = price if price else 100.0  # Placeholder price
        
        # Check if we have sufficient balance
        order_value = market_price * quantity
        if order_value > self.paper_balance.available_balance:
            raise InsufficientFundsException(
                f"Insufficient balance: need ₹{order_value:.2f}, have ₹{self.paper_balance.available_balance:.2f}"
            )
        
        # Create order
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status=OrderStatus.COMPLETE,  # Paper orders fill instantly
            filled_quantity=quantity,
            average_price=market_price,
            broker_order_id=f"PAPER-{order_id[:8]}"
        )
        
        self.paper_orders[order_id] = order
        
        # Update balance
        self.paper_balance.used_margin += order_value
        self.paper_balance.available_balance -= order_value
        
        # Create or update position
        await self._update_paper_position(order)
        
        logger.info(f"📝 Paper order placed: {symbol} {side.value.upper()} {quantity} @ ₹{market_price:.2f}")
        
        return order
    
    async def _place_live_order(
        self,
        order_id: str,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType,
        price: Optional[float],
        stop_loss: Optional[float],
        take_profit: Optional[float]
    ) -> Order:
        """Place real order via Kite API"""
        
        try:
            # Map to Kite parameters
            kite_transaction_type = "BUY" if side == OrderSide.BUY else "SELL"
            kite_order_type = {
                OrderType.MARKET: "MARKET",
                OrderType.LIMIT: "LIMIT",
                OrderType.STOP_LOSS: "SL",
                OrderType.STOP_LOSS_MARKET: "SL-M"
            }[order_type]
            
            # Place order
            kite_order_params = {
                "tradingsymbol": symbol,
                "exchange": "NSE",  # Default to NSE, adjust as needed
                "transaction_type": kite_transaction_type,
                "quantity": int(quantity),
                "order_type": kite_order_type,
                "product": "MIS",  # Intraday, adjust as needed
            }
            
            if price and order_type == OrderType.LIMIT:
                kite_order_params["price"] = price
            
            if stop_loss:
                kite_order_params["trigger_price"] = stop_loss
            
            broker_order_id = self.kite.place_order(**kite_order_params)
            
            # Create order object
            order = Order(
                order_id=order_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                status=OrderStatus.PLACED,
                broker_order_id=broker_order_id
            )
            
            logger.info(f"✅ Live order placed: {symbol} {side.value.upper()} {quantity}")
            logger.info(f"   Broker Order ID: {broker_order_id}")
            
            return order
            
        except Exception as e:
            logger.error(f"❌ Order placement failed: {e}")
            raise OrderPlacementException(f"Failed to place order: {e}")
    
    async def _update_paper_position(self, order: Order):
        """Update paper position after order fill"""
        symbol = order.symbol
        
        if symbol in self.paper_positions:
            # Position exists
            position = self.paper_positions[symbol]
            
            if order.side == OrderSide.BUY:
                # Adding to long or closing short
                if position.position_type == PositionType.LONG:
                    # Average up
                    total_quantity = position.quantity + order.quantity
                    total_cost = (position.entry_price * position.quantity) + (order.average_price * order.quantity)
                    position.entry_price = total_cost / total_quantity
                    position.quantity = total_quantity
                else:
                    # Closing short
                    if order.quantity >= position.quantity:
                        # Full close or reverse
                        realized_pnl = (position.entry_price - order.average_price) * position.quantity
                        self.paper_balance.realized_pnl += realized_pnl
                        del self.paper_positions[symbol]
                    else:
                        # Partial close
                        realized_pnl = (position.entry_price - order.average_price) * order.quantity
                        self.paper_balance.realized_pnl += realized_pnl
                        position.quantity -= order.quantity
            else:
                # SELL
                if position.position_type == PositionType.SHORT:
                    # Average down
                    total_quantity = position.quantity + order.quantity
                    total_cost = (position.entry_price * position.quantity) + (order.average_price * order.quantity)
                    position.entry_price = total_cost / total_quantity
                    position.quantity = total_quantity
                else:
                    # Closing long
                    if order.quantity >= position.quantity:
                        # Full close
                        realized_pnl = (order.average_price - position.entry_price) * position.quantity
                        self.paper_balance.realized_pnl += realized_pnl
                        del self.paper_positions[symbol]
                    else:
                        # Partial close
                        realized_pnl = (order.average_price - position.entry_price) * order.quantity
                        self.paper_balance.realized_pnl += realized_pnl
                        position.quantity -= order.quantity
        else:
            # New position
            position_type = PositionType.LONG if order.side == OrderSide.BUY else PositionType.SHORT
            position = Position(
                symbol=symbol,
                position_type=position_type,
                quantity=order.quantity,
                entry_price=order.average_price,
                current_price=order.average_price,
                unrealized_pnl=0.0,
                stop_loss=order.stop_loss,
                take_profit=order.take_profit
            )
            self.paper_positions[symbol] = position
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        if self.paper_mode:
            if order_id in self.paper_orders:
                order = self.paper_orders[order_id]
                if order.status in [OrderStatus.PENDING, OrderStatus.OPEN]:
                    order.status = OrderStatus.CANCELLED
                    logger.info(f"📝 Paper order cancelled: {order_id}")
                    return True
            return False
        else:
            # Live mode: cancel via Kite
            order = self.paper_orders.get(order_id)  # Assuming we track all orders
            if order and order.broker_order_id:
                try:
                    self.kite.cancel_order(order.broker_order_id)
                    logger.info(f"✅ Order cancelled: {order.broker_order_id}")
                    return True
                except Exception as e:
                    logger.error(f"❌ Cancel failed: {e}")
                    return False
            return False
    
    async def get_order_status(self, order_id: str) -> Order:
        """Get order status"""
        if order_id in self.paper_orders:
            return self.paper_orders[order_id]
        raise Exception(f"Order not found: {order_id}")
    
    async def get_positions(self) -> List[Position]:
        """Get all open positions"""
        if self.paper_mode:
            return list(self.paper_positions.values())
        else:
            # Live mode: fetch from Kite
            try:
                kite_positions = self.kite.positions()
                positions = []
                
                for p in kite_positions.get('net', []):
                    if p['quantity'] != 0:
                        position = Position(
                            symbol=p['tradingsymbol'],
                            position_type=PositionType.LONG if p['quantity'] > 0 else PositionType.SHORT,
                            quantity=abs(p['quantity']),
                            entry_price=p['average_price'],
                            current_price=p['last_price'],
                            unrealized_pnl=p['pnl'],
                            realized_pnl=p['realised']
                        )
                        positions.append(position)
                
                return positions
            except Exception as e:
                logger.error(f"❌ Failed to fetch positions: {e}")
                return []
    
    async def close_position(self, symbol: str) -> bool:
        """Close a position"""
        positions = await self.get_positions()
        
        for pos in positions:
            if pos.symbol == symbol:
                # Place opposite order to close
                close_side = OrderSide.SELL if pos.position_type == PositionType.LONG else OrderSide.BUY
                order = await self.place_order(
                    symbol=symbol,
                    side=close_side,
                    quantity=pos.quantity,
                    order_type=OrderType.MARKET
                )
                logger.info(f"✅ Position closed: {symbol}")
                return True
        
        return False
    
    async def get_balance(self) -> AccountBalance:
        """Get account balance"""
        if self.paper_mode:
            return self.paper_balance
        else:
            # Live mode: fetch from Kite
            try:
                margins = self.kite.margins()
                equity = margins['equity']
                
                return AccountBalance(
                    available_balance=equity['available']['live_balance'],
                    used_margin=equity['utilised']['debits'],
                    total_balance=equity['net']
                )
            except Exception as e:
                logger.error(f"❌ Failed to fetch balance: {e}")
                return AccountBalance(
                    available_balance=0.0,
                    used_margin=0.0,
                    total_balance=0.0
                )
    
    async def get_market_price(self, symbol: str) -> float:
        """Get current market price"""
        if self.paper_mode:
            # Placeholder: return simulated price
            # In real system, this would connect to live data feed
            return 100.0
        else:
            # Live mode: fetch LTP from Kite
            try:
                quote = self.kite.quote(f"NSE:{symbol}")
                return quote[f"NSE:{symbol}"]['last_price']
            except Exception as e:
                logger.error(f"❌ Failed to fetch price for {symbol}: {e}")
                raise Exception(f"Could not fetch price: {e}")
