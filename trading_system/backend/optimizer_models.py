"""
Genetic Algorithm Strategy Optimizer - Data Models
Evolutionary parameter optimization for trading strategies.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid


class OptimizationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ParamType(str, Enum):
    INT = "int"
    FLOAT = "float"


class ParamDef(BaseModel):
    """Definition of a single optimizable parameter."""
    name: str
    param_type: ParamType = ParamType.FLOAT
    min_val: float
    max_val: float
    step: Optional[float] = None  # Discrete step; None = continuous


class StrategyGenome(BaseModel):
    """One individual: a set of strategy parameters."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    genes: Dict[str, float]  # param_name -> value
    fitness: float = 0.0
    generation: int = 0

    # Cached evaluation metrics
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    win_rate: float = 0.0
    net_profit: float = 0.0
    total_trades: int = 0
    monte_carlo_score: float = 0.0
    challenge_pass_pct: float = 0.0
    regime_consistency: float = 0.0


class GenerationSummary(BaseModel):
    """Summary of one generation."""
    generation: int
    population_size: int
    best_fitness: float
    avg_fitness: float
    worst_fitness: float
    best_sharpe: float
    best_drawdown: float
    diversity: float  # avg pairwise distance between genomes


class OptimizationResult(BaseModel):
    """Full optimization run result."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    status: OptimizationStatus = OptimizationStatus.PENDING

    # Config
    strategy_type: str
    symbol: str
    timeframe: str
    population_size: int
    num_generations: int
    initial_balance: float

    # Parameter definitions
    param_definitions: List[ParamDef]

    # GA settings
    crossover_rate: float
    mutation_rate: float
    mutation_strength: float
    elite_count: int
    tournament_size: int

    # Fitness weights
    fitness_weights: Dict[str, float]

    # Progress
    current_generation: int = 0
    total_evaluations: int = 0

    # Results
    generation_history: List[GenerationSummary] = []
    best_genome: Optional[StrategyGenome] = None
    top_genomes: List[StrategyGenome] = []

    # Timing
    execution_time_seconds: float = 0.0
    error_message: Optional[str] = None
    data_source: str = "mock"  # "real_candles" or "mock"

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


# Default parameter templates
DEFAULT_PARAMS: Dict[str, List[ParamDef]] = {
    "trend_following": [
        ParamDef(name="fast_ma_period", param_type=ParamType.INT, min_val=5, max_val=50, step=1),
        ParamDef(name="slow_ma_period", param_type=ParamType.INT, min_val=20, max_val=200, step=1),
        ParamDef(name="atr_period", param_type=ParamType.INT, min_val=7, max_val=30, step=1),
        ParamDef(name="stop_loss_atr_mult", param_type=ParamType.FLOAT, min_val=0.5, max_val=4.0),
        ParamDef(name="take_profit_atr_mult", param_type=ParamType.FLOAT, min_val=1.0, max_val=8.0),
        ParamDef(name="risk_per_trade_pct", param_type=ParamType.FLOAT, min_val=0.5, max_val=3.0),
        ParamDef(name="adx_threshold", param_type=ParamType.FLOAT, min_val=15.0, max_val=40.0),
    ],
    "mean_reversion": [
        ParamDef(name="rsi_period", param_type=ParamType.INT, min_val=5, max_val=30, step=1),
        ParamDef(name="rsi_oversold", param_type=ParamType.FLOAT, min_val=15, max_val=40),
        ParamDef(name="rsi_overbought", param_type=ParamType.FLOAT, min_val=60, max_val=85),
        ParamDef(name="bb_period", param_type=ParamType.INT, min_val=10, max_val=50, step=1),
        ParamDef(name="bb_std", param_type=ParamType.FLOAT, min_val=1.0, max_val=3.5),
        ParamDef(name="stop_loss_pct", param_type=ParamType.FLOAT, min_val=0.5, max_val=3.0),
        ParamDef(name="take_profit_pct", param_type=ParamType.FLOAT, min_val=0.5, max_val=5.0),
        ParamDef(name="risk_per_trade_pct", param_type=ParamType.FLOAT, min_val=0.5, max_val=3.0),
    ],
    "scalping": [
        ParamDef(name="ema_fast", param_type=ParamType.INT, min_val=3, max_val=20, step=1),
        ParamDef(name="ema_slow", param_type=ParamType.INT, min_val=10, max_val=50, step=1),
        ParamDef(name="atr_period", param_type=ParamType.INT, min_val=5, max_val=20, step=1),
        ParamDef(name="stop_loss_pips", param_type=ParamType.FLOAT, min_val=3.0, max_val=20.0),
        ParamDef(name="take_profit_pips", param_type=ParamType.FLOAT, min_val=3.0, max_val=30.0),
        ParamDef(name="risk_per_trade_pct", param_type=ParamType.FLOAT, min_val=0.3, max_val=2.0),
        ParamDef(name="max_spread", param_type=ParamType.FLOAT, min_val=0.5, max_val=3.0),
    ],
}


# Request model
class OptimizerRunRequest(BaseModel):
    session_id: str
    strategy_type: str = "trend_following"
    symbol: str = "EURUSD"
    timeframe: str = "1h"
    initial_balance: float = 10000.0
    duration_days: int = 90

    # GA config
    population_size: int = 30
    num_generations: int = 20
    crossover_rate: float = 0.8
    mutation_rate: float = 0.15
    mutation_strength: float = 0.2
    elite_count: int = 3
    tournament_size: int = 3

    # Fitness weights (sum to 1.0)
    sharpe_weight: float = 0.30
    drawdown_weight: float = 0.20
    monte_carlo_weight: float = 0.15
    challenge_weight: float = 0.15
    regime_weight: float = 0.10
    profit_factor_weight: float = 0.10

    # Optional custom params (overrides defaults)
    custom_params: Optional[List[ParamDef]] = None

    # Which prop firm to test against
    challenge_firm: str = "ftmo"

    # Template ID for real backtester (e.g., ema_crossover, rsi_mean_reversion)
    template_id: Optional[str] = None
