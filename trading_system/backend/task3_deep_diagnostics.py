#!/usr/bin/env python3
"""
TASK 3: Deep Diagnostics - Edge Identification
Analyze where profits come from and where losses occur
"""

import pandas as pd
import numpy as np
import sys
sys.path.append('/app/trading_system/backend')

from strategy_backtest_framework import SimpleBacktester, BacktestConfig, BacktestResult
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class StrategyDiagnostics:
    """Deep diagnostic analysis of strategy performance"""
    
    def __init__(self, result: BacktestResult, data: pd.DataFrame):
        """
        Initialize diagnostics
        
        Args:
            result: BacktestResult from backtest
            data: Original OHLC data with indicators
        """
        self.result = result
        self.data = data
        self.trades_df = self._create_trades_dataframe()
    
    def _create_trades_dataframe(self):
        """Convert trades to DataFrame for analysis"""
        if not self.result.trades:
            return pd.DataFrame()
        
        trades_data = []
        for trade in self.result.trades:
            trades_data.append({
                'entry_time': trade.entry_time,
                'exit_time': trade.exit_time,
                'direction': trade.direction,
                'profit_usd': trade.profit_usd,
                'profit_pips': trade.profit_pips,
                'duration_hours': trade.duration_hours,
                'session': trade.session,
                'is_winner': trade.profit_usd > 0
            })
        
        return pd.DataFrame(trades_data)
    
    def classify_market_regime(self):
        """Classify each trade by market regime"""
        if self.trades_df.empty:
            return self.trades_df
        
        df = self.trades_df.copy()
        
        # Add market regime at entry
        for idx, trade in df.iterrows():
            entry_idx = self.data.index.get_indexer([trade['entry_time']], method='nearest')[0]
            if entry_idx >= 0 and entry_idx < len(self.data):
                ema_50 = self.data.iloc[entry_idx]['ema_50']
                ema_200 = self.data.iloc[entry_idx]['ema_200']
                
                # Calculate regime
                if pd.notna(ema_50) and pd.notna(ema_200):
                    diff_pct = ((ema_50 - ema_200) / ema_200) * 100
                    
                    if diff_pct > 0.5:
                        regime = 'bull_trend'
                    elif diff_pct < -0.5:
                        regime = 'bear_trend'
                    else:
                        regime = 'ranging'
                else:
                    regime = 'unknown'
                
                df.at[idx, 'market_regime'] = regime
        
        return df
    
    def classify_volatility(self):
        """Classify each trade by volatility level"""
        if self.trades_df.empty:
            return self.trades_df
        
        df = self.trades_df.copy()
        
        # Calculate ATR percentiles from full dataset
        atr_values = self.data['atr_14'].dropna()
        low_threshold = atr_values.quantile(0.33)
        high_threshold = atr_values.quantile(0.67)
        
        # Add volatility at entry
        for idx, trade in df.iterrows():
            entry_idx = self.data.index.get_indexer([trade['entry_time']], method='nearest')[0]
            if entry_idx >= 0 and entry_idx < len(self.data):
                atr = self.data.iloc[entry_idx]['atr_14']
                
                if pd.notna(atr):
                    if atr < low_threshold:
                        volatility = 'low'
                    elif atr > high_threshold:
                        volatility = 'high'
                    else:
                        volatility = 'medium'
                else:
                    volatility = 'unknown'
                
                df.at[idx, 'volatility'] = volatility
        
        return df
    
    def classify_duration(self):
        """Classify trades by duration"""
        if self.trades_df.empty:
            return self.trades_df
        
        df = self.trades_df.copy()
        
        df['duration_category'] = pd.cut(
            df['duration_hours'],
            bins=[0, 10, 30, float('inf')],
            labels=['short (<10h)', 'medium (10-30h)', 'long (>30h)']
        )
        
        return df
    
    def analyze_by_dimension(self, dimension: str):
        """
        Analyze performance by a specific dimension
        
        Args:
            dimension: Column name to group by
            
        Returns:
            DataFrame with metrics per dimension
        """
        df = self.trades_df.copy()
        
        if dimension not in df.columns or df[dimension].isna().all():
            return None
        
        # Group by dimension
        groups = df.groupby(dimension)
        
        results = []
        for name, group in groups:
            winners = group[group['is_winner']]
            losers = group[~group['is_winner']]
            
            total_profit = winners['profit_usd'].sum() if len(winners) > 0 else 0
            total_loss = losers['profit_usd'].sum() if len(losers) > 0 else 0
            
            pf = abs(total_profit / total_loss) if total_loss != 0 else 0
            win_rate = (len(winners) / len(group)) * 100 if len(group) > 0 else 0
            
            # Calculate drawdown for this subset
            equity = [0]
            for _, trade in group.iterrows():
                equity.append(equity[-1] + trade['profit_usd'])
            
            equity_array = np.array(equity)
            running_max = np.maximum.accumulate(equity_array)
            drawdown = running_max - equity_array
            max_dd = np.max(drawdown)
            
            results.append({
                'Condition': name,
                'PF': pf,
                'Win Rate': win_rate,
                'Trades': len(group),
                'Winners': len(winners),
                'Losers': len(losers),
                'Total P&L': total_profit + total_loss,
                'Avg Trade': group['profit_usd'].mean(),
                'Max DD': max_dd
            })
        
        return pd.DataFrame(results).sort_values('PF', ascending=False)
    
    def generate_full_report(self):
        """Generate comprehensive diagnostic report"""
        print("\n" + "="*70)
        print(f"DEEP DIAGNOSTICS: {self.result.strategy_name} - {self.result.symbol}")
        print("="*70)
        
        # Classify all dimensions
        self.trades_df = self.classify_market_regime()
        self.trades_df = self.classify_volatility()
        self.trades_df = self.classify_duration()
        
        print(f"\n📊 BASELINE PERFORMANCE:")
        print(f"   Total Trades: {self.result.total_trades}")
        print(f"   Profit Factor: {self.result.profit_factor:.2f}")
        print(f"   Win Rate: {self.result.win_rate:.1f}%")
        print(f"   Net Profit: ${self.result.net_profit:.2f}")
        print(f"   Max Drawdown: ${self.result.max_drawdown:.2f} ({self.result.max_drawdown_pct:.1f}%)")
        
        # 1. Market Regime Analysis
        print(f"\n{'='*70}")
        print("1. MARKET REGIME ANALYSIS")
        print(f"{'='*70}")
        
        regime_results = self.analyze_by_dimension('market_regime')
        if regime_results is not None:
            print("\n" + regime_results.to_string(index=False))
            
            # Identify best regime
            best_regime = regime_results.iloc[0]
            print(f"\n✅ BEST REGIME: {best_regime['Condition']}")
            print(f"   PF: {best_regime['PF']:.2f} | WR: {best_regime['Win Rate']:.1f}% | Trades: {int(best_regime['Trades'])}")
        
        # 2. Volatility Analysis
        print(f"\n{'='*70}")
        print("2. VOLATILITY SEGMENTATION (ATR-based)")
        print(f"{'='*70}")
        
        vol_results = self.analyze_by_dimension('volatility')
        if vol_results is not None:
            print("\n" + vol_results.to_string(index=False))
            
            best_vol = vol_results.iloc[0]
            print(f"\n✅ BEST VOLATILITY: {best_vol['Condition']}")
            print(f"   PF: {best_vol['PF']:.2f} | WR: {best_vol['Win Rate']:.1f}% | Trades: {int(best_vol['Trades'])}")
        
        # 3. Session Analysis
        print(f"\n{'='*70}")
        print("3. SESSION PERFORMANCE")
        print(f"{'='*70}")
        
        session_results = self.analyze_by_dimension('session')
        if session_results is not None:
            print("\n" + session_results.to_string(index=False))
            
            best_session = session_results.iloc[0]
            print(f"\n✅ BEST SESSION: {best_session['Condition']}")
            print(f"   PF: {best_session['PF']:.2f} | WR: {best_session['Win Rate']:.1f}% | Trades: {int(best_session['Trades'])}")
        
        # 4. Duration Analysis
        print(f"\n{'='*70}")
        print("4. TRADE DURATION ANALYSIS")
        print(f"{'='*70}")
        
        duration_results = self.analyze_by_dimension('duration_category')
        if duration_results is not None:
            print("\n" + duration_results.to_string(index=False))
            
            best_duration = duration_results.iloc[0]
            print(f"\n✅ BEST DURATION: {best_duration['Condition']}")
            print(f"   PF: {best_duration['PF']:.2f} | WR: {best_duration['Win Rate']:.1f}% | Trades: {int(best_duration['Trades'])}")
        
        # 5. Combined Analysis
        print(f"\n{'='*70}")
        print("5. KEY INSIGHTS & RECOMMENDATIONS")
        print(f"{'='*70}")
        
        self._generate_insights(regime_results, vol_results, session_results, duration_results)
        
        return {
            'regime': regime_results,
            'volatility': vol_results,
            'session': session_results,
            'duration': duration_results
        }
    
    def _generate_insights(self, regime_df, vol_df, session_df, duration_df):
        """Generate actionable insights from analysis"""
        print("\n🎯 PROFITABLE CONDITIONS (Keep These):")
        
        filters = []
        
        # Best regime
        if regime_df is not None and len(regime_df) > 0:
            best = regime_df.iloc[0]
            if best['PF'] > 1.5:
                filters.append(f"   ✅ Trade in {best['Condition']} markets")
        
        # Best volatility
        if vol_df is not None and len(vol_df) > 0:
            best = vol_df.iloc[0]
            if best['PF'] > 1.5:
                filters.append(f"   ✅ Trade during {best['Condition']} volatility")
        
        # Best session
        if session_df is not None and len(session_df) > 0:
            best = session_df.iloc[0]
            if best['PF'] > 1.5:
                filters.append(f"   ✅ Focus on {best['Condition']} session")
        
        # Best duration
        if duration_df is not None and len(duration_df) > 0:
            best = duration_df.iloc[0]
            if best['PF'] > 1.5:
                filters.append(f"   ✅ Prefer {best['Condition']} trades")
        
        if filters:
            for f in filters:
                print(f)
        else:
            print("   ⚠️  No clear strong filters identified (all conditions similar)")
        
        print("\n❌ LOSING CONDITIONS (Eliminate These):")
        
        # Worst regime
        if regime_df is not None and len(regime_df) > 0:
            worst = regime_df.iloc[-1]
            if worst['PF'] < 1.0:
                print(f"   ❌ Avoid {worst['Condition']} markets (PF: {worst['PF']:.2f})")
        
        # Worst volatility
        if vol_df is not None and len(vol_df) > 0:
            worst = vol_df.iloc[-1]
            if worst['PF'] < 1.0:
                print(f"   ❌ Avoid {worst['Condition']} volatility (PF: {worst['PF']:.2f})")
        
        # Worst session
        if session_df is not None and len(session_df) > 0:
            worst = session_df.iloc[-1]
            if worst['PF'] < 1.0:
                print(f"   ❌ Skip {worst['Condition']} session (PF: {worst['PF']:.2f})")
        
        print(f"\n{'='*70}")


def load_clean_data(symbol):
    """Load clean CSV data"""
    filepath = f'/tmp/{symbol.lower()}_h1_clean.csv'
    df = pd.read_csv(filepath)
    df['time'] = pd.to_datetime(df['time'], format='mixed')
    df = df.set_index('time')
    return df


def run_diagnostics():
    """Run deep diagnostics on XAUUSD Mean Reversion strategy"""
    
    print("\n" + "="*70)
    print("TASK 3: DEEP DIAGNOSTICS - EDGE IDENTIFICATION")
    print("PRIMARY FOCUS: XAUUSD Mean Reversion Strategy")
    print("="*70)
    
    # Configuration
    config = BacktestConfig(
        initial_balance=10000,
        risk_per_trade_pct=1.0,
        spread_pips=2.0,
        slippage_pips=1.0,
        commission_per_lot=7.0,
        max_position_size=0.1
    )
    
    # Load XAUUSD data
    print("\n📥 Loading XAUUSD data...")
    df = load_clean_data('XAUUSD')
    logger.info(f"Loaded {len(df)} candles")
    
    # Run backtest
    print("🔄 Running Mean Reversion backtest...")
    backtester = SimpleBacktester(df, config, 'XAUUSD')
    backtester.calculate_indicators()
    
    signals = backtester.mean_reversion_strategy()
    result = backtester.execute_backtest(signals, "Mean Reversion")
    
    # Run diagnostics
    diagnostics = StrategyDiagnostics(result, backtester.data)
    analysis = diagnostics.generate_full_report()
    
    print("\n" + "="*70)
    print("✅ TASK 3 COMPLETE - Edge Identified")
    print("="*70)
    
    return analysis


if __name__ == '__main__':
    analysis = run_diagnostics()
