"""
ANTI-CHOP GRADIENT STRATEGY

Evolution of anti_chop_strategy.py with GRADIENT-BASED position sizing instead of binary filtering.

Key Innovation: Position size scales with market quality instead of binary skip/trade

Philosophy:
- Binary filtering (skip if choppy > threshold) is TOO AGGRESSIVE
- Gradient approach: Trade more in clean conditions, less in borderline conditions
- Maintains activity while controlling risk

Position Sizing Logic:
- Choppy Score < 30  → 100% position (excellent conditions)
- Choppy Score 30-45 → 80% position (good conditions)
- Choppy Score 45-60 → 60% position (acceptable conditions)
- Choppy Score > 60  → SKIP (too choppy)

Additional Features:
- Minimum position floor: 50% (ensures meaningful trades)
- Strong signal override: Boost position size when ADX high + strong signal
- Preserves all trend-following logic from anti_chop_strategy
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
from anti_chop_strategy import (
    detect_ema_whipsaws, 
    calculate_directional_movement_score, 
    calculate_choppy_score
)

logger = logging.getLogger(__name__)


def calculate_position_size_multiplier(
    choppy_score: float,
    adx: float,
    signal_strength: int,
    params: Dict
) -> Tuple[float, str]:
    """
    Calculate position size multiplier based on choppy score and signal strength
    
    Args:
        choppy_score: 0-100 (higher = more choppy)
        adx: Current ADX value
        signal_strength: Number of confirmations (0-5+)
        params: Strategy parameters
    
    Returns:
        (multiplier, reason) where multiplier is 0.0-1.0
    """
    
    # Base gradient thresholds
    if choppy_score > params["gradient_skip_threshold"]:
        return 0.0, f"Too choppy (score: {choppy_score:.1f})"
    
    # Gradient position sizing
    if choppy_score < params["gradient_full_threshold"]:
        base_multiplier = 1.0  # 100%
        confidence = "excellent"
    elif choppy_score < params["gradient_high_threshold"]:
        base_multiplier = 0.8  # 80%
        confidence = "good"
    elif choppy_score < params["gradient_medium_threshold"]:
        base_multiplier = 0.6  # 60%
        confidence = "acceptable"
    else:
        base_multiplier = 0.6  # 60% (fallback)
        confidence = "borderline"
    
    # Strong signal override: Boost position size if conditions are exceptional
    if params["enable_strong_signal_override"]:
        # Criteria for override:
        # 1. ADX shows strong trend (> 30)
        # 2. Multiple signal confirmations (3+)
        # 3. Not in the skip zone
        if adx > params["override_adx_threshold"] and signal_strength >= params["override_min_signals"]:
            # Boost by 20% (but cap at 100%)
            override_multiplier = min(base_multiplier + 0.2, 1.0)
            
            if override_multiplier > base_multiplier:
                return override_multiplier, f"Override boost: {confidence} + strong signal (ADX: {adx:.1f})"
    
    # Apply minimum position floor
    final_multiplier = max(base_multiplier, params["min_position_floor"])
    
    # Reason string
    if final_multiplier == params["min_position_floor"] and base_multiplier < params["min_position_floor"]:
        reason = f"{confidence} (floored to {params['min_position_floor']*100:.0f}%)"
    else:
        reason = f"{confidence} ({final_multiplier*100:.0f}%)"
    
    return final_multiplier, reason


def run_anti_chop_gradient_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Anti-Chop Gradient Strategy
    
    Core Logic:
    1. Calculate Choppy Score (0-100)
    2. Use GRADIENT position sizing instead of binary skip
    3. Allow strong signal overrides
    4. Maintain minimum position floor
    5. Preserve all trend-following and risk management logic
    
    NEW GRADIENT PARAMETERS:
    - gradient_full_threshold: 30 (100% position if score < this)
    - gradient_high_threshold: 45 (80% position if score < this)
    - gradient_medium_threshold: 60 (60% position if score < this)
    - gradient_skip_threshold: 60 (skip if score > this)
    - min_position_floor: 0.5 (50% minimum position)
    - enable_strong_signal_override: True
    - override_adx_threshold: 30
    - override_min_signals: 3
    """
    
    default_params = {
        # Trend-following parameters (from anti_chop_strategy)
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
        "min_confirmations": 2,  # Kept at 2 for better entry timing
        
        # Filters
        "avoid_ema200_zone_pct": 0.002,
        "min_distance_from_ema200_pct": 0.0015,
        "enable_ema_alignment_filter": True,  # NEW: Require EMA alignment for quality trades
        "enable_session_filter": True,  # NEW: Only trade high-liquidity sessions
        
        # Risk management
        "base_risk_pct": 0.7,
        "stop_loss_atr_mult": 1.9,
        "take_profit_atr_mult": 3.5,  # Reduced from 4.0 to 3.5 for better hit rate
        "max_trades_per_day": 3,
        "min_candles_between_trades": 2,
        "atr_lookback": 20,
        
        # Choppy Detection (from anti_chop_strategy)
        "ema_whipsaw_lookback": 20,
        "directional_lookback": 20,
        
        # NEW: GRADIENT POSITION SIZING
        "gradient_full_threshold": 30,      # 100% position if score < 30
        "gradient_high_threshold": 45,      # 80% position if score < 45
        "gradient_medium_threshold": 60,    # 60% position if score < 60
        "gradient_skip_threshold": 60,      # Skip if score > 60
        "min_position_floor": 0.5,          # Never go below 50% position
        
        # NEW: STRONG SIGNAL OVERRIDE
        "enable_strong_signal_override": True,
        "override_adx_threshold": 25,       # Reduced from 30 to 25 for more overrides
        "override_min_signals": 2,          # Reduced from 3 to 2 for easier activation
        
        # Circuit Breakers
        "enable_circuit_breakers": True,
        "circuit_breaker_consecutive_losses": 4,
        "circuit_breaker_pause_candles": 20,
        "circuit_breaker_drawdown_pct": 4.0,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running ANTI-CHOP GRADIENT strategy")
    logger.info(f"  Gradient: <{p['gradient_full_threshold']}=100%, "
                f"<{p['gradient_high_threshold']}=80%, "
                f"<{p['gradient_medium_threshold']}=60%, "
                f">{p['gradient_skip_threshold']}=skip")
    logger.info(f"  Min position floor: {p['min_position_floor']*100:.0f}%")
    logger.info(f"  Strong signal override: {p['enable_strong_signal_override']}")
    
    # Calculate indicators (same as anti_chop_strategy)
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
    position_size_distribution = {"100%": 0, "80%": 0, "60%": 0, "override": 0, "floored": 0}
    choppy_skipped_count = 0
    total_candles_evaluated = 0
    circuit_breaker_activations = 0
    
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
        
        # Exit management (same as anti_chop_strategy)
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
        
        # Entry logic - with GRADIENT POSITION SIZING
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
            
            # === CALCULATE CHOPPY SCORE ===
            ema_whipsaws = detect_ema_whipsaws(ema_fast, ema_medium, i, p["ema_whipsaw_lookback"])
            directional_movement = calculate_directional_movement_score(candles, i, p["directional_lookback"])
            
            choppy_score = calculate_choppy_score(
                adx=adx[i],
                choppiness_index=choppiness[i],
                ema_whipsaws=ema_whipsaws,
                directional_movement=directional_movement,
                params=p
            )
            
            # === GRADIENT POSITION SIZING ===
            # Check distance from EMA200
            distance_from_ema200 = abs(candle.close - ema_long[i]) / ema_long[i]
            
            if distance_from_ema200 < p["avoid_ema200_zone_pct"]:
                continue
            if distance_from_ema200 < p["min_distance_from_ema200_pct"]:
                continue
            
            bullish_bias = candle.close > ema_long[i]
            bearish_bias = candle.close < ema_long[i]
            
            # NEW: EMA Alignment Filter (improves entry quality)
            if p["enable_ema_alignment_filter"]:
                # For LONG: Require price above EMA50 (stronger trend confirmation)
                bullish_ema_aligned = candle.close > ema_medium[i]
                # For SHORT: Require price below EMA50
                bearish_ema_aligned = candle.close < ema_medium[i]
            else:
                bullish_ema_aligned = True
                bearish_ema_aligned = True
            
            # NEW: Session Filter (only trade high-liquidity periods)
            session_allowed = True
            if p["enable_session_filter"]:
                # Allow trading only during London (8-16 UTC) and NY (13-21 UTC)
                hour_utc = candle.timestamp.hour
                # London: 8-16, NY: 13-21, Overlap: 13-16 (best)
                session_allowed = (8 <= hour_utc < 21)  # Combined London + NY window
            
            signals = []
            confirmations = []
            
            # Adaptive confirmation requirements based on ADX (adjusted thresholds)
            if adx[i] >= 20:  # Reduced from 25 to 20 to catch more trends
                min_conf_add = 0
                risk_mult = 1.0
            elif adx[i] >= 15:  # Reduced from 20 to 15
                min_conf_add = 1
                risk_mult = 0.8
            else:
                min_conf_add = 1
                risk_mult = 0.7
            
            dynamic_min_confirmations = p["min_confirmations"] + min_conf_add
            
            # LONG SIGNALS (same logic as anti_chop)
            if bullish_bias and bullish_ema_aligned and session_allowed:  # Added EMA alignment and session filter
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
                signal_strength = total_score
                
                if p["require_confirmation"] and len(signals) >= 1 and total_score >= dynamic_min_confirmations:
                    # === CALCULATE GRADIENT POSITION SIZE ===
                    position_multiplier, position_reason = calculate_position_size_multiplier(
                        choppy_score=choppy_score,
                        adx=adx[i],
                        signal_strength=signal_strength,
                        params=p
                    )
                    
                    # Skip if multiplier is 0
                    if position_multiplier == 0.0:
                        choppy_skipped_count += 1
                        continue
                    
                    # Track position size distribution
                    if "override" in position_reason.lower():
                        position_size_distribution["override"] += 1
                    elif "floored" in position_reason.lower():
                        position_size_distribution["floored"] += 1
                    elif position_multiplier >= 0.99:
                        position_size_distribution["100%"] += 1
                    elif position_multiplier >= 0.79:
                        position_size_distribution["80%"] += 1
                    else:
                        position_size_distribution["60%"] += 1
                    
                    # Calculate position size with gradient multiplier
                    entry_price = candle.close
                    stop_loss = entry_price - (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = entry_price + (atr[i] * p["take_profit_atr_mult"])
                    
                    risk_amount = balance * (p["base_risk_pct"] * risk_mult / 100)
                    stop_distance_pips = (entry_price - stop_loss) * 10000
                    
                    if stop_distance_pips > 0:
                        base_lots = risk_amount / (stop_distance_pips * 10)
                        # APPLY GRADIENT MULTIPLIER
                        lots = base_lots * position_multiplier
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
                        "position_multiplier": position_multiplier,
                        "position_reason": position_reason,
                    }
                    trades_per_day[day_key] += 1
                    
                    for sig in signals:
                        signal_counts[sig] += 1
                    
                    logger.debug(f"LONG: {entry_price:.5f}, ADX: {adx[i]:.1f}, Choppy: {choppy_score:.1f}, "
                               f"Size: {position_multiplier*100:.0f}% ({position_reason}), Signals: {signals}")
            
            # SHORT SIGNALS (same logic, with gradient multiplier)
            elif bearish_bias and bearish_ema_aligned and session_allowed:  # Added EMA alignment and session filter
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
                signal_strength = total_score
                
                if p["require_confirmation"] and len(signals) >= 1 and total_score >= dynamic_min_confirmations:
                    # === CALCULATE GRADIENT POSITION SIZE ===
                    position_multiplier, position_reason = calculate_position_size_multiplier(
                        choppy_score=choppy_score,
                        adx=adx[i],
                        signal_strength=signal_strength,
                        params=p
                    )
                    
                    # Skip if multiplier is 0
                    if position_multiplier == 0.0:
                        choppy_skipped_count += 1
                        continue
                    
                    # Track position size distribution
                    if "override" in position_reason.lower():
                        position_size_distribution["override"] += 1
                    elif "floored" in position_reason.lower():
                        position_size_distribution["floored"] += 1
                    elif position_multiplier >= 0.99:
                        position_size_distribution["100%"] += 1
                    elif position_multiplier >= 0.79:
                        position_size_distribution["80%"] += 1
                    else:
                        position_size_distribution["60%"] += 1
                    
                    # Calculate position size with gradient multiplier
                    entry_price = candle.close
                    stop_loss = entry_price + (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = entry_price - (atr[i] * p["take_profit_atr_mult"])
                    
                    risk_amount = balance * (p["base_risk_pct"] * risk_mult / 100)
                    stop_distance_pips = (stop_loss - entry_price) * 10000
                    
                    if stop_distance_pips > 0:
                        base_lots = risk_amount / (stop_distance_pips * 10)
                        # APPLY GRADIENT MULTIPLIER
                        lots = base_lots * position_multiplier
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
                        "position_multiplier": position_multiplier,
                        "position_reason": position_reason,
                    }
                    trades_per_day[day_key] += 1
                    
                    for sig in signals:
                        signal_counts[sig] += 1
                    
                    logger.debug(f"SHORT: {entry_price:.5f}, ADX: {adx[i]:.1f}, Choppy: {choppy_score:.1f}, "
                               f"Size: {position_multiplier*100:.0f}% ({position_reason}), Signals: {signals}")
    
    # Close final position
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, "End of Test", config.symbol)
        trade.profit_loss *= position["lots"]
        trades.append(trade)
        balance += trade.profit_loss
    
    # Log statistics
    total_signals = sum(signal_counts.values())
    if total_signals > 0:
        logger.info(f"\n=== SIGNAL DISTRIBUTION ===")
        for signal, count in sorted(signal_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / total_signals * 100
            logger.info(f"  {signal}: {count} ({pct:.1f}%)")
    
    logger.info(f"\n=== GRADIENT POSITION SIZE DISTRIBUTION ===")
    total_positions = sum(position_size_distribution.values())
    if total_positions > 0:
        for size, count in sorted(position_size_distribution.items(), key=lambda x: x[1], reverse=True):
            pct = count / total_positions * 100
            logger.info(f"  {size}: {count} ({pct:.1f}%)")
    
    logger.info(f"\n=== CHOPPY FILTERING STATISTICS ===")
    logger.info(f"Candles evaluated: {total_candles_evaluated}")
    logger.info(f"Choppy skipped: {choppy_skipped_count}")
    if total_candles_evaluated > 0:
        choppy_pct = (choppy_skipped_count / total_candles_evaluated) * 100
        logger.info(f"Choppy %: {choppy_pct:.1f}%")
    
    if circuit_breaker_activations > 0:
        logger.info(f"\nCircuit breaker activations: {circuit_breaker_activations}")
    
    logger.info(f"\n✅ Anti-chop GRADIENT strategy complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
