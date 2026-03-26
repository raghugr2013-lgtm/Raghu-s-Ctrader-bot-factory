"""
Adaptive EURUSD Strategy - Version 2

Key improvements:
- Trend-following during strong trends
- Mean reversion during ranging markets
- Better risk management with trailing stops
- Dynamic position sizing based on ATR
- Multiple entry confirmation signals
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Optional

from market_data_models import Candle
from backtest_models import (
    TradeRecord, EquityPoint, BacktestConfig, Timeframe, TradeDirection, TradeStatus
)
from backtest_real_engine import _calculate_ema, _calculate_rsi, _create_trade
from improved_eurusd_strategy import calculate_atr, get_trading_session, TradingSession

logger = logging.getLogger(__name__)


def calculate_adx(candles: List[Candle], period: int = 14) -> Tuple[List[float], List[float], List[float]]:
    """Calculate ADX, +DI, -DI"""
    if len(candles) < period + 1:
        return [0.0] * len(candles), [0.0] * len(candles), [0.0] * len(candles)
    
    plus_dm = []
    minus_dm = []
    tr_list = []
    
    for i in range(1, len(candles)):
        high_diff = candles[i].high - candles[i-1].high
        low_diff = candles[i-1].low - candles[i].low
        
        # +DM and -DM
        if high_diff > low_diff and high_diff > 0:
            plus_dm.append(high_diff)
        else:
            plus_dm.append(0.0)
        
        if low_diff > high_diff and low_diff > 0:
            minus_dm.append(low_diff)
        else:
            minus_dm.append(0.0)
        
        # True Range
        hl = candles[i].high - candles[i].low
        hc = abs(candles[i].high - candles[i-1].close)
        lc = abs(candles[i].low - candles[i-1].close)
        tr_list.append(max(hl, hc, lc))
    
    # Smooth the values
    smooth_plus_dm = []
    smooth_minus_dm = []
    smooth_tr = []
    
    if len(plus_dm) >= period:
        # Initial sums
        smooth_plus_dm.append(sum(plus_dm[:period]))
        smooth_minus_dm.append(sum(minus_dm[:period]))
        smooth_tr.append(sum(tr_list[:period]))
        
        # Wilder's smoothing
        for i in range(period, len(plus_dm)):
            smooth_plus_dm.append(smooth_plus_dm[-1] - (smooth_plus_dm[-1] / period) + plus_dm[i])
            smooth_minus_dm.append(smooth_minus_dm[-1] - (smooth_minus_dm[-1] / period) + minus_dm[i])
            smooth_tr.append(smooth_tr[-1] - (smooth_tr[-1] / period) + tr_list[i])
    
    # Calculate +DI and -DI
    plus_di = []
    minus_di = []
    dx_list = []
    
    for i in range(len(smooth_tr)):
        if smooth_tr[i] > 0:
            pdi = 100 * smooth_plus_dm[i] / smooth_tr[i]
            mdi = 100 * smooth_minus_dm[i] / smooth_tr[i]
            plus_di.append(pdi)
            minus_di.append(mdi)
            
            # DX
            di_sum = pdi + mdi
            if di_sum > 0:
                dx = 100 * abs(pdi - mdi) / di_sum
                dx_list.append(dx)
            else:
                dx_list.append(0.0)
        else:
            plus_di.append(0.0)
            minus_di.append(0.0)
            dx_list.append(0.0)
    
    # Calculate ADX
    adx = []
    if len(dx_list) >= period:
        adx.append(sum(dx_list[:period]) / period)
        for i in range(period, len(dx_list)):
            adx.append((adx[-1] * (period - 1) + dx_list[i]) / period)
    
    # Pad to match candle length
    pad_length = len(candles) - len(adx)
    adx_padded = [0.0] * pad_length + adx
    pdi_padded = [0.0] * (len(candles) - len(plus_di)) + plus_di
    mdi_padded = [0.0] * (len(candles) - len(minus_di)) + minus_di
    
    return adx_padded, pdi_padded, mdi_padded


def run_adaptive_eurusd_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Adaptive EURUSD strategy that switches between trend-following and mean-reversion.
    
    Parameters:
    - ema_fast: 10 (entry signal)
    - ema_slow: 50 (trend filter)
    - ema_long: 200 (major trend)
    - rsi_period: 14
    - adx_period: 14
    - adx_trend_threshold: 25 (above = trending, below = ranging)
    - atr_period: 14
    - stop_loss_atr_mult: 2.0
    - take_profit_atr_mult: 3.5
    - trailing_stop_atr_mult: 1.5
    - risk_per_trade_pct: 1.0
    - max_trades_per_day: 4
    """
    
    # Default parameters
    default_params = {
        "ema_fast": 10,
        "ema_slow": 50,
        "ema_long": 200,
        "rsi_period": 14,
        "adx_period": 14,
        "adx_trend_threshold": 25,
        "atr_period": 14,
        "stop_loss_atr_mult": 2.0,
        "take_profit_atr_mult": 3.5,
        "trailing_stop_atr_mult": 1.5,
        "risk_per_trade_pct": 1.0,
        "max_trades_per_day": 4,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running adaptive EURUSD strategy on {len(candles)} candles")
    
    # Calculate indicators
    ema_fast = _calculate_ema(candles, p["ema_fast"])
    ema_slow = _calculate_ema(candles, p["ema_slow"])
    ema_long = _calculate_ema(candles, p["ema_long"])
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    adx, plus_di, minus_di = calculate_adx(candles, p["adx_period"])
    
    # Track state
    trades = []
    equity_curve = []
    balance = config.initial_balance
    peak_balance = balance
    position = None
    trades_per_day = {}
    
    for i, candle in enumerate(candles):
        current_equity = balance
        
        # Update equity if in position
        if position:
            if position["direction"] == "BUY":
                unrealized_pnl = (candle.close - position["entry_price"]) * 10000 * 10
                # Update trailing stop
                potential_trail = candle.close - (atr[i] * p["trailing_stop_atr_mult"])
                if potential_trail > position["trailing_stop"]:
                    position["trailing_stop"] = potential_trail
            else:
                unrealized_pnl = (position["entry_price"] - candle.close) * 10000 * 10
                # Update trailing stop
                potential_trail = candle.close + (atr[i] * p["trailing_stop_atr_mult"])
                if potential_trail < position["trailing_stop"]:
                    position["trailing_stop"] = potential_trail
            
            current_equity = balance + unrealized_pnl
        
        # Calculate drawdown
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
        if (ema_fast[i] is None or ema_slow[i] is None or ema_long[i] is None or 
            i < p["ema_long"]):
            continue
        
        # Trading session filter
        session = get_trading_session(candle.timestamp)
        day_key = candle.timestamp.date()
        if day_key not in trades_per_day:
            trades_per_day[day_key] = 0
        
        # Determine market regime
        is_trending = adx[i] > p["adx_trend_threshold"]
        is_ranging = adx[i] < p["adx_trend_threshold"]
        
        # Exit management
        if position:
            exit_reason = None
            exit_price = None
            
            if position["direction"] == "BUY":
                # Trailing stop
                if candle.low <= position["trailing_stop"]:
                    exit_price = position["trailing_stop"]
                    exit_reason = "Trailing Stop"
                # Hard stop loss
                elif candle.low <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                # Take profit
                elif candle.high >= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                # Trend reversal signal
                elif ema_fast[i] < ema_slow[i] and rsi[i] > 60:
                    exit_price = candle.close
                    exit_reason = "Trend Reversal"
            else:  # SELL
                # Trailing stop
                if candle.high >= position["trailing_stop"]:
                    exit_price = position["trailing_stop"]
                    exit_reason = "Trailing Stop"
                # Hard stop loss
                elif candle.high >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                # Take profit
                elif candle.low <= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                # Trend reversal signal
                elif ema_fast[i] > ema_slow[i] and rsi[i] < 40:
                    exit_price = candle.close
                    exit_reason = "Trend Reversal"
            
            # Close position
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trades.append(trade)
                balance += trade.profit_loss
                position = None
        
        # Entry logic
        if position is None:
            # Daily trade limit
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            # Session filter
            if session == TradingSession.OFF or session == TradingSession.ASIAN:
                continue
            
            # Volatility filter
            if atr[i] < 0.0005:  # Minimum ATR threshold
                continue
            
            # TREND-FOLLOWING MODE (when ADX > threshold)
            if is_trending:
                # BUY: Price above EMA200, fast EMA crosses above slow EMA, +DI > -DI
                if (candle.close > ema_long[i] and 
                    ema_fast[i] > ema_slow[i] and 
                    i > 0 and ema_fast[i-1] <= ema_slow[i-1] and
                    plus_di[i] > minus_di[i] and
                    30 < rsi[i] < 70):
                    
                    stop_loss = candle.close - (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = candle.close + (atr[i] * p["take_profit_atr_mult"])
                    trailing_stop = candle.close - (atr[i] * p["trailing_stop_atr_mult"])
                    
                    position = {
                        "direction": "BUY",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "trailing_stop": trailing_stop,
                        "regime": "trending"
                    }
                    trades_per_day[day_key] += 1
                
                # SELL: Price below EMA200, fast EMA crosses below slow EMA, -DI > +DI
                elif (candle.close < ema_long[i] and 
                      ema_fast[i] < ema_slow[i] and 
                      i > 0 and ema_fast[i-1] >= ema_slow[i-1] and
                      minus_di[i] > plus_di[i] and
                      30 < rsi[i] < 70):
                    
                    stop_loss = candle.close + (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = candle.close - (atr[i] * p["take_profit_atr_mult"])
                    trailing_stop = candle.close + (atr[i] * p["trailing_stop_atr_mult"])
                    
                    position = {
                        "direction": "SELL",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "trailing_stop": trailing_stop,
                        "regime": "trending"
                    }
                    trades_per_day[day_key] += 1
            
            # MEAN-REVERSION MODE (when ADX < threshold)
            else:
                # BUY: Oversold RSI, price near lower band
                if (rsi[i] < 35 and 
                    candle.close < ema_slow[i] and
                    candle.close > ema_long[i]):  # Still above major trend
                    
                    stop_loss = candle.close - (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = ema_slow[i]  # Target mean reversion to EMA50
                    trailing_stop = candle.close - (atr[i] * p["trailing_stop_atr_mult"])
                    
                    position = {
                        "direction": "BUY",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "trailing_stop": trailing_stop,
                        "regime": "ranging"
                    }
                    trades_per_day[day_key] += 1
                
                # SELL: Overbought RSI, price near upper band
                elif (rsi[i] > 65 and 
                      candle.close > ema_slow[i] and
                      candle.close < ema_long[i]):  # Still below major trend
                    
                    stop_loss = candle.close + (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = ema_slow[i]  # Target mean reversion to EMA50
                    trailing_stop = candle.close + (atr[i] * p["trailing_stop_atr_mult"])
                    
                    position = {
                        "direction": "SELL",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "trailing_stop": trailing_stop,
                        "regime": "ranging"
                    }
                    trades_per_day[day_key] += 1
    
    # Close any remaining position
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, "End of Backtest", config.symbol)
        trades.append(trade)
        balance += trade.profit_loss
    
    logger.info(f"Adaptive strategy completed: {len(trades)} trades, Final balance: ${balance:.2f}")
    
    return trades, equity_curve
