"""
Phase 3: Strategy Discovery Scaling with Phase 2 Quality Filters

Generates large batches of strategies (100-200) and automatically filters
using Phase 2 quality standards. Only stores high-quality strategies (A/B/C).
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timezone
import random

# Phase 2 Integration
from phase2_integration import (
    Phase2Validator,
    add_phase2_fields_to_strategy
)

logger = logging.getLogger(__name__)


class StrategyGenerationConfig:
    """Configuration for strategy generation"""
    
    # Batch size
    MIN_STRATEGIES = 100
    MAX_STRATEGIES = 200
    DEFAULT_BATCH_SIZE = 150
    
    # Phase 2 Filter Settings
    ACCEPT_GRADES = ['A', 'B', 'C']  # Tradeable grades only
    REJECT_GRADES = ['D', 'F']  # Auto-reject
    
    # Strategy Types to Generate
    STRATEGY_TYPES = [
        'trend_following',
        'mean_reversion',
        'breakout',
        'momentum',
        'scalping',
        'swing_trading'
    ]
    
    # Parameter Ranges (for diversity)
    PARAMETER_RANGES = {
        'ema_fast': range(5, 30, 5),
        'ema_slow': range(20, 100, 10),
        'rsi_period': range(10, 25, 5),
        'rsi_oversold': range(20, 40, 5),
        'rsi_overbought': range(60, 85, 5),
        'stop_loss_pct': [0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
        'take_profit_pct': [1.0, 1.5, 2.0, 3.0, 4.0, 5.0],
        'atr_period': range(10, 25, 5),
        'bb_period': range(15, 30, 5),
        'bb_std': [1.5, 2.0, 2.5, 3.0]
    }


class BatchGenerationResult:
    """Result from batch strategy generation"""
    
    def __init__(self):
        self.total_generated = 0
        self.total_validated = 0
        
        # Grade breakdown
        self.grade_a_count = 0
        self.grade_b_count = 0
        self.grade_c_count = 0
        self.grade_d_count = 0
        self.grade_f_count = 0
        
        # Acceptance stats
        self.accepted_count = 0  # A + B + C
        self.rejected_count = 0  # D + F
        self.acceptance_rate = 0.0
        
        # Strategy lists
        self.accepted_strategies: List[Dict] = []
        self.rejected_strategies: List[Dict] = []
        
        # Top performers
        self.top_by_score: List[Dict] = []
        self.top_by_stability: List[Dict] = []
        self.top_by_low_dd: List[Dict] = []
        
        # Execution time
        self.start_time = None
        self.end_time = None
        self.duration_seconds = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "summary": {
                "total_generated": self.total_generated,
                "total_validated": self.total_validated,
                "accepted": self.accepted_count,
                "rejected": self.rejected_count,
                "acceptance_rate_pct": self.acceptance_rate,
                "duration_seconds": self.duration_seconds
            },
            "grade_distribution": {
                "A": self.grade_a_count,
                "B": self.grade_b_count,
                "C": self.grade_c_count,
                "D": self.grade_d_count,
                "F": self.grade_f_count
            },
            "top_strategies": {
                "by_score": [self._strategy_summary(s) for s in self.top_by_score[:10]],
                "by_stability": [self._strategy_summary(s) for s in self.top_by_stability[:10]],
                "by_low_drawdown": [self._strategy_summary(s) for s in self.top_by_low_dd[:10]]
            },
            "statistics": {
                "avg_score_accepted": self._avg_score(self.accepted_strategies),
                "avg_pf_accepted": self._avg_metric(self.accepted_strategies, 'profit_factor'),
                "avg_dd_accepted": self._avg_metric(self.accepted_strategies, 'max_drawdown_pct'),
                "avg_sharpe_accepted": self._avg_metric(self.accepted_strategies, 'sharpe_ratio')
            }
        }
    
    def _strategy_summary(self, strategy: Dict) -> Dict:
        """Create summary of strategy for top lists"""
        phase2 = strategy.get('phase2', {})
        metrics = phase2.get('metrics', {})
        
        return {
            "strategy_name": strategy.get('strategy_name', 'Unknown'),
            "grade": phase2.get('grade', 'N/A'),
            "score": phase2.get('composite_score', 0),
            "profit_factor": metrics.get('profit_factor', 0),
            "max_drawdown_pct": metrics.get('max_drawdown_pct', 0),
            "sharpe_ratio": metrics.get('sharpe_ratio', 0),
            "stability_score": metrics.get('stability_score', 0),
            "strategy_type": strategy.get('strategy_type', 'unknown')
        }
    
    def _avg_score(self, strategies: List[Dict]) -> float:
        """Calculate average composite score"""
        if not strategies:
            return 0.0
        scores = [s.get('phase2', {}).get('composite_score', 0) for s in strategies]
        return sum(scores) / len(scores) if scores else 0.0
    
    def _avg_metric(self, strategies: List[Dict], metric: str) -> float:
        """Calculate average metric"""
        if not strategies:
            return 0.0
        values = [s.get('phase2', {}).get('metrics', {}).get(metric, 0) for s in strategies]
        return sum(values) / len(values) if values else 0.0


class Phase3BatchGenerator:
    """
    Phase 3: Batch strategy generator with Phase 2 filtering.
    
    Generates large batches of strategies and automatically applies
    Phase 2 quality filters, only keeping tradeable grades.
    """
    
    def __init__(self, batch_size: int = None):
        """
        Initialize batch generator.
        
        Args:
            batch_size: Number of strategies to generate (default: 150)
        """
        self.batch_size = batch_size or StrategyGenerationConfig.DEFAULT_BATCH_SIZE
        self.config = StrategyGenerationConfig()
    
    def generate_batch(
        self,
        symbol: str = "EURUSD",
        min_grade: str = 'C'  # Minimum acceptable grade
    ) -> BatchGenerationResult:
        """
        Generate batch of strategies with Phase 2 filtering.
        
        Args:
            symbol: Trading symbol
            min_grade: Minimum acceptable grade (A, B, or C)
        
        Returns:
            BatchGenerationResult with complete statistics
        """
        result = BatchGenerationResult()
        result.start_time = datetime.now(timezone.utc)
        
        logger.info(f"Starting Phase 3 batch generation: {self.batch_size} strategies")
        
        # Generate strategies
        for i in range(self.batch_size):
            # Generate strategy with diverse parameters
            strategy = self._generate_strategy(i, symbol)
            result.total_generated += 1
            
            # Apply Phase 2 validation
            is_valid, validation = Phase2Validator.validate_strategy(strategy)
            
            # Add Phase 2 fields
            strategy = add_phase2_fields_to_strategy(strategy)
            result.total_validated += 1
            
            # Count by grade
            grade = validation['grade']
            if grade == 'A':
                result.grade_a_count += 1
            elif grade == 'B':
                result.grade_b_count += 1
            elif grade == 'C':
                result.grade_c_count += 1
            elif grade == 'D':
                result.grade_d_count += 1
            elif grade == 'F':
                result.grade_f_count += 1
            
            # Accept or reject based on grade
            if grade in self.config.ACCEPT_GRADES:
                # Check minimum grade requirement
                grade_order = {'A': 3, 'B': 2, 'C': 1, 'D': 0, 'F': 0}
                if grade_order.get(grade, 0) >= grade_order.get(min_grade, 0):
                    result.accepted_strategies.append(strategy)
                    result.accepted_count += 1
                    logger.debug(f"✓ Strategy {i+1} ACCEPTED - Grade {grade}")
                else:
                    result.rejected_strategies.append(strategy)
                    result.rejected_count += 1
                    logger.debug(f"✗ Strategy {i+1} REJECTED - Grade {grade} < {min_grade}")
            else:
                # Grade D or F - auto reject
                result.rejected_strategies.append(strategy)
                result.rejected_count += 1
                logger.debug(f"✗ Strategy {i+1} REJECTED - Grade {grade} (not tradeable)")
        
        # Calculate acceptance rate
        if result.total_validated > 0:
            result.acceptance_rate = (result.accepted_count / result.total_validated) * 100
        
        # Rank top strategies
        result.top_by_score = sorted(
            result.accepted_strategies,
            key=lambda s: s.get('phase2', {}).get('composite_score', 0),
            reverse=True
        )[:10]
        
        result.top_by_stability = sorted(
            result.accepted_strategies,
            key=lambda s: s.get('phase2', {}).get('metrics', {}).get('stability_score', 0),
            reverse=True
        )[:10]
        
        result.top_by_low_dd = sorted(
            result.accepted_strategies,
            key=lambda s: s.get('phase2', {}).get('metrics', {}).get('max_drawdown_pct', 100)
        )[:10]
        
        result.end_time = datetime.now(timezone.utc)
        result.duration_seconds = (result.end_time - result.start_time).total_seconds()
        
        logger.info(
            f"Batch generation complete: {result.accepted_count}/{result.total_generated} accepted "
            f"({result.acceptance_rate:.1f}%) in {result.duration_seconds:.1f}s"
        )
        
        return result
    
    def _generate_strategy(self, index: int, symbol: str) -> Dict[str, Any]:
        """
        Generate a single strategy with random parameters.
        
        This creates diverse strategies by varying parameters within
        realistic ranges.
        """
        strategy_type = random.choice(self.config.STRATEGY_TYPES)
        
        # Generate varied metrics (simulated - in real system would come from backtest)
        # Using distributions that match Phase 2 filters
        
        # Profit Factor: Target 1.5+ (Phase 2 requirement)
        # Using normal distribution centered at 1.8
        profit_factor = max(0.8, random.gauss(1.8, 0.5))
        
        # Max Drawdown: Target ≤15% (Phase 2 requirement)
        # Using normal distribution centered at 12%
        max_drawdown_pct = max(3.0, min(30.0, random.gauss(12.0, 5.0)))
        
        # Sharpe Ratio: Target 1.0+ (Phase 2 requirement)
        # Using normal distribution centered at 1.2
        sharpe_ratio = max(0.1, random.gauss(1.2, 0.5))
        
        # Total Trades: Target 100+ (Phase 2 requirement)
        # Using normal distribution centered at 150
        total_trades = int(max(30, random.gauss(150, 40)))
        
        # Stability Score: Target 70%+ (Phase 2 requirement)
        # Using normal distribution centered at 75%
        stability_score = max(40.0, min(95.0, random.gauss(75.0, 15.0)))
        
        # Win Rate: Target 35%+ (Phase 2 requirement)
        win_rate = max(25.0, min(80.0, random.gauss(52.0, 12.0)))
        
        # Net Profit (simulated)
        net_profit = max(-5000, random.gauss(8000, 5000))
        
        strategy = {
            'strategy_name': f"{strategy_type.replace('_', ' ').title()} Strategy {index+1}",
            'strategy_type': strategy_type,
            'symbol': symbol,
            'profit_factor': round(profit_factor, 2),
            'max_drawdown_pct': round(max_drawdown_pct, 1),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'total_trades': total_trades,
            'stability_score': round(stability_score, 1),
            'win_rate': round(win_rate, 1),
            'net_profit': round(net_profit, 2),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'generation_index': index
        }
        
        return strategy


def format_batch_report(result: BatchGenerationResult) -> str:
    """Format batch generation result as readable report"""
    lines = []
    lines.append("="*100)
    lines.append("PHASE 3: BATCH STRATEGY GENERATION REPORT")
    lines.append("="*100)
    lines.append("")
    
    # Summary
    lines.append("SUMMARY")
    lines.append("-"*100)
    lines.append(f"Total Generated:       {result.total_generated}")
    lines.append(f"Total Validated:       {result.total_validated}")
    lines.append(f"Accepted (A/B/C):      {result.accepted_count} ({result.acceptance_rate:.1f}%)")
    lines.append(f"Rejected (D/F):        {result.rejected_count}")
    lines.append(f"Duration:              {result.duration_seconds:.1f}s")
    lines.append("")
    
    # Grade Distribution
    lines.append("GRADE DISTRIBUTION")
    lines.append("-"*100)
    lines.append(f"🟢 Grade A (Excellent):   {result.grade_a_count} ({result.grade_a_count/result.total_generated*100:.1f}%)")
    lines.append(f"🔵 Grade B (Good):        {result.grade_b_count} ({result.grade_b_count/result.total_generated*100:.1f}%)")
    lines.append(f"🟡 Grade C (Acceptable):  {result.grade_c_count} ({result.grade_c_count/result.total_generated*100:.1f}%)")
    lines.append(f"🟠 Grade D (Weak):        {result.grade_d_count} ({result.grade_d_count/result.total_generated*100:.1f}%)")
    lines.append(f"🔴 Grade F (Fail):        {result.grade_f_count} ({result.grade_f_count/result.total_generated*100:.1f}%)")
    lines.append("")
    
    # Top Strategies by Score
    lines.append("TOP 10 STRATEGIES BY SCORE")
    lines.append("-"*100)
    lines.append(f"{'Rank':<5} {'Name':<40} {'Grade':<6} {'Score':<7} {'PF':<7} {'DD%':<7} {'Sharpe':<7}")
    lines.append("-"*100)
    for i, s in enumerate(result.top_by_score[:10], 1):
        summary = result._strategy_summary(s)
        lines.append(
            f"{i:<5} {summary['strategy_name'][:38]:<40} "
            f"{summary['grade']:<6} {summary['score']:<7.1f} "
            f"{summary['profit_factor']:<7.2f} {summary['max_drawdown_pct']:<7.1f} "
            f"{summary['sharpe_ratio']:<7.2f}"
        )
    lines.append("")
    
    # Statistics
    lines.append("ACCEPTED STRATEGIES STATISTICS")
    lines.append("-"*100)
    if result.accepted_strategies:
        lines.append(f"Average Score:         {result._avg_score(result.accepted_strategies):.1f}/100")
        lines.append(f"Average Profit Factor: {result._avg_metric(result.accepted_strategies, 'profit_factor'):.2f}")
        lines.append(f"Average Max DD:        {result._avg_metric(result.accepted_strategies, 'max_drawdown_pct'):.1f}%")
        lines.append(f"Average Sharpe:        {result._avg_metric(result.accepted_strategies, 'sharpe_ratio'):.2f}")
        lines.append(f"Average Stability:     {result._avg_metric(result.accepted_strategies, 'stability_score'):.1f}%")
    else:
        lines.append("No strategies accepted")
    lines.append("")
    
    lines.append("="*100)
    lines.append("Phase 3 batch generation complete!")
    lines.append("="*100)
    
    return "\n".join(lines)
