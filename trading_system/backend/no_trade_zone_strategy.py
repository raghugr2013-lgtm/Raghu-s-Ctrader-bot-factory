"""
NO-TRADE ZONE Adaptive Strategy

CRITICAL UPGRADE: Detects and AVOIDS trading when edge doesn't exist

KEY FEATURES:
1. Choppiness Index - Detects sideways/oscillating markets
2. Bollinger Band Contraction - Low volatility squeeze detection
3. Whipsaw Detector - Frequent EMA crossovers = choppy conditions
4. Consecutive Loss Circuit Breaker - Pause after losses
5. Rapid Drawdown Protection - Stop during equity drawdowns
6. Combined NO-TRADE ZONE - Strict filter blocks all trading

Goal: Consistency 22% → 40%+ by avoiding Segment 2-like conditions
"""

import logging
from typing import List, Tuple, Dict, Optional
from datetime import datetime
import numpy as np

from market_data_models import Candle
from backtest_models import (
    TradeRecord, EquityPoint, BacktestConfig, TradeDirection, TradeStatus
)
from backtest_real_engine import _calculate_ema, _calculate_rsi, _create_trade
from improved_eurusd_strategy import calculate_atr, get_trading_session, TradingSession
from adaptive_multi_signal import calculate_adx, calculate_recent_high_low, is_strong_candle

logger = logging.getLogger(__name__)


def calculate_choppiness_index(candles: List[Candle], period: int = 14) -> List[Optional[float]]:
    """
    Choppiness Index (CI)
    - CI near 100: Strong sideways/choppy market
    - CI near 0: Strong trending market
    - Threshold: CI > 61.8 = choppy, avoid trading
    """
    ci_values = [None] * len(candles)
    
    if len(candles) < period:
        return ci_values
    
    for i in range(period, len(candles)):
        # Calculate True Range sum
        tr_sum = 0
        high_low_diff = 0
        
        for j in range(i - period, i):
            tr = max(
                candles[j].high - candles[j].low,
                abs(candles[j].high - candles[j-1].close) if j > 0 else candles[j].high - candles[j].low,
                abs(candles[j].low - candles[j-1].close) if j > 0 else candles[j].high - candles[j].low
            )
            tr_sum += tr
        
        # Calculate high-low difference over period
        period_candles = candles[i - period:i]
        period_high = max(c.high for c in period_candles)
        period_low = min(c.low for c in period_candles)
        high_low_diff = period_high - period_low
        
        # Calculate CI
        if high_low_diff > 0 and tr_sum > 0:
            ci = 100 * np.log10(tr_sum / high_low_diff) / np.log10(period)
            ci_values[i] = ci
        else:
            ci_values[i] = None
    
    return ci_values


def calculate_bollinger_bands(candles: List[Candle], period: int = 20, std_dev: float = 2.0) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """
    Calculate Bollinger Bands (middle, upper, lower)
    Returns: (middle_band, upper_band, lower_band, bandwidth_pct)
    """
    middle = [None] * len(candles)
    upper = [None] * len(candles)
    lower = [None] * len(candles)
    bandwidth_pct = [None] * len(candles)
    
    if len(candles) < period:
        return middle, upper, lower, bandwidth_pct
    
    for i in range(period - 1, len(candles)):
        period_closes = [candles[j].close for j in range(i - period + 1, i + 1)]
        
        sma = sum(period_closes) / period
        variance = sum((x - sma) ** 2 for x in period_closes) / period
        std = variance ** 0.5
        
        middle[i] = sma
        upper[i] = sma + (std_dev * std)
        lower[i] = sma - (std_dev * std)
        
        # Bandwidth as percentage of price
        if sma > 0:
            bandwidth_pct[i] = ((upper[i] - lower[i]) / sma) * 100
        else:
            bandwidth_pct[i] = None
    
    return middle, upper, lower, bandwidth_pct


def detect_ema_whipsaws(ema_fast: List[Optional[float]], ema_medium: List[Optional[float]], 
                        current_idx: int, lookback: int = 20) -> int:
    """
    Count EMA crossovers in recent period
    Many crossovers = choppy/whipsaw conditions
    """
    if current_idx < lookback:
        return 0
    
    crossovers = 0
    
    for i in range(current_idx - lookback + 1, current_idx):
        if ema_fast[i] is None or ema_medium[i] is None:
            continue
        if ema_fast[i-1] is None or ema_medium[i-1] is None:
            continue
        
        # Detect crossover
        was_above = ema_fast[i-1] > ema_medium[i-1]
        is_above = ema_fast[i] > ema_medium[i]
        
        if was_above != is_above:
            crossovers += 1
    
    return crossovers


def detect_price_oscillation(candles: List[Candle], ema_long: List[Optional[float]], 
                             current_idx: int, lookback: int = 30) -> int:
    """
    Count how many times price crosses EMA 200 in recent period
    Many crosses = sideways/oscillating market
    """
    if current_idx < lookback or ema_long[current_idx] is None:
        return 0
    
    crosses = 0
    
    for i in range(current_idx - lookback + 1, current_idx):
        if ema_long[i] is None or ema_long[i-1] is None:
            continue
        
        was_above = candles[i-1].close > ema_long[i-1]
        is_above = candles[i].close > ema_long[i]
        
        if was_above != is_above:
            crosses += 1
    
    return crosses


def is_no_trade_zone(
    adx: float,
    atr: float,
    atr_ma: float,
    choppiness_index: Optional[float],
    bb_bandwidth_pct: Optional[float],
    ema_crossovers: int,
    price_oscillations: int,
    consecutive_losses: int,
    recent_drawdown_pct: float,
    params: Dict
) -> Tuple[bool, str]:
    """
    Determine if we're in a NO-TRADE ZONE
    
    Uses scoring system: need multiple conditions to trigger no-trade
    
    Returns: (is_no_trade_zone, reason)
    """
    
    # Count how many bad conditions exist
    bad_conditions = []
    
    # CONDITION 1: Low ADX (weak trend)
    if adx < params["no_trade_adx_threshold"]:
        bad_conditions.append("low_adx")
    
    # CONDITION 2: Low Volatility
    if atr < atr_ma * params["no_trade_atr_mult"]:
        bad_conditions.append("low_vol")
    
    # CONDITION 3: High Choppiness
    if choppiness_index is not None and choppiness_index > params["no_trade_choppiness_threshold"]:
        bad_conditions.append("high_choppiness")
    
    # CONDITION 4: BB Squeeze
    if bb_bandwidth_pct is not None and bb_bandwidth_pct < params["no_trade_bb_bandwidth_threshold"]:
        bad_conditions.append("bb_squeeze")
    
    # CONDITION 5: EMA Whipsaws
    if ema_crossovers >= params["no_trade_max_ema_crossovers"]:
        bad_conditions.append("ema_whipsaw")
    
    # CONDITION 6: Price Oscillations
    if price_oscillations >= params["no_trade_max_price_oscillations"]:
        bad_conditions.append("price_oscillation")
    
    # STRICT FILTER: Need at least 3 bad conditions to block trading
    # (This prevents over-filtering while still catching genuinely bad periods)
    if len(bad_conditions) >= 3:
        return True, "+".join(bad_conditions)
    
    # CIRCUIT BREAKER 1: Consecutive Losses (immediate block)
    if consecutive_losses >= params["circuit_breaker_consecutive_losses"]:
        return True, "circuit_breaker_losses"
    
    # CIRCUIT BREAKER 2: Rapid Drawdown (immediate block)
    if recent_drawdown_pct > params["circuit_breaker_drawdown_pct"]:
        return True, "circuit_breaker_drawdown"
    
    return False, ""


def calculate_recent_drawdown(equity_curve: List[EquityPoint], lookback_candles: int = 50) -> float:
    """
    Calculate drawdown over recent period
    Returns: drawdown percentage
    """
    if len(equity_curve) < lookback_candles:
        return 0.0
    
    recent_equity = equity_curve[-lookback_candles:]
    peak = max(ep.equity for ep in recent_equity)
    current = recent_equity[-1].equity
    
    if peak > 0:
        return (peak - current) / peak * 100
    return 0.0


def get_regime_multipliers(adx: float, atr: float, atr_ma: float) -> Dict[str, float]:
    """
    Get risk multipliers based on regime (for trades outside no-trade zone)
    """
    if adx >= 25 and atr > atr_ma * 1.1:
        return {
            "risk_mult": 1.0,
            "min_conf_add": 0,
            "sl_mult": 1.0,
            "tp_mult": 1.0,
        }
    elif adx >= 20:
        return {
            "risk_mult": 0.8,
            "min_conf_add": 1,
            "sl_mult": 0.95,
            "tp_mult": 1.0,
        }
    else:
        return {
            "risk_mult": 0.6,
            "min_conf_add": 1,
            "sl_mult": 0.9,
            "tp_mult": 0.95,
        }


def run_no_trade_zone_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    NO-TRADE ZONE Adaptive Strategy
    
    Strictly avoids trading when market conditions indicate no edge exists.
    
    NEW PARAMETERS:
    - no_trade_adx_threshold: 20 (Don't trade if ADX < this)
    - no_trade_atr_mult: 0.8 (Don't trade if ATR < this * ATR_MA)
    - no_trade_choppiness_threshold: 61.8 (Don't trade if CI > this)
    - no_trade_bb_bandwidth_threshold: 2.0 (Don't trade if BB bandwidth < this %)
    - no_trade_max_ema_crossovers: 4 (Don't trade if > this crossovers in 20 candles)
    - no_trade_max_price_oscillations: 5 (Don't trade if > this EMA200 crosses in 30 candles)
    - circuit_breaker_consecutive_losses: 4 (Pause after this many losses)
    - circuit_breaker_drawdown_pct: 3.0 (Pause if recent DD > this %)
    - circuit_breaker_pause_candles: 20 (Pause duration after circuit breaker)
    """
    
    default_params = {
        # Original parameters
        "ema_micro": 3,
        "ema_fast": 20,
        "ema_medium": 50,
        "ema_long": 200,
        "rsi_period": 14,
        "atr_period": 14,
        "adx_period": 14,
        
        # Signal parameters
        "pullback_rsi_min": 42,
        "pullback_rsi_max": 58,
        "pullback_distance_pct": 0.003,
        "breakout_lookback": 20,
        "breakout_buffer_pct": 0.0002,
        "momentum_threshold": 0.85,
        
        # Confirmation
        "require_confirmation": True,
        "min_confirmations": 2,
        
        # Filters
        "avoid_ema200_zone_pct": 0.002,
        "min_distance_from_ema200_pct": 0.0015,
        
        # Risk management
        "base_risk_pct": 0.75,
        "stop_loss_atr_mult": 1.9,
        "take_profit_atr_mult": 4.0,
        "max_trades_per_day": 3,
        "min_candles_between_trades": 2,
        "min_atr_threshold": 0.0003,
        "atr_lookback": 20,
        
        # NEW: No-Trade Zone Detection (CALIBRATED for balance)
        "no_trade_adx_threshold": 15,  # Lower: only block very weak trends
        "no_trade_atr_mult": 0.65,     # Lower: only block very low volatility
        "no_trade_choppiness_threshold": 70,  # Higher: only block extreme chop
        "no_trade_bb_bandwidth_threshold": 1.5,  # Lower: only block severe squeezes
        "no_trade_max_ema_crossovers": 6,  # Higher: tolerate more crossovers
        "no_trade_max_price_oscillations": 7,  # Higher: tolerate more oscillations
        
        # NEW: Circuit Breakers
        "circuit_breaker_consecutive_losses": 4,
        "circuit_breaker_drawdown_pct": 3.5,  # Slightly higher tolerance
        "circuit_breaker_pause_candles": 15,   # Shorter pause
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running NO-TRADE ZONE strategy with strict filtering")
    
    # Calculate indicators
    ema_micro = _calculate_ema(candles, p["ema_micro"])
    ema_fast = _calculate_ema(candles, p["ema_fast"])
    ema_medium = _calculate_ema(candles, p["ema_medium"])
    ema_long = _calculate_ema(candles, p["ema_long"])
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    adx = calculate_adx(candles, p["adx_period"])
    
    # NEW: Calculate no-trade zone indicators
    choppiness = calculate_choppiness_index(candles, 14)
    bb_middle, bb_upper, bb_lower, bb_bandwidth = calculate_bollinger_bands(candles, 20, 2.0)
    
    # ATR MA
    atr_ma = [None] * len(candles)
    for i in range(p["atr_lookback"], len(candles)):
        if all(atr[j] is not None for j in range(i - p["atr_lookback"], i)):
            atr_ma[i] = sum(atr[i - p["atr_lookback"]:i]) / p["atr_lookback"]
    
    # State
    trades = []
    equity_curve = []
    balance = config.initial_balance
    peak_balance = balance
    position = None
    trades_per_day = {}
    last_exit_index = -100
    consecutive_losses = 0
    circuit_breaker_active_until = -1
    
    # Statistics
    signal_counts = {"pullback": 0, "breakout": 0, "momentum": 0, "micro_cross": 0}
    no_trade_reasons = {
        "low_adx_low_vol": 0,
        "high_choppiness": 0,
        "bb_squeeze": 0,
        "ema_whipsaw": 0,
        "price_oscillation": 0,
        "circuit_breaker_losses": 0,
        "circuit_breaker_drawdown": 0,
    }
    total_no_trade_candles = 0
    
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
        if (ema_micro[i] is None or ema_fast[i] is None or 
            ema_medium[i] is None or ema_long[i] is None or 
            adx[i] is None or atr_ma[i] is None or
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
                elif candle.close < ema_long[i] - (atr[i] * 0.5):
                    exit_price = candle.close
                    exit_reason = "Trend Reversal"
            else:
                if candle.high >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                elif candle.low <= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                elif candle.close > ema_long[i] + (atr[i] * 0.5):
                    exit_price = candle.close
                    exit_reason = "Trend Reversal"
            
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trade.profit_loss *= position["lots"]
                trades.append(trade)
                balance += trade.profit_loss
                last_exit_index = i
                
                # Track consecutive losses
                if trade.profit_loss < 0:
                    consecutive_losses += 1
                    
                    # Activate circuit breaker if threshold reached
                    if consecutive_losses >= p["circuit_breaker_consecutive_losses"]:
                        circuit_breaker_active_until = i + p["circuit_breaker_pause_candles"]
                        logger.info(f"⚠️  Circuit breaker activated at {candle.timestamp}: "
                                  f"{consecutive_losses} consecutive losses. "
                                  f"Pausing trading for {p['circuit_breaker_pause_candles']} candles")
                else:
                    consecutive_losses = 0  # Reset on winning trade
                
                position = None
        
        # Entry logic - with NO-TRADE ZONE detection
        if position is None:
            # Check circuit breaker
            if i < circuit_breaker_active_until:
                continue
            
            # Basic filters
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            if session not in [TradingSession.LONDON, TradingSession.OVERLAP, TradingSession.NY]:
                continue
            
            if atr[i] < p["min_atr_threshold"]:
                continue
            
            if i - last_exit_index < p["min_candles_between_trades"]:
                continue
            
            # NEW: Calculate no-trade zone indicators
            ema_crossovers = detect_ema_whipsaws(ema_fast, ema_medium, i, 20)
            price_oscillations = detect_price_oscillation(candles, ema_long, i, 30)
            recent_dd = calculate_recent_drawdown(equity_curve, 50) if len(equity_curve) >= 50 else 0.0
            
            # NEW: Check if we're in NO-TRADE ZONE (STRICT)
            in_no_trade_zone, no_trade_reason = is_no_trade_zone(
                adx=adx[i],
                atr=atr[i],
                atr_ma=atr_ma[i],
                choppiness_index=choppiness[i],
                bb_bandwidth_pct=bb_bandwidth[i],
                ema_crossovers=ema_crossovers,
                price_oscillations=price_oscillations,
                consecutive_losses=consecutive_losses,
                recent_drawdown_pct=recent_dd,
                params=p
            )
            
            if in_no_trade_zone:
                total_no_trade_candles += 1
                if no_trade_reason not in no_trade_reasons:
                    no_trade_reasons[no_trade_reason] = 0
                no_trade_reasons[no_trade_reason] += 1
                continue  # SKIP TRADING
            
            # Get regime multipliers for trades outside no-trade zone
            regime_mults = get_regime_multipliers(adx[i], atr[i], atr_ma[i])
            
            distance_from_ema200 = abs(candle.close - ema_long[i]) / ema_long[i]
            
            if distance_from_ema200 < p["avoid_ema200_zone_pct"]:
                continue
            
            if distance_from_ema200 < p["min_distance_from_ema200_pct"]:
                continue
            
            bullish_bias = candle.close > ema_long[i]
            bearish_bias = candle.close < ema_long[i]
            
            signals = []
            confirmations = []
            
            dynamic_min_confirmations = p["min_confirmations"] + regime_mults["min_conf_add"]
            
            # LONG SIGNALS
            if bullish_bias:
                near_ema20 = abs(candle.close - ema_fast[i]) / ema_fast[i] < p["pullback_distance_pct"]
                near_ema50 = abs(candle.close - ema_medium[i]) / ema_medium[i] < p["pullback_distance_pct"]
                
                if (near_ema20 or near_ema50) and candle.close > candle.open:
                    signals.append("pullback")
                
                if i >= p["breakout_lookback"]:
                    recent_high, _ = calculate_recent_high_low(candles, i, p["breakout_lookback"])
                    breakout_level = recent_high * (1 + p["breakout_buffer_pct"])
                    if candle.close > breakout_level and candle.close > candle.open:
                        signals.append("breakout")
                
                is_strong, direction = is_strong_candle(candle, atr[i], p["momentum_threshold"])
                if is_strong and direction == "bullish":
                    signals.append("momentum")
                
                if i > 0:
                    micro_cross = (ema_micro[i] > ema_fast[i] and ema_micro[i-1] <= ema_fast[i-1])
                    if micro_cross:
                        signals.append("micro_cross")
                
                # Confirmations
                if p["pullback_rsi_min"] <= rsi[i] <= p["pullback_rsi_max"]:
                    confirmations.append("rsi")
                if is_strong and direction == "bullish":
                    confirmations.append("strong_candle")
                if candle.close > ema_fast[i] and candle.close > ema_medium[i]:
                    confirmations.append("above_emas")
                if i > 0 and (candle.close - candle.open) > (candles[i-1].close - candles[i-1].open):
                    confirmations.append("momentum_increasing")
                if adx[i] > 25:
                    confirmations.append("strong_adx")
                if atr[i] > atr_ma[i] * 1.2:
                    confirmations.append("good_volatility")
                
                total_score = len(signals) + len(confirmations)
                
                if p["require_confirmation"] and len(signals) >= 1 and total_score >= dynamic_min_confirmations:
                    entry_price = candle.close
                    adjusted_sl_mult = p["stop_loss_atr_mult"] * regime_mults["sl_mult"]
                    adjusted_tp_mult = p["take_profit_atr_mult"] * regime_mults["tp_mult"]
                    stop_loss = entry_price - (atr[i] * adjusted_sl_mult)
                    take_profit = entry_price + (atr[i] * adjusted_tp_mult)
                    adjusted_risk_pct = p["base_risk_pct"] * regime_mults["risk_mult"]
                    risk_amount = balance * (adjusted_risk_pct / 100)
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
                        "signals": signals,
                        "confirmations": confirmations,
                        "adx": adx[i],
                    }
                    trades_per_day[day_key] += 1
                    
                    for sig in signals:
                        signal_counts[sig] += 1
                    
                    ci_str = f"{choppiness[i]:.1f}" if choppiness[i] is not None else "N/A"
                    logger.debug(f"LONG: {entry_price:.5f}, ADX: {adx[i]:.1f}, "
                               f"CI: {ci_str}, "
                               f"Signals: {len(signals)}, Confirmations: {len(confirmations)}")
            
            # SHORT SIGNALS
            elif bearish_bias:
                near_ema20 = abs(candle.close - ema_fast[i]) / ema_fast[i] < p["pullback_distance_pct"]
                near_ema50 = abs(candle.close - ema_medium[i]) / ema_medium[i] < p["pullback_distance_pct"]
                
                if (near_ema20 or near_ema50) and candle.close < candle.open:
                    signals.append("pullback")
                
                if i >= p["breakout_lookback"]:
                    _, recent_low = calculate_recent_high_low(candles, i, p["breakout_lookback"])
                    breakout_level = recent_low * (1 - p["breakout_buffer_pct"])
                    if candle.close < breakout_level and candle.close < candle.open:
                        signals.append("breakout")
                
                is_strong, direction = is_strong_candle(candle, atr[i], p["momentum_threshold"])
                if is_strong and direction == "bearish":
                    signals.append("momentum")
                
                if i > 0:
                    micro_cross = (ema_micro[i] < ema_fast[i] and ema_micro[i-1] >= ema_fast[i-1])
                    if micro_cross:
                        signals.append("micro_cross")
                
                if p["pullback_rsi_min"] <= rsi[i] <= p["pullback_rsi_max"]:
                    confirmations.append("rsi")
                if is_strong and direction == "bearish":
                    confirmations.append("strong_candle")
                if candle.close < ema_fast[i] and candle.close < ema_medium[i]:
                    confirmations.append("below_emas")
                if i > 0 and (candle.open - candle.close) > (candles[i-1].open - candles[i-1].close):
                    confirmations.append("momentum_increasing")
                if adx[i] > 25:
                    confirmations.append("strong_adx")
                if atr[i] > atr_ma[i] * 1.2:
                    confirmations.append("good_volatility")
                
                total_score = len(signals) + len(confirmations)
                
                if p["require_confirmation"] and len(signals) >= 1 and total_score >= dynamic_min_confirmations:
                    entry_price = candle.close
                    adjusted_sl_mult = p["stop_loss_atr_mult"] * regime_mults["sl_mult"]
                    adjusted_tp_mult = p["take_profit_atr_mult"] * regime_mults["tp_mult"]
                    stop_loss = entry_price + (atr[i] * adjusted_sl_mult)
                    take_profit = entry_price - (atr[i] * adjusted_tp_mult)
                    adjusted_risk_pct = p["base_risk_pct"] * regime_mults["risk_mult"]
                    risk_amount = balance * (adjusted_risk_pct / 100)
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
                        "signals": signals,
                        "confirmations": confirmations,
                        "adx": adx[i],
                    }
                    trades_per_day[day_key] += 1
                    
                    for sig in signals:
                        signal_counts[sig] += 1
                    
                    ci_str = f"{choppiness[i]:.1f}" if choppiness[i] is not None else "N/A"
                    logger.debug(f"SHORT: {entry_price:.5f}, ADX: {adx[i]:.1f}, "
                               f"CI: {ci_str}, "
                               f"Signals: {len(signals)}, Confirmations: {len(confirmations)}")
    
    # Close final position
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, "End of Test", config.symbol)
        trade.profit_loss *= position["lots"]
        trades.append(trade)
        balance += trade.profit_loss
    
    # Log statistics
    total_signals = sum(signal_counts.values())
    if total_signals > 0:
        logger.info(f"\nSignal Distribution:")
        for signal, count in sorted(signal_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / total_signals * 100
            logger.info(f"  {signal}: {count} ({pct:.1f}%)")
    
    # Log no-trade zone statistics
    total_filtered = sum(no_trade_reasons.values())
    if total_filtered > 0:
        logger.info(f"\nNo-Trade Zone Activations:")
        for reason, count in sorted(no_trade_reasons.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                logger.info(f"  {reason}: {count}")
        
        no_trade_pct = (total_no_trade_candles / len(candles)) * 100
        logger.info(f"\nTotal candles in no-trade zone: {total_no_trade_candles} ({no_trade_pct:.1f}%)")
    
    logger.info(f"\nNo-trade zone strategy complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
