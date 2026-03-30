"""
Regime-Based EURUSD Strategy

Adapts trading approach based on market conditions:
- TRENDING: Follow trends with EMA crossovers
- RANGING: Mean reversion with Bollinger Bands
- LOW VOLATILITY: Stay flat

This solves the problem of using wrong strategy for market conditions.
"""

import logging
from typing import List, Tuple, Dict, Optional
from enum import Enum
from datetime import datetime

from market_data_models import Candle
from backtest_models import (
    TradeRecord, EquityPoint, BacktestConfig, TradeDirection, TradeStatus
)
from backtest_real_engine import _calculate_ema, _calculate_rsi, _create_trade
from improved_eurusd_strategy import calculate_atr, get_trading_session, TradingSession

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    """Market regimes"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    LOW_VOLATILITY = "low_volatility"
    UNKNOWN = "unknown"


def calculate_bollinger_bands(candles: List[Candle], period: int = 20, std_mult: float = 2.0) -> Tuple[List[float], List[float], List[float]]:
    """Calculate Bollinger Bands (middle, upper, lower)"""
    if len(candles) < period:
        return [0.0] * len(candles), [0.0] * len(candles), [0.0] * len(candles)
    
    closes = [c.close for c in candles]
    middle = []
    upper = []
    lower = []
    
    for i in range(len(closes)):
        if i < period - 1:
            middle.append(closes[i])
            upper.append(closes[i])
            lower.append(closes[i])
        else:
            window = closes[i - period + 1:i + 1]
            sma = sum(window) / period
            variance = sum((x - sma) ** 2 for x in window) / period
            std = variance ** 0.5
            
            middle.append(sma)
            upper.append(sma + std_mult * std)
            lower.append(sma - std_mult * std)
    
    return middle, upper, lower


def calculate_ema_slope(ema_values: List[float], lookback: int = 10) -> List[float]:
    """Calculate slope of EMA (rate of change)"""
    slopes = []
    
    for i in range(len(ema_values)):
        if i < lookback or ema_values[i] is None or ema_values[i - lookback] is None:
            slopes.append(0.0)
        else:
            # Slope as percentage change
            slope = (ema_values[i] - ema_values[i - lookback]) / ema_values[i - lookback] * 100
            slopes.append(slope)
    
    return slopes


def detect_regime(
    candle: Candle,
    ema_200: float,
    ema_200_slope: float,
    atr: float,
    atr_avg: float,
    bb_upper: float,
    bb_lower: float,
    bb_middle: float,
    params: Dict
) -> MarketRegime:
    """
    Detect current market regime.
    
    Logic:
    1. LOW_VOLATILITY: If ATR < threshold
    2. TRENDING_UP: Price > EMA200, strong positive slope, ATR rising
    3. TRENDING_DOWN: Price < EMA200, strong negative slope, ATR rising
    4. RANGING: Price oscillating around EMA200, weak slope
    """
    
    # Check low volatility first
    if atr < params["low_volatility_threshold"]:
        return MarketRegime.LOW_VOLATILITY
    
    # Price position relative to EMA 200
    price_vs_ema200 = candle.close - ema_200
    distance_pct = abs(price_vs_ema200) / ema_200 * 100
    
    # ATR trend (rising or falling)
    atr_vs_avg = (atr / atr_avg - 1) * 100 if atr_avg > 0 else 0
    
    # Bollinger Band position
    bb_range = bb_upper - bb_lower
    bb_position = (candle.close - bb_lower) / bb_range if bb_range > 0 else 0.5
    
    # TRENDING UP detection
    if (candle.close > ema_200 and 
        ema_200_slope > params["trend_slope_threshold"] and
        distance_pct > params["min_trend_distance_pct"]):
        return MarketRegime.TRENDING_UP
    
    # TRENDING DOWN detection
    if (candle.close < ema_200 and 
        ema_200_slope < -params["trend_slope_threshold"] and
        distance_pct > params["min_trend_distance_pct"]):
        return MarketRegime.TRENDING_DOWN
    
    # RANGING detection (price near EMA200, weak slope)
    if (abs(ema_200_slope) < params["range_slope_threshold"] and
        distance_pct < params["max_range_distance_pct"]):
        return MarketRegime.RANGING
    
    return MarketRegime.UNKNOWN


def calculate_position_size(
    balance: float,
    risk_pct: float,
    entry_price: float,
    stop_price: float,
    symbol: str = "EURUSD"
) -> float:
    """
    Calculate position size based on risk percentage.
    
    Risk Management:
    - Risk only X% of account balance
    - Position size = (Account * Risk%) / Stop Distance in $
    
    For EURUSD: 1 pip = $10 per lot
    """
    risk_amount = balance * (risk_pct / 100)
    stop_distance = abs(entry_price - stop_price)
    
    # Convert to pips (for EURUSD)
    stop_pips = stop_distance * 10000
    
    # Calculate lots
    # Risk $ = Lots * Stop Pips * $10/pip
    # Lots = Risk $ / (Stop Pips * $10)
    if stop_pips > 0:
        lots = risk_amount / (stop_pips * 10)
        # Limit to reasonable range
        lots = max(0.01, min(lots, 10.0))
    else:
        lots = 0.01
    
    return lots


def run_regime_based_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Regime-based strategy that adapts to market conditions.
    
    Parameters:
    - ema_fast: 5
    - ema_medium: 50
    - ema_long: 200
    - rsi_period: 14
    - bb_period: 20
    - bb_std_mult: 2.0
    - atr_period: 14
    - ema_slope_lookback: 10
    - atr_avg_period: 50
    
    Regime Detection:
    - low_volatility_threshold: 0.0004
    - trend_slope_threshold: 0.05 (0.05% per 10 candles)
    - min_trend_distance_pct: 0.1 (price must be 0.1% from EMA200)
    - range_slope_threshold: 0.02
    - max_range_distance_pct: 0.3
    
    Risk Management:
    - risk_per_trade_pct: 0.75 (0.75% of account)
    - max_trades_per_day: 3
    - min_candles_between_trades: 2
    
    Trend Strategy:
    - stop_loss_atr_mult: 2.0
    - take_profit_atr_mult: 3.5
    
    Range Strategy:
    - rsi_oversold: 30
    - rsi_overbought: 70
    - stop_loss_atr_mult: 2.5
    - take_profit_pct: 0.005 (0.5% target)
    """
    
    default_params = {
        # Indicators
        "ema_fast": 5,
        "ema_medium": 50,
        "ema_long": 200,
        "rsi_period": 14,
        "bb_period": 20,
        "bb_std_mult": 2.0,
        "atr_period": 14,
        "ema_slope_lookback": 10,
        "atr_avg_period": 50,
        
        # Regime detection
        "low_volatility_threshold": 0.0004,
        "trend_slope_threshold": 0.05,
        "min_trend_distance_pct": 0.1,
        "range_slope_threshold": 0.02,
        "max_range_distance_pct": 0.3,
        
        # Risk management
        "risk_per_trade_pct": 0.75,
        "max_trades_per_day": 3,
        "min_candles_between_trades": 2,
        
        # Trend strategy
        "trend_stop_atr_mult": 2.0,
        "trend_tp_atr_mult": 3.5,
        
        # Range strategy
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "range_stop_atr_mult": 2.5,
        "range_tp_pct": 0.005,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running regime-based strategy")
    
    # Calculate indicators
    ema_fast = _calculate_ema(candles, p["ema_fast"])
    ema_medium = _calculate_ema(candles, p["ema_medium"])
    ema_long = _calculate_ema(candles, p["ema_long"])
    ema_long_slope = calculate_ema_slope(ema_long, p["ema_slope_lookback"])
    
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    
    bb_middle, bb_upper, bb_lower = calculate_bollinger_bands(
        candles, p["bb_period"], p["bb_std_mult"]
    )
    
    # Calculate ATR average for regime detection
    atr_avg = []
    for i in range(len(atr)):
        if i < p["atr_avg_period"]:
            atr_avg.append(atr[i])
        else:
            avg = sum(atr[i - p["atr_avg_period"]:i]) / p["atr_avg_period"]
            atr_avg.append(avg)
    
    # State tracking
    trades = []
    equity_curve = []
    balance = config.initial_balance
    peak_balance = balance
    position = None
    trades_per_day = {}
    last_exit_index = -100
    
    # Regime tracking for logging
    regime_counts = {r: 0 for r in MarketRegime}
    
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
        if (ema_long[i] is None or i < p["ema_long"]):
            continue
        
        # Detect regime
        regime = detect_regime(
            candle, ema_long[i], ema_long_slope[i],
            atr[i], atr_avg[i],
            bb_upper[i], bb_lower[i], bb_middle[i],
            p
        )
        regime_counts[regime] += 1
        
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
                # Trend strategy: exit if trend weakens
                elif position["strategy"] == "trend" and ema_fast[i] < ema_medium[i]:
                    exit_price = candle.close
                    exit_reason = "Trend Weakening"
                # Range strategy: exit if reaches BB middle
                elif position["strategy"] == "range" and candle.close >= bb_middle[i]:
                    exit_price = candle.close
                    exit_reason = "Mean Reversion Complete"
            
            else:  # SELL
                if candle.high >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                elif candle.low <= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                elif position["strategy"] == "trend" and ema_fast[i] > ema_medium[i]:
                    exit_price = candle.close
                    exit_reason = "Trend Weakening"
                elif position["strategy"] == "range" and candle.close <= bb_middle[i]:
                    exit_price = candle.close
                    exit_reason = "Mean Reversion Complete"
            
            # Execute exit
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                # Adjust P&L for position size
                trade.profit_loss *= position["lots"]
                trades.append(trade)
                balance += trade.profit_loss
                last_exit_index = i
                position = None
        
        # Entry logic based on regime
        if position is None:
            # Basic filters
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            if session not in [TradingSession.LONDON, TradingSession.OVERLAP, TradingSession.NY]:
                continue
            
            if i - last_exit_index < p["min_candles_between_trades"]:
                continue
            
            # LOW VOLATILITY: Skip trading
            if regime == MarketRegime.LOW_VOLATILITY:
                continue
            
            # TRENDING UP: Long only with EMA crossover
            elif regime == MarketRegime.TRENDING_UP:
                if (ema_fast[i] > ema_medium[i] and
                    i > 0 and ema_fast[i-1] <= ema_medium[i-1]):
                    
                    entry_price = candle.close
                    stop_loss = entry_price - (atr[i] * p["trend_stop_atr_mult"])
                    take_profit = entry_price + (atr[i] * p["trend_tp_atr_mult"])
                    
                    # Calculate position size
                    lots = calculate_position_size(
                        balance, p["risk_per_trade_pct"],
                        entry_price, stop_loss
                    )
                    
                    position = {
                        "direction": "BUY",
                        "entry_price": entry_price,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "lots": lots,
                        "strategy": "trend",
                        "regime": regime.value,
                    }
                    trades_per_day[day_key] += 1
                    logger.debug(f"TREND LONG: {entry_price:.5f}, Lots: {lots:.2f}")
            
            # TRENDING DOWN: Short only with EMA crossover
            elif regime == MarketRegime.TRENDING_DOWN:
                if (ema_fast[i] < ema_medium[i] and
                    i > 0 and ema_fast[i-1] >= ema_medium[i-1]):
                    
                    entry_price = candle.close
                    stop_loss = entry_price + (atr[i] * p["trend_stop_atr_mult"])
                    take_profit = entry_price - (atr[i] * p["trend_tp_atr_mult"])
                    
                    lots = calculate_position_size(
                        balance, p["risk_per_trade_pct"],
                        entry_price, stop_loss
                    )
                    
                    position = {
                        "direction": "SELL",
                        "entry_price": entry_price,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "lots": lots,
                        "strategy": "trend",
                        "regime": regime.value,
                    }
                    trades_per_day[day_key] += 1
                    logger.debug(f"TREND SHORT: {entry_price:.5f}, Lots: {lots:.2f}")
            
            # RANGING: Mean reversion with BB + RSI
            elif regime == MarketRegime.RANGING:
                # Buy at lower BB when oversold
                if (candle.close <= bb_lower[i] and
                    rsi[i] < p["rsi_oversold"]):
                    
                    entry_price = candle.close
                    stop_loss = entry_price - (atr[i] * p["range_stop_atr_mult"])
                    take_profit = bb_middle[i]  # Target mean reversion
                    
                    lots = calculate_position_size(
                        balance, p["risk_per_trade_pct"],
                        entry_price, stop_loss
                    )
                    
                    position = {
                        "direction": "BUY",
                        "entry_price": entry_price,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "lots": lots,
                        "strategy": "range",
                        "regime": regime.value,
                    }
                    trades_per_day[day_key] += 1
                    logger.debug(f"RANGE LONG: {entry_price:.5f}, RSI: {rsi[i]:.1f}, Lots: {lots:.2f}")
                
                # Sell at upper BB when overbought
                elif (candle.close >= bb_upper[i] and
                      rsi[i] > p["rsi_overbought"]):
                    
                    entry_price = candle.close
                    stop_loss = entry_price + (atr[i] * p["range_stop_atr_mult"])
                    take_profit = bb_middle[i]
                    
                    lots = calculate_position_size(
                        balance, p["risk_per_trade_pct"],
                        entry_price, stop_loss
                    )
                    
                    position = {
                        "direction": "SELL",
                        "entry_price": entry_price,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "lots": lots,
                        "strategy": "range",
                        "regime": regime.value,
                    }
                    trades_per_day[day_key] += 1
                    logger.debug(f"RANGE SHORT: {entry_price:.5f}, RSI: {rsi[i]:.1f}, Lots: {lots:.2f}")
    
    # Close final position
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, "End of Test", config.symbol)
        trade.profit_loss *= position["lots"]
        trades.append(trade)
        balance += trade.profit_loss
    
    # Log regime statistics
    total_candles = sum(regime_counts.values())
    logger.info(f"\nRegime Distribution:")
    for regime, count in regime_counts.items():
        pct = count / total_candles * 100 if total_candles > 0 else 0
        logger.info(f"  {regime.value}: {count} ({pct:.1f}%)")
    
    logger.info(f"\nRegime-based strategy complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
