"""
Optimized EURUSD Strategy - Designed for actual market conditions

Based on analysis:
- Market is 68% bearish during test period
- Best simple EMA: 5/50
- Need to follow the trend, not fight it
- Need more frequent entries with proper risk management

Strategy:
- EMA 5/20 for faster signals (more trades)
- EMA 200 trend filter
- RSI for entry timing (pullbacks in trend direction)
- ATR-based stops
- Session filter
- Max 5 trades per day
"""

import logging
from datetime import datetime
from typing import List, Tuple, Dict, Optional

from market_data_models import Candle
from backtest_models import (
    TradeRecord, EquityPoint, BacktestConfig, TradeDirection, TradeStatus
)
from backtest_real_engine import _calculate_ema, _calculate_rsi, _create_trade
from improved_eurusd_strategy import calculate_atr, get_trading_session, TradingSession

logger = logging.getLogger(__name__)


def run_optimized_eurusd_strategy(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    Optimized EURUSD strategy based on market analysis.
    
    Parameters:
    - ema_fast: 5 (quick signal)
    - ema_medium: 20 (entry confirmation)
    - ema_trend: 200 (major trend)
    - rsi_period: 14
    - rsi_neutral_min: 40 (pullback buy zone start)
    - rsi_neutral_max: 60 (pullback sell zone start)
    - atr_period: 14
    - stop_loss_atr_mult: 2.5
    - take_profit_atr_mult: 4.0
    - risk_per_trade_pct: 1.0
    - max_trades_per_day: 5
    - use_trailing_stop: True
    - trailing_atr_mult: 2.0
    """
    
    default_params = {
        "ema_fast": 5,
        "ema_medium": 20,
        "ema_trend": 200,
        "rsi_period": 14,
        "rsi_neutral_min": 40,
        "rsi_neutral_max": 60,
        "atr_period": 14,
        "stop_loss_atr_mult": 2.5,
        "take_profit_atr_mult": 4.0,
        "risk_per_trade_pct": 1.0,
        "max_trades_per_day": 5,
        "use_trailing_stop": True,
        "trailing_atr_mult": 2.0,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running optimized EURUSD strategy with params: {p}")
    
    # Calculate indicators
    ema_fast = _calculate_ema(candles, p["ema_fast"])
    ema_medium = _calculate_ema(candles, p["ema_medium"])
    ema_trend = _calculate_ema(candles, p["ema_trend"])
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    
    # State tracking
    trades = []
    equity_curve = []
    balance = config.initial_balance
    peak_balance = balance
    position = None
    trades_per_day = {}
    
    for i, candle in enumerate(candles):
        current_equity = balance
        
        # Update unrealized P&L
        if position:
            if position["direction"] == "BUY":
                unrealized_pnl = (candle.close - position["entry_price"]) * 10000 * 10
                # Trailing stop
                if p["use_trailing_stop"]:
                    new_trail = candle.close - (atr[i] * p["trailing_atr_mult"])
                    if new_trail > position["trailing_stop"]:
                        position["trailing_stop"] = new_trail
            else:
                unrealized_pnl = (position["entry_price"] - candle.close) * 10000 * 10
                # Trailing stop
                if p["use_trailing_stop"]:
                    new_trail = candle.close + (atr[i] * p["trailing_atr_mult"])
                    if new_trail < position["trailing_stop"]:
                        position["trailing_stop"] = new_trail
            
            current_equity = balance + unrealized_pnl
        
        # Drawdown tracking
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
        
        # Skip if not enough data
        if (ema_fast[i] is None or ema_medium[i] is None or ema_trend[i] is None or 
            i < p["ema_trend"]):
            continue
        
        # Session & day tracking
        session = get_trading_session(candle.timestamp)
        day_key = candle.timestamp.date()
        if day_key not in trades_per_day:
            trades_per_day[day_key] = 0
        
        # Exit management
        if position:
            exit_reason = None
            exit_price = None
            
            if position["direction"] == "BUY":
                # Trailing stop (if enabled)
                if p["use_trailing_stop"] and candle.low <= position["trailing_stop"]:
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
                # EMA cross signal (trend reversal)
                elif ema_fast[i] < ema_medium[i]:
                    exit_price = candle.close
                    exit_reason = "EMA Cross Exit"
            
            else:  # SELL
                # Trailing stop
                if p["use_trailing_stop"] and candle.high >= position["trailing_stop"]:
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
                # EMA cross signal
                elif ema_fast[i] > ema_medium[i]:
                    exit_price = candle.close
                    exit_reason = "EMA Cross Exit"
            
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trades.append(trade)
                balance += trade.profit_loss
                position = None
        
        # Entry logic
        if position is None:
            # Filters
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            if session == TradingSession.OFF or session == TradingSession.ASIAN:
                continue
            
            if atr[i] < 0.0003:  # Minimum volatility
                continue
            
            # Determine overall trend
            in_uptrend = candle.close > ema_trend[i]
            in_downtrend = candle.close < ema_trend[i]
            
            # BUY SIGNAL: Uptrend + fast EMA above medium + RSI not overbought
            if in_uptrend and ema_fast[i] > ema_medium[i]:
                # Entry on pullback or continuation
                if (p["rsi_neutral_min"] <= rsi[i] <= 70 and 
                    (i == 0 or ema_fast[i-1] <= ema_medium[i-1])):  # Fresh cross or first bar above
                    
                    stop_loss = candle.close - (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = candle.close + (atr[i] * p["take_profit_atr_mult"])
                    trailing_stop = candle.close - (atr[i] * p["trailing_atr_mult"]) if p["use_trailing_stop"] else stop_loss
                    
                    position = {
                        "direction": "BUY",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "trailing_stop": trailing_stop,
                    }
                    trades_per_day[day_key] += 1
            
            # SELL SIGNAL: Downtrend + fast EMA below medium + RSI not oversold
            elif in_downtrend and ema_fast[i] < ema_medium[i]:
                # Entry on pullback or continuation
                if (30 <= rsi[i] <= p["rsi_neutral_max"] and 
                    (i == 0 or ema_fast[i-1] >= ema_medium[i-1])):  # Fresh cross or first bar below
                    
                    stop_loss = candle.close + (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = candle.close - (atr[i] * p["take_profit_atr_mult"])
                    trailing_stop = candle.close + (atr[i] * p["trailing_atr_mult"]) if p["use_trailing_stop"] else stop_loss
                    
                    position = {
                        "direction": "SELL",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "trailing_stop": trailing_stop,
                    }
                    trades_per_day[day_key] += 1
    
    # Close remaining position
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, "End of Test", config.symbol)
        trades.append(trade)
        balance += trade.profit_loss
    
    logger.info(f"Strategy complete: {len(trades)} trades, Balance: ${balance:.2f}")
    
    return trades, equity_curve
