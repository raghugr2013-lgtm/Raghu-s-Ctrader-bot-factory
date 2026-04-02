"""
Bootstrap Resampling Engine
Phase 2: Statistical Validation via Trade Resampling

Performs bootstrap analysis on trade sequences:
- Resamples trades with replacement (1000+ iterations)
- Calculates survival probability
- Generates confidence intervals for key metrics
- Identifies statistical significance of strategy edge
"""

import numpy as np
import uuid
import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from enum import Enum
import random

logger = logging.getLogger(__name__)


class BootstrapConfig(BaseModel):
    """Configuration for bootstrap analysis"""
    num_simulations: int = Field(default=1000, ge=100, le=10000)
    initial_balance: float = Field(default=10000.0)
    ruin_threshold_percent: float = Field(default=10.0, description="Max drawdown before ruin")
    confidence_level: float = Field(default=0.95, ge=0.80, le=0.99)
    use_block_bootstrap: bool = Field(default=True, description="Preserve trade sequence dependencies")
    block_size: int = Field(default=10, description="Block size for block bootstrap")


class BootstrapMetrics(BaseModel):
    """Metrics from bootstrap simulation"""
    # Survival metrics
    survival_rate: float = 0.0
    ruin_rate: float = 0.0
    
    # P&L metrics
    mean_final_balance: float = 0.0
    median_final_balance: float = 0.0
    std_final_balance: float = 0.0
    
    # Return metrics
    mean_return_percent: float = 0.0
    median_return_percent: float = 0.0
    return_ci_lower: float = 0.0
    return_ci_upper: float = 0.0
    
    # Drawdown metrics
    mean_max_drawdown: float = 0.0
    median_max_drawdown: float = 0.0
    drawdown_ci_lower: float = 0.0
    drawdown_ci_upper: float = 0.0
    worst_case_drawdown: float = 0.0
    
    # Performance metrics
    mean_profit_factor: float = 0.0
    mean_win_rate: float = 0.0
    mean_sharpe: float = 0.0
    
    # Statistical significance
    profit_probability: float = 0.0
    edge_confidence: float = 0.0


class BootstrapScore(BaseModel):
    """Bootstrap-based strategy score"""
    total_score: float = 0.0
    survival_score: float = 0.0
    consistency_score: float = 0.0
    robustness_score: float = 0.0
    edge_score: float = 0.0
    grade: str = "F"
    is_robust: bool = False
    strengths: List[str] = []
    weaknesses: List[str] = []
    recommendations: List[str] = []


class BootstrapResult(BaseModel):
    """Complete bootstrap analysis result"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    strategy_name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Configuration
    config: BootstrapConfig = Field(default_factory=BootstrapConfig)
    
    # Results
    total_simulations: int = 0
    original_trades: int = 0
    metrics: BootstrapMetrics = Field(default_factory=BootstrapMetrics)
    bootstrap_score: BootstrapScore = Field(default_factory=BootstrapScore)
    
    # Distribution data (for visualization)
    final_balance_distribution: List[float] = []
    return_distribution: List[float] = []
    drawdown_distribution: List[float] = []
    
    execution_time_seconds: float = 0.0


class BootstrapEngine:
    """
    Bootstrap Resampling Engine for Trade Sequence Analysis
    
    Provides statistically rigorous validation of strategy robustness
    through Monte Carlo-style resampling of historical trades.
    """
    
    def __init__(self, config: BootstrapConfig, trades: List[Dict]):
        self.config = config
        self.trades = trades
        self.trade_pnls = [t.get('profit_loss', t.get('pnl', 0)) for t in trades]
        
    def run(self) -> BootstrapResult:
        """
        Run bootstrap analysis on trade sequence
        """
        start_time = datetime.now()
        
        result = BootstrapResult(
            config=self.config,
            original_trades=len(self.trades)
        )
        
        if len(self.trade_pnls) < 10:
            logger.warning("Insufficient trades for bootstrap analysis")
            result.bootstrap_score.recommendations.append(
                "Need at least 10 trades for meaningful bootstrap analysis"
            )
            return result
        
        # Run simulations
        simulation_results = self._run_simulations()
        
        # Calculate metrics
        result.metrics = self._calculate_metrics(simulation_results)
        result.total_simulations = self.config.num_simulations
        
        # Store distributions (subsample for storage)
        sample_size = min(500, len(simulation_results['final_balances']))
        indices = np.random.choice(len(simulation_results['final_balances']), sample_size, replace=False)
        result.final_balance_distribution = [simulation_results['final_balances'][i] for i in indices]
        result.return_distribution = [simulation_results['returns'][i] for i in indices]
        result.drawdown_distribution = [simulation_results['max_drawdowns'][i] for i in indices]
        
        # Calculate score
        result.bootstrap_score = self._calculate_score(result.metrics)
        
        result.execution_time_seconds = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Bootstrap complete: {result.metrics.survival_rate:.1%} survival, "
                   f"Score: {result.bootstrap_score.total_score:.1f}")
        
        return result
    
    def _run_simulations(self) -> Dict[str, List[float]]:
        """
        Run bootstrap simulations
        """
        final_balances = []
        returns = []
        max_drawdowns = []
        profit_factors = []
        win_rates = []
        survived = 0
        profitable = 0
        
        n_trades = len(self.trade_pnls)
        
        for _ in range(self.config.num_simulations):
            # Resample trades
            if self.config.use_block_bootstrap:
                resampled_pnls = self._block_bootstrap()
            else:
                # Standard bootstrap with replacement
                indices = np.random.randint(0, n_trades, size=n_trades)
                resampled_pnls = [self.trade_pnls[i] for i in indices]
            
            # Simulate equity curve
            balance = self.config.initial_balance
            peak = balance
            max_dd = 0
            equity_curve = [balance]
            
            wins = 0
            losses = 0
            total_profit = 0
            total_loss = 0
            ruin = False
            
            for pnl in resampled_pnls:
                balance += pnl
                equity_curve.append(balance)
                
                if pnl > 0:
                    wins += 1
                    total_profit += pnl
                else:
                    losses += 1
                    total_loss += abs(pnl)
                
                if balance > peak:
                    peak = balance
                
                current_dd = (peak - balance) / peak * 100 if peak > 0 else 0
                max_dd = max(max_dd, current_dd)
                
                # Check for ruin
                if current_dd >= self.config.ruin_threshold_percent:
                    ruin = True
                    break
            
            final_balances.append(balance)
            returns.append((balance - self.config.initial_balance) / self.config.initial_balance * 100)
            max_drawdowns.append(max_dd)
            
            if not ruin:
                survived += 1
            
            if balance > self.config.initial_balance:
                profitable += 1
            
            # Calculate metrics for this simulation
            pf = total_profit / total_loss if total_loss > 0 else 10.0
            wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
            profit_factors.append(pf)
            win_rates.append(wr)
        
        return {
            'final_balances': final_balances,
            'returns': returns,
            'max_drawdowns': max_drawdowns,
            'profit_factors': profit_factors,
            'win_rates': win_rates,
            'survived': survived,
            'profitable': profitable
        }
    
    def _block_bootstrap(self) -> List[float]:
        """
        Block bootstrap to preserve temporal dependencies
        """
        n_trades = len(self.trade_pnls)
        block_size = min(self.config.block_size, n_trades // 2)
        n_blocks = (n_trades + block_size - 1) // block_size
        
        resampled = []
        for _ in range(n_blocks):
            start_idx = random.randint(0, n_trades - block_size)
            block = self.trade_pnls[start_idx:start_idx + block_size]
            resampled.extend(block)
        
        return resampled[:n_trades]
    
    def _calculate_metrics(self, sim_results: Dict) -> BootstrapMetrics:
        """
        Calculate bootstrap metrics from simulation results
        """
        final_balances = np.array(sim_results['final_balances'])
        returns = np.array(sim_results['returns'])
        max_drawdowns = np.array(sim_results['max_drawdowns'])
        profit_factors = np.array(sim_results['profit_factors'])
        win_rates = np.array(sim_results['win_rates'])
        
        n_sims = self.config.num_simulations
        ci = self.config.confidence_level
        lower_pct = (1 - ci) / 2 * 100
        upper_pct = (1 + ci) / 2 * 100
        
        return BootstrapMetrics(
            survival_rate=sim_results['survived'] / n_sims,
            ruin_rate=1 - sim_results['survived'] / n_sims,
            
            mean_final_balance=float(np.mean(final_balances)),
            median_final_balance=float(np.median(final_balances)),
            std_final_balance=float(np.std(final_balances)),
            
            mean_return_percent=float(np.mean(returns)),
            median_return_percent=float(np.median(returns)),
            return_ci_lower=float(np.percentile(returns, lower_pct)),
            return_ci_upper=float(np.percentile(returns, upper_pct)),
            
            mean_max_drawdown=float(np.mean(max_drawdowns)),
            median_max_drawdown=float(np.median(max_drawdowns)),
            drawdown_ci_lower=float(np.percentile(max_drawdowns, lower_pct)),
            drawdown_ci_upper=float(np.percentile(max_drawdowns, upper_pct)),
            worst_case_drawdown=float(np.percentile(max_drawdowns, 99)),
            
            mean_profit_factor=float(np.mean(profit_factors)),
            mean_win_rate=float(np.mean(win_rates)),
            mean_sharpe=self._calculate_sharpe(returns),
            
            profit_probability=sim_results['profitable'] / n_sims,
            edge_confidence=self._calculate_edge_confidence(returns)
        )
    
    def _calculate_sharpe(self, returns: np.ndarray) -> float:
        """Calculate Sharpe ratio of return distribution"""
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        return float(np.mean(returns) / np.std(returns) * np.sqrt(252))
    
    def _calculate_edge_confidence(self, returns: np.ndarray) -> float:
        """
        Calculate confidence that strategy has positive edge
        (percentage of simulations with positive return)
        """
        return float(np.mean(returns > 0))
    
    def _calculate_score(self, metrics: BootstrapMetrics) -> BootstrapScore:
        """
        Calculate bootstrap score from metrics
        """
        score = BootstrapScore()
        strengths = []
        weaknesses = []
        recommendations = []
        
        # Survival Score (0-25)
        survival_score = min(25, metrics.survival_rate * 25)
        score.survival_score = survival_score
        
        if metrics.survival_rate >= 0.95:
            strengths.append(f"Excellent survival rate: {metrics.survival_rate:.1%}")
        elif metrics.survival_rate >= 0.80:
            strengths.append(f"Good survival rate: {metrics.survival_rate:.1%}")
        elif metrics.survival_rate < 0.60:
            weaknesses.append(f"Poor survival rate: {metrics.survival_rate:.1%}")
            recommendations.append("Reduce position sizing or improve risk management")
        
        # Consistency Score (0-25) - based on return distribution
        return_cv = abs(metrics.std_final_balance / metrics.mean_final_balance) if metrics.mean_final_balance > 0 else 1
        consistency_score = max(0, min(25, 25 * (1 - return_cv)))
        score.consistency_score = consistency_score
        
        if return_cv < 0.2:
            strengths.append("Very consistent performance across simulations")
        elif return_cv > 0.5:
            weaknesses.append("High variance in simulation outcomes")
            recommendations.append("Strategy results are highly variable - consider parameter tuning")
        
        # Robustness Score (0-25) - based on profit probability and edge
        robustness_score = min(25, (metrics.profit_probability * 15 + metrics.edge_confidence * 10))
        score.robustness_score = robustness_score
        
        if metrics.profit_probability >= 0.70:
            strengths.append(f"High profit probability: {metrics.profit_probability:.1%}")
        elif metrics.profit_probability < 0.50:
            weaknesses.append(f"Low profit probability: {metrics.profit_probability:.1%}")
            recommendations.append("Strategy may not have statistical edge")
        
        # Edge Score (0-25) - based on Sharpe and profit factor
        sharpe_component = min(12.5, max(0, metrics.mean_sharpe * 5))
        pf_component = min(12.5, max(0, (metrics.mean_profit_factor - 1) * 10))
        edge_score = sharpe_component + pf_component
        score.edge_score = edge_score
        
        if metrics.mean_sharpe >= 1.5:
            strengths.append(f"Excellent risk-adjusted returns (Sharpe: {metrics.mean_sharpe:.2f})")
        elif metrics.mean_sharpe < 0.5:
            weaknesses.append(f"Poor risk-adjusted returns (Sharpe: {metrics.mean_sharpe:.2f})")
        
        # Total score
        score.total_score = survival_score + consistency_score + robustness_score + edge_score
        
        # Grade
        if score.total_score >= 85:
            score.grade = "A"
        elif score.total_score >= 70:
            score.grade = "B"
        elif score.total_score >= 55:
            score.grade = "C"
        elif score.total_score >= 40:
            score.grade = "D"
        else:
            score.grade = "F"
        
        # Is robust?
        score.is_robust = (
            metrics.survival_rate >= 0.80 and
            metrics.profit_probability >= 0.55 and
            score.total_score >= 55
        )
        
        score.strengths = strengths
        score.weaknesses = weaknesses
        score.recommendations = recommendations
        
        return score


def create_bootstrap_engine(config: BootstrapConfig, trades: List[Dict]) -> BootstrapEngine:
    """Factory function to create bootstrap engine"""
    return BootstrapEngine(config, trades)
