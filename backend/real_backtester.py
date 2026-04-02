"""
Real Strategy Backtester
Runs template strategies against real OHLCV candle data using vectorized
indicator calculations and candle-by-candle trade simulation.
"""

import math
import uuid
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone

import numpy as np

from market_data_models import Candle
from backtest_models import TradeRecord, TradeDirection, TradeStatus, EquityPoint

logger = logging.getLogger(__name__)

PIP_SIZE = 0.0001
PIP_VALUE = 10.0  # $10 per pip per standard lot


def get_pip_size(symbol: str) -> float:
    """Return pip size based on currency pair. JPY pairs use 0.01."""
    jpy_pairs = {"USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"}
    return 0.01 if symbol.upper() in jpy_pairs else 0.0001


# ---------------------------------------------------------------------------
# Technical Indicators (vectorized)
# ---------------------------------------------------------------------------

def ema(prices: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    out = np.full_like(prices, np.nan)
    if len(prices) < period:
        return out
    mult = 2.0 / (period + 1)
    out[period - 1] = np.mean(prices[:period])
    for i in range(period, len(prices)):
        out[i] = (prices[i] - out[i - 1]) * mult + out[i - 1]
    return out


def sma(prices: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    out = np.full_like(prices, np.nan)
    if len(prices) < period:
        return out
    cs = np.cumsum(prices)
    cs = np.insert(cs, 0, 0)
    out[period - 1:] = (cs[period:] - cs[:-period]) / period
    return out


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Average True Range."""
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    return ema(tr, period)


def rsi(close: np.ndarray, period: int) -> np.ndarray:
    """Relative Strength Index."""
    out = np.full_like(close, np.nan)
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    if len(gain) < period:
        return out
    avg_gain = np.mean(gain[:period])
    avg_loss = np.mean(loss[:period])
    for i in range(period, len(gain)):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        if avg_loss == 0:
            out[i + 1] = 100.0
        else:
            out[i + 1] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    if avg_loss == 0:
        out[period] = 100.0
    else:
        out[period] = 100.0 - 100.0 / (1.0 + np.mean(gain[:period]) / np.mean(loss[:period]))
    return out


def bollinger_bands(close: np.ndarray, period: int, std_mult: float):
    """Bollinger Bands -> (middle, upper, lower)."""
    mid = sma(close, period)
    std = np.full_like(close, np.nan)
    for i in range(period - 1, len(close)):
        std[i] = np.std(close[i - period + 1: i + 1], ddof=0)
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return mid, upper, lower


def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Average Directional Index (simplified)."""
    n = len(close)
    out = np.full(n, np.nan)
    if n < period * 2:
        return out
    up_move = np.diff(high)
    down_move = -np.diff(low)
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_vals = atr(high, low, close, period)
    smooth_plus = ema(plus_dm, period)
    smooth_minus = ema(minus_dm, period)
    # Align lengths
    min_len = min(len(smooth_plus), len(smooth_minus), n - 1)
    for i in range(min_len):
        idx = i + 1
        if idx >= n:
            break
        a = atr_vals[idx] if not np.isnan(atr_vals[idx]) else 1.0
        if a == 0:
            a = 1.0
        di_plus = (smooth_plus[i] / a) * 100 if not np.isnan(smooth_plus[i]) else 0
        di_minus = (smooth_minus[i] / a) * 100 if not np.isnan(smooth_minus[i]) else 0
        di_sum = di_plus + di_minus
        if di_sum == 0:
            out[idx] = 0
        else:
            out[idx] = abs(di_plus - di_minus) / di_sum * 100
    # Smooth ADX
    smoothed = ema(out[~np.isnan(out)], period) if np.any(~np.isnan(out)) else out
    valid_indices = np.where(~np.isnan(out))[0]
    for j, idx in enumerate(valid_indices):
        if j < len(smoothed) and not np.isnan(smoothed[j]):
            out[idx] = smoothed[j]
    return out


def macd(close: np.ndarray, fast: int, slow: int, signal: int = 9):
    """MACD -> (macd_line, signal_line, histogram)."""
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line[~np.isnan(macd_line)], signal)
    # Align signal line
    full_signal = np.full_like(close, np.nan)
    valid = np.where(~np.isnan(macd_line))[0]
    start = valid[0] if len(valid) > 0 else 0
    for i, val in enumerate(signal_line):
        idx = start + i
        if idx < len(full_signal):
            full_signal[idx] = val
    histogram = macd_line - full_signal
    return macd_line, full_signal, histogram


# ---------------------------------------------------------------------------
# Trade Simulation
# ---------------------------------------------------------------------------

class TradeSimulator:
    """Candle-by-candle trade simulation with SL/TP."""

    def __init__(self, initial_balance: float, spread_pips: float = 1.5, pip_size: float = 0.0001):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.spread_pips = spread_pips
        self.pip_size = pip_size
        self.trades: List[TradeRecord] = []
        self.equity_curve: List[EquityPoint] = []
        self.open_position: Optional[dict] = None
        self.backtest_id = str(uuid.uuid4())
        self.peak = initial_balance

    def open_trade(self, direction: str, price: float, sl: float, tp: float,
                   volume: float, timestamp: datetime):
        if self.open_position is not None:
            return  # only one position at a time
        entry = price + (self.spread_pips * self.pip_size) if direction == "buy" else price
        self.open_position = {
            "id": str(uuid.uuid4()),
            "direction": direction,
            "entry_price": entry,
            "sl": sl,
            "tp": tp,
            "volume": volume,
            "entry_time": timestamp,
        }

    def update(self, high: float, low: float, close: float, timestamp: datetime):
        """Check SL/TP on current candle."""
        if self.open_position is None:
            return
        pos = self.open_position
        if pos["direction"] == "buy":
            if pos["sl"] and low <= pos["sl"]:
                self._close(pos["sl"], "stop_loss", timestamp)
            elif pos["tp"] and high >= pos["tp"]:
                self._close(pos["tp"], "take_profit", timestamp)
        else:
            if pos["sl"] and high >= pos["sl"]:
                self._close(pos["sl"], "stop_loss", timestamp)
            elif pos["tp"] and low <= pos["tp"]:
                self._close(pos["tp"], "take_profit", timestamp)

    def _close(self, exit_price: float, reason: str, timestamp: datetime):
        pos = self.open_position
        if pos is None:
            return
        if pos["direction"] == "buy":
            pips = (exit_price - pos["entry_price"]) / self.pip_size
        else:
            pips = (pos["entry_price"] - exit_price) / self.pip_size
        profit = pips * PIP_VALUE * pos["volume"]
        self.balance += profit

        direction = TradeDirection.BUY if pos["direction"] == "buy" else TradeDirection.SELL
        duration = (timestamp - pos["entry_time"]).total_seconds() / 60

        trade = TradeRecord(
            id=pos["id"],
            backtest_id=self.backtest_id,
            entry_time=pos["entry_time"],
            exit_time=timestamp,
            symbol="EURUSD",
            direction=direction,
            entry_price=pos["entry_price"],
            exit_price=exit_price,
            stop_loss=pos["sl"],
            take_profit=pos["tp"],
            volume=pos["volume"],
            position_size=pos["volume"] * 100000,
            profit_loss=profit,
            profit_loss_pips=pips,
            profit_loss_percent=(profit / self.initial_balance) * 100,
            duration_minutes=int(duration),
            commission=7.0 * pos["volume"],
            status=TradeStatus.CLOSED,
            close_reason=reason,
        )
        self.trades.append(trade)
        self.open_position = None

    def force_close(self, close_price: float, timestamp: datetime):
        if self.open_position is not None:
            self._close(close_price, "simulation_end", timestamp)

    def record_equity(self, timestamp: datetime):
        equity = self.balance
        if self.open_position:
            # approximate floating PnL not added for simplicity
            pass
        if equity > self.peak:
            self.peak = equity
        dd = self.peak - equity
        dd_pct = (dd / self.peak * 100) if self.peak > 0 else 0
        self.equity_curve.append(EquityPoint(
            timestamp=timestamp, balance=self.balance, equity=equity,
            drawdown=dd, drawdown_percent=dd_pct,
        ))


# ---------------------------------------------------------------------------
# Real Backtester
# ---------------------------------------------------------------------------

class RealBacktester:
    """
    Run a template strategy against real OHLCV candles.
    Returns (trades, equity_curve, config_dict).
    """

    def run(
        self,
        template_id: str,
        genes: Dict[str, float],
        candles: List[Candle],
        initial_balance: float = 10000.0,
    ) -> Tuple[List[TradeRecord], List[EquityPoint], dict]:

        if len(candles) < 60:
            return [], [], {"initial_balance": initial_balance}

        # Convert to numpy
        opens = np.array([c.open for c in candles])
        highs = np.array([c.high for c in candles])
        lows = np.array([c.low for c in candles])
        closes = np.array([c.close for c in candles])
        timestamps = [c.timestamp for c in candles]
        n = len(closes)

        # Route to template-specific signal generator
        dispatch = {
            "ema_crossover": self._signals_ema_crossover,
            "macd_trend": self._signals_macd_trend,
            "rsi_mean_reversion": self._signals_rsi_mean_reversion,
            "bollinger_breakout": self._signals_bollinger_breakout,
            "atr_volatility_breakout": self._signals_atr_breakout,
            # Backtest strategy type aliases
            "trend_following": self._signals_ema_crossover,
            "mean_reversion": self._signals_rsi_mean_reversion,
            "breakout": self._signals_bollinger_breakout,
        }

        signal_fn = dispatch.get(template_id, self._signals_ema_crossover)
        signals, sl_distances, tp_distances = signal_fn(
            genes, opens, highs, lows, closes, n
        )

        # Determine pip size for this symbol
        symbol = candles[0].symbol if candles else "EURUSD"
        pip_sz = get_pip_size(symbol)

        # Simulate trades
        risk_pct = genes.get("risk_per_trade_pct", 1.0) / 100.0
        sim = TradeSimulator(initial_balance, pip_size=pip_sz)
        sim.record_equity(timestamps[0])

        for i in range(n):
            # Update open positions first
            sim.update(highs[i], lows[i], closes[i], timestamps[i])

            # Process signal
            if signals[i] != 0 and sim.open_position is None:
                sl_dist = sl_distances[i] if not np.isnan(sl_distances[i]) else 0.01
                tp_dist = tp_distances[i] if not np.isnan(tp_distances[i]) else 0.02

                # Position sizing from risk
                sl_pips = sl_dist / pip_sz
                if sl_pips <= 0:
                    sl_pips = 100
                volume = max(0.01, round((sim.balance * risk_pct) / (sl_pips * PIP_VALUE), 2))
                volume = min(volume, 5.0)  # cap at 5 lots

                if signals[i] == 1:  # BUY
                    sl = closes[i] - sl_dist
                    tp = closes[i] + tp_dist
                    sim.open_trade("buy", closes[i], sl, tp, volume, timestamps[i])
                elif signals[i] == -1:  # SELL
                    sl = closes[i] + sl_dist
                    tp = closes[i] - tp_dist
                    sim.open_trade("sell", closes[i], sl, tp, volume, timestamps[i])

            # Record equity periodically
            if i % 5 == 0 or i == n - 1:
                sim.record_equity(timestamps[i])

        # Force close remaining
        sim.force_close(closes[-1], timestamps[-1])
        sim.record_equity(timestamps[-1])

        config = type("Config", (), {
            "initial_balance": initial_balance,
            "symbol": candles[0].symbol if candles else "EURUSD",
            "timeframe": candles[0].timeframe.value if candles else "1d",
            "start_date": timestamps[0],
            "end_date": timestamps[-1],
            "total_candles": n,
        })()
        return sim.trades, sim.equity_curve, config

    # ------------------------------------------------------------------
    # Signal generators per template
    # ------------------------------------------------------------------

    def _signals_ema_crossover(self, genes, opens, highs, lows, closes, n):
        fast_p = max(2, int(genes.get("fast_ma_period", 12)))
        slow_p = max(fast_p + 1, int(genes.get("slow_ma_period", 50)))
        atr_p = max(2, int(genes.get("atr_period", 14)))
        sl_mult = genes.get("stop_loss_atr_mult", 2.0)
        tp_mult = genes.get("take_profit_atr_mult", 3.0)
        adx_thresh = genes.get("adx_threshold", 25.0)

        fast_ema = ema(closes, fast_p)
        slow_ema = ema(closes, slow_p)
        atr_vals = atr(highs, lows, closes, atr_p)
        adx_vals = adx(highs, lows, closes, min(atr_p, 14))

        signals = np.zeros(n)
        sl_dist = np.full(n, np.nan)
        tp_dist = np.full(n, np.nan)

        for i in range(1, n):
            if np.isnan(fast_ema[i]) or np.isnan(slow_ema[i]) or np.isnan(fast_ema[i-1]):
                continue
            adx_ok = np.isnan(adx_vals[i]) or adx_vals[i] >= adx_thresh
            a = atr_vals[i] if not np.isnan(atr_vals[i]) else 0.001
            if fast_ema[i] > slow_ema[i] and fast_ema[i-1] <= slow_ema[i-1] and adx_ok:
                signals[i] = 1
                sl_dist[i] = a * sl_mult
                tp_dist[i] = a * tp_mult
            elif fast_ema[i] < slow_ema[i] and fast_ema[i-1] >= slow_ema[i-1] and adx_ok:
                signals[i] = -1
                sl_dist[i] = a * sl_mult
                tp_dist[i] = a * tp_mult

        return signals, sl_dist, tp_dist

    def _signals_macd_trend(self, genes, opens, highs, lows, closes, n):
        fast_p = max(2, int(genes.get("fast_ma_period", 12)))
        slow_p = max(fast_p + 1, int(genes.get("slow_ma_period", 26)))
        atr_p = max(2, int(genes.get("atr_period", 14)))
        sl_mult = genes.get("stop_loss_atr_mult", 2.0)
        tp_mult = genes.get("take_profit_atr_mult", 3.0)
        adx_thresh = genes.get("adx_threshold", 25.0)

        macd_line, sig_line, hist = macd(closes, fast_p, slow_p)
        atr_vals = atr(highs, lows, closes, atr_p)
        adx_vals = adx(highs, lows, closes, min(atr_p, 14))

        signals = np.zeros(n)
        sl_dist = np.full(n, np.nan)
        tp_dist = np.full(n, np.nan)

        for i in range(1, n):
            if np.isnan(hist[i]) or np.isnan(hist[i-1]):
                continue
            adx_ok = np.isnan(adx_vals[i]) or adx_vals[i] >= adx_thresh
            a = atr_vals[i] if not np.isnan(atr_vals[i]) else 0.001
            if hist[i] > 0 and hist[i-1] <= 0 and adx_ok:
                signals[i] = 1
                sl_dist[i] = a * sl_mult
                tp_dist[i] = a * tp_mult
            elif hist[i] < 0 and hist[i-1] >= 0 and adx_ok:
                signals[i] = -1
                sl_dist[i] = a * sl_mult
                tp_dist[i] = a * tp_mult

        return signals, sl_dist, tp_dist

    def _signals_rsi_mean_reversion(self, genes, opens, highs, lows, closes, n):
        rsi_p = max(2, int(genes.get("rsi_period", 14)))
        rsi_os = genes.get("rsi_oversold", 30.0)
        rsi_ob = genes.get("rsi_overbought", 70.0)
        bb_p = max(2, int(genes.get("bb_period", 20)))
        bb_s = genes.get("bb_std", 2.0)
        sl_pct = genes.get("stop_loss_pct", 1.0) / 100.0
        tp_pct = genes.get("take_profit_pct", 1.5) / 100.0

        rsi_vals = rsi(closes, rsi_p)
        _, bb_upper, bb_lower = bollinger_bands(closes, bb_p, bb_s)

        signals = np.zeros(n)
        sl_dist = np.full(n, np.nan)
        tp_dist = np.full(n, np.nan)

        for i in range(1, n):
            if np.isnan(rsi_vals[i]) or np.isnan(rsi_vals[i-1]):
                continue
            # Buy when RSI crosses up from oversold + price near lower BB
            bb_ok_buy = np.isnan(bb_lower[i]) or closes[i] <= bb_lower[i] * 1.01
            bb_ok_sell = np.isnan(bb_upper[i]) or closes[i] >= bb_upper[i] * 0.99
            if rsi_vals[i] > rsi_os and rsi_vals[i-1] <= rsi_os and bb_ok_buy:
                signals[i] = 1
                sl_dist[i] = closes[i] * sl_pct
                tp_dist[i] = closes[i] * tp_pct
            elif rsi_vals[i] < rsi_ob and rsi_vals[i-1] >= rsi_ob and bb_ok_sell:
                signals[i] = -1
                sl_dist[i] = closes[i] * sl_pct
                tp_dist[i] = closes[i] * tp_pct

        return signals, sl_dist, tp_dist

    def _signals_bollinger_breakout(self, genes, opens, highs, lows, closes, n):
        bb_p = max(2, int(genes.get("bb_period", 20)))
        bb_s = genes.get("bb_std", 2.0)
        atr_p = max(2, int(genes.get("atr_period", 14)))
        sl_mult = genes.get("stop_loss_atr_mult", 2.0)
        tp_mult = genes.get("take_profit_atr_mult", 3.0)
        adx_thresh = genes.get("adx_threshold", 20.0)

        _, bb_upper, bb_lower = bollinger_bands(closes, bb_p, bb_s)
        atr_vals = atr(highs, lows, closes, atr_p)
        adx_vals = adx(highs, lows, closes, min(atr_p, 14))

        signals = np.zeros(n)
        sl_dist = np.full(n, np.nan)
        tp_dist = np.full(n, np.nan)

        for i in range(1, n):
            if np.isnan(bb_upper[i]) or np.isnan(bb_lower[i]):
                continue
            adx_ok = np.isnan(adx_vals[i]) or adx_vals[i] >= adx_thresh
            a = atr_vals[i] if not np.isnan(atr_vals[i]) else 0.001
            # Breakout above upper band
            if closes[i] > bb_upper[i] and closes[i-1] <= bb_upper[i-1] and adx_ok:
                signals[i] = 1
                sl_dist[i] = a * sl_mult
                tp_dist[i] = a * tp_mult
            # Breakout below lower band
            elif closes[i] < bb_lower[i] and closes[i-1] >= bb_lower[i-1] and adx_ok:
                signals[i] = -1
                sl_dist[i] = a * sl_mult
                tp_dist[i] = a * tp_mult

        return signals, sl_dist, tp_dist

    def _signals_atr_breakout(self, genes, opens, highs, lows, closes, n):
        atr_p = max(2, int(genes.get("atr_period", 14)))
        sl_mult = genes.get("stop_loss_atr_mult", 1.5)
        tp_mult = genes.get("take_profit_atr_mult", 4.0)
        adx_thresh = genes.get("adx_threshold", 20.0)
        fast_p = max(2, int(genes.get("fast_ma_period", 10)))
        slow_p = max(fast_p + 1, int(genes.get("slow_ma_period", 40)))

        atr_vals = atr(highs, lows, closes, atr_p)
        adx_vals = adx(highs, lows, closes, min(atr_p, 14))
        fast_ema = ema(closes, fast_p)
        slow_ema = ema(closes, slow_p)

        signals = np.zeros(n)
        sl_dist = np.full(n, np.nan)
        tp_dist = np.full(n, np.nan)

        for i in range(1, n):
            if np.isnan(atr_vals[i]) or np.isnan(atr_vals[i]):
                continue
            a = atr_vals[i]
            move = abs(closes[i] - closes[i-1])
            adx_ok = np.isnan(adx_vals[i]) or adx_vals[i] >= adx_thresh
            # Trend filter
            trend_up = np.isnan(fast_ema[i]) or np.isnan(slow_ema[i]) or fast_ema[i] > slow_ema[i]

            if move > a * 1.5 and adx_ok:
                if closes[i] > closes[i-1] and trend_up:
                    signals[i] = 1
                    sl_dist[i] = a * sl_mult
                    tp_dist[i] = a * tp_mult
                elif closes[i] < closes[i-1] and not trend_up:
                    signals[i] = -1
                    sl_dist[i] = a * sl_mult
                    tp_dist[i] = a * tp_mult

        return signals, sl_dist, tp_dist


# Singleton
real_backtester = RealBacktester()
