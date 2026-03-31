"""
Strategy Simulator - Candle Replay Engine
Phase 4: Real Strategy Execution with Historical Data
"""

from typing import List, Optional, Dict
from datetime import datetime, timedelta, timezone
import uuid
import logging

from market_data_models import Candle, DataTimeframe
from backtest_models import (
    TradeRecord,
    TradeDirection,
    TradeStatus,
    EquityPoint,
    BacktestConfig,
    PerformanceMetrics,
    BacktestResult
)
from strategy_interface import (
    BaseStrategy,
    TradingSignal,
    SignalType,
    Position,
    AccountInfo
)
from backtest_calculator import performance_calculator, strategy_scorer

logger = logging.getLogger(__name__)


class TradeExecutor:
    """Simulates realistic trade execution"""
    
    def __init__(
        self,
        account: AccountInfo,
        symbol: str,
        spread_pips: float = 1.0,
        commission_per_lot: float = 7.0,
        pip_size: float = 0.0001
    ):
        self.account = account
        self.symbol = symbol
        self.spread_pips = spread_pips
        self.commission_per_lot = commission_per_lot
        self.pip_size = pip_size
        self.positions: Dict[str, Position] = {}
    
    def execute_market_order(
        self,
        signal: TradingSignal,
        current_candle: Candle
    ) -> Optional[Position]:
        """Execute market order"""
        
        # Determine direction
        if signal.signal_type == SignalType.BUY:
            direction = TradeDirection.BUY
            entry_price = current_candle.close + (self.spread_pips * self.pip_size)  # Ask price
        elif signal.signal_type == SignalType.SELL:
            direction = TradeDirection.SELL
            entry_price = current_candle.close  # Bid price
        else:
            return None
        
        # Create position
        position = Position(
            id=str(uuid.uuid4()),
            symbol=self.symbol,
            direction=direction,
            entry_price=entry_price,
            volume=signal.volume,
            entry_time=current_candle.timestamp,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit
        )
        
        # Deduct commission
        commission = self.commission_per_lot * signal.volume
        self.account.balance -= commission
        
        # Store position
        self.positions[position.id] = position
        
        logger.info(f"Opened {direction.value} position at {entry_price:.5f}, SL: {signal.stop_loss}, TP: {signal.take_profit}")
        
        return position
    
    def update_positions(self, current_candle: Candle) -> List[tuple[Position, str, float]]:
        """
        Update all positions and check for SL/TP hits
        Returns: List of (Position, close_reason, profit)
        """
        closed_positions = []
        
        for position in list(self.positions.values()):
            # Update floating P&L
            position.update_price(current_candle.close, self.pip_size)
            
            # Check stop loss hit (use candle low/high for realism)
            if position.direction == TradeDirection.BUY:
                if position.stop_loss and current_candle.low <= position.stop_loss:
                    closed_positions.append((position, "stop_loss", position.stop_loss))
                    continue
                if position.take_profit and current_candle.high >= position.take_profit:
                    closed_positions.append((position, "take_profit", position.take_profit))
                    continue
            
            else:  # SELL
                if position.stop_loss and current_candle.high >= position.stop_loss:
                    closed_positions.append((position, "stop_loss", position.stop_loss))
                    continue
                if position.take_profit and current_candle.low <= position.take_profit:
                    closed_positions.append((position, "take_profit", position.take_profit))
                    continue
        
        return closed_positions
    
    def close_position(
        self,
        position: Position,
        exit_price: float,
        close_reason: str
    ) -> float:
        """Close position and return profit"""
        
        # Calculate profit
        if position.direction == TradeDirection.BUY:
            pips = (exit_price - position.entry_price) / self.pip_size
        else:  # SELL
            pips = (position.entry_price - exit_price) / self.pip_size
        
        profit = pips * 10 * position.volume
        
        # Update account
        self.account.balance += profit
        
        # Remove position
        if position.id in self.positions:
            del self.positions[position.id]
        
        logger.info(f"Closed {position.direction.value} position at {exit_price:.5f}, Profit: ${profit:.2f} ({pips:.1f} pips)")
        
        return profit
    
    def get_floating_pnl(self) -> float:
        """Calculate total floating P&L"""
        return sum(pos.floating_pnl for pos in self.positions.values())
    
    def close_all_positions(self, current_price: float) -> List[tuple[Position, float]]:
        """Close all open positions"""
        closed = []
        for position in list(self.positions.values()):
            profit = self.close_position(position, current_price, "strategy_close")
            closed.append((position, profit))
        return closed


class EquityTracker:
    """Track equity curve and drawdown"""
    
    def __init__(self, initial_balance: float):
        self.initial_balance = initial_balance
        self.equity_curve: List[EquityPoint] = []
        self.peak_balance = initial_balance
    
    def record_point(self, timestamp: datetime, balance: float, floating_pnl: float):
        """Record equity point"""
        equity = balance + floating_pnl
        
        # Update peak
        if equity > self.peak_balance:
            self.peak_balance = equity
        
        # Calculate drawdown
        drawdown = self.peak_balance - equity
        drawdown_pct = (drawdown / self.peak_balance * 100) if self.peak_balance > 0 else 0
        
        point = EquityPoint(
            timestamp=timestamp,
            balance=balance,
            equity=equity,
            drawdown=drawdown,
            drawdown_percent=drawdown_pct
        )
        
        self.equity_curve.append(point)
    
    def get_equity_curve(self) -> List[EquityPoint]:
        """Get equity curve"""
        return self.equity_curve


class StrategySimulator:
    """
    Main Strategy Simulation Engine
    Replays historical candles and executes strategy
    """
    
    def __init__(
        self,
        strategy: BaseStrategy,
        config: BacktestConfig,
        candles: List[Candle]
    ):
        self.strategy = strategy
        self.config = config
        self.candles = candles
        self.backtest_id = str(uuid.uuid4())
        
        # Initialize components
        self.account = AccountInfo(
            initial_balance=config.initial_balance,
            currency=config.currency,
            leverage=config.leverage
        )
        
        # Determine pip size based on symbol
        pip_size = 0.01 if "XAU" in config.symbol or "GOLD" in config.symbol else 0.0001
        
        self.trade_executor = TradeExecutor(
            account=self.account,
            symbol=config.symbol,
            spread_pips=config.spread_pips,
            commission_per_lot=config.commission_per_lot,
            pip_size=pip_size
        )
        
        self.equity_tracker = EquityTracker(config.initial_balance)
        
        # Trade history
        self.trades: List[TradeRecord] = []
        
        # Statistics
        self.total_signals = 0
        self.executed_trades = 0
    
    def run(self) -> Dict:
        """
        Run strategy simulation
        Returns: {trades, equity_curve, stats}
        """
        logger.info(f"Starting strategy simulation with {len(self.candles)} candles")
        
        # Initialize strategy
        self.strategy.initialize(self.account)
        self.strategy.on_start()
        
        # Record initial equity point
        self.equity_tracker.record_point(
            self.candles[0].timestamp,
            self.account.balance,
            0.0
        )
        
        # Candle replay loop
        for i, candle in enumerate(self.candles):
            # Add candle to strategy history
            self.strategy.candle_history.append(candle)
            
            # Update open positions (check SL/TP)
            closed_positions = self.trade_executor.update_positions(candle)
            
            # Process closed positions
            for position, close_reason, exit_price in closed_positions:
                profit = self.trade_executor.close_position(position, exit_price, close_reason)
                
                # Record trade
                trade = self._create_trade_record(position, exit_price, profit, close_reason)
                self.trades.append(trade)
                
                # Update strategy's position list after closing
                self.strategy.positions = list(self.trade_executor.positions.values())
                
                # Notify strategy
                self.strategy.on_trade_closed(position, profit)
            
            # Get trading signal from strategy
            signal = self.strategy.on_candle(candle)
            
            if signal:
                self.total_signals += 1
                
                # Execute signal
                if signal.signal_type in [SignalType.BUY, SignalType.SELL]:
                    # Check position limit
                    if len(self.trade_executor.positions) < self.strategy.max_positions:
                        position = self.trade_executor.execute_market_order(signal, candle)
                        
                        if position:
                            self.executed_trades += 1
                            self.strategy.positions = list(self.trade_executor.positions.values())
                            self.strategy.on_trade_opened(position)
            
            # Update equity curve every 10 candles (for performance)
            if i % 10 == 0 or i == len(self.candles) - 1:
                floating_pnl = self.trade_executor.get_floating_pnl()
                self.account.update_equity(floating_pnl)
                self.equity_tracker.record_point(candle.timestamp, self.account.balance, floating_pnl)
        
        # Close all remaining positions at end
        if self.trade_executor.positions:
            last_candle = self.candles[-1]
            closed_final = self.trade_executor.close_all_positions(last_candle.close)
            
            for position, profit in closed_final:
                trade = self._create_trade_record(
                    position,
                    last_candle.close,
                    profit,
                    "simulation_end"
                )
                self.trades.append(trade)
        
        # Strategy cleanup
        self.strategy.on_stop()
        
        # Final equity point
        self.equity_tracker.record_point(
            self.candles[-1].timestamp,
            self.account.balance,
            0.0
        )
        
        logger.info(f"Simulation complete: {len(self.trades)} trades executed")
        
        return {
            "trades": self.trades,
            "equity_curve": self.equity_tracker.get_equity_curve(),
            "final_balance": self.account.balance,
            "total_signals": self.total_signals,
            "executed_trades": self.executed_trades
        }
    
    def _create_trade_record(
        self,
        position: Position,
        exit_price: float,
        profit: float,
        close_reason: str
    ) -> TradeRecord:
        """Create trade record from position"""
        
        # Calculate pips
        if position.direction == TradeDirection.BUY:
            pips = (exit_price - position.entry_price) / 0.0001
        else:
            pips = (position.entry_price - exit_price) / 0.0001
        
        # Calculate duration
        # For now, use last candle timestamp as exit time
        duration = (self.candles[-1].timestamp - position.entry_time).total_seconds() / 60
        
        trade = TradeRecord(
            id=position.id,
            backtest_id=self.backtest_id,
            entry_time=position.entry_time,
            exit_time=self.candles[-1].timestamp,
            symbol=position.symbol,
            direction=position.direction,
            entry_price=position.entry_price,
            exit_price=exit_price,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            volume=position.volume,
            position_size=position.volume * 100000,
            profit_loss=profit,
            profit_loss_pips=pips,
            profit_loss_percent=(profit / self.config.initial_balance) * 100,
            duration_minutes=int(duration),
            commission=self.config.commission_per_lot * position.volume,
            status=TradeStatus.CLOSED,
            close_reason=close_reason
        )
        
        return trade


# Factory function
def create_strategy_simulator(
    strategy: BaseStrategy,
    config: BacktestConfig,
    candles: List[Candle]
) -> StrategySimulator:
    """Create strategy simulator instance"""
    return StrategySimulator(strategy, config, candles)
