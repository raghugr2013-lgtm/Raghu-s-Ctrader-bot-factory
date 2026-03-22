"""
Monte Carlo Simulation Engine
Phase 6: Probabilistic Risk Analysis and Robustness Testing
"""

from typing import List, Dict, Tuple
import random
import statistics
import logging

from backtest_models import TradeRecord
from montecarlo_models import (
    MonteCarloConfig,
    MonteCarloResult,
    SimulationRun,
    MonteCarloMetrics,
    MonteCarloScore,
    ResamplingMethod
)

logger = logging.getLogger(__name__)


class TradeResampler:
    """Resample trades for Monte Carlo simulation"""
    
    @staticmethod
    def shuffle_trades(trades: List[TradeRecord]) -> List[TradeRecord]:
        """Randomize trade order (preserves all trades)"""
        shuffled = trades.copy()
        random.shuffle(shuffled)
        return shuffled
    
    @staticmethod
    def bootstrap_trades(trades: List[TradeRecord]) -> List[TradeRecord]:
        """Sample with replacement (same count, but some trades repeated/omitted)"""
        return random.choices(trades, k=len(trades))
    
    @staticmethod
    def skip_random_trades(
        trades: List[TradeRecord],
        skip_probability: float = 0.1
    ) -> List[TradeRecord]:
        """
        Randomly skip trades (simulates missed opportunities)
        Each trade has skip_probability chance of being excluded
        """
        return [t for t in trades if random.random() > skip_probability]
    
    @staticmethod
    def resample(
        trades: List[TradeRecord],
        method: ResamplingMethod,
        skip_probability: float = 0.1
    ) -> List[TradeRecord]:
        """Apply resampling method"""
        if method == ResamplingMethod.SHUFFLE:
            return TradeResampler.shuffle_trades(trades)
        elif method == ResamplingMethod.BOOTSTRAP:
            return TradeResampler.bootstrap_trades(trades)
        elif method == ResamplingMethod.SKIP_RANDOM:
            return TradeResampler.skip_random_trades(trades, skip_probability)
        else:
            return trades.copy()


class EquityCalculator:
    """Calculate equity curve from resampled trades"""
    
    @staticmethod
    def calculate_equity_curve(
        trades: List[TradeRecord],
        initial_balance: float
    ) -> Tuple[float, float, float]:
        """
        Calculate equity curve from trades
        Returns: (final_balance, max_drawdown, max_drawdown_percent)
        """
        balance = initial_balance
        peak_balance = initial_balance
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        
        for trade in trades:
            if trade.profit_loss:
                balance += trade.profit_loss
                
                # Update peak
                if balance > peak_balance:
                    peak_balance = balance
                
                # Calculate drawdown
                drawdown = peak_balance - balance
                drawdown_pct = (drawdown / peak_balance * 100) if peak_balance > 0 else 0
                
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                if drawdown_pct > max_drawdown_pct:
                    max_drawdown_pct = drawdown_pct
        
        return balance, max_drawdown, max_drawdown_pct


class MonteCarloSimulator:
    """Run Monte Carlo simulations"""
    
    def __init__(self, config: MonteCarloConfig, trades: List[TradeRecord]):
        self.config = config
        self.original_trades = trades
        self.resampler = TradeResampler()
        self.equity_calculator = EquityCalculator()
    
    def run_simulations(self) -> List[SimulationRun]:
        """
        Run N Monte Carlo simulations
        Returns list of simulation results
        """
        logger.info(f"Running {self.config.num_simulations} Monte Carlo simulations")
        
        simulation_runs = []
        
        for i in range(self.config.num_simulations):
            # Resample trades
            resampled_trades = self.resampler.resample(
                self.original_trades,
                self.config.resampling_method,
                self.config.skip_probability
            )
            
            if not resampled_trades:
                continue
            
            # Calculate equity
            final_balance, max_dd, max_dd_pct = self.equity_calculator.calculate_equity_curve(
                resampled_trades,
                self.config.initial_balance
            )
            
            # Calculate metrics
            total_return = final_balance - self.config.initial_balance
            total_return_pct = (total_return / self.config.initial_balance) * 100
            is_profitable = final_balance > self.config.initial_balance
            
            # Check ruin
            ruin_threshold = self.config.initial_balance * (1 - self.config.ruin_threshold_percent / 100)
            is_ruined = final_balance < ruin_threshold
            
            run = SimulationRun(
                run_number=i + 1,
                final_balance=final_balance,
                final_equity=final_balance,
                max_drawdown=max_dd,
                max_drawdown_percent=max_dd_pct,
                total_return=total_return,
                total_return_percent=total_return_pct,
                is_profitable=is_profitable,
                is_ruined=is_ruined
            )
            
            simulation_runs.append(run)
        
        logger.info(f"Completed {len(simulation_runs)} simulations")
        return simulation_runs


class MonteCarloMetricsCalculator:
    """Calculate aggregated Monte Carlo metrics"""
    
    @staticmethod
    def calculate_metrics(
        runs: List[SimulationRun],
        config: MonteCarloConfig
    ) -> MonteCarloMetrics:
        """Calculate all Monte Carlo metrics from simulation runs"""
        
        if not runs:
            return MonteCarloMetricsCalculator._empty_metrics()
        
        # Extract values
        balances = [r.final_balance for r in runs]
        drawdowns = [r.max_drawdown_percent for r in runs]
        returns = [r.total_return_percent for r in runs]
        
        # Sort for percentiles
        sorted_balances = sorted(balances)
        sorted_drawdowns = sorted(drawdowns)
        sorted_returns = sorted(returns)
        
        # Balance statistics
        worst_balance = min(balances)
        best_balance = max(balances)
        avg_balance = statistics.mean(balances)
        median_balance = statistics.median(balances)
        
        # Percentiles
        n = len(sorted_balances)
        balance_5th = sorted_balances[int(n * 0.05)]
        balance_25th = sorted_balances[int(n * 0.25)]
        balance_75th = sorted_balances[int(n * 0.75)]
        balance_95th = sorted_balances[int(n * 0.95)]
        
        # Drawdown statistics
        worst_dd = max(drawdowns)
        best_dd = min(drawdowns)
        avg_dd = statistics.mean(drawdowns)
        median_dd = statistics.median(drawdowns)
        
        dd_5th = sorted_drawdowns[int(n * 0.05)]
        dd_95th = sorted_drawdowns[int(n * 0.95)]
        
        # Return statistics
        avg_return = statistics.mean(returns)
        median_return = statistics.median(returns)
        return_std = statistics.stdev(returns) if len(returns) > 1 else 0
        
        # Probabilities
        profit_count = sum(1 for r in runs if r.is_profitable)
        ruin_count = sum(1 for r in runs if r.is_ruined)
        
        profit_prob = (profit_count / len(runs)) * 100
        ruin_prob = (ruin_count / len(runs)) * 100
        
        # Expected values
        expected_balance = avg_balance
        expected_return = avg_return
        
        # Confidence intervals (95% default)
        ci_level = config.confidence_level
        lower_idx = int(n * (1 - ci_level) / 2)
        upper_idx = int(n * (1 + ci_level) / 2)
        
        balance_ci_lower = sorted_balances[lower_idx]
        balance_ci_upper = sorted_balances[upper_idx]
        
        drawdown_ci_lower = sorted_drawdowns[lower_idx]
        drawdown_ci_upper = sorted_drawdowns[upper_idx]
        
        return_ci_lower = sorted_returns[lower_idx]
        return_ci_upper = sorted_returns[upper_idx]
        
        return MonteCarloMetrics(
            worst_case_balance=worst_balance,
            best_case_balance=best_balance,
            average_balance=avg_balance,
            median_balance=median_balance,
            balance_5th_percentile=balance_5th,
            balance_25th_percentile=balance_25th,
            balance_75th_percentile=balance_75th,
            balance_95th_percentile=balance_95th,
            worst_case_drawdown=worst_dd,
            best_case_drawdown=best_dd,
            average_drawdown=avg_dd,
            median_drawdown=median_dd,
            drawdown_5th_percentile=dd_5th,
            drawdown_95th_percentile=dd_95th,
            average_return_percent=avg_return,
            median_return_percent=median_return,
            return_std_dev=return_std,
            profit_probability=profit_prob,
            ruin_probability=ruin_prob,
            expected_final_balance=expected_balance,
            expected_return_percent=expected_return,
            balance_ci_lower=balance_ci_lower,
            balance_ci_upper=balance_ci_upper,
            drawdown_ci_lower=drawdown_ci_lower,
            drawdown_ci_upper=drawdown_ci_upper,
            return_ci_lower=return_ci_lower,
            return_ci_upper=return_ci_upper
        )
    
    @staticmethod
    def _empty_metrics() -> MonteCarloMetrics:
        """Return empty metrics"""
        return MonteCarloMetrics(
            worst_case_balance=0, best_case_balance=0, average_balance=0, median_balance=0,
            balance_5th_percentile=0, balance_25th_percentile=0,
            balance_75th_percentile=0, balance_95th_percentile=0,
            worst_case_drawdown=0, best_case_drawdown=0, average_drawdown=0, median_drawdown=0,
            drawdown_5th_percentile=0, drawdown_95th_percentile=0,
            average_return_percent=0, median_return_percent=0, return_std_dev=0,
            profit_probability=0, ruin_probability=0,
            expected_final_balance=0, expected_return_percent=0,
            balance_ci_lower=0, balance_ci_upper=0,
            drawdown_ci_lower=0, drawdown_ci_upper=0,
            return_ci_lower=0, return_ci_upper=0
        )


class RobustnessScorer:
    """Calculate Monte Carlo robustness score"""
    
    @staticmethod
    def calculate_score(metrics: MonteCarloMetrics) -> MonteCarloScore:
        """
        Calculate robustness score (0-100)
        
        Components:
        - Drawdown Consistency (40%): Lower variance = higher score
        - Profit Stability (40%): Higher profit probability = higher score
        - Ruin Resistance (20%): Lower ruin probability = higher score
        """
        
        # Component 1: Drawdown Consistency (40%)
        # Score based on drawdown range (95th - 5th percentile)
        dd_range = metrics.drawdown_95th_percentile - metrics.drawdown_5th_percentile
        dd_consistency = RobustnessScorer._drawdown_consistency_score(dd_range)
        
        # Component 2: Profit Stability (40%)
        # Score based on profit probability
        profit_stability = RobustnessScorer._profit_stability_score(metrics.profit_probability)
        
        # Component 3: Ruin Resistance (20%)
        # Score based on ruin probability
        ruin_resistance = RobustnessScorer._ruin_resistance_score(metrics.ruin_probability)
        
        # Weighted total
        total_score = (
            dd_consistency * 0.40 +
            profit_stability * 0.40 +
            ruin_resistance * 0.20
        )
        
        total_score = min(100, max(0, total_score))
        
        # Assign grade
        if total_score >= 90:
            grade = "S"
        elif total_score >= 80:
            grade = "A"
        elif total_score >= 70:
            grade = "B"
        elif total_score >= 60:
            grade = "C"
        elif total_score >= 50:
            grade = "D"
        else:
            grade = "F"
        
        # Risk level
        if total_score >= 80:
            risk_level = "Low"
        elif total_score >= 65:
            risk_level = "Medium"
        elif total_score >= 50:
            risk_level = "High"
        else:
            risk_level = "Very High"
        
        # Robustness threshold
        is_robust = total_score >= 70
        
        # Generate insights
        strengths, weaknesses, recommendations = RobustnessScorer._generate_insights(
            metrics, dd_consistency, profit_stability, ruin_resistance, total_score
        )
        
        return MonteCarloScore(
            drawdown_consistency_score=round(dd_consistency, 1),
            profit_stability_score=round(profit_stability, 1),
            ruin_resistance_score=round(ruin_resistance, 1),
            total_score=round(total_score, 1),
            grade=grade,
            risk_level=risk_level,
            is_robust=is_robust,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations
        )
    
    @staticmethod
    def _drawdown_consistency_score(dd_range: float) -> float:
        """
        Score based on drawdown range
        
        Range < 5% = 100 (very consistent)
        Range = 10% = 75
        Range = 20% = 50
        Range > 30% = 0 (inconsistent)
        """
        if dd_range <= 5:
            return 100
        elif dd_range >= 30:
            return 0
        elif dd_range <= 10:
            return 75 + ((10 - dd_range) / 5) * 25
        elif dd_range <= 20:
            return 50 + ((20 - dd_range) / 10) * 25
        else:
            return ((30 - dd_range) / 10) * 50
    
    @staticmethod
    def _profit_stability_score(profit_prob: float) -> float:
        """
        Score based on profit probability
        
        Prob >= 90% = 100
        Prob = 70% = 70
        Prob = 50% = 40
        Prob < 30% = 0
        """
        if profit_prob >= 90:
            return 100
        elif profit_prob >= 70:
            return 70 + ((profit_prob - 70) / 20) * 30
        elif profit_prob >= 50:
            return 40 + ((profit_prob - 50) / 20) * 30
        elif profit_prob >= 30:
            return ((profit_prob - 30) / 20) * 40
        else:
            return 0
    
    @staticmethod
    def _ruin_resistance_score(ruin_prob: float) -> float:
        """
        Score based on ruin probability (lower is better)
        
        Ruin < 1% = 100
        Ruin = 5% = 75
        Ruin = 10% = 50
        Ruin > 20% = 0
        """
        if ruin_prob < 1:
            return 100
        elif ruin_prob <= 5:
            return 75 + ((5 - ruin_prob) / 4) * 25
        elif ruin_prob <= 10:
            return 50 + ((10 - ruin_prob) / 5) * 25
        elif ruin_prob <= 20:
            return ((20 - ruin_prob) / 10) * 50
        else:
            return 0
    
    @staticmethod
    def _generate_insights(
        metrics: MonteCarloMetrics,
        dd_score: float,
        profit_score: float,
        ruin_score: float,
        total_score: float
    ) -> Tuple[List[str], List[str], List[str]]:
        """Generate strengths, weaknesses, and recommendations"""
        
        strengths = []
        weaknesses = []
        recommendations = []
        
        # Analyze drawdown consistency
        if dd_score >= 75:
            strengths.append(f"Consistent drawdown range ({metrics.drawdown_5th_percentile:.1f}% - {metrics.drawdown_95th_percentile:.1f}%)")
        elif dd_score < 50:
            weaknesses.append(f"Wide drawdown range ({metrics.drawdown_95th_percentile - metrics.drawdown_5th_percentile:.1f}% spread)")
            recommendations.append("Implement adaptive position sizing or stricter stop losses")
        
        # Analyze profit stability
        if profit_score >= 75:
            strengths.append(f"High profit probability ({metrics.profit_probability:.1f}%)")
        elif profit_score < 50:
            weaknesses.append(f"Low profit probability ({metrics.profit_probability:.1f}%)")
            recommendations.append("Improve win rate or risk/reward ratio")
        
        # Analyze ruin risk
        if ruin_score >= 90:
            strengths.append(f"Excellent ruin resistance ({metrics.ruin_probability:.1f}% risk)")
        elif ruin_score < 75:
            weaknesses.append(f"Significant ruin risk ({metrics.ruin_probability:.1f}%)")
            recommendations.append("Reduce position sizes or implement circuit breakers")
        
        # Overall assessment
        if total_score >= 70:
            strengths.append("✓ Strategy passes Monte Carlo robustness test")
        else:
            recommendations.append("⚠ Strategy robustness below threshold - reconsider deployment")
        
        return strengths, weaknesses, recommendations


class MonteCarloEngine:
    """Main Monte Carlo simulation engine"""
    
    def __init__(self, config: MonteCarloConfig, trades: List[TradeRecord]):
        self.config = config
        self.trades = trades
        self.simulator = MonteCarloSimulator(config, trades)
        self.metrics_calculator = MonteCarloMetricsCalculator()
        self.scorer = RobustnessScorer()
    
    def run(self) -> MonteCarloResult:
        """Run complete Monte Carlo analysis"""
        
        from datetime import datetime
        start_time = datetime.now()
        
        logger.info("Starting Monte Carlo simulation")
        
        # Run simulations
        simulation_runs = self.simulator.run_simulations()
        
        # Calculate metrics
        metrics = self.metrics_calculator.calculate_metrics(simulation_runs, self.config)
        
        # Calculate robustness score
        mc_score = self.scorer.calculate_score(metrics)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Monte Carlo completed: Score {mc_score.total_score:.1f}/100, Grade {mc_score.grade}")
        
        return MonteCarloResult(
            session_id="",  # Will be set by API
            backtest_id="",  # Will be set by API
            strategy_name="",  # Will be set by API
            config=self.config,
            simulation_runs=simulation_runs,
            metrics=metrics,
            monte_carlo_score=mc_score,
            total_simulations=len(simulation_runs),
            original_trades_count=len(self.trades),
            execution_time_seconds=execution_time
        )


# Factory function
def create_monte_carlo_engine(config: MonteCarloConfig, trades: List[TradeRecord]) -> MonteCarloEngine:
    """Create Monte Carlo engine instance"""
    return MonteCarloEngine(config, trades)
