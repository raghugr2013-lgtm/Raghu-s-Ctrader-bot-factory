#!/usr/bin/env python3
"""
TASK 5: Risk Optimization
Preserve edge (PF 2.46) while reducing drawdown through risk management
"""

import pandas as pd
import numpy as np
import sys
from datetime import datetime, timedelta
sys.path.append('/app/trading_system/backend')

from strategy_backtest_framework import SimpleBacktester, BacktestConfig, print_backtest_results, Trade, BacktestResult
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class RiskManagedBacktester(SimpleBacktester):
    """Enhanced backtester with advanced risk management"""
    
    def execute_backtest_with_risk_management(
        self, 
        signals_df: pd.DataFrame, 
        strategy_name: str,
        base_risk_pct: float = 1.0,
        max_concurrent_trades: int = 5,
        equity_scaling: bool = True,
        daily_loss_limit_pct: float = 3.0,
        weekly_loss_limit_pct: float = 8.0,
        partial_profit_taking: bool = False
    ) -> BacktestResult:
        """
        Execute backtest with advanced risk management
        
        Risk Controls:
        1. Adjustable base risk per trade
        2. Equity-based position scaling during drawdown
        3. Max concurrent trades limit
        4. Daily/weekly loss limits
        5. Optional partial profit taking
        """
        df = signals_df.copy()
        
        trades = []
        equity = [self.config.initial_balance]
        current_balance = self.config.initial_balance
        peak_balance = self.config.initial_balance
        
        # Track open positions
        open_positions = []
        
        # Daily/weekly tracking
        daily_pnl = {}
        weekly_pnl = {}
        
        # Calculate ATR for stop loss
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
            current_time = df.index[i]
            current_date = current_time.date()
            current_week = current_time.isocalendar()[1]
            
            if pd.isna(df.iloc[i]['position']) or pd.isna(df.iloc[i]['atr_14']):
                continue
            
            # Check daily/weekly loss limits
            daily_loss = daily_pnl.get(current_date, 0)
            weekly_loss = weekly_pnl.get(current_week, 0)
            
            if daily_loss < -(self.config.initial_balance * daily_loss_limit_pct / 100):
                # Hit daily loss limit, skip new entries
                continue
            
            if weekly_loss < -(self.config.initial_balance * weekly_loss_limit_pct / 100):
                # Hit weekly loss limit, skip new entries
                continue
            
            # Entry signal
            if df.iloc[i]['position'] != 0 and df.iloc[i]['position'] != df.iloc[i-1 if i > 0 else 0].get('position', 0):
                
                # Check max concurrent trades limit
                if len(open_positions) >= max_concurrent_trades:
                    continue  # Skip entry, too many open positions
                
                # Calculate current drawdown for equity scaling
                current_drawdown_pct = ((peak_balance - current_balance) / peak_balance) * 100 if peak_balance > 0 else 0
                
                # Equity-based risk adjustment
                if equity_scaling:
                    if current_drawdown_pct > 20:
                        risk_multiplier = 0.25  # Reduce to 25% size
                    elif current_drawdown_pct > 10:
                        risk_multiplier = 0.50  # Reduce to 50% size
                    else:
                        risk_multiplier = 1.0
                else:
                    risk_multiplier = 1.0
                
                # Adjust risk
                adjusted_risk = base_risk_pct * risk_multiplier
                
                # Calculate stop loss
                atr = df.iloc[i]['atr_14']
                
                if 'XAU' in self.symbol or 'GOLD' in self.symbol:
                    stop_loss_distance = atr * 1.5
                    max_sl = 50.0
                    stop_loss_distance = min(stop_loss_distance, max_sl)
                else:
                    stop_loss_distance = (atr / self.pip_size) * 2.0
                    stop_loss_distance = min(stop_loss_distance, 100.0)
                
                # Calculate position size with adjusted risk
                risk_amount = current_balance * (adjusted_risk / 100)
                
                if 'XAU' in self.symbol or 'GOLD' in self.symbol:
                    stop_loss_value_per_lot = stop_loss_distance * 100.0
                else:
                    stop_loss_value_per_lot = stop_loss_distance * 10.0
                
                if stop_loss_value_per_lot > 0:
                    position_size = risk_amount / stop_loss_value_per_lot
                else:
                    position_size = 0.01
                
                position_size = min(position_size, self.config.max_position_size)
                position_size = max(position_size, 0.01)
                position_size = round(position_size, 2)
                
                # Entry price
                entry_price = df.iloc[i]['close']
                if df.iloc[i]['position'] > 0:
                    entry_price += (self.config.spread_pips * self.pip_size)
                else:
                    entry_price -= (self.config.spread_pips * self.pip_size)
                
                # Create position
                position = {
                    'direction': 'long' if df.iloc[i]['position'] > 0 else 'short',
                    'entry_time': current_time,
                    'entry_price': entry_price,
                    'entry_idx': i,
                    'position_size': position_size,
                    'stop_loss_distance': stop_loss_distance,
                    'partial_closed': False
                }
                
                open_positions.append(position)
            
            # Check all open positions for exits
            positions_to_close = []
            
            for pos_idx, position in enumerate(open_positions):
                should_exit = False
                exit_reason = "signal"
                
                # Check stop loss
                if position['direction'] == 'long':
                    stop_loss_price = position['entry_price'] - (position['stop_loss_distance'] * self.pip_size)
                    if df.iloc[i]['low'] <= stop_loss_price:
                        should_exit = True
                        exit_reason = "stop_loss"
                else:
                    stop_loss_price = position['entry_price'] + (position['stop_loss_distance'] * self.pip_size)
                    if df.iloc[i]['high'] >= stop_loss_price:
                        should_exit = True
                        exit_reason = "stop_loss"
                
                # Partial profit taking (optional)
                if partial_profit_taking and not position['partial_closed']:
                    # Check if in profit by 1.5x initial risk
                    if 'XAU' in self.symbol:
                        current_price = df.iloc[i]['close']
                        if position['direction'] == 'long':
                            profit_points = current_price - position['entry_price']
                        else:
                            profit_points = position['entry_price'] - current_price
                        
                        target_profit = position['stop_loss_distance'] * 1.5
                        
                        if profit_points >= target_profit:
                            # Close 50% of position
                            exit_price = df.iloc[i]['close']
                            partial_size = position['position_size'] / 2
                            
                            # Calculate partial profit
                            price_diff = exit_price - position['entry_price']
                            if position['direction'] == 'short':
                                price_diff = -price_diff
                            profit_usd = price_diff * partial_size * 100
                            profit_usd -= self.config.commission_per_lot * partial_size
                            
                            current_balance += profit_usd
                            equity.append(current_balance)
                            
                            # Update position
                            position['position_size'] = partial_size
                            position['partial_closed'] = True
                
                # Exit signal (opposite signal)
                if df.iloc[i]['position'] != 0:
                    if (position['direction'] == 'long' and df.iloc[i]['position'] < 0) or \
                       (position['direction'] == 'short' and df.iloc[i]['position'] > 0):
                        should_exit = True
                        exit_reason = "signal"
                
                # Max holding period
                hold_duration = i - position['entry_idx']
                if hold_duration >= 48:
                    should_exit = True
                    exit_reason = "timeout"
                
                if should_exit:
                    positions_to_close.append(pos_idx)
                    
                    # Calculate exit
                    if exit_reason == "stop_loss":
                        exit_price = stop_loss_price
                    else:
                        exit_price = df.iloc[i]['close'] - (self.config.slippage_pips * self.pip_size)
                    
                    exit_time = df.index[i]
                    
                    # Calculate P&L
                    if 'XAU' in self.symbol or 'GOLD' in self.symbol:
                        price_diff = exit_price - position['entry_price']
                        if position['direction'] == 'short':
                            price_diff = -price_diff
                        profit_usd = price_diff * position['position_size'] * 100
                        profit_pips = price_diff
                    else:
                        if position['direction'] == 'long':
                            profit_pips = (exit_price - position['entry_price']) / self.pip_size
                        else:
                            profit_pips = (position['entry_price'] - exit_price) / self.pip_size
                        profit_usd = profit_pips * 10 * position['position_size']
                    
                    profit_usd -= self.config.commission_per_lot * position['position_size']
                    
                    # Update balance and tracking
                    current_balance += profit_usd
                    
                    # Update peak
                    if current_balance > peak_balance:
                        peak_balance = current_balance
                    
                    # Track daily/weekly P&L
                    daily_pnl[current_date] = daily_pnl.get(current_date, 0) + profit_usd
                    weekly_pnl[current_week] = weekly_pnl.get(current_week, 0) + profit_usd
                    
                    # Create trade record
                    trade = Trade(
                        entry_time=position['entry_time'],
                        exit_time=exit_time,
                        direction=position['direction'],
                        entry_price=position['entry_price'],
                        exit_price=exit_price,
                        profit_pips=profit_pips,
                        profit_usd=profit_usd,
                        duration_hours=(exit_time - position['entry_time']).total_seconds() / 3600,
                        session=df.iloc[i]['session']
                    )
                    
                    trades.append(trade)
                    equity.append(current_balance)
            
            # Remove closed positions
            for idx in reversed(positions_to_close):
                open_positions.pop(idx)
        
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


def run_risk_optimization():
    """Test different risk management configurations"""
    
    print("\n" + "="*70)
    print("TASK 5: RISK OPTIMIZATION - PRESERVE EDGE, CONTROL DRAWDOWN")
    print("="*70)
    
    # Load data
    print("\n📥 Loading XAUUSD data...")
    df = load_clean_data('XAUUSD')
    
    results = {}
    
    # Test configurations
    configs_to_test = [
        {
            'name': 'BASELINE (1.0% risk)',
            'base_risk': 1.0,
            'max_concurrent': 999,  # No limit
            'equity_scaling': False,
            'daily_limit': 999,
            'weekly_limit': 999,
            'partial_tp': False
        },
        {
            'name': 'REDUCED RISK (0.75%)',
            'base_risk': 0.75,
            'max_concurrent': 999,
            'equity_scaling': False,
            'daily_limit': 999,
            'weekly_limit': 999,
            'partial_tp': False
        },
        {
            'name': 'REDUCED RISK (0.5%)',
            'base_risk': 0.5,
            'max_concurrent': 999,
            'equity_scaling': False,
            'daily_limit': 999,
            'weekly_limit': 999,
            'partial_tp': False
        },
        {
            'name': 'FULL RISK MANAGEMENT',
            'base_risk': 0.75,
            'max_concurrent': 5,
            'equity_scaling': True,
            'daily_limit': 3.0,
            'weekly_limit': 8.0,
            'partial_tp': True
        }
    ]
    
    for config_spec in configs_to_test:
        print("\n" + "="*70)
        print(f"TESTING: {config_spec['name']}")
        print("="*70)
        
        config = BacktestConfig(
            initial_balance=10000,
            risk_per_trade_pct=config_spec['base_risk'],
            spread_pips=2.0,
            slippage_pips=1.0,
            commission_per_lot=7.0,
            max_position_size=0.1
        )
        
        backtester = RiskManagedBacktester(df, config, 'XAUUSD')
        backtester.calculate_indicators()
        
        # Generate baseline signals (no strategy filters)
        signals = backtester.mean_reversion_strategy()
        
        # Execute with risk management
        result = backtester.execute_backtest_with_risk_management(
            signals,
            config_spec['name'],
            base_risk_pct=config_spec['base_risk'],
            max_concurrent_trades=config_spec['max_concurrent'],
            equity_scaling=config_spec['equity_scaling'],
            daily_loss_limit_pct=config_spec['daily_limit'],
            weekly_loss_limit_pct=config_spec['weekly_limit'],
            partial_profit_taking=config_spec['partial_tp']
        )
        
        print_backtest_results(result)
        results[config_spec['name']] = result
    
    # Comparison table
    print("\n" + "="*70)
    print("📊 RISK OPTIMIZATION COMPARISON")
    print("="*70)
    
    comparison = pd.DataFrame({
        'Configuration': list(results.keys()),
        'Trades': [r.total_trades for r in results.values()],
        'PF': [round(r.profit_factor, 2) for r in results.values()],
        'Win Rate (%)': [round(r.win_rate, 1) for r in results.values()],
        'Net Profit ($)': [round(r.net_profit, 2) for r in results.values()],
        'Max DD (%)': [round(r.max_drawdown_pct, 1) for r in results.values()],
        'Sharpe': [round(r.sharpe_ratio, 2) for r in results.values()]
    })
    
    print("\n" + comparison.to_string(index=False))
    
    # Identify best
    print("\n" + "="*70)
    print("🏆 BEST CONFIGURATION")
    print("="*70)
    
    # Score each config
    scores = []
    for name, result in results.items():
        score = 0
        if result.profit_factor >= 2.0:
            score += 2
        if result.max_drawdown_pct < 25:
            score += 3
        if result.max_drawdown_pct < 20:
            score += 2
        if result.net_profit > 50000:
            score += 2
        if result.win_rate > 35:
            score += 1
        
        scores.append((name, score, result))
    
    scores.sort(key=lambda x: x[1], reverse=True)
    best_name, best_score, best_result = scores[0]
    
    print(f"\n✅ WINNER: {best_name}")
    print(f"   Score: {best_score}/10")
    print(f"   PF: {best_result.profit_factor:.2f}")
    print(f"   DD: {best_result.max_drawdown_pct:.1f}%")
    print(f"   Profit: ${best_result.net_profit:,.2f}")
    print(f"   Trades: {best_result.total_trades}")
    
    print("\n" + "="*70)
    print("✅ TASK 5 COMPLETE - Risk Optimization Done")
    print("="*70)
    
    return results


if __name__ == '__main__':
    results = run_risk_optimization()
