"""
MARKET REGIME DETECTOR

Classifies market conditions into distinct regimes:
- Trending vs Ranging
- High vs Low Volatility
- Bullish vs Bearish

Used by regime-adaptive trading system to select appropriate strategy.
"""

import logging
from typing import List, Tuple, Optional
from enum import Enum

from market_data_models import Candle
from no_trade_zone_strategy import calculate_adx, calculate_choppiness_index
from improved_eurusd_strategy import calculate_atr
from backtest_real_engine import _calculate_ema

logger = logging.getLogger(__name__)


class TrendRegime(str, Enum):
    """Trend classification"""
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    RANGING = "ranging"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"
    UNCLEAR = "unclear"


class VolatilityRegime(str, Enum):
    """Volatility classification"""
    HIGH = "high_vol"
    MEDIUM = "medium_vol"
    LOW = "low_vol"


class MarketRegime:
    """Complete market regime classification"""
    
    def __init__(
        self,
        trend: TrendRegime,
        volatility: VolatilityRegime,
        adx: float,
        atr_percentile: float,
        choppiness: float,
        confidence: float
    ):
        self.trend = trend
        self.volatility = volatility
        self.adx = adx
        self.atr_percentile = atr_percentile
        self.choppiness = choppiness
        self.confidence = confidence
    
    def is_trending(self) -> bool:
        """Check if market is in trending regime"""
        return self.trend in [
            TrendRegime.STRONG_UPTREND,
            TrendRegime.UPTREND,
            TrendRegime.DOWNTREND,
            TrendRegime.STRONG_DOWNTREND
        ]
    
    def is_ranging(self) -> bool:
        """Check if market is in ranging regime"""
        return self.trend == TrendRegime.RANGING
    
    def is_bullish(self) -> bool:
        """Check if market is bullish"""
        return self.trend in [TrendRegime.STRONG_UPTREND, TrendRegime.UPTREND]
    
    def is_bearish(self) -> bool:
        """Check if market is bearish"""
        return self.trend in [TrendRegime.STRONG_DOWNTREND, TrendRegime.DOWNTREND]
    
    def is_high_volatility(self) -> bool:
        """Check if volatility is high"""
        return self.volatility == VolatilityRegime.HIGH
    
    def is_clear(self, min_confidence: float = 0.4) -> bool:
        """Check if regime is clear enough to trade"""
        return self.trend != TrendRegime.UNCLEAR and self.confidence > min_confidence
    
    def __str__(self):
        return f"Regime({self.trend.value}, {self.volatility.value}, conf={self.confidence:.2f})"


def detect_market_regime(
    candles: List[Candle],
    current_idx: int,
    lookback: int = 50
) -> Optional[MarketRegime]:
    """
    Detect current market regime
    
    Uses multiple indicators to classify market:
    - ADX: Trend strength
    - ATR: Volatility
    - Choppiness Index: Range-bound detection
    - EMA slope: Trend direction
    
    Returns MarketRegime object or None if insufficient data
    """
    
    if current_idx < lookback:
        return None
    
    # Calculate indicators
    adx_values = calculate_adx(candles, 14)
    atr_values = calculate_atr(candles, 14)
    choppiness_values = calculate_choppiness_index(candles, 14)
    ema_20 = _calculate_ema(candles, 20)
    ema_50 = _calculate_ema(candles, 50)
    ema_200 = _calculate_ema(candles, 200)
    
    if (adx_values[current_idx] is None or 
        atr_values[current_idx] is None or
        choppiness_values[current_idx] is None or
        ema_20[current_idx] is None or
        ema_50[current_idx] is None or
        ema_200[current_idx] is None):
        return None
    
    adx = adx_values[current_idx]
    atr = atr_values[current_idx]
    choppiness = choppiness_values[current_idx]
    current_price = candles[current_idx].close
    
    # === TREND REGIME DETECTION ===
    
    # 1. ADX-based trend strength
    # ADX > 25: Strong trend
    # ADX 20-25: Moderate trend
    # ADX < 20: Weak trend / ranging
    
    # 2. Choppiness Index
    # > 61.8: Very choppy (ranging)
    # 38.2-61.8: Moderate
    # < 38.2: Trending
    
    # 3. EMA alignment
    trend_direction = 0  # -1 = down, 0 = neutral, 1 = up
    
    if ema_20[current_idx] > ema_50[current_idx] > ema_200[current_idx]:
        trend_direction = 1  # Bullish alignment
    elif ema_20[current_idx] < ema_50[current_idx] < ema_200[current_idx]:
        trend_direction = -1  # Bearish alignment
    
    # Price position relative to EMAs
    above_200 = current_price > ema_200[current_idx]
    above_50 = current_price > ema_50[current_idx]
    above_20 = current_price > ema_20[current_idx]
    
    # Determine trend regime
    trend_confidence = 0.0
    
    if adx > 25 and choppiness < 45:
        # Strong trending market
        if trend_direction == 1 and above_200 and above_50:
            trend = TrendRegime.STRONG_UPTREND
            trend_confidence = min(adx / 40, 1.0)  # Scale ADX to confidence
        elif trend_direction == -1 and not above_200 and not above_50:
            trend = TrendRegime.STRONG_DOWNTREND
            trend_confidence = min(adx / 40, 1.0)
        elif trend_direction == 1:
            trend = TrendRegime.UPTREND
            trend_confidence = min(adx / 35, 0.8)
        elif trend_direction == -1:
            trend = TrendRegime.DOWNTREND
            trend_confidence = min(adx / 35, 0.8)
        else:
            trend = TrendRegime.UNCLEAR
            trend_confidence = 0.5
    
    elif adx > 20 and choppiness < 55:
        # Moderate trending market
        if trend_direction == 1 and above_50:
            trend = TrendRegime.UPTREND
            trend_confidence = min(adx / 30, 0.7)
        elif trend_direction == -1 and not above_50:
            trend = TrendRegime.DOWNTREND
            trend_confidence = min(adx / 30, 0.7)
        else:
            trend = TrendRegime.UNCLEAR
            trend_confidence = 0.4
    
    elif choppiness > 50 or adx < 20:
        # Ranging / choppy market (FURTHER RELAXED from 55 → 50 for more ranging detection)
        trend = TrendRegime.RANGING
        # Confidence based on how choppy (RELAXED: starts at choppiness 50 instead of 55)
        if choppiness > 50:
            trend_confidence = min((choppiness - 50) / 30 + 0.4, 1.0)  # Starts at 0.4 confidence
        else:
            trend_confidence = 0.5  # When ADX < 20 but choppiness not high
    
    else:
        # Unclear
        trend = TrendRegime.UNCLEAR
        trend_confidence = 0.3
    
    # === VOLATILITY REGIME DETECTION ===
    
    # Calculate ATR percentile over lookback period
    recent_atr = [atr_values[i] for i in range(current_idx - lookback, current_idx + 1) 
                  if atr_values[i] is not None]
    
    if not recent_atr:
        return None
    
    atr_percentile = sum(1 for x in recent_atr if x < atr) / len(recent_atr) * 100
    
    # Classify volatility
    if atr_percentile >= 70:
        volatility = VolatilityRegime.HIGH
    elif atr_percentile >= 40:
        volatility = VolatilityRegime.MEDIUM
    else:
        volatility = VolatilityRegime.LOW
    
    # Overall confidence
    # Weight: 60% trend confidence, 40% clarity (inverse of choppiness normalized)
    clarity_score = max(0, 1 - (choppiness / 100))
    overall_confidence = trend_confidence * 0.6 + clarity_score * 0.4
    
    return MarketRegime(
        trend=trend,
        volatility=volatility,
        adx=adx,
        atr_percentile=atr_percentile,
        choppiness=choppiness,
        confidence=overall_confidence
    )


def calculate_regime_statistics(
    candles: List[Candle],
    lookback: int = 50
) -> dict:
    """
    Calculate regime distribution over the dataset
    
    Returns dictionary with regime statistics
    """
    
    regime_counts = {
        "strong_uptrend": 0,
        "uptrend": 0,
        "ranging": 0,
        "downtrend": 0,
        "strong_downtrend": 0,
        "unclear": 0,
        "high_vol": 0,
        "medium_vol": 0,
        "low_vol": 0,
    }
    
    total_regimes = 0
    
    for i in range(lookback, len(candles)):
        regime = detect_market_regime(candles, i, lookback)
        
        if regime:
            total_regimes += 1
            regime_counts[regime.trend.value] += 1
            regime_counts[regime.volatility.value] += 1
    
    # Calculate percentages
    if total_regimes > 0:
        for key in ["strong_uptrend", "uptrend", "ranging", "downtrend", "strong_downtrend", "unclear"]:
            regime_counts[f"{key}_pct"] = regime_counts[key] / total_regimes * 100
        
        for key in ["high_vol", "medium_vol", "low_vol"]:
            regime_counts[f"{key}_pct"] = regime_counts[key] / total_regimes * 100
    
    regime_counts["total_periods"] = total_regimes
    
    return regime_counts
