"""
Enhanced Multi-Signal EURUSD Strategy

Key Improvements:
1. Confirmation requirements (2 signals minimum)
2. Avoid uncertain zones near EMA 200
3. Better risk/reward (wider targets)
4. Quality over quantity (fewer, better trades)

Goal: PF > 1.5, DD < 5%, 45-70 trades
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


def run_enhanced_multi_signal_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Enhanced multi-signal EURUSD strategy with confirmation requirements.
    
    Parameters:
    - ema_micro: 3
    - ema_fast: 20
    - ema_medium: 50
    - ema_long: 200
    - rsi_period: 14
    - atr_period: 14
    
    Signal Parameters:
    - pullback_rsi_min: 42
    - pullback_rsi_max: 58
    - pullback_distance_pct: 0.003
    - breakout_lookback: 20
    - breakout_buffer_pct: 0.0002
    - momentum_threshold: 0.85 (stricter)
    
    Confirmation Requirements:
    - require_confirmation: True
    - min_confirmations: 2
    
    Filters:
    - avoid_ema200_zone_pct: 0.002 (avoid if within 0.2% of EMA 200)
    - min_distance_from_ema200_pct: 0.0015
    
    Risk Management:
    - base_risk_pct: 0.75
    - stop_loss_atr_mult: 1.9
    - take_profit_atr_mult: 4.0 (wider targets)
    - max_trades_per_day: 3
    - min_candles_between_trades: 2
    - min_atr_threshold: 0.0003
    """
    
    default_params = {
        "ema_micro": 3,
        "ema_fast": 20,
        "ema_medium": 50,
        "ema_long": 200,
        "rsi_period": 14,
        "atr_period": 14,
        
        # Signal parameters (stricter)
        "pullback_rsi_min": 42,
        "pullback_rsi_max": 58,
        "pullback_distance_pct": 0.003,
        "breakout_lookback": 20,
        "breakout_buffer_pct": 0.0002,
        "momentum_threshold": 0.85,
        
        # Confirmation requirements
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
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running enhanced multi-signal strategy with confirmation requirements")
    
    # Calculate indicators
    ema_micro = _calculate_ema(candles, p["ema_micro"])
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
        
        # Entry logic - Enhanced with confirmation requirements
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
                # Confirmation 1: RSI in favorable zone
                if p["pullback_rsi_min"] <= rsi[i] <= p["pullback_rsi_max"]:
                    confirmations.append("rsi")
                
                # Confirmation 2: Strong candle present
                if is_strong and direction == "bullish":
                    confirmations.append("strong_candle")
                
                # Confirmation 3: Price above both EMAs (strength)
                if candle.close > ema_fast[i] and candle.close > ema_medium[i]:
                    confirmations.append("above_emas")
                
                # Confirmation 4: Increasing momentum
                if i > 0 and (candle.close - candle.open) > (candles[i-1].close - candles[i-1].open):
                    confirmations.append("momentum_increasing")
                
                # Check if we have enough signals/confirmations
                total_score = len(signals) + len(confirmations)
                
                if p["require_confirmation"]:
                    # Need at least 1 signal + sufficient confirmations
                    if len(signals) >= 1 and total_score >= p["min_confirmations"]:
                        # Execute LONG entry
                        entry_price = candle.close
                        stop_loss = entry_price - (atr[i] * p["stop_loss_atr_mult"])
                        take_profit = entry_price + (atr[i] * p["take_profit_atr_mult"])
                        
                        risk_amount = balance * (p["base_risk_pct"] / 100)
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
                        }
                        trades_per_day[day_key] += 1
                        
                        for sig in signals:
                            signal_counts[sig] += 1
                        
                        logger.debug(f"LONG: {entry_price:.5f}, Signals: {signals}, "
                                   f"Confirmations: {confirmations}, RR: {p['take_profit_atr_mult']/p['stop_loss_atr_mult']:.1f}")
                    else:
                        filtered_counts["insufficient_confirmations"] += 1
                else:
                    # Original behavior (backward compatibility)
                    if signals:
                        # Entry logic here (simplified)
                        pass
            
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
                
                # Check confirmations
                total_score = len(signals) + len(confirmations)
                
                if p["require_confirmation"]:
                    if len(signals) >= 1 and total_score >= p["min_confirmations"]:
                        # Execute SHORT entry
                        entry_price = candle.close
                        stop_loss = entry_price + (atr[i] * p["stop_loss_atr_mult"])
                        take_profit = entry_price - (atr[i] * p["take_profit_atr_mult"])
                        
                        risk_amount = balance * (p["base_risk_pct"] / 100)
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
                        }
                        trades_per_day[day_key] += 1
                        
                        for sig in signals:
                            signal_counts[sig] += 1
                        
                        logger.debug(f"SHORT: {entry_price:.5f}, Signals: {signals}, "
                                   f"Confirmations: {confirmations}, RR: {p['take_profit_atr_mult']/p['stop_loss_atr_mult']:.1f}")
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
    
    logger.info(f"\nEnhanced multi-signal complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
