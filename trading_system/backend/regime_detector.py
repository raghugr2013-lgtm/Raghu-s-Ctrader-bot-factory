"""
HYBRID TRADING SYSTEM - Market Regime Detection Engine

Intelligently classifies market conditions and enables strategy switching
"""

import logging
from typing import List, Optional, Tuple
from enum import Enum
from market_data_models import Candle

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market condition classification"""
    TRENDING = "trending"
    RANGING = "ranging"
    UNCERTAIN = "uncertain"


class RegimeDetector:
    """
    Detects market regime using multiple indicators
    
    Features:
    - ADX for trend strength
    - ATR for volatility
    - Choppiness Index for market state
    - Smooth switching with confirmation
    """
    
    def __init__(self, params: dict = None):
        default_params = {
            # ADX thresholds
            "adx_trending_threshold": 25,    # ADX > this = trending
            "adx_ranging_threshold": 18,     # ADX < this = ranging
            
            # Choppiness thresholds
            "chop_trending_threshold": 50,   # CI < this = trending
            "chop_ranging_threshold": 61.8,  # CI > this = ranging
            
            # ATR volatility check
            "atr_low_threshold": 0.7,        # ATR/ATR_MA < this = low vol
            
            # Smoothing parameters
            "regime_confirmation_candles": 5,  # Require 5 candles to confirm switch
            "regime_lookback": 10,            # Consider last 10 regime classifications
        }
        
        self.params = default_params
        if params:
            self.params.update(params)
        
        self.regime_history = []
        self.current_regime = MarketRegime.UNCERTAIN
        self.regime_strength = 0.0  # 0-100, confidence in current regime
    
    def detect_regime(
        self,
        adx: float,
        atr: float,
        atr_ma: float,
        choppiness: Optional[float]
    ) -> Tuple[MarketRegime, float]:
        """
        Detect current market regime
        
        Returns: (regime, confidence_score)
        """
        
        scores = {
            MarketRegime.TRENDING: 0,
            MarketRegime.RANGING: 0,
            MarketRegime.UNCERTAIN: 0,
        }
        
        # ADX Analysis (weight: 40%)
        if adx >= self.params["adx_trending_threshold"]:
            scores[MarketRegime.TRENDING] += 40
        elif adx <= self.params["adx_ranging_threshold"]:
            scores[MarketRegime.RANGING] += 40
        else:
            # Middle zone
            scores[MarketRegime.UNCERTAIN] += 40
        
        # Choppiness Analysis (weight: 35%)
        if choppiness is not None:
            if choppiness < self.params["chop_trending_threshold"]:
                scores[MarketRegime.TRENDING] += 35
            elif choppiness > self.params["chop_ranging_threshold"]:
                scores[MarketRegime.RANGING] += 35
            else:
                scores[MarketRegime.UNCERTAIN] += 35
        else:
            # If no choppiness data, split based on ADX
            if adx > 20:
                scores[MarketRegime.TRENDING] += 17
                scores[MarketRegime.UNCERTAIN] += 18
            else:
                scores[MarketRegime.RANGING] += 17
                scores[MarketRegime.UNCERTAIN] += 18
        
        # ATR/Volatility Analysis (weight: 25%)
        atr_ratio = atr / atr_ma if atr_ma > 0 else 1.0
        
        if atr_ratio < self.params["atr_low_threshold"]:
            # Low volatility favors ranging
            scores[MarketRegime.RANGING] += 25
        elif atr_ratio > 1.2:
            # High volatility can be trending or breakout
            scores[MarketRegime.TRENDING] += 15
            scores[MarketRegime.UNCERTAIN] += 10
        else:
            # Normal volatility
            scores[MarketRegime.UNCERTAIN] += 25
        
        # Determine regime
        best_regime = max(scores, key=scores.get)
        confidence = scores[best_regime]
        
        return best_regime, confidence
    
    def update_regime(
        self,
        adx: float,
        atr: float,
        atr_ma: float,
        choppiness: Optional[float]
    ) -> MarketRegime:
        """
        Update regime with smoothing/confirmation logic
        
        Returns: Current confirmed regime
        """
        
        # Detect instantaneous regime
        detected_regime, confidence = self.detect_regime(adx, atr, atr_ma, choppiness)
        
        # Add to history
        self.regime_history.append(detected_regime)
        
        # Keep only recent history
        if len(self.regime_history) > self.params["regime_lookback"]:
            self.regime_history = self.regime_history[-self.params["regime_lookback"]:]
        
        # Check for regime switch confirmation
        if len(self.regime_history) >= self.params["regime_confirmation_candles"]:
            recent = self.regime_history[-self.params["regime_confirmation_candles"]:]
            
            # Count occurrences
            regime_counts = {}
            for r in recent:
                regime_counts[r] = regime_counts.get(r, 0) + 1
            
            # Find most common regime
            most_common_regime = max(regime_counts, key=regime_counts.get)
            most_common_count = regime_counts[most_common_regime]
            
            # Require strong consensus (at least 60% of recent candles)
            required_count = int(self.params["regime_confirmation_candles"] * 0.6)
            
            if most_common_count >= required_count:
                # Strong consensus - switch regime
                if most_common_regime != self.current_regime:
                    logger.info(f"🔄 Regime switch: {self.current_regime.value} → {most_common_regime.value} "
                              f"(confidence: {most_common_count}/{self.params['regime_confirmation_candles']})")
                    self.current_regime = most_common_regime
                    self.regime_strength = (most_common_count / self.params['regime_confirmation_candles']) * 100
        
        return self.current_regime
    
    def get_regime_info(self) -> dict:
        """Get current regime information"""
        return {
            "regime": self.current_regime,
            "strength": self.regime_strength,
            "history_length": len(self.regime_history),
        }
