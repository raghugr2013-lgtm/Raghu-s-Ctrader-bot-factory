"""
ANTI-CHOP GRADIENT ENHANCED STRATEGY

Enhanced version focusing on ENTRY QUALITY over filtering quantity.

Philosophy:
- Don't just filter choppy markets - SELECT HIGH-QUALITY ENTRIES
- Improve profit factor by taking better trades, not fewer trades
- Maintain stability while increasing edge

Key Enhancements:
1. RSI Momentum Direction (not just level - direction matters)
2. EMA Slope Strength (trend steepness and cleanness)
3. Trade Quality Scoring (0-100 score for each setup)
4. Pullback Quality Assessment (optimal depth and structure)
5. Improved Risk-Reward (higher TP, tight SL)
6. Clean Structure Requirements (avoid noise)

Target Metrics:
- Profit Factor > 1.5 (up from 1.33)
- Max Drawdown < 6% (maintain)
- Consistency > 50% (maintain 66.7%)
- Trades: 25-40 (maintain frequency)
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
from anti_chop_gradient import calculate_position_size_multiplier

logger = logging.getLogger(__name__)


def calculate_rsi_momentum(rsi: List[Optional[float]], current_idx: int, lookback: int = 3) -> Optional[str]:
    """
    Calculate RSI momentum direction
    
    Returns:
        "rising": RSI is trending up (bullish momentum)
        "falling": RSI is trending down (bearish momentum)
        "flat": RSI is sideways (no clear momentum)
        None: Not enough data
    """
    if current_idx < lookback:
        return None
    
    if any(rsi[i] is None for i in range(current_idx - lookback, current_idx + 1)):
        return None
    
    # Calculate RSI slope
    rsi_values = [rsi[i] for i in range(current_idx - lookback, current_idx + 1)]
    
    # Simple slope: difference between current and lookback periods
    rsi_change = rsi_values[-1] - rsi_values[0]
    
    # Threshold for momentum detection
    if rsi_change > 2.0:
        return "rising"
    elif rsi_change < -2.0:
        return "falling"
    else:
        return "flat"


def calculate_ema_slope(ema: List[Optional[float]], current_idx: int, lookback: int = 5) -> Optional[float]:
    """
    Calculate EMA slope (trend strength)
    
    Returns:
        Positive: Uptrend (higher = stronger)
        Negative: Downtrend (lower = stronger)
        Near zero: Flat/weak trend
        None: Not enough data
    """
    if current_idx < lookback:
        return None
    
    if any(ema[i] is None for i in range(current_idx - lookback, current_idx + 1)):
        return None
    
    ema_values = [ema[i] for i in range(current_idx - lookback, current_idx + 1)]
    
    # Calculate average change per bar (normalized by price)
    total_change = ema_values[-1] - ema_values[0]
    avg_change_per_bar = total_change / lookback
    
    # Normalize by current price (percentage change)
    pct_change_per_bar = (avg_change_per_bar / ema_values[-1]) * 100
    
    return pct_change_per_bar


def assess_pullback_quality(
    candles: List[Candle],
    current_idx: int,
    direction: str,
    lookback: int = 20
) -> Tuple[float, str]:
    """
    Assess pullback quality (0-100 score)
    
    Criteria:
    - Optimal depth (38.2% - 61.8% retracement)
    - Clean structure (few whipsaws)
    - Appropriate duration (not too fast, not too slow)
    
    Returns:
        (score, reason)
    """
    if current_idx < lookback:
        return 0.0, "Insufficient data"
    
    recent_candles = candles[current_idx - lookback:current_idx + 1]
    
    # Find swing high and low
    if direction == "LONG":
        swing_high = max(c.high for c in recent_candles[:-5])
        swing_low = min(c.low for c in recent_candles[-10:])
        current_price = candles[current_idx].close
        
        # Calculate retracement depth
        swing_range = swing_high - swing_low
        if swing_range <= 0:
            return 0.0, "Invalid swing"
        
        pullback_from_high = swing_high - current_price
        retracement_pct = (pullback_from_high / swing_range) * 100
        
    else:  # SHORT
        swing_low = min(c.low for c in recent_candles[:-5])
        swing_high = max(c.high for c in recent_candles[-10:])
        current_price = candles[current_idx].close
        
        swing_range = swing_high - swing_low
        if swing_range <= 0:
            return 0.0, "Invalid swing"
        
        pullback_from_low = current_price - swing_low
        retracement_pct = (pullback_from_low / swing_range) * 100
    
    # Score based on optimal retracement (38.2% - 61.8%)
    depth_score = 0.0
    if 38.2 <= retracement_pct <= 61.8:
        depth_score = 40.0  # Optimal zone
        reason = f"Optimal pullback ({retracement_pct:.1f}%)"
    elif 25 <= retracement_pct < 38.2 or 61.8 < retracement_pct <= 75:
        depth_score = 25.0  # Acceptable zone
        reason = f"Acceptable pullback ({retracement_pct:.1f}%)"
    elif 15 <= retracement_pct < 25 or 75 < retracement_pct <= 85:
        depth_score = 10.0  # Marginal zone
        reason = f"Marginal pullback ({retracement_pct:.1f}%)"
    else:
        depth_score = 0.0  # Too shallow or too deep
        reason = f"Poor pullback depth ({retracement_pct:.1f}%)"
    
    # Assess structure cleanness (check for whipsaws during pullback)
    pullback_candles = recent_candles[-10:]
    
    if direction == "LONG":
        # Count bars that went against pullback (closed higher during pullback)
        counter_moves = sum(1 for i in range(1, len(pullback_candles)) 
                          if pullback_candles[i].close > pullback_candles[i-1].close)
    else:  # SHORT
        counter_moves = sum(1 for i in range(1, len(pullback_candles))
                          if pullback_candles[i].close < pullback_candles[i-1].close)
    
    # Structure score (fewer counter-moves = cleaner)
    if counter_moves <= 2:
        structure_score = 35.0
    elif counter_moves <= 4:
        structure_score = 20.0
    elif counter_moves <= 6:
        structure_score = 10.0
    else:
        structure_score = 0.0
    
    # Duration score (pullback should take 5-12 bars)
    duration_score = 25.0 if 5 <= len(pullback_candles) <= 12 else 15.0
    
    total_score = depth_score + structure_score + duration_score
    
    return total_score, reason


def calculate_trade_quality_score(
    adx: float,
    rsi_momentum: str,
    ema_slope: float,
    pullback_score: float,
    signal_count: int,
    confirmation_count: int,
    choppy_score: float,
    direction: str
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate overall trade quality score (0-100)
    
    Components:
    - Trend Strength (ADX): 30 points
    - Pullback Quality: 25 points
    - Signal Alignment: 25 points
    - Momentum Direction: 20 points
    
    Returns:
        (total_score, component_breakdown)
    """
    breakdown = {}
    
    # Component 1: Trend Strength (ADX) - 30 points
    if adx >= 35:
        trend_score = 30.0
    elif adx >= 28:
        trend_score = 25.0
    elif adx >= 22:
        trend_score = 18.0
    elif adx >= 18:
        trend_score = 10.0
    else:
        trend_score = 0.0
    
    breakdown['trend_strength'] = trend_score
    
    # Component 2: Pullback Quality - 25 points
    breakdown['pullback_quality'] = pullback_score * 0.25  # Normalize to 25 points
    
    # Component 3: Signal Alignment - 25 points
    signal_alignment_score = min((signal_count + confirmation_count) * 4, 25.0)
    breakdown['signal_alignment'] = signal_alignment_score
    
    # Component 4: Momentum Direction - 20 points
    if direction == "LONG":
        if rsi_momentum == "rising" and ema_slope > 0.01:
            momentum_score = 20.0  # Perfect alignment
        elif rsi_momentum == "rising" or ema_slope > 0.005:
            momentum_score = 12.0  # Partial alignment
        else:
            momentum_score = 0.0  # No alignment
    else:  # SHORT
        if rsi_momentum == "falling" and ema_slope < -0.01:
            momentum_score = 20.0
        elif rsi_momentum == "falling" or ema_slope < -0.005:
            momentum_score = 12.0
        else:
            momentum_score = 0.0
    
    breakdown['momentum_direction'] = momentum_score
    
    # Penalty for high choppy score (reduce quality if market is choppy)
    choppy_penalty = 0.0
    if choppy_score > 50:
        choppy_penalty = min((choppy_score - 50) * 0.3, 15.0)
    
    breakdown['choppy_penalty'] = -choppy_penalty
    
    total_score = (trend_score + breakdown['pullback_quality'] + 
                   signal_alignment_score + momentum_score - choppy_penalty)
    
    return max(0, min(100, total_score)), breakdown


def run_anti_chop_gradient_enhanced_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Anti-Chop Gradient Enhanced Strategy
    
    Focus: ENTRY QUALITY over quantity filtering
    
    NEW FEATURES:
    - RSI momentum direction confirmation
    - EMA slope strength measurement
    - Trade quality scoring (0-100)
    - Pullback quality assessment
    - Higher TP for better RR
    - Quality threshold filter
    
    MAINTAINED:
    - Gradient position sizing
    - Anti-chop filtering
    - Risk management
    - Circuit breakers
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
        
        # Risk management - ENHANCED RR
        "base_risk_pct": 0.7,
        "stop_loss_atr_mult": 1.9,  # Keep tight
        "take_profit_atr_mult": 4.8,  # Increased from 4.3 to 4.8
        "max_trades_per_day": 3,
        "min_candles_between_trades": 2,
        "atr_lookback": 20,
        
        # Choppy Detection
        "ema_whipsaw_lookback": 20,
        "directional_lookback": 20,
        
        # Gradient Position Sizing (from gradient strategy)
        "gradient_full_threshold": 32,
        "gradient_high_threshold": 47,
        "gradient_medium_threshold": 62,
        "gradient_skip_threshold": 62,
        "min_position_floor": 0.5,
        
        # Strong Signal Override
        "enable_strong_signal_override": True,
        "override_adx_threshold": 29,
        "override_min_signals": 3,
        
        # NEW: ENTRY QUALITY ENHANCEMENT
        "enable_quality_filter": True,
        "min_quality_score": 55,  # Only take trades with quality > 55/100
        "rsi_momentum_lookback": 3,
        "ema_slope_lookback": 5,
        "pullback_assessment_lookback": 20,
        "require_rsi_momentum_alignment": True,
        "require_positive_ema_slope": True,
        "min_pullback_quality": 40,  # Minimum pullback quality score
        
        # Circuit Breakers
        "enable_circuit_breakers": True,
        "circuit_breaker_consecutive_losses": 4,
        "circuit_breaker_pause_candles": 20,
        "circuit_breaker_drawdown_pct": 4.0,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running ANTI-CHOP GRADIENT ENHANCED strategy")
    logger.info(f"  Entry Quality Focus: Min quality score {p['min_quality_score']}/100")
    logger.info(f"  Risk-Reward: TP {p['take_profit_atr_mult']}x / SL {p['stop_loss_atr_mult']}x = {p['take_profit_atr_mult']/p['stop_loss_atr_mult']:.2f}:1")
    logger.info(f"  Gradient: <{p['gradient_full_threshold']}=100%, "
                f"<{p['gradient_high_threshold']}=80%, "
                f"<{p['gradient_medium_threshold']}=60%")
    
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
    quality_distribution = {"excellent": 0, "good": 0, "acceptable": 0, "filtered": 0}
    quality_filtered_count = 0
    choppy_skipped_count = 0
    total_opportunities = 0
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
            adx[i] is None or atr_ma[i] is None or rsi[i] is None or
            i < p["ema_long"]):
            continue
        
        # Session and day tracking
        session = get_trading_session(candle.timestamp)
        day_key = candle.timestamp.date()
        if day_key not in trades_per_day:
            trades_per_day[day_key] = 0
        
        # Exit management (same as gradient strategy)
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
                        logger.info(f"⚠️  Circuit breaker #{circuit_breaker_activations} at {candle.timestamp}")
                else:
                    consecutive_losses = 0
                
                position = None
        
        # Entry logic - with ENHANCED QUALITY FILTER
        if position is None:
            total_opportunities += 1
            
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
            
            # Skip if too choppy
            if choppy_score > p["gradient_skip_threshold"]:
                choppy_skipped_count += 1
                continue
            
            # Check distance from EMA200
            distance_from_ema200 = abs(candle.close - ema_long[i]) / ema_long[i]
            
            if distance_from_ema200 < p["avoid_ema200_zone_pct"]:
                continue
            if distance_from_ema200 < p["min_distance_from_ema200_pct"]:
                continue
            
            bullish_bias = candle.close > ema_long[i]
            bearish_bias = candle.close < ema_long[i]
            
            # === NEW: CALCULATE ENHANCED QUALITY METRICS ===
            rsi_momentum = calculate_rsi_momentum(rsi, i, p["rsi_momentum_lookback"])
            ema_fast_slope = calculate_ema_slope(ema_fast, i, p["ema_slope_lookback"])
            
            if rsi_momentum is None or ema_fast_slope is None:
                continue
            
            signals = []
            confirmations = []
            
            # Adaptive confirmation requirements
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
            
            # LONG SIGNALS with ENHANCED QUALITY
            if bullish_bias:
                # === NEW: RSI Momentum Check ===
                if p["require_rsi_momentum_alignment"] and rsi_momentum != "rising":
                    continue  # Skip if RSI momentum doesn't align
                
                # === NEW: EMA Slope Check ===
                if p["require_positive_ema_slope"] and ema_fast_slope <= 0.005:
                    continue  # Skip if EMA not trending up strongly
                
                # === NEW: Assess Pullback Quality ===
                pullback_score, pullback_reason = assess_pullback_quality(
                    candles, i, "LONG", p["pullback_assessment_lookback"]
                )
                
                if pullback_score < p["min_pullback_quality"]:
                    continue  # Skip poor quality pullbacks
                
                # Original signal detection
                near_ema20 = abs(candle.close - ema_fast[i]) / ema_fast[i] < p["pullback_distance_pct"]
                near_ema50 = abs(candle.close - ema_medium[i]) / ema_medium[i] < p["pullback_distance_pct"]
                if (near_ema20 or near_ema50) and candle.close > candle.open:
                    signals.append("pullback")
                
                if i >= p["breakout_lookback"]:
                    recent_high, _ = calculate_recent_high_low(candles, i, p["breakout_lookback"])
                    if candle.close > recent_high * (1 + p["breakout_buffer_pct"]) and candle.close > candle.open:
                        signals.append("breakout")
                
                is_strong, direction = is_strong_candle(candle, atr[i], p["momentum_threshold"])
                if is_strong and direction == "bullish":
                    signals.append("momentum")
                
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
                    # === NEW: CALCULATE TRADE QUALITY SCORE ===
                    quality_score, quality_breakdown = calculate_trade_quality_score(
                        adx=adx[i],
                        rsi_momentum=rsi_momentum,
                        ema_slope=ema_fast_slope,
                        pullback_score=pullback_score,
                        signal_count=len(signals),
                        confirmation_count=len(confirmations),
                        choppy_score=choppy_score,
                        direction="LONG"
                    )
                    
                    # === NEW: QUALITY FILTER ===
                    if p["enable_quality_filter"] and quality_score < p["min_quality_score"]:
                        quality_filtered_count += 1
                        continue  # Skip low-quality setups
                    
                    # Track quality distribution
                    if quality_score >= 75:
                        quality_distribution["excellent"] += 1
                    elif quality_score >= 65:
                        quality_distribution["good"] += 1
                    else:
                        quality_distribution["acceptable"] += 1
                    
                    # Calculate gradient position size
                    position_multiplier, position_reason = calculate_position_size_multiplier(
                        choppy_score=choppy_score,
                        adx=adx[i],
                        signal_strength=signal_strength,
                        params=p
                    )
                    
                    if position_multiplier == 0.0:
                        choppy_skipped_count += 1
                        continue
                    
                    # Calculate position with enhanced RR
                    entry_price = candle.close
                    stop_loss = entry_price - (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = entry_price + (atr[i] * p["take_profit_atr_mult"])
                    
                    risk_amount = balance * (p["base_risk_pct"] * risk_mult / 100)
                    stop_distance_pips = (entry_price - stop_loss) * 10000
                    
                    if stop_distance_pips > 0:
                        base_lots = risk_amount / (stop_distance_pips * 10)
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
                        "quality_score": quality_score,
                        "quality_breakdown": quality_breakdown,
                    }
                    trades_per_day[day_key] += 1
                    
                    for sig in signals:
                        signal_counts[sig] += 1
                    
                    logger.debug(f"LONG: {entry_price:.5f}, Quality: {quality_score:.0f}/100, "
                               f"ADX: {adx[i]:.1f}, RSI Momentum: {rsi_momentum}, "
                               f"EMA Slope: {ema_fast_slope:.4f}, Pullback: {pullback_score:.0f}")
            
            # SHORT SIGNALS with ENHANCED QUALITY
            elif bearish_bias:
                # === NEW: RSI Momentum Check ===
                if p["require_rsi_momentum_alignment"] and rsi_momentum != "falling":
                    continue
                
                # === NEW: EMA Slope Check ===
                if p["require_positive_ema_slope"] and ema_fast_slope >= -0.005:
                    continue
                
                # === NEW: Assess Pullback Quality ===
                pullback_score, pullback_reason = assess_pullback_quality(
                    candles, i, "SHORT", p["pullback_assessment_lookback"]
                )
                
                if pullback_score < p["min_pullback_quality"]:
                    continue
                
                # Original signal detection
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
                
                # Confirmations
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
                    # === NEW: CALCULATE TRADE QUALITY SCORE ===
                    quality_score, quality_breakdown = calculate_trade_quality_score(
                        adx=adx[i],
                        rsi_momentum=rsi_momentum,
                        ema_slope=ema_fast_slope,
                        pullback_score=pullback_score,
                        signal_count=len(signals),
                        confirmation_count=len(confirmations),
                        choppy_score=choppy_score,
                        direction="SHORT"
                    )
                    
                    # === NEW: QUALITY FILTER ===
                    if p["enable_quality_filter"] and quality_score < p["min_quality_score"]:
                        quality_filtered_count += 1
                        continue
                    
                    # Track quality distribution
                    if quality_score >= 75:
                        quality_distribution["excellent"] += 1
                    elif quality_score >= 65:
                        quality_distribution["good"] += 1
                    else:
                        quality_distribution["acceptable"] += 1
                    
                    # Calculate gradient position size
                    position_multiplier, position_reason = calculate_position_size_multiplier(
                        choppy_score=choppy_score,
                        adx=adx[i],
                        signal_strength=signal_strength,
                        params=p
                    )
                    
                    if position_multiplier == 0.0:
                        choppy_skipped_count += 1
                        continue
                    
                    # Calculate position with enhanced RR
                    entry_price = candle.close
                    stop_loss = entry_price + (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = entry_price - (atr[i] * p["take_profit_atr_mult"])
                    
                    risk_amount = balance * (p["base_risk_pct"] * risk_mult / 100)
                    stop_distance_pips = (stop_loss - entry_price) * 10000
                    
                    if stop_distance_pips > 0:
                        base_lots = risk_amount / (stop_distance_pips * 10)
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
                        "quality_score": quality_score,
                        "quality_breakdown": quality_breakdown,
                    }
                    trades_per_day[day_key] += 1
                    
                    for sig in signals:
                        signal_counts[sig] += 1
                    
                    logger.debug(f"SHORT: {entry_price:.5f}, Quality: {quality_score:.0f}/100, "
                               f"ADX: {adx[i]:.1f}, RSI Momentum: {rsi_momentum}, "
                               f"EMA Slope: {ema_fast_slope:.4f}, Pullback: {pullback_score:.0f}")
    
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
    
    logger.info(f"\n=== QUALITY DISTRIBUTION ===")
    total_quality_trades = sum(quality_distribution.values()) - quality_distribution["filtered"]
    if total_quality_trades > 0:
        for quality, count in sorted(quality_distribution.items(), key=lambda x: x[1], reverse=True):
            if quality != "filtered":
                pct = count / total_quality_trades * 100
                logger.info(f"  {quality}: {count} ({pct:.1f}%)")
    
    logger.info(f"\n=== FILTERING STATISTICS ===")
    logger.info(f"Total opportunities evaluated: {total_opportunities}")
    logger.info(f"Choppy filtered: {choppy_skipped_count}")
    logger.info(f"Quality filtered: {quality_filtered_count}")
    logger.info(f"Trades executed: {len(trades)}")
    if total_opportunities > 0:
        execution_rate = (len(trades) / total_opportunities) * 100
        logger.info(f"Execution rate: {execution_rate:.1f}%")
    
    if circuit_breaker_activations > 0:
        logger.info(f"\nCircuit breaker activations: {circuit_breaker_activations}")
    
    logger.info(f"\n✅ Anti-chop GRADIENT ENHANCED strategy complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
