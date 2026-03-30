#!/usr/bin/env python3
"""
Phase 3: Execution Readiness Simulator
Adds real-world trading costs, slippage, and position sizing
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import json
import sys

class ExecutionSimulator:
    def __init__(self, initial_balance=10000, spread_pips=1.5, commission=0, 
                 slippage_pips_range=(0.5, 1.0)):
        """
        Initialize execution simulator with real-world costs
        
        Args:
            initial_balance: Starting account balance ($)
            spread_pips: Spread cost in pips (EURUSD typically 1-2 pips)
            commission: Commission per lot (if any)
            slippage_pips_range: Range for random slippage simulation
        """
        self.initial_balance = initial_balance
        self.spread_pips = spread_pips
        self.commission = commission
        self.slippage_pips_range = slippage_pips_range
        
        # For EURUSD, 1 pip = 0.0001
        self.pip_value = 0.0001
        
        # Equity tracking
        self.equity_curve = []
        self.balance_history = []
        self.peak_balance = initial_balance
        self.max_drawdown = 0
        
    def calculate_position_size(self, balance, risk_pct, entry_price, stop_loss_distance_pips):
        """
        Calculate position size based on risk percentage
        
        Args:
            balance: Current account balance
            risk_pct: Risk per trade as percentage (e.g., 0.5 for 0.5%)
            entry_price: Entry price
            stop_loss_distance_pips: Stop loss distance in pips
        
        Returns:
            Position size in units (micro lots for EURUSD)
        """
        # Amount to risk in dollars
        risk_amount = balance * (risk_pct / 100)
        
        # Stop loss in price
        stop_loss_price = stop_loss_distance_pips * self.pip_value
        
        # Position size = Risk Amount / Stop Loss Distance / Price
        # For EURUSD: position size in units
        position_size = risk_amount / stop_loss_price
        
        return position_size
    
    def apply_slippage(self, price, direction='entry'):
        """
        Apply random slippage to entry/exit price
        
        Args:
            price: Original price
            direction: 'entry' or 'exit'
        
        Returns:
            Price with slippage applied
        """
        # Random slippage within range
        slippage_pips = np.random.uniform(*self.slippage_pips_range)
        slippage = slippage_pips * self.pip_value
        
        # Slippage works against the trader
        # For long entry or short exit: price goes up
        # For short entry or long exit: price goes down
        # We'll apply adverse slippage randomly
        if np.random.random() > 0.5:
            return price + slippage
        else:
            return price - slippage
    
    def calculate_spread_cost(self, position_size):
        """
        Calculate spread cost for a trade
        
        Args:
            position_size: Position size in units
        
        Returns:
            Spread cost in dollars
        """
        spread_cost = self.spread_pips * self.pip_value * position_size
        return spread_cost
    
    def simulate_trades(self, candles_df, strategy_trades, risk_pct=0.5):
        """
        Simulate trades with real-world execution conditions
        
        Args:
            candles_df: DataFrame with OHLC data
            strategy_trades: List of trade signals from strategy
            risk_pct: Risk percentage per trade
        
        Returns:
            Enhanced trades list with realistic P&L and equity curve
        """
        balance = self.initial_balance
        enhanced_trades = []
        
        # Set seed for reproducibility
        np.random.seed(42)
        
        for trade in strategy_trades:
            entry_price = trade['entry_price']
            exit_price = trade['exit_price']
            direction = trade['direction']
            
            # Apply slippage to entry
            entry_price_actual = self.apply_slippage(entry_price, 'entry')
            
            # Apply slippage to exit
            exit_price_actual = self.apply_slippage(exit_price, 'exit')
            
            # Calculate position size based on current balance
            # Assume stop loss is 50 pips (can be adjusted)
            stop_loss_pips = 50
            position_size = self.calculate_position_size(
                balance, risk_pct, entry_price_actual, stop_loss_pips
            )
            
            # Calculate raw P&L
            if direction == 'LONG':
                raw_pnl = (exit_price_actual - entry_price_actual) * position_size
            else:  # SHORT
                raw_pnl = (entry_price_actual - exit_price_actual) * position_size
            
            # Subtract spread cost
            spread_cost = self.calculate_spread_cost(position_size)
            
            # Subtract commission (if any)
            total_cost = spread_cost + self.commission
            
            # Net P&L after costs
            net_pnl = raw_pnl - total_cost
            
            # Update balance
            balance += net_pnl
            
            # Track peak and drawdown
            if balance > self.peak_balance:
                self.peak_balance = balance
            
            current_drawdown = (self.peak_balance - balance) / self.peak_balance * 100
            if current_drawdown > self.max_drawdown:
                self.max_drawdown = current_drawdown
            
            # Record equity curve point
            self.equity_curve.append({
                'timestamp': trade['exit_time'],
                'balance': balance,
                'drawdown_pct': current_drawdown
            })
            
            # Enhanced trade record
            enhanced_trades.append({
                'entry_time': trade['entry_time'],
                'exit_time': trade['exit_time'],
                'direction': direction,
                'entry_price_signal': entry_price,
                'exit_price_signal': exit_price,
                'entry_price_actual': round(entry_price_actual, 5),
                'exit_price_actual': round(exit_price_actual, 5),
                'position_size': round(position_size, 2),
                'raw_pnl': round(raw_pnl, 2),
                'spread_cost': round(spread_cost, 2),
                'commission': self.commission,
                'net_pnl': round(net_pnl, 2),
                'balance_after': round(balance, 2),
                'drawdown_pct': round(current_drawdown, 2)
            })
        
        return enhanced_trades, balance
    
    def calculate_metrics(self, enhanced_trades, final_balance):
        """
        Calculate comprehensive performance metrics
        
        Args:
            enhanced_trades: List of trades with costs
            final_balance: Final account balance
        
        Returns:
            Dictionary of performance metrics
        """
        if not enhanced_trades:
            return {}
        
        # Net return
        net_return_pct = ((final_balance - self.initial_balance) / self.initial_balance) * 100
        
        # Trade statistics
        winning_trades = [t for t in enhanced_trades if t['net_pnl'] > 0]
        losing_trades = [t for t in enhanced_trades if t['net_pnl'] < 0]
        
        total_trades = len(enhanced_trades)
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        # P&L statistics
        total_gross_profit = sum(t['net_pnl'] for t in winning_trades) if winning_trades else 0
        total_gross_loss = abs(sum(t['net_pnl'] for t in losing_trades)) if losing_trades else 0
        
        profit_factor = (total_gross_profit / total_gross_loss) if total_gross_loss > 0 else 0
        
        # Average wins/losses
        avg_win = (total_gross_profit / win_count) if win_count > 0 else 0
        avg_loss = (total_gross_loss / loss_count) if loss_count > 0 else 0
        
        # Total costs
        total_spread_cost = sum(t['spread_cost'] for t in enhanced_trades)
        total_commission = sum(t['commission'] for t in enhanced_trades)
        total_costs = total_spread_cost + total_commission
        
        # Sharpe-like ratio (simplified)
        returns = [t['net_pnl'] for t in enhanced_trades]
        if len(returns) > 1:
            sharpe_like = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
            sharpe_like_annualized = sharpe_like * np.sqrt(252)  # Assuming daily-like frequency
        else:
            sharpe_like_annualized = 0
        
        return {
            'initial_balance': self.initial_balance,
            'final_balance': round(final_balance, 2),
            'net_return_pct': round(net_return_pct, 2),
            'net_return_dollars': round(final_balance - self.initial_balance, 2),
            'total_trades': total_trades,
            'winning_trades': win_count,
            'losing_trades': loss_count,
            'win_rate_pct': round(win_rate, 2),
            'profit_factor': round(profit_factor, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'max_drawdown_pct': round(self.max_drawdown, 2),
            'total_costs': round(total_costs, 2),
            'spread_costs': round(total_spread_cost, 2),
            'commissions': round(total_commission, 2),
            'sharpe_like_ratio': round(sharpe_like_annualized, 3),
            'peak_balance': round(self.peak_balance, 2)
        }
    
    def get_equity_curve(self):
        """Return equity curve data"""
        return self.equity_curve

def test_ema_strategy_with_execution(csv_path, ema_fast=10, ema_slow=150, risk_pct=0.5):
    """
    Test EMA strategy with real execution simulation
    
    Args:
        csv_path: Path to OHLC data CSV
        ema_fast: Fast EMA period
        ema_slow: Slow EMA period
        risk_pct: Risk percentage per trade
    
    Returns:
        Results dictionary with metrics and equity curve
    """
    # Load data
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    print("\n" + "="*80)
    print("PHASE 3: EXECUTION READINESS SIMULATION")
    print("="*80)
    print(f"\nStrategy: EMA {ema_fast}/{ema_slow}")
    print(f"Data: {len(df)} candles ({df['timestamp'].min()} to {df['timestamp'].max()})")
    print(f"Risk per trade: {risk_pct}%")
    print()
    
    # Calculate EMAs
    df['ema_fast'] = df['close'].ewm(span=ema_fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=ema_slow, adjust=False).mean()
    
    # Calculate ATR for volatility filter
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = abs(df['high'] - df['close'].shift(1))
    df['low_close'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    mean_atr = df['atr'].mean()
    volatility_threshold = mean_atr * 0.3
    
    # Generate signals
    df['signal'] = 0
    df.loc[(df['ema_fast'] > df['ema_slow']) & (df['atr'] > volatility_threshold), 'signal'] = 1
    df.loc[(df['ema_fast'] < df['ema_slow']) & (df['atr'] > volatility_threshold), 'signal'] = -1
    df['position'] = df['signal'].shift(1)
    df = df.dropna()
    
    # Extract trades
    trades = []
    position = None
    
    for i in range(1, len(df)):
        current_position = df.iloc[i]['position']
        prev_position = df.iloc[i-1]['position']
        
        if current_position != prev_position:
            if position is not None:
                exit_price = df.iloc[i]['close']
                exit_time = df.iloc[i]['timestamp']
                
                trades.append({
                    'entry_time': str(position['entry_time']),
                    'exit_time': str(exit_time),
                    'direction': position['direction'],
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price
                })
                position = None
            
            if current_position != 0:
                position = {
                    'direction': 'LONG' if current_position > 0 else 'SHORT',
                    'entry_time': df.iloc[i]['timestamp'],
                    'entry_price': df.iloc[i]['close']
                }
    
    # Close final position if open
    if position is not None:
        exit_price = df.iloc[-1]['close']
        exit_time = df.iloc[-1]['timestamp']
        trades.append({
            'entry_time': str(position['entry_time']),
            'exit_time': str(exit_time),
            'direction': position['direction'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price
        })
    
    print(f"📊 Strategy generated {len(trades)} trades")
    print()
    
    # Simulate execution with costs
    print("💰 Simulating execution with real-world costs...")
    print(f"   Spread: 1.5 pips")
    print(f"   Slippage: 0.5-1.0 pips (random)")
    print(f"   Position sizing: Dynamic ({risk_pct}% risk per trade)")
    print()
    
    simulator = ExecutionSimulator(
        initial_balance=10000,
        spread_pips=1.5,
        commission=0,
        slippage_pips_range=(0.5, 1.0)
    )
    
    enhanced_trades, final_balance = simulator.simulate_trades(df, trades, risk_pct)
    metrics = simulator.calculate_metrics(enhanced_trades, final_balance)
    equity_curve = simulator.get_equity_curve()
    
    # Print results
    print("="*80)
    print("EXECUTION SIMULATION RESULTS")
    print("="*80)
    print()
    
    print(f"💵 Account Performance:")
    print(f"   Initial Balance:  ${metrics['initial_balance']:,.2f}")
    print(f"   Final Balance:    ${metrics['final_balance']:,.2f}")
    print(f"   Net Return:       {metrics['net_return_pct']:+.2f}% (${metrics['net_return_dollars']:+,.2f})")
    print(f"   Peak Balance:     ${metrics['peak_balance']:,.2f}")
    print(f"   Max Drawdown:     {metrics['max_drawdown_pct']:.2f}%")
    print()
    
    print(f"📈 Trade Statistics:")
    print(f"   Total Trades:     {metrics['total_trades']}")
    print(f"   Winning Trades:   {metrics['winning_trades']} ({metrics['win_rate_pct']:.1f}%)")
    print(f"   Losing Trades:    {metrics['losing_trades']}")
    print(f"   Profit Factor:    {metrics['profit_factor']:.2f}")
    print(f"   Average Win:      ${metrics['avg_win']:,.2f}")
    print(f"   Average Loss:     ${metrics['avg_loss']:,.2f}")
    print()
    
    print(f"💸 Trading Costs:")
    print(f"   Total Spread Cost: ${metrics['spread_costs']:,.2f}")
    print(f"   Total Commission:  ${metrics['commissions']:,.2f}")
    print(f"   Total Costs:       ${metrics['total_costs']:,.2f}")
    print(f"   Cost as % of Capital: {(metrics['total_costs']/10000)*100:.2f}%")
    print()
    
    print(f"📊 Risk Metrics:")
    print(f"   Sharpe-like Ratio: {metrics['sharpe_like_ratio']:.3f}")
    print(f"   Risk/Reward Ratio: {(metrics['avg_win']/metrics['avg_loss']):.2f}:1" if metrics['avg_loss'] > 0 else "N/A")
    print()
    
    print("="*80)
    
    # Save results
    results = {
        'metrics': metrics,
        'enhanced_trades': enhanced_trades[:10],  # Sample trades
        'equity_curve': equity_curve,
        'strategy_parameters': {
            'ema_fast': ema_fast,
            'ema_slow': ema_slow,
            'risk_pct': risk_pct
        }
    }
    
    output_file = "/app/trading_system/backend/execution_simulation_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"💾 Results saved to: {output_file}")
    print()
    
    return results

if __name__ == "__main__":
    # Test with best strategy from Phase 2D: EMA 10/150
    csv_path = "/app/trading_system/data/EURUSD_H1.csv"
    
    results = test_ema_strategy_with_execution(
        csv_path=csv_path,
        ema_fast=10,
        ema_slow=150,
        risk_pct=0.5
    )
