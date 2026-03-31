"""
Strategy Interface and Base Classes
Phase 4: Strategy Simulation Engine
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum

from market_data_models import Candle
from backtest_models import TradeDirection


class SignalType(str, Enum):
    """Trading signal types"""
    BUY = "buy"
    SELL = "sell"
    CLOSE_BUY = "close_buy"
    CLOSE_SELL = "close_sell"
    NONE = "none"


class TradingSignal:
    """Represents a trading signal"""
    
    def __init__(
        self,
        signal_type: SignalType,
        volume: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = ""
    ):
        self.signal_type = signal_type
        self.volume = volume
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.comment = comment
        self.timestamp = datetime.now()


class Position:
    """Represents an open trading position"""
    
    def __init__(
        self,
        id: str,
        symbol: str,
        direction: TradeDirection,
        entry_price: float,
        volume: float,
        entry_time: datetime,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ):
        self.id = id
        self.symbol = symbol
        self.direction = direction
        self.entry_price = entry_price
        self.volume = volume
        self.entry_time = entry_time
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.current_price = entry_price
        self.floating_pnl = 0.0
    
    def update_price(self, current_price: float, pip_size: float = 0.0001):
        """Update current price and calculate floating P&L"""
        self.current_price = current_price
        
        if self.direction == TradeDirection.BUY:
            pips = (current_price - self.entry_price) / pip_size
        else:  # SELL
            pips = (self.entry_price - current_price) / pip_size
        
        # $10 per pip per 0.1 lot (standard calculation)
        self.floating_pnl = pips * 10 * self.volume
    
    def check_stop_loss(self, current_price: float) -> bool:
        """Check if stop loss is hit"""
        if not self.stop_loss:
            return False
        
        if self.direction == TradeDirection.BUY:
            return current_price <= self.stop_loss
        else:  # SELL
            return current_price >= self.stop_loss
    
    def check_take_profit(self, current_price: float) -> bool:
        """Check if take profit is hit"""
        if not self.take_profit:
            return False
        
        if self.direction == TradeDirection.BUY:
            return current_price >= self.take_profit
        else:  # SELL
            return current_price <= self.take_profit


class AccountInfo:
    """Trading account information"""
    
    def __init__(self, initial_balance: float, currency: str = "USD", leverage: int = 100):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.currency = currency
        self.leverage = leverage
        self.margin = 0.0
        self.free_margin = initial_balance
        self.margin_level = 0.0
    
    def update_equity(self, floating_pnl: float):
        """Update equity based on floating P&L"""
        self.equity = self.balance + floating_pnl
        self.free_margin = self.equity - self.margin
        
        if self.margin > 0:
            self.margin_level = (self.equity / self.margin) * 100
        else:
            self.margin_level = 0.0


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies
    
    Subclasses must implement:
    - on_start(): Initialize strategy
    - on_candle(candle): Process each candle
    """
    
    def __init__(self, symbol: str, timeframe: str):
        self.symbol = symbol
        self.timeframe = timeframe
        self.account: Optional[AccountInfo] = None
        self.positions: List[Position] = []
        self.candle_history: List[Candle] = []
        self.indicators: Dict = {}
        
        # Strategy parameters (can be overridden)
        self.max_positions = 3
        self.risk_percent = 2.0
        self.pip_size = 0.0001
    
    def initialize(self, account: AccountInfo):
        """Initialize strategy with account info"""
        self.account = account
    
    @abstractmethod
    def on_start(self):
        """Called once at strategy start"""
        pass
    
    @abstractmethod
    def on_candle(self, candle: Candle) -> Optional[TradingSignal]:
        """
        Called for each new candle
        Must return TradingSignal or None
        """
        pass
    
    def on_stop(self):
        """Called once at strategy end (optional override)"""
        pass
    
    def on_trade_opened(self, position: Position):
        """Called when a trade is opened (optional override)"""
        pass
    
    def on_trade_closed(self, position: Position, profit: float):
        """Called when a trade is closed (optional override)"""
        pass
    
    # Helper methods for strategy development
    def get_candles(self, count: int) -> List[Candle]:
        """Get last N candles"""
        return self.candle_history[-count:] if len(self.candle_history) >= count else self.candle_history
    
    def calculate_sma(self, period: int, price_type: str = "close") -> Optional[float]:
        """Calculate Simple Moving Average"""
        candles = self.get_candles(period)
        if len(candles) < period:
            return None
        
        prices = [getattr(c, price_type) for c in candles]
        return sum(prices) / period
    
    def calculate_ema(self, period: int, price_type: str = "close") -> Optional[float]:
        """Calculate Exponential Moving Average"""
        candles = self.get_candles(period)
        if len(candles) < period:
            return None
        
        prices = [getattr(c, price_type) for c in candles]
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def calculate_rsi(self, period: int = 14) -> Optional[float]:
        """Calculate Relative Strength Index"""
        candles = self.get_candles(period + 1)
        if len(candles) < period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(1, len(candles)):
            change = candles[i].close - candles[i-1].close
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def has_open_positions(self) -> bool:
        """Check if there are any open positions"""
        return len(self.positions) > 0
    
    def get_position_count(self) -> int:
        """Get number of open positions"""
        return len(self.positions)
    
    def calculate_position_size(self, stop_loss_pips: float) -> float:
        """
        Calculate position size based on risk percentage
        Returns: volume in lots
        """
        if not self.account or stop_loss_pips <= 0:
            return 0.1  # Default
        
        risk_amount = self.account.balance * (self.risk_percent / 100)
        pip_value = 10  # $10 per pip per standard lot
        
        # Calculate lot size
        lots = risk_amount / (stop_loss_pips * pip_value)
        
        # Round to 2 decimals and ensure minimum
        lots = max(0.01, round(lots, 2))
        
        return lots


# Example Strategy Implementation
class SimpleMACrossStrategy(BaseStrategy):
    """Simple Moving Average Crossover Strategy"""
    
    def __init__(self, symbol: str, timeframe: str, fast_period: int = 20, slow_period: int = 50):
        super().__init__(symbol, timeframe)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.last_signal = SignalType.NONE
        
        # Set pip size based on symbol
        if "XAU" in symbol.upper() or "GOLD" in symbol.upper():
            self.pip_size = 0.01  # Gold: 1 pip = $0.01
        else:
            self.pip_size = 0.0001  # Forex: 1 pip = 0.0001
    
    def on_start(self):
        """Initialize strategy"""
        print(f"Starting MA Cross Strategy: {self.fast_period}/{self.slow_period}")
    
    def on_candle(self, candle: Candle) -> Optional[TradingSignal]:
        """Process candle and generate signals"""
        
        # Need enough history
        if len(self.candle_history) < self.slow_period:
            return None
        
        # Calculate moving averages
        fast_ma = self.calculate_sma(self.fast_period)
        slow_ma = self.calculate_sma(self.slow_period)
        
        if fast_ma is None or slow_ma is None:
            return None
        
        # Get previous MAs for crossover detection
        prev_candles = self.candle_history[-self.slow_period-1:-1]
        if len(prev_candles) < self.slow_period:
            return None
        
        prev_fast_ma = sum([c.close for c in prev_candles[-self.fast_period:]]) / self.fast_period
        prev_slow_ma = sum([c.close for c in prev_candles[-self.slow_period:]]) / self.slow_period
        
        # Detect crossovers
        if fast_ma > slow_ma and prev_fast_ma <= prev_slow_ma:
            # Bullish crossover - BUY signal
            if not self.has_open_positions() and self.last_signal != SignalType.BUY:
                self.last_signal = SignalType.BUY
                
                # Calculate SL/TP (500 pips SL, 1000 pips TP for wider stops)
                stop_loss = candle.close - (500 * self.pip_size)
                take_profit = candle.close + (1000 * self.pip_size)
                
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    volume=0.1,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    comment=f"MA Cross: {fast_ma:.5f} > {slow_ma:.5f}"
                )
        
        elif fast_ma < slow_ma and prev_fast_ma >= prev_slow_ma:
            # Bearish crossover - SELL signal
            if not self.has_open_positions() and self.last_signal != SignalType.SELL:
                self.last_signal = SignalType.SELL
                
                # Calculate SL/TP (500 pips SL, 1000 pips TP for wider stops)
                stop_loss = candle.close + (500 * self.pip_size)
                take_profit = candle.close - (1000 * self.pip_size)
                
                return TradingSignal(
                    signal_type=SignalType.SELL,
                    volume=0.1,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    comment=f"MA Cross: {fast_ma:.5f} < {slow_ma:.5f}"
                )
        
        return None
