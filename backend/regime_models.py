"""
Market Regime Detection Engine - Data Models
Classifies market conditions: Trending, Ranging, High Volatility, Low Volatility.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
from datetime import datetime, timezone
from enum import Enum
import uuid


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


class RegimeCandle(BaseModel):
    """Single candle with regime label and indicator values."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    regime: MarketRegime
    adx: float
    atr: float
    atr_pct: float
    bb_width: float
    ma_slope: float


class RegimeSegment(BaseModel):
    """Contiguous segment of a single regime."""
    regime: MarketRegime
    start: str
    end: str
    candle_count: int
    avg_atr: float
    avg_adx: float


class RegimeDistribution(BaseModel):
    """Distribution of regimes across the data."""
    regime: MarketRegime
    candle_count: int
    percent: float


class RegimeTradeMetrics(BaseModel):
    """Strategy performance within one regime."""
    regime: MarketRegime
    trade_count: int
    win_rate: float
    net_profit: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    sharpe_ratio: float
    avg_trade: float
    best_trade: float
    worst_trade: float


class RegimeAnalysisResult(BaseModel):
    """Full regime analysis output."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    backtest_id: str = ""

    # Config
    symbol: str
    timeframe: str
    total_candles: int

    # Indicator parameters used
    adx_period: int
    atr_period: int
    bb_period: int
    bb_std: float
    ma_period: int

    # Thresholds used
    adx_trend_threshold: float
    atr_high_vol_percentile: float
    atr_low_vol_percentile: float

    # Regime distribution
    distribution: List[RegimeDistribution]
    segments: List[RegimeSegment]
    dominant_regime: MarketRegime

    # Per-regime strategy performance (only when trades provided)
    regime_performance: List[RegimeTradeMetrics] = []
    best_regime: Optional[MarketRegime] = None
    worst_regime: Optional[MarketRegime] = None

    # Insights
    insights: List[str] = []
    recommendations: List[str] = []

    execution_time_seconds: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Request models

class RegimeDetectRequest(BaseModel):
    """Detect regimes on raw candle data from DB."""
    session_id: str
    symbol: str
    timeframe: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    # Indicator params
    adx_period: int = 14
    atr_period: int = 14
    bb_period: int = 20
    bb_std: float = 2.0
    ma_period: int = 50
    # Thresholds
    adx_trend_threshold: float = 25.0
    atr_high_vol_percentile: float = 75.0
    atr_low_vol_percentile: float = 25.0


class RegimeBacktestRequest(BaseModel):
    """Analyze strategy performance per regime using backtest data."""
    session_id: str
    backtest_id: str
    # Indicator params (same defaults)
    adx_period: int = 14
    atr_period: int = 14
    bb_period: int = 20
    bb_std: float = 2.0
    ma_period: int = 50
    adx_trend_threshold: float = 25.0
    atr_high_vol_percentile: float = 75.0
    atr_low_vol_percentile: float = 25.0
