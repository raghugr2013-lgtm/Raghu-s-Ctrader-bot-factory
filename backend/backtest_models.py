"""
Backtesting Engine - Data Models and Architecture
Phase 2 Step 3: Design only, no real market data integration yet
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Literal
from datetime import datetime, timezone
from enum import Enum
import uuid


# Enums
class TradeDirection(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


# Trade Record Model
class TradeRecord(BaseModel):
    """Individual trade in backtest"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    backtest_id: str
    
    # Trade Details
    entry_time: datetime
    exit_time: Optional[datetime] = None
    symbol: str
    direction: TradeDirection
    
    # Price Information
    entry_price: float
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Position Sizing
    volume: float  # Lot size
    position_size: float  # In base currency
    
    # Performance
    profit_loss: Optional[float] = None  # In currency
    profit_loss_pips: Optional[float] = None  # In pips
    profit_loss_percent: Optional[float] = None  # Percentage
    
    # Trade Metadata
    duration_minutes: Optional[int] = None
    commission: float = 0.0
    swap: float = 0.0
    notes: Optional[str] = None  # Additional metadata (e.g., strategy name, regime info)
    
    # Status
    status: TradeStatus = TradeStatus.OPEN
    close_reason: Optional[str] = None  # "stop_loss", "take_profit", "signal", "manual"


# Equity Point Model (for equity curve)
class EquityPoint(BaseModel):
    """Point on equity curve"""
    timestamp: datetime
    balance: float
    equity: float
    drawdown: float  # Absolute drawdown
    drawdown_percent: float  # Percentage drawdown


# Performance Metrics Model
class PerformanceMetrics(BaseModel):
    """Calculated performance metrics"""
    
    # Profitability
    net_profit: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    
    # Risk Metrics
    max_drawdown: float  # Absolute
    max_drawdown_percent: float
    average_drawdown: float
    recovery_factor: float  # Net Profit / Max Drawdown
    
    # Trade Statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float  # Percentage
    
    # Returns
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    average_trade: float
    
    # Risk-Adjusted Returns
    sharpe_ratio: float
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None  # Return / Max Drawdown
    
    # Trade Duration
    average_trade_duration_minutes: float
    average_winning_duration_minutes: float
    average_losing_duration_minutes: float
    
    # Consecutive Stats
    max_consecutive_wins: int
    max_consecutive_losses: int
    
    # Risk Metrics
    risk_reward_ratio: float
    expectancy: float  # (Win% × Avg Win) - (Loss% × Avg Loss)


# Backtest Configuration Model
class BacktestConfig(BaseModel):
    """Backtest configuration parameters"""
    
    # Symbol and Timeframe
    symbol: str = "EURUSD"
    timeframe: Timeframe = Timeframe.H1
    
    # Date Range
    start_date: datetime
    end_date: datetime
    
    # Initial Conditions
    initial_balance: float = 10000.0
    currency: str = "USD"
    leverage: int = 100
    
    # Commission and Costs
    commission_per_lot: float = 7.0  # $ per lot
    spread_pips: float = 1.0
    
    # Risk Management (from bot code)
    max_risk_per_trade_percent: float = 2.0
    max_positions: int = 3
    
    # Prop Firm Rules (if applicable)
    prop_firm: Optional[str] = None
    max_daily_loss_percent: Optional[float] = None
    max_total_drawdown_percent: Optional[float] = None


# Strategy Score Model
class StrategyScore(BaseModel):
    """Overall strategy evaluation score"""
    
    # Component Scores (0-100 each)
    profitability_score: float  # Based on profit factor
    risk_score: float  # Based on drawdown
    consistency_score: float  # Based on win rate
    efficiency_score: float  # Based on Sharpe ratio
    
    # Overall Score (0-100)
    total_score: float
    
    # Grade
    grade: str  # S, A, B, C, D, F
    
    # Evaluation
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]


# Main Backtest Result Model
class BacktestResult(BaseModel):
    """Complete backtest result"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    bot_name: str
    
    # Configuration
    config: BacktestConfig
    
    # Performance
    metrics: PerformanceMetrics
    
    # Score
    strategy_score: StrategyScore
    
    # Trade History
    trades: List[TradeRecord]
    
    # Equity Curve
    equity_curve: List[EquityPoint]
    
    # Status
    status: str = "completed"  # running, completed, failed
    execution_time_seconds: float = 0.0
    
    # Compliance Check
    is_compliant: bool = True
    compliance_violations: List[str] = []
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


# Request Models for API
class BacktestRequest(BaseModel):
    """Request to run a backtest"""
    session_id: str
    bot_code: str
    bot_name: str
    config: BacktestConfig
    prop_firm: Optional[str] = None


class BacktestSimulateRequest(BaseModel):
    """Request to run simulated backtest (Phase 3 - mock data)"""
    session_id: str
    bot_name: str
    symbol: str = "EURUSD"
    timeframe: str = "1h"
    duration_days: int = 90
    initial_balance: float = 10000.0
    strategy_type: str = "trend_following"  # For generating realistic mock data


# Response Models
class BacktestSummary(BaseModel):
    """Summary of backtest for listing"""
    id: str
    bot_name: str
    symbol: str
    timeframe: str
    total_trades: int
    net_profit: float
    win_rate: float
    max_drawdown_percent: float
    strategy_score: float
    created_at: datetime


# Architecture Documentation
BACKTEST_ARCHITECTURE = {
    "data_flow": {
        "step_1": "Bot code + Config → Backtest Engine",
        "step_2": "Parse strategy logic from code",
        "step_3": "Simulate trades with historical data (mocked for Phase 3)",
        "step_4": "Calculate performance metrics",
        "step_5": "Generate equity curve and drawdown chart",
        "step_6": "Calculate strategy score",
        "step_7": "Check prop firm compliance",
        "step_8": "Store results in MongoDB",
        "step_9": "Return results to frontend"
    },
    
    "integration_points": {
        "bot_generator": "Generated bots can be immediately backtested",
        "compliance_engine": "Backtest validates prop firm rules during simulation",
        "chat_workspace": "Users can upload backtest results for AI analysis",
        "code_validator": "Validates bot code before backtesting",
        "future_walk_forward": "Backtests feed into walk-forward optimization"
    },
    
    "calculation_priority": [
        "Trade-level calculations (P&L, pips, duration)",
        "Aggregate statistics (win rate, averages)",
        "Risk metrics (drawdown, Sharpe ratio)",
        "Strategy score",
        "Compliance check"
    ],
    
    "future_enhancements": {
        "phase_4": "Real market data integration (historical OHLCV)",
        "phase_5": "Monte Carlo simulation",
        "phase_6": "Walk-forward optimization",
        "phase_7": "Multi-symbol portfolio testing",
        "phase_8": "Genetic algorithm for parameter optimization"
    }
}
