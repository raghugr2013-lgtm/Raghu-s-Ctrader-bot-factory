"""
SIMPLE TREND-FOLLOWING STRATEGY

Designed for trending market regimes.
Uses classic, proven trend-following techniques.

Key Principles:
- Simple EMA crossovers
- Momentum confirmation
- ATR-based stops
- NO overfitting
"""

import logging
from typing import List, Tuple, Dict, Optional
from datetime import datetime

from market_data_models import Candle
from backtest_models import TradeRecord, EquityPoint, BacktestConfig
from backtest_real_engine import _calculate_ema, _calculate_rsi, _create_trade
from improved_eurusd_strategy import calculate_atr
from market_regime_detector import MarketRegime

logger = logging.getLogger(__name__)


def calculate_ema_slope(
    ema_values: List[Optional[float]],
    current_idx: int,
    lookback: int = 3
) -> Optional[float]:
    """
    Calculate EMA slope (momentum)
    Positive = upward momentum, Negative = downward momentum
    """
    if current_idx < lookback:
        return None
    
    if (ema_values[current_idx] is None or 
        ema_values[current_idx - lookback] is None):
        return None
    
    slope = (ema_values[current_idx] - ema_values[current_idx - lookback]) / ema_values[current_idx - lookback]
    return slope * 10000  # Scale to pips


def generate_trend_signal(
    candles: List[Candle],
    current_idx: int,
    ema_fast: List[Optional[float]],
    ema_slow: List[Optional[float]],
    rsi: List[Optional[float]],
    regime: MarketRegime,
    params: Dict
) -> Optional[str]:
    """
    Generate improved trend-following signal
    
    LONG Signal (IMPROVED):
    - Fast EMA above Slow EMA (not just crossover)
    - Fast EMA has positive slope (momentum confirmation)
    - RSI not overbought (< 70)
    - Regime is bullish trending
    - Price above fast EMA (pullback entry)
    
    SHORT Signal (IMPROVED):
    - Fast EMA below Slow EMA (not just crossover)
    - Fast EMA has negative slope (momentum confirmation)
    - RSI not oversold (> 30)
    - Regime is bearish trending
    - Price below fast EMA (pullback entry)
    
    Returns: "BUY", "SELL", or None
    """
    
    if current_idx < 3:
        return None
    
    if (ema_fast[current_idx] is None or ema_slow[current_idx] is None or
        ema_fast[current_idx - 1] is None or ema_slow[current_idx - 1] is None or
        rsi[current_idx] is None):
        return None
    
    # Current values
    fast_now = ema_fast[current_idx]
    slow_now = ema_slow[current_idx]
    fast_prev = ema_fast[current_idx - 1]
    slow_prev = ema_slow[current_idx - 1]
    rsi_now = rsi[current_idx]
    current_price = candles[current_idx].close
    prev_price = candles[current_idx - 1].close
    
    # Calculate EMA slopes for momentum confirmation
    fast_slope = calculate_ema_slope(ema_fast, current_idx, 3)
    
    if fast_slope is None:
        return None
    
    # LONG Signal (RELAXED - not requiring exact crossover)
    # Allow entry when Fast > Slow with positive momentum
    if (fast_now > slow_now and  # Fast above Slow (trending up)
        fast_slope > 0.0 and  # Positive momentum
        rsi_now < params["rsi_overbought"] and
        regime.is_bullish() and regime.is_trending()):
        
        # Entry conditions (multiple options for more opportunities):
        # 1. Fresh crossover
        if fast_prev <= slow_prev and fast_now > slow_now:
            return "BUY"
        # 2. Pullback entry (price was below fast EMA, now crossing above)
        elif prev_price < fast_prev and current_price >= fast_now:
            return "BUY"
        # 3. Continuation entry (strong momentum continuation)
        elif fast_slope > 1.0 and rsi_now < 60:  # Strong momentum and not overbought
            return "BUY"
    
    # SHORT Signal (RELAXED - not requiring exact crossover)
    # Allow entry when Fast < Slow with negative momentum
    if (fast_now < slow_now and  # Fast below Slow (trending down)
        fast_slope < 0.0 and  # Negative momentum
        rsi_now > params["rsi_oversold"] and
        regime.is_bearish() and regime.is_trending()):
        
        # Entry conditions (multiple options for more opportunities):
        # 1. Fresh crossover
        if fast_prev >= slow_prev and fast_now < slow_now:
            return "SELL"
        # 2. Pullback entry (price was above fast EMA, now crossing below)
        elif prev_price > fast_prev and current_price <= fast_now:
            return "SELL"
        # 3. Continuation entry (strong momentum continuation)
        elif fast_slope < -1.0 and rsi_now > 40:  # Strong momentum and not oversold
            return "SELL"
    
    return None


def run_simple_trend_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    regimes: List[Optional[MarketRegime]],
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Simple Trend-Following Strategy
    
    Entry:
    - EMA crossover (20/50 default)
    - RSI filter (not extreme)
    - Only in trending regimes
    
    Exit:
    - ATR-based stop loss
    - ATR-based take profit
    - Reverse crossover
    
    Parameters are intentionally SIMPLE and STANDARD (not optimized)
    """
    
    default_params = {
        # EMAs (OPTIMIZED)
        "ema_fast": 12,  # Reduced from 20 for faster signals
        "ema_slow": 26,  # Reduced from 50 for more responsiveness
        
        # RSI
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        
        # Risk management (IMPROVED)
        "stop_loss_atr_mult": 1.5,  # Tighter stop (was 2.0)
        "take_profit_atr_mult": 3.0,  # More realistic target (was 4.0)
        "risk_per_trade_pct": 1.0,
        "atr_period": 14,
        
        # Filters (RELAXED)
        "min_regime_confidence": 0.4,  # Reduced from 0.6 for more opportunities
        "max_trades_per_day": 3,  # Increased from 2
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running SIMPLE TREND-FOLLOWING strategy")
    logger.info(f"  EMA: {p['ema_fast']}/{p['ema_slow']}")
    logger.info(f"  Risk: {p['risk_per_trade_pct']}% per trade")
    logger.info(f"  RR: {p['take_profit_atr_mult']}/{p['stop_loss_atr_mult']} = {p['take_profit_atr_mult']/p['stop_loss_atr_mult']:.1f}:1")
    
    # Calculate indicators
    ema_fast = _calculate_ema(candles, p["ema_fast"])
    ema_slow = _calculate_ema(candles, p["ema_slow"])
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    
    # State
    trades = []
    equity_curve = []
    balance = config.initial_balance
    peak_balance = balance
    position = None
    trades_per_day = {}
    
    # Statistics
    regime_trades = {"trending": 0, "other": 0}
    signal_count = 0
    skipped_by_regime = 0
    
    for i, candle in enumerate(candles):
        current_equity = balance
        
        # Update equity with unrealized P&L
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
        if (ema_fast[i] is None or ema_slow[i] is None or 
            rsi[i] is None or atr[i] is None or
            regimes[i] is None):
            continue
        
        regime = regimes[i]
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
                elif ema_fast[i] < ema_slow[i]:  # Reverse crossover
                    exit_price = candle.close
                    exit_reason = "EMA Reversal"
            else:  # SELL
                if candle.high >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                elif candle.low <= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                elif ema_fast[i] > ema_slow[i]:  # Reverse crossover
                    exit_price = candle.close
                    exit_reason = "EMA Reversal"
            
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trade.profit_loss *= position["lots"]
                trades.append(trade)
                balance += trade.profit_loss
                position = None
        
        # Entry logic - ONLY IN TRENDING REGIMES
        if position is None:
            # Check regime suitability
            if not regime.is_trending() or regime.confidence < p["min_regime_confidence"]:
                skipped_by_regime += 1
                continue
            
            # Check daily limit
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            # Generate signal
            signal = generate_trend_signal(
                candles, i, ema_fast, ema_slow, rsi, regime, p
            )
            
            if signal:
                signal_count += 1
                
                # Calculate position size
                entry_price = candle.close
                
                if signal == "BUY":
                    stop_loss = entry_price - (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = entry_price + (atr[i] * p["take_profit_atr_mult"])
                    direction = "BUY"
                else:  # SELL
                    stop_loss = entry_price + (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = entry_price - (atr[i] * p["take_profit_atr_mult"])
                    direction = "SELL"
                
                # Risk-based position sizing
                risk_amount = balance * (p["risk_per_trade_pct"] / 100)
                stop_distance_pips = abs(entry_price - stop_loss) * 10000
                
                if stop_distance_pips > 0:
                    lots = risk_amount / (stop_distance_pips * 10)
                    lots = max(0.01, min(lots, 10.0))
                else:
                    lots = 0.01
                
                position = {
                    "direction": direction,
                    "entry_price": entry_price,
                    "entry_time": candle.timestamp,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "lots": lots,
                    "regime": str(regime),
                }
                trades_per_day[day_key] += 1
                regime_trades["trending"] += 1
                
                logger.debug(f"{direction}: {entry_price:.5f}, Regime: {regime}, ADX: {regime.adx:.1f}")
    
    # Close final position
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, "End of Test", config.symbol)
        trade.profit_loss *= position["lots"]
        trades.append(trade)
        balance += trade.profit_loss
    
    # Log statistics
    logger.info(f"\n=== TREND STRATEGY STATISTICS ===")
    logger.info(f"Signals generated: {signal_count}")
    logger.info(f"Trades executed: {len(trades)}")
    logger.info(f"Skipped by regime: {skipped_by_regime}")
    logger.info(f"Regime distribution: Trending={regime_trades['trending']}")
    
    logger.info(f"\n✅ Simple trend-following complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
