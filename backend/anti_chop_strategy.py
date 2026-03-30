"""
ANTI-CHOP ADAPTIVE STRATEGY

Key Philosophy: Trade only when edge exists, SKIP choppy conditions entirely

Core Principle: NO strategy works in choppy markets → DON'T TRADE THEM

Features:
1. Multi-indicator Choppy Detection (ADX, CI, EMA whipsaws, directional movement)
2. Strict No-Trade Rule (skip all trades when choppy)
3. Adaptive Multi-Signal Logic (only in clean conditions)
4. Circuit Breakers (consecutive losses, drawdown)
"""

import logging
from typing import List, Tuple, Dict, Optional
from datetime import datetime

from market_data_models import Candle
from backtest_models import TradeRecord, EquityPoint, BacktestConfig
from backtest_real_engine import _calculate_ema, _calculate_rsi, _create_trade
from improved_eurusd_strategy import calculate_atr, get_trading_session, TradingSession
from no_trade_zone_strategy import calculate_adx, calculate_choppiness_index
from adaptive_multi_signal import calculate_recent_high_low, is_strong_candle

logger = logging.getLogger(__name__)


def detect_ema_whipsaws(ema_fast: List[Optional[float]], ema_medium: List[Optional[float]], 
                        current_idx: int, lookback: int = 20) -> int:
    """Count EMA crossovers in recent period (whipsaw indicator)"""
    if current_idx < lookback:
        return 0
    
    crossovers = 0
    for i in range(current_idx - lookback + 1, current_idx):
        if ema_fast[i] is None or ema_medium[i] is None:
            continue
        if ema_fast[i-1] is None or ema_medium[i-1] is None:
            continue
        
        was_above = ema_fast[i-1] > ema_medium[i-1]
        is_above = ema_fast[i] > ema_medium[i]
        
        if was_above != is_above:
            crossovers += 1
    
    return crossovers


def calculate_directional_movement_score(candles: List[Candle], current_idx: int, lookback: int = 20) -> float:
    """
    Calculate how directional price movement is (0-100)
    High score = directional/trending
    Low score = choppy/random
    """
    if current_idx < lookback:
        return 50.0
    
    recent_candles = candles[current_idx - lookback:current_idx]
    
    # Calculate net directional movement
    up_moves = 0
    down_moves = 0
    
    for i in range(1, len(recent_candles)):
        if recent_candles[i].close > recent_candles[i-1].close:
            up_moves += 1
        elif recent_candles[i].close < recent_candles[i-1].close:
            down_moves += 1
    
    # Strong directional bias = high score
    total_moves = up_moves + down_moves
    if total_moves == 0:
        return 0
    
    max_directional = max(up_moves, down_moves)
    directional_pct = (max_directional / total_moves) * 100
    
    return directional_pct


def calculate_choppy_score(
    adx: float,
    choppiness_index: Optional[float],
    ema_whipsaws: int,
    directional_movement: float,
    params: Dict
) -> float:
    """
    Calculate Choppy Score (0-100)
    Higher score = more choppy
    
    Components:
    - ADX (weight: 30%)
    - Choppiness Index (weight: 30%)
    - EMA Whipsaws (weight: 25%)
    - Directional Movement (weight: 15%)
    """
    
    choppy_score = 0
    
    # Component 1: ADX (inverse - low ADX = choppy)
    if adx < 15:
        choppy_score += 30
    elif adx < 20:
        choppy_score += 20
    elif adx < 25:
        choppy_score += 10
    else:
        choppy_score += 0
    
    # Component 2: Choppiness Index
    if choppiness_index is not None:
        if choppiness_index > 61.8:
            choppy_score += 30
        elif choppiness_index > 55:
            choppy_score += 20
        elif choppiness_index > 50:
            choppy_score += 10
        else:
            choppy_score += 0
    else:
        # If no CI, use ADX to estimate
        if adx < 18:
            choppy_score += 15
    
    # Component 3: EMA Whipsaws
    if ema_whipsaws >= 5:
        choppy_score += 25
    elif ema_whipsaws >= 3:
        choppy_score += 15
    elif ema_whipsaws >= 2:
        choppy_score += 8
    else:
        choppy_score += 0
    
    # Component 4: Directional Movement (inverse)
    if directional_movement < 55:
        choppy_score += 15
    elif directional_movement < 65:
        choppy_score += 8
    else:
        choppy_score += 0
    
    return choppy_score


def run_anti_chop_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Anti-Chop Adaptive Strategy
    
    Core Logic:
    1. Calculate Choppy Score for current market
    2. If Choppy Score > threshold → SKIP TRADING
    3. If market is clean → Use adaptive multi-signal logic
    4. Circuit breakers for extra safety
    
    NEW PARAMETERS:
    - choppy_score_threshold: 50 (Skip if score > this)
    - enable_circuit_breakers: True
    - circuit_breaker_consecutive_losses: 4
    - circuit_breaker_pause_candles: 20
    - ema_whipsaw_lookback: 20
    - directional_lookback: 20
    """
    
    default_params = {
        # Trend-following parameters
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
        "base_risk_pct": 0.7,
        "stop_loss_atr_mult": 1.9,
        "take_profit_atr_mult": 4.0,
        "max_trades_per_day": 3,
        "min_candles_between_trades": 2,
        "atr_lookback": 20,
        
        # NEW: Choppy Detection (STRICT)
        "choppy_score_threshold": 50,  # Skip if score > this
        "ema_whipsaw_lookback": 20,
        "directional_lookback": 20,
        
        # NEW: Circuit Breakers
        "enable_circuit_breakers": True,
        "circuit_breaker_consecutive_losses": 4,
        "circuit_breaker_pause_candles": 20,
        "circuit_breaker_drawdown_pct": 4.0,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running ANTI-CHOP strategy (skip choppy conditions)")
    
    # Calculate indicators
    ema_micro = _calculate_ema(candles, p["ema_micro"])
    ema_fast = _calculate_ema(candles, p["ema_fast"])
    ema_medium = _calculate_ema(candles, p["ema_medium"])
    ema_long = _calculate_ema(candles, p["ema_long"])
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    adx = calculate_adx(candles, p["adx_period"])
    choppiness = calculate_choppiness_index(candles, 14)
    
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
    choppy_filtered_count = 0
    circuit_breaker_activations = 0
    total_candles_evaluated = 0
    
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
                    
                    # Circuit breaker
                    if p["enable_circuit_breakers"] and consecutive_losses >= p["circuit_breaker_consecutive_losses"]:
                        circuit_breaker_active_until = i + p["circuit_breaker_pause_candles"]
                        circuit_breaker_activations += 1
                        logger.info(f"⚠️  Circuit breaker #{circuit_breaker_activations} at {candle.timestamp}: "
                                  f"{consecutive_losses} losses. Pausing {p['circuit_breaker_pause_candles']} candles")
                else:
                    consecutive_losses = 0
                
                position = None
        
        # Entry logic - with CHOPPY DETECTION
        if position is None:
            total_candles_evaluated += 1
            
            # Check circuit breaker
            if i < circuit_breaker_active_until:
                continue
            
            # Check drawdown circuit breaker
            if p["enable_circuit_breakers"] and drawdown_pct > p["circuit_breaker_drawdown_pct"]:
                continue
            
            # Basic filters
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            if session not in [TradingSession.LONDON, TradingSession.OVERLAP, TradingSession.NY]:
                continue
            
            if i - last_exit_index < p["min_candles_between_trades"]:
                continue
            
            # === CHOPPY DETECTION (STRICT) ===
            ema_whipsaws = detect_ema_whipsaws(ema_fast, ema_medium, i, p["ema_whipsaw_lookback"])
            directional_movement = calculate_directional_movement_score(candles, i, p["directional_lookback"])
            
            choppy_score = calculate_choppy_score(
                adx=adx[i],
                choppiness_index=choppiness[i],
                ema_whipsaws=ema_whipsaws,
                directional_movement=directional_movement,
                params=p
            )
            
            # STRICT NO-TRADE RULE
            if choppy_score > p["choppy_score_threshold"]:
                choppy_filtered_count += 1
                continue  # SKIP TRADING IN CHOPPY CONDITIONS
            
            # If we reach here, market is clean enough to trade
            # Use adaptive multi-signal logic
            
            distance_from_ema200 = abs(candle.close - ema_long[i]) / ema_long[i]
            
            if distance_from_ema200 < p["avoid_ema200_zone_pct"]:
                continue
            if distance_from_ema200 < p["min_distance_from_ema200_pct"]:
                continue
            
            bullish_bias = candle.close > ema_long[i]
            bearish_bias = candle.close < ema_long[i]
            
            signals = []
            confirmations = []
            
            # Adaptive confirmation requirements based on ADX
            if adx[i] >= 25:
                min_conf_add = 0
                risk_mult = 1.0
            elif adx[i] >= 20:
                min_conf_add = 1
                risk_mult = 0.8
            else:
                min_conf_add = 1
                risk_mult = 0.7
            
            dynamic_min_confirmations = p["min_confirmations"] + min_conf_add
            
            # LONG SIGNALS
            if bullish_bias:
                # Pullback
                near_ema20 = abs(candle.close - ema_fast[i]) / ema_fast[i] < p["pullback_distance_pct"]
                near_ema50 = abs(candle.close - ema_medium[i]) / ema_medium[i] < p["pullback_distance_pct"]
                if (near_ema20 or near_ema50) and candle.close > candle.open:
                    signals.append("pullback")
                
                # Breakout
                if i >= p["breakout_lookback"]:
                    recent_high, _ = calculate_recent_high_low(candles, i, p["breakout_lookback"])
                    if candle.close > recent_high * (1 + p["breakout_buffer_pct"]) and candle.close > candle.open:
                        signals.append("breakout")
                
                # Momentum
                is_strong, direction = is_strong_candle(candle, atr[i], p["momentum_threshold"])
                if is_strong and direction == "bullish":
                    signals.append("momentum")
                
                # Micro cross
                if i > 0:
                    if ema_micro[i] > ema_fast[i] and ema_micro[i-1] <= ema_fast[i-1]:
                        signals.append("micro_cross")
                
                # Confirmations
                if p["pullback_rsi_min"] <= rsi[i] <= p["pullback_rsi_max"]:
                    confirmations.append("rsi")
                if is_strong and direction == "bullish":
                    confirmations.append("strong_candle")
                if candle.close > ema_fast[i] and candle.close > ema_medium[i]:
                    confirmations.append("above_emas")
                if adx[i] > 25:
                    confirmations.append("strong_adx")
                if atr[i] > atr_ma[i] * 1.1:
                    confirmations.append("good_volatility")
                
                total_score = len(signals) + len(confirmations)
                
                if p["require_confirmation"] and len(signals) >= 1 and total_score >= dynamic_min_confirmations:
                    entry_price = candle.close
                    stop_loss = entry_price - (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = entry_price + (atr[i] * p["take_profit_atr_mult"])
                    
                    risk_amount = balance * (p["base_risk_pct"] * risk_mult / 100)
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
                        "choppy_score": choppy_score,
                    }
                    trades_per_day[day_key] += 1
                    
                    for sig in signals:
                        signal_counts[sig] += 1
                    
                    logger.debug(f"LONG: {entry_price:.5f}, ADX: {adx[i]:.1f}, Choppy: {choppy_score:.1f}, "
                               f"Signals: {signals}")
            
            # SHORT SIGNALS
            elif bearish_bias:
                near_ema20 = abs(candle.close - ema_fast[i]) / ema_fast[i] < p["pullback_distance_pct"]
                near_ema50 = abs(candle.close - ema_medium[i]) / ema_medium[i] < p["pullback_distance_pct"]
                if (near_ema20 or near_ema50) and candle.close < candle.open:
                    signals.append("pullback")
                
                if i >= p["breakout_lookback"]:
                    _, recent_low = calculate_recent_high_low(candles, i, p["breakout_lookback"])
                    if candle.close < recent_low * (1 - p["breakout_buffer_pct"]) and candle.close < candle.open:
                        signals.append("breakout")
                
                is_strong, direction = is_strong_candle(candle, atr[i], p["momentum_threshold"])
                if is_strong and direction == "bearish":
                    signals.append("momentum")
                
                if i > 0:
                    if ema_micro[i] < ema_fast[i] and ema_micro[i-1] >= ema_fast[i-1]:
                        signals.append("micro_cross")
                
                if p["pullback_rsi_min"] <= rsi[i] <= p["pullback_rsi_max"]:
                    confirmations.append("rsi")
                if is_strong and direction == "bearish":
                    confirmations.append("strong_candle")
                if candle.close < ema_fast[i] and candle.close < ema_medium[i]:
                    confirmations.append("below_emas")
                if adx[i] > 25:
                    confirmations.append("strong_adx")
                if atr[i] > atr_ma[i] * 1.1:
                    confirmations.append("good_volatility")
                
                total_score = len(signals) + len(confirmations)
                
                if p["require_confirmation"] and len(signals) >= 1 and total_score >= dynamic_min_confirmations:
                    entry_price = candle.close
                    stop_loss = entry_price + (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = entry_price - (atr[i] * p["take_profit_atr_mult"])
                    
                    risk_amount = balance * (p["base_risk_pct"] * risk_mult / 100)
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
                        "choppy_score": choppy_score,
                    }
                    trades_per_day[day_key] += 1
                    
                    for sig in signals:
                        signal_counts[sig] += 1
                    
                    logger.debug(f"SHORT: {entry_price:.5f}, ADX: {adx[i]:.1f}, Choppy: {choppy_score:.1f}, "
                               f"Signals: {signals}")
    
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
    
    logger.info(f"\n=== CHOPPY FILTERING STATISTICS ===")
    logger.info(f"Candles evaluated: {total_candles_evaluated}")
    logger.info(f"Choppy filtered: {choppy_filtered_count}")
    if total_candles_evaluated > 0:
        choppy_pct = (choppy_filtered_count / total_candles_evaluated) * 100
        logger.info(f"Choppy %: {choppy_pct:.1f}%")
    
    if circuit_breaker_activations > 0:
        logger.info(f"Circuit breaker activations: {circuit_breaker_activations}")
    
    logger.info(f"\nAnti-chop strategy complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
