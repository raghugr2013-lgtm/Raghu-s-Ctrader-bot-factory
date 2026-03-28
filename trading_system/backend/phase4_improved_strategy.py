#!/usr/bin/env python3
"""
Phase 4: Strategy Improvement
Enhanced EMA strategy with improved filters and exits
"""
import pandas as pd
import numpy as np
from typing import Dict, List
import json
import sys

class ImprovedEMAStrategy:
    def __init__(self, candles_df, ema_fast=10, ema_slow=150, risk_pct=0.5):
        """
        Enhanced EMA trend following with quality filters
        
        Args:
            candles_df: DataFrame with OHLC data
            ema_fast: Fast EMA period
            ema_slow: Slow EMA period
            risk_pct: Risk percentage per trade
        """
        self.df = candles_df.copy()
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.risk_pct = risk_pct
        
        # Ultra-selective parameters for quality over quantity
        self.adx_threshold = 35  # Very strong trends only
        self.adx_sustained_bars = 3  # ADX must stay above threshold for 3 bars
        self.atr_multiplier = 0.70  # High volatility only
        self.min_ema_separation_pct = 0.15  # EMA must be well-separated (0.15%)
        self.trailing_stop_atr = 3.0  # Wider stop to avoid whipsaws
        self.take_profit_atr = 6.0  # Bigger targets
        
    def calculate_indicators(self):
        """Calculate all technical indicators"""
        df = self.df
        
        # EMAs
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        
        # ATR for volatility and stops
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_close'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        # ADX for trend strength
        df['plus_dm'] = df['high'].diff()
        df['minus_dm'] = -df['low'].diff()
        
        # Set negative DMs to 0
        df.loc[df['plus_dm'] < 0, 'plus_dm'] = 0
        df.loc[df['minus_dm'] < 0, 'minus_dm'] = 0
        
        # When plus_dm and minus_dm both positive, keep larger one
        df.loc[df['plus_dm'] < df['minus_dm'], 'plus_dm'] = 0
        df.loc[df['minus_dm'] < df['plus_dm'], 'minus_dm'] = 0
        
        # Smooth DMs
        df['plus_dm_smooth'] = df['plus_dm'].rolling(window=14).mean()
        df['minus_dm_smooth'] = df['minus_dm'].rolling(window=14).mean()
        
        # Directional indicators
        df['plus_di'] = 100 * df['plus_dm_smooth'] / df['atr']
        df['minus_di'] = 100 * df['minus_dm_smooth'] / df['atr']
        
        # ADX
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
        df['adx'] = df['dx'].rolling(window=14).mean()
        
        # Volatility threshold
        mean_atr = df['atr'].mean()
        self.volatility_threshold = mean_atr * self.atr_multiplier
        
        return df
    
    def generate_signals(self, df):
        """Generate ultra-selective trading signals"""
        df['signal'] = 0
        
        # Calculate EMA separation percentage
        df['ema_separation_pct'] = abs((df['ema_fast'] - df['ema_slow']) / df['ema_slow']) * 100
        
        # Check if ADX has been strong for sustained period
        df['adx_strong'] = (df['adx'] > self.adx_threshold).astype(int)
        df['adx_sustained'] = df['adx_strong'].rolling(window=self.adx_sustained_bars).sum()
        
        # LONG conditions (ultra-strict):
        long_conditions = (
            (df['ema_fast'] > df['ema_slow']) &  # Trend direction
            (df['adx_sustained'] >= self.adx_sustained_bars) &  # Sustained strong trend
            (df['atr'] > self.volatility_threshold) &  # High volatility
            (df['plus_di'] > df['minus_di'] + 5) &  # Clear directional bias
            (df['ema_separation_pct'] > self.min_ema_separation_pct)  # Well-separated EMAs
        )
        
        # SHORT conditions (ultra-strict):
        short_conditions = (
            (df['ema_fast'] < df['ema_slow']) &  # Trend direction
            (df['adx_sustained'] >= self.adx_sustained_bars) &  # Sustained strong trend
            (df['atr'] > self.volatility_threshold) &  # High volatility
            (df['minus_di'] > df['plus_di'] + 5) &  # Clear directional bias
            (df['ema_separation_pct'] > self.min_ema_separation_pct)  # Well-separated EMAs
        )
        
        df.loc[long_conditions, 'signal'] = 1
        df.loc[short_conditions, 'signal'] = -1
        
        # Shift to avoid lookahead bias
        df['position'] = df['signal'].shift(1)
        
        return df
    
    def simulate_trades_with_exits(self, df):
        """
        Simulate trades with enhanced exit logic:
        - Trailing stop
        - Take profit target
        - EMA crossover exit
        """
        df = df.dropna()
        
        trades = []
        position = None
        trailing_stop = None
        take_profit = None
        
        for i in range(1, len(df)):
            current_row = df.iloc[i]
            current_position = current_row['position']
            prev_position = df.iloc[i-1]['position']
            
            # Manage open position
            if position is not None:
                current_price = current_row['close']
                
                # Check exits
                exit_triggered = False
                exit_reason = None
                
                # 1. Trailing stop hit
                if position['direction'] == 'LONG':
                    if current_price <= trailing_stop:
                        exit_triggered = True
                        exit_reason = 'trailing_stop'
                    # Update trailing stop if price moves in our favor
                    elif current_price > position['highest']:
                        position['highest'] = current_price
                        trailing_stop = current_price - (current_row['atr'] * self.trailing_stop_atr)
                else:  # SHORT
                    if current_price >= trailing_stop:
                        exit_triggered = True
                        exit_reason = 'trailing_stop'
                    # Update trailing stop if price moves in our favor
                    elif current_price < position['lowest']:
                        position['lowest'] = current_price
                        trailing_stop = current_price + (current_row['atr'] * self.trailing_stop_atr)
                
                # 2. Take profit hit
                if not exit_triggered:
                    if position['direction'] == 'LONG' and current_price >= take_profit:
                        exit_triggered = True
                        exit_reason = 'take_profit'
                    elif position['direction'] == 'SHORT' and current_price <= take_profit:
                        exit_triggered = True
                        exit_reason = 'take_profit'
                
                # 3. Signal reversal (position changes)
                if not exit_triggered and current_position != prev_position:
                    exit_triggered = True
                    exit_reason = 'signal_reversal'
                
                # Execute exit
                if exit_triggered:
                    trades.append({
                        'entry_time': str(position['entry_time']),
                        'exit_time': str(current_row['timestamp']),
                        'direction': position['direction'],
                        'entry_price': position['entry_price'],
                        'exit_price': current_price,
                        'exit_reason': exit_reason,
                        'atr_at_entry': position['atr_at_entry'],
                        'adx_at_entry': position['adx_at_entry']
                    })
                    position = None
                    trailing_stop = None
                    take_profit = None
            
            # Open new position
            if position is None and current_position != 0:
                entry_price = current_row['close']
                atr = current_row['atr']
                
                if current_position > 0:  # LONG
                    position = {
                        'direction': 'LONG',
                        'entry_time': current_row['timestamp'],
                        'entry_price': entry_price,
                        'highest': entry_price,
                        'atr_at_entry': atr,
                        'adx_at_entry': current_row['adx']
                    }
                    trailing_stop = entry_price - (atr * self.trailing_stop_atr)
                    take_profit = entry_price + (atr * self.take_profit_atr)
                else:  # SHORT
                    position = {
                        'direction': 'SHORT',
                        'entry_time': current_row['timestamp'],
                        'entry_price': entry_price,
                        'lowest': entry_price,
                        'atr_at_entry': atr,
                        'adx_at_entry': current_row['adx']
                    }
                    trailing_stop = entry_price + (atr * self.trailing_stop_atr)
                    take_profit = entry_price - (atr * self.take_profit_atr)
        
        # Close final position if still open
        if position is not None:
            current_price = df.iloc[-1]['close']
            trades.append({
                'entry_time': str(position['entry_time']),
                'exit_time': str(df.iloc[-1]['timestamp']),
                'direction': position['direction'],
                'entry_price': position['entry_price'],
                'exit_price': current_price,
                'exit_reason': 'end_of_data',
                'atr_at_entry': position['atr_at_entry'],
                'adx_at_entry': position['adx_at_entry']
            })
        
        return trades
    
    def run(self):
        """Execute improved strategy"""
        # Calculate indicators
        df = self.calculate_indicators()
        
        # Generate signals
        df = self.generate_signals(df)
        
        # Simulate trades with improved exits
        trades = self.simulate_trades_with_exits(df)
        
        return trades, df

def test_improved_strategy(csv_path):
    """Test improved strategy and compare with baseline"""
    
    print("\n" + "="*80)
    print("PHASE 4: STRATEGY IMPROVEMENT TESTING")
    print("="*80)
    print()
    
    # Load data
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    print(f"Data: {len(df)} candles")
    print(f"Period: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print()
    
    # Run improved strategy
    print("🔧 Running ULTRA-SELECTIVE strategy...")
    print("   Enhancements:")
    print("   - ADX threshold: 35 (only strongest trends)")
    print("   - ADX sustained: 3 bars minimum")
    print("   - ATR filter: 70% of mean (very high volatility only)")
    print("   - EMA separation: > 0.15% (clear trend)")
    print("   - DI gap: > 5 points (strong directional bias)")
    print("   - Trailing stop: 3.0 × ATR (room to breathe)")
    print("   - Take profit: 6.0 × ATR (bigger targets)")
    print("   - Goal: Trade only the absolute best setups")
    print()
    
    strategy = ImprovedEMAStrategy(df, ema_fast=10, ema_slow=150, risk_pct=0.5)
    trades, signal_df = strategy.run()
    
    print(f"✅ Strategy generated {len(trades)} trades")
    print()
    
    # Calculate basic metrics (without execution costs for comparison)
    if trades:
        winning_trades = []
        losing_trades = []
        
        for trade in trades:
            if trade['direction'] == 'LONG':
                pnl = trade['exit_price'] - trade['entry_price']
            else:
                pnl = trade['entry_price'] - trade['exit_price']
            
            pnl_pct = (pnl / trade['entry_price']) * 100
            trade['pnl_pct'] = pnl_pct
            
            if pnl > 0:
                winning_trades.append(trade)
            else:
                losing_trades.append(trade)
        
        total_trades = len(trades)
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        total_wins = sum(t['pnl_pct'] for t in winning_trades)
        total_losses = abs(sum(t['pnl_pct'] for t in losing_trades)) if losing_trades else 0
        
        pf = (total_wins / total_losses) if total_losses > 0 else 0
        net_return = total_wins - total_losses
        
        # Exit reason analysis
        exit_reasons = {}
        for trade in trades:
            reason = trade.get('exit_reason', 'unknown')
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        print("="*80)
        print("IMPROVED STRATEGY RESULTS (Before Execution Costs)")
        print("="*80)
        print()
        
        print(f"📊 Performance Metrics:")
        print(f"   Total Trades:     {total_trades}")
        print(f"   Winning Trades:   {win_count} ({win_rate:.1f}%)")
        print(f"   Losing Trades:    {loss_count}")
        print(f"   Profit Factor:    {pf:.2f}")
        print(f"   Net Return:       {net_return:.2f}%")
        print()
        
        print(f"📈 Trade Quality:")
        if winning_trades:
            avg_win = sum(t['pnl_pct'] for t in winning_trades) / len(winning_trades)
            print(f"   Average Win:      {avg_win:.2f}%")
        if losing_trades:
            avg_loss = sum(t['pnl_pct'] for t in losing_trades) / len(losing_trades)
            print(f"   Average Loss:     {avg_loss:.2f}%")
        print()
        
        print(f"🚪 Exit Reasons:")
        for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_trades) * 100
            print(f"   {reason:20s}: {count:3d} ({pct:5.1f}%)")
        print()
        
        # Sample trades
        print("📋 Sample Trades (First 5):")
        for i, trade in enumerate(trades[:5], 1):
            print(f"   {i}. {trade['direction']:5s} | "
                  f"Entry: {trade['entry_price']:.5f} | "
                  f"Exit: {trade['exit_price']:.5f} | "
                  f"P&L: {trade['pnl_pct']:+.2f}% | "
                  f"Exit: {trade['exit_reason']}")
        print()
        
        print("="*80)
        
        # Save results
        results = {
            'metrics': {
                'total_trades': total_trades,
                'winning_trades': win_count,
                'losing_trades': loss_count,
                'win_rate_pct': round(win_rate, 2),
                'profit_factor': round(pf, 2),
                'net_return_pct': round(net_return, 2)
            },
            'trades': trades,
            'exit_reasons': exit_reasons
        }
        
        output_file = "/app/trading_system/backend/improved_strategy_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"💾 Results saved to: {output_file}")
        
        return results
    
    return None

if __name__ == "__main__":
    csv_path = "/app/trading_system/data/EURUSD_H1.csv"
    results = test_improved_strategy(csv_path)
