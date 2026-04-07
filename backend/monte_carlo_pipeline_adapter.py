"""
Monte Carlo Pipeline Adapter
Converts strategy objects to Monte Carlo-compatible format and generates synthetic trades.
"""

import logging
import random
from typing import Dict, Any, List
from datetime import datetime, timedelta
import uuid

from backtest_models import TradeRecord, TradeDirection, TradeStatus
from montecarlo_models import MonteCarloConfig, ResamplingMethod
from montecarlo_engine import MonteCarloEngine

logger = logging.getLogger(__name__)


class SyntheticTradeGenerator:
    """
    Generates synthetic trade history from strategy summary metrics.
    Used when detailed trade data is not available.
    """
    
    def __init__(self, strategy: Dict[str, Any]):
        self.strategy = strategy
        self.total_trades = max(strategy.get("total_trades", 100), 100)  # Ensure minimum 100 trades
        self.win_rate = strategy.get("win_rate", 50.0) / 100.0
        self.net_profit = strategy.get("net_profit", 1000.0)  # Default positive profit
        self.profit_factor = max(strategy.get("profit_factor", 1.5), 1.01)  # Ensure > 1
        self.initial_balance = 10000.0
        self.symbol = strategy.get("symbol", "EURUSD")
        
    def generate_trades(self) -> List[TradeRecord]:
        """
        Generate synthetic trade records that match the strategy's summary metrics.
        
        Returns:
            List of TradeRecord objects with realistic P&L distribution
        """
        if self.total_trades <= 0:
            return []
        
        trades = []
        
        # Calculate number of winning and losing trades
        num_wins = int(self.total_trades * self.win_rate)
        num_losses = self.total_trades - num_wins
        
        # Calculate average win and average loss based on net profit and profit factor
        # Profit Factor = Gross Profit / Gross Loss
        # Net Profit = Gross Profit - Gross Loss
        # Therefore: Gross Profit = Net Profit + Gross Loss
        # And: Profit Factor = (Net Profit + Gross Loss) / Gross Loss
        # Solving: Gross Loss = Net Profit / (Profit Factor - 1)
        
        if self.profit_factor > 1.0 and num_losses > 0:
            gross_loss = abs(self.net_profit / (self.profit_factor - 1))
            gross_profit = self.net_profit + gross_loss
            avg_win = gross_profit / num_wins if num_wins > 0 else 0
            avg_loss = -gross_loss / num_losses if num_losses > 0 else 0
        elif num_wins > 0:
            # Fallback: distribute profit across wins
            avg_win = self.net_profit / num_wins
            avg_loss = -10  # Small arbitrary loss
        else:
            avg_win = 10
            avg_loss = -10
        
        # Generate winning trades
        for i in range(num_wins):
            # Add some variance (±30%)
            variance = random.uniform(0.7, 1.3)
            profit = avg_win * variance
            
            trade = TradeRecord(
                id=str(uuid.uuid4()),
                backtest_id="synthetic",
                direction=TradeDirection.BUY if random.random() > 0.5 else TradeDirection.SELL,
                entry_price=1.0000 + random.uniform(-0.01, 0.01),
                exit_price=1.0000 + random.uniform(-0.01, 0.01),
                entry_time=datetime.now() - timedelta(days=random.randint(1, 365)),
                exit_time=datetime.now() - timedelta(days=random.randint(0, 364)),
                volume=100000,
                stop_loss=0.0,
                take_profit=0.0,
                profit_loss=profit,
                profit_loss_pips=profit / 10,
                status=TradeStatus.CLOSED,
                exit_reason="take_profit"
            )
            trades.append(trade)
        
        # Generate losing trades
        for i in range(num_losses):
            # Add some variance (±30%)
            variance = random.uniform(0.7, 1.3)
            loss = avg_loss * variance
            
            trade = TradeRecord(
                id=str(uuid.uuid4()),
                backtest_id="synthetic",
                symbol=self.symbol,
                direction=TradeDirection.BUY if random.random() > 0.5 else TradeDirection.SELL,
                entry_price=1.0000 + random.uniform(-0.01, 0.01),
                exit_price=1.0000 + random.uniform(-0.01, 0.01),
                entry_time=datetime.now() - timedelta(days=random.randint(1, 365)),
                exit_time=datetime.now() - timedelta(days=random.randint(0, 364)),
                volume=100000,
                position_size=1.0,
                stop_loss=0.0,
                take_profit=0.0,
                profit_loss=loss,
                profit_loss_pips=loss / 10,
                status=TradeStatus.CLOSED,
                exit_reason="stop_loss"
            )
            trades.append(trade)
        
        # Shuffle to randomize order
        random.shuffle(trades)
        
        logger.debug(f"Generated {len(trades)} synthetic trades (W:{num_wins}, L:{num_losses})")
        
        return trades


class MonteCarloValidator:
    """
    Validates strategies using Monte Carlo simulation.
    Handles both real trade data and synthetic trade generation.
    """
    
    def __init__(
        self,
        num_simulations: int = 1000,
        initial_balance: float = 10000.0,
        min_survival_rate: float = 70.0,
        max_ruin_probability: float = 10.0,
        max_worst_drawdown: float = 50.0
    ):
        self.num_simulations = num_simulations
        self.initial_balance = initial_balance
        self.min_survival_rate = min_survival_rate
        self.max_ruin_probability = max_ruin_probability
        self.max_worst_drawdown = max_worst_drawdown
    
    def validate_strategy(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run Monte Carlo validation on a strategy.
        
        Args:
            strategy: Strategy dictionary with metrics
            
        Returns:
            Strategy enriched with Monte Carlo results and pass/fail status
        """
        strategy_name = strategy.get("name", "Unknown")
        
        try:
            # Generate synthetic trades from strategy metrics
            trade_generator = SyntheticTradeGenerator(strategy)
            trades = trade_generator.generate_trades()
            
            if len(trades) < 10:
                logger.warning(f"[{strategy_name}] Insufficient trades ({len(trades)}), skipping Monte Carlo")
                return self._add_failed_mc_results(strategy, "insufficient_trades")
            
            # Configure Monte Carlo simulation
            mc_config = MonteCarloConfig(
                num_simulations=self.num_simulations,
                resampling_method=ResamplingMethod.SHUFFLE,
                skip_probability=0.1,
                confidence_level=0.95,
                initial_balance=self.initial_balance,
                ruin_threshold_percent=50.0
            )
            
            # Run Monte Carlo simulation
            logger.debug(f"[{strategy_name}] Running {self.num_simulations} Monte Carlo simulations...")
            
            mc_engine = MonteCarloEngine(mc_config, trades)
            mc_result = mc_engine.run()
            
            # Extract key metrics
            survival_rate = mc_result.metrics.profit_probability
            ruin_probability = mc_result.metrics.ruin_probability
            worst_drawdown = mc_result.metrics.worst_case_drawdown
            mc_score = mc_result.monte_carlo_score.total_score
            mc_grade = mc_result.monte_carlo_score.grade
            
            logger.info(
                f"[{strategy_name}] MC Results: "
                f"Survival={survival_rate:.1f}%, Ruin={ruin_probability:.1f}%, "
                f"Worst DD={worst_drawdown:.1f}%, Score={mc_score:.1f}, Grade={mc_grade}"
            )
            
            # Check if strategy passes Monte Carlo validation
            passes_mc = (
                survival_rate >= self.min_survival_rate and
                ruin_probability <= self.max_ruin_probability and
                worst_drawdown <= self.max_worst_drawdown
            )
            
            # Enrich strategy with Monte Carlo results
            enriched_strategy = strategy.copy()
            enriched_strategy.update({
                "monte_carlo_survival_rate": survival_rate,
                "monte_carlo_ruin_probability": ruin_probability,
                "monte_carlo_worst_drawdown": worst_drawdown,
                "monte_carlo_avg_drawdown": mc_result.metrics.average_drawdown,
                "monte_carlo_score": mc_score,
                "monte_carlo_grade": mc_grade,
                "monte_carlo_is_robust": mc_result.monte_carlo_score.is_robust,
                "monte_carlo_risk_level": mc_result.monte_carlo_score.risk_level,
                "monte_carlo_passes": passes_mc,
                "monte_carlo_simulations_count": len(mc_result.simulation_runs),
                # Additional insights
                "monte_carlo_p5_balance": mc_result.metrics.balance_5th_percentile,
                "monte_carlo_p95_balance": mc_result.metrics.balance_95th_percentile,
            })
            
            return enriched_strategy
            
        except Exception as e:
            logger.error(f"[{strategy_name}] Monte Carlo validation failed: {str(e)}")
            return self._add_failed_mc_results(strategy, str(e))
    
    def _add_failed_mc_results(self, strategy: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """Add failed Monte Carlo results to strategy"""
        enriched_strategy = strategy.copy()
        enriched_strategy.update({
            "monte_carlo_survival_rate": 0.0,
            "monte_carlo_ruin_probability": 100.0,
            "monte_carlo_worst_drawdown": 100.0,
            "monte_carlo_avg_drawdown": 100.0,
            "monte_carlo_score": 0.0,
            "monte_carlo_grade": "F",
            "monte_carlo_is_robust": False,
            "monte_carlo_risk_level": "Very High",
            "monte_carlo_passes": False,
            "monte_carlo_simulations_count": 0,
            "monte_carlo_error": reason,
        })
        return enriched_strategy
    
    def validate_batch(self, strategies: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Validate a batch of strategies with Monte Carlo.
        
        Args:
            strategies: List of strategy dictionaries
            
        Returns:
            Tuple of (validated_strategies, summary_stats)
        """
        validated_strategies = []
        passed_count = 0
        failed_count = 0
        
        logger.info(f"Starting Monte Carlo validation for {len(strategies)} strategies...")
        
        for idx, strategy in enumerate(strategies):
            logger.info(f"[{idx+1}/{len(strategies)}] Validating: {strategy.get('name', 'Unknown')}")
            
            enriched_strategy = self.validate_strategy(strategy)
            validated_strategies.append(enriched_strategy)
            
            if enriched_strategy.get("monte_carlo_passes", False):
                passed_count += 1
            else:
                failed_count += 1
        
        summary = {
            "total_validated": len(strategies),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "pass_rate": (passed_count / len(strategies) * 100) if strategies else 0,
            "avg_survival_rate": sum(s.get("monte_carlo_survival_rate", 0) for s in validated_strategies) / len(validated_strategies) if validated_strategies else 0,
            "avg_ruin_probability": sum(s.get("monte_carlo_ruin_probability", 0) for s in validated_strategies) / len(validated_strategies) if validated_strategies else 0,
            "avg_mc_score": sum(s.get("monte_carlo_score", 0) for s in validated_strategies) / len(validated_strategies) if validated_strategies else 0,
        }
        
        logger.info(
            f"Monte Carlo validation complete: "
            f"{passed_count} passed, {failed_count} failed "
            f"(Pass rate: {summary['pass_rate']:.1f}%)"
        )
        
        return validated_strategies, summary
