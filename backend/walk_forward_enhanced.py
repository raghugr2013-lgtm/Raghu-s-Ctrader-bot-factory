"""
Phase 2: Enhanced Walk-Forward Validation
Minimum 5 splits with consistency requirements across all periods
"""

import logging
from typing import List, Dict, Tuple
from datetime import datetime
import statistics

logger = logging.getLogger(__name__)


class WalkForwardConfig:
    """Configuration for walk-forward validation"""
    MIN_SPLITS = 5  # Phase 2: Minimum 5 splits required
    TRAIN_RATIO = 0.70  # 70% training, 30% testing
    MIN_CONSISTENCY_SCORE = 70.0  # Minimum consistency across splits
    MAX_PERFORMANCE_VARIANCE = 0.40  # Max variance in performance (40%)


class WalkForwardSplit:
    """Single walk-forward split result"""
    def __init__(
        self,
        split_number: int,
        train_start: datetime,
        train_end: datetime,
        test_start: datetime,
        test_end: datetime,
        train_candles: int,
        test_candles: int
    ):
        self.split_number = split_number
        self.train_start = train_start
        self.train_end = train_end
        self.test_start = test_start
        self.test_end = test_end
        self.train_candles = train_candles
        self.test_candles = test_candles
        
        # Results (populated after backtest)
        self.in_sample_metrics = {}
        self.out_sample_metrics = {}
        self.performance_retention = 0.0
        self.is_profitable_oos = False


class WalkForwardResult:
    """Complete walk-forward validation result"""
    def __init__(self, symbol: str, strategy_name: str):
        self.symbol = symbol
        self.strategy_name = strategy_name
        self.splits: List[WalkForwardSplit] = []
        
        # Aggregated metrics
        self.total_splits = 0
        self.profitable_oos_splits = 0
        self.avg_performance_retention = 0.0
        self.consistency_score = 0.0
        self.stability_score = 0.0
        
        # Variance metrics (Phase 2)
        self.profit_variance = 0.0
        self.sharpe_variance = 0.0
        self.dd_variance = 0.0
        
        # Pass/Fail
        self.passes_minimum_splits = False
        self.passes_consistency_check = False
        self.is_stable = True  # False if high variance
        self.overall_verdict = ""
        self.rejection_reasons = []


class WalkForwardValidator:
    """
    Phase 2: Enhanced Walk-Forward Validator
    
    Enforces:
    - Minimum 5 splits
    - Consistency across all periods
    - Stability scoring based on variance
    """
    
    @staticmethod
    def create_splits(
        candles: List,
        min_splits: int = WalkForwardConfig.MIN_SPLITS,
        train_ratio: float = WalkForwardConfig.TRAIN_RATIO
    ) -> List[WalkForwardSplit]:
        """
        Create walk-forward splits.
        
        For anchored walk-forward:
        - Training set grows incrementally
        - Test set is fixed-size window after training
        
        Args:
            candles: Historical candles
            min_splits: Minimum number of splits
            train_ratio: Training/testing ratio
        
        Returns:
            List of WalkForwardSplit objects
        """
        total_candles = len(candles)
        
        if total_candles < min_splits * 200:  # Minimum 200 candles per split
            raise ValueError(
                f"Insufficient data: {total_candles} candles. "
                f"Need at least {min_splits * 200} for {min_splits} splits"
            )
        
        splits = []
        
        # Calculate split size
        test_size = int(total_candles * (1 - train_ratio) / min_splits)
        
        for i in range(min_splits):
            # Growing training window
            train_end_idx = int(total_candles * train_ratio) + (i * test_size)
            train_start_idx = 0
            
            # Fixed-size test window
            test_start_idx = train_end_idx
            test_end_idx = min(test_start_idx + test_size, total_candles)
            
            if test_end_idx > total_candles:
                break
            
            split = WalkForwardSplit(
                split_number=i + 1,
                train_start=candles[train_start_idx].timestamp,
                train_end=candles[train_end_idx - 1].timestamp,
                test_start=candles[test_start_idx].timestamp,
                test_end=candles[test_end_idx - 1].timestamp,
                train_candles=train_end_idx - train_start_idx,
                test_candles=test_end_idx - test_start_idx
            )
            
            splits.append(split)
        
        return splits
    
    @staticmethod
    def calculate_consistency_score(splits: List[WalkForwardSplit]) -> float:
        """
        Calculate consistency score based on out-of-sample performance.
        
        Consistency = how stable the strategy performs across different test periods
        
        Returns score 0-100
        """
        if not splits:
            return 0.0
        
        oos_profits = []
        for split in splits:
            oos = split.out_sample_metrics
            if oos and 'net_profit' in oos:
                oos_profits.append(oos['net_profit'])
        
        if not oos_profits or len(oos_profits) < 2:
            return 0.0
        
        # Check profitable count
        profitable_count = sum(1 for p in oos_profits if p > 0)
        profitable_pct = (profitable_count / len(oos_profits)) * 100
        
        # Calculate coefficient of variation (CV)
        mean_profit = statistics.mean(oos_profits)
        if mean_profit <= 0:
            return 0.0  # Losing strategy
        
        std_dev = statistics.stdev(oos_profits)
        cv = (std_dev / abs(mean_profit)) if mean_profit != 0 else 999
        
        # Lower CV = more consistent
        # CV < 0.3 = excellent (100-90 points)
        # CV 0.3-0.5 = good (90-70 points)
        # CV 0.5-1.0 = acceptable (70-50 points)
        # CV > 1.0 = poor (<50 points)
        
        if cv < 0.3:
            consistency_score = 100 - (cv * 33)  # 100-90
        elif cv < 0.5:
            consistency_score = 90 - ((cv - 0.3) * 100)  # 90-70
        elif cv < 1.0:
            consistency_score = 70 - ((cv - 0.5) * 40)  # 70-50
        else:
            consistency_score = max(0, 50 - ((cv - 1.0) * 25))  # <50
        
        # Boost score if all splits are profitable
        if profitable_pct == 100:
            consistency_score = min(100, consistency_score * 1.1)
        
        return consistency_score
    
    @staticmethod
    def calculate_stability_metrics(splits: List[WalkForwardSplit]) -> Dict:
        """
        Phase 2: Calculate stability metrics across splits.
        
        Returns:
            Dictionary with variance metrics
        """
        if not splits or len(splits) < 2:
            return {
                'profit_variance': 0.0,
                'sharpe_variance': 0.0,
                'dd_variance': 0.0,
                'is_stable': False
            }
        
        profits = []
        sharpes = []
        drawdowns = []
        
        for split in splits:
            oos = split.out_sample_metrics
            if oos:
                profits.append(oos.get('net_profit', 0))
                sharpes.append(oos.get('sharpe_ratio', 0))
                drawdowns.append(abs(oos.get('max_drawdown_pct', 0)))
        
        # Calculate coefficients of variation
        def calc_cv(values):
            if not values or len(values) < 2:
                return 0.0
            mean_val = statistics.mean(values)
            if mean_val == 0:
                return 999.0
            std_val = statistics.stdev(values)
            return std_val / abs(mean_val)
        
        profit_cv = calc_cv(profits)
        sharpe_cv = calc_cv(sharpes)
        dd_cv = calc_cv(drawdowns)
        
        # Check if stable (low variance)
        is_stable = (
            profit_cv < WalkForwardConfig.MAX_PERFORMANCE_VARIANCE and
            sharpe_cv < 0.5 and  # Sharpe shouldn't vary more than 50%
            dd_cv < 0.5  # Drawdown variance should be controlled
        )
        
        return {
            'profit_variance': profit_cv,
            'sharpe_variance': sharpe_cv,
            'dd_variance': dd_cv,
            'is_stable': is_stable
        }
    
    @staticmethod
    def validate_result(result: WalkForwardResult) -> Tuple[bool, List[str]]:
        """
        Phase 2: Validate walk-forward result against strict criteria.
        
        Returns:
            (passes, rejection_reasons)
        """
        rejection_reasons = []
        
        # Check 1: Minimum splits
        if result.total_splits < WalkForwardConfig.MIN_SPLITS:
            rejection_reasons.append(
                f"Insufficient splits: {result.total_splits} < {WalkForwardConfig.MIN_SPLITS} required"
            )
        
        # Check 2: Consistency score
        if result.consistency_score < WalkForwardConfig.MIN_CONSISTENCY_SCORE:
            rejection_reasons.append(
                f"Low consistency: {result.consistency_score:.1f}% < {WalkForwardConfig.MIN_CONSISTENCY_SCORE}% required"
            )
        
        # Check 3: Profitable OOS splits
        profitable_pct = (result.profitable_oos_splits / result.total_splits * 100) if result.total_splits > 0 else 0
        if profitable_pct < 60.0:  # At least 60% of splits must be profitable OOS
            rejection_reasons.append(
                f"Too few profitable OOS periods: {profitable_pct:.0f}% < 60% required"
            )
        
        # Check 4: Performance retention
        if result.avg_performance_retention < 30.0:  # At least 30% retention
            rejection_reasons.append(
                f"Poor performance retention: {result.avg_performance_retention:.0f}% < 30% required"
            )
        
        # Check 5: Stability (Phase 2)
        if not result.is_stable:
            rejection_reasons.append(
                f"High variance detected: Strategy shows unstable performance across periods "
                f"(profit_variance: {result.profit_variance:.2f})"
            )
        
        passes = len(rejection_reasons) == 0
        
        return passes, rejection_reasons
    
    @staticmethod
    def generate_verdict(result: WalkForwardResult) -> str:
        """Generate overall verdict message"""
        passes, reasons = WalkForwardValidator.validate_result(result)
        
        if passes:
            if result.consistency_score >= 90:
                return "EXCELLENT - Strategy shows exceptional consistency across all test periods"
            elif result.consistency_score >= 80:
                return "STRONG - Strategy demonstrates robust out-of-sample performance"
            else:
                return "PASS - Strategy meets minimum walk-forward requirements"
        else:
            return f"FAIL - Strategy rejected: {'; '.join(reasons)}"


def format_walk_forward_report(result: WalkForwardResult) -> str:
    """Format walk-forward result as readable report"""
    
    lines = []
    lines.append("=" * 100)
    lines.append(f"WALK-FORWARD VALIDATION REPORT - {result.strategy_name} ({result.symbol})")
    lines.append("=" * 100)
    lines.append("")
    
    # Split-by-split details
    lines.append(f"Total Splits: {result.total_splits}")
    lines.append("")
    lines.append(f"{'Split':<6} {'Period':>5} {'Trades':>7} {'Net P&L':>10} {'Sharpe':>8} {'DD%':>7} {'Retention':>10}")
    lines.append("-" * 100)
    
    for split in result.splits:
        ins = split.in_sample_metrics
        oos = split.out_sample_metrics
        
        lines.append(
            f"{split.split_number:<6} {'TRAIN':>5} {ins.get('trades', 0):>7} "
            f"{ins.get('net_profit', 0):>10.2f} {ins.get('sharpe_ratio', 0):>8.2f} "
            f"{ins.get('max_drawdown_pct', 0):>6.2f}% {'':>10}"
        )
        lines.append(
            f"{'':6} {'TEST':>5} {oos.get('trades', 0):>7} "
            f"{oos.get('net_profit', 0):>10.2f} {oos.get('sharpe_ratio', 0):>8.2f} "
            f"{oos.get('max_drawdown_pct', 0):>6.2f}% {split.performance_retention:>9.0f}%"
        )
        lines.append("")
    
    # Summary metrics
    lines.append("=" * 100)
    lines.append("SUMMARY METRICS")
    lines.append("=" * 100)
    lines.append(f"Profitable OOS Splits:     {result.profitable_oos_splits}/{result.total_splits} ({result.profitable_oos_splits/result.total_splits*100:.0f}%)")
    lines.append(f"Avg Performance Retention: {result.avg_performance_retention:.1f}%")
    lines.append(f"Consistency Score:         {result.consistency_score:.1f}/100")
    lines.append(f"Stability Score:           {result.stability_score:.1f}/100")
    lines.append("")
    lines.append(f"Profit Variance (CV):      {result.profit_variance:.3f}")
    lines.append(f"Sharpe Variance (CV):      {result.sharpe_variance:.3f}")
    lines.append(f"Drawdown Variance (CV):    {result.dd_variance:.3f}")
    lines.append(f"Is Stable:                 {'YES ✓' if result.is_stable else 'NO ✗'}")
    lines.append("")
    
    # Verdict
    lines.append("=" * 100)
    lines.append(f"VERDICT: {result.overall_verdict}")
    lines.append("=" * 100)
    
    if result.rejection_reasons:
        lines.append("")
        lines.append("REJECTION REASONS:")
        for reason in result.rejection_reasons:
            lines.append(f"  • {reason}")
    
    return "\n".join(lines)
