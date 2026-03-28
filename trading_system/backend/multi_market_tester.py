#!/usr/bin/env python3
"""
Multi-Market Strategy Testing
Test EMA 10/150 on Gold, Crypto, and Indices
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import sys

sys.path.append('/app/trading_system/backend')
from phase3_execution_simulator import ExecutionSimulator

class MultiMarketTester:
    def __init__(self):
        self.markets = {
            'XAUUSD': {
                'symbol': 'GC=F',  # Gold Futures
                'name': 'Gold (XAUUSD)',
                'spread_pips': 0.50,
                'pip_value': 0.10,  # $0.10 per 0.10 move
                'description': 'Precious metal - known for trending'
            },
            'BTCUSD': {
                'symbol': 'BTC-USD',
                'name': 'Bitcoin (BTCUSD)',
                'spread_pips': 10.0,  # ~$10 spread
                'pip_value': 1.0,  # $1 per point
                'description': 'Cryptocurrency - highly volatile'
            },
            'NAS100': {
                'symbol': '^IXIC',  # Nasdaq Composite
                'name': 'Nasdaq 100',
                'spread_pips': 2.0,
                'pip_value': 1.0,  # $1 per point
                'description': 'Tech index - strong trends'
            },
            'SPX': {
                'symbol': '^GSPC',  # S&P 500
                'name': 'S&P 500',
                'spread_pips': 0.25,
                'pip_value': 1.0,
                'description': 'US equity index - benchmark'
            }
        }
    
    def download_data(self, market_key, months=12):
        """Download historical data for a market"""
        market = self.markets[market_key]
        
        print(f"\n📥 Downloading {market['name']} data...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months*30)
        
        try:
            # Download data
            ticker = yf.Ticker(market['symbol'])
            df = ticker.history(start=start_date, end=end_date, interval='1h')
            
            if len(df) == 0:
                print(f"   ❌ No data available for {market['symbol']}")
                return None
            
            # Reset index and rename columns
            df = df.reset_index()
            
            # Handle different column name formats
            if 'Datetime' in df.columns:
                df = df.rename(columns={'Datetime': 'timestamp'})
            elif 'Date' in df.columns:
                df = df.rename(columns={'Date': 'timestamp'})
            
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Select required columns
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            # Drop NaN
            df = df.dropna()
            
            # Ensure proper types
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            print(f"   ✅ Downloaded {len(df)} candles")
            print(f"   Period: {df['timestamp'].min()} to {df['timestamp'].max()}")
            print(f"   Price range: {df['close'].min():.2f} to {df['close'].max():.2f}")
            
            return df
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            return None
    
    def run_ema_strategy(self, df, ema_fast=10, ema_slow=150):
        """Run EMA crossover strategy (same as baseline)"""
        df = df.copy()
        
        # Calculate EMAs
        df['ema_fast'] = df['close'].ewm(span=ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=ema_slow, adjust=False).mean()
        
        # Calculate ATR
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_close'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        # Volatility filter (30% of mean ATR)
        mean_atr = df['atr'].mean()
        volatility_threshold = mean_atr * 0.30
        
        # Generate signals
        df['signal'] = 0
        df.loc[(df['ema_fast'] > df['ema_slow']) & (df['atr'] > volatility_threshold), 'signal'] = 1
        df.loc[(df['ema_fast'] < df['ema_slow']) & (df['atr'] > volatility_threshold), 'signal'] = -1
        
        # Shift to avoid lookahead
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
                    trades.append({
                        'entry_time': str(position['entry_time']),
                        'exit_time': str(df.iloc[i]['timestamp']),
                        'direction': position['direction'],
                        'entry_price': position['entry_price'],
                        'exit_price': df.iloc[i]['close']
                    })
                    position = None
                
                if current_position != 0:
                    position = {
                        'direction': 'LONG' if current_position > 0 else 'SHORT',
                        'entry_time': df.iloc[i]['timestamp'],
                        'entry_price': df.iloc[i]['close']
                    }
        
        # Close final position
        if position is not None:
            trades.append({
                'entry_time': str(position['entry_time']),
                'exit_time': str(df.iloc[-1]['timestamp']),
                'direction': position['direction'],
                'entry_price': position['entry_price'],
                'exit_price': df.iloc[-1]['close']
            })
        
        return trades
    
    def test_market(self, market_key):
        """Test strategy on a specific market"""
        market = self.markets[market_key]
        
        print("\n" + "="*80)
        print(f"TESTING: {market['name']}")
        print("="*80)
        print(f"Description: {market['description']}")
        print(f"Spread: {market['spread_pips']} pips")
        print()
        
        # Download data
        df = self.download_data(market_key)
        
        if df is None or len(df) < 200:
            print(f"❌ Insufficient data for {market['name']}")
            return None
        
        # Run strategy
        print(f"\n🔧 Running EMA 10/150 strategy...")
        trades = self.run_ema_strategy(df)
        
        if not trades:
            print(f"❌ No trades generated for {market['name']}")
            return None
        
        print(f"   Generated {len(trades)} trades")
        
        # Simulate execution with market-specific costs
        print(f"\n💰 Simulating execution...")
        
        simulator = ExecutionSimulator(
            initial_balance=10000,
            spread_pips=market['spread_pips'],
            commission=0,
            slippage_pips_range=(market['spread_pips']*0.3, market['spread_pips']*0.6)
        )
        
        # Adjust pip value for this market
        simulator.pip_value = market['pip_value']
        
        enhanced_trades, final_balance = simulator.simulate_trades(df, trades, risk_pct=0.5)
        metrics = simulator.calculate_metrics(enhanced_trades, final_balance)
        
        # Print results
        print(f"\n📊 Results for {market['name']}:")
        print(f"   Net Return:       {metrics['net_return_pct']:+.2f}%")
        print(f"   Profit Factor:    {metrics['profit_factor']:.2f}")
        print(f"   Max Drawdown:     {metrics['max_drawdown_pct']:.2f}%")
        print(f"   Total Trades:     {metrics['total_trades']}")
        print(f"   Win Rate:         {metrics['win_rate_pct']:.1f}%")
        print(f"   Trading Costs:    ${metrics['total_costs']:.2f}")
        print(f"   Sharpe Ratio:     {metrics['sharpe_like_ratio']:.3f}")
        
        return {
            'market': market['name'],
            'metrics': metrics,
            'trades_count': len(trades)
        }

def main():
    print("\n" + "="*80)
    print("MULTI-MARKET STRATEGY TESTING")
    print("Strategy: EMA 10/150 (Baseline)")
    print("="*80)
    
    tester = MultiMarketTester()
    
    results = {}
    
    # Test each market
    for market_key in ['XAUUSD', 'BTCUSD', 'NAS100', 'SPX']:
        result = tester.test_market(market_key)
        if result:
            results[market_key] = result
    
    # Comparison table
    if results:
        print("\n" + "="*80)
        print("MULTI-MARKET COMPARISON")
        print("="*80)
        print()
        
        # Add EURUSD baseline for comparison
        eurusd_baseline = {
            'market': 'EURUSD (Baseline)',
            'metrics': {
                'net_return_pct': 1.10,
                'profit_factor': 1.05,
                'max_drawdown_pct': 7.12,
                'total_trades': 93,
                'win_rate_pct': 31.2,
                'total_costs': 143.00,
                'sharpe_like_ratio': 0.232
            }
        }
        
        results['EURUSD'] = eurusd_baseline
        
        print(f"{'Market':<20} {'Return %':>10} {'PF':>8} {'Max DD %':>10} {'Trades':>8} {'Costs $':>10} {'Sharpe':>8}")
        print("-" * 90)
        
        for key, result in results.items():
            m = result['metrics']
            print(f"{result['market']:<20} "
                  f"{m['net_return_pct']:>9.2f}% "
                  f"{m['profit_factor']:>8.2f} "
                  f"{m['max_drawdown_pct']:>9.2f}% "
                  f"{m['total_trades']:>8} "
                  f"{m['total_costs']:>9.2f} "
                  f"{m['sharpe_like_ratio']:>8.3f}")
        
        # Find best market
        best_market = max(results.items(), 
                         key=lambda x: x[1]['metrics']['net_return_pct'])
        
        print()
        print(f"🏆 Best Market: {best_market[1]['market']}")
        print(f"   Return: {best_market[1]['metrics']['net_return_pct']:+.2f}%")
        print(f"   PF: {best_market[1]['metrics']['profit_factor']:.2f}")
        
        # Save results
        output_file = "/app/trading_system/backend/multi_market_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Results saved to: {output_file}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
