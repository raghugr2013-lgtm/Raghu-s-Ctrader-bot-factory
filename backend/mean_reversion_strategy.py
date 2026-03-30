"""
MEAN REVERSION STRATEGY for RANGING Markets

Trades range-bound conditions using:
- Bollinger Bands (buy oversold, sell overbought)
- RSI confirmation
- Mean reversion to middle band
"""

import logging
from typing import List, Tuple, Dict, Optional
from datetime import datetime

from market_data_models import Candle
from backtest_models import TradeRecord, EquityPoint, BacktestConfig
from backtest_real_engine import _calculate_ema, _calculate_rsi, _create_trade
from improved_eurusd_strategy import calculate_atr, get_trading_session, TradingSession

logger = logging.getLogger(__name__)


def calculate_bollinger_bands(
    candles: List[Candle], 
    period: int = 20, 
    std_dev: float = 2.0
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """Calculate Bollinger Bands"""
    middle = [None] * len(candles)
    upper = [None] * len(candles)
    lower = [None] * len(candles)
    
    if len(candles) < period:
        return middle, upper, lower
    
    for i in range(period - 1, len(candles)):
        period_closes = [candles[j].close for j in range(i - period + 1, i + 1)]
        
        sma = sum(period_closes) / period
        variance = sum((x - sma) ** 2 for x in period_closes) / period
        std = variance ** 0.5
        
        middle[i] = sma
        upper[i] = sma + (std_dev * std)
        lower[i] = sma - (std_dev * std)
    
    return middle, upper, lower


def run_mean_reversion_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Mean Reversion Strategy for Ranging Markets
    
    Entry Logic:
    - BUY when price touches/breaks lower BB AND RSI < 30
    - SELL when price touches/breaks upper BB AND RSI > 70
    
    Exit Logic:
    - Target: Middle BB (mean reversion)
    - Stop: ATR-based beyond BB
    
    Parameters:
    - bb_period: 20 (BB calculation period)
    - bb_std_dev: 2.0 (BB standard deviations)
    - rsi_period: 14
    - rsi_oversold: 35 (buy threshold)
    - rsi_overbought: 65 (sell threshold)
    - entry_bb_penetration: 0.0003 (must penetrate BB by this %)
    - stop_loss_atr_mult: 2.5 (stop beyond BB)
    - base_risk_pct: 0.5 (conservative for ranging)
    - max_trades_per_day: 2
    """
    
    default_params = {
        # Bollinger Bands
        "bb_period": 20,
        "bb_std_dev": 2.0,
        
        # RSI
        "rsi_period": 14,
        "rsi_oversold": 35,    # More lenient than traditional 30
        "rsi_overbought": 65,  # More lenient than traditional 70
        
        # Entry rules
        "entry_bb_penetration": 0.0003,  # Must penetrate BB by 0.03%
        "require_rsi_confirmation": True,
        
        # Risk management
        "base_risk_pct": 0.5,           # Conservative
        "stop_loss_atr_mult": 2.5,      # Wider stop for ranges
        "target_middle_bb": True,       # Exit at middle band
        "use_trailing_stop": False,     # Don't trail in ranges
        "max_trades_per_day": 2,
        "min_candles_between_trades": 3,
        
        # ATR
        "atr_period": 14,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running MEAN REVERSION strategy for ranging markets")
    
    # Calculate indicators
    bb_middle, bb_upper, bb_lower = calculate_bollinger_bands(
        candles, p["bb_period"], p["bb_std_dev"]
    )
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    
    # State
    trades = []
    equity_curve = []
    balance = config.initial_balance
    peak_balance = balance
    position = None
    trades_per_day = {}
    last_exit_index = -100
    
    # Statistics
    signal_counts = {"bb_lower_touch": 0, "bb_upper_touch": 0}
    
    for i, candle in enumerate(candles):
        current_equity = balance
        
        # Update position
        if position:
            if position["direction"] == "BUY":
                unrealized_pnl = (candle.close - position["entry_price"]) * 10000 * 10 * position["lots"]
            else:
                unrealized_pnl = (position["entry_price"] - candle.close) * 10000 * 10 * position["lots"]
            current_equity = balance + unrealized_pnl
        
        # Drawdown
        if current_equity > peak_balance:
            peak_balance = current_equity
        drawdown = peak_balance - current_equity
        drawdown_pct = (drawdown / peak_balance * 100) if peak_balance > 0 else 0
        
        equity_curve.append(EquityPoint(
            timestamp=candle.timestamp,
            balance=balance,
            equity=current_equity,
            drawdown=drawdown,
            drawdown_percent=drawdown_pct,
        ))
        
        # Skip if indicators not ready
        if (bb_middle[i] is None or bb_upper[i] is None or bb_lower[i] is None or
            rsi[i] is None or atr[i] is None or i < p["bb_period"]):
            continue
        
        # Session and day tracking
        session = get_trading_session(candle.timestamp)
        day_key = candle.timestamp.date()
        if day_key not in trades_per_day:
            trades_per_day[day_key] = 0
        
        # Exit management
        if position:
            exit_reason = None
            exit_price = None
            
            if position["direction"] == "BUY":
                # Stop loss
                if candle.low <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                # Target: Middle BB (mean reversion)
                elif p["target_middle_bb"] and candle.high >= bb_middle[i]:
                    exit_price = bb_middle[i]
                    exit_reason = "Target (Middle BB)"
                # Alternative: Upper BB touch
                elif candle.high >= bb_upper[i]:
                    exit_price = min(candle.close, bb_upper[i])
                    exit_reason = "Upper BB Touch"
            
            else:  # SELL
                # Stop loss
                if candle.high >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                # Target: Middle BB (mean reversion)
                elif p["target_middle_bb"] and candle.low <= bb_middle[i]:
                    exit_price = bb_middle[i]
                    exit_reason = "Target (Middle BB)"
                # Alternative: Lower BB touch
                elif candle.low <= bb_lower[i]:
                    exit_price = max(candle.close, bb_lower[i])
                    exit_reason = "Lower BB Touch"
            
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trade.profit_loss *= position["lots"]
                trades.append(trade)
                balance += trade.profit_loss
                last_exit_index = i
                position = None
        
        # Entry logic - Mean Reversion
        if position is None:
            # Basic filters
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            if session not in [TradingSession.LONDON, TradingSession.OVERLAP, TradingSession.NY]:
                continue
            
            if i - last_exit_index < p["min_candles_between_trades"]:
                continue
            
            # LONG Entry: Price at/below lower BB + RSI oversold
            lower_bb_penetration = (bb_lower[i] - candle.low) / bb_lower[i]
            
            if lower_bb_penetration >= -p["entry_bb_penetration"]:  # At or slightly below
                # Check RSI confirmation
                rsi_confirmed = not p["require_rsi_confirmation"] or rsi[i] < p["rsi_oversold"]
                
                if rsi_confirmed:
                    # LONG Entry
                    entry_price = candle.close
                    stop_loss = entry_price - (atr[i] * p["stop_loss_atr_mult"])
                    
                    # Target is middle BB
                    if p["target_middle_bb"]:
                        take_profit = bb_middle[i]
                    else:
                        take_profit = entry_price + (atr[i] * 2.0)
                    
                    # Position sizing
                    risk_amount = balance * (p["base_risk_pct"] / 100)
                    stop_distance_pips = (entry_price - stop_loss) * 10000
                    
                    if stop_distance_pips > 0:
                        lots = risk_amount / (stop_distance_pips * 10)
                        lots = max(0.01, min(lots, 5.0))  # Conservative max
                    else:
                        lots = 0.01
                    
                    position = {
                        "direction": "BUY",
                        "entry_price": entry_price,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "lots": lots,
                        "entry_type": "mean_reversion",
                    }
                    trades_per_day[day_key] += 1
                    signal_counts["bb_lower_touch"] += 1
                    
                    logger.debug(f"MR LONG: {entry_price:.5f}, RSI: {rsi[i]:.1f}, "
                               f"BB Lower: {bb_lower[i]:.5f}, Target: {take_profit:.5f}")
            
            # SHORT Entry: Price at/above upper BB + RSI overbought
            upper_bb_penetration = (candle.high - bb_upper[i]) / bb_upper[i]
            
            if upper_bb_penetration >= -p["entry_bb_penetration"]:  # At or slightly above
                # Check RSI confirmation
                rsi_confirmed = not p["require_rsi_confirmation"] or rsi[i] > p["rsi_overbought"]
                
                if rsi_confirmed:
                    # SHORT Entry
                    entry_price = candle.close
                    stop_loss = entry_price + (atr[i] * p["stop_loss_atr_mult"])
                    
                    # Target is middle BB
                    if p["target_middle_bb"]:
                        take_profit = bb_middle[i]
                    else:
                        take_profit = entry_price - (atr[i] * 2.0)
                    
                    # Position sizing
                    risk_amount = balance * (p["base_risk_pct"] / 100)
                    stop_distance_pips = (stop_loss - entry_price) * 10000
                    
                    if stop_distance_pips > 0:
                        lots = risk_amount / (stop_distance_pips * 10)
                        lots = max(0.01, min(lots, 5.0))
                    else:
                        lots = 0.01
                    
                    position = {
                        "direction": "SELL",
                        "entry_price": entry_price,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "lots": lots,
                        "entry_type": "mean_reversion",
                    }
                    trades_per_day[day_key] += 1
                    signal_counts["bb_upper_touch"] += 1
                    
                    logger.debug(f"MR SHORT: {entry_price:.5f}, RSI: {rsi[i]:.1f}, "
                               f"BB Upper: {bb_upper[i]:.5f}, Target: {take_profit:.5f}")
    
    # Close final position
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, "End of Test", config.symbol)
        trade.profit_loss *= position["lots"]
        trades.append(trade)
        balance += trade.profit_loss
    
    # Log statistics
    total_signals = sum(signal_counts.values())
    if total_signals > 0:
        logger.info(f"\nMean Reversion Signal Distribution:")
        for signal, count in signal_counts.items():
            pct = count / total_signals * 100
            logger.info(f"  {signal}: {count} ({pct:.1f}%)")
    
    logger.info(f"\nMean reversion strategy complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
