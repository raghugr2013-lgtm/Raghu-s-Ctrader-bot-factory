"""
Improved EURUSD Strategy - High Frequency with Quality

Features:
- EMA 200 trend filter
- RSI pullback zones (35-45 buy, 55-65 sell)
- ATR volatility filter
- Session filter (London/NY overlap)
- Up to 5 trades per day
- Pullback zone entry (not exact EMA touch)

Goals:
- 50-120 trades
- Profit Factor > 1.5
- Drawdown < 5%
"""

import logging
from datetime import datetime, timezone, timedelta, time as dt_time
from typing import List, Tuple, Dict, Optional
from enum import Enum

from market_data_models import Candle
from backtest_models import (
    TradeRecord, EquityPoint, BacktestConfig, Timeframe, TradeDirection, TradeStatus
)
from backtest_real_engine import _calculate_ema, _calculate_rsi, _create_trade

logger = logging.getLogger(__name__)


class TradingSession(str, Enum):
    """Trading sessions"""
    LONDON = "london"  # 08:00-12:00 UTC
    NY = "ny"  # 13:00-17:00 UTC
    OVERLAP = "overlap"  # 13:00-17:00 UTC (London/NY overlap)
    ASIAN = "asian"  # 00:00-08:00 UTC
    OFF = "off"


def get_trading_session(timestamp: datetime) -> TradingSession:
    """Determine trading session from timestamp"""
    hour = timestamp.hour
    
    if 13 <= hour < 17:
        return TradingSession.OVERLAP  # Best session
    elif 8 <= hour < 13:
        return TradingSession.LONDON
    elif 17 <= hour < 22:
        return TradingSession.NY
    else:
        return TradingSession.OFF


def calculate_atr(candles: List[Candle], period: int = 14) -> List[float]:
    """Calculate Average True Range"""
    if len(candles) < period:
        return [0.0] * len(candles)
    
    true_ranges = []
    for i in range(1, len(candles)):
        high_low = candles[i].high - candles[i].low
        high_close = abs(candles[i].high - candles[i-1].close)
        low_close = abs(candles[i].low - candles[i-1].close)
        true_ranges.append(max(high_low, high_close, low_close))
    
    atr_values = []
    
    # Initial ATR (SMA of true ranges)
    if len(true_ranges) >= period:
        initial_atr = sum(true_ranges[:period]) / period
        atr_values.append(initial_atr)
        
        # Subsequent ATR (smoothed)
        for i in range(period, len(true_ranges)):
            new_atr = (atr_values[-1] * (period - 1) + true_ranges[i]) / period
            atr_values.append(new_atr)
    
    # Pad with initial value
    result = [atr_values[0] if atr_values else 0.0] * (len(candles) - len(atr_values)) + atr_values
    return result


def run_improved_eurusd_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Improved EURUSD strategy with relaxed entry conditions.
    
    Parameters (with defaults):
    - ema_trend_period: 200 (long-term trend filter)
    - rsi_period: 14
    - rsi_buy_min: 35 (relaxed from 30)
    - rsi_buy_max: 45 (pullback zone)
    - rsi_sell_min: 55 (pullback zone)
    - rsi_sell_max: 65 (relaxed from 70)
    - atr_period: 14
    - atr_min_multiplier: 0.5 (minimum volatility threshold)
    - pullback_zone_pct: 0.002 (0.2% zone around EMA 20)
    - stop_loss_atr_mult: 2.0
    - take_profit_atr_mult: 3.0
    - risk_per_trade_pct: 1.0
    - max_trades_per_day: 5
    """
    
    # Default parameters
    default_params = {
        "ema_trend_period": 200,
        "ema_signal_period": 20,
        "rsi_period": 14,
        "rsi_buy_min": 35,
        "rsi_buy_max": 45,
        "rsi_sell_min": 55,
        "rsi_sell_max": 65,
        "atr_period": 14,
        "atr_min_multiplier": 0.5,
        "pullback_zone_pct": 0.002,
        "stop_loss_atr_mult": 2.0,
        "take_profit_atr_mult": 3.0,
        "risk_per_trade_pct": 1.0,
        "max_trades_per_day": 5,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running improved EURUSD strategy on {len(candles)} candles")
    logger.info(f"Parameters: {p}")
    
    # Calculate indicators
    ema_trend = _calculate_ema(candles, p["ema_trend_period"])
    ema_signal = _calculate_ema(candles, p["ema_signal_period"])
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    
    # Track state
    trades = []
    equity_curve = []
    balance = config.initial_balance
    peak_balance = balance
    position = None
    
    # Track trades per day
    trades_per_day = {}
    
    for i, candle in enumerate(candles):
        current_equity = balance
        
        # Update equity if in position
        if position:
            if position["direction"] == "BUY":
                unrealized_pnl = (candle.close - position["entry_price"]) * 10000 * 10  # EURUSD pip value
            else:
                unrealized_pnl = (position["entry_price"] - candle.close) * 10000 * 10
            current_equity = balance + unrealized_pnl
        
        # Calculate drawdown
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
        if ema_trend[i] is None or ema_signal[i] is None or i < p["ema_trend_period"]:
            continue
        
        # Get trading session
        session = get_trading_session(candle.timestamp)
        
        # Count trades for the day
        day_key = candle.timestamp.date()
        if day_key not in trades_per_day:
            trades_per_day[day_key] = 0
        
        # Exit management
        if position:
            exit_reason = None
            exit_price = None
            
            if position["direction"] == "BUY":
                # Stop loss hit
                if candle.low <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                # Take profit hit
                elif candle.high >= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                # Opposite signal (fast exit on trend reversal)
                elif rsi[i] >= p["rsi_sell_min"] and candle.close < ema_signal[i]:
                    exit_price = candle.close
                    exit_reason = "Reversal Signal"
            else:  # SELL
                # Stop loss hit
                if candle.high >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                # Take profit hit
                elif candle.low <= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                # Opposite signal
                elif rsi[i] <= p["rsi_buy_max"] and candle.close > ema_signal[i]:
                    exit_price = candle.close
                    exit_reason = "Reversal Signal"
            
            # Close position
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trades.append(trade)
                balance += trade.profit_loss
                position = None
                logger.debug(f"Closed {trade.direction.value} at {exit_price:.5f}, PnL: {trade.profit_loss:.2f}")
        
        # Entry logic (only if no position)
        if position is None:
            # Check if we've hit max trades per day
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            # Filter 1: Trading session (prefer London/NY overlap)
            if session == TradingSession.OFF or session == TradingSession.ASIAN:
                continue
            
            # Filter 2: ATR volatility (minimum volatility required)
            current_atr = atr[i]
            avg_price = (candle.high + candle.low) / 2
            atr_pct = current_atr / avg_price
            
            if atr_pct < p["atr_min_multiplier"] * 0.001:  # Minimum 0.05% ATR
                continue
            
            # Filter 3: Trend filter (EMA 200)
            trend_bullish = candle.close > ema_trend[i]
            trend_bearish = candle.close < ema_trend[i]
            
            # Pullback zone calculation
            pullback_zone = ema_signal[i] * p["pullback_zone_pct"]
            
            # BUY SIGNAL: Bullish trend + RSI pullback zone + near EMA 20
            if trend_bullish:
                in_pullback_zone = abs(candle.close - ema_signal[i]) <= pullback_zone
                rsi_in_buy_zone = p["rsi_buy_min"] <= rsi[i] <= p["rsi_buy_max"]
                
                if rsi_in_buy_zone and (in_pullback_zone or candle.close > ema_signal[i]):
                    # Calculate position sizing
                    stop_distance = current_atr * p["stop_loss_atr_mult"]
                    stop_loss = candle.close - stop_distance
                    take_profit = candle.close + (current_atr * p["take_profit_atr_mult"])
                    
                    position = {
                        "direction": "BUY",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "atr": current_atr,
                    }
                    trades_per_day[day_key] += 1
                    logger.debug(f"BUY at {candle.close:.5f}, RSI: {rsi[i]:.1f}, Session: {session.value}")
            
            # SELL SIGNAL: Bearish trend + RSI pullback zone + near EMA 20
            elif trend_bearish:
                in_pullback_zone = abs(candle.close - ema_signal[i]) <= pullback_zone
                rsi_in_sell_zone = p["rsi_sell_min"] <= rsi[i] <= p["rsi_sell_max"]
                
                if rsi_in_sell_zone and (in_pullback_zone or candle.close < ema_signal[i]):
                    # Calculate position sizing
                    stop_distance = current_atr * p["stop_loss_atr_mult"]
                    stop_loss = candle.close + stop_distance
                    take_profit = candle.close - (current_atr * p["take_profit_atr_mult"])
                    
                    position = {
                        "direction": "SELL",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "atr": current_atr,
                    }
                    trades_per_day[day_key] += 1
                    logger.debug(f"SELL at {candle.close:.5f}, RSI: {rsi[i]:.1f}, Session: {session.value}")
    
    # Close any remaining position at last candle
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, "End of Backtest", config.symbol)
        trades.append(trade)
        balance += trade.profit_loss
    
    logger.info(f"Strategy completed: {len(trades)} trades, Final balance: ${balance:.2f}")
    
    return trades, equity_curve
