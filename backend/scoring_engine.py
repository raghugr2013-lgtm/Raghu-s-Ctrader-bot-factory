"""
Composite Scoring Engine
Unified scoring system for ranking forex trading strategies based on multiple performance metrics.
"""

import logging
from typing import Dict, Any, List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class Grade(str, Enum):
    """Strategy grade classification"""
    A = "A"  # Excellent (90-100)
    B = "B"  # Good (80-89)
    C = "C"  # Acceptable (70-79)
    D = "D"  # Poor (60-69)
    F = "F"  # Fail (<60)


class CompositeScoreWeights:
    """Default weights for composite score calculation - UPDATED for quality"""
    PROFIT_FACTOR = 0.35     # 35% - PRIMARY: Profitability (highest weight)
    MAX_DRAWDOWN = 0.25      # 25% - Capital preservation  
    SHARPE_RATIO = 0.20      # 20% - Risk-adjusted returns
    MONTE_CARLO = 0.12       # 12% - Statistical robustness
    WALK_FORWARD = 0.08      # 8% - Generalization ability
    
    @classmethod
    def validate(cls):
        """Ensure weights sum to 1.0"""
        total = cls.SHARPE_RATIO + cls.MAX_DRAWDOWN + cls.MONTE_CARLO + cls.WALK_FORWARD + cls.PROFIT_FACTOR
        assert abs(total - 1.0) < 0.001, f"Weights must sum to 1.0, got {total}"


class QualityFilters:
    """Minimum quality thresholds for strategy validation"""
    MIN_PROFIT_FACTOR = 1.2       # Must be profitable with margin
    MAX_DRAWDOWN_PCT = 20.0       # Maximum allowed drawdown
    MIN_STABILITY_PCT = 60.0      # Minimum stability score
    MIN_TRADES = 50               # Minimum number of trades
    MIN_WIN_RATE = 30.0           # Minimum win rate %
    MIN_SHARPE = 0.0              # Minimum Sharpe ratio (positive)
    
    @classmethod
    def passes_all(cls, strategy: dict) -> tuple:
        """
        Check if strategy passes all quality filters.
        Returns (passes: bool, reasons: list)
        """
        reasons = []
        
        pf = strategy.get('profit_factor', 0)
        if pf < cls.MIN_PROFIT_FACTOR:
            reasons.append(f"PF {pf:.2f} < {cls.MIN_PROFIT_FACTOR}")
        
        dd = abs(strategy.get('max_drawdown_pct', 100))
        if dd > cls.MAX_DRAWDOWN_PCT:
            reasons.append(f"DD {dd:.1f}% > {cls.MAX_DRAWDOWN_PCT}%")
        
        # Stability from walkforward or monte carlo
        stability = strategy.get('stability_score', 0)
        if not stability:
            wf = strategy.get('walkforward', {})
            stability = wf.get('stability_score', 0) * 100 if wf else 0
        if not stability:
            mc = strategy.get('monte_carlo_score', 0)
            stability = mc if mc else 50  # Default to 50 if not calculated
        if stability < cls.MIN_STABILITY_PCT:
            reasons.append(f"Stability {stability:.0f}% < {cls.MIN_STABILITY_PCT}%")
        
        trades = strategy.get('total_trades', 0)
        if trades < cls.MIN_TRADES:
            reasons.append(f"Trades {trades} < {cls.MIN_TRADES}")
        
        sharpe = strategy.get('sharpe_ratio', -999)
        if sharpe < cls.MIN_SHARPE:
            reasons.append(f"Sharpe {sharpe:.2f} < {cls.MIN_SHARPE}")
        
        return (len(reasons) == 0, reasons)
    
    @classmethod
    def get_quality_label(cls, strategy: dict) -> tuple:
        """
        Get quality label for strategy.
        Returns (label: str, color: str, emoji: str)
        """
        pf = strategy.get('profit_factor', 0)
        dd = abs(strategy.get('max_drawdown_pct', 100))
        sharpe = strategy.get('sharpe_ratio', 0)
        
        # Strong: PF ≥ 1.5, DD ≤ 15%, Sharpe ≥ 1.0
        if pf >= 1.5 and dd <= 15 and sharpe >= 1.0:
            return ('Strong', 'emerald', '🟢')
        
        # Moderate: PF ≥ 1.2, DD ≤ 20%
        if pf >= 1.2 and dd <= 20:
            return ('Moderate', 'amber', '🟡')
        
        # Weak: Everything else
        return ('Weak', 'red', '🔴')


class MetricNormalizer:
    """
    Normalizes various metrics to 0-100 scale.
    Each metric has optimal ranges and normalization logic.
    """
    
    @staticmethod
    def normalize_sharpe_ratio(sharpe: float) -> float:
        """
        Normalize Sharpe ratio to 0-100 scale.
        
        Reference scale:
        - < 0: 0 points (losing strategy)
        - 0-1: 0-50 points (below acceptable)
        - 1-2: 50-75 points (acceptable)
        - 2-3: 75-90 points (good)
        - > 3: 90-100 points (excellent)
        """
        if sharpe <= 0:
            return 0.0
        elif sharpe <= 1.0:
            return sharpe * 50.0
        elif sharpe <= 2.0:
            return 50.0 + (sharpe - 1.0) * 25.0
        elif sharpe <= 3.0:
            return 75.0 + (sharpe - 2.0) * 15.0
        else:
            # Cap at 100, with diminishing returns
            return min(100.0, 90.0 + (sharpe - 3.0) * 5.0)
    
    @staticmethod
    def normalize_max_drawdown(drawdown_pct: float) -> float:
        """
        Normalize max drawdown to 0-100 scale (inverted - lower is better).
        
        Reference scale:
        - 0-5%: 100-90 points (excellent)
        - 5-10%: 90-80 points (good)
        - 10-20%: 80-60 points (acceptable)
        - 20-30%: 60-40 points (poor)
        - 30-50%: 40-20 points (very poor)
        - > 50%: 20-0 points (unacceptable)
        """
        dd = abs(drawdown_pct)
        
        if dd <= 5.0:
            return 100.0 - dd * 2.0
        elif dd <= 10.0:
            return 90.0 - (dd - 5.0) * 2.0
        elif dd <= 20.0:
            return 80.0 - (dd - 10.0) * 2.0
        elif dd <= 30.0:
            return 60.0 - (dd - 20.0) * 2.0
        elif dd <= 50.0:
            return 40.0 - (dd - 30.0) * 1.0
        else:
            return max(0.0, 20.0 - (dd - 50.0) * 0.4)
    
    @staticmethod
    def normalize_monte_carlo_score(mc_score: float) -> float:
        """
        Normalize Monte Carlo score (already 0-100).
        Can apply slight adjustments if needed.
        """
        return max(0.0, min(100.0, mc_score))
    
    @staticmethod
    def normalize_walk_forward_retention(retention_pct: float) -> float:
        """
        Normalize walk-forward retention to 0-100 scale.
        
        Reference scale:
        - > 80%: 100-90 points (excellent generalization)
        - 60-80%: 90-70 points (good)
        - 40-60%: 70-50 points (acceptable)
        - 20-40%: 50-30 points (poor)
        - < 20%: 30-0 points (overfitting)
        """
        if retention_pct >= 80.0:
            return 90.0 + (retention_pct - 80.0) * 0.5
        elif retention_pct >= 60.0:
            return 70.0 + (retention_pct - 60.0) * 1.0
        elif retention_pct >= 40.0:
            return 50.0 + (retention_pct - 40.0) * 1.0
        elif retention_pct >= 20.0:
            return 30.0 + (retention_pct - 20.0) * 1.0
        else:
            return retention_pct * 1.5
    
    @staticmethod
    def normalize_profit_factor(pf: float) -> float:
        """
        Normalize profit factor to 0-100 scale.
        UPDATED: More aggressive scoring - PF near 1.0 gets very low scores.
        
        Reference scale:
        - < 1.0: 0 points (losing strategy)
        - 1.0-1.2: 0-20 points (barely profitable - NOT TRADABLE)
        - 1.2-1.5: 20-50 points (marginal - minimum acceptable)
        - 1.5-2.0: 50-75 points (good)
        - 2.0-3.0: 75-90 points (very good)
        - > 3.0: 90-100 points (excellent)
        """
        if pf < 1.0:
            return 0.0
        elif pf < 1.2:
            # Heavily penalize PF between 1.0 and 1.2 (barely profitable)
            return (pf - 1.0) * 100.0  # 0-20 points
        elif pf < 1.5:
            # Still penalized but acceptable range
            return 20.0 + (pf - 1.2) * 100.0  # 20-50 points
        elif pf <= 2.0:
            return 50.0 + (pf - 1.5) * 50.0  # 50-75 points
        elif pf <= 3.0:
            return 75.0 + (pf - 2.0) * 15.0  # 75-90 points
        else:
            return min(100.0, 90.0 + (pf - 3.0) * 5.0)


class CompositeScorer:
    """
    Calculates composite scores for trading strategies.
    Combines multiple performance metrics into a single unified score.
    """
    
    def __init__(
        self,
        sharpe_weight: float = CompositeScoreWeights.SHARPE_RATIO,
        drawdown_weight: float = CompositeScoreWeights.MAX_DRAWDOWN,
        monte_carlo_weight: float = CompositeScoreWeights.MONTE_CARLO,
        walk_forward_weight: float = CompositeScoreWeights.WALK_FORWARD,
        profit_factor_weight: float = CompositeScoreWeights.PROFIT_FACTOR,
    ):
        self.sharpe_weight = sharpe_weight
        self.drawdown_weight = drawdown_weight
        self.monte_carlo_weight = monte_carlo_weight
        self.walk_forward_weight = walk_forward_weight
        self.profit_factor_weight = profit_factor_weight
        
        # Validate weights sum to 1.0
        total = sum([
            self.sharpe_weight,
            self.drawdown_weight,
            self.monte_carlo_weight,
            self.walk_forward_weight,
            self.profit_factor_weight
        ])
        
        if abs(total - 1.0) > 0.001:
            logger.warning(f"Weights sum to {total}, not 1.0. Normalizing...")
            self.sharpe_weight /= total
            self.drawdown_weight /= total
            self.monte_carlo_weight /= total
            self.walk_forward_weight /= total
            self.profit_factor_weight /= total
        
        self.normalizer = MetricNormalizer()
    
    def calculate_composite_score(self, strategy: Dict[str, Any]) -> float:
        """
        Calculate composite score for a strategy.
        
        Args:
            strategy: Strategy dict with performance metrics
            
        Returns:
            Composite score (0-100)
        """
        # Extract raw metrics
        sharpe = strategy.get("sharpe_ratio", 0.0)
        max_dd = strategy.get("max_drawdown_pct", 100.0)
        mc_score = strategy.get("monte_carlo_score", 0.0)
        wf_retention = strategy.get("walk_forward_retention", 50.0)
        profit_factor = strategy.get("profit_factor", 1.0)
        
        # Normalize each metric to 0-100 scale
        sharpe_norm = self.normalizer.normalize_sharpe_ratio(sharpe)
        dd_norm = self.normalizer.normalize_max_drawdown(max_dd)
        mc_norm = self.normalizer.normalize_monte_carlo_score(mc_score)
        wf_norm = self.normalizer.normalize_walk_forward_retention(wf_retention)
        pf_norm = self.normalizer.normalize_profit_factor(profit_factor)
        
        # Calculate weighted composite score
        composite = (
            sharpe_norm * self.sharpe_weight +
            dd_norm * self.drawdown_weight +
            mc_norm * self.monte_carlo_weight +
            wf_norm * self.walk_forward_weight +
            pf_norm * self.profit_factor_weight
        )
        
        return round(composite, 2)
    
    def assign_grade(self, score: float) -> Grade:
        """
        Assign letter grade based on composite score.
        
        Args:
            score: Composite score (0-100)
            
        Returns:
            Grade enum (A, B, C, D, F)
        """
        if score >= 90.0:
            return Grade.A
        elif score >= 80.0:
            return Grade.B
        elif score >= 70.0:
            return Grade.C
        elif score >= 60.0:
            return Grade.D
        else:
            return Grade.F
    
    def score_strategy(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score a single strategy and enrich with composite metrics.
        
        Args:
            strategy: Strategy dict
            
        Returns:
            Strategy enriched with composite_score and composite_grade
        """
        composite_score = self.calculate_composite_score(strategy)
        composite_grade = self.assign_grade(composite_score)
        
        enriched = strategy.copy()
        enriched.update({
            "composite_score": composite_score,
            "composite_grade": composite_grade.value,
        })
        
        return enriched
    
    def score_and_rank_strategies(
        self,
        strategies: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Score all strategies, rank them, and return sorted list.
        
        Args:
            strategies: List of strategy dicts
            
        Returns:
            Tuple of (sorted_strategies, summary_stats)
        """
        if not strategies:
            return [], {
                "total_strategies": 0,
                "avg_composite_score": 0,
                "grade_distribution": {},
            }
        
        logger.info(f"Scoring and ranking {len(strategies)} strategies...")
        
        # Score each strategy
        scored_strategies = []
        for idx, strategy in enumerate(strategies):
            scored = self.score_strategy(strategy)
            scored_strategies.append(scored)
            
            logger.debug(
                f"[{idx+1}/{len(strategies)}] {strategy.get('name', 'Unknown')}: "
                f"Score={scored['composite_score']}, Grade={scored['composite_grade']}"
            )
        
        # Sort by composite score (descending)
        sorted_strategies = sorted(
            scored_strategies,
            key=lambda s: s.get("composite_score", 0),
            reverse=True
        )
        
        # Add ranking position
        for rank, strategy in enumerate(sorted_strategies, start=1):
            strategy["ranking_position"] = rank
        
        # Calculate summary statistics
        scores = [s.get("composite_score", 0) for s in sorted_strategies]
        grades = [s.get("composite_grade", "F") for s in sorted_strategies]
        
        grade_distribution = {
            "A": grades.count("A"),
            "B": grades.count("B"),
            "C": grades.count("C"),
            "D": grades.count("D"),
            "F": grades.count("F"),
        }
        
        summary = {
            "total_strategies": len(sorted_strategies),
            "avg_composite_score": sum(scores) / len(scores) if scores else 0,
            "min_composite_score": min(scores) if scores else 0,
            "max_composite_score": max(scores) if scores else 0,
            "grade_distribution": grade_distribution,
            "top_grade": sorted_strategies[0].get("composite_grade", "F") if sorted_strategies else "F",
            "top_score": sorted_strategies[0].get("composite_score", 0) if sorted_strategies else 0,
        }
        
        logger.info(
            f"Scoring complete: Avg={summary['avg_composite_score']:.2f}, "
            f"Top={summary['top_score']:.2f} (Grade {summary['top_grade']})"
        )
        logger.info(f"Grade distribution: {grade_distribution}")
        
        return sorted_strategies, summary


class StrategyRanker:
    """
    High-level interface for ranking strategies in the pipeline.
    Handles edge cases and fallback logic.
    """
    
    def __init__(self):
        self.scorer = CompositeScorer()
    
    def rank_strategies(
        self,
        strategies: List[Dict[str, Any]],
        top_n: int = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Rank strategies by composite score and optionally select top N.
        
        Args:
            strategies: List of strategy dicts
            top_n: If specified, return only top N strategies
            
        Returns:
            Tuple of (ranked_strategies, summary)
        """
        try:
            # Score and rank
            ranked_strategies, summary = self.scorer.score_and_rank_strategies(strategies)
            
            # Optionally limit to top N
            if top_n is not None and top_n > 0:
                original_count = len(ranked_strategies)
                ranked_strategies = ranked_strategies[:top_n]
                logger.info(f"Selected top {len(ranked_strategies)} of {original_count} strategies")
            
            return ranked_strategies, summary
            
        except Exception as e:
            logger.error(f"Strategy ranking failed: {str(e)}")
            
            # Fallback: Return strategies unsorted with minimal scoring
            fallback_strategies = []
            for idx, strategy in enumerate(strategies):
                fallback = strategy.copy()
                fallback.update({
                    "composite_score": 50.0,  # Neutral score
                    "composite_grade": "C",
                    "ranking_position": idx + 1,
                })
                fallback_strategies.append(fallback)
            
            fallback_summary = {
                "total_strategies": len(fallback_strategies),
                "avg_composite_score": 50.0,
                "fallback": True,
                "error": str(e),
            }
            
            return fallback_strategies, fallback_summary


# Validate weights on module load
CompositeScoreWeights.validate()
