"""
Aggressive Adaptive Multi-Signal Strategy - Version 2

KEY CHANGES from adaptive_multi_signal.py:
1. MORE aggressive regime filtering (can skip trading entirely)
2. Circuit breaker for consecutive losses
3. Stricter ADX thresholds
4. Add higher timeframe trend filter
5. Skip trading when conditions are very unfavorable

Goal: Push consistency from 22% to 50%+ by being more selective
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
from adaptive_multi_signal import calculate_adx, classify_market_regime, calculate_recent_high_low, is_strong_candle

logger = logging.getLogger(__name__)


def get_aggressive_regime_multipliers(regime: str, consecutive_losses: int) -> Dict[str, float]:
    """
    More aggressive regime multipliers + circuit breaker
    
    Ranging markets: SKIP trading (risk_mult = 0)
    Low volatility: Minimal trading
    Consecutive losses: Reduce exposure further
    """
    base_multipliers = {
        "strong_trend": {
            "risk_mult": 1.0,
            "min_conf_add": 0,
            "sl_mult": 1.0,
            "tp_mult": 1.0,
            "skip_trading": False,
        },
        "weak_trend": {
            "risk_mult": 0.6,      # Reduced from 0.75
            "min_conf_add": 1,
            "sl_mult": 0.9,
            "tp_mult": 1.0,
            "skip_trading": False,
        },
        "ranging": {
            "risk_mult": 0.0,      # SKIP TRADING (was 0.5)
            "min_conf_add": 3,
            "sl_mult": 0.8,
            "tp_mult": 0.9,
            "skip_trading": True,   # NEW: Skip entirely
        },
        "low_volatility": {
            "risk_mult": 0.3,      # Reduced from 0.6
            "min_conf_add": 2,
            "sl_mult": 0.85,
            "tp_mult": 0.95,
            "skip_trading": False,
        },
    }
    
    mults = base_multipliers.get(regime, base_multipliers["weak_trend"])
    
    # Circuit breaker: Reduce risk after consecutive losses
    if consecutive_losses >= 3:
        mults["risk_mult"] *= 0.5
        mults["min_conf_add"] += 1
    elif consecutive_losses >= 2:
        mults["risk_mult"] *= 0.7
    
    return mults


def calculate_higher_timeframe_bias(candles: List[Candle], current_idx: int, lookback: int = 100) -> str:
    """
    Calculate higher timeframe trend bias
    Returns: "bullish", "bearish", or "neutral"
    """
    if current_idx < lookback:
        return "neutral"
    
    htf_candles = candles[current_idx - lookback:current_idx]
    
    # Simple higher timeframe trend: compare recent price to lookback price
    start_price = htf_candles[0].close
    current_price = candles[current_idx].close
    
    price_change_pct = (current_price - start_price) / start_price
    
    if price_change_pct > 0.01:  # 1% up
        return "bullish"
    elif price_change_pct < -0.01:  # 1% down
        return "bearish"
    else:
        return "neutral"


def run_aggressive_adaptive_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Aggressive adaptive strategy that can SKIP trading in unfavorable conditions
    
    NEW FEATURES:
    - Skip trading entirely in ranging markets (ADX < 20)
    - Circuit breaker for consecutive losses
    - Higher timeframe trend filter
    - More aggressive confirmation requirements
    """
    
    default_params = {
        "ema_micro": 3,
        "ema_fast": 20,
        "ema_medium": 50,
        "ema_long": 200,
        "rsi_period": 14,
        "atr_period": 14,
        
        "pullback_rsi_min": 42,
        "pullback_rsi_max": 58,
        "pullback_distance_pct": 0.003,
        "breakout_lookback": 20,
        "breakout_buffer_pct": 0.0002,
        "momentum_threshold": 0.85,
        
        "require_confirmation": True,
        "min_confirmations": 2,
        
        "avoid_ema200_zone_pct": 0.002,
        "min_distance_from_ema200_pct": 0.0015,
        
        "base_risk_pct": 0.75,
        "stop_loss_atr_mult": 1.9,
        "take_profit_atr_mult": 4.0,
        "max_trades_per_day": 3,
        "min_candles_between_trades": 2,
        "min_atr_threshold": 0.0003,
        
        # Regime detection (MORE AGGRESSIVE)
        "adx_period": 14,
        "adx_trending_threshold": 25,
        "adx_ranging_threshold": 20,  # Raised from 18 (stricter)
        "atr_lookback": 20,
        "enable_regime_adaptation": True,
        
        # NEW: Higher timeframe
        "htf_lookback": 100,
        "require_htf_alignment": True,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running AGGRESSIVE adaptive strategy with skip logic")
    
    # Calculate indicators
    ema_micro = _calculate_ema(candles, p["ema_micro"])
    ema_fast = _calculate_ema(candles, p["ema_fast"])
    ema_medium = _calculate_ema(candles, p["ema_medium"])
    ema_long = _calculate_ema(candles, p["ema_long"])
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    adx = calculate_adx(candles, p["adx_period"])
    
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
    
    # Statistics
    signal_counts = {"pullback": 0, "breakout": 0, "momentum": 0, "micro_cross": 0}
    filtered_counts = {"near_ema200": 0, "insufficient_confirmations": 0, "regime_skip": 0, "htf_misalignment": 0}
    regime_counts = {"strong_trend": 0, "weak_trend": 0, "ranging": 0, "low_volatility": 0}
    
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
        
        if (ema_micro[i] is None or ema_fast[i] is None or 
            ema_medium[i] is None or ema_long[i] is None or 
            adx[i] is None or atr_ma[i] is None or
            i < p["ema_long"]):
            continue
        
        # Classify regime
        current_regime = classify_market_regime(adx[i], atr[i], atr_ma[i])
        regime_counts[current_regime] += 1
        
        # Get multipliers (includes consecutive loss adjustment)
        regime_mults = get_aggressive_regime_multipliers(current_regime, consecutive_losses)
        
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
                else:
                    consecutive_losses = 0
                
                position = None
        
        # Entry logic
        if position is None:
            # NEW: Skip trading entirely if regime says so
            if regime_mults.get("skip_trading", False):
                filtered_counts["regime_skip"] += 1
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
            
            distance_from_ema200 = abs(candle.close - ema_long[i]) / ema_long[i]
            
            if distance_from_ema200 < p["avoid_ema200_zone_pct"]:
                filtered_counts["near_ema200"] += 1
                continue
            
            if distance_from_ema200 < p["min_distance_from_ema200_pct"]:
                continue
            
            # NEW: Higher timeframe alignment check
            htf_bias = calculate_higher_timeframe_bias(candles, i, p["htf_lookback"])
            
            bullish_bias = candle.close > ema_long[i]
            bearish_bias = candle.close < ema_long[i]
            
            # Skip if HTF misaligned (optional but recommended)
            if p["require_htf_alignment"]:
                if bullish_bias and htf_bias == "bearish":
                    filtered_counts["htf_misalignment"] += 1
                    continue
                if bearish_bias and htf_bias == "bullish":
                    filtered_counts["htf_misalignment"] += 1
                    continue
            
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
                if current_regime == "strong_trend" and adx[i] > 30:
                    confirmations.append("strong_adx")
                if atr[i] > atr_ma[i] * 1.2:
                    confirmations.append("good_volatility")
                if htf_bias == "bullish":
                    confirmations.append("htf_aligned")
                
                total_score = len(signals) + len(confirmations)
                
                if p["require_confirmation"] and len(signals) >= 1 and total_score >= dynamic_min_confirmations:
                    # Only trade if risk_mult > 0
                    if regime_mults["risk_mult"] > 0:
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
                            "regime": current_regime,
                            "adx": adx[i],
                        }
                        trades_per_day[day_key] += 1
                        
                        for sig in signals:
                            signal_counts[sig] += 1
                        
                        logger.debug(f"LONG: {entry_price:.5f}, Regime: {current_regime}, ADX: {adx[i]:.1f}, "
                                   f"HTF: {htf_bias}, Signals: {len(signals)}, Confirmations: {len(confirmations)}")
                else:
                    filtered_counts["insufficient_confirmations"] += 1
            
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
                if current_regime == "strong_trend" and adx[i] > 30:
                    confirmations.append("strong_adx")
                if atr[i] > atr_ma[i] * 1.2:
                    confirmations.append("good_volatility")
                if htf_bias == "bearish":
                    confirmations.append("htf_aligned")
                
                total_score = len(signals) + len(confirmations)
                
                if p["require_confirmation"] and len(signals) >= 1 and total_score >= dynamic_min_confirmations:
                    if regime_mults["risk_mult"] > 0:
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
                            "regime": current_regime,
                            "adx": adx[i],
                        }
                        trades_per_day[day_key] += 1
                        
                        for sig in signals:
                            signal_counts[sig] += 1
                        
                        logger.debug(f"SHORT: {entry_price:.5f}, Regime: {current_regime}, ADX: {adx[i]:.1f}, "
                                   f"HTF: {htf_bias}, Signals: {len(signals)}, Confirmations: {len(confirmations)}")
                else:
                    filtered_counts["insufficient_confirmations"] += 1
    
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
    
    total_candles = sum(regime_counts.values())
    if total_candles > 0:
        logger.info(f"\nMarket Regime Distribution:")
        for regime, count in sorted(regime_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / total_candles * 100
            logger.info(f"  {regime}: {count} ({pct:.1f}%)")
    
    logger.info(f"\nAggressive adaptive complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
