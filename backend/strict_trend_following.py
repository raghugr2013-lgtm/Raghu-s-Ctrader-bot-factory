"""
Strict Trend-Following EURUSD Strategy

Key Features:
- ONLY trades in EMA 200 trend direction
- No counter-trend trades
- EMA 5/50 for timing
- RSI for pullback confirmation (35-60 for longs, 40-65 for shorts)
- Quick exit on adverse movement
- Conservative risk management

Goals:
- Profit Factor > 1.5
- Max Drawdown < 5%
- 50-70 trades
- Smooth equity curve
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


def run_strict_trend_following(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Strict trend-following strategy - only trades with EMA 200 trend.
    
    Parameters:
    - ema_fast: 5 (quick signal)
    - ema_medium: 50 (trend confirmation)
    - ema_long: 200 (STRICT trend filter)
    - rsi_period: 14
    - rsi_pullback_long_min: 35 (oversold in uptrend)
    - rsi_pullback_long_max: 60 (not overbought)
    - rsi_pullback_short_min: 40 (not oversold)
    - rsi_pullback_short_max: 65 (overbought in downtrend)
    - atr_period: 14
    - atr_min_threshold: 0.0004 (minimum volatility required)
    - stop_loss_atr_mult: 2.0 (conservative)
    - take_profit_atr_mult: 3.2 (reasonable target)
    - emergency_exit_atr: -1.0 (quick exit if loss > 1 ATR)
    - max_trades_per_day: 3 (quality over quantity)
    - min_candles_between_trades: 3 (avoid overtrading)
    - use_trailing_stop: True
    - trailing_activation_atr: 1.5 (start trailing after 1.5 ATR profit)
    - trailing_distance_atr: 1.2 (trail 1.2 ATR from peak)
    """
    
    default_params = {
        "ema_fast": 5,
        "ema_medium": 50,
        "ema_long": 200,
        "rsi_period": 14,
        "rsi_pullback_long_min": 35,
        "rsi_pullback_long_max": 60,
        "rsi_pullback_short_min": 40,
        "rsi_pullback_short_max": 65,
        "atr_period": 14,
        "atr_min_threshold": 0.0004,
        "stop_loss_atr_mult": 2.0,
        "take_profit_atr_mult": 3.2,
        "emergency_exit_atr": -1.0,
        "max_trades_per_day": 3,
        "min_candles_between_trades": 3,
        "use_trailing_stop": True,
        "trailing_activation_atr": 1.5,
        "trailing_distance_atr": 1.2,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running strict trend-following strategy")
    logger.info(f"Parameters: {p}")
    
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
    
    # For tracking highest profit in position (for trailing)
    highest_profit = 0
    
    for i, candle in enumerate(candles):
        current_equity = balance
        
        # Update position tracking
        if position:
            if position["direction"] == "BUY":
                current_pnl_price = candle.close - position["entry_price"]
                current_pnl_atr = current_pnl_price / atr[i]
                unrealized_pnl = current_pnl_price * 10000 * 10
                
                # Track highest profit for trailing
                if current_pnl_atr > highest_profit:
                    highest_profit = current_pnl_atr
                
                # Update trailing stop if activated
                if (p["use_trailing_stop"] and 
                    highest_profit >= p["trailing_activation_atr"]):
                    # Trail from highest point
                    peak_price = position["entry_price"] + (highest_profit * atr[i])
                    new_trail = peak_price - (p["trailing_distance_atr"] * atr[i])
                    if new_trail > position["trailing_stop"]:
                        position["trailing_stop"] = new_trail
            else:
                current_pnl_price = position["entry_price"] - candle.close
                current_pnl_atr = current_pnl_price / atr[i]
                unrealized_pnl = current_pnl_price * 10000 * 10
                
                # Track highest profit
                if current_pnl_atr > highest_profit:
                    highest_profit = current_pnl_atr
                
                # Update trailing stop
                if (p["use_trailing_stop"] and 
                    highest_profit >= p["trailing_activation_atr"]):
                    peak_price = position["entry_price"] - (highest_profit * atr[i])
                    new_trail = peak_price + (p["trailing_distance_atr"] * atr[i])
                    if new_trail < position["trailing_stop"]:
                        position["trailing_stop"] = new_trail
            
            current_equity = balance + unrealized_pnl
        
        # Drawdown calculation
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
                # Emergency exit (quick loss)
                if current_pnl_atr <= p["emergency_exit_atr"]:
                    exit_price = candle.close
                    exit_reason = "Emergency Exit"
                # Trailing stop (if activated)
                elif (p["use_trailing_stop"] and 
                      highest_profit >= p["trailing_activation_atr"] and
                      candle.low <= position["trailing_stop"]):
                    exit_price = position["trailing_stop"]
                    exit_reason = "Trailing Stop"
                # Hard stop loss
                elif candle.low <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                # Take profit
                elif candle.high >= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                # Trend weakening (fast EMA crosses below medium)
                elif ema_fast[i] < ema_medium[i]:
                    exit_price = candle.close
                    exit_reason = "Trend Weakening"
            
            else:  # SELL
                # Emergency exit
                if current_pnl_atr <= p["emergency_exit_atr"]:
                    exit_price = candle.close
                    exit_reason = "Emergency Exit"
                # Trailing stop
                elif (p["use_trailing_stop"] and 
                      highest_profit >= p["trailing_activation_atr"] and
                      candle.high >= position["trailing_stop"]):
                    exit_price = position["trailing_stop"]
                    exit_reason = "Trailing Stop"
                # Hard stop loss
                elif candle.high >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                # Take profit
                elif candle.low <= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                # Trend weakening
                elif ema_fast[i] > ema_medium[i]:
                    exit_price = candle.close
                    exit_reason = "Trend Weakening"
            
            # Execute exit
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trades.append(trade)
                balance += trade.profit_loss
                last_exit_index = i
                position = None
                highest_profit = 0  # Reset
                
                logger.debug(f"Exit {trade.direction.value}: {exit_price:.5f}, "
                           f"P&L: {trade.profit_loss:.2f}, Reason: {exit_reason}")
        
        # Entry logic - STRICT TREND FOLLOWING
        if position is None:
            # Basic filters
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            # Session filter: Only London and NY
            if session not in [TradingSession.LONDON, TradingSession.OVERLAP, TradingSession.NY]:
                continue
            
            # Volatility filter
            if atr[i] < p["atr_min_threshold"]:
                continue
            
            # Cooldown between trades
            if i - last_exit_index < p["min_candles_between_trades"]:
                continue
            
            # Determine STRICT trend direction
            price_vs_ema200 = candle.close - ema_long[i]
            price_distance_pct = abs(price_vs_ema200) / ema_long[i]
            
            strict_uptrend = candle.close > ema_long[i] and price_distance_pct > 0.0001
            strict_downtrend = candle.close < ema_long[i] and price_distance_pct > 0.0001
            
            # LONG ENTRIES (only in strict uptrend)
            if strict_uptrend:
                # EMA alignment: fast > medium (both above long)
                ema_aligned = ema_fast[i] > ema_medium[i]
                
                # RSI pullback zone (not overbought)
                rsi_pullback = (p["rsi_pullback_long_min"] <= rsi[i] <= p["rsi_pullback_long_max"])
                
                # Entry conditions:
                # 1. Fresh cross OR
                # 2. Pullback to EMA 50 with RSI support
                fresh_cross = (i > 0 and ema_fast[i-1] <= ema_medium[i-1] and ema_fast[i] > ema_medium[i])
                
                near_ema_medium = abs(candle.close - ema_medium[i]) / ema_medium[i] < 0.002
                pullback_entry = near_ema_medium and rsi_pullback and ema_aligned
                
                if fresh_cross or pullback_entry:
                    entry_price = candle.close
                    stop_loss = entry_price - (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = entry_price + (atr[i] * p["take_profit_atr_mult"])
                    trailing_stop = stop_loss  # Initial trailing = stop loss
                    
                    position = {
                        "direction": "BUY",
                        "entry_price": entry_price,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "trailing_stop": trailing_stop,
                        "entry_atr": atr[i],
                    }
                    trades_per_day[day_key] += 1
                    highest_profit = 0
                    
                    logger.debug(f"Enter LONG: {entry_price:.5f}, RSI: {rsi[i]:.1f}, "
                               f"SL: {stop_loss:.5f}, TP: {take_profit:.5f}")
            
            # SHORT ENTRIES (only in strict downtrend)
            elif strict_downtrend:
                # EMA alignment: fast < medium (both below long)
                ema_aligned = ema_fast[i] < ema_medium[i]
                
                # RSI pullback zone (not oversold)
                rsi_pullback = (p["rsi_pullback_short_min"] <= rsi[i] <= p["rsi_pullback_short_max"])
                
                # Entry conditions
                fresh_cross = (i > 0 and ema_fast[i-1] >= ema_medium[i-1] and ema_fast[i] < ema_medium[i])
                
                near_ema_medium = abs(candle.close - ema_medium[i]) / ema_medium[i] < 0.002
                pullback_entry = near_ema_medium and rsi_pullback and ema_aligned
                
                if fresh_cross or pullback_entry:
                    entry_price = candle.close
                    stop_loss = entry_price + (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = entry_price - (atr[i] * p["take_profit_atr_mult"])
                    trailing_stop = stop_loss  # Initial trailing = stop loss
                    
                    position = {
                        "direction": "SELL",
                        "entry_price": entry_price,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "trailing_stop": trailing_stop,
                        "entry_atr": atr[i],
                    }
                    trades_per_day[day_key] += 1
                    highest_profit = 0
                    
                    logger.debug(f"Enter SHORT: {entry_price:.5f}, RSI: {rsi[i]:.1f}, "
                               f"SL: {stop_loss:.5f}, TP: {take_profit:.5f}")
    
    # Close final position
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, 
                            "End of Backtest", config.symbol)
        trades.append(trade)
        balance += trade.profit_loss
    
    logger.info(f"Strict trend-following complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
