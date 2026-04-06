"""
Strategy Diversity Engine
Analyzes and filters strategies based on category diversity and uniqueness scoring.

Ensures the portfolio contains strategies with different:
- Technical indicator combinations
- Trading styles (trend/mean-reversion/breakout)
- Parameter spaces
- Risk profiles
"""

import logging
from typing import List, Dict, Any
from collections import defaultdict
import math

logger = logging.getLogger(__name__)


class DiversityEngine:
    """Analyzes strategy diversity and filters redundant strategies"""
    
    def __init__(self):
        self.categories = {
            "EMA_CROSSOVER": "trend_following",
            "MACD_TREND": "trend_following",
            "RSI_MEAN_REVERSION": "mean_reversion",
            "BOLLINGER_BREAKOUT": "breakout",
            "ATR_VOLATILITY_BREAKOUT": "breakout",
        }
    
    def analyze_and_filter(
        self,
        strategies: List[Dict[str, Any]],
        min_diversity_score: float = 60.0
    ) -> Dict[str, Any]:
        """
        Analyze diversity and filter strategies.
        
        Returns:
            {
                "filtered_strategies": List of diverse strategies,
                "portfolio_diversity_score": Overall diversity score,
                "categories": Category distribution,
                "removed_count": Number of strategies removed
            }
        """
        if not strategies:
            return {
                "filtered_strategies": [],
                "portfolio_diversity_score": 0,
                "categories": {},
                "removed_count": 0
            }
        
        # Categorize strategies
        category_counts = defaultdict(int)
        category_strategies = defaultdict(list)
        
        for strat in strategies:
            template_id = strat.get("template_id", "UNKNOWN")
            category = self.categories.get(template_id, "unknown")
            category_counts[category] += 1
            category_strategies[category].append(strat)
        
        # Calculate diversity score
        total = len(strategies)
        num_categories = len(category_counts)
        
        # Balance score: how evenly distributed across categories
        if num_categories > 0:
            expected_per_category = total / num_categories
            balance_variance = sum(
                (count - expected_per_category) ** 2 
                for count in category_counts.values()
            ) / num_categories
            balance_score = max(0, 100 - (balance_variance / expected_per_category) * 10)
        else:
            balance_score = 0
        
        # Category coverage score: percentage of available categories
        max_categories = len(set(self.categories.values()))
        coverage_score = (num_categories / max_categories) * 100 if max_categories > 0 else 0
        
        # Overall diversity score
        diversity_score = (balance_score * 0.6 + coverage_score * 0.4)
        
        # Filter: Select best strategies from each category
        filtered = []
        target_per_category = max(2, total // (num_categories + 1)) if num_categories > 0 else total
        
        for category, strats in category_strategies.items():
            # Sort by fitness within category
            sorted_strats = sorted(strats, key=lambda s: s.get("fitness", 0), reverse=True)
            # Take top N from each category
            filtered.extend(sorted_strats[:target_per_category])
        
        # If we still have room, add more high-fitness strategies
        if len(filtered) < total * 0.8:  # Keep at least 80% of strategies
            remaining = [s for s in strategies if s not in filtered]
            remaining_sorted = sorted(remaining, key=lambda s: s.get("fitness", 0), reverse=True)
            needed = int(total * 0.8) - len(filtered)
            filtered.extend(remaining_sorted[:needed])
        
        logger.info(f"[CODEX DIVERSITY ENGINE] Analyzed {total} strategies")
        logger.info(f"[CODEX DIVERSITY ENGINE] Categories: {dict(category_counts)}")
        logger.info(f"[CODEX DIVERSITY ENGINE] Diversity Score: {diversity_score:.1f}/100")
        logger.info(f"[CODEX DIVERSITY ENGINE] Filtered: {total} → {len(filtered)}")
        
        return {
            "filtered_strategies": filtered,
            "portfolio_diversity_score": round(diversity_score, 1),
            "categories": dict(category_counts),
            "removed_count": total - len(filtered)
        }
    
    def calculate_strategy_similarity(self, strat1: Dict, strat2: Dict) -> float:
        """
        Calculate similarity between two strategies (0-1 scale).
        
        Returns:
            Similarity score (0 = completely different, 1 = identical)
        """
        # Same template = high baseline similarity
        if strat1.get("template_id") == strat2.get("template_id"):
            base_similarity = 0.5
            
            # Compare parameter genes
            genes1 = strat1.get("genes", {})
            genes2 = strat2.get("genes", {})
            
            if genes1 and genes2:
                # Calculate parameter similarity
                param_diffs = []
                for key in genes1.keys():
                    if key in genes2:
                        val1 = genes1[key]
                        val2 = genes2[key]
                        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                            # Normalized difference
                            max_val = max(abs(val1), abs(val2), 1)
                            diff = abs(val1 - val2) / max_val
                            param_diffs.append(1 - diff)  # Convert to similarity
                
                if param_diffs:
                    param_similarity = sum(param_diffs) / len(param_diffs)
                    return base_similarity + (param_similarity * 0.5)
            
            return base_similarity
        else:
            # Different templates = low similarity
            cat1 = self.categories.get(strat1.get("template_id", ""), "unknown")
            cat2 = self.categories.get(strat2.get("template_id", ""), "unknown")
            
            # Same category but different template
            if cat1 == cat2:
                return 0.3
            else:
                return 0.1
