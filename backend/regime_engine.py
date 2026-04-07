"""
Market Regime Detection Engine
Classifies candles into regimes using ADX, ATR, Bollinger Band width, and MA slope.
"""

import math
import statistics
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from regime_models import (
    MarketRegime,
    RegimeCandle,
    RegimeSegment,
    RegimeDistribution,
    RegimeTradeMetrics,
    RegimeAnalysisResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Technical Indicator Calculators
# ---------------------------------------------------------------------------

def _ema(values: List[float], period: int) -> List[Optional[float]]:
    """Exponential Moving Average."""
    out: List[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2 / (period + 1)
    sma = sum(values[:period]) / period
    out[period - 1] = sma
    prev = sma
    for i in range(period, len(values)):
        val = values[i] * k + prev * (1 - k)
        out[i] = val
        prev = val
    return out


def _sma(values: List[float], period: int) -> List[Optional[float]]:
    """Simple Moving Average."""
    out: List[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return out
    window_sum = sum(values[:period])
    out[period - 1] = window_sum / period
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        out[i] = window_sum / period
    return out


def _true_range(highs: List[float], lows: List[float], closes: List[float]) -> List[float]:
    """True Range series."""
    tr = [highs[0] - lows[0]]
    for i in range(1, len(highs)):
        tr.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    return tr


def calc_atr(
    highs: List[float], lows: List[float], closes: List[float], period: int
) -> List[Optional[float]]:
    """Average True Range."""
    tr = _true_range(highs, lows, closes)
    return _ema(tr, period)


def calc_adx(
    highs: List[float], lows: List[float], closes: List[float], period: int
) -> List[Optional[float]]:
    """Average Directional Index."""
    n = len(highs)
    out: List[Optional[float]] = [None] * n
    if n < period * 2:
        return out

    # +DM / -DM
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        plus_dm[i] = up if up > dn and up > 0 else 0
        minus_dm[i] = dn if dn > up and dn > 0 else 0

    tr = _true_range(highs, lows, closes)

    # Smoothed via Wilder method
    sm_tr = [0.0] * n
    sm_plus = [0.0] * n
    sm_minus = [0.0] * n
    sm_tr[period] = sum(tr[1:period + 1])
    sm_plus[period] = sum(plus_dm[1:period + 1])
    sm_minus[period] = sum(minus_dm[1:period + 1])
    for i in range(period + 1, n):
        sm_tr[i] = sm_tr[i - 1] - sm_tr[i - 1] / period + tr[i]
        sm_plus[i] = sm_plus[i - 1] - sm_plus[i - 1] / period + plus_dm[i]
        sm_minus[i] = sm_minus[i - 1] - sm_minus[i - 1] / period + minus_dm[i]

    # DI+ / DI- / DX
    dx_vals: List[Optional[float]] = [None] * n
    for i in range(period, n):
        if sm_tr[i] == 0:
            continue
        di_plus = (sm_plus[i] / sm_tr[i]) * 100
        di_minus = (sm_minus[i] / sm_tr[i]) * 100
        di_sum = di_plus + di_minus
        if di_sum > 0:
            dx_vals[i] = abs(di_plus - di_minus) / di_sum * 100

    # ADX = smoothed DX
    start = period
    while start < n and dx_vals[start] is None:
        start += 1
    first_valid = [v for v in dx_vals[start:start + period] if v is not None]
    if len(first_valid) < period:
        return out
    adx_val = sum(first_valid) / period
    idx = start + period - 1
    if idx < n:
        out[idx] = adx_val
    for i in range(idx + 1, n):
        dxv = dx_vals[i]
        if dxv is not None:
            adx_val = (adx_val * (period - 1) + dxv) / period
            out[i] = adx_val

    return out


def calc_bb_width(closes: List[float], period: int, num_std: float) -> List[Optional[float]]:
    """Bollinger Band width as percentage of middle band."""
    out: List[Optional[float]] = [None] * len(closes)
    if len(closes) < period:
        return out
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1:i + 1]
        mid = sum(window) / period
        if mid == 0:
            continue
        sd = math.sqrt(sum((v - mid) ** 2 for v in window) / period)
        width = (num_std * 2 * sd) / mid * 100  # percentage
        out[i] = width
    return out


def calc_ma_slope(closes: List[float], period: int, lookback: int = 5) -> List[Optional[float]]:
    """Slope of the SMA over `lookback` bars, normalised by price."""
    sma_vals = _sma(closes, period)
    out: List[Optional[float]] = [None] * len(closes)
    for i in range(lookback, len(closes)):
        cur = sma_vals[i]
        prev = sma_vals[i - lookback]
        if cur is not None and prev is not None and prev != 0:
            out[i] = (cur - prev) / prev * 100
    return out


# ---------------------------------------------------------------------------
# Regime Classifier
# ---------------------------------------------------------------------------

class RegimeClassifier:
    """Classify each candle into a market regime."""

    def __init__(
        self,
        adx_period: int = 14,
        atr_period: int = 14,
        bb_period: int = 20,
        bb_std: float = 2.0,
        ma_period: int = 50,
        adx_trend_threshold: float = 25.0,
        atr_high_vol_pct: float = 75.0,
        atr_low_vol_pct: float = 25.0,
    ):
        self.adx_period = adx_period
        self.atr_period = atr_period
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.ma_period = ma_period
        self.adx_thresh = adx_trend_threshold
        self.atr_hi_pct = atr_high_vol_pct
        self.atr_lo_pct = atr_low_vol_pct

    def classify(
        self,
        timestamps: List[str],
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
    ) -> List[RegimeCandle]:
        n = len(closes)

        adx = calc_adx(highs, lows, closes, self.adx_period)
        atr = calc_atr(highs, lows, closes, self.atr_period)
        bb_w = calc_bb_width(closes, self.bb_period, self.bb_std)
        ma_sl = calc_ma_slope(closes, self.ma_period)

        # Compute ATR as percentage of price
        atr_pct = [None] * n
        for i in range(n):
            if atr[i] is not None and closes[i] > 0:
                atr_pct[i] = (atr[i] / closes[i]) * 100

        # Percentile thresholds for ATR%
        valid_atr = [v for v in atr_pct if v is not None]
        if valid_atr:
            sorted_atr = sorted(valid_atr)
            hi_idx = min(int(len(sorted_atr) * self.atr_hi_pct / 100), len(sorted_atr) - 1)
            lo_idx = min(int(len(sorted_atr) * self.atr_lo_pct / 100), len(sorted_atr) - 1)
            atr_hi_thresh = sorted_atr[hi_idx]
            atr_lo_thresh = sorted_atr[lo_idx]
        else:
            atr_hi_thresh = 999
            atr_lo_thresh = 0

        results: List[RegimeCandle] = []
        for i in range(n):
            adx_v = adx[i] or 0
            atr_v = atr[i] or 0
            atr_pct_v = atr_pct[i] or 0
            bb_v = bb_w[i] or 0
            slope_v = ma_sl[i] or 0

            regime = self._decide(adx_v, atr_pct_v, slope_v, atr_hi_thresh, atr_lo_thresh)

            results.append(RegimeCandle(
                timestamp=timestamps[i],
                open=opens[i],
                high=highs[i],
                low=lows[i],
                close=closes[i],
                volume=volumes[i],
                regime=regime,
                adx=round(adx_v, 2),
                atr=round(atr_v, 6),
                atr_pct=round(atr_pct_v, 4),
                bb_width=round(bb_v, 4),
                ma_slope=round(slope_v, 4),
            ))

        return results

    def _decide(
        self,
        adx: float,
        atr_pct: float,
        slope: float,
        atr_hi: float,
        atr_lo: float,
    ) -> MarketRegime:
        # Priority: extreme volatility > trend > range > low vol
        if atr_pct >= atr_hi:
            return MarketRegime.HIGH_VOLATILITY
        if adx >= self.adx_thresh:
            return MarketRegime.TRENDING_UP if slope >= 0 else MarketRegime.TRENDING_DOWN
        if atr_pct <= atr_lo:
            return MarketRegime.LOW_VOLATILITY
        return MarketRegime.RANGING


# ---------------------------------------------------------------------------
# Regime Analyser (segments, distribution, trade mapping)
# ---------------------------------------------------------------------------

class RegimeAnalyser:
    """Analyse regimes and map trades to them."""

    @staticmethod
    def distribution(candles: List[RegimeCandle]) -> List[RegimeDistribution]:
        counts: Dict[MarketRegime, int] = {}
        for c in candles:
            counts[c.regime] = counts.get(c.regime, 0) + 1
        total = len(candles) or 1
        return [
            RegimeDistribution(regime=r, candle_count=cnt, percent=round(cnt / total * 100, 1))
            for r, cnt in sorted(counts.items(), key=lambda x: -x[1])
        ]

    @staticmethod
    def segments(candles: List[RegimeCandle]) -> List[RegimeSegment]:
        if not candles:
            return []
        segs: List[RegimeSegment] = []
        cur_regime = candles[0].regime
        start_ts = candles[0].timestamp
        count = 1
        atrs = [candles[0].atr]
        adxs = [candles[0].adx]

        for c in candles[1:]:
            if c.regime == cur_regime:
                count += 1
                atrs.append(c.atr)
                adxs.append(c.adx)
            else:
                segs.append(RegimeSegment(
                    regime=cur_regime, start=start_ts, end=candles[candles.index(c) - 1].timestamp if candles.index(c) > 0 else start_ts,
                    candle_count=count,
                    avg_atr=round(sum(atrs) / len(atrs), 6),
                    avg_adx=round(sum(adxs) / len(adxs), 2),
                ))
                cur_regime = c.regime
                start_ts = c.timestamp
                count = 1
                atrs = [c.atr]
                adxs = [c.adx]

        segs.append(RegimeSegment(
            regime=cur_regime, start=start_ts, end=candles[-1].timestamp,
            candle_count=count,
            avg_atr=round(sum(atrs) / len(atrs), 6),
            avg_adx=round(sum(adxs) / len(adxs), 2),
        ))
        return segs

    @staticmethod
    def map_trades_to_regimes(
        regime_candles: List[RegimeCandle],
        trades: List[Dict],
    ) -> Dict[MarketRegime, List[Dict]]:
        """Map each trade to the regime active at its entry time."""
        # Build time -> regime lookup
        regime_lookup: Dict[str, MarketRegime] = {}
        for c in regime_candles:
            regime_lookup[c.timestamp] = c.regime

        # Sort regime timestamps for nearest-match
        sorted_ts = sorted(regime_lookup.keys())

        mapped: Dict[MarketRegime, List[Dict]] = {r: [] for r in MarketRegime}

        for t in trades:
            entry = t.get("entry_time", "")
            if isinstance(entry, datetime):
                entry = entry.isoformat()
            entry_str = str(entry)

            # Find closest regime candle <= entry_time
            regime = MarketRegime.RANGING  # default
            for ts in reversed(sorted_ts):
                if ts <= entry_str:
                    regime = regime_lookup[ts]
                    break

            mapped[regime].append(t)

        return mapped

    @staticmethod
    def compute_regime_metrics(
        mapped: Dict[MarketRegime, List[Dict]],
        initial_balance: float,
    ) -> List[RegimeTradeMetrics]:
        metrics: List[RegimeTradeMetrics] = []
        for regime, trades in mapped.items():
            closed = [t for t in trades if t.get("status") == "closed" and t.get("profit_loss") is not None]
            if not closed:
                continue

            pnls = [t["profit_loss"] for t in closed]
            winners = [p for p in pnls if p > 0]
            losers = [p for p in pnls if p < 0]

            gp = sum(winners)
            gl = abs(sum(losers))
            net = gp - gl
            pf = gp / gl if gl > 0 else (gp if gp > 0 else 0)
            wr = len(winners) / len(closed) * 100 if closed else 0
            avg = net / len(closed) if closed else 0

            # Sharpe
            if len(pnls) > 1:
                rets = [p / initial_balance for p in pnls]
                avg_r = statistics.mean(rets)
                sd = statistics.stdev(rets)
                sharpe = (avg_r / sd) * math.sqrt(252) if sd > 0 else 0
            else:
                sharpe = 0

            metrics.append(RegimeTradeMetrics(
                regime=regime,
                trade_count=len(closed),
                win_rate=round(wr, 2),
                net_profit=round(net, 2),
                gross_profit=round(gp, 2),
                gross_loss=round(gl, 2),
                profit_factor=round(pf, 4),
                sharpe_ratio=round(sharpe, 2),
                avg_trade=round(avg, 2),
                best_trade=round(max(pnls), 2),
                worst_trade=round(min(pnls), 2),
            ))

        return sorted(metrics, key=lambda m: -m.net_profit)

    @staticmethod
    def generate_insights(
        distribution: List[RegimeDistribution],
        regime_perf: List[RegimeTradeMetrics],
    ) -> Tuple[List[str], List[str]]:
        insights: List[str] = []
        recs: List[str] = []

        # Distribution insights
        for d in distribution:
            if d.percent > 40:
                insights.append(f"Market is dominantly {d.regime.value} ({d.percent}% of candles)")
        hi_vol = next((d for d in distribution if d.regime == MarketRegime.HIGH_VOLATILITY), None)
        if hi_vol and hi_vol.percent > 30:
            insights.append(f"High volatility regime is significant ({hi_vol.percent}%)")
            recs.append("Consider wider stops during high-volatility periods")

        # Performance insights
        if regime_perf:
            best = regime_perf[0]
            worst = regime_perf[-1]
            insights.append(f"Best performing regime: {best.regime.value} (profit: ${best.net_profit:.0f}, WR: {best.win_rate:.0f}%)")
            if worst.net_profit < 0:
                insights.append(f"Worst performing regime: {worst.regime.value} (loss: ${worst.net_profit:.0f})")
                recs.append(f"Consider disabling strategy during {worst.regime.value} conditions")

            # Regime-specific recs
            for m in regime_perf:
                if m.win_rate < 40 and m.trade_count >= 5:
                    recs.append(f"Low win rate ({m.win_rate:.0f}%) in {m.regime.value} — add regime filter")
                if m.profit_factor > 2.0 and m.trade_count >= 10:
                    insights.append(f"Strong edge in {m.regime.value} (PF: {m.profit_factor:.1f})")

        return insights, recs
