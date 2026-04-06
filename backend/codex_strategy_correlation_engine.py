"""
Strategy Correlation Engine
Filters out highly correlated strategies to ensure portfolio diversity.
"""

import logging
import statistics
import math
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class CorrelationEngine:
    """Filters strategies based on correlation analysis"""
    
    def filter_correlated(
        self,
        strategies: List[Dict[str, Any]],
        max_correlation: float = 0.7
    ) -> Dict[str, Any]:
        """
        Remove highly correlated strategies.
        
        Args:
            strategies: List of validated strategies
            max_correlation: Maximum allowed correlation threshold
            
        Returns:
            {
                "filtered_strategies": List of uncorrelated strategies,
                "avg_correlation": Average correlation,
                "removed_count": Number removed
            }
        """
        if len(strategies) < 2:
            return {
                "filtered_strategies": strategies,
                "avg_correlation": 0.0,
                "removed_count": 0
            }
        
        # Build correlation matrix (simplified - using fitness as proxy)
        correlations = []
        filtered = []
        removed = []
        
        # Start with highest fitness strategy
        sorted_strats = sorted(strategies, key=lambda s: s.get("fitness", 0), reverse=True)
        filtered.append(sorted_strats[0])
        
        # Add strategies that are not highly correlated with existing ones
        for strat in sorted_strats[1:]:
            is_correlated = False
            
            for existing in filtered:
                # Simplified correlation based on template and parameters
                corr = self._calculate_correlation(strat, existing)
                correlations.append(corr)
                
                if corr > max_correlation:
                    is_correlated = True
                    break
            
            if not is_correlated:
                filtered.append(strat)
            else:
                removed.append(strat)
        
        avg_corr = statistics.mean(correlations) if correlations else 0.0
        
        logger.info(f"[CODEX CORRELATION ENGINE] Filtered {len(strategies)} → {len(filtered)}")
        logger.info(f"[CODEX CORRELATION ENGINE] Avg Correlation: {avg_corr:.3f}")
        logger.info(f"[CODEX CORRELATION ENGINE] Removed {len(removed)} correlated strategies")
        
        return {
            "filtered_strategies": filtered,
            "avg_correlation": round(avg_corr, 3),
            "removed_count": len(removed)
        }
    
    def _calculate_correlation(self, strat1: Dict, strat2: Dict) -> float:
        """
        Calculate correlation between two strategies.
        Simplified version using template and parameter similarity.
        
        Returns:
            Correlation coefficient (0-1)
        """
        # Same template = higher baseline correlation
        if strat1.get("template_id") == strat2.get("template_id"):
            base_corr = 0.6
            
            # Compare genes
            genes1 = strat1.get("genes", {})
            genes2 = strat2.get("genes", {})
            
            if genes1 and genes2:
                similarities = []
                for key in genes1.keys():
                    if key in genes2:
                        val1 = genes1[key]
                        val2 = genes2[key]
                        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                            max_val = max(abs(val1), abs(val2), 1)
                            similarity = 1 - (abs(val1 - val2) / max_val)
                            similarities.append(similarity)
                
                if similarities:
                    param_corr = statistics.mean(similarities)
                    return base_corr + (param_corr * 0.4)
            
            return base_corr
        else:
            # Different templates = lower correlation
            return 0.2
