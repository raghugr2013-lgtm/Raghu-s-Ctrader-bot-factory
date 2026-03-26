"""
Walk-Forward Testing Engine - Data Models
Phase 5: Advanced Strategy Validation
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
from datetime import datetime, timezone
import uuid
from enum import Enum

from backtest_models import PerformanceMetrics


class SegmentType(str, Enum):
    """Segment type"""
    TRAINING = "training"
    TESTING = "testing"


class WalkForwardSegment(BaseModel):
    """Individual walk-forward segment"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    segment_number: int
    segment_type: SegmentType
    
    # Date range
    start_date: datetime
    end_date: datetime
    
    # Optimized parameters (if training)
    optimized_params: Optional[Dict] = None
    
    # Performance metrics (if testing)
    metrics: Optional[PerformanceMetrics] = None
    
    # Results
    backtest_id: Optional[str] = None
    total_trades: int = 0
    net_profit: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_percent: float = 0.0
    sharpe_ratio: float = 0.0


class StabilityMetrics(BaseModel):
    """Stability analysis across segments"""
    
    # Consistency scores (0-100)
    profit_factor_consistency: float
    drawdown_stability: float
    win_rate_consistency: float
    sharpe_consistency: float
    
    # Statistical measures
    profit_factor_cv: float  # Coefficient of variation
    drawdown_cv: float
    win_rate_cv: float
    sharpe_cv: float
    
    # Average values across testing segments
    avg_profit_factor: float
    avg_drawdown: float
    avg_win_rate: float
    avg_sharpe: float
    
    # Standard deviations
    std_profit_factor: float
    std_drawdown: float
    std_win_rate: float
    std_sharpe: float


class WalkForwardScore(BaseModel):
    """Overall walk-forward stability score"""
    
    # Component scores (0-100 each)
    profit_factor_consistency: float
    drawdown_stability: float
    win_rate_consistency: float
    sharpe_consistency: float
    
    # Overall stability score (0-100)
    total_score: float
    
    # Grade
    grade: str  # S, A, B, C, D, F
    
    # Recommendation
    is_deployable: bool  # True if score >= 70
    
    # Insights
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]


class WalkForwardConfig(BaseModel):
    """Walk-forward testing configuration"""
    
    # Symbol and timeframe
    symbol: str
    timeframe: str
    
    # Date range
    start_date: datetime
    end_date: datetime
    
    # Window sizes (in days)
    training_window_days: int = 730  # 2 years
    testing_window_days: int = 365  # 1 year
    step_size_days: int = 365  # Roll forward by 1 year
    
    # Strategy parameters to optimize
    param_ranges: Dict[str, List]  # e.g., {"fast_ma": [10, 20, 30], "slow_ma": [40, 50, 60]}
    
    # Backtesting settings
    initial_balance: float = 10000.0
    
    # Optimization criteria
    optimization_metric: str = "sharpe_ratio"  # or "profit_factor", "win_rate", etc.


class WalkForwardResult(BaseModel):
    """Complete walk-forward test result"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    strategy_name: str
    
    # Configuration
    config: WalkForwardConfig
    
    # All segments (training + testing)
    segments: List[WalkForwardSegment]
    
    # Testing segments only (for stability analysis)
    testing_segments: List[WalkForwardSegment]
    
    # Stability analysis
    stability_metrics: StabilityMetrics
    
    # Overall score
    walk_forward_score: WalkForwardScore
    
    # Best parameters found
    best_params: Dict
    
    # Execution metadata
    total_segments: int
    execution_time_seconds: float
    status: str = "completed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Request Models
class WalkForwardRequest(BaseModel):
    """Request to run walk-forward test"""
    session_id: str
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    training_window_days: int = 730
    testing_window_days: int = 365
    step_size_days: int = 365
    initial_balance: float = 10000.0
    
    # Parameter ranges for optimization
    fast_ma_range: List[int] = [10, 20, 30]
    slow_ma_range: List[int] = [40, 50, 60]
    
    optimization_metric: str = "sharpe_ratio"


# Response Models
class WalkForwardSummary(BaseModel):
    """Summary for listing walk-forward tests"""
    id: str
    strategy_name: str
    symbol: str
    timeframe: str
    total_segments: int
    stability_score: float
    grade: str
    is_deployable: bool
    created_at: datetime
