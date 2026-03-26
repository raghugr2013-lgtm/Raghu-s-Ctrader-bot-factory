"""
Real Candle Backtest Engine
Runs backtests on actual market data instead of mock data.

Supports:
- Multiple data sources: API (existing) and Dukascopy (new)
- Multi-symbol: EURUSD, XAUUSD, US100, ETHUSD
- Symbol-specific pip/lot calculations
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Any, Optional
from enum import Enum

from market_data_models import Candle
from backtest_models import (
    TradeRecord, EquityPoint, BacktestConfig, Timeframe, TradeDirection, TradeStatus
)
from config.symbol_config import get_symbol_config, SymbolConfig, calculate_pips, calculate_pip_value

logger = logging.getLogger(__name__)


class DataSource(str, Enum):
    """Data source for backtesting"""
    API = "api"
    DUKASCOPY = "dukascopy"


def get_symbol_pip_multiplier(symbol: str) -> float:
    """Get pip multiplier for PnL calculation based on symbol"""
    config = get_symbol_config(symbol)
    if config:
        # For forex (EURUSD): pip_value = 0.0001, multiplier = 10000
        # For metals (XAUUSD): pip_value = 0.01, multiplier = 100
        # For index (US100): pip_value = 1, multiplier = 1
        # For crypto (ETHUSD): pip_value = 0.1, multiplier = 10
        return 1.0 / config.pip_value
    return 10000.0  # Default forex


def get_pip_value_per_lot(symbol: str) -> float:
    """Get dollar value per pip per lot"""
    config = get_symbol_config(symbol)
    if config:
        return config.value_per_pip_per_lot
    return 10.0  # Default forex


def run_backtest_on_real_candles(
    candles: List[Candle],
    bot_name: str,
    symbol: str,
    timeframe: str,
    duration_days: int,
    initial_balance: float,
    strategy_type: str = "trend_following",
) -> Tuple[List[TradeRecord], List[EquityPoint], BacktestConfig]:
    """
    Run backtest using REAL candle data.
    
    This generates trades based on actual price movements,
    providing realistic performance metrics.
    """
    if not candles:
        raise ValueError("No candles provided for backtest")
    
    logger.info(f"Running backtest on {len(candles)} real candles for {symbol} {timeframe}")
    
    # Sort candles by timestamp
    candles = sorted(candles, key=lambda c: c.timestamp)
    
    # Determine backtest period
    end_date = candles[-1].timestamp
    start_date = end_date - timedelta(days=duration_days)
    
    # Filter candles to duration
    filtered_candles = [c for c in candles if c.timestamp >= start_date]
    if len(filtered_candles) < 20:
        # Use all available candles if not enough for duration
        filtered_candles = candles
        start_date = filtered_candles[0].timestamp
    
    logger.info(f"Using {len(filtered_candles)} candles from {start_date} to {end_date}")
    
    # Create backtest config
    config = BacktestConfig(
        symbol=symbol,
        timeframe=Timeframe(timeframe) if timeframe in ["1h", "4h", "1d", "15m", "30m"] else Timeframe.H1,
        start_date=start_date if isinstance(start_date, datetime) else datetime.now(timezone.utc) - timedelta(days=duration_days),
        end_date=end_date if isinstance(end_date, datetime) else datetime.now(timezone.utc),
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
    """Helper to create a properly formatted TradeRecord with symbol-specific pip calculations."""
    # Use symbol-specific pip multiplier
    pip_multiplier = get_symbol_pip_multiplier(symbol)
    pip_value_per_lot = get_pip_value_per_lot(symbol)
    
    if position["direction"] == "BUY":
        pips = (exit_price - position["entry_price"]) * pip_multiplier
    else:
        pips = (position["entry_price"] - exit_price) * pip_multiplier
    
    pnl = pips * pip_value_per_lot  # Symbol-specific pip value
    
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



# =============================================================================
# PRO VALIDATION SUPPORT - Dukascopy Integration
# =============================================================================

async def run_backtest_with_dukascopy(
    symbol: str,
    timeframe: str,
    duration_days: int = 90,
    initial_balance: float = 10000.0,
    strategy_type: str = "trend_following",
    bot_name: str = "ProValidation"
) -> Tuple[List[TradeRecord], List[EquityPoint], BacktestConfig]:
    """
    Run backtest using Dukascopy historical data (PRO validation mode)
    
    Args:
        symbol: Trading symbol (EURUSD, XAUUSD, US100, ETHUSD)
        timeframe: Candle timeframe (M1, M15, H1, etc.)
        duration_days: Number of days to backtest (default 90)
        initial_balance: Starting balance
        strategy_type: Strategy to simulate
        bot_name: Name of the bot being validated
    
    Returns:
        Tuple of (trades, equity_curve, config)
    """
    from market_data.dukascopy_provider import get_dukascopy_provider, DukascopyCandle
    
    logger.info(f"Running PRO backtest with Dukascopy data: {symbol} {timeframe} {duration_days} days")
    
    # Get Dukascopy provider
    provider = get_dukascopy_provider()
    
    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=duration_days)
    
    # Get OHLC data from Dukascopy
    dukascopy_candles = await provider.get_ohlc(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    if not dukascopy_candles:
        raise ValueError(f"No Dukascopy data available for {symbol} {timeframe}")
    
    logger.info(f"Loaded {len(dukascopy_candles)} candles from Dukascopy")
    
    # Convert DukascopyCandle to Candle format
    candles = [
        Candle(
            timestamp=c.timestamp,
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume
        )
        for c in dukascopy_candles
    ]
    
    # Run backtest on the candles
    return run_backtest_on_real_candles(
        candles=candles,
        bot_name=bot_name,
        symbol=symbol,
        timeframe=timeframe,
        duration_days=duration_days,
        initial_balance=initial_balance,
        strategy_type=strategy_type
    )


async def run_unified_backtest(
    symbol: str,
    timeframe: str,
    data_source: str = "api",
    duration_days: int = 90,
    initial_balance: float = 10000.0,
    strategy_type: str = "trend_following",
    bot_name: str = "UnifiedBacktest",
    candles: Optional[List[Candle]] = None
) -> Tuple[List[TradeRecord], List[EquityPoint], BacktestConfig]:
    """
    Unified backtest function supporting multiple data sources
    
    Args:
        symbol: Trading symbol
        timeframe: Candle timeframe
        data_source: "api" (existing) or "dukascopy" (PRO)
        duration_days: Days to backtest
        initial_balance: Starting balance
        strategy_type: Strategy type
        bot_name: Bot name
        candles: Pre-loaded candles (for API source)
    
    Returns:
        Tuple of (trades, equity_curve, config)
    """
    if data_source == DataSource.DUKASCOPY or data_source == "dukascopy":
        # Use Dukascopy data
        return await run_backtest_with_dukascopy(
            symbol=symbol,
            timeframe=timeframe,
            duration_days=duration_days,
            initial_balance=initial_balance,
            strategy_type=strategy_type,
            bot_name=bot_name
        )
    else:
        # Use existing API data (requires candles to be provided)
        if not candles:
            raise ValueError("Candles must be provided for API data source")
        
        return run_backtest_on_real_candles(
            candles=candles,
            bot_name=bot_name,
            symbol=symbol,
            timeframe=timeframe,
            duration_days=duration_days,
            initial_balance=initial_balance,
            strategy_type=strategy_type
        )


def get_symbol_adjusted_spread(symbol: str) -> float:
    """Get spread in pips for symbol"""
    config = get_symbol_config(symbol)
    if config:
        return config.spread
    return 1.5  # Default


def get_symbol_adjusted_sl_tp(symbol: str, atr: float = 0.0) -> Tuple[float, float]:
    """
    Get recommended SL/TP distances for symbol
    
    Returns:
        Tuple of (stop_loss_pips, take_profit_pips)
    """
    config = get_symbol_config(symbol)
    if config:
        sl = config.default_stop_loss_pips
        tp = config.default_take_profit_pips
        
        # Adjust for volatility if ATR provided
        if atr > 0:
            volatility_factor = 1.0 + (atr * 0.1)
            sl *= volatility_factor
            tp *= volatility_factor
        
        return sl, tp
    
    return 50.0, 100.0  # Defaults
