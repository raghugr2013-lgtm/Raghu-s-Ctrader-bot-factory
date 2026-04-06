"""
Monte Carlo Simulation Engine
Tests strategy robustness by randomizing trade order and adding market noise.

Features:
- Randomizes trade execution order (1000 simulations)
- Adds realistic spread/slippage variation
- Calculates survival rate, worst-case drawdown, return distribution
- Filters fragile strategies (survival < 70%)
"""

import logging
import random
import statistics
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation"""
    strategy_id: str
    strategy_name: str
    
    # Simulation stats
    num_simulations: int
    survival_rate: float  # % of simulations that were profitable
    avg_return: float
    median_return: float
    
    # Risk metrics
    worst_case_return: float
    worst_case_drawdown: float
    best_case_return: float
    
    # Distribution
    return_std: float
    return_percentiles: Dict[str, float]  # 10th, 25th, 75th, 90th
    
    # Robustness score (0-100)
    robustness_score: float
    
    # Pass/Fail
    passed: bool
    failure_reason: Optional[str] = None


class MonteCarloEngine:
    """
    Runs Monte Carlo simulations to test strategy robustness.
    
    Methodology:
    1. Take original trade sequence from backtest
    2. For each simulation:
       - Shuffle trade order randomly
       - Add random spread variation (1-3 pips)
       - Add random slippage (0-2 pips)
       - Recalculate equity curve and metrics
    3. Analyze distribution of outcomes
    """
    
    def __init__(
        self,
        num_simulations: int = 1000,
        min_survival_rate: float = 70.0,
        spread_variation_pips: Tuple[float, float] = (0.5, 2.5),
        slippage_variation_pips: Tuple[float, float] = (0.0, 1.5)
    ):
        self.num_simulations = num_simulations
        self.min_survival_rate = min_survival_rate
        self.spread_variation_pips = spread_variation_pips
        self.slippage_variation_pips = slippage_variation_pips
        self.pip_value = 10.0  # $10 per pip per standard lot
    
    def simulate_strategy(
        self,
        strategy: Dict[str, Any],
        trades: List[Dict[str, Any]],
        initial_balance: float = 10000.0
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on strategy.
        
        Args:
            strategy: Strategy configuration
            trades: List of trades from backtest (with profit_loss_pips)
            initial_balance: Starting balance
            
        Returns:
            MonteCarloResult with simulation statistics
        """
        if not trades or len(trades) < 5:
            # Not enough trades for meaningful simulation
            return MonteCarloResult(
                strategy_id=strategy.get("id", "unknown"),
                strategy_name=strategy.get("name", "Unknown"),
                num_simulations=0,
                survival_rate=0.0,
                avg_return=0.0,
                median_return=0.0,
                worst_case_return=0.0,
                worst_case_drawdown=100.0,
                best_case_return=0.0,
                return_std=0.0,
                return_percentiles={},
                robustness_score=0.0,
                passed=False,
                failure_reason="Insufficient trades for Monte Carlo (minimum 5 required)"
            )
        
        logger.info(f"[MONTE CARLO] Running {self.num_simulations} simulations on {strategy.get('name')}")
        logger.info(f"[MONTE CARLO] Base trades: {len(trades)}, Initial balance: ${initial_balance:.2f}")
        
        simulation_results = []
        
        # Run simulations
        for sim_num in range(self.num_simulations):
            result = self._run_single_simulation(
                trades=trades,
                initial_balance=initial_balance
            )
            simulation_results.append(result)
        
        # Analyze results
        analysis = self._analyze_simulations(simulation_results)
        
        # Calculate survival rate
        profitable_sims = sum(1 for r in simulation_results if r["final_return"] > 0)
        survival_rate = (profitable_sims / self.num_simulations) * 100
        
        # Check if passed
        passed = survival_rate >= self.min_survival_rate
        failure_reason = None
        if not passed:
            failure_reason = f"Low survival rate: {survival_rate:.1f}% < {self.min_survival_rate}%"
        
        # Calculate robustness score (0-100)
        # Based on: survival rate (50%), return stability (30%), drawdown control (20%)
        robustness_score = self._calculate_robustness_score(
            survival_rate=survival_rate,
            return_std=analysis["return_std"],
            worst_case_dd=analysis["worst_case_drawdown"]
        )
        
        result = MonteCarloResult(
            strategy_id=strategy.get("id", "unknown"),
            strategy_name=strategy.get("name", "Unknown"),
            num_simulations=self.num_simulations,
            survival_rate=survival_rate,
            avg_return=analysis["avg_return"],
            median_return=analysis["median_return"],
            worst_case_return=analysis["worst_case_return"],
            worst_case_drawdown=analysis["worst_case_drawdown"],
            best_case_return=analysis["best_case_return"],
            return_std=analysis["return_std"],
            return_percentiles=analysis["percentiles"],
            robustness_score=robustness_score,
            passed=passed,
            failure_reason=failure_reason
        )
        
        logger.info(f"[MONTE CARLO] ✓ Simulation complete: Survival={survival_rate:.1f}%, Robustness={robustness_score:.1f}")
        
        return result
    
    def _run_single_simulation(
        self,
        trades: List[Dict[str, Any]],
        initial_balance: float
    ) -> Dict[str, Any]:
        """
        Run a single Monte Carlo simulation.
        
        Steps:
        1. Shuffle trade order
        2. Apply random spread/slippage to each trade
        3. Recalculate equity curve
        4. Return final metrics
        """
        # Shuffle trades
        shuffled_trades = trades.copy()
        random.shuffle(shuffled_trades)
        
        # Apply market noise and simulate
        balance = initial_balance
        peak = initial_balance
        max_dd = 0.0
        
        for trade in shuffled_trades:
            # Get original profit in pips
            original_pips = trade.get("profit_loss_pips", 0)
            volume = trade.get("volume", 0.01)
            
            # Add random spread variation
            spread_noise = random.uniform(*self.spread_variation_pips)
            # Spread always reduces profit (costs money)
            spread_noise = -abs(spread_noise)
            
            # Add random slippage variation
            slippage_noise = random.uniform(*self.slippage_variation_pips)
            # Slippage can be positive or negative
            if trade.get("direction") == "buy" or trade.get("direction") == "BUY":
                slippage_noise = -abs(slippage_noise)  # Negative for buys
            else:
                slippage_noise = abs(slippage_noise) if random.random() > 0.5 else -abs(slippage_noise)
            
            # Calculate adjusted profit
            adjusted_pips = original_pips + spread_noise + slippage_noise
            adjusted_profit = adjusted_pips * self.pip_value * volume
            
            # Update balance
            balance += adjusted_profit
            
            # Track drawdown
            if balance > peak:
                peak = balance
            dd = ((peak - balance) / peak * 100) if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        # Calculate final return
        final_return = ((balance - initial_balance) / initial_balance) * 100
        
        return {
            "final_balance": balance,
            "final_return": final_return,
            "max_drawdown": max_dd
        }
    
    def _analyze_simulations(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze simulation results and calculate statistics"""
        returns = [r["final_return"] for r in results]
        drawdowns = [r["max_drawdown"] for r in results]
        
        return {
            "avg_return": statistics.mean(returns),
            "median_return": statistics.median(returns),
            "return_std": statistics.stdev(returns) if len(returns) > 1 else 0,
            "worst_case_return": min(returns),
            "best_case_return": max(returns),
            "worst_case_drawdown": max(drawdowns),
            "percentiles": {
                "10th": np.percentile(returns, 10),
                "25th": np.percentile(returns, 25),
                "75th": np.percentile(returns, 75),
                "90th": np.percentile(returns, 90)
            }
        }
    
    def _calculate_robustness_score(
        self,
        survival_rate: float,
        return_std: float,
        worst_case_dd: float
    ) -> float:
        """
        Calculate overall robustness score (0-100).
        
        Components:
        - Survival rate: 50%
        - Return stability (low std): 30%
        - Drawdown control: 20%
        """
        # Survival component (0-50)
        survival_component = (survival_rate / 100) * 50
        
        # Stability component (0-30)
        # Lower std is better - normalize to reasonable range (0-50% std)
        stability_component = max(0, 30 - (return_std / 50 * 30))
        
        # Drawdown component (0-20)
        # Lower DD is better - normalize to 0-50% DD
        dd_component = max(0, 20 - (worst_case_dd / 50 * 20))
        
        total_score = survival_component + stability_component + dd_component
        return round(total_score, 1)
    
    def batch_simulate(
        self,
        strategies: List[Dict[str, Any]],
        initial_balance: float = 10000.0
    ) -> Tuple[List[MonteCarloResult], List[MonteCarloResult]]:
        """
        Run Monte Carlo on multiple strategies.
        
        Returns:
            (passed_strategies, failed_strategies)
        """
        passed = []
        failed = []
        
        for strategy in strategies:
            # Get trades from strategy
            trades = strategy.get("trades", [])
            
            result = self.simulate_strategy(
                strategy=strategy,
                trades=trades,
                initial_balance=initial_balance
            )
            
            if result.passed:
                passed.append(result)
            else:
                failed.append(result)
        
        logger.info(f"[MONTE CARLO] Batch complete: {len(passed)} passed, {len(failed)} failed")
        
        return passed, failed
