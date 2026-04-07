"""
Risk & Capital Allocation Engine
Allocates capital and risk across selected strategies.
"""

import logging
import statistics
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class RiskAllocationEngine:
    """Allocates risk and capital across portfolio strategies"""
    
    def allocate(
        self,
        strategies: List[Dict[str, Any]],
        method: str = "MAX_SHARPE",
        max_risk_per_strategy: float = 2.0,
        max_portfolio_risk: float = 8.0
    ) -> Dict[str, Any]:
        """
        Allocate capital based on selected method.
        
        Args:
            strategies: Selected strategies
            method: Allocation method
            max_risk_per_strategy: Max risk % per strategy
            max_portfolio_risk: Max total portfolio risk %
            
        Returns:
            {
                "allocations": Dict[strategy_name, weight],
                "method": Method used,
                "total_risk": Estimated total portfolio risk
            }
        """
        if not strategies:
            return {"allocations": {}, "method": method, "total_risk": 0.0}
        
        n = len(strategies)
        allocations = {}
        
        if method == "EQUAL_WEIGHT":
            weight = 1.0 / n
            for strat in strategies:
                allocations[strat["name"]] = weight
        
        elif method == "RISK_PARITY":
            # Allocate inversely proportional to risk (drawdown)
            risks = [strat.get("max_drawdown_pct", 10) for strat in strategies]
            inv_risks = [1.0 / max(r, 0.1) for r in risks]
            total_inv_risk = sum(inv_risks)
            
            for strat, inv_risk in zip(strategies, inv_risks):
                allocations[strat["name"]] = inv_risk / total_inv_risk
        
        elif method == "MAX_SHARPE":
            # Weight by Sharpe ratio
            sharpes = [max(strat.get("sharpe_ratio", 0), 0.1) for strat in strategies]
            total_sharpe = sum(sharpes)
            
            for strat, sharpe in zip(strategies, sharpes):
                allocations[strat["name"]] = sharpe / total_sharpe
        
        elif method == "MIN_VARIANCE":
            # Equal weight with slight bias toward lower volatility
            vols = [strat.get("max_drawdown_pct", 10) for strat in strategies]
            inv_vols = [1.0 / max(v, 1.0) for v in vols]
            total_inv_vol = sum(inv_vols)
            
            for strat, inv_vol in zip(strategies, inv_vols):
                allocations[strat["name"]] = inv_vol / total_inv_vol
        
        else:
            # Default to equal weight
            weight = 1.0 / n
            for strat in strategies:
                allocations[strat["name"]] = weight
        
        # Calculate estimated portfolio risk
        total_risk = 0.0
        for strat in strategies:
            weight = allocations[strat["name"]]
            strat_risk = strat.get("max_drawdown_pct", 10) * weight
            total_risk += strat_risk
        
        logger.info(f"[RISK ALLOCATION] Method: {method}")
        logger.info(f"[RISK ALLOCATION] Total Risk: {total_risk:.2f}%")
        for name, weight in sorted(allocations.items(), key=lambda x: -x[1]):
            logger.info(f"   {name}: {weight*100:.1f}%")
        
        return {
            "allocations": allocations,
            "method": method,
            "total_risk": round(total_risk, 2)
        }
