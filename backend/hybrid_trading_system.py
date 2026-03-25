"""
HYBRID TRADING SYSTEM

Intelligently switches between:
- Trend-Following Strategy (for trending markets)
- Mean-Reversion Strategy (for ranging markets)

Based on real-time market regime detection
"""

import logging
from typing import List, Tuple, Dict, Optional
from datetime import datetime

from market_data_models import Candle
from backtest_models import TradeRecord, EquityPoint, BacktestConfig
from backtest_real_engine import _calculate_ema, _calculate_rsi, _create_trade
from improved_eurusd_strategy import calculate_atr, get_trading_session, TradingSession
from regime_detector import RegimeDetector, MarketRegime
from no_trade_zone_strategy import calculate_adx, calculate_choppiness_index, calculate_bollinger_bands
from adaptive_multi_signal import (
    calculate_recent_high_low, is_strong_candle
)

logger = logging.getLogger(__name__)


def run_hybrid_trading_system(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Hybrid Trading System
    
    Dynamically switches between strategies based on market regime:
    - TRENDING → Trend-following (adaptive multi-signal)
    - RANGING → Mean-reversion (Bollinger Bands + RSI)
    - UNCERTAIN → Reduced exposure or skip
    
    NEW PARAMETERS:
    - enable_trend_following: True
    - enable_mean_reversion: True
    - uncertain_regime_behavior: "reduce_size" or "skip"
    - uncertain_risk_mult: 0.4 (reduce size in uncertain conditions)
    """
    
    default_params = {
        # Strategy enablement
        "enable_trend_following": True,
        "enable_mean_reversion": True,
        "uncertain_regime_behavior": "reduce_size",  # or "skip"
        "uncertain_risk_mult": 0.4,
        
        # Trend-following parameters (from adaptive_multi_signal)
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
        "base_risk_pct_trend": 0.7,
        "stop_loss_atr_mult": 1.9,
        "take_profit_atr_mult": 4.0,
        
        # Mean-reversion parameters
        "bb_period": 20,
        "bb_std_dev": 2.0,
        "rsi_oversold": 35,
        "rsi_overbought": 65,
        "base_risk_pct_range": 0.5,
        "mr_stop_loss_atr_mult": 2.5,
        "target_middle_bb": True,
        
        # General
        "max_trades_per_day": 3,
        "min_candles_between_trades": 2,
        "atr_lookback": 20,
        
        # Regime detection
        "adx_period": 14,
        "adx_trending_threshold": 25,
        "adx_ranging_threshold": 18,
        "chop_trending_threshold": 50,
        "chop_ranging_threshold": 61.8,
        "atr_low_threshold": 0.7,
        "regime_confirmation_candles": 5,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running HYBRID TRADING SYSTEM (Trend + Mean-Reversion)")
    
    # Calculate indicators
    ema_micro = _calculate_ema(candles, p["ema_micro"])
    ema_fast = _calculate_ema(candles, p["ema_fast"])
    ema_medium = _calculate_ema(candles, p["ema_medium"])
    ema_long = _calculate_ema(candles, p["ema_long"])
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    adx = calculate_adx(candles, p["adx_period"])
    choppiness = calculate_choppiness_index(candles, 14)
    bb_middle, bb_upper, bb_lower, _ = calculate_bollinger_bands(candles, p["bb_period"], p["bb_std_dev"])
    
    # ATR MA
    atr_ma = [None] * len(candles)
    for i in range(p["atr_lookback"], len(candles)):
        if all(atr[j] is not None for j in range(i - p["atr_lookback"], i)):
            atr_ma[i] = sum(atr[i - p["atr_lookback"]:i]) / p["atr_lookback"]
    
    # Initialize regime detector
    regime_detector = RegimeDetector({
        "adx_trending_threshold": p["adx_trending_threshold"],
        "adx_ranging_threshold": p["adx_ranging_threshold"],
        "chop_trending_threshold": p["chop_trending_threshold"],
        "chop_ranging_threshold": p["chop_ranging_threshold"],
        "atr_low_threshold": p["atr_low_threshold"],
        "regime_confirmation_candles": p["regime_confirmation_candles"],
    })
    
    # State
    trades = []
    equity_curve = []
    balance = config.initial_balance
    peak_balance = balance
    position = None
    trades_per_day = {}
    last_exit_index = -100
    
    # Statistics
    regime_trade_counts = {
        MarketRegime.TRENDING: 0,
        MarketRegime.RANGING: 0,
        MarketRegime.UNCERTAIN: 0,
    }
    strategy_trade_counts = {
        "trend_following": 0,
        "mean_reversion": 0,
    }
    
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
            bb_middle[i] is None or
            i < p["ema_long"]):
            continue
        
        # Update market regime
        current_regime = regime_detector.update_regime(adx[i], atr[i], atr_ma[i], choppiness[i])
        
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
                # Check stop loss
                if candle.low <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                # Check take profit
                elif candle.high >= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                # Strategy-specific exits
                elif position.get("strategy") == "trend_following":
                    # Trend reversal exit
                    if candle.close < ema_long[i] - (atr[i] * 0.5):
                        exit_price = candle.close
                        exit_reason = "Trend Reversal"
                elif position.get("strategy") == "mean_reversion":
                    # Mean reversion target
                    if p["target_middle_bb"] and candle.high >= bb_middle[i]:
                        exit_price = bb_middle[i]
                        exit_reason = "Target (Middle BB)"
            
            else:  # SELL
                if candle.high >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                elif candle.low <= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                elif position.get("strategy") == "trend_following":
                    if candle.close > ema_long[i] + (atr[i] * 0.5):
                        exit_price = candle.close
                        exit_reason = "Trend Reversal"
                elif position.get("strategy") == "mean_reversion":
                    if p["target_middle_bb"] and candle.low <= bb_middle[i]:
                        exit_price = bb_middle[i]
                        exit_reason = "Target (Middle BB)"
            
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trade.profit_loss *= position["lots"]
                trades.append(trade)
                balance += trade.profit_loss
                last_exit_index = i
                position = None
        
        # Entry logic - REGIME-BASED STRATEGY SELECTION
        if position is None:
            # Basic filters
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            if session not in [TradingSession.LONDON, TradingSession.OVERLAP, TradingSession.NY]:
                continue
            
            if i - last_exit_index < p["min_candles_between_trades"]:
                continue
            
            # ================================================================
            # TRENDING REGIME → Trend-Following Strategy
            # ================================================================
            if current_regime == MarketRegime.TRENDING and p["enable_trend_following"]:
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
                
                # Get regime multipliers for adaptive risk
                if adx[i] >= 25 and atr[i] > atr_ma[i] * 1.1:
                    regime_mults = {
                        "risk_mult": 1.0,
                        "min_conf_add": 0,
                        "sl_mult": 1.0,
                        "tp_mult": 1.0,
                    }
                elif adx[i] >= 20:
                    regime_mults = {
                        "risk_mult": 0.8,
                        "min_conf_add": 1,
                        "sl_mult": 0.95,
                        "tp_mult": 1.0,
                    }
                else:
                    regime_mults = {
                        "risk_mult": 0.6,
                        "min_conf_add": 1,
                        "sl_mult": 0.9,
                        "tp_mult": 0.95,
                    }
                
                dynamic_min_confirmations = p["min_confirmations"] + regime_mults["min_conf_add"]
                
                # LONG signals
                if bullish_bias:
                    # Pullback signal
                    near_ema20 = abs(candle.close - ema_fast[i]) / ema_fast[i] < p["pullback_distance_pct"]
                    near_ema50 = abs(candle.close - ema_medium[i]) / ema_medium[i] < p["pullback_distance_pct"]
                    if (near_ema20 or near_ema50) and candle.close > candle.open:
                        signals.append("pullback")
                    
                    # Breakout signal
                    if i >= p["breakout_lookback"]:
                        recent_high, _ = calculate_recent_high_low(candles, i, p["breakout_lookback"])
                        if candle.close > recent_high * (1 + p["breakout_buffer_pct"]) and candle.close > candle.open:
                            signals.append("breakout")
                    
                    # Momentum signal
                    is_strong, direction = is_strong_candle(candle, atr[i], p["momentum_threshold"])
                    if is_strong and direction == "bullish":
                        signals.append("momentum")
                    
                    # Confirmations
                    if p["pullback_rsi_min"] <= rsi[i] <= p["pullback_rsi_max"]:
                        confirmations.append("rsi")
                    if candle.close > ema_fast[i] and candle.close > ema_medium[i]:
                        confirmations.append("above_emas")
                    if adx[i] > 25:
                        confirmations.append("strong_adx")
                    
                    total_score = len(signals) + len(confirmations)
                    
                    if p["require_confirmation"] and len(signals) >= 1 and total_score >= dynamic_min_confirmations:
                        entry_price = candle.close
                        stop_loss = entry_price - (atr[i] * p["stop_loss_atr_mult"] * regime_mults["sl_mult"])
                        take_profit = entry_price + (atr[i] * p["take_profit_atr_mult"] * regime_mults["tp_mult"])
                        
                        risk_pct = p["base_risk_pct_trend"] * regime_mults["risk_mult"]
                        risk_amount = balance * (risk_pct / 100)
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
                            "strategy": "trend_following",
                            "regime": current_regime,
                        }
                        trades_per_day[day_key] += 1
                        regime_trade_counts[current_regime] += 1
                        strategy_trade_counts["trend_following"] += 1
                        
                        logger.debug(f"TREND LONG: {entry_price:.5f}, ADX: {adx[i]:.1f}, Signals: {signals}")
                
                # SHORT signals (similar logic)
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
                    
                    if p["pullback_rsi_min"] <= rsi[i] <= p["pullback_rsi_max"]:
                        confirmations.append("rsi")
                    if candle.close < ema_fast[i] and candle.close < ema_medium[i]:
                        confirmations.append("below_emas")
                    if adx[i] > 25:
                        confirmations.append("strong_adx")
                    
                    total_score = len(signals) + len(confirmations)
                    
                    if p["require_confirmation"] and len(signals) >= 1 and total_score >= dynamic_min_confirmations:
                        entry_price = candle.close
                        stop_loss = entry_price + (atr[i] * p["stop_loss_atr_mult"] * regime_mults["sl_mult"])
                        take_profit = entry_price - (atr[i] * p["take_profit_atr_mult"] * regime_mults["tp_mult"])
                        
                        risk_pct = p["base_risk_pct_trend"] * regime_mults["risk_mult"]
                        risk_amount = balance * (risk_pct / 100)
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
                            "strategy": "trend_following",
                            "regime": current_regime,
                        }
                        trades_per_day[day_key] += 1
                        regime_trade_counts[current_regime] += 1
                        strategy_trade_counts["trend_following"] += 1
                        
                        logger.debug(f"TREND SHORT: {entry_price:.5f}, ADX: {adx[i]:.1f}, Signals: {signals}")
            
            # ================================================================
            # RANGING REGIME → Mean-Reversion Strategy
            # ================================================================
            elif current_regime == MarketRegime.RANGING and p["enable_mean_reversion"]:
                # LONG: Price at lower BB + RSI oversold
                lower_bb_penetration = (bb_lower[i] - candle.low) / bb_lower[i]
                
                if lower_bb_penetration >= -0.0003 and rsi[i] < p["rsi_oversold"]:
                    entry_price = candle.close
                    stop_loss = entry_price - (atr[i] * p["mr_stop_loss_atr_mult"])
                    take_profit = bb_middle[i] if p["target_middle_bb"] else entry_price + (atr[i] * 2.0)
                    
                    risk_amount = balance * (p["base_risk_pct_range"] / 100)
                    stop_distance_pips = (entry_price - stop_loss) * 10000
                    
                    if stop_distance_pips > 0:
                        lots = risk_amount / (stop_distance_pips * 10)
                        lots = max(0.01, min(lots, 5.0))
                    else:
                        lots = 0.01
                    
                    position = {
                        "direction": "BUY",
                        "entry_price": entry_price,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "lots": lots,
                        "strategy": "mean_reversion",
                        "regime": current_regime,
                    }
                    trades_per_day[day_key] += 1
                    regime_trade_counts[current_regime] += 1
                    strategy_trade_counts["mean_reversion"] += 1
                    
                    logger.debug(f"MR LONG: {entry_price:.5f}, RSI: {rsi[i]:.1f}, BB Lower: {bb_lower[i]:.5f}")
                
                # SHORT: Price at upper BB + RSI overbought
                upper_bb_penetration = (candle.high - bb_upper[i]) / bb_upper[i]
                
                if upper_bb_penetration >= -0.0003 and rsi[i] > p["rsi_overbought"]:
                    entry_price = candle.close
                    stop_loss = entry_price + (atr[i] * p["mr_stop_loss_atr_mult"])
                    take_profit = bb_middle[i] if p["target_middle_bb"] else entry_price - (atr[i] * 2.0)
                    
                    risk_amount = balance * (p["base_risk_pct_range"] / 100)
                    stop_distance_pips = (stop_loss - entry_price) * 10000
                    
                    if stop_distance_pips > 0:
                        lots = risk_amount / (stop_distance_pips * 10)
                        lots = max(0.01, min(lots, 5.0))
                    else:
                        lots = 0.01
                    
                    position = {
                        "direction": "SELL",
                        "entry_price": entry_price,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "lots": lots,
                        "strategy": "mean_reversion",
                        "regime": current_regime,
                    }
                    trades_per_day[day_key] += 1
                    regime_trade_counts[current_regime] += 1
                    strategy_trade_counts["mean_reversion"] += 1
                    
                    logger.debug(f"MR SHORT: {entry_price:.5f}, RSI: {rsi[i]:.1f}, BB Upper: {bb_upper[i]:.5f}")
            
            # ================================================================
            # UNCERTAIN REGIME → Reduced exposure or skip
            # ================================================================
            elif current_regime == MarketRegime.UNCERTAIN:
                if p["uncertain_regime_behavior"] == "skip":
                    continue  # Skip trading
                # If "reduce_size", could implement reduced risk logic here
                # For now, just skip for simplicity
                continue
    
    # Close final position
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, "End of Test", config.symbol)
        trade.profit_loss *= position["lots"]
        trades.append(trade)
        balance += trade.profit_loss
    
    # Log statistics
    logger.info(f"\n=== HYBRID SYSTEM STATISTICS ===")
    logger.info(f"\nTrades by Regime:")
    for regime, count in regime_trade_counts.items():
        if count > 0:
            logger.info(f"  {regime.value}: {count} trades")
    
    logger.info(f"\nTrades by Strategy:")
    for strategy, count in strategy_trade_counts.items():
        if count > 0:
            logger.info(f"  {strategy}: {count} trades")
    
    logger.info(f"\nHybrid system complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
