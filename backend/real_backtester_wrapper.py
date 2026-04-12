"""
Wrapper for RealBacktester to provide run_backtest method
and convert results to dictionary format expected by pipeline.
"""

from typing import Dict, List, Any
from real_backtester import RealBacktester as OriginalRealBacktester
import logging

logger = logging.getLogger(__name__)


class RealBacktesterWrapper:
    """
    Wrapper around RealBacktester that provides run_backtest() method
    and converts results to dict format for pipeline compatibility.
    """
    
    def __init__(self):
        self.backtester = OriginalRealBacktester()
    
    def run_backtest(
        self,
        strategy: Dict[str, Any],
        candles: List[Dict],
        initial_balance: float = 10000.0
    ) -> Dict[str, Any]:
        """
        Run backtest on strategy with real candles.
        
        Args:
            strategy: Strategy dict with template_id and parameters
            candles: List of candle dicts with OHLCV data
            initial_balance: Starting balance
            
        Returns:
            Dict with backtest results
        """
        logger.info(f"   🔄 RealBacktester starting - {len(candles):,} candles")
        
        # Extract template and genes from strategy
        template_id = strategy.get('template_id', strategy.get('strategy_type', 'ema_crossover'))
        
        # Build genes dict from strategy parameters
        genes = {
            'fast_ema': strategy.get('fast_ema', strategy.get('ema_fast', 10)),
            'slow_ema': strategy.get('slow_ema', strategy.get('ema_slow', 30)),
            'rsi_period': strategy.get('rsi_period', 14),
            'rsi_oversold': strategy.get('rsi_oversold', 30),
            'rsi_overbought': strategy.get('rsi_overbought', 70),
            'bb_period': strategy.get('bb_period', 20),
            'bb_std': strategy.get('bb_std', 2.0),
            'atr_period': strategy.get('atr_period', 14),
            'atr_multiplier': strategy.get('atr_multiplier', 2.0),
            'sl_atr_mult': strategy.get('sl_atr_mult', 1.5),
            'tp_atr_mult': strategy.get('tp_atr_mult', 3.0),
            'risk_per_trade_pct': strategy.get('risk_per_trade_pct', 1.0),
        }
        
        # Convert candle dicts to Candle objects
        from market_data_models import Candle
        candle_objects = []
        
        for c in candles:
            try:
                candle = Candle(
                    symbol=c.get('symbol', 'EURUSD'),
                    timestamp=c.get('timestamp'),
                    timeframe="1m",  # Use "1m" instead of "M1" for enum compatibility
                    open=float(c.get('open', 0)),
                    high=float(c.get('high', 0)),
                    low=float(c.get('low', 0)),
                    close=float(c.get('close', 0)),
                    volume=int(c.get('volume', 0)),
                    confidence="high"
                )
                candle_objects.append(candle)
            except Exception as e:
                logger.error(f"Error converting candle: {e}")
                continue
        
        if len(candle_objects) < 100:
            raise Exception(f"Insufficient valid candles: {len(candle_objects)} (need at least 100)")
        
        logger.info(f"   📊 Converted {len(candle_objects):,} candles to objects")
        
        # Run real backtest
        try:
            trades, equity_curve, config = self.backtester.run(
                template_id=template_id,
                genes=genes,
                candles=candle_objects,
                initial_balance=initial_balance
            )
            
            logger.info(f"   ✅ Backtest complete - {len(trades)} trades generated")
            
        except Exception as e:
            logger.error(f"   ❌ Backtest execution failed: {e}")
            raise
        
        # Calculate metrics
        if len(trades) == 0:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'net_profit': 0.0,
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'sharpe_ratio': 0.0,
                'final_balance': initial_balance,
                'roi_pct': 0.0,
            }
        
        # Calculate statistics
        winning_trades = [t for t in trades if t.profit_loss and t.profit_loss > 0]
        losing_trades = [t for t in trades if t.profit_loss and t.profit_loss <= 0]
        
        total_profit = sum(t.profit_loss for t in winning_trades if t.profit_loss)
        total_loss = abs(sum(t.profit_loss for t in losing_trades if t.profit_loss))
        
        profit_factor = total_profit / total_loss if total_loss > 0 else (total_profit if total_profit > 0 else 0)
        win_rate = (len(winning_trades) / len(trades)) * 100 if trades else 0
        
        net_profit = sum(t.profit_loss for t in trades if t.profit_loss)
        final_balance = initial_balance + net_profit
        roi_pct = (net_profit / initial_balance) * 100
        
        # Calculate max drawdown
        max_dd = 0
        max_dd_pct = 0
        if equity_curve:
            for point in equity_curve:
                if point.drawdown > max_dd:
                    max_dd = point.drawdown
                if point.drawdown_percent > max_dd_pct:
                    max_dd_pct = point.drawdown_percent
        
        # Simplified Sharpe calculation
        sharpe_ratio = 0.0
        if trades and len(trades) > 1:
            returns = [t.profit_loss / initial_balance for t in trades if t.profit_loss]
            if returns:
                import numpy as np
                if np.std(returns) > 0:
                    sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252)
        
        result = {
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'net_profit': net_profit,
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd_pct,
            'sharpe_ratio': sharpe_ratio,
            'final_balance': final_balance,
            'roi_pct': roi_pct,
            'initial_balance': initial_balance,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'avg_win': total_profit / len(winning_trades) if winning_trades else 0,
            'avg_loss': total_loss / len(losing_trades) if losing_trades else 0,
            'candles_processed': len(candle_objects),
        }
        
        logger.info(f"   📈 Results: {len(trades)} trades, PF={profit_factor:.2f}, WR={win_rate:.1f}%")
        
        return result
