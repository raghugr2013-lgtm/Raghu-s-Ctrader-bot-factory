"""
Monte Carlo Simulation Engine - Data Models
Phase 6: Probabilistic Risk Analysis
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
from datetime import datetime, timezone
import uuid
from enum import Enum

from backtest_models import TradeRecord


class ResamplingMethod(str, Enum):
    """Trade resampling method"""
    SHUFFLE = "shuffle"  # Randomize trade order
    BOOTSTRAP = "bootstrap"  # Sample with replacement
    SKIP_RANDOM = "skip_random"  # Randomly skip trades


class MonteCarloConfig(BaseModel):
    """Monte Carlo simulation configuration"""
    
    # Number of simulations (Phase 2: increased to 1000)
    num_simulations: int = 1000
    
    # Resampling method
    resampling_method: ResamplingMethod = ResamplingMethod.SHUFFLE
    
    # Parameters
    skip_probability: float = 0.1  # For skip_random method
    confidence_level: float = 0.95  # 95% confidence intervals
    
    # Initial balance
    initial_balance: float = 10000.0
    
    # Risk thresholds
    ruin_threshold_percent: float = 50.0  # Consider ruined if balance drops 50%
    
    # Phase 2: Stability thresholds
    high_variance_threshold: float = 0.30  # Reject if variance/mean > 30%
    min_profitable_simulations_pct: float = 70.0  # At least 70% sims must be profitable


class SimulationRun(BaseModel):
    """Single Monte Carlo simulation run result"""
    
    run_number: int
    final_balance: float
    final_equity: float
    max_drawdown: float
    max_drawdown_percent: float
    total_return: float
    total_return_percent: float
    is_profitable: bool
    is_ruined: bool  # Hit ruin threshold


class MonteCarloMetrics(BaseModel):
    """Aggregated Monte Carlo metrics"""
    
    # Final balance distribution
    worst_case_balance: float
    best_case_balance: float
    average_balance: float
    median_balance: float
    
    # Balance percentiles
    balance_5th_percentile: float
    balance_25th_percentile: float
    balance_75th_percentile: float
    balance_95th_percentile: float
    
    # Drawdown distribution
    worst_case_drawdown: float
    best_case_drawdown: float
    average_drawdown: float
    median_drawdown: float
    
    # Drawdown percentiles
    drawdown_5th_percentile: float
    drawdown_95th_percentile: float
    
    # Return distribution
    average_return_percent: float
    median_return_percent: float
    return_std_dev: float
    
    # Probabilities
    profit_probability: float  # % of runs that are profitable
    ruin_probability: float  # % of runs that hit ruin threshold
    
    # Expected values
    expected_final_balance: float
    expected_return_percent: float
    
    # Confidence intervals (95% by default)
    balance_ci_lower: float
    balance_ci_upper: float
    drawdown_ci_lower: float
    drawdown_ci_upper: float
    return_ci_lower: float
    return_ci_upper: float


class MonteCarloScore(BaseModel):
    """Monte Carlo robustness score"""
    
    # Component scores (0-100)
    drawdown_consistency_score: float  # Lower variance = higher score
    profit_stability_score: float  # Higher profit prob = higher score
    ruin_resistance_score: float  # Lower ruin prob = higher score
    
    # Phase 2: Additional stability metrics
    variance_stability_score: float = 0.0  # Coefficient of variation score
    downside_protection_score: float = 0.0  # Score based on worst-case scenarios
    
    # Overall robustness score (0-100)
    total_score: float
    
    # Grade
    grade: str  # S, A, B, C, D, F
    
    # Risk assessment
    risk_level: str  # "Low", "Medium", "High", "Very High"
    is_robust: bool  # True if score >= 70
    
    # Phase 2: High variance flag
    is_high_variance: bool = False  # True if variance/mean > threshold
    
    # Insights
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]


class MonteCarloResult(BaseModel):
    """Complete Monte Carlo simulation result"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    backtest_id: str
    strategy_name: str
    
    # Configuration
    config: MonteCarloConfig
    
    # All simulation runs
    simulation_runs: List[SimulationRun]
    
    # Aggregated metrics
    metrics: MonteCarloMetrics
    
    # Robustness score
    monte_carlo_score: MonteCarloScore
    
    # Execution metadata
    total_simulations: int
    original_trades_count: int
    execution_time_seconds: float
    status: str = "completed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Request Models
class MonteCarloRequest(BaseModel):
    """Request to run Monte Carlo simulation"""
    session_id: str
    backtest_id: str
    strategy_name: str
    num_simulations: int = 1000
    resampling_method: str = "shuffle"
    skip_probability: float = 0.1
    confidence_level: float = 0.95
    ruin_threshold_percent: float = 50.0


# Response Models
class MonteCarloSummary(BaseModel):
    """Summary for listing Monte Carlo results"""
    id: str
    strategy_name: str
    num_simulations: int
    profit_probability: float
    ruin_probability: float
    robustness_score: float
    grade: str
    is_robust: bool
    created_at: datetime
