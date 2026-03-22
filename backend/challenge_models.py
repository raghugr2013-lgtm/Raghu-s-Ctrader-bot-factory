"""
Prop Firm Challenge Simulator - Data Models
Simulates full prop firm challenge scenarios with Monte Carlo analysis.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
from datetime import datetime, timezone
from enum import Enum
import uuid


class ChallengeFirm(str, Enum):
    FTMO = "ftmo"
    FUNDED_NEXT = "fundednext"
    THE5ERS = "the5ers"
    PIPFARM = "pipfarm"


class ChallengePhase(str, Enum):
    PHASE_1 = "phase_1"  # Evaluation / Challenge
    PHASE_2 = "phase_2"  # Verification
    FUNDED = "funded"     # Funded account


class ChallengeRules(BaseModel):
    """Rules for a specific prop firm challenge phase."""
    firm: ChallengeFirm
    phase: ChallengePhase
    label: str

    # Targets & limits
    profit_target_pct: float           # e.g. 10 for 10%
    daily_loss_limit_pct: float        # e.g. 5 for 5%
    max_drawdown_pct: float            # e.g. 10 for 10%
    min_trading_days: int              # minimum calendar days with >= 1 trade
    time_limit_days: int               # max calendar days to hit target

    # Flags
    trailing_drawdown: bool = False    # drawdown trails high-water mark
    news_trading_allowed: bool = True
    weekend_holding_allowed: bool = True


class DayResult(BaseModel):
    """Single trading day inside a simulation run."""
    day: int
    pnl: float
    balance: float
    peak: float
    drawdown_pct: float
    daily_loss_pct: float
    trades_today: int
    violated_daily: bool = False
    violated_drawdown: bool = False


class SimulationOutcome(BaseModel):
    """Outcome of one Monte Carlo simulation run."""
    run_id: int
    passed: bool
    days_to_target: Optional[int] = None
    final_balance: float
    peak_balance: float
    max_drawdown_pct: float
    max_daily_loss_pct: float
    trading_days: int
    fail_reason: Optional[str] = None  # "daily_loss" | "drawdown" | "time_limit" | "min_days"


class ChallengeSimulationResult(BaseModel):
    """Full result of a challenge simulation for one phase."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    firm: ChallengeFirm
    phase: ChallengePhase
    rules: ChallengeRules

    # Monte Carlo config
    num_simulations: int
    initial_balance: float

    # Probabilities
    pass_probability: float               # 0–100
    daily_loss_violation_probability: float
    drawdown_violation_probability: float
    time_limit_violation_probability: float

    # Statistics
    avg_days_to_target: Optional[float] = None
    median_days_to_target: Optional[float] = None
    avg_final_balance: float
    avg_max_drawdown: float
    avg_max_daily_loss: float

    # Confidence intervals (95%)
    pass_rate_ci_lower: float
    pass_rate_ci_upper: float

    # Score (0–100)
    challenge_score: float
    grade: str
    risk_level: str

    # Insights
    strengths: List[str] = []
    weaknesses: List[str] = []
    recommendations: List[str] = []

    # Fail breakdown
    fail_reasons: Dict[str, int] = {}  # reason -> count

    execution_time_seconds: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FullChallengeResult(BaseModel):
    """Multi-phase challenge result (Phase 1 + Phase 2 + Funded)."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    backtest_id: str
    firm: ChallengeFirm

    phase_results: List[ChallengeSimulationResult]
    combined_pass_probability: float  # P(pass phase1) * P(pass phase2)
    overall_score: float
    overall_grade: str

    is_viable: bool  # True if combined pass > 50%
    recommendation: str

    execution_time_seconds: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Request models
class ChallengeSimRequest(BaseModel):
    session_id: str
    backtest_id: str
    firm: ChallengeFirm
    initial_balance: float = 100000.0
    num_simulations: int = 1000
