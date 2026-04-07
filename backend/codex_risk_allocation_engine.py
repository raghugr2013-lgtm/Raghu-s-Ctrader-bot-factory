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
        max_portfolio_risk: float = 8.0,
        account_size: float = 10000.0,        # NEW
        risk_per_trade: float = 1.0           # NEW (in %)
    ) -> Dict[str, Any]:
        """
        Allocate capital based on selected method with position sizing.
        
        Args:
            strategies: Selected strategies
            method: Allocation method
            max_risk_per_strategy: Max risk % per strategy
            max_portfolio_risk: Max total portfolio risk %
            account_size: Total account capital (NEW)
            risk_per_trade: Risk per trade in % (NEW)
            
        Returns:
            {
                "allocations": Dict[strategy_name, allocation_info],
                "method": Method used,
                "total_risk": Estimated total portfolio risk,
                "account_size": Account size used,
                "risk_per_trade": Risk per trade %
            }
        """
        if not strategies:
            return {
                "allocations": {},
                "method": method,
                "total_risk": 0.0,
                "account_size": account_size,
                "risk_per_trade": risk_per_trade
            }
        
        n = len(strategies)
        allocations = {}
        
        if method == "EQUAL_WEIGHT":
            weight = 1.0 / n
            for strat in strategies:
                allocations[strat["name"]] = {"weight": weight}
        
        elif method == "RISK_PARITY":
            # Allocate inversely proportional to risk (drawdown)
            risks = [strat.get("max_drawdown_pct", 10) for strat in strategies]
            inv_risks = [1.0 / max(r, 0.1) for r in risks]
            total_inv_risk = sum(inv_risks)
            
            for strat, inv_risk in zip(strategies, inv_risks):
                weight = inv_risk / total_inv_risk
                allocations[strat["name"]] = {"weight": weight}
        
        elif method == "MAX_SHARPE":
            # Weight by Sharpe ratio
            sharpes = [max(strat.get("sharpe_ratio", 0), 0.1) for strat in strategies]
            total_sharpe = sum(sharpes)
            
            for strat, sharpe in zip(strategies, sharpes):
                weight = sharpe / total_sharpe
                allocations[strat["name"]] = {"weight": weight}
        
        elif method == "MIN_VARIANCE":
            # Equal weight with slight bias toward lower volatility
            vols = [strat.get("max_drawdown_pct", 10) for strat in strategies]
            inv_vols = [1.0 / max(v, 1.0) for v in vols]
            total_inv_vol = sum(inv_vols)
            
            for strat, inv_vol in zip(strategies, inv_vols):
                weight = inv_vol / total_inv_vol
                allocations[strat["name"]] = {"weight": weight}
        
        else:
            # Default to equal weight
            weight = 1.0 / n
            for strat in strategies:
                allocations[strat["name"]] = {"weight": weight}
        
        # Calculate capital allocation and position sizing for each strategy
        total_risk = 0.0
        
        for strat in strategies:
            name = strat["name"]
            weight = allocations[name]["weight"]
            
            # Capital allocated to this strategy
            allocated_capital = account_size * weight
            
            # Calculate position size based on risk per trade
            # Position size = (Account Size × Risk %) / Stop Loss %
            # Using max_drawdown as proxy for stop loss
            stop_loss_pct = strat.get("max_drawdown_pct", 10) / 100  # Convert to decimal
            
            # Position size calculation
            # Risk amount = account_size * (risk_per_trade / 100)
            # Position size = risk_amount / stop_loss_pct
            risk_amount = account_size * (risk_per_trade / 100)
            position_size_dollars = risk_amount / stop_loss_pct if stop_loss_pct > 0 else allocated_capital
            
            # Cap position size at allocated capital
            position_size_dollars = min(position_size_dollars, allocated_capital)
            
            # Calculate actual risk for this strategy
            strat_risk = strat.get("max_drawdown_pct", 10) * weight
            total_risk += strat_risk
            
            # Store allocation info
            allocations[name] = {
                "weight": weight,
                "weight_percent": round(weight * 100, 2),
                "allocated_capital": round(allocated_capital, 2),
                "position_size": round(position_size_dollars, 2),
                "risk_percent": round(strat_risk, 2),
                "stop_loss_pct": round(stop_loss_pct * 100, 2)
            }
        
        logger.info(f"[RISK ALLOCATION] Method: {method}")
        logger.info(f"[RISK ALLOCATION] Account Size: ${account_size:,.2f}")
        logger.info(f"[RISK ALLOCATION] Risk per Trade: {risk_per_trade}%")
        logger.info(f"[RISK ALLOCATION] Total Risk: {total_risk:.2f}%")
        for name, alloc in sorted(allocations.items(), key=lambda x: -x[1]['weight']):
            logger.info(
                f"   {name}: {alloc['weight_percent']:.1f}% | "
                f"Capital: ${alloc['allocated_capital']:,.2f} | "
                f"Position: ${alloc['position_size']:,.2f} | "
                f"Risk: {alloc['risk_percent']:.2f}%"
            )
        
        return {
            "allocations": allocations,
            "method": method,
            "total_risk": round(total_risk, 2),
            "account_size": account_size,
            "risk_per_trade": risk_per_trade
        }
