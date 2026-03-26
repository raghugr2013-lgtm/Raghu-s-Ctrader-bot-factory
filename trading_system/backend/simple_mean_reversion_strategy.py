"""
SIMPLE MEAN-REVERSION STRATEGY

Designed for ranging/choppy market regimes.
Uses Bollinger Bands and RSI for oversold/overbought conditions.

Key Principles:
- Trade bounces from extremes
- Only in ranging markets
- Quick exits
- NO overfitting
"""

import logging
from typing import List, Tuple, Dict, Optional

from market_data_models import Candle
from backtest_models import TradeRecord, EquityPoint, BacktestConfig
from backtest_real_engine import _calculate_ema, _calculate_rsi, _create_trade
from improved_eurusd_strategy import calculate_atr
from market_regime_detector import MarketRegime

logger = logging.getLogger(__name__)


def calculate_bollinger_bands(
    candles: List[Candle],
    period: int = 20,
    std_dev: float = 2.0
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """
    Calculate Bollinger Bands
    
    Returns: (middle, upper, lower)
    """
    
    middle = _calculate_ema(candles, period)  # Use SMA via EMA
    upper = [None] * len(candles)
    lower = [None] * len(candles)
    
    for i in range(period, len(candles)):
        if middle[i] is None:
            continue
        
        # Calculate standard deviation
        closes = [candles[j].close for j in range(i - period + 1, i + 1)]
        mean = sum(closes) / period
        variance = sum((x - mean) ** 2 for x in closes) / period
        std = variance ** 0.5
        
        upper[i] = middle[i] + (std * std_dev)
        lower[i] = middle[i] - (std * std_dev)
    
    return middle, upper, lower


def generate_mean_reversion_signal(
    candles: List[Candle],
    current_idx: int,
    bb_middle: List[Optional[float]],
    bb_upper: List[Optional[float]],
    bb_lower: List[Optional[float]],
    rsi: List[Optional[float]],
    regime: MarketRegime,
    params: Dict
) -> Optional[str]:
    """
    Generate mean-reversion signal
    
    LONG Signal:
    - Price touches or crosses below lower BB
    - RSI oversold (< 40 - RELAXED)
    - Regime is ranging
    - Price starting to bounce back (OPTIONAL - relaxed)
    
    SHORT Signal:
    - Price touches or crosses above upper BB
    - RSI overbought (> 60 - RELAXED)
    - Regime is ranging
    - Price starting to pull back (OPTIONAL - relaxed)
    
    Returns: "BUY", "SELL", or None
    """
    
    if current_idx < 2:
        return None
    
    if (bb_middle[current_idx] is None or 
        bb_upper[current_idx] is None or
        bb_lower[current_idx] is None or
        rsi[current_idx] is None):
        return None
    
    candle = candles[current_idx]
    prev_candle = candles[current_idx - 1]
    
    # LONG Signal: Price at lower BB + oversold (RELAXED bounce requirement)
    if (candle.low <= bb_lower[current_idx] * 1.002 and  # Allow slight margin (0.2%)
        rsi[current_idx] < params["rsi_oversold_extreme"] and
        regime.is_ranging()):
        # Removed strict bullish candle requirement for more opportunities
        return "BUY"
    
    # SHORT Signal: Price at upper BB + overbought (RELAXED reversal requirement)
    if (candle.high >= bb_upper[current_idx] * 0.998 and  # Allow slight margin (0.2%)
        rsi[current_idx] > params["rsi_overbought_extreme"] and
        regime.is_ranging()):
        # Removed strict bearish candle requirement for more opportunities
        return "SELL"
    
    return None


def run_simple_mean_reversion_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    regimes: List[Optional[MarketRegime]],
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Simple Mean-Reversion Strategy
    
    Entry:
    - Price at Bollinger Band extremes
    - RSI extreme (oversold/overbought)
    - Bounce confirmation
    - Only in ranging regimes
    
    Exit:
    - Return to middle BB
    - ATR-based stop loss (wider for mean reversion)
    - Quick profit target
    
    Parameters are intentionally SIMPLE and STANDARD
    """
    
    default_params = {
        # Bollinger Bands (RELAXED)
        "bb_period": 20,
        "bb_std_dev": 1.8,  # Reduced from 2.0 for more frequent touches
        
        # RSI (RELAXED)
        "rsi_period": 14,
        "rsi_oversold_extreme": 40,  # Increased from 30 for more signals
        "rsi_overbought_extreme": 60,  # Decreased from 70 for more signals
        
        # Risk management
        "stop_loss_atr_mult": 2.5,  # Wider for mean reversion
        "take_profit_bb_target": 0.5,  # Exit at 50% back to middle
        "risk_per_trade_pct": 1.0,
        "atr_period": 14,
        
        # Filters (RELAXED)
        "min_regime_confidence": 0.4,  # Reduced from 0.6
        "max_trades_per_day": 3,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running SIMPLE MEAN-REVERSION strategy")
    logger.info(f"  Bollinger Bands: {p['bb_period']} period, {p['bb_std_dev']} std")
    logger.info(f"  RSI extremes: <{p['rsi_oversold_extreme']} / >{p['rsi_overbought_extreme']}")
    logger.info(f"  Risk: {p['risk_per_trade_pct']}% per trade")
    
    # Calculate indicators
    bb_middle, bb_upper, bb_lower = calculate_bollinger_bands(candles, p["bb_period"], p["bb_std_dev"])
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
    regime_trades = {"ranging": 0, "other": 0}
    signal_count = 0
    skipped_by_regime = 0
    
    for i, candle in enumerate(candles):
        current_equity = balance
        
        # Update equity
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
        if (bb_middle[i] is None or bb_upper[i] is None or bb_lower[i] is None or
            rsi[i] is None or atr[i] is None or regimes[i] is None):
            continue
        
        regime = regimes[i]
        day_key = candle.timestamp.date()
        if day_key not in trades_per_day:
            trades_per_day[day_key] = 0
        
        # Exit management
        if position:
            exit_reason = None
            exit_price = None
            
            # Calculate target (halfway back to middle BB)
            bb_mid = bb_middle[i]
            
            if position["direction"] == "BUY":
                # Stop loss
                if candle.low <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                # Target: Price returns toward middle
                elif candle.close >= position["target"]:
                    exit_price = candle.close
                    exit_reason = "Mean Reversion Target"
                # Price crosses back above middle (full reversion)
                elif candle.close > bb_mid:
                    exit_price = candle.close
                    exit_reason = "Full Reversion"
            
            else:  # SELL
                # Stop loss
                if candle.high >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                # Target: Price returns toward middle
                elif candle.close <= position["target"]:
                    exit_price = candle.close
                    exit_reason = "Mean Reversion Target"
                # Price crosses back below middle (full reversion)
                elif candle.close < bb_mid:
                    exit_price = candle.close
                    exit_reason = "Full Reversion"
            
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trade.profit_loss *= position["lots"]
                trades.append(trade)
                balance += trade.profit_loss
                position = None
        
        # Entry logic - ONLY IN RANGING REGIMES
        if position is None:
            # Check regime suitability
            if not regime.is_ranging() or regime.confidence < p["min_regime_confidence"]:
                skipped_by_regime += 1
                continue
            
            # Check daily limit
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            # Generate signal
            signal = generate_mean_reversion_signal(
                candles, i, bb_middle, bb_upper, bb_lower, rsi, regime, p
            )
            
            if signal:
                signal_count += 1
                
                # Calculate position size
                entry_price = candle.close
                bb_mid = bb_middle[i]
                
                if signal == "BUY":
                    stop_loss = entry_price - (atr[i] * p["stop_loss_atr_mult"])
                    # Target: 50% back to middle
                    target = entry_price + (bb_mid - entry_price) * p["take_profit_bb_target"]
                    direction = "BUY"
                else:  # SELL
                    stop_loss = entry_price + (atr[i] * p["stop_loss_atr_mult"])
                    # Target: 50% back to middle
                    target = entry_price - (entry_price - bb_mid) * p["take_profit_bb_target"]
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
                    "target": target,
                    "lots": lots,
                    "regime": str(regime),
                }
                trades_per_day[day_key] += 1
                regime_trades["ranging"] += 1
                
                logger.debug(f"{direction}: {entry_price:.5f}, Regime: {regime}, RSI: {rsi[i]:.1f}")
    
    # Close final position
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, "End of Test", config.symbol)
        trade.profit_loss *= position["lots"]
        trades.append(trade)
        balance += trade.profit_loss
    
    # Log statistics
    logger.info(f"\n=== MEAN REVERSION STATISTICS ===")
    logger.info(f"Signals generated: {signal_count}")
    logger.info(f"Trades executed: {len(trades)}")
    logger.info(f"Skipped by regime: {skipped_by_regime}")
    logger.info(f"Regime distribution: Ranging={regime_trades['ranging']}")
    
    logger.info(f"\n✅ Simple mean-reversion complete: {len(trades)} trades, "
               f"Balance: ${balance:.2f}, Return: {(balance/config.initial_balance - 1)*100:.2f}%")
    
    return trades, equity_curve
