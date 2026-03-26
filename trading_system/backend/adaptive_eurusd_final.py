"""
Adaptive EURUSD Strategy

Key Principle: ADAPT, don't block.
- Adjust position size based on conditions
- Adjust stop/target distances based on volatility
- Use soft bias instead of hard filters
- Always look for opportunities

Base: EMA 5/50 crossover
Adaptive Elements: Position sizing, stop/target distances, risk level
"""

import logging
from typing import List, Tuple, Dict, Optional
from datetime import datetime

from market_data_models import Candle
from backtest_models import (
    TradeRecord, EquityPoint, BacktestConfig, TradeDirection, TradeStatus
)
from backtest_real_engine import _calculate_ema, _calculate_rsi, _create_trade
from improved_eurusd_strategy import calculate_atr, get_trading_session, TradingSession

logger = logging.getLogger(__name__)


def calculate_atr_percentile(atr_values: List[float], current_idx: int, lookback: int = 100) -> float:
    """Calculate what percentile the current ATR is in recent history"""
    if current_idx < lookback:
        return 0.5  # Default to middle
    
    recent_atr = atr_values[max(0, current_idx - lookback):current_idx]
    current = atr_values[current_idx]
    
    if not recent_atr:
        return 0.5
    
    # Calculate percentile
    below = sum(1 for v in recent_atr if v < current)
    percentile = below / len(recent_atr)
    
    return percentile


def calculate_trend_strength(candle: Candle, ema_200: float, ema_50: float) -> float:
    """
    Calculate trend strength (0.0 to 1.0).
    
    Strong trend = price far from EMA 200, moving with EMA 50
    Weak trend = price near EMA 200, choppy
    """
    if ema_200 is None or ema_50 is None:
        return 0.5
    
    # Distance from EMA 200
    distance_from_200 = abs(candle.close - ema_200) / ema_200
    distance_score = min(distance_from_200 / 0.003, 1.0)  # 0.3% = full strength
    
    # Alignment with EMA 50
    ema_50_distance = abs(candle.close - ema_50) / ema_50
    alignment_score = 1.0 - min(ema_50_distance / 0.002, 1.0)  # Close to EMA 50 = better
    
    # Combined strength
    strength = (distance_score * 0.6 + alignment_score * 0.4)
    
    return strength


def calculate_adaptive_risk(
    base_risk_pct: float,
    trend_strength: float,
    atr_percentile: float,
    distance_from_ema200_pct: float
) -> float:
    """
    Calculate adaptive risk percentage.
    
    Higher risk when:
    - Strong trend
    - Normal volatility
    - Price away from EMA 200
    
    Lower risk when:
    - Weak trend
    - Extreme volatility (high or low)
    - Price near EMA 200 (uncertain)
    """
    risk = base_risk_pct
    
    # Trend strength adjustment (0.7x to 1.3x)
    trend_mult = 0.7 + (trend_strength * 0.6)
    risk *= trend_mult
    
    # Volatility adjustment (prefer middle range)
    if atr_percentile < 0.2 or atr_percentile > 0.8:
        # Extreme volatility (very low or very high)
        risk *= 0.7
    else:
        # Normal volatility
        risk *= 1.0
    
    # Distance from EMA 200 adjustment
    if distance_from_ema200_pct < 0.001:  # Very close to EMA 200
        risk *= 0.6  # Reduce risk (uncertain zone)
    elif distance_from_ema200_pct > 0.005:  # Far from EMA 200
        risk *= 1.1  # Slightly increase (clearer trend)
    
    # Clamp to reasonable range
    risk = max(0.2, min(risk, 1.5))
    
    return risk


def calculate_adaptive_stops(
    base_stop_mult: float,
    base_tp_mult: float,
    atr_percentile: float,
    trend_strength: float
) -> Tuple[float, float]:
    """
    Calculate adaptive stop loss and take profit multipliers.
    
    High ATR → Wider stops
    Low ATR → Tighter stops (but not too tight)
    Strong trend → Wider targets
    """
    # Stop loss adjustment based on ATR percentile
    if atr_percentile < 0.3:
        # Low volatility - can use tighter stops
        stop_mult = base_stop_mult * 0.9
    elif atr_percentile > 0.7:
        # High volatility - need wider stops
        stop_mult = base_stop_mult * 1.3
    else:
        # Normal volatility
        stop_mult = base_stop_mult
    
    # Take profit adjustment based on trend and volatility
    if trend_strength > 0.7 and atr_percentile > 0.5:
        # Strong trend + good volatility = let winners run
        tp_mult = base_tp_mult * 1.3
    elif trend_strength < 0.3:
        # Weak trend = take profits faster
        tp_mult = base_tp_mult * 0.8
    else:
        tp_mult = base_tp_mult
    
    # Ensure minimums
    stop_mult = max(1.5, min(stop_mult, 3.0))
    tp_mult = max(2.0, min(tp_mult, 5.0))
    
    return stop_mult, tp_mult


def run_adaptive_eurusd_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Adaptive EURUSD strategy.
    
    Parameters:
    - ema_fast: 5
    - ema_medium: 50
    - ema_long: 200 (soft bias, not hard filter)
    - rsi_period: 14
    - atr_period: 14
    - base_risk_pct: 0.75
    - base_stop_atr_mult: 2.0
    - base_tp_atr_mult: 3.0
    - max_trades_per_day: 4
    - min_candles_between_trades: 1
    - min_atr_threshold: 0.0002 (very low, just safety)
    - use_rsi_confirmation: False (optional, not required)
    - rsi_neutral_min: 35
    - rsi_neutral_max: 65
    """
    
    default_params = {
        "ema_fast": 5,
        "ema_medium": 50,
        "ema_long": 200,
        "rsi_period": 14,
        "atr_period": 14,
        "base_risk_pct": 0.75,
        "base_stop_atr_mult": 2.0,
        "base_tp_atr_mult": 3.0,
        "max_trades_per_day": 4,
        "min_candles_between_trades": 1,
        "min_atr_threshold": 0.0002,
        "use_rsi_confirmation": False,
        "rsi_neutral_min": 35,
        "rsi_neutral_max": 65,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running adaptive EURUSD strategy")
    
    # Calculate indicators
    ema_fast = _calculate_ema(candles, p["ema_fast"])
    ema_medium = _calculate_ema(candles, p["ema_medium"])
    ema_long = _calculate_ema(candles, p["ema_long"])
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    
    # State tracking
    trades = []
    equity_curve = []
    balance = config.initial_balance
    peak_balance = balance
    position = None
    trades_per_day = {}
    last_exit_index = -100
    
    # Statistics for logging
    total_risk_adjustments = 0
    avg_risk_used = []
    
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
        
        # Record equity
        equity_curve.append(EquityPoint(
            timestamp=candle.timestamp,
            balance=balance,
            equity=current_equity,
            drawdown=drawdown,
            drawdown_percent=drawdown_pct,
        ))
        
        # Skip if indicators not ready
        if (ema_fast[i] is None or ema_medium[i] is None or ema_long[i] is None or 
            i < p["ema_long"]):
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
                if candle.low <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                elif candle.high >= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                # Exit on opposite crossover
                elif ema_fast[i] < ema_medium[i]:
                    exit_price = candle.close
                    exit_reason = "EMA Cross Exit"
            
            else:  # SELL
                if candle.high >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                elif candle.low <= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                elif ema_fast[i] > ema_medium[i]:
                    exit_price = candle.close
                    exit_reason = "EMA Cross Exit"
            
            # Execute exit
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trade.profit_loss *= position["lots"]
                trades.append(trade)
                balance += trade.profit_loss
                last_exit_index = i
                position = None
        
        # Entry logic
        if position is None:
            # Basic filters (minimal)
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            # Session filter
            if session not in [TradingSession.LONDON, TradingSession.OVERLAP, TradingSession.NY]:
                continue
            
            # Safety ATR filter (very low threshold)
            if atr[i] < p["min_atr_threshold"]:
                continue
            
            # Cooldown
            if i - last_exit_index < p["min_candles_between_trades"]:
                continue
            
            # Calculate adaptive parameters
            atr_percentile = calculate_atr_percentile(atr, i, 100)
            trend_strength = calculate_trend_strength(candle, ema_long[i], ema_medium[i])
            distance_from_ema200 = abs(candle.close - ema_long[i]) / ema_long[i]
            
            # Calculate adaptive risk
            adaptive_risk = calculate_adaptive_risk(
                p["base_risk_pct"],
                trend_strength,
                atr_percentile,
                distance_from_ema200
            )
            
            # Calculate adaptive stops
            stop_mult, tp_mult = calculate_adaptive_stops(
                p["base_stop_atr_mult"],
                p["base_tp_atr_mult"],
                atr_percentile,
                trend_strength
            )
            
            # Soft bias from EMA 200 (not a hard filter)
            ema200_bias = 1.0
            if candle.close > ema_long[i]:
                ema200_bias = 1.1  # Slight preference for longs
            else:
                ema200_bias = 1.1  # Slight preference for shorts
            
            # Entry signals - EMA 5/50 crossover
            fresh_long_cross = (i > 0 and 
                               ema_fast[i] > ema_medium[i] and 
                               ema_fast[i-1] <= ema_medium[i-1])
            
            fresh_short_cross = (i > 0 and 
                                ema_fast[i] < ema_medium[i] and 
                                ema_fast[i-1] >= ema_medium[i-1])
            
            # RSI confirmation (optional)
            rsi_ok = True
            if p["use_rsi_confirmation"]:
                rsi_ok = p["rsi_neutral_min"] <= rsi[i] <= p["rsi_neutral_max"]
            
            # LONG ENTRY
            if fresh_long_cross and rsi_ok:
                entry_price = candle.close
                stop_loss = entry_price - (atr[i] * stop_mult)
                take_profit = entry_price + (atr[i] * tp_mult)
                
                # Apply EMA 200 bias to risk
                final_risk = adaptive_risk * (ema200_bias if candle.close > ema_long[i] else 1.0)
                
                # Calculate position size
                risk_amount = balance * (final_risk / 100)
                stop_distance_pips = (entry_price - stop_loss) * 10000
                
                if stop_distance_pips > 0:
                    lots = risk_amount / (stop_distance_pips * 10)
                    lots = max(0.01, min(lots, 10.0))
                else:
                    lots = 0.01
                
                position = {
                    "direction": "BUY",
                    "entry_price": entry_price,
                    "entry_time": candle.timestamp,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "lots": lots,
                    "risk_pct": final_risk,
                    "stop_mult": stop_mult,
                    "tp_mult": tp_mult,
                }
                trades_per_day[day_key] += 1
                avg_risk_used.append(final_risk)
                
                logger.debug(f"LONG: {entry_price:.5f}, Lots: {lots:.2f}, Risk: {final_risk:.2f}%, "
                           f"SL: {stop_mult:.1f}ATR, TP: {tp_mult:.1f}ATR, Trend: {trend_strength:.2f}")
            
            # SHORT ENTRY
            elif fresh_short_cross and rsi_ok:
                entry_price = candle.close
                stop_loss = entry_price + (atr[i] * stop_mult)
                take_profit = entry_price - (atr[i] * tp_mult)
                
                # Apply EMA 200 bias
                final_risk = adaptive_risk * (ema200_bias if candle.close < ema_long[i] else 1.0)
                
                # Calculate position size
                risk_amount = balance * (final_risk / 100)
                stop_distance_pips = (stop_loss - entry_price) * 10000
                
                if stop_distance_pips > 0:
                    lots = risk_amount / (stop_distance_pips * 10)
                    lots = max(0.01, min(lots, 10.0))
                else:
                    lots = 0.01
                
                position = {
                    "direction": "SELL",
                    "entry_price": entry_price,
                    "entry_time": candle.timestamp,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "lots": lots,
                    "risk_pct": final_risk,
                    "stop_mult": stop_mult,
                    "tp_mult": tp_mult,
                }
                trades_per_day[day_key] += 1
                avg_risk_used.append(final_risk)
                
                logger.debug(f"SHORT: {entry_price:.5f}, Lots: {lots:.2f}, Risk: {final_risk:.2f}%, "
                           f"SL: {stop_mult:.1f}ATR, TP: {tp_mult:.1f}ATR, Trend: {trend_strength:.2f}")
    
    # Close final position
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, "End of Test", config.symbol)
        trade.profit_loss *= position["lots"]
        trades.append(trade)
        balance += trade.profit_loss
    
    # Log statistics
    if avg_risk_used:
        logger.info(f"\nAdaptive Risk Statistics:")
        logger.info(f"  Average Risk Used: {sum(avg_risk_used)/len(avg_risk_used):.2f}%")
        logger.info(f"  Min Risk: {min(avg_risk_used):.2f}%")
        logger.info(f"  Max Risk: {max(avg_risk_used):.2f}%")
    
    logger.info(f"\nAdaptive strategy complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
