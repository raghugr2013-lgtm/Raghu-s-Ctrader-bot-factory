"""
Portfolio Strategy Engine - Data Models
Phase 7: Multi-Strategy Portfolio Management
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
from datetime import datetime, timezone
from enum import Enum
import uuid


class AllocationMethod(str, Enum):
    """Portfolio allocation optimization method"""
    EQUAL_WEIGHT = "equal_weight"
    RISK_PARITY = "risk_parity"
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    MAX_DIVERSIFICATION = "max_diversification"


class PortfolioStrategy(BaseModel):
    """Individual strategy within a portfolio"""
    model_config = ConfigDict(extra="ignore")

    strategy_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    backtest_id: str  # Reference to a completed backtest
    symbol: str
    timeframe: str

    # Allocation
    weight: float = 0.0  # 0-1, fraction of capital allocated
    weight_percent: float = 0.0  # 0-100

    # Performance snapshot from backtest
    net_profit: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_percent: float = 0.0
    total_trades: int = 0
    strategy_score: float = 0.0

    # Daily returns series (stored as list of floats for correlation)
    daily_returns: List[float] = []


class CorrelationPair(BaseModel):
    """Correlation between two strategies"""
    strategy_a: str
    strategy_b: str
    correlation: float  # -1 to 1
    interpretation: str  # "strong_positive", "weak_positive", "uncorrelated", etc.


class CorrelationResult(BaseModel):
    """Full correlation analysis result"""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    portfolio_id: str
    pairs: List[CorrelationPair]
    matrix: Dict[str, Dict[str, float]]  # strategy_name -> strategy_name -> correlation
    average_correlation: float
    diversification_score: float  # 0-100, higher = more diversified
    recommendations: List[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioEquityPoint(BaseModel):
    """Point on combined portfolio equity curve"""
    timestamp: str  # ISO string for serialization
    balance: float
    drawdown_percent: float
    strategy_contributions: Dict[str, float]  # strategy_name -> contribution at this point


class PortfolioPerformanceMetrics(BaseModel):
    """Portfolio-level performance metrics"""
    # Profitability
    net_profit: float
    total_return_percent: float
    profit_factor: float

    # Risk
    max_drawdown: float
    max_drawdown_percent: float
    average_drawdown_percent: float

    # Risk-adjusted
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Trade stats
    total_trades: int
    win_rate: float

    # Portfolio specific
    diversification_ratio: float  # Portfolio vol / weighted avg vol
    portfolio_score: float  # 0-100


class PortfolioBacktestResult(BaseModel):
    """Combined portfolio backtest result"""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    portfolio_id: str
    session_id: str

    # Configuration
    initial_balance: float
    strategy_count: int

    # Per-strategy results
    strategy_results: List[Dict]  # name, weight, net_profit, contribution_percent

    # Combined metrics
    metrics: PortfolioPerformanceMetrics

    # Portfolio equity curve
    equity_curve: List[PortfolioEquityPoint]

    # Grade
    grade: str
    is_deployable: bool

    execution_time_seconds: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioMonteCarloResult(BaseModel):
    """Portfolio-level Monte Carlo simulation result"""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    portfolio_id: str
    session_id: str

    # Simulation config
    num_simulations: int
    initial_balance: float

    # Results
    profit_probability: float
    ruin_probability: float
    expected_return_percent: float
    worst_case_drawdown: float
    average_drawdown: float

    # Confidence intervals
    balance_ci_lower: float
    balance_ci_upper: float
    return_ci_lower: float
    return_ci_upper: float

    # Score
    robustness_score: float
    grade: str
    risk_level: str

    # Insights
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]

    execution_time_seconds: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AllocationResult(BaseModel):
    """Risk allocation optimization result"""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    portfolio_id: str
    method: AllocationMethod

    # Optimized weights
    weights: Dict[str, float]  # strategy_name -> weight (0-1)

    # Portfolio metrics with optimized weights
    expected_return: float
    expected_volatility: float
    expected_sharpe: float
    expected_max_drawdown: float

    # Comparison to current
    improvement_vs_equal: float  # % improvement in Sharpe vs equal weight

    recommendations: List[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Portfolio(BaseModel):
    """Portfolio of strategies"""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    name: str
    description: str = ""

    # Strategies
    strategies: List[PortfolioStrategy] = []

    # Current allocation
    allocation_method: AllocationMethod = AllocationMethod.EQUAL_WEIGHT

    # Portfolio state
    initial_balance: float = 100000.0

    # Latest results
    correlation_result: Optional[CorrelationResult] = None
    backtest_result: Optional[PortfolioBacktestResult] = None
    monte_carlo_result: Optional[PortfolioMonteCarloResult] = None
    allocation_result: Optional[AllocationResult] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Request Models
class CreatePortfolioRequest(BaseModel):
    session_id: str
    name: str
    description: str = ""
    initial_balance: float = 100000.0


class AddStrategyRequest(BaseModel):
    backtest_id: str
    name: str
    weight: Optional[float] = None  # If None, auto-equal-weight


class PortfolioBacktestRequest(BaseModel):
    session_id: str
    initial_balance: Optional[float] = None  # Override portfolio default


class PortfolioMonteCarloRequest(BaseModel):
    session_id: str
    num_simulations: int = 1000
    ruin_threshold_percent: float = 50.0


class OptimizeAllocationRequest(BaseModel):
    method: AllocationMethod = AllocationMethod.MAX_SHARPE
