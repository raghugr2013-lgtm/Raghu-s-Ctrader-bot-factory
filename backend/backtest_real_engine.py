"""
Real Candle Backtest Engine
Runs backtests on actual market data instead of mock data.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Any

from market_data_models import Candle
from backtest_models import (
    TradeRecord, EquityPoint, BacktestConfig, Timeframe, TradeDirection, TradeStatus
)

logger = logging.getLogger(__name__)


def run_backtest_on_real_candles(
    candles: List[Candle],
    bot_name: str,
    symbol: str,
    timeframe: str,
    duration_days: int,
    initial_balance: float,
    strategy_type: str = "trend_following",
    from_date: datetime = None,  # NEW: Custom start date
    to_date: datetime = None,    # NEW: Custom end date
) -> Tuple[List[TradeRecord], List[EquityPoint], BacktestConfig]:
    """
    Run backtest using REAL candle data.
    
    This generates trades based on actual price movements,
    providing realistic performance metrics.
    
    Args:
        candles: List of real market candles
        bot_name: Strategy name
        symbol: Trading symbol
        timeframe: Candle timeframe
        duration_days: Backtest duration (used if from_date/to_date not provided)
        initial_balance: Starting balance
        strategy_type: Strategy type (trend_following, mean_reversion, breakout)
        from_date: Custom backtest start date (overrides duration_days)
        to_date: Custom backtest end date (defaults to last candle)
    
    Returns:
        Tuple of (trades, equity_curve, config)
    """
    if not candles:
        raise ValueError("No candles provided for backtest")
    
    logger.info(f"Running backtest on {len(candles)} real candles for {symbol} {timeframe}")
    
    # Sort candles by timestamp
    candles = sorted(candles, key=lambda c: c.timestamp)
    
    # Determine backtest period
    if to_date is None:
        end_date = candles[-1].timestamp
    else:
        end_date = to_date if isinstance(to_date, datetime) else datetime.fromisoformat(to_date)
    
    if from_date is None:
        # Use duration_days if no custom start date
        start_date = end_date - timedelta(days=duration_days)
    else:
        start_date = from_date if isinstance(from_date, datetime) else datetime.fromisoformat(from_date)
    
    # Filter candles to date range
    filtered_candles = [
        c for c in candles 
        if start_date <= c.timestamp <= end_date
    ]
    
    if len(filtered_candles) < 20:
        # Use all available candles if not enough for date range
        logger.warning(
            f"Only {len(filtered_candles)} candles in range {start_date} to {end_date}. "
            f"Using all {len(candles)} available candles."
        )
        filtered_candles = candles
        start_date = filtered_candles[0].timestamp
        end_date = filtered_candles[-1].timestamp
    
    logger.info(f"Using {len(filtered_candles)} candles from {start_date} to {end_date}")
    logger.info(f"Backtest period: {(end_date - start_date).days} days")
    
    # Create backtest config with proper timeframe handling
    try:
        config_timeframe = Timeframe(timeframe)
    except (ValueError, KeyError):
        logger.warning(f"Invalid timeframe '{timeframe}', defaulting to 1h")
        config_timeframe = Timeframe.H1
    
    config = BacktestConfig(
        symbol=symbol,
        timeframe=config_timeframe,
        start_date=start_date,
        end_date=end_date,
        initial_balance=initial_balance,
        spread_pips=1.5,
        commission_per_lot=7.0,
        leverage=100,
    )
    
    # Run strategy on real candles
    if strategy_type == "trend_following":
        trades, equity_curve = _run_trend_following(filtered_candles, config)
    elif strategy_type == "mean_reversion":
        trades, equity_curve = _run_mean_reversion(filtered_candles, config)
    elif strategy_type == "breakout":
        trades, equity_curve = _run_breakout(filtered_candles, config)
    else:
        trades, equity_curve = _run_trend_following(filtered_candles, config)
    
    return trades, equity_curve, config


def _calculate_ema(candles: List[Candle], period: int) -> List[float]:
    """Calculate EMA values for candles."""
    closes = [c.close for c in candles]
    ema = []
    multiplier = 2 / (period + 1)
    
    if len(closes) >= period:
        # Initial SMA
        sma = sum(closes[:period]) / period
        ema.append(sma)
        
        for i in range(period, len(closes)):
            val = (closes[i] - ema[-1]) * multiplier + ema[-1]
            ema.append(val)
    
    # Pad with None for initial periods
    return [None] * (len(candles) - len(ema)) + ema


def _calculate_rsi(candles: List[Candle], period: int = 14) -> List[float]:
    """Calculate RSI values."""
    closes = [c.close for c in candles]
    rsi = [50.0] * period  # Default for initial periods
    
    gains = []
    losses = []
    
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        gains.append(max(0, change))
        losses.append(max(0, -change))
    
    if len(gains) >= period:
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100 - (100 / (1 + rs)))
    
    return rsi + [50.0] * (len(candles) - len(rsi))


def _create_trade(
    position: Dict,
    exit_time: datetime,
    exit_price: float,
    exit_reason: str,
    symbol: str,
) -> TradeRecord:
    """Helper to create a properly formatted TradeRecord."""
    if position["direction"] == "BUY":
        pips = (exit_price - position["entry_price"]) * 10000
    else:
        pips = (position["entry_price"] - exit_price) * 10000
    
    pnl = pips * 10  # $10 per pip for 1 lot
    
    return TradeRecord(
        backtest_id="real_candle_backtest",
        entry_time=position["entry_time"],
        exit_time=exit_time,
        symbol=symbol,
        direction=TradeDirection.BUY if position["direction"] == "BUY" else TradeDirection.SELL,
        volume=1.0,
        position_size=10000.0,
        entry_price=position["entry_price"],
        exit_price=exit_price,
        profit_loss=pnl,
        profit_loss_pips=pips,
        stop_loss=position["stop_loss"],
        take_profit=position["take_profit"],
        status=TradeStatus.CLOSED,
        close_reason=exit_reason,
    )


def _run_trend_following(candles: List[Candle], config: BacktestConfig) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """EMA crossover strategy on real candles."""
    trades = []
    equity_curve = []
    balance = config.initial_balance
    position = None
    
    fast_ema = _calculate_ema(candles, 10)
    slow_ema = _calculate_ema(candles, 20)
    
    for i, candle in enumerate(candles):
        # Record equity
        equity_curve.append(EquityPoint(
            timestamp=candle.timestamp,
            balance=balance,
            equity=balance,
            drawdown=0.0,
            drawdown_percent=0.0,
        ))
        
        if fast_ema[i] is None or slow_ema[i] is None:
            continue
        
        # Entry signals
        if position is None:
            # Buy signal: fast EMA crosses above slow EMA
            if i > 0 and fast_ema[i-1] is not None and slow_ema[i-1] is not None:
                if fast_ema[i] > slow_ema[i] and fast_ema[i-1] <= slow_ema[i-1]:
                    position = {
                        "direction": "BUY",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": candle.close - (candle.high - candle.low) * 2,
                        "take_profit": candle.close + (candle.high - candle.low) * 3,
                    }
                # Sell signal: fast EMA crosses below slow EMA
                elif fast_ema[i] < slow_ema[i] and fast_ema[i-1] >= slow_ema[i-1]:
                    position = {
                        "direction": "SELL",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": candle.close + (candle.high - candle.low) * 2,
                        "take_profit": candle.close - (candle.high - candle.low) * 3,
                    }
        
        # Exit check
        elif position:
            exit_reason = None
            exit_price = None
            
            if position["direction"] == "BUY":
                if candle.low <= position["stop_loss"]:
                    exit_reason = "SL"
                    exit_price = position["stop_loss"]
                elif candle.high >= position["take_profit"]:
                    exit_reason = "TP"
                    exit_price = position["take_profit"]
                elif fast_ema[i] < slow_ema[i]:
                    exit_reason = "Signal"
                    exit_price = candle.close
            else:  # SELL
                if candle.high >= position["stop_loss"]:
                    exit_reason = "SL"
                    exit_price = position["stop_loss"]
                elif candle.low <= position["take_profit"]:
                    exit_reason = "TP"
                    exit_price = position["take_profit"]
                elif fast_ema[i] > slow_ema[i]:
                    exit_reason = "Signal"
                    exit_price = candle.close
            
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trades.append(trade)
                balance += trade.profit_loss
                position = None
    
    return trades, equity_curve


def _run_mean_reversion(candles: List[Candle], config: BacktestConfig) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """RSI mean reversion strategy on real candles."""
    trades = []
    equity_curve = []
    balance = config.initial_balance
    position = None
    
    rsi = _calculate_rsi(candles, 14)
    
    for i, candle in enumerate(candles):
        equity_curve.append(EquityPoint(
            timestamp=candle.timestamp,
            balance=balance,
            equity=balance,
            drawdown=0.0,
            drawdown_percent=0.0,
        ))
        
        if i < 14:
            continue
        
        # Entry signals
        if position is None:
            if rsi[i] < 30:  # Oversold - buy
                position = {
                    "direction": "BUY",
                    "entry_price": candle.close,
                    "entry_time": candle.timestamp,
                    "stop_loss": candle.close * 0.99,
                    "take_profit": candle.close * 1.02,
                }
            elif rsi[i] > 70:  # Overbought - sell
                position = {
                    "direction": "SELL",
                    "entry_price": candle.close,
                    "entry_time": candle.timestamp,
                    "stop_loss": candle.close * 1.01,
                    "take_profit": candle.close * 0.98,
                }
        
        # Exit check
        elif position:
            exit_reason = None
            exit_price = None
            
            if position["direction"] == "BUY":
                if candle.low <= position["stop_loss"]:
                    exit_reason = "SL"
                    exit_price = position["stop_loss"]
                elif candle.high >= position["take_profit"]:
                    exit_reason = "TP"
                    exit_price = position["take_profit"]
                elif rsi[i] > 50:
                    exit_reason = "Signal"
                    exit_price = candle.close
            else:
                if candle.high >= position["stop_loss"]:
                    exit_reason = "SL"
                    exit_price = position["stop_loss"]
                elif candle.low <= position["take_profit"]:
                    exit_reason = "TP"
                    exit_price = position["take_profit"]
                elif rsi[i] < 50:
                    exit_reason = "Signal"
                    exit_price = candle.close
            
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trades.append(trade)
                balance += trade.profit_loss
                position = None
    
    return trades, equity_curve


def _run_breakout(candles: List[Candle], config: BacktestConfig) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """Breakout strategy on real candles."""
    trades = []
    equity_curve = []
    balance = config.initial_balance
    position = None
    lookback = 20
    
    for i, candle in enumerate(candles):
        equity_curve.append(EquityPoint(
            timestamp=candle.timestamp,
            balance=balance,
            equity=balance,
            drawdown=0.0,
            drawdown_percent=0.0,
        ))
        
        if i < lookback:
            continue
        
        # Calculate range high/low
        range_high = max(c.high for c in candles[i-lookback:i])
        range_low = min(c.low for c in candles[i-lookback:i])
        
        # Entry signals
        if position is None:
            if candle.close > range_high:  # Breakout up
                position = {
                    "direction": "BUY",
                    "entry_price": candle.close,
                    "entry_time": candle.timestamp,
                    "stop_loss": range_low,
                    "take_profit": candle.close + (range_high - range_low),
                }
            elif candle.close < range_low:  # Breakout down
                position = {
                    "direction": "SELL",
                    "entry_price": candle.close,
                    "entry_time": candle.timestamp,
                    "stop_loss": range_high,
                    "take_profit": candle.close - (range_high - range_low),
                }
        
        # Exit check
        elif position:
            exit_reason = None
            exit_price = None
            
            if position["direction"] == "BUY":
                if candle.low <= position["stop_loss"]:
                    exit_reason = "SL"
                    exit_price = position["stop_loss"]
                elif candle.high >= position["take_profit"]:
                    exit_reason = "TP"
                    exit_price = position["take_profit"]
            else:
                if candle.high >= position["stop_loss"]:
                    exit_reason = "SL"
                    exit_price = position["stop_loss"]
                elif candle.low <= position["take_profit"]:
                    exit_reason = "TP"
                    exit_price = position["take_profit"]
            
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trades.append(trade)
                balance += trade.profit_loss
                position = None
    
    return trades, equity_curve
