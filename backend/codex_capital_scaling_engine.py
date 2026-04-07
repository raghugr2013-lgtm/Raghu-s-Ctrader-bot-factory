"""
Capital Scaling Engine
Adjusts capital allocation based on performance and confidence.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class CapitalScalingEngine:
    """Scales capital based on performance metrics"""
    
    def scale_capital(
        self,
        allocated_portfolio: Dict[str, Any],
        initial_balance: float = 10000.0
    ) -> Dict[str, Any]:
        """
        Scale capital based on portfolio confidence and performance.
        
        Args:
            allocated_portfolio: Portfolio with allocations
            initial_balance: Initial capital
            
        Returns:
            {
                "total_capital": Scaled total capital,
                "scaling_factor": Scaling multiplier,
                "capital_per_strategy": Dict of capital allocations
            }
        """
        allocations = allocated_portfolio.get("allocations", {})
        total_risk = allocated_portfolio.get("total_risk", 5.0)
        
        # Calculate scaling factor based on risk
        # Lower risk = can use more capital
        # Higher risk = reduce capital
        if total_risk < 10:
            scaling_factor = 1.2  # Confident - increase capital
        elif total_risk < 15:
            scaling_factor = 1.0  # Normal
        elif total_risk < 20:
            scaling_factor = 0.8  # Cautious - reduce capital
        else:
            scaling_factor = 0.6  # Very cautious
        
        total_capital = initial_balance * scaling_factor
        
        # Allocate capital to each strategy
        capital_per_strategy = {}
        for name, weight in allocations.items():
            capital_per_strategy[name] = round(total_capital * weight, 2)
        
        logger.info(f"[CAPITAL SCALING] Scaling Factor: {scaling_factor:.2f}x")
        logger.info(f"[CAPITAL SCALING] Total Capital: ${total_capital:,.2f}")
        for name, capital in sorted(capital_per_strategy.items(), key=lambda x: -x[1]):
            logger.info(f"   {name}: ${capital:,.2f}")
        
        return {
            "total_capital": round(total_capital, 2),
            "scaling_factor": scaling_factor,
            "capital_per_strategy": capital_per_strategy
        }
