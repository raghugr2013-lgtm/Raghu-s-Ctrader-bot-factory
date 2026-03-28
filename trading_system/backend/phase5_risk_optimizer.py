#!/usr/bin/env python3
"""
Phase 5: Risk Control & Capital Protection
Optimize position sizing and portfolio allocation
"""
import sys
sys.path.append('/app/trading_system/backend')

import pandas as pd
import numpy as np
import json
from phase3_execution_simulator import ExecutionSimulator

class RiskOptimizer:
    def __init__(self, market_data_dict):
        """
        Initialize with market data
        
        Args:
            market_data_dict: Dict with 'GOLD' and 'SPX' dataframes and trade lists
        """
        self.market_data = market_data_dict
        
    def test_position_sizing(self, market_key, risk_levels=[0.5, 0.25, 0.1]):
        """Test different position sizing levels"""
        
        print(f"\n{'='*80}")
        print(f"POSITION SIZING OPTIMIZATION: {market_key}")
        print('='*80)
        print()
        
        market_data = self.market_data[market_key]
        df = market_data['df']
        trades = market_data['trades']
        spread_pips = market_data['spread_pips']
        pip_value = market_data['pip_value']
        
        results = {}
        
        for risk_pct in risk_levels:
            print(f"📊 Testing {risk_pct}% risk per trade...")
            
            simulator = ExecutionSimulator(
                initial_balance=10000,
                spread_pips=spread_pips,
                commission=0,
                slippage_pips_range=(spread_pips*0.3, spread_pips*0.6)
            )
            simulator.pip_value = pip_value
            
            enhanced_trades, final_balance = simulator.simulate_trades(df, trades, risk_pct=risk_pct)
            metrics = simulator.calculate_metrics(enhanced_trades, final_balance)
            
            # Calculate return/DD ratio
            return_dd_ratio = (metrics['net_return_pct'] / metrics['max_drawdown_pct']) if metrics['max_drawdown_pct'] > 0 else 0
            
            results[risk_pct] = {
                'metrics': metrics,
                'return_dd_ratio': return_dd_ratio
            }
            
            print(f"   Return:          {metrics['net_return_pct']:+.2f}%")
            print(f"   Max DD:          {metrics['max_drawdown_pct']:.2f}%")
            print(f"   Return/DD Ratio: {return_dd_ratio:.2f}")
            print(f"   Profit Factor:   {metrics['profit_factor']:.2f}")
            print()
        
        # Find best risk level (highest return/DD ratio with acceptable DD)
        acceptable = {k: v for k, v in results.items() if v['metrics']['max_drawdown_pct'] < 30}
        
        if acceptable:
            best_risk = max(acceptable.items(), key=lambda x: x[1]['return_dd_ratio'])
            print(f"🏆 Optimal Risk Level: {best_risk[0]}%")
            print(f"   Return: {best_risk[1]['metrics']['net_return_pct']:+.2f}%")
            print(f"   Max DD: {best_risk[1]['metrics']['max_drawdown_pct']:.2f}%")
            print(f"   Return/DD: {best_risk[1]['return_dd_ratio']:.2f}")
        else:
            print("⚠️ No risk level meets DD < 30% criteria")
        
        return results
    
    def add_equity_stop(self, trades, df, risk_pct=0.5, stop_dd_pct=25, spread_pips=0.5, pip_value=0.1):
        """
        Simulate trading with equity stop
        
        Stops trading when drawdown exceeds threshold
        """
        print(f"\n{'='*80}")
        print(f"EQUITY STOP SIMULATION")
        print('='*80)
        print(f"Stop Level: {stop_dd_pct}% drawdown")
        print()
        
        simulator = ExecutionSimulator(
            initial_balance=10000,
            spread_pips=spread_pips,
            commission=0,
            slippage_pips_range=(spread_pips*0.3, spread_pips*0.6)
        )
        simulator.pip_value = pip_value
        
        # Simulate with equity stop
        balance = simulator.initial_balance
        peak_balance = balance
        enhanced_trades = []
        trading_stopped = False
        stop_triggered_at = None
        
        np.random.seed(42)
        
        for trade in trades:
            # Check if trading should be stopped
            current_dd = ((peak_balance - balance) / peak_balance) * 100 if peak_balance > 0 else 0
            
            if current_dd >= stop_dd_pct and not trading_stopped:
                trading_stopped = True
                stop_triggered_at = trade['entry_time']
                print(f"🛑 Equity stop triggered at {stop_dd_pct}% drawdown")
                print(f"   Balance: ${balance:.2f}")
                print(f"   Date: {stop_triggered_at}")
                break
            
            # Process trade (simplified from ExecutionSimulator)
            entry_price = trade['entry_price']
            exit_price = trade['exit_price']
            direction = trade['direction']
            
            # Slippage
            entry_price_actual = entry_price + np.random.uniform(-spread_pips*pip_value, spread_pips*pip_value)
            exit_price_actual = exit_price + np.random.uniform(-spread_pips*pip_value, spread_pips*pip_value)
            
            # Position size
            stop_loss_pips = 50
            risk_amount = balance * (risk_pct / 100)
            position_size = risk_amount / (stop_loss_pips * pip_value)
            
            # P&L
            if direction == 'LONG':
                raw_pnl = (exit_price_actual - entry_price_actual) * position_size
            else:
                raw_pnl = (entry_price_actual - exit_price_actual) * position_size
            
            spread_cost = spread_pips * pip_value * position_size
            net_pnl = raw_pnl - spread_cost
            
            balance += net_pnl
            
            if balance > peak_balance:
                peak_balance = balance
            
            enhanced_trades.append({
                'net_pnl': net_pnl,
                'balance_after': balance
            })
        
        final_balance = balance
        max_dd = ((peak_balance - min([t['balance_after'] for t in enhanced_trades])) / peak_balance) * 100 if enhanced_trades else 0
        net_return = ((final_balance - simulator.initial_balance) / simulator.initial_balance) * 100
        
        print(f"\n📊 Results with Equity Stop:")
        print(f"   Final Balance:   ${final_balance:.2f}")
        print(f"   Net Return:      {net_return:+.2f}%")
        print(f"   Max DD:          {max_dd:.2f}%")
        print(f"   Trades Taken:    {len(enhanced_trades)}/{len(trades)}")
        
        if trading_stopped:
            print(f"   ⚠️ Trading stopped early to protect capital")
        else:
            print(f"   ✅ Completed full test period")
        
        return {
            'final_balance': final_balance,
            'net_return_pct': net_return,
            'max_dd_pct': max_dd,
            'trades_taken': len(enhanced_trades),
            'total_trades': len(trades),
            'stopped': trading_stopped
        }
    
    def test_portfolio(self, allocations=[(60, 40), (50, 50), (70, 30)]):
        """
        Test portfolio combinations of Gold and S&P 500
        
        Args:
            allocations: List of (gold_pct, spx_pct) tuples
        """
        print(f"\n{'='*80}")
        print(f"PORTFOLIO OPTIMIZATION")
        print('='*80)
        print()
        
        gold_data = self.market_data['GOLD']
        spx_data = self.market_data['SPX']
        
        results = {}
        
        for gold_pct, spx_pct in allocations:
            print(f"📊 Testing {gold_pct}% Gold / {spx_pct}% S&P 500...")
            
            # Allocate capital
            gold_capital = 10000 * (gold_pct / 100)
            spx_capital = 10000 * (spx_pct / 100)
            
            # Run Gold simulation
            gold_sim = ExecutionSimulator(
                initial_balance=gold_capital,
                spread_pips=gold_data['spread_pips'],
                commission=0,
                slippage_pips_range=(gold_data['spread_pips']*0.3, gold_data['spread_pips']*0.6)
            )
            gold_sim.pip_value = gold_data['pip_value']
            
            gold_trades, gold_final = gold_sim.simulate_trades(
                gold_data['df'], gold_data['trades'], risk_pct=0.25  # Reduced risk
            )
            gold_metrics = gold_sim.calculate_metrics(gold_trades, gold_final)
            
            # Run S&P simulation
            spx_sim = ExecutionSimulator(
                initial_balance=spx_capital,
                spread_pips=spx_data['spread_pips'],
                commission=0,
                slippage_pips_range=(spx_data['spread_pips']*0.3, spx_data['spread_pips']*0.6)
            )
            spx_sim.pip_value = spx_data['pip_value']
            
            spx_trades, spx_final = spx_sim.simulate_trades(
                spx_data['df'], spx_data['trades'], risk_pct=0.4  # Slightly higher for S&P (lower volatility)
            )
            spx_metrics = spx_sim.calculate_metrics(spx_trades, spx_final)
            
            # Combined metrics
            combined_final = gold_final + spx_final
            combined_return = ((combined_final - 10000) / 10000) * 100
            
            # Approximate combined DD (conservative estimate)
            combined_dd = max(gold_metrics['max_drawdown_pct'] * (gold_pct/100),
                            spx_metrics['max_drawdown_pct'] * (spx_pct/100))
            
            # Combined Sharpe (weighted)
            combined_sharpe = (gold_metrics['sharpe_like_ratio'] * (gold_pct/100) +
                             spx_metrics['sharpe_like_ratio'] * (spx_pct/100))
            
            return_dd_ratio = combined_return / combined_dd if combined_dd > 0 else 0
            
            results[f"{gold_pct}/{spx_pct}"] = {
                'allocation': f"{gold_pct}% Gold / {spx_pct}% S&P",
                'combined_return_pct': combined_return,
                'combined_dd_pct': combined_dd,
                'combined_sharpe': combined_sharpe,
                'return_dd_ratio': return_dd_ratio,
                'gold_return': gold_metrics['net_return_pct'],
                'spx_return': spx_metrics['net_return_pct']
            }
            
            print(f"   Combined Return:  {combined_return:+.2f}%")
            print(f"   Combined DD:      {combined_dd:.2f}%")
            print(f"   Return/DD Ratio:  {return_dd_ratio:.2f}")
            print(f"   Combined Sharpe:  {combined_sharpe:.3f}")
            print(f"   (Gold: {gold_metrics['net_return_pct']:+.2f}%, S&P: {spx_metrics['net_return_pct']:+.2f}%)")
            print()
        
        # Find best portfolio
        best_portfolio = max(results.items(), key=lambda x: x[1]['return_dd_ratio'])
        
        print(f"🏆 Optimal Portfolio: {best_portfolio[1]['allocation']}")
        print(f"   Return: {best_portfolio[1]['combined_return_pct']:+.2f}%")
        print(f"   Max DD: {best_portfolio[1]['combined_dd_pct']:.2f}%")
        print(f"   Return/DD: {best_portfolio[1]['return_dd_ratio']:.2f}")
        print(f"   Sharpe: {best_portfolio[1]['combined_sharpe']:.3f}")
        
        return results

def main():
    print("\n" + "="*80)
    print("PHASE 5: RISK CONTROL & CAPITAL PROTECTION")
    print("="*80)
    print()
    
    # Load Gold and S&P data (reuse from multi-market test)
    print("📥 Loading market data...")
    
    # For this demo, we'll load from the previous results
    # In production, this would fetch fresh data
    
    import yfinance as yf
    from datetime import datetime, timedelta
    
    # Download Gold data
    print("   Gold (XAUUSD)...")
    gold_ticker = yf.Ticker("GC=F")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    gold_df = gold_ticker.history(start=start_date, end=end_date, interval='1h')
    
    if len(gold_df) == 0:
        print("❌ Could not load Gold data")
        return
    
    gold_df = gold_df.reset_index()
    if 'Datetime' in gold_df.columns:
        gold_df = gold_df.rename(columns={'Datetime': 'timestamp'})
    elif 'Date' in gold_df.columns:
        gold_df = gold_df.rename(columns={'Date': 'timestamp'})
    
    gold_df = gold_df.rename(columns={
        'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
    })
    gold_df = gold_df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].dropna()
    gold_df['timestamp'] = pd.to_datetime(gold_df['timestamp'])
    
    # Download S&P data
    print("   S&P 500...")
    spx_ticker = yf.Ticker("^GSPC")
    spx_df = spx_ticker.history(start=start_date, end=end_date, interval='1h')
    
    if len(spx_df) == 0:
        print("❌ Could not load S&P data")
        return
    
    spx_df = spx_df.reset_index()
    if 'Datetime' in spx_df.columns:
        spx_df = spx_df.rename(columns={'Datetime': 'timestamp'})
    elif 'Date' in spx_df.columns:
        spx_df = spx_df.rename(columns={'Date': 'timestamp'})
    
    spx_df = spx_df.rename(columns={
        'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
    })
    spx_df = spx_df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].dropna()
    spx_df['timestamp'] = pd.to_datetime(spx_df['timestamp'])
    
    print(f"   ✅ Gold: {len(gold_df)} candles")
    print(f"   ✅ S&P: {len(spx_df)} candles")
    print()
    
    # Run strategy on both (reuse from multi-market tester)
    from multi_market_tester import MultiMarketTester
    
    tester = MultiMarketTester()
    
    gold_trades = tester.run_ema_strategy(gold_df)
    spx_trades = tester.run_ema_strategy(spx_df)
    
    print(f"📊 Generated trades:")
    print(f"   Gold: {len(gold_trades)} trades")
    print(f"   S&P:  {len(spx_trades)} trades")
    
    # Prepare market data
    market_data = {
        'GOLD': {
            'df': gold_df,
            'trades': gold_trades,
            'spread_pips': 0.50,
            'pip_value': 0.10
        },
        'SPX': {
            'df': spx_df,
            'trades': spx_trades,
            'spread_pips': 0.25,
            'pip_value': 1.0
        }
    }
    
    optimizer = RiskOptimizer(market_data)
    
    # 1. Test position sizing
    print("\n" + "="*80)
    print("PART 1: POSITION SIZING OPTIMIZATION")
    print("="*80)
    
    gold_sizing_results = optimizer.test_position_sizing('GOLD', risk_levels=[0.5, 0.25, 0.1])
    
    # 2. Test equity stop
    print("\n" + "="*80)
    print("PART 2: EQUITY STOP PROTECTION")
    print("="*80)
    
    equity_stop_result = optimizer.add_equity_stop(
        gold_trades, gold_df,
        risk_pct=0.25,
        stop_dd_pct=25,
        spread_pips=0.50,
        pip_value=0.10
    )
    
    # 3. Test portfolio allocations
    print("\n" + "="*80)
    print("PART 3: PORTFOLIO DIVERSIFICATION")
    print("="*80)
    
    portfolio_results = optimizer.test_portfolio(allocations=[(60, 40), (50, 50), (70, 30), (40, 60)])
    
    # Final recommendations
    print("\n" + "="*80)
    print("FINAL RECOMMENDATIONS")
    print("="*80)
    print()
    
    # Save all results
    results = {
        'position_sizing': {k: v['metrics'] for k, v in gold_sizing_results.items()},
        'equity_stop': equity_stop_result,
        'portfolio': portfolio_results
    }
    
    with open('/app/trading_system/backend/risk_optimization_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print("💾 Results saved to: /app/trading_system/backend/risk_optimization_results.json")
    print()

if __name__ == "__main__":
    main()
