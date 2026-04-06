"""
Strategy Backtest Helper
Helper functions to run backtests on strategies using real_backtester.
"""

import logging
from typing import Dict, Any, List
from real_backtester import real_backtester
from market_data_models import Candle

logger = logging.getLogger(__name__)


def run_strategy_backtest(
    strategy: Dict[str, Any],
    candles: List[Candle],
    initial_balance: float,
    symbol: str,
    timeframe: str
) -> Dict[str, Any]:
    """
    Run backtest on a strategy using real_backtester.
    
    Args:
        strategy: Strategy configuration with genes
        candles: List of Candle objects
        initial_balance: Starting balance
        symbol: Trading symbol
        timeframe: Chart timeframe
        
    Returns:
        Dict with backtest metrics and trade list
    """
    try:
        # Get template ID and genes
        template_id = strategy.get("template_id", "EMA_CROSSOVER")
        genes = strategy.get("genes", {})
        
        # Map template_id to backtester format
        # The backtester expects lowercase with underscores
        template_map = {
            "EMA_CROSSOVER": "ema_crossover",
            "RSI_MEAN_REVERSION": "rsi_mean_reversion",
            "BOLLINGER_BREAKOUT": "bollinger_breakout",
            "ATR_VOLATILITY_BREAKOUT": "atr_volatility_breakout",
            "MACD_TREND": "macd_trend",
        }
        
        # Also support type-based mapping
        strategy_type = strategy.get("type", "")
        if strategy_type == "trend_following":
            template_id = "ema_crossover"
        elif strategy_type == "mean_reversion":
            template_id = "rsi_mean_reversion"
        elif strategy_type == "breakout":
            template_id = "bollinger_breakout"
        else:
            template_id = template_map.get(template_id, "ema_crossover")
        
        # Run backtest
        trades, equity_curve, config = real_backtester.run(
            template_id=template_id,
            genes=genes,
            candles=candles,
            initial_balance=initial_balance
        )
        
        # Calculate metrics from trades
        if not trades:
            return {
                "fitness": 0,
                "sharpe_ratio": 0,
                "max_drawdown_pct": 0,
                "profit_factor": 0,
                "win_rate": 0,
                "net_profit": 0,
                "total_trades": 0,
                "trades": [],
                "equity_curve": []
            }
        
        # Convert trades to dict format
        trade_dicts = []
        for trade in trades:
            trade_dicts.append({
                "id": trade.id,
                "entry_time": trade.entry_time.isoformat(),
                "exit_time": trade.exit_time.isoformat(),
                "direction": trade.direction.value,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "stop_loss": trade.stop_loss,
                "take_profit": trade.take_profit,
                "volume": trade.volume,
                "profit_loss": trade.profit_loss,
                "profit_loss_pips": trade.profit_loss_pips,
                "profit_loss_percent": trade.profit_loss_percent,
                "duration_minutes": trade.duration_minutes,
                "close_reason": trade.close_reason
            })
        
        # Calculate metrics
        winning_trades = [t for t in trades if t.profit_loss > 0]
        losing_trades = [t for t in trades if t.profit_loss <= 0]
        
        total_profit = sum(t.profit_loss for t in winning_trades)
        total_loss = abs(sum(t.profit_loss for t in losing_trades))
        
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
        win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0
        
        net_profit = sum(t.profit_loss for t in trades)
        
        # Calculate Sharpe ratio from equity curve
        if len(equity_curve) > 1:
            returns = []
            for i in range(1, len(equity_curve)):
                prev_equity = equity_curve[i-1].equity
                curr_equity = equity_curve[i].equity
                if prev_equity > 0:
                    ret = (curr_equity - prev_equity) / prev_equity
                    returns.append(ret)
            
            if returns:
                import statistics
                mean_return = statistics.mean(returns)
                std_return = statistics.stdev(returns) if len(returns) > 1 else 0.0001
                sharpe_ratio = (mean_return / std_return) * (252 ** 0.5) if std_return > 0 else 0
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
        
        # Max drawdown from equity curve
        max_dd = max([e.drawdown_percent for e in equity_curve]) if equity_curve else 0
        
        # Calculate fitness score
        # Fitness = weighted combination of metrics
        # Sharpe (40%) + Win Rate (20%) + Profit Factor (20%) - Drawdown penalty (20%)
        sharpe_component = min(40, (sharpe_ratio / 2.0) * 40)
        win_rate_component = min(20, (win_rate / 70) * 20)
        pf_component = min(20, (profit_factor / 2.5) * 20)
        dd_component = max(0, 20 - (max_dd / 40) * 20)
        
        fitness = sharpe_component + win_rate_component + pf_component + dd_component
        
        return {
            "fitness": round(fitness, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "profit_factor": round(profit_factor, 2),
            "win_rate": round(win_rate, 1),
            "net_profit": round(net_profit, 2),
            "total_trades": len(trades),
            "trades": trade_dicts,
            "equity_curve": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "balance": e.balance,
                    "equity": e.equity,
                    "drawdown": e.drawdown,
                    "drawdown_percent": e.drawdown_percent
                }
                for e in equity_curve
            ]
        }
        
    except Exception as e:
        logger.error(f"Backtest failed for {strategy.get('name')}: {str(e)}")
        raise


# Make it compatible with existing code
real_backtester.run_strategy_backtest = run_strategy_backtest
