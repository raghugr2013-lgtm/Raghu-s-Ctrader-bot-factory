"""
Walk-Forward Validation System
Ensures strategies are robust and not curve-fitted.

Supports:
1. Single split validation (70% training / 30% validation)
2. Multi-period rolling validation (advanced)

Rejects strategies that:
- Perform well in training but poorly in validation (overfitting)
- Show large performance degradation between periods
- Have insufficient trade count for statistical reliability
"""

import logging
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field

from market_data_models import Candle
from backtest_models import TradeRecord, EquityPoint, BacktestConfig
from backtest_real_engine import (
    StrategyParameters,
    _run_parameterized_strategy,
    _calculate_ema,
    _calculate_rsi,
    _calculate_atr
)

logger = logging.getLogger(__name__)


@dataclass
class PeriodMetrics:
    """Metrics for a single period (training or validation)."""
    period_name: str
    start_date: datetime
    end_date: datetime
    candles_used: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    profit_factor: float
    win_rate: float
    max_drawdown_pct: float
    net_profit: float
    sharpe_ratio: float
    avg_win: float
    avg_loss: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "period_name": self.period_name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "candles_used": self.candles_used,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "profit_factor": round(self.profit_factor, 3),
            "win_rate": round(self.win_rate, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "net_profit": round(self.net_profit, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2)
        }


@dataclass
class WalkForwardResult:
    """Complete walk-forward validation result."""
    strategy_name: str
    training_metrics: PeriodMetrics
    validation_metrics: PeriodMetrics
    # Stability metrics
    stability_score: float  # 0-1, higher = more stable
    pf_stability: float     # validation PF / training PF
    wr_stability: float     # validation WR / training WR
    dd_stability: float     # training DD / validation DD (inverted, lower val DD = better)
    # Overfitting detection
    is_overfit: bool
    overfit_severity: str   # "none", "mild", "severe"
    overfit_reasons: List[str]
    # Overall assessment
    is_robust: bool
    robustness_grade: str   # "A", "B", "C", "D", "F"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "training": self.training_metrics.to_dict(),
            "validation": self.validation_metrics.to_dict(),
            "stability_score": round(self.stability_score, 3),
            "pf_stability": round(self.pf_stability, 3),
            "wr_stability": round(self.wr_stability, 3),
            "dd_stability": round(self.dd_stability, 3),
            "is_overfit": self.is_overfit,
            "overfit_severity": self.overfit_severity,
            "overfit_reasons": self.overfit_reasons,
            "is_robust": self.is_robust,
            "robustness_grade": self.robustness_grade
        }


@dataclass
class RollingPeriodResult:
    """Result for a single rolling period validation."""
    period_name: str
    training_start: datetime
    training_end: datetime
    validation_start: datetime
    validation_end: datetime
    training_metrics: PeriodMetrics
    validation_metrics: PeriodMetrics
    pf_stability: float
    wr_stability: float
    is_profitable: bool  # Validation PF > 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "period_name": self.period_name,
            "training_period": f"{self.training_start.strftime('%Y-%m')} to {self.training_end.strftime('%Y-%m')}",
            "validation_period": f"{self.validation_start.strftime('%Y-%m')} to {self.validation_end.strftime('%Y-%m')}",
            "training": self.training_metrics.to_dict(),
            "validation": self.validation_metrics.to_dict(),
            "pf_stability": round(self.pf_stability, 3),
            "wr_stability": round(self.wr_stability, 3),
            "is_profitable": self.is_profitable
        }


@dataclass
class MultiPeriodWalkForwardResult:
    """
    Complete multi-period rolling walk-forward validation result.
    Tests strategy across multiple time periods for consistency.
    """
    strategy_name: str
    num_periods: int
    periods: List[RollingPeriodResult] = field(default_factory=list)
    
    # Aggregated metrics
    avg_training_pf: float = 0.0
    avg_validation_pf: float = 0.0
    avg_training_wr: float = 0.0
    avg_validation_wr: float = 0.0
    worst_validation_pf: float = 0.0
    worst_validation_dd: float = 0.0
    
    # Total trade counts
    total_training_trades: int = 0
    total_validation_trades: int = 0
    
    # Consistency metrics
    pf_consistency: float = 0.0  # Lower std dev = more consistent
    profitable_periods: int = 0  # Periods with validation PF > 1.0
    profitable_ratio: float = 0.0
    
    # Overall stability
    stability_score: float = 0.0
    robustness_grade: str = "F"
    is_robust: bool = False
    rejection_reasons: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "num_periods": self.num_periods,
            "periods": [p.to_dict() for p in self.periods],
            "avg_training_pf": round(self.avg_training_pf, 3),
            "avg_validation_pf": round(self.avg_validation_pf, 3),
            "avg_training_wr": round(self.avg_training_wr, 2),
            "avg_validation_wr": round(self.avg_validation_wr, 2),
            "worst_validation_pf": round(self.worst_validation_pf, 3),
            "worst_validation_dd": round(self.worst_validation_dd, 2),
            "total_training_trades": self.total_training_trades,
            "total_validation_trades": self.total_validation_trades,
            "pf_consistency": round(self.pf_consistency, 3),
            "profitable_periods": self.profitable_periods,
            "profitable_ratio": round(self.profitable_ratio, 3),
            "stability_score": round(self.stability_score, 3),
            "robustness_grade": self.robustness_grade,
            "is_robust": self.is_robust,
            "rejection_reasons": self.rejection_reasons
        }


def split_candles_for_walkforward(
    candles: List[Candle],
    training_ratio: float = 0.7
) -> Tuple[List[Candle], List[Candle]]:
    """
    Split candles into training and validation periods.
    
    Args:
        candles: Full list of candles (must be sorted by timestamp)
        training_ratio: Ratio of data for training (default 70%)
    
    Returns:
        Tuple of (training_candles, validation_candles)
    """
    if not candles:
        return [], []
    
    # Sort by timestamp
    sorted_candles = sorted(candles, key=lambda c: c.timestamp)
    
    split_idx = int(len(sorted_candles) * training_ratio)
    
    # Ensure minimum candles in each period
    min_candles = 50
    if split_idx < min_candles:
        split_idx = min_candles
    if len(sorted_candles) - split_idx < min_candles:
        split_idx = len(sorted_candles) - min_candles
    
    training_candles = sorted_candles[:split_idx]
    validation_candles = sorted_candles[split_idx:]
    
    logger.info(
        f"Walk-forward split: {len(training_candles)} training, "
        f"{len(validation_candles)} validation candles"
    )
    
    return training_candles, validation_candles


def calculate_period_metrics(
    trades: List[TradeRecord],
    equity_curve: List[EquityPoint],
    period_name: str,
    candles: List[Candle],
    initial_balance: float = 10000
) -> PeriodMetrics:
    """Calculate comprehensive metrics for a single period."""
    
    if not candles:
        return PeriodMetrics(
            period_name=period_name,
            start_date=None,
            end_date=None,
            candles_used=0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            profit_factor=0,
            win_rate=0,
            max_drawdown_pct=100,
            net_profit=0,
            sharpe_ratio=0,
            avg_win=0,
            avg_loss=0
        )
    
    start_date = candles[0].timestamp
    end_date = candles[-1].timestamp
    
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t.profit_loss > 0)
    losing_trades = sum(1 for t in trades if t.profit_loss < 0)
    
    # Win rate
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Net profit
    net_profit = sum(t.profit_loss for t in trades)
    
    # Profit factor
    gross_profit = sum(t.profit_loss for t in trades if t.profit_loss > 0)
    gross_loss = abs(sum(t.profit_loss for t in trades if t.profit_loss < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (2.0 if gross_profit > 0 else 0)
    
    # Max drawdown
    max_drawdown_pct = 0
    if equity_curve:
        max_drawdown_pct = max((e.drawdown_percent for e in equity_curve), default=0)
    
    # Average win/loss
    wins = [t.profit_loss for t in trades if t.profit_loss > 0]
    losses = [abs(t.profit_loss) for t in trades if t.profit_loss < 0]
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    
    # Sharpe ratio (simplified)
    if trades:
        returns = [t.profit_loss / initial_balance for t in trades]
        if len(returns) > 1:
            import statistics
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 1
            sharpe_ratio = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
    else:
        sharpe_ratio = 0
    
    return PeriodMetrics(
        period_name=period_name,
        start_date=start_date,
        end_date=end_date,
        candles_used=len(candles),
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        profit_factor=profit_factor,
        win_rate=win_rate,
        max_drawdown_pct=max_drawdown_pct,
        net_profit=net_profit,
        sharpe_ratio=sharpe_ratio,
        avg_win=avg_win,
        avg_loss=avg_loss
    )


def run_walkforward_validation(
    candles: List[Candle],
    strategy_name: str,
    symbol: str,
    timeframe: str,
    params: StrategyParameters,
    initial_balance: float = 10000,
    training_ratio: float = 0.7,
    min_stability_threshold: float = 0.6,  # Validation must be >= 60% of training
    min_validation_pf: float = 1.0         # Validation PF must be >= 1.0
) -> WalkForwardResult:
    """
    Run walk-forward validation on a strategy.
    
    This splits data into training and validation periods,
    runs the strategy on both, and checks for overfitting.
    """
    from backtest_models import Timeframe
    
    # Split data
    training_candles, validation_candles = split_candles_for_walkforward(
        candles, training_ratio
    )
    
    if len(training_candles) < 50 or len(validation_candles) < 20:
        logger.warning("Insufficient data for walk-forward validation")
        # Return failed result
        empty_metrics = PeriodMetrics(
            period_name="insufficient_data",
            start_date=None,
            end_date=None,
            candles_used=0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            profit_factor=0,
            win_rate=0,
            max_drawdown_pct=100,
            net_profit=0,
            sharpe_ratio=0,
            avg_win=0,
            avg_loss=0
        )
        return WalkForwardResult(
            strategy_name=strategy_name,
            training_metrics=empty_metrics,
            validation_metrics=empty_metrics,
            stability_score=0,
            pf_stability=0,
            wr_stability=0,
            dd_stability=0,
            is_overfit=True,
            overfit_severity="severe",
            overfit_reasons=["Insufficient data for validation"],
            is_robust=False,
            robustness_grade="F"
        )
    
    # Create backtest config
    tf_map = {"1m": Timeframe.M1, "5m": Timeframe.M5, "15m": Timeframe.M15,
              "30m": Timeframe.M30, "1h": Timeframe.H1, "4h": Timeframe.H4, "1d": Timeframe.D1}
    tf = tf_map.get(timeframe, Timeframe.H1)
    
    config = BacktestConfig(
        symbol=symbol,
        timeframe=tf,
        start_date=training_candles[0].timestamp,
        end_date=validation_candles[-1].timestamp,
        initial_balance=initial_balance,
        spread_pips=1.5,
        commission_per_lot=7.0,
        leverage=100,
    )
    
    # Run on training period
    logger.info(f"Running training period backtest ({len(training_candles)} candles)")
    training_trades, training_equity = _run_parameterized_strategy(
        training_candles, config, params
    )
    training_metrics = calculate_period_metrics(
        training_trades, training_equity, "training", training_candles, initial_balance
    )
    
    # Run on validation period (use same params - this is the key!)
    logger.info(f"Running validation period backtest ({len(validation_candles)} candles)")
    validation_trades, validation_equity = _run_parameterized_strategy(
        validation_candles, config, params
    )
    validation_metrics = calculate_period_metrics(
        validation_trades, validation_equity, "validation", validation_candles, initial_balance
    )
    
    # Calculate stability scores
    pf_stability = _calculate_stability_ratio(
        validation_metrics.profit_factor,
        training_metrics.profit_factor,
        higher_is_better=True
    )
    
    wr_stability = _calculate_stability_ratio(
        validation_metrics.win_rate,
        training_metrics.win_rate,
        higher_is_better=True
    )
    
    dd_stability = _calculate_stability_ratio(
        training_metrics.max_drawdown_pct,
        validation_metrics.max_drawdown_pct,
        higher_is_better=False  # Lower drawdown is better
    )
    
    # Overall stability score (weighted average)
    stability_score = (
        pf_stability * 0.5 +    # PF stability most important
        wr_stability * 0.3 +    # Win rate stability
        dd_stability * 0.2      # Drawdown stability
    )
    
    # Detect overfitting
    overfit_reasons = []
    
    # Check 1: Validation PF too low
    if validation_metrics.profit_factor < min_validation_pf:
        overfit_reasons.append(
            f"Validation PF ({validation_metrics.profit_factor:.2f}) below threshold ({min_validation_pf})"
        )
    
    # Check 2: Large PF drop
    if pf_stability < min_stability_threshold:
        overfit_reasons.append(
            f"PF dropped {(1-pf_stability)*100:.1f}% from training to validation"
        )
    
    # Check 3: Win rate collapse
    if wr_stability < 0.7:  # Win rate dropped more than 30%
        overfit_reasons.append(
            f"Win rate dropped {(1-wr_stability)*100:.1f}% in validation"
        )
    
    # Check 4: Drawdown spike
    if validation_metrics.max_drawdown_pct > training_metrics.max_drawdown_pct * 1.5:
        overfit_reasons.append(
            f"Drawdown increased from {training_metrics.max_drawdown_pct:.1f}% to {validation_metrics.max_drawdown_pct:.1f}%"
        )
    
    # Check 5: Too few validation trades
    if validation_metrics.total_trades < 5:
        overfit_reasons.append(
            f"Too few validation trades ({validation_metrics.total_trades})"
        )
    
    # Determine overfit severity
    is_overfit = len(overfit_reasons) > 0
    if len(overfit_reasons) == 0:
        overfit_severity = "none"
    elif len(overfit_reasons) <= 2:
        overfit_severity = "mild"
    else:
        overfit_severity = "severe"
    
    # Determine robustness
    is_robust = (
        not is_overfit or overfit_severity == "mild"
    ) and (
        validation_metrics.profit_factor >= 1.0 and
        stability_score >= min_stability_threshold
    )
    
    # Assign grade
    if stability_score >= 0.9 and validation_metrics.profit_factor >= 1.3:
        robustness_grade = "A"
    elif stability_score >= 0.75 and validation_metrics.profit_factor >= 1.1:
        robustness_grade = "B"
    elif stability_score >= 0.6 and validation_metrics.profit_factor >= 1.0:
        robustness_grade = "C"
    elif stability_score >= 0.5:
        robustness_grade = "D"
    else:
        robustness_grade = "F"
    
    result = WalkForwardResult(
        strategy_name=strategy_name,
        training_metrics=training_metrics,
        validation_metrics=validation_metrics,
        stability_score=stability_score,
        pf_stability=pf_stability,
        wr_stability=wr_stability,
        dd_stability=dd_stability,
        is_overfit=is_overfit,
        overfit_severity=overfit_severity,
        overfit_reasons=overfit_reasons,
        is_robust=is_robust,
        robustness_grade=robustness_grade
    )
    
    logger.info(
        f"Walk-forward result for {strategy_name}: "
        f"Grade={robustness_grade}, Stability={stability_score:.2f}, "
        f"Overfit={overfit_severity}"
    )
    
    return result


def _calculate_stability_ratio(
    validation_value: float,
    training_value: float,
    higher_is_better: bool = True
) -> float:
    """
    Calculate stability ratio between validation and training.
    Returns 0-1 where 1 = perfectly stable (or better in validation).
    """
    if training_value == 0:
        return 1.0 if validation_value >= 0 else 0.0
    
    if higher_is_better:
        # For metrics where higher is better (PF, WR)
        ratio = validation_value / training_value
    else:
        # For metrics where lower is better (DD)
        # If validation DD is lower, that's good (ratio > 1)
        ratio = training_value / validation_value if validation_value > 0 else 1.0
    
    # Cap at 1.0 (validation can be better but we don't give extra credit)
    # Minimum is 0
    return min(1.0, max(0.0, ratio))


def filter_robust_strategies(
    results: List[WalkForwardResult],
    min_grade: str = "C",
    min_stability: float = 0.6
) -> List[WalkForwardResult]:
    """
    Filter to keep only robust strategies.
    
    Args:
        results: List of walk-forward results
        min_grade: Minimum robustness grade ("A", "B", "C", "D")
        min_stability: Minimum stability score
    
    Returns:
        List of strategies that passed robustness check
    """
    grade_order = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
    min_grade_value = grade_order.get(min_grade, 2)
    
    robust = []
    for r in results:
        grade_value = grade_order.get(r.robustness_grade, 0)
        if grade_value >= min_grade_value and r.stability_score >= min_stability:
            robust.append(r)
    
    return robust



def create_rolling_periods(
    candles: List[Candle],
    training_years: int = 2,
    validation_years: int = 1,
    step_months: int = 12
) -> List[Tuple[List[Candle], List[Candle], str]]:
    """
    Create rolling train/validation periods from candles.
    
    Example with training_years=2, validation_years=1, step_months=12:
    - Period 1: Train 2020-2022, Validate 2022-2023
    - Period 2: Train 2021-2023, Validate 2023-2024
    - Period 3: Train 2022-2024, Validate 2024-2025
    
    Args:
        candles: Full list of candles (sorted by timestamp)
        training_years: Years of data for training
        validation_years: Years of data for validation
        step_months: Months to step forward for each period
    
    Returns:
        List of (training_candles, validation_candles, period_name) tuples
    """
    if not candles:
        return []
    
    sorted_candles = sorted(candles, key=lambda c: c.timestamp)
    
    first_date = sorted_candles[0].timestamp
    last_date = sorted_candles[-1].timestamp
    
    training_days = training_years * 365
    validation_days = validation_years * 365
    step_days = step_months * 30
    
    periods = []
    current_start = first_date
    period_num = 1
    
    while True:
        train_end = current_start + timedelta(days=training_days)
        val_start = train_end
        val_end = val_start + timedelta(days=validation_days)
        
        # Stop if we don't have enough data for validation
        if val_end > last_date:
            break
        
        # Get candles for each period
        train_candles = [c for c in sorted_candles 
                        if current_start <= c.timestamp < train_end]
        val_candles = [c for c in sorted_candles 
                      if val_start <= c.timestamp < val_end]
        
        # Only add period if we have minimum candles
        if len(train_candles) >= 500 and len(val_candles) >= 200:
            period_name = f"Period {period_num}: {current_start.strftime('%Y')}-{train_end.strftime('%Y')} → {val_end.strftime('%Y')}"
            periods.append((train_candles, val_candles, period_name))
            period_num += 1
        
        # Step forward
        current_start = current_start + timedelta(days=step_days)
        
        # Safety limit
        if period_num > 10:
            break
    
    logger.info(f"Created {len(periods)} rolling walk-forward periods")
    return periods


def run_multi_period_walkforward(
    candles: List[Candle],
    strategy_name: str,
    symbol: str,
    timeframe: str,
    params: StrategyParameters,
    initial_balance: float = 10000,
    training_years: int = 2,
    validation_years: int = 1,
    step_months: int = 12,
    min_validation_trades: int = 30,
    min_validation_pf: float = 1.1,
    min_profitable_ratio: float = 0.7  # At least 70% of periods must be profitable
) -> MultiPeriodWalkForwardResult:
    """
    Run multi-period rolling walk-forward validation.
    
    This tests the strategy across multiple overlapping time periods
    to ensure consistency and statistical reliability.
    
    Args:
        candles: Full historical data
        strategy_name: Name of the strategy
        symbol: Trading symbol
        timeframe: Timeframe
        params: Strategy parameters
        initial_balance: Starting balance
        training_years: Years per training period
        validation_years: Years per validation period
        step_months: Months to step forward
        min_validation_trades: Minimum trades required in validation
        min_validation_pf: Minimum validation profit factor
        min_profitable_ratio: Minimum ratio of profitable periods
    
    Returns:
        MultiPeriodWalkForwardResult with aggregated metrics
    """
    from backtest_models import Timeframe
    
    # Create rolling periods
    periods = create_rolling_periods(
        candles, training_years, validation_years, step_months
    )
    
    if len(periods) < 2:
        logger.warning("Insufficient data for multi-period walk-forward validation")
        return MultiPeriodWalkForwardResult(
            strategy_name=strategy_name,
            num_periods=0,
            rejection_reasons=["Insufficient data for multi-period validation"],
            is_robust=False,
            robustness_grade="F"
        )
    
    # Setup
    tf_map = {"1m": Timeframe.M1, "5m": Timeframe.M5, "15m": Timeframe.M15,
              "30m": Timeframe.M30, "1h": Timeframe.H1, "4h": Timeframe.H4, "1d": Timeframe.D1}
    tf = tf_map.get(timeframe, Timeframe.H1)
    
    config = BacktestConfig(
        symbol=symbol,
        timeframe=tf,
        start_date=candles[0].timestamp,
        end_date=candles[-1].timestamp,
        initial_balance=initial_balance,
        spread_pips=1.5,
        commission_per_lot=7.0,
        leverage=100,
    )
    
    # Run validation on each period
    period_results = []
    training_pfs = []
    validation_pfs = []
    training_wrs = []
    validation_wrs = []
    total_train_trades = 0
    total_val_trades = 0
    profitable_count = 0
    worst_val_pf = float('inf')
    worst_val_dd = 0
    
    for train_candles, val_candles, period_name in periods:
        # Run on training period
        train_trades, train_equity = _run_parameterized_strategy(
            train_candles, config, params
        )
        train_metrics = calculate_period_metrics(
            train_trades, train_equity, "training", train_candles, initial_balance
        )
        
        # Run on validation period (same params)
        val_trades, val_equity = _run_parameterized_strategy(
            val_candles, config, params
        )
        val_metrics = calculate_period_metrics(
            val_trades, val_equity, "validation", val_candles, initial_balance
        )
        
        # Calculate stability
        pf_stability = _calculate_stability_ratio(
            val_metrics.profit_factor, train_metrics.profit_factor, True
        )
        wr_stability = _calculate_stability_ratio(
            val_metrics.win_rate, train_metrics.win_rate, True
        )
        
        is_profitable = val_metrics.profit_factor >= 1.0
        
        period_result = RollingPeriodResult(
            period_name=period_name,
            training_start=train_candles[0].timestamp,
            training_end=train_candles[-1].timestamp,
            validation_start=val_candles[0].timestamp,
            validation_end=val_candles[-1].timestamp,
            training_metrics=train_metrics,
            validation_metrics=val_metrics,
            pf_stability=pf_stability,
            wr_stability=wr_stability,
            is_profitable=is_profitable
        )
        period_results.append(period_result)
        
        # Collect stats
        training_pfs.append(train_metrics.profit_factor)
        validation_pfs.append(val_metrics.profit_factor)
        training_wrs.append(train_metrics.win_rate)
        validation_wrs.append(val_metrics.win_rate)
        total_train_trades += train_metrics.total_trades
        total_val_trades += val_metrics.total_trades
        
        if is_profitable:
            profitable_count += 1
        
        if val_metrics.profit_factor < worst_val_pf:
            worst_val_pf = val_metrics.profit_factor
        if val_metrics.max_drawdown_pct > worst_val_dd:
            worst_val_dd = val_metrics.max_drawdown_pct
    
    # Calculate aggregated metrics
    avg_train_pf = statistics.mean(training_pfs) if training_pfs else 0
    avg_val_pf = statistics.mean(validation_pfs) if validation_pfs else 0
    avg_train_wr = statistics.mean(training_wrs) if training_wrs else 0
    avg_val_wr = statistics.mean(validation_wrs) if validation_wrs else 0
    
    # PF consistency (lower std dev = more consistent)
    pf_std = statistics.stdev(validation_pfs) if len(validation_pfs) > 1 else 0
    pf_consistency = max(0, 1 - (pf_std / (avg_val_pf + 0.01)))  # Normalize
    
    profitable_ratio = profitable_count / len(periods) if periods else 0
    
    # Rejection checks
    rejection_reasons = []
    
    # Check 1: Minimum validation trades
    if total_val_trades < min_validation_trades:
        rejection_reasons.append(
            f"Insufficient validation trades: {total_val_trades} < {min_validation_trades}"
        )
    
    # Check 2: Average validation PF
    if avg_val_pf < min_validation_pf:
        rejection_reasons.append(
            f"Low average validation PF: {avg_val_pf:.2f} < {min_validation_pf}"
        )
    
    # Check 3: Profitable periods ratio
    if profitable_ratio < min_profitable_ratio:
        rejection_reasons.append(
            f"Low profitable ratio: {profitable_ratio*100:.1f}% < {min_profitable_ratio*100:.1f}%"
        )
    
    # Check 4: Worst-case validation PF
    if worst_val_pf < 0.8:
        rejection_reasons.append(
            f"Worst validation PF too low: {worst_val_pf:.2f}"
        )
    
    # Check 5: Consistency
    if pf_consistency < 0.5:
        rejection_reasons.append(
            f"Inconsistent performance: consistency score {pf_consistency:.2f}"
        )
    
    # Calculate overall stability score
    stability_score = (
        min(avg_val_pf / 2, 1.0) * 0.30 +  # Avg PF (cap at 2.0)
        pf_consistency * 0.25 +             # Consistency
        profitable_ratio * 0.25 +           # Profitable periods
        (1 - worst_val_dd / 50) * 0.20      # Worst DD penalty (cap at 50%)
    )
    stability_score = max(0, min(1, stability_score))
    
    # Determine grade
    is_robust = len(rejection_reasons) == 0
    if stability_score >= 0.85 and total_val_trades >= 50:
        robustness_grade = "A+"
    elif stability_score >= 0.75 and total_val_trades >= 40:
        robustness_grade = "A"
    elif stability_score >= 0.65 and total_val_trades >= 30:
        robustness_grade = "B"
    elif stability_score >= 0.55:
        robustness_grade = "C"
    elif stability_score >= 0.45:
        robustness_grade = "D"
    else:
        robustness_grade = "F"
    
    result = MultiPeriodWalkForwardResult(
        strategy_name=strategy_name,
        num_periods=len(periods),
        periods=period_results,
        avg_training_pf=avg_train_pf,
        avg_validation_pf=avg_val_pf,
        avg_training_wr=avg_train_wr,
        avg_validation_wr=avg_val_wr,
        worst_validation_pf=worst_val_pf if worst_val_pf != float('inf') else 0,
        worst_validation_dd=worst_val_dd,
        total_training_trades=total_train_trades,
        total_validation_trades=total_val_trades,
        pf_consistency=pf_consistency,
        profitable_periods=profitable_count,
        profitable_ratio=profitable_ratio,
        stability_score=stability_score,
        robustness_grade=robustness_grade,
        is_robust=is_robust,
        rejection_reasons=rejection_reasons
    )
    
    logger.info(
        f"Multi-period WF for {strategy_name}: "
        f"Grade={robustness_grade}, Stability={stability_score:.2f}, "
        f"Periods={len(periods)}, Profitable={profitable_count}/{len(periods)}, "
        f"Val Trades={total_val_trades}"
    )
    
    return result
