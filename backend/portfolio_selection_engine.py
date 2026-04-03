"""
Portfolio Selection Engine
Selects the best strategies for the portfolio based on multiple criteria.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class PortfolioSelectionEngine:
    """Selects optimal strategies for portfolio"""
    
    def select_best(
        self,
        strategies: List[Dict[str, Any]],
        portfolio_size: int = 5
    ) -> Dict[str, Any]:
        """
        Select best strategies based on fitness, diversity, and risk.
        
        Args:
            strategies: List of candidate strategies
            portfolio_size: Target number of strategies
            
        Returns:
            {
                "selected_strategies": List of selected strategies,
                "method": Selection method used
            }
        """
        if not strategies:
            return {"selected_strategies": [], "method": "none"}
        
        if len(strategies) <= portfolio_size:
            logger.info(f"[PORTFOLIO SELECTION] All {len(strategies)} strategies selected")
            return {
                "selected_strategies": strategies,
                "method": "all_included"
            }
        
        # Multi-criteria selection
        # 1. Sort by fitness
        sorted_by_fitness = sorted(
            strategies,
            key=lambda s: s.get("fitness", 0),
            reverse=True
        )
        
        # 2. Apply diversity constraint
        selected = []
        templates_used = set()
        
        # First pass: one from each template
        for strat in sorted_by_fitness:
            template = strat.get("template_id")
            if template not in templates_used:
                selected.append(strat)
                templates_used.add(template)
                if len(selected) >= portfolio_size:
                    break
        
        # Second pass: fill remaining slots with highest fitness
        if len(selected) < portfolio_size:
            remaining = [s for s in sorted_by_fitness if s not in selected]
            needed = portfolio_size - len(selected)
            selected.extend(remaining[:needed])
        
        logger.info(f"[PORTFOLIO SELECTION] Selected {len(selected)} strategies")
        for i, strat in enumerate(selected, 1):
            logger.info(
                f"   {i}. {strat.get('name', 'Unknown')} - "
                f"Fitness: {strat.get('fitness', 0):.2f}, "
                f"Sharpe: {strat.get('sharpe_ratio', 0):.2f}, "
                f"DD: {strat.get('max_drawdown_pct', 0):.1f}%"
            )
        
        return {
            "selected_strategies": selected,
            "method": "fitness_with_diversity"
        }
