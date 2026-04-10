"""
Composite Scoring Engine
Unified scoring system for ranking forex trading strategies based on multiple performance metrics.
Uses dynamic configuration from strategy_config module.
"""

import logging
from typing import Dict, Any, List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

# Import config manager
try:
    from strategy_config import config_manager, get_filters, get_scoring
except ImportError:
    config_manager = None
    logger.warning("strategy_config not available, using hardcoded defaults")


class Grade(str, Enum):
    """Strategy grade classification"""
    A = "A"  # Excellent (90-100)
    B = "B"  # Good (80-89)
    C = "C"  # Acceptable (70-79)
    D = "D"  # Poor (60-69)
    F = "F"  # Fail (<60)


class StrategyGrader:
    """
    Phase 2: Strategy Grading System
    Assigns letter grades (A-F) based on composite score and quality metrics.
    """
    
    @staticmethod
    def calculate_grade(composite_score: float, strategy: dict) -> tuple[Grade, str, dict]:
        """
        Calculate strategy grade based on composite score and quality filters.
        
        Returns:
            (grade, description, details)
        """
        # Check if passes minimum filters
        passes, fail_reasons = QualityFilters.passes_all(strategy)
        
        if not passes:
            return (
                Grade.F,
                f"REJECTED - Failed quality filters: {', '.join(fail_reasons)}",
                {
                    "score": composite_score,
                    "fail_reasons": fail_reasons,
                    "recommendation": "Do not trade - does not meet minimum requirements"
                }
            )
        
        # Grade based on composite score
        if composite_score >= 90.0:
            return (
                Grade.A,
                "Excellent - Production ready, high confidence",
                {
                    "score": composite_score,
                    "quality": "exceptional",
                    "recommendation": "Deploy with full capital allocation"
                }
            )
        elif composite_score >= 80.0:
            return (
                Grade.B,
                "Good - Solid performance, ready for live trading",
                {
                    "score": composite_score,
                    "quality": "strong",
                    "recommendation": "Deploy with standard capital allocation"
                }
            )
        elif composite_score >= 70.0:
            return (
                Grade.C,
                "Acceptable - Passes minimum requirements",
                {
                    "score": composite_score,
                    "quality": "adequate",
                    "recommendation": "Deploy with reduced capital allocation, monitor closely"
                }
            )
        elif composite_score >= 60.0:
            return (
                Grade.D,
                "Weak - Marginal performance, high risk",
                {
                    "score": composite_score,
                    "quality": "poor",
                    "recommendation": "Paper trade only, not recommended for live deployment"
                }
            )
        else:
            return (
                Grade.F,
                "Fail - Insufficient performance",
                {
                    "score": composite_score,
                    "quality": "unacceptable",
                    "recommendation": "Do not trade - performance too weak"
                }
            )
    
    @staticmethod
    def get_grade_emoji(grade: Grade) -> str:
        """Get emoji for grade"""
        emoji_map = {
            Grade.A: "🟢",
            Grade.B: "🔵",
            Grade.C: "🟡",
            Grade.D: "🟠",
            Grade.F: "🔴"
        }
        return emoji_map.get(grade, "⚪")
    
    @staticmethod
    def get_grade_color(grade: Grade) -> str:
        """Get color for grade (for UI)"""
        color_map = {
            Grade.A: "emerald",
            Grade.B: "blue",
            Grade.C: "yellow",
            Grade.D: "orange",
            Grade.F: "red"
        }
        return color_map.get(grade, "gray")
    
    @staticmethod
    def is_tradeable(grade: Grade) -> bool:
        """Check if strategy is tradeable based on grade"""
        return grade in [Grade.A, Grade.B, Grade.C]


class CompositeScoreWeights:
    """Weights for composite score calculation - loads from config"""
    
    @classmethod
    def get_weights(cls) -> Dict[str, float]:
        """Get scoring weights from config"""
        if config_manager:
            s = config_manager.scoring
            return {
                'profit_factor': s.profit_factor_weight,
                'max_drawdown': s.drawdown_weight,
                'sharpe_ratio': s.sharpe_weight,
                'monte_carlo': s.monte_carlo_weight,
                'walk_forward': s.walkforward_weight
            }
        # Fallback defaults
        return {
            'profit_factor': 0.35,
            'max_drawdown': 0.25,
            'sharpe_ratio': 0.20,
            'monte_carlo': 0.12,
            'walk_forward': 0.08
        }
    
    @classmethod
    def validate(cls):
        """Ensure weights sum to 1.0"""
        weights = cls.get_weights()
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001, f"Weights must sum to 1.0, got {total}"


class QualityFilters:
    """
    Quality filters for strategy validation.
    Loads thresholds from config system - NO HARDCODED VALUES.
    """
    
    @classmethod
    def _get_config(cls):
        """Get filter config with fallback"""
        if config_manager:
            return config_manager.filters
        # Fallback to strict defaults (Phase 2)
        class DefaultFilters:
            min_profit_factor = 1.5
            max_drawdown_pct = 15.0
            min_stability_pct = 70.0
            min_trades = 100
            min_sharpe_ratio = 1.0
            min_win_rate = 35.0
            strong_pf = 2.0
            strong_dd = 10.0
            strong_sharpe = 1.5
            moderate_pf = 1.5
            moderate_dd = 15.0
        return DefaultFilters()
    
    @classmethod
    def passes_all(cls, strategy: dict) -> tuple:
        """
        Check if strategy passes all quality filters.
        Returns (passes: bool, reasons: list)
        """
        f = cls._get_config()
        reasons = []
        
        pf = strategy.get('profit_factor', 0)
        if pf < f.min_profit_factor:
            reasons.append(f"PF {pf:.2f} < {f.min_profit_factor}")
        
        dd = abs(strategy.get('max_drawdown_pct', 100))
        if dd > f.max_drawdown_pct:
            reasons.append(f"DD {dd:.1f}% > {f.max_drawdown_pct}%")
        
        sharpe = strategy.get('sharpe_ratio', -999)
        if sharpe < f.min_sharpe_ratio:
            reasons.append(f"Sharpe {sharpe:.2f} < {f.min_sharpe_ratio}")
        
        trades = strategy.get('total_trades', 0)
        if trades < f.min_trades:
            reasons.append(f"Trades {trades} < {f.min_trades}")
        
        # Stability check
        stability = strategy.get('stability_score', 0)
        if not stability:
            wf = strategy.get('walkforward', {})
            stability = wf.get('stability_score', 0) * 100 if wf else 0
        if not stability:
            mc = strategy.get('monte_carlo_score', 0)
            stability = mc if mc else 50
        if stability < f.min_stability_pct:
            reasons.append(f"Stability {stability:.0f}% < {f.min_stability_pct}%")
        
        return (len(reasons) == 0, reasons)
    
    @classmethod
    def get_quality_label(cls, strategy: dict) -> tuple:
        """
        Get quality label for strategy.
        Returns (label: str, color: str, emoji: str)
        Only Strong and Moderate shown - Weak hidden from results.
        """
        f = cls._get_config()
        pf = strategy.get('profit_factor', 0)
        dd = abs(strategy.get('max_drawdown_pct', 100))
        sharpe = strategy.get('sharpe_ratio', 0)
        
        # Check if passes minimum filters first
        passes, _ = cls.passes_all(strategy)
        
        if not passes:
            return ('Weak', 'red', '🔴')
        
        # Strong: High PF, Low DD, High Sharpe
        if pf >= f.strong_pf and dd <= f.strong_dd and sharpe >= f.strong_sharpe:
            return ('Strong', 'emerald', '🟢')
        
        # Moderate: Passes minimum filters
        return ('Moderate', 'amber', '🟡')
    
    @classmethod
    def can_generate_cbot(cls, strategy: dict) -> tuple:
        """
        Check if strategy is allowed to generate cBot.
        Returns (allowed: bool, reason: str)
        """
        passes, reasons = cls.passes_all(strategy)
        if not passes:
            return (False, f"Strategy does not meet quality filters: {', '.join(reasons)}")
        return (True, "Strategy validated for cBot generation")
    
    @classmethod
    def get_detailed_rejection_report(cls, strategy: dict) -> dict:
        """
        Phase 2: Get detailed rejection report with specific failure reasons.
        
        Returns comprehensive rejection details for debugging and improvement.
        """
        f = cls._get_config()
        passes, reasons = cls.passes_all(strategy)
        
        if passes:
            return {
                "status": "accepted",
                "passes_all_filters": True,
                "rejection_reasons": [],
                "metrics": {
                    "profit_factor": strategy.get('profit_factor', 0),
                    "max_drawdown_pct": abs(strategy.get('max_drawdown_pct', 0)),
                    "sharpe_ratio": strategy.get('sharpe_ratio', 0),
                    "total_trades": strategy.get('total_trades', 0),
                    "stability_score": strategy.get('stability_score', 0)
                },
                "message": "Strategy passes all quality filters"
            }
        
        # Build detailed rejection report
        rejection_details = []
        
        pf = strategy.get('profit_factor', 0)
        if pf < f.min_profit_factor:
            rejection_details.append({
                "filter": "Profit Factor",
                "value": round(pf, 2),
                "threshold": f.min_profit_factor,
                "reason": f"Profit Factor too low ({pf:.2f} < {f.min_profit_factor})",
                "improvement_needed": f"{((f.min_profit_factor - pf) / pf * 100):.1f}%",
                "recommendation": "Strategy needs higher win rate or better risk/reward ratio"
            })
        
        dd = abs(strategy.get('max_drawdown_pct', 100))
        if dd > f.max_drawdown_pct:
            rejection_details.append({
                "filter": "Max Drawdown",
                "value": round(dd, 1),
                "threshold": f.max_drawdown_pct,
                "reason": f"Max Drawdown too high ({dd:.1f}% > {f.max_drawdown_pct}%)",
                "improvement_needed": f"{dd - f.max_drawdown_pct:.1f}% reduction required",
                "recommendation": "Implement tighter risk management, reduce position sizes, or add trailing stops"
            })
        
        sharpe = strategy.get('sharpe_ratio', -999)
        if sharpe < f.min_sharpe_ratio:
            rejection_details.append({
                "filter": "Sharpe Ratio",
                "value": round(sharpe, 2),
                "threshold": f.min_sharpe_ratio,
                "reason": f"Sharpe Ratio too low ({sharpe:.2f} < {f.min_sharpe_ratio})",
                "improvement_needed": f"{f.min_sharpe_ratio - sharpe:.2f} increase required",
                "recommendation": "Improve risk-adjusted returns by reducing volatility or increasing consistency"
            })
        
        trades = strategy.get('total_trades', 0)
        if trades < f.min_trades:
            rejection_details.append({
                "filter": "Total Trades",
                "value": trades,
                "threshold": f.min_trades,
                "reason": f"Insufficient trades ({trades} < {f.min_trades})",
                "improvement_needed": f"{f.min_trades - trades} more trades required",
                "recommendation": "Test with longer historical period or adjust entry conditions for more signals"
            })
        
        stability = strategy.get('stability_score', 0)
        if stability < f.min_stability_pct:
            rejection_details.append({
                "filter": "Stability Score",
                "value": round(stability, 1),
                "threshold": f.min_stability_pct,
                "reason": f"Stability too low ({stability:.1f}% < {f.min_stability_pct}%)",
                "improvement_needed": f"{f.min_stability_pct - stability:.1f}% increase required",
                "recommendation": "Strategy shows inconsistent performance across different market conditions or time periods"
            })
        
        return {
            "status": "rejected",
            "passes_all_filters": False,
            "rejection_reasons": reasons,
            "detailed_failures": rejection_details,
            "failed_filter_count": len(rejection_details),
            "metrics": {
                "profit_factor": pf,
                "max_drawdown_pct": dd,
                "sharpe_ratio": sharpe,
                "total_trades": trades,
                "stability_score": stability
            },
            "message": f"Strategy REJECTED - Failed {len(rejection_details)} quality filter(s)",
            "recommendation": "Review rejection details and improve strategy before resubmitting"
        }


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
        sharpe_weight: float = None,
        drawdown_weight: float = None,
        monte_carlo_weight: float = None,
        walk_forward_weight: float = None,
        profit_factor_weight: float = None,
    ):
        # Get weights from config or use provided
        weights = CompositeScoreWeights.get_weights()
        
        self.sharpe_weight = sharpe_weight if sharpe_weight is not None else weights['sharpe_ratio']
        self.drawdown_weight = drawdown_weight if drawdown_weight is not None else weights['max_drawdown']
        self.monte_carlo_weight = monte_carlo_weight if monte_carlo_weight is not None else weights['monte_carlo']
        self.walk_forward_weight = walk_forward_weight if walk_forward_weight is not None else weights['walk_forward']
        self.profit_factor_weight = profit_factor_weight if profit_factor_weight is not None else weights['profit_factor']
        
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
