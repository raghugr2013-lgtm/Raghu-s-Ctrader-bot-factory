"""
Enhanced Scoring Engine
Combines multiple validation metrics into a composite score for strategy ranking.

Composite Score Formula:
- Backtest Performance: 25%
- Walk-Forward Consistency: 25%
- Monte Carlo Robustness: 50%
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)


@dataclass
class CompositeScore:
    """Composite score for a strategy"""
    strategy_id: str
    strategy_name: str
    
    # Individual scores (0-100)
    backtest_score: float
    walkforward_score: float
    montecarlo_score: float
    forward_test_score: Optional[float] = None
    
    # Composite score (0-100)
    composite_score: float
    
    # Component weights used
    weights: Dict[str, float] = None
    
    # Ranking
    rank: Optional[int] = None


class EnhancedScoringEngine:
    """
    Calculates composite scores for strategies based on multiple validation metrics.
    
    Default weights:
    - Backtest: 25%
    - Walk-Forward: 25%
    - Monte Carlo: 50%
    """
    
    def __init__(
        self,
        backtest_weight: float = 0.25,
        walkforward_weight: float = 0.25,
        montecarlo_weight: float = 0.50,
        forward_test_weight: float = 0.0
    ):
        # Normalize weights
        total = backtest_weight + walkforward_weight + montecarlo_weight + forward_test_weight
        self.backtest_weight = backtest_weight / total
        self.walkforward_weight = walkforward_weight / total
        self.montecarlo_weight = montecarlo_weight / total
        self.forward_test_weight = forward_test_weight / total
    
    def calculate_composite_score(
        self,
        strategy: Dict[str, Any],
        backtest_metrics: Dict[str, Any],
        walkforward_metrics: Optional[Dict[str, Any]] = None,
        montecarlo_metrics: Optional[Dict[str, Any]] = None,
        forward_test_metrics: Optional[Dict[str, Any]] = None
    ) -> CompositeScore:
        """
        Calculate composite score for a strategy.
        
        Args:
            strategy: Strategy configuration
            backtest_metrics: Metrics from backtesting
            walkforward_metrics: Metrics from walk-forward validation (optional)
            montecarlo_metrics: Metrics from Monte Carlo simulation (optional)
            forward_test_metrics: Metrics from forward testing (optional)
            
        Returns:
            CompositeScore with weighted average
        """
        # Calculate individual scores
        backtest_score = self._calculate_backtest_score(backtest_metrics)
        
        walkforward_score = 50.0  # Default neutral score
        if walkforward_metrics:
            walkforward_score = self._calculate_walkforward_score(walkforward_metrics)
        
        montecarlo_score = 50.0  # Default neutral score
        if montecarlo_metrics:
            montecarlo_score = montecarlo_metrics.get("robustness_score", 50.0)
        
        forward_test_score = None
        if forward_test_metrics:
            forward_test_score = forward_test_metrics.get("decay_score", 50.0)
        
        # Calculate weighted composite score
        composite = (
            backtest_score * self.backtest_weight +
            walkforward_score * self.walkforward_weight +
            montecarlo_score * self.montecarlo_weight
        )
        
        if forward_test_score is not None and self.forward_test_weight > 0:
            composite += forward_test_score * self.forward_test_weight
        
        return CompositeScore(
            strategy_id=strategy.get("id", "unknown"),
            strategy_name=strategy.get("name", "Unknown"),
            backtest_score=backtest_score,
            walkforward_score=walkforward_score,
            montecarlo_score=montecarlo_score,
            forward_test_score=forward_test_score,
            composite_score=round(composite, 2),
            weights={
                "backtest": self.backtest_weight,
                "walkforward": self.walkforward_weight,
                "montecarlo": self.montecarlo_weight,
                "forward_test": self.forward_test_weight
            }
        )
    
    def _calculate_backtest_score(self, metrics: Dict[str, Any]) -> float:
        """
        Calculate backtest score (0-100) from performance metrics.
        
        Components:
        - Sharpe ratio: 40%
        - Win rate: 30%
        - Profit factor: 20%
        - Max drawdown: 10%
        """
        # Sharpe ratio component (0-40)
        # Normalize: 0 = 0, 2.0+ = 40
        sharpe = metrics.get("sharpe_ratio", 0)
        sharpe_score = min(40, (sharpe / 2.0) * 40)
        
        # Win rate component (0-30)
        # Normalize: 0% = 0, 70%+ = 30
        win_rate = metrics.get("win_rate", 0)
        win_rate_score = min(30, (win_rate / 70) * 30)
        
        # Profit factor component (0-20)
        # Normalize: 0 = 0, 2.5+ = 20
        profit_factor = metrics.get("profit_factor", 0)
        pf_score = min(20, (profit_factor / 2.5) * 20)
        
        # Drawdown component (0-10)
        # Lower is better: 0% = 10, 40%+ = 0
        max_dd = metrics.get("max_drawdown_pct", 100)
        dd_score = max(0, 10 - (max_dd / 40) * 10)
        
        total_score = sharpe_score + win_rate_score + pf_score + dd_score
        return round(total_score, 1)
    
    def _calculate_walkforward_score(self, metrics: Dict[str, Any]) -> float:
        """
        Calculate walk-forward score (0-100) from validation metrics.
        
        Components:
        - Consistency score: 60%
        - Average performance: 40%
        """
        # Consistency component (0-60)
        consistency = metrics.get("consistency_score", 0)
        consistency_score = (consistency / 100) * 60
        
        # Average performance component (0-40)
        # Based on average Sharpe across segments
        avg_sharpe = metrics.get("avg_sharpe", 0)
        performance_score = min(40, (avg_sharpe / 2.0) * 40)
        
        total_score = consistency_score + performance_score
        return round(total_score, 1)
    
    def rank_strategies(
        self,
        composite_scores: List[CompositeScore],
        top_n: Optional[int] = None
    ) -> List[CompositeScore]:
        """
        Rank strategies by composite score.
        
        Args:
            composite_scores: List of CompositeScore objects
            top_n: Return only top N strategies (None = all)
            
        Returns:
            Ranked list of CompositeScore objects
        """
        # Sort by composite score (descending)
        ranked = sorted(
            composite_scores,
            key=lambda s: s.composite_score,
            reverse=True
        )
        
        # Assign ranks
        for i, score in enumerate(ranked, 1):
            score.rank = i
        
        # Return top N if specified
        if top_n:
            return ranked[:top_n]
        
        return ranked
    
    def batch_score_strategies(
        self,
        strategies: List[Dict[str, Any]],
        backtest_results: Dict[str, Dict[str, Any]],
        walkforward_results: Optional[Dict[str, Dict[str, Any]]] = None,
        montecarlo_results: Optional[Dict[str, Dict[str, Any]]] = None,
        forward_test_results: Optional[Dict[str, Dict[str, Any]]] = None,
        top_n: Optional[int] = None
    ) -> List[CompositeScore]:
        """
        Calculate and rank composite scores for multiple strategies.
        
        Args:
            strategies: List of strategy configurations
            backtest_results: Dict mapping strategy_id -> backtest metrics
            walkforward_results: Dict mapping strategy_id -> walkforward metrics
            montecarlo_results: Dict mapping strategy_id -> montecarlo metrics
            forward_test_results: Dict mapping strategy_id -> forward test metrics
            top_n: Return only top N strategies (None = all)
            
        Returns:
            Ranked list of CompositeScore objects
        """
        logger.info(f"[ENHANCED SCORING] Calculating composite scores for {len(strategies)} strategies")
        
        composite_scores = []
        
        for strategy in strategies:
            strategy_id = strategy.get("id")
            
            # Get metrics for this strategy
            backtest = backtest_results.get(strategy_id, {})
            walkforward = walkforward_results.get(strategy_id) if walkforward_results else None
            montecarlo = montecarlo_results.get(strategy_id) if montecarlo_results else None
            forward_test = forward_test_results.get(strategy_id) if forward_test_results else None
            
            # Calculate composite score
            score = self.calculate_composite_score(
                strategy=strategy,
                backtest_metrics=backtest,
                walkforward_metrics=walkforward,
                montecarlo_metrics=montecarlo,
                forward_test_metrics=forward_test
            )
            
            composite_scores.append(score)
        
        # Rank strategies
        ranked = self.rank_strategies(composite_scores, top_n=top_n)
        
        logger.info("[ENHANCED SCORING] ✓ Ranking complete")
        if ranked:
            logger.info("[ENHANCED SCORING] Top 3:")
            for i, score in enumerate(ranked[:3], 1):
                logger.info(
                    f"[ENHANCED SCORING]    {i}. {score.strategy_name} - "
                    f"Composite: {score.composite_score:.1f} "
                    f"(BT: {score.backtest_score:.1f}, WF: {score.walkforward_score:.1f}, MC: {score.montecarlo_score:.1f})"
                )
        
        return ranked
