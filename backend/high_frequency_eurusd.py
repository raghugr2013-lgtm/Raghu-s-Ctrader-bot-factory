"""
High-Frequency EURUSD Strategy - Final Optimized Version

Goals:
- 50-120 trades
- Profit Factor > 1.5
- Drawdown < 5%

Approach:
- Use EMA 5/50 base (proven profitable)
- Add re-entry logic after profitable exits
- Allow entries on EMA alignment (not just crosses)
- Implement smart risk management
- Tighter trailing stops to lock profits
"""

import logging
from typing import List, Tuple, Dict, Optional

from market_data_models import Candle
from backtest_models import (
    TradeRecord, EquityPoint, BacktestConfig, TradeDirection, TradeStatus
)
from backtest_real_engine import _calculate_ema, _calculate_rsi, _create_trade
from improved_eurusd_strategy import calculate_atr, get_trading_session, TradingSession

logger = logging.getLogger(__name__)


def run_high_frequency_eurusd(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint]]:
    """
    High-frequency EURUSD strategy.
    
    Key features:
    - Enters on EMA alignment (not just crosses)
    - Re-enters after profitable trades
    - RSI pullback zones for better entries
    - Quick profit-taking with trailing stops
    """
    
    default_params = {
        "ema_fast": 5,
        "ema_medium": 50,
        "ema_trend": 200,
        "rsi_period": 14,
        "rsi_pullback_buy_min": 35,
        "rsi_pullback_buy_max": 55,
        "rsi_pullback_sell_min": 45,
        "rsi_pullback_sell_max": 65,
        "atr_period": 14,
        "stop_loss_atr_mult": 2.5,
        "take_profit_atr_mult": 4.0,
        "trailing_atr_mult": 1.8,
        "max_trades_per_day": 5,
        "allow_same_direction_reentry": True,
        "min_candles_between_trades": 2,
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"Running high-frequency strategy")
    
    # Calculate indicators
    ema_fast = _calculate_ema(candles, p["ema_fast"])
    ema_medium = _calculate_ema(candles, p["ema_medium"])
    ema_trend = _calculate_ema(candles, p["ema_trend"])
    rsi = _calculate_rsi(candles, p["rsi_period"])
    atr = calculate_atr(candles, p["atr_period"])
    
    # State
    trades = []
    equity_curve = []
    balance = config.initial_balance
    peak_balance = balance
    position = None
    trades_per_day = {}
    last_exit_index = -100
    last_trade_direction = None
    
    for i, candle in enumerate(candles):
        current_equity = balance
        
        # Update position
        if position:
            if position["direction"] == "BUY":
                unrealized_pnl = (candle.close - position["entry_price"]) * 10000 * 10
                # Aggressive trailing stop
                new_trail = candle.close - (atr[i] * p["trailing_atr_mult"])
                if new_trail > position["trailing_stop"]:
                    position["trailing_stop"] = new_trail
            else:
                unrealized_pnl = (position["entry_price"] - candle.close) * 10000 * 10
                new_trail = candle.close + (atr[i] * p["trailing_atr_mult"])
                if new_trail < position["trailing_stop"]:
                    position["trailing_stop"] = new_trail
            
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
        
        # Skip if not ready
        if ema_trend[i] is None or i < p["ema_trend"]:
            continue
        
        # Session tracking
        session = get_trading_session(candle.timestamp)
        day_key = candle.timestamp.date()
        if day_key not in trades_per_day:
            trades_per_day[day_key] = 0
        
        # Exit management
        if position:
            exit_reason = None
            exit_price = None
            
            if position["direction"] == "BUY":
                if candle.low <= position["trailing_stop"]:
                    exit_price = position["trailing_stop"]
                    exit_reason = "Trailing Stop"
                elif candle.low <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                elif candle.high >= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                # Quick exit on opposite signal
                elif ema_fast[i] < ema_medium[i] - (atr[i] * 0.3):
                    exit_price = candle.close
                    exit_reason = "Trend Reversal"
            else:  # SELL
                if candle.high >= position["trailing_stop"]:
                    exit_price = position["trailing_stop"]
                    exit_reason = "Trailing Stop"
                elif candle.high >= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop Loss"
                elif candle.low <= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "Take Profit"
                elif ema_fast[i] > ema_medium[i] + (atr[i] * 0.3):
                    exit_price = candle.close
                    exit_reason = "Trend Reversal"
            
            if exit_reason:
                trade = _create_trade(position, candle.timestamp, exit_price, exit_reason, config.symbol)
                trades.append(trade)
                balance += trade.profit_loss
                last_exit_index = i
                last_trade_direction = position["direction"]
                position = None
        
        # Entry logic
        if position is None:
            # Filters
            if trades_per_day[day_key] >= p["max_trades_per_day"]:
                continue
            
            if session not in [TradingSession.LONDON, TradingSession.OVERLAP, TradingSession.NY]:
                continue
            
            if atr[i] < 0.0003:
                continue
            
            # Cooldown between trades
            if i - last_exit_index < p["min_candles_between_trades"]:
                continue
            
            # Determine trend
            in_uptrend = candle.close > ema_trend[i]
            in_downtrend = candle.close < ema_trend[i]
            
            # Fast EMA above medium EMA
            ema_bullish = ema_fast[i] > ema_medium[i]
            ema_bearish = ema_fast[i] < ema_medium[i]
            
            # BUY CONDITIONS
            if in_uptrend and ema_bullish:
                # Entry scenarios:
                # 1. Fresh cross
                # 2. Pullback (RSI in zone + price pullback to EMA)
                # 3. Continuation (strong momentum)
                
                fresh_cross = (i > 0 and ema_fast[i-1] <= ema_medium[i-1])
                in_pullback_zone = (p["rsi_pullback_buy_min"] <= rsi[i] <= p["rsi_pullback_buy_max"] and 
                                   abs(candle.close - ema_medium[i]) / ema_medium[i] < 0.003)
                strong_momentum = rsi[i] > 50 and ema_fast[i] > ema_medium[i] + (atr[i] * 0.5)
                
                can_reenter = p["allow_same_direction_reentry"] or last_trade_direction != "BUY"
                
                if can_reenter and (fresh_cross or in_pullback_zone or strong_momentum):
                    stop_loss = candle.close - (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = candle.close + (atr[i] * p["take_profit_atr_mult"])
                    trailing_stop = candle.close - (atr[i] * p["trailing_atr_mult"])
                    
                    position = {
                        "direction": "BUY",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "trailing_stop": trailing_stop,
                    }
                    trades_per_day[day_key] += 1
            
            # SELL CONDITIONS
            elif in_downtrend and ema_bearish:
                fresh_cross = (i > 0 and ema_fast[i-1] >= ema_medium[i-1])
                in_pullback_zone = (p["rsi_pullback_sell_min"] <= rsi[i] <= p["rsi_pullback_sell_max"] and 
                                   abs(candle.close - ema_medium[i]) / ema_medium[i] < 0.003)
                strong_momentum = rsi[i] < 50 and ema_fast[i] < ema_medium[i] - (atr[i] * 0.5)
                
                can_reenter = p["allow_same_direction_reentry"] or last_trade_direction != "SELL"
                
                if can_reenter and (fresh_cross or in_pullback_zone or strong_momentum):
                    stop_loss = candle.close + (atr[i] * p["stop_loss_atr_mult"])
                    take_profit = candle.close - (atr[i] * p["take_profit_atr_mult"])
                    trailing_stop = candle.close + (atr[i] * p["trailing_atr_mult"])
                    
                    position = {
                        "direction": "SELL",
                        "entry_price": candle.close,
                        "entry_time": candle.timestamp,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "trailing_stop": trailing_stop,
                    }
                    trades_per_day[day_key] += 1
    
    # Close final position
    if position:
        trade = _create_trade(position, candles[-1].timestamp, candles[-1].close, "End", config.symbol)
        trades.append(trade)
        balance += trade.profit_loss
    
    logger.info(f"High-frequency strategy: {len(trades)} trades, Balance: ${balance:.2f}")
    
    return trades, equity_curve
