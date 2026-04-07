"""
Mock Backtest Data Generator
Generates realistic simulated backtest data for testing
Phase 3: No real market data integration yet
"""

import random
from datetime import datetime, timedelta, timezone
from typing import List
import uuid

from backtest_models import (
    TradeRecord,
    TradeDirection,
    TradeStatus,
    EquityPoint,
    BacktestConfig,
    Timeframe
)


class MockBacktestGenerator:
    """Generate realistic mock backtest data"""
    
    @staticmethod
    def generate_mock_backtest(
        bot_name: str,
        symbol: str = "EURUSD",
        timeframe: Timeframe = Timeframe.H1,
        duration_days: int = 90,
        initial_balance: float = 10000.0,
        strategy_type: str = "trend_following"
    ) -> tuple[List[TradeRecord], List[EquityPoint], BacktestConfig]:
        """
        Generate complete mock backtest data
        
        Strategy types:
        - trend_following: Higher win rate, larger winners
        - mean_reversion: Lower win rate, frequent trades
        - breakout: Mixed, volatile equity curve
        - scalping: Very high frequency, small profits
        """
        
        backtest_id = str(uuid.uuid4())
        
        # Create config
        config = BacktestConfig(
            symbol=symbol,
            timeframe=timeframe,
            start_date=datetime.now(timezone.utc) - timedelta(days=duration_days),
            end_date=datetime.now(timezone.utc),
            initial_balance=initial_balance,
            currency="USD",
            leverage=100,
            commission_per_lot=7.0,
            spread_pips=1.0
        )
        
        # Generate trades based on strategy type
        if strategy_type == "trend_following":
            trades = MockBacktestGenerator._generate_trend_following_trades(
                backtest_id, config, duration_days
            )
        elif strategy_type == "mean_reversion":
            trades = MockBacktestGenerator._generate_mean_reversion_trades(
                backtest_id, config, duration_days
            )
        elif strategy_type == "breakout":
            trades = MockBacktestGenerator._generate_breakout_trades(
                backtest_id, config, duration_days
            )
        elif strategy_type == "scalping":
            trades = MockBacktestGenerator._generate_scalping_trades(
                backtest_id, config, duration_days
            )
        else:
            trades = MockBacktestGenerator._generate_generic_trades(
                backtest_id, config, duration_days
            )
        
        # Generate equity curve from trades
        equity_curve = MockBacktestGenerator._generate_equity_curve(
            trades, initial_balance
        )
        
        return trades, equity_curve, config
    
    @staticmethod
    def _generate_trend_following_trades(
        backtest_id: str,
        config: BacktestConfig,
        duration_days: int
    ) -> List[TradeRecord]:
        """Generate trades for trend following strategy"""
        
        trades = []
        current_time = config.start_date
        balance = config.initial_balance
        
        # Trend following: 45-55% win rate, but winners are 2-3x losers
        num_trades = random.randint(15, 30)
        
        for i in range(num_trades):
            is_winner = random.random() < 0.50  # 50% win rate
            
            # Entry
            entry_time = current_time + timedelta(hours=random.randint(12, 72))
            direction = random.choice([TradeDirection.BUY, TradeDirection.SELL])
            entry_price = 1.1000 + random.uniform(-0.0100, 0.0100)
            
            # Position size (2% risk)
            volume = 0.1
            position_size = volume * 100000  # Standard lot
            
            # Exit
            if is_winner:
                # Winners: 2-4% gain
                pips = random.uniform(40, 120)
                duration = random.randint(8, 48)  # 8-48 hours
            else:
                # Losers: 1-2% loss
                pips = random.uniform(-30, -15)
                duration = random.randint(2, 12)  # 2-12 hours
            
            exit_time = entry_time + timedelta(hours=duration)
            profit_loss = pips * 10 * volume  # $10 per pip per 0.1 lot
            exit_price = entry_price + (pips * 0.0001)
            
            # Stop loss and take profit
            sl = entry_price - (0.0030 if direction == TradeDirection.BUY else -0.0030)
            tp = entry_price + (0.0080 if direction == TradeDirection.BUY else -0.0080)
            
            trade = TradeRecord(
                id=str(uuid.uuid4()),
                backtest_id=backtest_id,
                entry_time=entry_time,
                exit_time=exit_time,
                symbol=config.symbol,
                direction=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                stop_loss=sl,
                take_profit=tp,
                volume=volume,
                position_size=position_size,
                profit_loss=profit_loss,
                profit_loss_pips=pips,
                profit_loss_percent=(profit_loss / balance) * 100,
                duration_minutes=duration * 60,
                commission=config.commission_per_lot * volume,
                status=TradeStatus.CLOSED,
                close_reason="take_profit" if is_winner else "stop_loss"
            )
            
            trades.append(trade)
            balance += profit_loss
            current_time = exit_time
        
        return trades
    
    @staticmethod
    def _generate_mean_reversion_trades(
        backtest_id: str,
        config: BacktestConfig,
        duration_days: int
    ) -> List[TradeRecord]:
        """Generate trades for mean reversion strategy"""
        
        trades = []
        current_time = config.start_date
        balance = config.initial_balance
        
        # Mean reversion: 60-70% win rate, smaller wins
        num_trades = random.randint(40, 60)
        
        for i in range(num_trades):
            is_winner = random.random() < 0.65  # 65% win rate
            
            entry_time = current_time + timedelta(hours=random.randint(6, 24))
            direction = random.choice([TradeDirection.BUY, TradeDirection.SELL])
            entry_price = 1.1000 + random.uniform(-0.0050, 0.0050)
            volume = 0.1
            position_size = volume * 100000
            
            if is_winner:
                pips = random.uniform(10, 25)  # Small wins
                duration = random.randint(2, 8)
            else:
                pips = random.uniform(-15, -30)  # Larger losses
                duration = random.randint(1, 6)
            
            exit_time = entry_time + timedelta(hours=duration)
            profit_loss = pips * 10 * volume
            exit_price = entry_price + (pips * 0.0001)
            
            sl = entry_price - (0.0035 if direction == TradeDirection.BUY else -0.0035)
            tp = entry_price + (0.0025 if direction == TradeDirection.BUY else -0.0025)
            
            trade = TradeRecord(
                id=str(uuid.uuid4()),
                backtest_id=backtest_id,
                entry_time=entry_time,
                exit_time=exit_time,
                symbol=config.symbol,
                direction=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                stop_loss=sl,
                take_profit=tp,
                volume=volume,
                position_size=position_size,
                profit_loss=profit_loss,
                profit_loss_pips=pips,
                profit_loss_percent=(profit_loss / balance) * 100,
                duration_minutes=duration * 60,
                commission=config.commission_per_lot * volume,
                status=TradeStatus.CLOSED,
                close_reason="take_profit" if is_winner else "stop_loss"
            )
            
            trades.append(trade)
            balance += profit_loss
            current_time = exit_time
        
        return trades
    
    @staticmethod
    def _generate_breakout_trades(
        backtest_id: str,
        config: BacktestConfig,
        duration_days: int
    ) -> List[TradeRecord]:
        """Generate trades for breakout strategy"""
        
        trades = []
        current_time = config.start_date
        balance = config.initial_balance
        
        num_trades = random.randint(20, 35)
        
        for i in range(num_trades):
            is_winner = random.random() < 0.48  # 48% win rate, but big wins
            
            entry_time = current_time + timedelta(hours=random.randint(12, 48))
            direction = random.choice([TradeDirection.BUY, TradeDirection.SELL])
            entry_price = 1.1000 + random.uniform(-0.0080, 0.0080)
            volume = 0.1
            position_size = volume * 100000
            
            if is_winner:
                pips = random.uniform(60, 150)  # Big wins
                duration = random.randint(12, 72)
            else:
                pips = random.uniform(-25, -10)  # Small losses
                duration = random.randint(1, 8)
            
            exit_time = entry_time + timedelta(hours=duration)
            profit_loss = pips * 10 * volume
            exit_price = entry_price + (pips * 0.0001)
            
            sl = entry_price - (0.0028 if direction == TradeDirection.BUY else -0.0028)
            tp = entry_price + (0.0120 if direction == TradeDirection.BUY else -0.0120)
            
            trade = TradeRecord(
                id=str(uuid.uuid4()),
                backtest_id=backtest_id,
                entry_time=entry_time,
                exit_time=exit_time,
                symbol=config.symbol,
                direction=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                stop_loss=sl,
                take_profit=tp,
                volume=volume,
                position_size=position_size,
                profit_loss=profit_loss,
                profit_loss_pips=pips,
                profit_loss_percent=(profit_loss / balance) * 100,
                duration_minutes=duration * 60,
                commission=config.commission_per_lot * volume,
                status=TradeStatus.CLOSED,
                close_reason="take_profit" if is_winner else "stop_loss"
            )
            
            trades.append(trade)
            balance += profit_loss
            current_time = exit_time
        
        return trades
    
    @staticmethod
    def _generate_scalping_trades(
        backtest_id: str,
        config: BacktestConfig,
        duration_days: int
    ) -> List[TradeRecord]:
        """Generate trades for scalping strategy"""
        
        trades = []
        current_time = config.start_date
        balance = config.initial_balance
        
        num_trades = random.randint(100, 150)  # High frequency
        
        for i in range(num_trades):
            is_winner = random.random() < 0.58  # 58% win rate
            
            entry_time = current_time + timedelta(minutes=random.randint(30, 180))
            direction = random.choice([TradeDirection.BUY, TradeDirection.SELL])
            entry_price = 1.1000 + random.uniform(-0.0030, 0.0030)
            volume = 0.1
            position_size = volume * 100000
            
            if is_winner:
                pips = random.uniform(5, 12)  # Small wins
                duration = random.randint(15, 90)  # Minutes
            else:
                pips = random.uniform(-8, -4)  # Small losses
                duration = random.randint(10, 60)
            
            exit_time = entry_time + timedelta(minutes=duration)
            profit_loss = pips * 10 * volume
            exit_price = entry_price + (pips * 0.0001)
            
            sl = entry_price - (0.0010 if direction == TradeDirection.BUY else -0.0010)
            tp = entry_price + (0.0012 if direction == TradeDirection.BUY else -0.0012)
            
            trade = TradeRecord(
                id=str(uuid.uuid4()),
                backtest_id=backtest_id,
                entry_time=entry_time,
                exit_time=exit_time,
                symbol=config.symbol,
                direction=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                stop_loss=sl,
                take_profit=tp,
                volume=volume,
                position_size=position_size,
                profit_loss=profit_loss,
                profit_loss_pips=pips,
                profit_loss_percent=(profit_loss / balance) * 100,
                duration_minutes=duration,
                commission=config.commission_per_lot * volume,
                status=TradeStatus.CLOSED,
                close_reason="take_profit" if is_winner else "stop_loss"
            )
            
            trades.append(trade)
            balance += profit_loss
            current_time = exit_time
        
        return trades
    
    @staticmethod
    def _generate_generic_trades(
        backtest_id: str,
        config: BacktestConfig,
        duration_days: int
    ) -> List[TradeRecord]:
        """Generate generic trades"""
        return MockBacktestGenerator._generate_trend_following_trades(
            backtest_id, config, duration_days
        )
    
    @staticmethod
    def _generate_equity_curve(
        trades: List[TradeRecord],
        initial_balance: float
    ) -> List[EquityPoint]:
        """Generate equity curve from trade history"""
        
        equity_curve = []
        balance = initial_balance
        peak = initial_balance
        
        # Starting point
        if trades:
            equity_curve.append(EquityPoint(
                timestamp=trades[0].entry_time,
                balance=balance,
                equity=balance,
                drawdown=0.0,
                drawdown_percent=0.0
            ))
        
        # Track equity after each trade
        for trade in trades:
            if trade.profit_loss:
                balance += trade.profit_loss
                
                if balance > peak:
                    peak = balance
                
                drawdown = peak - balance
                drawdown_pct = (drawdown / peak * 100) if peak > 0 else 0
                
                equity_curve.append(EquityPoint(
                    timestamp=trade.exit_time,
                    balance=balance,
                    equity=balance,
                    drawdown=drawdown,
                    drawdown_percent=drawdown_pct
                ))
        
        return equity_curve


# Singleton instance
mock_generator = MockBacktestGenerator()
