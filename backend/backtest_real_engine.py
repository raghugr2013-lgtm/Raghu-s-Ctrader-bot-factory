"""
Real Candle Backtest Engine
Runs backtests on actual market data instead of mock data.
Supports parameterized strategies for unique results.
"""

import logging
import random
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Any, Optional

from market_data_models import Candle
from backtest_models import (
    TradeRecord, EquityPoint, BacktestConfig, Timeframe, TradeDirection, TradeStatus
)

logger = logging.getLogger(__name__)


class StrategyParameters:
    """
    Parameterized strategy settings for unique backtests.
    Each parameter variation produces different trade results.
    """
    def __init__(
        self,
        # Trend indicators
        fast_ema: int = 10,
        slow_ema: int = 20,
        # RSI settings
        rsi_period: int = 14,
        rsi_oversold: int = 30,
        rsi_overbought: int = 70,
        # Breakout settings
        breakout_lookback: int = 20,
        # Risk parameters
        stop_loss_mult: float = 2.0,
        take_profit_mult: float = 3.0,
        # Trade timing
        max_trades_per_day: int = 5,
        min_candles_between_trades: int = 3,
        # Filter thresholds
        min_volatility: float = 0.001,
        # Strategy type (0=trend, 1=mean_rev, 2=breakout, 3=hybrid)
        strategy_variant: int = 0,
        # Seed for reproducibility
        seed: int = 42
    ):
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.breakout_lookback = breakout_lookback
        self.stop_loss_mult = stop_loss_mult
        self.take_profit_mult = take_profit_mult
        self.max_trades_per_day = max_trades_per_day
        self.min_candles_between_trades = min_candles_between_trades
        self.min_volatility = min_volatility
        self.strategy_variant = strategy_variant
        self.seed = seed
    
    @classmethod
    def generate_random(cls, strategy_type: str, risk_level: str, seed: int = None) -> 'StrategyParameters':
        """Generate random but realistic strategy parameters."""
        if seed is None:
            seed = random.randint(1, 999999)
        
        rng = random.Random(seed)
        
        # Base parameters by strategy type
        if strategy_type == "scalping":
            params = {
                "fast_ema": rng.randint(3, 8),
                "slow_ema": rng.randint(10, 20),
                "rsi_period": rng.randint(7, 14),
                "rsi_oversold": rng.randint(20, 35),
                "rsi_overbought": rng.randint(65, 80),
                "breakout_lookback": rng.randint(5, 15),
                "stop_loss_mult": rng.uniform(1.0, 2.0),
                "take_profit_mult": rng.uniform(1.5, 3.0),
                "max_trades_per_day": rng.randint(5, 15),
                "min_candles_between_trades": rng.randint(1, 3),
                "min_volatility": rng.uniform(0.0005, 0.002),
                "strategy_variant": rng.randint(0, 3),
            }
        elif strategy_type == "swing":
            params = {
                "fast_ema": rng.randint(15, 30),
                "slow_ema": rng.randint(40, 100),
                "rsi_period": rng.randint(14, 21),
                "rsi_oversold": rng.randint(25, 40),
                "rsi_overbought": rng.randint(60, 75),
                "breakout_lookback": rng.randint(30, 60),
                "stop_loss_mult": rng.uniform(2.0, 4.0),
                "take_profit_mult": rng.uniform(3.0, 6.0),
                "max_trades_per_day": rng.randint(1, 3),
                "min_candles_between_trades": rng.randint(10, 30),
                "min_volatility": rng.uniform(0.002, 0.005),
                "strategy_variant": rng.randint(0, 3),
            }
        else:  # intraday (default)
            params = {
                "fast_ema": rng.randint(8, 15),
                "slow_ema": rng.randint(20, 50),
                "rsi_period": rng.randint(10, 18),
                "rsi_oversold": rng.randint(25, 35),
                "rsi_overbought": rng.randint(65, 75),
                "breakout_lookback": rng.randint(15, 30),
                "stop_loss_mult": rng.uniform(1.5, 3.0),
                "take_profit_mult": rng.uniform(2.0, 4.0),
                "max_trades_per_day": rng.randint(2, 8),
                "min_candles_between_trades": rng.randint(3, 10),
                "min_volatility": rng.uniform(0.001, 0.003),
                "strategy_variant": rng.randint(0, 3),
            }
        
        # Adjust by risk level
        if risk_level == "low":
            params["stop_loss_mult"] *= 0.8
            params["take_profit_mult"] *= 0.7
            params["max_trades_per_day"] = max(1, params["max_trades_per_day"] - 2)
        elif risk_level == "high":
            params["stop_loss_mult"] *= 1.3
            params["take_profit_mult"] *= 1.4
            params["max_trades_per_day"] = min(20, params["max_trades_per_day"] + 3)
        
        params["seed"] = seed
        return cls(**params)


def run_backtest_on_real_candles(
    candles: List[Candle],
    bot_name: str,
    symbol: str,
    timeframe: str,
    duration_days: int,
    initial_balance: float,
    strategy_type: str = "trend_following",
    params: Optional[StrategyParameters] = None,
) -> Tuple[List[TradeRecord], List[EquityPoint], BacktestConfig]:
    """
    Run backtest using REAL candle data with parameterized strategy.
    
    This generates trades based on actual price movements,
    providing realistic and UNIQUE performance metrics for each strategy.
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
        timeframe=Timeframe(timeframe) if timeframe in ["1h", "4h", "1d", "15m", "30m", "1m", "5m"] else Timeframe.H1,
        start_date=start_date if isinstance(start_date, datetime) else datetime.now(timezone.utc) - timedelta(days=duration_days),
        end_date=end_date if isinstance(end_date, datetime) else datetime.now(timezone.utc),
        initial_balance=initial_balance,
        spread_pips=1.5,
        commission_per_lot=7.0,
        leverage=100,
    )
    
    # Generate random params if not provided
    if params is None:
        # Create unique seed from bot_name for reproducibility
        seed = int(hashlib.md5(bot_name.encode()).hexdigest()[:8], 16)
        params = StrategyParameters.generate_random(strategy_type, "medium", seed)
    
    # Run parameterized strategy
    trades, equity_curve = _run_parameterized_strategy(filtered_candles, config, params)
    
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


def _calculate_atr(candles: List[Candle], period: int = 14) -> List[float]:
    """Calculate Average True Range."""
    atr = [0.0] * period
    
    if len(candles) < period:
        return [0.0] * len(candles)
    
    tr_values = []
    for i in range(1, len(candles)):
        high = candles[i].high
        low = candles[i].low
        prev_close = candles[i-1].close
        
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
    
    # First ATR is simple average
    if len(tr_values) >= period:
        atr_val = sum(tr_values[:period]) / period
        atr.append(atr_val)
        
        # Subsequent ATRs use smoothing
        for i in range(period, len(tr_values)):
            atr_val = (atr_val * (period - 1) + tr_values[i]) / period
            atr.append(atr_val)
    
    return atr + [atr[-1] if atr else 0.0] * (len(candles) - len(atr))


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


def _run_parameterized_strategy(
    candles: List[Candle], 
    config: BacktestConfig, 
    params: StrategyParameters
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Run a parameterized strategy that produces UNIQUE results.
    Different parameter combinations = different trade outcomes.
    """
    trades = []
    equity_curve = []
    balance = config.initial_balance
    position = None
    last_trade_idx = -params.min_candles_between_trades
    trades_today = 0
    current_day = None
    
    # Calculate indicators based on params
    fast_ema = _calculate_ema(candles, params.fast_ema)
    slow_ema = _calculate_ema(candles, params.slow_ema)
    rsi = _calculate_rsi(candles, params.rsi_period)
    atr = _calculate_atr(candles, 14)
    
    # Random generator for this strategy (seeded for reproducibility)
    rng = random.Random(params.seed)
    
    for i, candle in enumerate(candles):
        # Track daily trades
        candle_day = candle.timestamp.date() if hasattr(candle.timestamp, 'date') else None
        if candle_day != current_day:
            current_day = candle_day
            trades_today = 0
        
        # Record equity point
        current_equity = balance
        if position:
            # Mark-to-market
            if position["direction"] == "BUY":
                unrealized = (candle.close - position["entry_price"]) * 10000 * 10
            else:
                unrealized = (position["entry_price"] - candle.close) * 10000 * 10
            current_equity = balance + unrealized
        
        peak = max(config.initial_balance, max((e.balance for e in equity_curve), default=config.initial_balance))
        dd = max(0, peak - current_equity)
        dd_pct = (dd / peak * 100) if peak > 0 else 0
        
        equity_curve.append(EquityPoint(
            timestamp=candle.timestamp,
            balance=current_equity,
            equity=current_equity,
            drawdown=dd,
            drawdown_percent=dd_pct,
        ))
        
        # Skip if indicators not ready
        min_lookback = max(params.slow_ema, params.breakout_lookback, params.rsi_period) + 5
        if i < min_lookback:
            continue
        
        if fast_ema[i] is None or slow_ema[i] is None:
            continue
        
        # Calculate volatility filter
        candle_range = candle.high - candle.low
        avg_range = atr[i] if i < len(atr) else candle_range
        volatility = candle_range / candle.close if candle.close > 0 else 0
        
        # Skip low volatility periods
        if volatility < params.min_volatility:
            continue
        
        # Entry logic based on strategy variant
        if position is None:
            # Check trade limits
            if trades_today >= params.max_trades_per_day:
                continue
            if i - last_trade_idx < params.min_candles_between_trades:
                continue
            
            entry_signal = None
            
            if params.strategy_variant == 0:  # Trend following (EMA crossover)
                if i > 0 and fast_ema[i-1] is not None and slow_ema[i-1] is not None:
                    if fast_ema[i] > slow_ema[i] and fast_ema[i-1] <= slow_ema[i-1]:
                        entry_signal = "BUY"
                    elif fast_ema[i] < slow_ema[i] and fast_ema[i-1] >= slow_ema[i-1]:
                        entry_signal = "SELL"
            
            elif params.strategy_variant == 1:  # Mean reversion (RSI)
                if rsi[i] < params.rsi_oversold:
                    # Add randomness for unique entries
                    if rng.random() > 0.3:  # 70% chance to enter
                        entry_signal = "BUY"
                elif rsi[i] > params.rsi_overbought:
                    if rng.random() > 0.3:
                        entry_signal = "SELL"
            
            elif params.strategy_variant == 2:  # Breakout
                lookback_candles = candles[max(0, i-params.breakout_lookback):i]
                if lookback_candles:
                    range_high = max(c.high for c in lookback_candles)
                    range_low = min(c.low for c in lookback_candles)
                    
                    if candle.close > range_high:
                        entry_signal = "BUY"
                    elif candle.close < range_low:
                        entry_signal = "SELL"
            
            else:  # Hybrid (combine signals)
                buy_signals = 0
                sell_signals = 0
                
                # EMA trend
                if fast_ema[i] > slow_ema[i]:
                    buy_signals += 1
                else:
                    sell_signals += 1
                
                # RSI
                if rsi[i] < params.rsi_oversold + 10:
                    buy_signals += 1
                elif rsi[i] > params.rsi_overbought - 10:
                    sell_signals += 1
                
                # Momentum
                if i >= 3:
                    if candle.close > candles[i-3].close:
                        buy_signals += 1
                    else:
                        sell_signals += 1
                
                if buy_signals >= 2 and rng.random() > 0.4:
                    entry_signal = "BUY"
                elif sell_signals >= 2 and rng.random() > 0.4:
                    entry_signal = "SELL"
            
            # Create position
            if entry_signal:
                sl_distance = avg_range * params.stop_loss_mult
                tp_distance = avg_range * params.take_profit_mult
                
                if entry_signal == "BUY":
                    position = {
                        "direction": "BUY",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": candle.close - sl_distance,
                        "take_profit": candle.close + tp_distance,
                    }
                else:
                    position = {
                        "direction": "SELL",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": candle.close + sl_distance,
                        "take_profit": candle.close - tp_distance,
                    }
                
                last_trade_idx = i
                trades_today += 1
        
        # Exit logic
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
                # Trailing exit conditions
                elif params.strategy_variant == 0 and fast_ema[i] < slow_ema[i]:
                    exit_reason = "Signal"
                    exit_price = candle.close
                elif params.strategy_variant == 1 and rsi[i] > 50:
                    exit_reason = "Signal"
                    exit_price = candle.close
            else:  # SELL
                if candle.high >= position["stop_loss"]:
                    exit_reason = "SL"
                    exit_price = position["stop_loss"]
                elif candle.low <= position["take_profit"]:
                    exit_reason = "TP"
                    exit_price = position["take_profit"]
                elif params.strategy_variant == 0 and fast_ema[i] > slow_ema[i]:
                    exit_reason = "Signal"
                    exit_price = candle.close
                elif params.strategy_variant == 1 and rsi[i] < 50:
                    exit_reason = "Signal"
                    exit_price = candle.close
            
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trades.append(trade)
                balance += trade.profit_loss
                position = None
    
    # Close any remaining position
    if position and candles:
        last_candle = candles[-1]
        trade = _create_trade(position, last_candle.timestamp, last_candle.close, "EOD", config.symbol)
        trades.append(trade)
        balance += trade.profit_loss
    
    return trades, equity_curve


# Keep legacy functions for backwards compatibility
def _run_trend_following(candles: List[Candle], config: BacktestConfig) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """EMA crossover strategy on real candles (legacy)."""
    params = StrategyParameters(fast_ema=10, slow_ema=20, strategy_variant=0)
    return _run_parameterized_strategy(candles, config, params)


def _run_mean_reversion(candles: List[Candle], config: BacktestConfig) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """RSI mean reversion strategy on real candles (legacy)."""
    params = StrategyParameters(rsi_period=14, rsi_oversold=30, rsi_overbought=70, strategy_variant=1)
    return _run_parameterized_strategy(candles, config, params)


def _run_breakout(candles: List[Candle], config: BacktestConfig) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """Breakout strategy on real candles (legacy)."""
    params = StrategyParameters(breakout_lookback=20, strategy_variant=2)
    return _run_parameterized_strategy(candles, config, params)
