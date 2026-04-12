"""
Abstract Broker Interface

Defines the contract that all broker adapters must implement.
This ensures broker-agnostic code in the execution layer.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class OrderType(Enum):
    """Order types supported"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LOSS_MARKET = "stop_loss_market"


class OrderSide(Enum):
    """Order side"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order lifecycle states"""
    PENDING = "pending"
    PLACED = "placed"
    OPEN = "open"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    FAILED = "failed"


class PositionType(Enum):
    """Position direction"""
    LONG = "long"
    SHORT = "short"


@dataclass
class BrokerConfig:
    """Broker configuration"""
    name: str
    api_key: str
    api_secret: str
    access_token: Optional[str] = None
    paper_mode: bool = True  # Default to paper trading
    base_url: Optional[str] = None


@dataclass
class Order:
    """Order representation"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_price: Optional[float] = None
    timestamp: datetime = None
    error_message: Optional[str] = None
    broker_order_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class Position:
    """Position representation"""
    symbol: str
    position_type: PositionType
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    opened_at: datetime = None
    
    def __post_init__(self):
        if self.opened_at is None:
            self.opened_at = datetime.utcnow()
    
    def update_price(self, current_price: float):
        """Update current price and recalculate PnL"""
        self.current_price = current_price
        if self.position_type == PositionType.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity


@dataclass
class AccountBalance:
    """Account balance information"""
    available_balance: float
    used_margin: float
    total_balance: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


class BrokerInterface(ABC):
    """
    Abstract base class for all broker implementations.
    
    All broker adapters (Zerodha, Interactive Brokers, etc.) must implement
    this interface to ensure compatibility with the execution engine.
    """
    
    def __init__(self, config: BrokerConfig):
        self.config = config
        self.is_connected = False
        self.paper_mode = config.paper_mode
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to broker API.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Close connection to broker API.
        
        Returns:
            True if disconnection successful
        """
        pass
    
    @abstractmethod
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
        Place an order with the broker.
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD", "RELIANCE")
            side: BUY or SELL
            quantity: Order quantity
            order_type: MARKET, LIMIT, etc.
            price: Limit price (required for LIMIT orders)
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            
        Returns:
            Order object with broker order ID and status
            
        Raises:
            BrokerException: If order placement fails
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.
        
        Args:
            order_id: Internal order ID
            
        Returns:
            True if cancellation successful
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Order:
        """
        Get current status of an order.
        
        Args:
            order_id: Internal order ID
            
        Returns:
            Order object with updated status
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """
        Fetch all open positions.
        
        Returns:
            List of Position objects
        """
        pass
    
    @abstractmethod
    async def close_position(self, symbol: str) -> bool:
        """
        Close an open position for the given symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if position closed successfully
        """
        pass
    
    @abstractmethod
    async def get_balance(self) -> AccountBalance:
        """
        Get account balance and margin information.
        
        Returns:
            AccountBalance object
        """
        pass
    
    @abstractmethod
    async def get_market_price(self, symbol: str) -> float:
        """
        Get current market price for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current market price
        """
        pass
    
    def is_paper_mode(self) -> bool:
        """Check if broker is in paper trading mode"""
        return self.paper_mode


class BrokerException(Exception):
    """Base exception for broker-related errors"""
    pass


class OrderPlacementException(BrokerException):
    """Exception raised when order placement fails"""
    pass


class InsufficientFundsException(BrokerException):
    """Exception raised when account has insufficient funds"""
    pass


class SymbolNotFoundException(BrokerException):
    """Exception raised when symbol is not found"""
    pass


class ConnectionException(BrokerException):
    """Exception raised when connection to broker fails"""
    pass
