"""
Strategy Factory - Data Models
Automatic strategy generation from predefined templates.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
from datetime import datetime, timezone
from enum import Enum
import uuid

from optimizer_models import ParamDef, ParamType


class TemplateId(str, Enum):
    EMA_CROSSOVER = "ema_crossover"
    RSI_MEAN_REVERSION = "rsi_mean_reversion"
    MACD_TREND = "macd_trend"
    BOLLINGER_BREAKOUT = "bollinger_breakout"
    ATR_VOLATILITY_BREAKOUT = "atr_volatility_breakout"


class FactoryStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StrategyTemplate(BaseModel):
    """Predefined strategy template with parameter ranges."""
    id: TemplateId
    name: str
    description: str
    backtest_strategy_type: str  # maps to mock generator type
    param_definitions: List[ParamDef]


class GeneratedStrategy(BaseModel):
    """A single strategy instance created from a template."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    template_id: TemplateId
    genes: Dict[str, float]
    
    # Optional name (generated from template)
    name: str = ""

    # Evaluation metrics
    fitness: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    win_rate: float = 0.0
    net_profit: float = 0.0
    total_trades: int = 0
    monte_carlo_score: float = 0.0
    challenge_pass_pct: float = 0.0

    evaluated: bool = False


class FactoryRun(BaseModel):
    """Result of a strategy factory run."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    status: FactoryStatus = FactoryStatus.PENDING

    # Config
    templates_used: List[str]
    strategies_per_template: int
    symbol: str
    timeframe: str
    initial_balance: float
    duration_days: int
    challenge_firm: str

    # Results
    total_generated: int = 0
    total_evaluated: int = 0
    
    # Codex filtering metrics
    total_after_diversity: int = 0
    total_after_correlation: int = 0
    portfolio_diversity_score: float = 0.0
    correlation_method: str = ""
    
    strategies: List[GeneratedStrategy] = []
    best_strategy: Optional[GeneratedStrategy] = None

    # GA optimization results (if auto_optimize was on)
    auto_optimized: bool = False
    optimization_job_ids: List[str] = []
    data_source: str = "mock"  # "real_candles" or "mock"

    execution_time_seconds: float = 0.0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FactoryRunRequest(BaseModel):
    session_id: str
    templates: List[TemplateId] = list(TemplateId)  # default: all templates
    strategies_per_template: int = 10
    symbol: str = "EURUSD"
    timeframe: str = "1h"
    initial_balance: float = 10000.0
    duration_days: int = 90
    challenge_firm: str = "ftmo"
    auto_optimize_top: int = 0  # 0 = skip, N = auto-optimize top N via GA
