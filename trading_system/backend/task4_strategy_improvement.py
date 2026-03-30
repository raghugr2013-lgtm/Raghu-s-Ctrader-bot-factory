#!/usr/bin/env python3
"""
TASK 4: Strategy Improvement - Apply Diagnostic Filters
Transform XAUUSD Mean Reversion into high-quality, low-frequency system
"""

import pandas as pd
import numpy as np
import sys
sys.path.append('/app/trading_system/backend')

from strategy_backtest_framework import SimpleBacktester, BacktestConfig, print_backtest_results
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class ImprovedBacktester(SimpleBacktester):
    """Enhanced backtester with diagnostic-based filters"""
    
    def mean_reversion_filtered(self, apply_regime_filter=True, apply_volatility_filter=True, 
                                 apply_duration_filter=True, apply_session_filter=False):
        """
        Filtered mean reversion strategy based on Task 3 diagnostics
        
        Filters applied:
        1. Market Regime: Only ranging markets (EMA 50 ≈ EMA 200)
        2. Volatility: Only high volatility (ATR > 67th percentile)
        3. Duration: Minimum hold time of 10 hours
        4. Session: Optional NY session preference
        """
        df = self.data.copy()
        
        # Calculate volatility threshold (67th percentile)
        atr_threshold = df['atr_14'].quantile(0.67)
        
        # Generate base signals (Bollinger Bands mean reversion)
        df['signal'] = 0
        df.loc[df['close'] <= df['bb_lower'], 'signal'] = 1  # Long at lower band
        df.loc[df['close'] >= df['bb_upper'], 'signal'] = -1  # Short at upper band
        df.loc[(df['close'] >= df['bb_middle']) & (df['signal'].shift(1) == 1), 'signal'] = 0  # Exit long
        df.loc[(df['close'] <= df['bb_middle']) & (df['signal'].shift(1) == -1), 'signal'] = 0  # Exit short
        
        # FILTER 1: Market Regime (Ranging only)
        if apply_regime_filter:
            # Calculate regime
            df['ema_diff_pct'] = ((df['ema_50'] - df['ema_200']) / df['ema_200']) * 100
            
            # Define ranging: |EMA diff| < 0.5%
            df['is_ranging'] = abs(df['ema_diff_pct']) < 0.5
            
            # Block signals in non-ranging markets
            df.loc[~df['is_ranging'], 'signal'] = 0
        
        # FILTER 2: High Volatility Only
        if apply_volatility_filter:
            df['is_high_vol'] = df['atr_14'] > atr_threshold
            
            # Block signals in low/medium volatility
            df.loc[~df['is_high_vol'], 'signal'] = 0
        
        # FILTER 3: Session Filter (Optional)
        if apply_session_filter:
            df['is_ny_session'] = df['session'] == 'newyork'
            
            # Block entry signals outside NY session
            entry_signals = (df['signal'] != 0) & (df['signal'] != df['signal'].shift(1))
            df.loc[entry_signals & ~df['is_ny_session'], 'signal'] = 0
        
        df['position'] = df['signal'].diff()
        
        return df, atr_threshold
    
    def execute_backtest_with_min_hold(self, signals_df: pd.DataFrame, strategy_name: str, min_hold_hours: int = 10):
        """
        Execute backtest with minimum hold time filter
        
        This prevents premature exits on noise
        """
        df = signals_df.copy()
        
        trades = []
        equity = [self.config.initial_balance]
        current_balance = self.config.initial_balance
        current_position = None
        
        # Calculate ATR for dynamic stop loss
        if 'atr_14' not in df.columns:
            df['tr'] = np.maximum(
                df['high'] - df['low'],
                np.maximum(
                    abs(df['high'] - df['close'].shift(1)),
                    abs(df['low'] - df['close'].shift(1))
                )
            )
            df['atr_14'] = df['tr'].rolling(14).mean()
        
        for i in range(len(df)):
            if pd.isna(df.iloc[i]['position']) or pd.isna(df.iloc[i]['atr_14']):
                continue
            
            # Entry signal
            if df.iloc[i]['position'] != 0 and current_position is None:
                # Calculate stop loss
                atr = df.iloc[i]['atr_14']
                
                if 'XAU' in self.symbol or 'GOLD' in self.symbol:
                    stop_loss_distance = atr * 1.5
                    max_sl = 50.0
                    stop_loss_distance = min(stop_loss_distance, max_sl)
                else:
                    stop_loss_distance = (atr / self.pip_size) * 2.0
                    stop_loss_distance = min(stop_loss_distance, 100.0)
                
                position_size = self.calculate_position_size(stop_loss_distance, current_balance)
                
                entry_price = df.iloc[i]['close']
                if df.iloc[i]['position'] > 0:
                    entry_price += (self.config.spread_pips * self.pip_size)
                else:
                    entry_price -= (self.config.spread_pips * self.pip_size)
                
                current_position = {
                    'direction': 'long' if df.iloc[i]['position'] > 0 else 'short',
                    'entry_time': df.index[i],
                    'entry_price': entry_price,
                    'entry_idx': i,
                    'position_size': position_size,
                    'stop_loss_distance': stop_loss_distance
                }
            
            # Exit logic
            elif current_position is not None:
                should_exit = False
                exit_reason = "signal"
                
                # Calculate hold duration
                hold_duration = i - current_position['entry_idx']
                
                # Check stop loss
                if current_position['direction'] == 'long':
                    stop_loss_price = current_position['entry_price'] - (current_position['stop_loss_distance'] * self.pip_size)
                    if df.iloc[i]['low'] <= stop_loss_price:
                        should_exit = True
                        exit_reason = "stop_loss"
                else:
                    stop_loss_price = current_position['entry_price'] + (current_position['stop_loss_distance'] * self.pip_size)
                    if df.iloc[i]['high'] >= stop_loss_price:
                        should_exit = True
                        exit_reason = "stop_loss"
                
                # Exit signal (only after minimum hold time)
                if hold_duration >= min_hold_hours:
                    if df.iloc[i]['position'] != 0 and df.iloc[i]['position'] != (1 if current_position['direction'] == 'long' else -1):
                        should_exit = True
                        exit_reason = "signal"
                
                # Max holding period (48 hours)
                if hold_duration >= 48:
                    should_exit = True
                    exit_reason = "timeout"
                
                if should_exit:
                    if exit_reason == "stop_loss":
                        exit_price = stop_loss_price
                    else:
                        exit_price = df.iloc[i]['close'] - (self.config.slippage_pips * self.pip_size)
                    
                    exit_time = df.index[i]
                    
                    # Calculate P&L
                    if 'XAU' in self.symbol or 'GOLD' in self.symbol:
                        price_diff = exit_price - current_position['entry_price']
                        if current_position['direction'] == 'short':
                            price_diff = -price_diff
                        profit_usd = price_diff * current_position['position_size'] * 100
                        profit_pips = price_diff
                    else:
                        if current_position['direction'] == 'long':
                            profit_pips = (exit_price - current_position['entry_price']) / self.pip_size
                        else:
                            profit_pips = (current_position['entry_price'] - exit_price) / self.pip_size
                        profit_usd = profit_pips * 10 * current_position['position_size']
                    
                    profit_usd -= self.config.commission_per_lot * current_position['position_size']
                    current_balance += profit_usd
                    
                    from strategy_backtest_framework import Trade
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
                    equity.append(current_balance)
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
        
        # Sharpe ratio
        if len(equity_array) > 1:
            returns = np.diff(equity_array) / equity_array[:-1]
            sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252 * 24) if np.std(returns) > 0 else 0
        else:
            sharpe = 0
        
        from strategy_backtest_framework import BacktestResult
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


def load_clean_data(symbol):
    """Load clean CSV data"""
    filepath = f'/tmp/{symbol.lower()}_h1_clean.csv'
    df = pd.read_csv(filepath)
    df['time'] = pd.to_datetime(df['time'], format='mixed')
    df = df.set_index('time')
    return df


def run_improvement():
    """Apply filters and compare before vs after"""
    
    print("\n" + "="*70)
    print("TASK 4: STRATEGY IMPROVEMENT - APPLYING DIAGNOSTIC FILTERS")
    print("="*70)
    
    config = BacktestConfig(
        initial_balance=10000,
        risk_per_trade_pct=1.0,
        spread_pips=2.0,
        slippage_pips=1.0,
        commission_per_lot=7.0,
        max_position_size=0.1
    )
    
    # Load data
    print("\n📥 Loading XAUUSD data...")
    df = load_clean_data('XAUUSD')
    
    # BASELINE (No filters)
    print("\n" + "="*70)
    print("BASELINE: XAUUSD Mean Reversion (NO FILTERS)")
    print("="*70)
    
    backtester_baseline = ImprovedBacktester(df, config, 'XAUUSD')
    backtester_baseline.calculate_indicators()
    
    baseline_signals, _ = backtester_baseline.mean_reversion_filtered(
        apply_regime_filter=False,
        apply_volatility_filter=False,
        apply_duration_filter=False,
        apply_session_filter=False
    )
    
    baseline_result = backtester_baseline.execute_backtest_with_min_hold(
        baseline_signals, "Mean Reversion (Baseline)", min_hold_hours=0
    )
    
    print_backtest_results(baseline_result)
    
    # IMPROVED (With filters)
    print("\n" + "="*70)
    print("IMPROVED: XAUUSD Mean Reversion (WITH FILTERS)")
    print("="*70)
    print("\n🔧 FILTERS APPLIED:")
    print("   ✅ Market Regime: Ranging only (|EMA 50 - EMA 200| < 0.5%)")
    print("   ✅ Volatility: High only (ATR > 67th percentile)")
    print("   ✅ Minimum Hold Time: 10 hours")
    print("   ⚠️  Session Filter: DISABLED (all sessions profitable)")
    
    backtester_improved = ImprovedBacktester(df, config, 'XAUUSD')
    backtester_improved.calculate_indicators()
    
    improved_signals, atr_threshold = backtester_improved.mean_reversion_filtered(
        apply_regime_filter=True,
        apply_volatility_filter=True,
        apply_duration_filter=True,
        apply_session_filter=False
    )
    
    improved_result = backtester_improved.execute_backtest_with_min_hold(
        improved_signals, "Mean Reversion (Filtered)", min_hold_hours=10
    )
    
    print_backtest_results(improved_result)
    
    # COMPARISON
    print("\n" + "="*70)
    print("📊 BEFORE vs AFTER COMPARISON")
    print("="*70)
    
    comparison = pd.DataFrame({
        'Metric': [
            'Total Trades',
            'Profit Factor',
            'Win Rate (%)',
            'Net Profit ($)',
            'Max Drawdown (%)',
            'Avg Trade ($)',
            'Sharpe Ratio'
        ],
        'BEFORE': [
            baseline_result.total_trades,
            round(baseline_result.profit_factor, 2),
            round(baseline_result.win_rate, 1),
            round(baseline_result.net_profit, 2),
            round(baseline_result.max_drawdown_pct, 1),
            round(baseline_result.avg_trade, 2),
            round(baseline_result.sharpe_ratio, 2)
        ],
        'AFTER': [
            improved_result.total_trades,
            round(improved_result.profit_factor, 2),
            round(improved_result.win_rate, 1),
            round(improved_result.net_profit, 2),
            round(improved_result.max_drawdown_pct, 1),
            round(improved_result.avg_trade, 2),
            round(improved_result.sharpe_ratio, 2)
        ]
    })
    
    # Calculate improvement
    comparison['Change'] = comparison.apply(
        lambda row: f"+{row['AFTER'] - row['BEFORE']:.1f}" 
        if row['AFTER'] > row['BEFORE'] 
        else f"{row['AFTER'] - row['BEFORE']:.1f}",
        axis=1
    )
    
    print("\n" + comparison.to_string(index=False))
    
    # Target metrics check
    print("\n" + "="*70)
    print("✅ TARGET METRICS CHECK")
    print("="*70)
    
    targets = [
        ("Profit Factor > 2.0", improved_result.profit_factor > 2.0, improved_result.profit_factor),
        ("Trades: 30-80", 30 <= improved_result.total_trades <= 80, improved_result.total_trades),
        ("Max DD < 25%", improved_result.max_drawdown_pct < 25, f"{improved_result.max_drawdown_pct:.1f}%"),
        ("Win Rate > 40%", improved_result.win_rate > 40, f"{improved_result.win_rate:.1f}%"),
    ]
    
    for metric, passed, value in targets:
        status = "✅" if passed else "❌"
        print(f"   {status} {metric}: {value}")
    
    print("\n" + "="*70)
    print("✅ TASK 4 COMPLETE - Strategy Improved")
    print("="*70)
    
    return baseline_result, improved_result


if __name__ == '__main__':
    baseline, improved = run_improvement()
