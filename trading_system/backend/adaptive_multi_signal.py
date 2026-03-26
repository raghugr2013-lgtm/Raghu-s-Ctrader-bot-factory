"""
Adaptive Multi-Signal EURUSD Strategy

IMPROVEMENTS OVER enhanced_multi_signal.py:
1. Market Condition Filter (ADX + ATR) - LIGHT filtering
2. Adaptive Risk Management - Dynamic position sizing
3. Trade Quality Scoring - Enhanced confirmation in weak conditions
4. Soft Filters - Reduce exposure, don't block trades completely

Goal: Fix consistency issues (18.7% -> 50%+) without reducing profitability
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


def calculate_adx(candles: List[Candle], period: int = 14) -> List[Optional[float]]:
    """
    Calculate Average Directional Index (ADX)
    ADX measures trend strength (0-100)
    - ADX < 20: Weak/no trend (ranging)
    - ADX 20-25: Emerging trend
    - ADX 25-50: Strong trend
    - ADX > 50: Very strong trend
    """
    if len(candles) < period * 2:
        return [None] * len(candles)
    
    adx_values = [None] * len(candles)
    
    # Calculate +DM, -DM
    plus_dm = []
    minus_dm = []
    tr_list = []
    
    for i in range(1, len(candles)):
        high_diff = candles[i].high - candles[i-1].high
        low_diff = candles[i-1].low - candles[i].low
        
        # +DM
        if high_diff > low_diff and high_diff > 0:
            plus_dm.append(high_diff)
        else:
            plus_dm.append(0.0)
        
        # -DM
        if low_diff > high_diff and low_diff > 0:
            minus_dm.append(low_diff)
        else:
            minus_dm.append(0.0)
        
        # True Range
        tr = max(
            candles[i].high - candles[i].low,
            abs(candles[i].high - candles[i-1].close),
            abs(candles[i].low - candles[i-1].close)
        )
        tr_list.append(tr)
    
    # Smooth using EMA
    if len(tr_list) < period:
        return adx_values
    
    # Calculate +DI and -DI
    smoothed_plus_dm = [sum(plus_dm[:period]) / period]
    smoothed_minus_dm = [sum(minus_dm[:period]) / period]
    smoothed_tr = [sum(tr_list[:period]) / period]
    
    for i in range(period, len(plus_dm)):
        smoothed_plus_dm.append(smoothed_plus_dm[-1] - smoothed_plus_dm[-1]/period + plus_dm[i])
        smoothed_minus_dm.append(smoothed_minus_dm[-1] - smoothed_minus_dm[-1]/period + minus_dm[i])
        smoothed_tr.append(smoothed_tr[-1] - smoothed_tr[-1]/period + tr_list[i])
    
    # Calculate DI
    plus_di = [(dm / tr * 100) if tr > 0 else 0 for dm, tr in zip(smoothed_plus_dm, smoothed_tr)]
    minus_di = [(dm / tr * 100) if tr > 0 else 0 for dm, tr in zip(smoothed_minus_dm, smoothed_tr)]
    
    # Calculate DX
    dx = []
    for pdi, mdi in zip(plus_di, minus_di):
        di_sum = pdi + mdi
        if di_sum > 0:
            dx.append(abs(pdi - mdi) / di_sum * 100)
        else:
            dx.append(0)
    
    # Calculate ADX (smoothed DX)
    if len(dx) < period:
        return adx_values
    
    adx = [sum(dx[:period]) / period]
    
    for i in range(period, len(dx)):
        adx.append((adx[-1] * (period - 1) + dx[i]) / period)
    
    # Fill the results array
    start_idx = period * 2
    for i, val in enumerate(adx):
        if start_idx + i < len(candles):
            adx_values[start_idx + i] = val
    
    return adx_values


def classify_market_regime(adx: float, atr: float, atr_ma: float) -> str:
    """
    Classify market regime based on ADX and ATR
    
    Returns:
    - "strong_trend": ADX > 25, good conditions
    - "weak_trend": ADX 18-25, acceptable conditions
    - "ranging": ADX < 18, reduce exposure
    - "low_volatility": ATR < 70% of MA, reduce exposure
    """
    if atr < atr_ma * 0.7:
        return "low_volatility"
    
    if adx >= 25:
        return "strong_trend"
    elif adx >= 18:
        return "weak_trend"
    else:
        return "ranging"


def calculate_recent_high_low(candles: List[Candle], current_idx: int, lookback: int = 20) -> Tuple[float, float]:
    """Calculate recent high and low over lookback period"""
    if current_idx < lookback:
        return 0.0, 0.0
    
    recent_candles = candles[max(0, current_idx - lookback):current_idx]
    if not recent_candles:
        return 0.0, 0.0
    
    recent_high = max(c.high for c in recent_candles)
    recent_low = min(c.low for c in recent_candles)
    
    return recent_high, recent_low


def is_strong_candle(candle: Candle, atr: float, strength_threshold: float = 0.8) -> Tuple[bool, str]:
    """Detect strong momentum candles"""
    candle_size = abs(candle.close - candle.open)
    
    if candle_size < atr * strength_threshold:
        return False, "none"
    
    if candle.close > candle.open:
        total_range = candle.high - candle.low
        body_ratio = candle_size / total_range if total_range > 0 else 0
        if body_ratio > 0.6:
            return True, "bullish"
    
    elif candle.close < candle.open:
        total_range = candle.high - candle.low
        body_ratio = candle_size / total_range if total_range > 0 else 0
        if body_ratio > 0.6:
            return True, "bearish"
    
    return False, "none"


def get_regime_multipliers(regime: str) -> Dict[str, float]:
    """
    Get risk and confirmation multipliers based on market regime
    SOFT filters - reduce exposure but don't block completely
    """
    multipliers = {
        "strong_trend": {
            "risk_mult": 1.0,      # Full position size
            "min_conf_add": 0,     # No extra confirmations needed
            "sl_mult": 1.0,        # Standard SL
            "tp_mult": 1.0,        # Standard TP
        },
        "weak_trend": {
            "risk_mult": 0.75,     # 75% position size
            "min_conf_add": 1,     # +1 extra confirmation
            "sl_mult": 0.9,        # Slightly tighter SL
            "tp_mult": 1.0,        # Standard TP
        },
        "ranging": {
            "risk_mult": 0.5,      # 50% position size (not zero!)
            "min_conf_add": 2,     # +2 extra confirmations (high quality only)
            "sl_mult": 0.8,        # Tighter SL
            "tp_mult": 0.9,        # Slightly lower TP
        },
        "low_volatility": {
            "risk_mult": 0.6,      # 60% position size
            "min_conf_add": 1,     # +1 extra confirmation
            "sl_mult": 0.85,       # Tighter SL for low vol
            "tp_mult": 0.95,       # Slightly lower TP
        },
    }
    
    return multipliers.get(regime, multipliers["weak_trend"])


def run_adaptive_multi_signal_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Adaptive multi-signal EURUSD strategy with market regime detection.
    
    NEW PARAMETERS:
    - adx_period: 14 (ADX calculation period)
    - adx_trending_threshold: 25 (Strong trend if ADX > this)
    - adx_ranging_threshold: 18 (Ranging if ADX < this)
    - atr_lookback: 20 (ATR moving average for volatility comparison)
    - enable_regime_adaptation: True (Use adaptive filters)
    
    BEHAVIOR BY REGIME:
    - Strong Trend (ADX > 25): Full exposure, standard confirmations
    - Weak Trend (ADX 18-25): 75% size, +1 confirmation
    - Ranging (ADX < 18): 50% size, +2 confirmations
    - Low Volatility: 60% size, +1 confirmation, tighter SL/TP
    """
    
    default_params = {
        # Original parameters
        "ema_micro": 3,
        "ema_fast": 20,
        "ema_medium": 50,
        "ema_long": 200,
        "rsi_period": 14,
        "atr_period": 14,
        
        # Signal parameters
        "pullback_rsi_min": 42,
        "pullback_rsi_max": 58,
        "pullback_distance_pct": 0.003,
        "breakout_lookback": 20,
        "breakout_buffer_pct": 0.0002,
        "momentum_threshold": 0.85,
        
        # Confirmation requirements
        "require_confirmation": True,
        "min_confirmations": 2,  # Base requirement (will be increased in weak regimes)
        
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
        
        # NEW: Regime detection parameters
        "adx_period": 14,
        "adx_trending_threshold": 25,
        "adx_ranging_threshold": 18,
        "atr_lookback": 20,
        "enable_regime_adaptation": True,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running ADAPTIVE multi-signal strategy with regime detection")
    
    # Calculate indicators
    ema_micro = _calculate_ema(candles, p["ema_micro"])
    ema_fast = _calculate_ema(candles, p["ema_fast"])
    ema_medium = _calculate_ema(candles, p["ema_medium"])
    ema_long = _calculate_ema(candles, p["ema_long"])
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    
    # NEW: Calculate ADX for trend strength
    adx = calculate_adx(candles, p["adx_period"])
    
    # Calculate ATR moving average for volatility detection
    atr_ma = [None] * len(candles)
    for i in range(p["atr_lookback"], len(candles)):
        if all(atr[j] is not None for j in range(i - p["atr_lookback"], i)):
            atr_ma[i] = sum(atr[i - p["atr_lookback"]:i]) / p["atr_lookback"]
    
    # State tracking
    trades = []
    equity_curve = []
    balance = config.initial_balance
    peak_balance = balance
    position = None
    trades_per_day = {}
    last_exit_index = -100
    
    # Statistics
    signal_counts = {
        "pullback": 0,
        "breakout": 0,
        "momentum": 0,
        "micro_cross": 0,
    }
    filtered_counts = {
        "near_ema200": 0,
        "insufficient_confirmations": 0,
        "weak_setup": 0,
    }
    regime_counts = {
        "strong_trend": 0,
        "weak_trend": 0,
        "ranging": 0,
        "low_volatility": 0,
    }
    regime_filtered = 0
    
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
        if (ema_micro[i] is None or ema_fast[i] is None or 
            ema_medium[i] is None or ema_long[i] is None or 
            adx[i] is None or atr_ma[i] is None or
            i < p["ema_long"]):
            continue
        
        # NEW: Classify market regime
        current_regime = classify_market_regime(adx[i], atr[i], atr_ma[i])
        regime_counts[current_regime] += 1
        
        # Get regime-based multipliers
        regime_mults = get_regime_multipliers(current_regime)
        
        # Session and day tracking
        session = get_trading_session(candle.timestamp)
        day_key = candle.timestamp.date()
        if day_key not in trades_per_day:
            trades_per_day[day_key] = 0
        
        # Exit management (same as before)
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
            
            else:  # SELL
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
                position = None
        
        # Entry logic - Enhanced with regime adaptation
        if position is None:
            # Basic filters
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            if session not in [TradingSession.LONDON, TradingSession.OVERLAP, TradingSession.NY]:
                continue
            
            if atr[i] < p["min_atr_threshold"]:
                continue
            
            if i - last_exit_index < p["min_candles_between_trades"]:
                continue
            
            # Determine directional bias and distance from EMA 200
            distance_from_ema200 = abs(candle.close - ema_long[i]) / ema_long[i]
            
            # Filter: Avoid uncertain zone near EMA 200
            if distance_from_ema200 < p["avoid_ema200_zone_pct"]:
                filtered_counts["near_ema200"] += 1
                continue
            
            # Require minimum distance from EMA 200 for entry
            if distance_from_ema200 < p["min_distance_from_ema200_pct"]:
                continue
            
            bullish_bias = candle.close > ema_long[i]
            bearish_bias = candle.close < ema_long[i]
            
            # Collect all active signals and confirmations
            signals = []
            confirmations = []
            
            # Calculate dynamic confirmation requirement based on regime
            dynamic_min_confirmations = p["min_confirmations"] + regime_mults["min_conf_add"]
            
            # ===================================================================
            # LONG SIGNALS
            # ===================================================================
            if bullish_bias:
                # Signal 1: Pullback
                near_ema20 = abs(candle.close - ema_fast[i]) / ema_fast[i] < p["pullback_distance_pct"]
                near_ema50 = abs(candle.close - ema_medium[i]) / ema_medium[i] < p["pullback_distance_pct"]
                
                if (near_ema20 or near_ema50) and candle.close > candle.open:
                    signals.append("pullback")
                
                # Signal 2: Breakout
                if i >= p["breakout_lookback"]:
                    recent_high, _ = calculate_recent_high_low(candles, i, p["breakout_lookback"])
                    breakout_level = recent_high * (1 + p["breakout_buffer_pct"])
                    
                    if candle.close > breakout_level and candle.close > candle.open:
                        signals.append("breakout")
                
                # Signal 3: Momentum candle
                is_strong, direction = is_strong_candle(candle, atr[i], p["momentum_threshold"])
                if is_strong and direction == "bullish":
                    signals.append("momentum")
                
                # Signal 4: Micro crossover
                if i > 0:
                    micro_cross = (ema_micro[i] > ema_fast[i] and 
                                  ema_micro[i-1] <= ema_fast[i-1])
                    if micro_cross:
                        signals.append("micro_cross")
                
                # Confirmations (additional quality checks)
                if p["pullback_rsi_min"] <= rsi[i] <= p["pullback_rsi_max"]:
                    confirmations.append("rsi")
                
                if is_strong and direction == "bullish":
                    confirmations.append("strong_candle")
                
                if candle.close > ema_fast[i] and candle.close > ema_medium[i]:
                    confirmations.append("above_emas")
                
                if i > 0 and (candle.close - candle.open) > (candles[i-1].close - candles[i-1].open):
                    confirmations.append("momentum_increasing")
                
                # NEW: Regime-specific confirmations
                if current_regime == "strong_trend" and adx[i] > 30:
                    confirmations.append("strong_adx")
                
                if atr[i] > atr_ma[i] * 1.2:
                    confirmations.append("good_volatility")
                
                # Check if we have enough signals/confirmations (DYNAMIC THRESHOLD)
                total_score = len(signals) + len(confirmations)
                
                if p["require_confirmation"]:
                    if len(signals) >= 1 and total_score >= dynamic_min_confirmations:
                        # Calculate regime-adjusted position size and SL/TP
                        entry_price = candle.close
                        
                        # Apply regime multipliers to SL/TP
                        adjusted_sl_mult = p["stop_loss_atr_mult"] * regime_mults["sl_mult"]
                        adjusted_tp_mult = p["take_profit_atr_mult"] * regime_mults["tp_mult"]
                        
                        stop_loss = entry_price - (atr[i] * adjusted_sl_mult)
                        take_profit = entry_price + (atr[i] * adjusted_tp_mult)
                        
                        # Apply regime multiplier to risk
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
                            "regime": current_regime,
                            "adx": adx[i],
                        }
                        trades_per_day[day_key] += 1
                        
                        for sig in signals:
                            signal_counts[sig] += 1
                        
                        logger.debug(f"LONG: {entry_price:.5f}, Regime: {current_regime}, ADX: {adx[i]:.1f}, "
                                   f"Signals: {signals}, Confirmations: {confirmations}, Size: {lots:.2f} "
                                   f"(Risk mult: {regime_mults['risk_mult']:.2f})")
                    else:
                        filtered_counts["insufficient_confirmations"] += 1
                        if p["enable_regime_adaptation"]:
                            regime_filtered += 1
            
            # ===================================================================
            # SHORT SIGNALS
            # ===================================================================
            elif bearish_bias:
                # Signal 1: Pullback
                near_ema20 = abs(candle.close - ema_fast[i]) / ema_fast[i] < p["pullback_distance_pct"]
                near_ema50 = abs(candle.close - ema_medium[i]) / ema_medium[i] < p["pullback_distance_pct"]
                
                if (near_ema20 or near_ema50) and candle.close < candle.open:
                    signals.append("pullback")
                
                # Signal 2: Breakout
                if i >= p["breakout_lookback"]:
                    _, recent_low = calculate_recent_high_low(candles, i, p["breakout_lookback"])
                    breakout_level = recent_low * (1 - p["breakout_buffer_pct"])
                    
                    if candle.close < breakout_level and candle.close < candle.open:
                        signals.append("breakout")
                
                # Signal 3: Momentum candle
                is_strong, direction = is_strong_candle(candle, atr[i], p["momentum_threshold"])
                if is_strong and direction == "bearish":
                    signals.append("momentum")
                
                # Signal 4: Micro crossover
                if i > 0:
                    micro_cross = (ema_micro[i] < ema_fast[i] and 
                                  ema_micro[i-1] >= ema_fast[i-1])
                    if micro_cross:
                        signals.append("micro_cross")
                
                # Confirmations
                if p["pullback_rsi_min"] <= rsi[i] <= p["pullback_rsi_max"]:
                    confirmations.append("rsi")
                
                if is_strong and direction == "bearish":
                    confirmations.append("strong_candle")
                
                if candle.close < ema_fast[i] and candle.close < ema_medium[i]:
                    confirmations.append("below_emas")
                
                if i > 0 and (candle.open - candle.close) > (candles[i-1].open - candles[i-1].close):
                    confirmations.append("momentum_increasing")
                
                # NEW: Regime-specific confirmations
                if current_regime == "strong_trend" and adx[i] > 30:
                    confirmations.append("strong_adx")
                
                if atr[i] > atr_ma[i] * 1.2:
                    confirmations.append("good_volatility")
                
                # Check confirmations (DYNAMIC THRESHOLD)
                total_score = len(signals) + len(confirmations)
                
                if p["require_confirmation"]:
                    if len(signals) >= 1 and total_score >= dynamic_min_confirmations:
                        # Calculate regime-adjusted position size and SL/TP
                        entry_price = candle.close
                        
                        # Apply regime multipliers
                        adjusted_sl_mult = p["stop_loss_atr_mult"] * regime_mults["sl_mult"]
                        adjusted_tp_mult = p["take_profit_atr_mult"] * regime_mults["tp_mult"]
                        
                        stop_loss = entry_price + (atr[i] * adjusted_sl_mult)
                        take_profit = entry_price - (atr[i] * adjusted_tp_mult)
                        
                        # Apply regime multiplier to risk
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
                            "regime": current_regime,
                            "adx": adx[i],
                        }
                        trades_per_day[day_key] += 1
                        
                        for sig in signals:
                            signal_counts[sig] += 1
                        
                        logger.debug(f"SHORT: {entry_price:.5f}, Regime: {current_regime}, ADX: {adx[i]:.1f}, "
                                   f"Signals: {signals}, Confirmations: {confirmations}, Size: {lots:.2f} "
                                   f"(Risk mult: {regime_mults['risk_mult']:.2f})")
                    else:
                        filtered_counts["insufficient_confirmations"] += 1
                        if p["enable_regime_adaptation"]:
                            regime_filtered += 1
    
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
    
    total_filtered = sum(filtered_counts.values())
    if total_filtered > 0:
        logger.info(f"\nFiltered Setups:")
        for reason, count in filtered_counts.items():
            logger.info(f"  {reason}: {count}")
    
    # Log regime statistics
    total_candles = sum(regime_counts.values())
    if total_candles > 0:
        logger.info(f"\nMarket Regime Distribution:")
        for regime, count in sorted(regime_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / total_candles * 100
            logger.info(f"  {regime}: {count} ({pct:.1f}%)")
        logger.info(f"  Regime-filtered trades: {regime_filtered}")
    
    logger.info(f"\nAdaptive multi-signal complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
