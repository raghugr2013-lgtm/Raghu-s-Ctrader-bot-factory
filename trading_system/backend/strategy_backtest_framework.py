#!/usr/bin/env python3
"""
Comprehensive Strategy Backtesting & Optimization
Tasks 2-7: Baseline testing, diagnostics, optimization, and reporting
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple
import json
from dataclasses import dataclass, asdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Backtest configuration"""
    initial_balance: float = 10000
    position_size: float = 0.01  # lot size
    spread_pips: float = 2.0
    slippage_pips: float = 1.0
    commission_per_lot: float = 7.0
    

@dataclass
class Trade:
    """Individual trade record"""
    entry_time: datetime
    exit_time: datetime
    direction: str  # 'long' or 'short'
    entry_price: float
    exit_price: float
    profit_pips: float
    profit_usd: float
    duration_hours: float
    session: str  # 'asian', 'london', 'newyork'


@dataclass
class BacktestResult:
    """Backtest results"""
    symbol: str
    strategy_name: str
    config: BacktestConfig
    
    # Core metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # P&L
    total_profit: float
    total_loss: float
    net_profit: float
    profit_factor: float
    
    # Risk metrics
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    
    # Trade stats
    avg_win: float
    avg_loss: float
    avg_trade: float
    largest_win: float
    largest_loss: float
    
    # Duration
    avg_trade_duration_hours: float
    
    # Equity curve
    equity_curve: List[float]
    
    # All trades
    trades: List[Trade]
    
    def to_dict(self):
        """Convert to dictionary"""
        result = asdict(self)
        result['trades'] = [asdict(t) for t in self.trades]
        return result


class SimpleBacktester:
    """Simple vectorized backtester for strategy evaluation"""
    
    def __init__(self, data: pd.DataFrame, config: BacktestConfig, symbol: str):
        """
        Initialize backtester
        
        Args:
            data: OHLC DataFrame with datetime index
            config: Backtest configuration
            symbol: Trading symbol
        """
        self.data = data.copy()
        self.config = config
        self.symbol = symbol
        
        # Calculate pip value
        if 'JPY' in symbol:
            self.pip_value = 0.01
        elif 'XAU' in symbol or 'GOLD' in symbol:
            self.pip_value = 0.1
        else:
            self.pip_value = 0.0001
    
    def calculate_indicators(self):
        """Calculate common indicators"""
        df = self.data
        
        # Moving averages
        df['ema_20'] = df['close'].ewm(span=20).mean()
        df['ema_50'] = df['close'].ewm(span=50).mean()
        df['ema_200'] = df['close'].ewm(span=200).mean()
        df['sma_50'] = df['close'].rolling(50).mean()
        df['sma_200'] = df['close'].rolling(200).mean()
        
        # ATR
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr_14'] = df['tr'].rolling(14).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # MACD
        df['ema_12'] = df['close'].ewm(span=12).mean()
        df['ema_26'] = df['close'].ewm(span=26).mean()
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
        
        # Session detection
        df['hour'] = df.index.hour
        df['session'] = df['hour'].apply(self._get_session)
        
        self.data = df
        return df
    
    def _get_session(self, hour):
        """Determine trading session"""
        if 0 <= hour < 8:
            return 'asian'
        elif 8 <= hour < 16:
            return 'london'
        else:
            return 'newyork'
    
    def trend_following_strategy(self) -> pd.DataFrame:
        """
        Simple trend following strategy
        Entry: EMA 20 crosses above EMA 50 (long) or below (short)
        Exit: Opposite cross or fixed SL/TP
        """
        df = self.data.copy()
        
        # Generate signals
        df['signal'] = 0
        df.loc[df['ema_20'] > df['ema_50'], 'signal'] = 1  # Long
        df.loc[df['ema_20'] < df['ema_50'], 'signal'] = -1  # Short
        
        # Detect signal changes
        df['position'] = df['signal'].diff()
        
        return df
    
    def mean_reversion_strategy(self) -> pd.DataFrame:
        """
        Mean reversion strategy using Bollinger Bands
        Entry: Price touches lower BB (long) or upper BB (short)
        Exit: Return to middle BB
        """
        df = self.data.copy()
        
        # Generate signals
        df['signal'] = 0
        df.loc[df['close'] <= df['bb_lower'], 'signal'] = 1  # Long at lower band
        df.loc[df['close'] >= df['bb_upper'], 'signal'] = -1  # Short at upper band
        df.loc[(df['close'] >= df['bb_middle']) & (df['signal'].shift(1) == 1), 'signal'] = 0  # Exit long
        df.loc[(df['close'] <= df['bb_middle']) & (df['signal'].shift(1) == -1), 'signal'] = 0  # Exit short
        
        df['position'] = df['signal'].diff()
        
        return df
    
    def execute_backtest(self, signals_df: pd.DataFrame, strategy_name: str) -> BacktestResult:
        """
        Execute backtest based on signals
        
        Args:
            signals_df: DataFrame with 'position' column indicating entry/exit
            strategy_name: Name of the strategy
            
        Returns:
            BacktestResult object
        """
        df = signals_df.copy()
        
        trades = []
        equity = [self.config.initial_balance]
        current_position = None
        
        for i in range(len(df)):
            if pd.isna(df.iloc[i]['position']):
                continue
            
            # Entry signal
            if df.iloc[i]['position'] != 0 and current_position is None:
                current_position = {
                    'direction': 'long' if df.iloc[i]['position'] > 0 else 'short',
                    'entry_time': df.index[i],
                    'entry_price': df.iloc[i]['close'] + (self.config.spread_pips * self.pip_value),
                    'entry_idx': i
                }
            
            # Exit signal (opposite position or timeout)
            elif current_position is not None:
                should_exit = False
                
                # Opposite signal
                if df.iloc[i]['position'] != 0:
                    should_exit = True
                
                # Max holding period (24 hours for H1 = 24 candles)
                if i - current_position['entry_idx'] >= 24:
                    should_exit = True
                
                if should_exit:
                    exit_price = df.iloc[i]['close'] - (self.config.slippage_pips * self.pip_value)
                    exit_time = df.index[i]
                    
                    # Calculate P&L
                    if current_position['direction'] == 'long':
                        profit_pips = (exit_price - current_position['entry_price']) / self.pip_value
                    else:
                        profit_pips = (current_position['entry_price'] - exit_price) / self.pip_value
                    
                    # Convert to USD
                    profit_usd = profit_pips * self.config.position_size * 100000 * self.pip_value
                    profit_usd -= self.config.commission_per_lot * self.config.position_size
                    
                    # Create trade record
                    trade = Trade(
                        entry_time=current_position['entry_time'],
                        exit_time=exit_time,
                        direction=current_position['direction'],
                        entry_price=current_position['entry_price'],
                        exit_price=exit_price,
                        profit_pips=profit_pips,
                        profit_usd=profit_usd,
                        duration_hours=(exit_time - current_position['entry_time']).total_seconds() / 3600,
                        session=df.iloc[i]['session']
                    )
                    
                    trades.append(trade)
                    equity.append(equity[-1] + profit_usd)
                    current_position = None
        
        # Calculate metrics
        if not trades:
            logger.warning(f"No trades generated for {strategy_name}")
            return self._empty_result(strategy_name)
        
        winning_trades = [t for t in trades if t.profit_usd > 0]
        losing_trades = [t for t in trades if t.profit_usd < 0]
        
        total_profit = sum(t.profit_usd for t in winning_trades) if winning_trades else 0
        total_loss = sum(t.profit_usd for t in losing_trades) if losing_trades else 0
        
        profit_factor = abs(total_profit / total_loss) if total_loss != 0 else 0
        
        # Drawdown
        equity_array = np.array(equity)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = running_max - equity_array
        max_drawdown = np.max(drawdown)
        max_drawdown_pct = (max_drawdown / self.config.initial_balance) * 100
        
        # Sharpe ratio (annualized)
        returns = np.diff(equity_array) / equity_array[:-1]
        sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252 * 24) if np.std(returns) > 0 else 0
        
        result = BacktestResult(
            symbol=self.symbol,
            strategy_name=strategy_name,
            config=self.config,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=len(winning_trades) / len(trades) * 100,
            total_profit=total_profit,
            total_loss=total_loss,
            net_profit=total_profit + total_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe,
            avg_win=np.mean([t.profit_usd for t in winning_trades]) if winning_trades else 0,
            avg_loss=np.mean([t.profit_usd for t in losing_trades]) if losing_trades else 0,
            avg_trade=np.mean([t.profit_usd for t in trades]),
            largest_win=max([t.profit_usd for t in winning_trades]) if winning_trades else 0,
            largest_loss=min([t.profit_usd for t in losing_trades]) if losing_trades else 0,
            avg_trade_duration_hours=np.mean([t.duration_hours for t in trades]),
            equity_curve=equity,
            trades=trades
        )
        
        return result
    
    def _empty_result(self, strategy_name):
        """Return empty result when no trades"""
        return BacktestResult(
            symbol=self.symbol,
            strategy_name=strategy_name,
            config=self.config,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0,
            total_profit=0,
            total_loss=0,
            net_profit=0,
            profit_factor=0,
            max_drawdown=0,
            max_drawdown_pct=0,
            sharpe_ratio=0,
            avg_win=0,
            avg_loss=0,
            avg_trade=0,
            largest_win=0,
            largest_loss=0,
            avg_trade_duration_hours=0,
            equity_curve=[self.config.initial_balance],
            trades=[]
        )


def print_backtest_results(result: BacktestResult):
    """Print formatted backtest results"""
    print(f"\n{'='*70}")
    print(f"{result.strategy_name} - {result.symbol}")
    print(f"{'='*70}")
    
    print(f"\n📊 TRADE STATISTICS:")
    print(f"   Total Trades: {result.total_trades}")
    print(f"   Winning: {result.winning_trades} | Losing: {result.losing_trades}")
    print(f"   Win Rate: {result.win_rate:.2f}%")
    
    print(f"\n💰 PROFIT/LOSS:")
    print(f"   Net Profit: ${result.net_profit:.2f}")
    print(f"   Total Profit: ${result.total_profit:.2f}")
    print(f"   Total Loss: ${result.total_loss:.2f}")
    print(f"   Profit Factor: {result.profit_factor:.2f}")
    
    print(f"\n📈 RISK METRICS:")
    print(f"   Max Drawdown: ${result.max_drawdown:.2f} ({result.max_drawdown_pct:.2f}%)")
    print(f"   Sharpe Ratio: {result.sharpe_ratio:.2f}")
    
    print(f"\n🎯 TRADE QUALITY:")
    print(f"   Avg Win: ${result.avg_win:.2f}")
    print(f"   Avg Loss: ${result.avg_loss:.2f}")
    print(f"   Avg Trade: ${result.avg_trade:.2f}")
    print(f"   Largest Win: ${result.largest_win:.2f}")
    print(f"   Largest Loss: ${result.largest_loss:.2f}")
    
    print(f"\n⏱️  DURATION:")
    print(f"   Avg Trade Duration: {result.avg_trade_duration_hours:.1f} hours")
    
    # Target metrics check
    print(f"\n✅ TARGET METRICS:")
    pf_pass = "✅" if result.profit_factor > 1.3 else "❌"
    trades_pass = "✅" if 30 <= result.total_trades <= 60 else "⚠️"
    wr_pass = "✅" if result.win_rate > 40 else "❌"
    dd_pass = "✅" if result.max_drawdown_pct < 20 else "❌"
    
    print(f"   {pf_pass} Profit Factor > 1.3: {result.profit_factor:.2f}")
    print(f"   {trades_pass} Trades 30-60: {result.total_trades}")
    print(f"   {wr_pass} Win Rate > 40%: {result.win_rate:.1f}%")
    print(f"   {dd_pass} Max DD < 20%: {result.max_drawdown_pct:.1f}%")


if __name__ == '__main__':
    # This will be called from the main testing script
    pass
