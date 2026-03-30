#!/usr/bin/env python3
"""
PHASE 1: RISK OPTIMIZATION - Individual Testing
Test each risk control separately, then combine best configurations

TARGET: Reduce DD from 54% to <25% while maintaining PF >= 2.0

Risk Controls to Test:
1. Risk Per Trade: 1% -> 0.75% -> 0.5%
2. Max Concurrent Trades: 3-5 limit
3. Equity-Based Scaling: Reduce size during drawdown
4. Loss Protection: Daily (3%) and Weekly (8%) caps
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Output directories
OUTPUT_DIR = "/app/trading_strategy/trading_system/backend/risk_optimization_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)


@dataclass
class BacktestConfig:
    """Backtest configuration"""
    initial_balance: float = 10000
    risk_per_trade_pct: float = 1.0
    spread_pips: float = 2.0
    slippage_pips: float = 1.0
    commission_per_lot: float = 7.0
    max_position_size: float = 0.5  # Max lot size for gold


@dataclass
class RiskConfig:
    """Risk management configuration"""
    name: str
    base_risk_pct: float = 1.0
    max_concurrent_trades: int = 999  # No limit by default
    equity_scaling_enabled: bool = False
    equity_scaling_threshold_10: float = 0.5   # Reduce to 50% at 10% DD
    equity_scaling_threshold_20: float = 0.25  # Reduce to 25% at 20% DD
    daily_loss_cap_pct: float = 999.0  # No cap by default
    weekly_loss_cap_pct: float = 999.0  # No cap by default


@dataclass
class Trade:
    """Individual trade record"""
    entry_time: datetime
    exit_time: datetime
    direction: str
    entry_price: float
    exit_price: float
    profit_pips: float
    profit_usd: float
    position_size: float
    duration_hours: float
    exit_reason: str


@dataclass
class BacktestResult:
    """Backtest results"""
    config_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_profit: float
    total_loss: float
    net_profit: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    avg_win: float
    avg_loss: float
    avg_trade: float
    equity_curve: List[float]
    trades: List[Trade]
    
    def to_dict(self):
        return {
            "config_name": self.config_name,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "net_profit": round(self.net_profit, 2),
            "profit_factor": round(self.profit_factor, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "avg_trade": round(self.avg_trade, 2)
        }


def generate_synthetic_xauusd_data(candles: int = 5000) -> pd.DataFrame:
    """
    Generate realistic XAUUSD H1 data for backtesting.
    Uses mean-reverting price action typical of gold.
    """
    np.random.seed(42)  # Reproducibility
    
    # Start from realistic gold price
    base_price = 1950.0
    
    # Generate timestamps (H1 candles, skip weekends)
    start_date = datetime(2024, 1, 1, 0, 0)
    timestamps = []
    current = start_date
    while len(timestamps) < candles:
        # Skip weekends
        if current.weekday() < 5:  # Monday to Friday
            timestamps.append(current)
        current += timedelta(hours=1)
    
    # Generate price movements with mean-reversion characteristics
    prices = [base_price]
    volatility = 0.0008  # ~0.08% per hour volatility
    mean_reversion_strength = 0.02
    
    for i in range(1, candles):
        # Mean reversion component
        deviation = (prices[-1] - base_price) / base_price
        mean_reversion = -mean_reversion_strength * deviation
        
        # Random component with occasional spikes
        random_move = np.random.normal(0, volatility)
        
        # Occasional volatility spikes (news events)
        if np.random.random() < 0.02:
            random_move *= 3
        
        # Calculate new price
        price_change = prices[-1] * (mean_reversion + random_move)
        new_price = prices[-1] + price_change
        
        # Keep within realistic bounds
        new_price = max(1800, min(2100, new_price))
        prices.append(new_price)
    
    # Generate OHLC from close prices
    data = []
    for i, (ts, close) in enumerate(zip(timestamps, prices)):
        # Generate realistic OHLC spread
        volatility_factor = np.random.uniform(0.001, 0.004)
        high = close * (1 + volatility_factor * np.random.uniform(0.3, 1.0))
        low = close * (1 - volatility_factor * np.random.uniform(0.3, 1.0))
        
        # Open is close of previous candle with small gap
        if i > 0:
            open_price = prices[i-1] * (1 + np.random.uniform(-0.0005, 0.0005))
        else:
            open_price = close * (1 + np.random.uniform(-0.001, 0.001))
        
        # Ensure OHLC consistency
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        
        data.append({
            'time': ts,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': np.random.uniform(1000, 5000)
        })
    
    df = pd.DataFrame(data)
    df['time'] = pd.to_datetime(df['time'])
    df = df.set_index('time')
    
    return df


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate technical indicators for mean reversion strategy"""
    
    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(20).mean()
    df['bb_std'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ATR for stop loss calculation
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    df['atr'] = df['tr'].rolling(14).mean()
    
    # Session (simplified)
    df['hour'] = df.index.hour
    
    return df


def generate_mean_reversion_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Generate mean reversion entry/exit signals"""
    
    df = df.copy()
    df['signal'] = 0
    
    # Entry signals
    # Long: Price at/below lower BB
    df.loc[df['close'] <= df['bb_lower'], 'signal'] = 1
    
    # Short: Price at/above upper BB
    df.loc[df['close'] >= df['bb_upper'], 'signal'] = -1
    
    # Track position changes
    df['position'] = df['signal'].diff()
    
    return df


class RiskManagedBacktester:
    """Backtester with configurable risk management"""
    
    def __init__(self, data: pd.DataFrame, backtest_config: BacktestConfig):
        self.data = data.copy()
        self.config = backtest_config
        self.pip_size = 1.0  # Gold: 1 point = 1 pip
        
    def calculate_position_size(
        self, 
        stop_loss_points: float, 
        current_balance: float,
        risk_pct: float
    ) -> float:
        """Calculate position size based on risk"""
        risk_amount = current_balance * (risk_pct / 100)
        
        # Gold: $100 per lot per point
        stop_loss_value_per_lot = stop_loss_points * 100.0
        
        if stop_loss_value_per_lot > 0:
            position_size = risk_amount / stop_loss_value_per_lot
        else:
            position_size = 0.01
        
        # Apply limits
        position_size = min(position_size, self.config.max_position_size)
        position_size = max(position_size, 0.01)
        
        return round(position_size, 2)
    
    def run_backtest(
        self, 
        signals_df: pd.DataFrame, 
        risk_config: RiskConfig
    ) -> BacktestResult:
        """
        Run backtest with specific risk configuration
        """
        df = signals_df.copy()
        
        trades = []
        equity = [self.config.initial_balance]
        current_balance = self.config.initial_balance
        peak_balance = self.config.initial_balance
        
        # Position tracking
        open_positions = []
        
        # Loss tracking
        daily_pnl = {}
        weekly_pnl = {}
        trades_today = {}
        
        for i in range(len(df)):
            if pd.isna(df.iloc[i].get('atr')) or i < 20:
                continue
            
            current_time = df.index[i]
            current_date = current_time.date()
            current_week = current_time.isocalendar()[1]
            
            # Reset daily counter
            if current_date not in trades_today:
                trades_today[current_date] = 0
            
            # Calculate current drawdown for equity scaling
            current_dd_pct = 0
            if peak_balance > 0:
                current_dd_pct = ((peak_balance - current_balance) / peak_balance) * 100
            
            # Determine effective risk based on equity scaling
            effective_risk = risk_config.base_risk_pct
            if risk_config.equity_scaling_enabled:
                if current_dd_pct > 20:
                    effective_risk = risk_config.base_risk_pct * risk_config.equity_scaling_threshold_20
                elif current_dd_pct > 10:
                    effective_risk = risk_config.base_risk_pct * risk_config.equity_scaling_threshold_10
            
            # Check loss caps
            daily_loss = daily_pnl.get(current_date, 0)
            weekly_loss = weekly_pnl.get(current_week, 0)
            
            daily_limit_hit = daily_loss < -(self.config.initial_balance * risk_config.daily_loss_cap_pct / 100)
            weekly_limit_hit = weekly_loss < -(self.config.initial_balance * risk_config.weekly_loss_cap_pct / 100)
            
            # Entry logic
            if df.iloc[i].get('position', 0) != 0 and len(open_positions) < risk_config.max_concurrent_trades:
                
                # Skip if loss limits hit
                if daily_limit_hit or weekly_limit_hit:
                    continue
                
                # Calculate stop loss
                atr = df.iloc[i]['atr']
                stop_loss_distance = min(atr * 1.5, 50.0)  # Cap at 50 points
                
                # Calculate position size
                position_size = self.calculate_position_size(
                    stop_loss_distance, 
                    current_balance,
                    effective_risk
                )
                
                # Entry price with spread
                entry_price = df.iloc[i]['close']
                direction = 'long' if df.iloc[i]['position'] > 0 else 'short'
                
                if direction == 'long':
                    entry_price += self.config.spread_pips
                else:
                    entry_price -= self.config.spread_pips
                
                position = {
                    'direction': direction,
                    'entry_time': current_time,
                    'entry_price': entry_price,
                    'entry_idx': i,
                    'position_size': position_size,
                    'stop_loss_distance': stop_loss_distance,
                    'target': df.iloc[i]['bb_middle']
                }
                
                open_positions.append(position)
                trades_today[current_date] += 1
            
            # Exit management for all open positions
            positions_to_close = []
            
            for pos_idx, pos in enumerate(open_positions):
                should_exit = False
                exit_reason = "signal"
                exit_price = df.iloc[i]['close']
                
                # Calculate current P&L
                if pos['direction'] == 'long':
                    current_pnl = (df.iloc[i]['close'] - pos['entry_price']) * pos['position_size'] * 100
                    stop_price = pos['entry_price'] - pos['stop_loss_distance']
                    
                    # Check stop loss
                    if df.iloc[i]['low'] <= stop_price:
                        should_exit = True
                        exit_reason = "stop_loss"
                        exit_price = stop_price
                    
                    # Check target (middle BB)
                    elif df.iloc[i]['high'] >= pos['target']:
                        should_exit = True
                        exit_reason = "target"
                        exit_price = pos['target']
                
                else:  # Short
                    current_pnl = (pos['entry_price'] - df.iloc[i]['close']) * pos['position_size'] * 100
                    stop_price = pos['entry_price'] + pos['stop_loss_distance']
                    
                    # Check stop loss
                    if df.iloc[i]['high'] >= stop_price:
                        should_exit = True
                        exit_reason = "stop_loss"
                        exit_price = stop_price
                    
                    # Check target (middle BB)
                    elif df.iloc[i]['low'] <= pos['target']:
                        should_exit = True
                        exit_reason = "target"
                        exit_price = pos['target']
                
                # Max holding period (48 hours)
                hold_duration = i - pos['entry_idx']
                if hold_duration >= 48:
                    should_exit = True
                    exit_reason = "timeout"
                
                if should_exit:
                    positions_to_close.append(pos_idx)
                    
                    # Calculate final P&L
                    if pos['direction'] == 'long':
                        profit_points = exit_price - pos['entry_price']
                    else:
                        profit_points = pos['entry_price'] - exit_price
                    
                    profit_usd = profit_points * pos['position_size'] * 100
                    profit_usd -= self.config.commission_per_lot * pos['position_size']
                    
                    # Update balance
                    current_balance += profit_usd
                    if current_balance > peak_balance:
                        peak_balance = current_balance
                    
                    # Track daily/weekly P&L
                    daily_pnl[current_date] = daily_pnl.get(current_date, 0) + profit_usd
                    weekly_pnl[current_week] = weekly_pnl.get(current_week, 0) + profit_usd
                    
                    # Record trade
                    trade = Trade(
                        entry_time=pos['entry_time'],
                        exit_time=current_time,
                        direction=pos['direction'],
                        entry_price=pos['entry_price'],
                        exit_price=exit_price,
                        profit_pips=profit_points,
                        profit_usd=profit_usd,
                        position_size=pos['position_size'],
                        duration_hours=hold_duration,
                        exit_reason=exit_reason
                    )
                    trades.append(trade)
                    equity.append(current_balance)
            
            # Remove closed positions
            for idx in reversed(positions_to_close):
                open_positions.pop(idx)
        
        # Calculate metrics
        return self._calculate_metrics(trades, equity, risk_config.name)
    
    def _calculate_metrics(
        self, 
        trades: List[Trade], 
        equity: List[float],
        config_name: str
    ) -> BacktestResult:
        """Calculate backtest metrics"""
        
        if not trades:
            return self._empty_result(config_name)
        
        winning = [t for t in trades if t.profit_usd > 0]
        losing = [t for t in trades if t.profit_usd <= 0]
        
        total_profit = sum(t.profit_usd for t in winning) if winning else 0
        total_loss = sum(t.profit_usd for t in losing) if losing else 0
        
        profit_factor = abs(total_profit / total_loss) if total_loss != 0 else 0
        
        # Drawdown
        equity_array = np.array(equity)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = running_max - equity_array
        max_drawdown = np.max(drawdown)
        max_drawdown_pct = (max_drawdown / self.config.initial_balance) * 100
        
        # Sharpe ratio
        if len(equity_array) > 1:
            returns = np.diff(equity_array) / equity_array[:-1]
            sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252 * 24) if np.std(returns) > 0 else 0
        else:
            sharpe = 0
        
        return BacktestResult(
            config_name=config_name,
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=len(winning) / len(trades) * 100 if trades else 0,
            total_profit=total_profit,
            total_loss=total_loss,
            net_profit=total_profit + total_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe,
            avg_win=np.mean([t.profit_usd for t in winning]) if winning else 0,
            avg_loss=np.mean([t.profit_usd for t in losing]) if losing else 0,
            avg_trade=np.mean([t.profit_usd for t in trades]) if trades else 0,
            equity_curve=equity,
            trades=trades
        )
    
    def _empty_result(self, config_name: str) -> BacktestResult:
        return BacktestResult(
            config_name=config_name,
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
            equity_curve=[self.config.initial_balance],
            trades=[]
        )


def plot_equity_curves(results: Dict[str, BacktestResult], filename: str):
    """Generate equity curve comparison plots"""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Equity Curves Comparison', 'Drawdown Comparison'),
            row_heights=[0.6, 0.4],
            vertical_spacing=0.12
        )
        
        colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B', '#95190C']
        
        for idx, (name, result) in enumerate(results.items()):
            color = colors[idx % len(colors)]
            
            # Equity curve
            fig.add_trace(
                go.Scatter(
                    y=result.equity_curve,
                    name=f"{name} (PF: {result.profit_factor:.2f}, DD: {result.max_drawdown_pct:.1f}%)",
                    line=dict(color=color, width=2),
                    hovertemplate=f"{name}<br>Equity: $%{{y:,.2f}}<extra></extra>"
                ),
                row=1, col=1
            )
            
            # Drawdown curve
            equity = np.array(result.equity_curve)
            running_max = np.maximum.accumulate(equity)
            dd_pct = (running_max - equity) / running_max * 100
            
            fig.add_trace(
                go.Scatter(
                    y=-dd_pct,
                    name=f"{name} DD",
                    line=dict(color=color, width=1),
                    fill='tozeroy',
                    fillcolor=f'rgba{tuple(list(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + [0.2])}',
                    showlegend=False
                ),
                row=2, col=1
            )
        
        fig.update_layout(
            title="Phase 1: Risk Optimization - Equity Curve Comparison",
            height=800,
            template="plotly_white",
            legend=dict(x=0.02, y=0.98, bgcolor='rgba(255,255,255,0.8)')
        )
        
        fig.update_yaxes(title_text="Equity ($)", row=1, col=1)
        fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
        
        # Save as HTML
        fig.write_html(f"{OUTPUT_DIR}/{filename}.html")
        
        # Save as PNG
        try:
            fig.write_image(f"{OUTPUT_DIR}/{filename}.png", width=1200, height=800)
        except Exception as e:
            logger.warning(f"Could not save PNG: {e}")
        
        logger.info(f"Saved equity curves to {OUTPUT_DIR}/{filename}")
        
    except ImportError:
        logger.warning("Plotly not available, skipping chart generation")


def run_phase1_optimization():
    """
    PHASE 1: Test each risk control individually
    """
    print("\n" + "="*80)
    print("PHASE 1: RISK OPTIMIZATION - INDIVIDUAL TESTING")
    print("="*80)
    print("\nTARGET: Reduce DD from 54% to <25%, maintain PF >= 2.0")
    
    # Generate data
    print("\n📊 Generating XAUUSD H1 test data...")
    df = generate_synthetic_xauusd_data(5000)
    df = calculate_indicators(df)
    signals_df = generate_mean_reversion_signals(df)
    
    print(f"   Data range: {df.index[0]} to {df.index[-1]}")
    print(f"   Total candles: {len(df)}")
    
    # Backtest configuration
    backtest_config = BacktestConfig(
        initial_balance=10000,
        spread_pips=2.0,
        slippage_pips=1.0,
        commission_per_lot=7.0,
        max_position_size=0.5
    )
    
    backtester = RiskManagedBacktester(df, backtest_config)
    
    results = {}
    
    # ========================================
    # TEST 1: BASELINE (1% Risk)
    # ========================================
    print("\n" + "-"*60)
    print("TEST 1: BASELINE (1% Risk, No Controls)")
    print("-"*60)
    
    baseline_config = RiskConfig(
        name="BASELINE (1% Risk)",
        base_risk_pct=1.0,
        max_concurrent_trades=999,
        equity_scaling_enabled=False,
        daily_loss_cap_pct=999,
        weekly_loss_cap_pct=999
    )
    
    results["Baseline_1pct"] = backtester.run_backtest(signals_df, baseline_config)
    print_result(results["Baseline_1pct"])
    
    # ========================================
    # TEST 2: REDUCED RISK (0.75%)
    # ========================================
    print("\n" + "-"*60)
    print("TEST 2: REDUCED RISK (0.75%)")
    print("-"*60)
    
    config_075 = RiskConfig(
        name="Risk 0.75%",
        base_risk_pct=0.75,
        max_concurrent_trades=999,
        equity_scaling_enabled=False,
        daily_loss_cap_pct=999,
        weekly_loss_cap_pct=999
    )
    
    results["Risk_075pct"] = backtester.run_backtest(signals_df, config_075)
    print_result(results["Risk_075pct"])
    
    # ========================================
    # TEST 3: REDUCED RISK (0.5%)
    # ========================================
    print("\n" + "-"*60)
    print("TEST 3: REDUCED RISK (0.5%)")
    print("-"*60)
    
    config_05 = RiskConfig(
        name="Risk 0.5%",
        base_risk_pct=0.5,
        max_concurrent_trades=999,
        equity_scaling_enabled=False,
        daily_loss_cap_pct=999,
        weekly_loss_cap_pct=999
    )
    
    results["Risk_05pct"] = backtester.run_backtest(signals_df, config_05)
    print_result(results["Risk_05pct"])
    
    # ========================================
    # TEST 4: MAX CONCURRENT TRADES (3)
    # ========================================
    print("\n" + "-"*60)
    print("TEST 4: MAX CONCURRENT TRADES = 3")
    print("-"*60)
    
    config_max3 = RiskConfig(
        name="Max 3 Concurrent",
        base_risk_pct=1.0,
        max_concurrent_trades=3,
        equity_scaling_enabled=False,
        daily_loss_cap_pct=999,
        weekly_loss_cap_pct=999
    )
    
    results["Max_3_Concurrent"] = backtester.run_backtest(signals_df, config_max3)
    print_result(results["Max_3_Concurrent"])
    
    # ========================================
    # TEST 5: MAX CONCURRENT TRADES (5)
    # ========================================
    print("\n" + "-"*60)
    print("TEST 5: MAX CONCURRENT TRADES = 5")
    print("-"*60)
    
    config_max5 = RiskConfig(
        name="Max 5 Concurrent",
        base_risk_pct=1.0,
        max_concurrent_trades=5,
        equity_scaling_enabled=False,
        daily_loss_cap_pct=999,
        weekly_loss_cap_pct=999
    )
    
    results["Max_5_Concurrent"] = backtester.run_backtest(signals_df, config_max5)
    print_result(results["Max_5_Concurrent"])
    
    # ========================================
    # TEST 6: EQUITY-BASED SCALING
    # ========================================
    print("\n" + "-"*60)
    print("TEST 6: EQUITY-BASED SCALING")
    print("-"*60)
    print("   DD > 10% -> Reduce to 50% size")
    print("   DD > 20% -> Reduce to 25% size")
    
    config_scaling = RiskConfig(
        name="Equity Scaling",
        base_risk_pct=1.0,
        max_concurrent_trades=999,
        equity_scaling_enabled=True,
        equity_scaling_threshold_10=0.5,
        equity_scaling_threshold_20=0.25,
        daily_loss_cap_pct=999,
        weekly_loss_cap_pct=999
    )
    
    results["Equity_Scaling"] = backtester.run_backtest(signals_df, config_scaling)
    print_result(results["Equity_Scaling"])
    
    # ========================================
    # TEST 7: DAILY LOSS CAP (3%)
    # ========================================
    print("\n" + "-"*60)
    print("TEST 7: DAILY LOSS CAP (3%)")
    print("-"*60)
    
    config_daily = RiskConfig(
        name="Daily Cap 3%",
        base_risk_pct=1.0,
        max_concurrent_trades=999,
        equity_scaling_enabled=False,
        daily_loss_cap_pct=3.0,
        weekly_loss_cap_pct=999
    )
    
    results["Daily_Cap_3pct"] = backtester.run_backtest(signals_df, config_daily)
    print_result(results["Daily_Cap_3pct"])
    
    # ========================================
    # TEST 8: WEEKLY LOSS CAP (8%)
    # ========================================
    print("\n" + "-"*60)
    print("TEST 8: WEEKLY LOSS CAP (8%)")
    print("-"*60)
    
    config_weekly = RiskConfig(
        name="Weekly Cap 8%",
        base_risk_pct=1.0,
        max_concurrent_trades=999,
        equity_scaling_enabled=False,
        daily_loss_cap_pct=999,
        weekly_loss_cap_pct=8.0
    )
    
    results["Weekly_Cap_8pct"] = backtester.run_backtest(signals_df, config_weekly)
    print_result(results["Weekly_Cap_8pct"])
    
    # ========================================
    # TEST 9: DAILY + WEEKLY CAPS
    # ========================================
    print("\n" + "-"*60)
    print("TEST 9: DAILY (3%) + WEEKLY (8%) CAPS")
    print("-"*60)
    
    config_caps = RiskConfig(
        name="Daily 3% + Weekly 8%",
        base_risk_pct=1.0,
        max_concurrent_trades=999,
        equity_scaling_enabled=False,
        daily_loss_cap_pct=3.0,
        weekly_loss_cap_pct=8.0
    )
    
    results["Loss_Caps"] = backtester.run_backtest(signals_df, config_caps)
    print_result(results["Loss_Caps"])
    
    # ========================================
    # COMPARISON SUMMARY
    # ========================================
    print("\n" + "="*80)
    print("📊 PHASE 1 RESULTS COMPARISON")
    print("="*80)
    
    comparison_data = []
    for name, result in results.items():
        comparison_data.append({
            "Config": name,
            "Trades": result.total_trades,
            "Win Rate": f"{result.win_rate:.1f}%",
            "PF": f"{result.profit_factor:.2f}",
            "Net Profit": f"${result.net_profit:,.0f}",
            "Max DD": f"{result.max_drawdown_pct:.1f}%",
            "Sharpe": f"{result.sharpe_ratio:.2f}",
            "Target Met": "✅" if result.profit_factor >= 2.0 and result.max_drawdown_pct < 25 else "❌"
        })
    
    comparison_df = pd.DataFrame(comparison_data)
    print("\n" + comparison_df.to_string(index=False))
    
    # Identify best performer
    print("\n" + "="*80)
    print("🏆 BEST CONFIGURATIONS BY CRITERIA")
    print("="*80)
    
    # Best drawdown reduction
    best_dd = min(results.items(), key=lambda x: x[1].max_drawdown_pct)
    print(f"\n✅ LOWEST DRAWDOWN: {best_dd[0]}")
    print(f"   DD: {best_dd[1].max_drawdown_pct:.1f}% | PF: {best_dd[1].profit_factor:.2f}")
    
    # Best profit factor maintaining DD target
    valid_configs = [(k, v) for k, v in results.items() if v.max_drawdown_pct < 25]
    if valid_configs:
        best_pf = max(valid_configs, key=lambda x: x[1].profit_factor)
        print(f"\n✅ BEST PF (DD < 25%): {best_pf[0]}")
        print(f"   PF: {best_pf[1].profit_factor:.2f} | DD: {best_pf[1].max_drawdown_pct:.1f}%")
    
    # Overall best balanced
    scores = []
    for name, result in results.items():
        score = 0
        if result.profit_factor >= 2.0:
            score += 3
        elif result.profit_factor >= 1.5:
            score += 1
        
        if result.max_drawdown_pct < 20:
            score += 3
        elif result.max_drawdown_pct < 25:
            score += 2
        elif result.max_drawdown_pct < 30:
            score += 1
        
        if result.net_profit > 0:
            score += 1
        
        scores.append((name, score, result))
    
    scores.sort(key=lambda x: (x[1], x[2].profit_factor), reverse=True)
    best_overall = scores[0]
    
    print(f"\n🏆 BEST OVERALL: {best_overall[0]}")
    print(f"   Score: {best_overall[1]}/7")
    print(f"   PF: {best_overall[2].profit_factor:.2f}")
    print(f"   DD: {best_overall[2].max_drawdown_pct:.1f}%")
    print(f"   Net Profit: ${best_overall[2].net_profit:,.2f}")
    
    # Generate charts
    print("\n📈 Generating equity curve charts...")
    plot_equity_curves(results, "phase1_equity_comparison")
    
    # Save results to JSON
    results_json = {name: result.to_dict() for name, result in results.items()}
    results_json["best_config"] = best_overall[0]
    results_json["analysis_timestamp"] = datetime.now().isoformat()
    
    with open(f"{OUTPUT_DIR}/phase1_results.json", 'w') as f:
        json.dump(results_json, f, indent=2)
    
    print(f"\n📁 Results saved to {OUTPUT_DIR}/")
    
    print("\n" + "="*80)
    print("✅ PHASE 1 COMPLETE")
    print("="*80)
    
    return results


def print_result(result: BacktestResult):
    """Print formatted result"""
    print(f"\n   📊 {result.config_name}")
    print(f"   Trades: {result.total_trades} | Win Rate: {result.win_rate:.1f}%")
    print(f"   PF: {result.profit_factor:.2f} | Net: ${result.net_profit:,.2f}")
    print(f"   Max DD: {result.max_drawdown_pct:.1f}% | Sharpe: {result.sharpe_ratio:.2f}")
    
    # Target check
    pf_ok = "✅" if result.profit_factor >= 2.0 else "❌"
    dd_ok = "✅" if result.max_drawdown_pct < 25 else "❌"
    print(f"   Target: PF >= 2.0 {pf_ok} | DD < 25% {dd_ok}")


if __name__ == "__main__":
    results = run_phase1_optimization()
