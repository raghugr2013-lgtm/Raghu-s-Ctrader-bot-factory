"""
Challenge Portfolio Engine
Phase 5: Multi-Strategy Portfolio for Prop Firm Challenges

Combines multiple strategies into a portfolio:
- Combined equity curve calculation
- Portfolio-level drawdown analysis
- Prop firm challenge simulation
- Portfolio pass probability estimation
"""

import numpy as np
import uuid
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class PortfolioConfig(BaseModel):
    """Configuration for portfolio challenge simulation"""
    initial_balance: float = Field(default=100000.0)
    profit_target_percent: float = Field(default=10.0)
    max_daily_loss_percent: float = Field(default=5.0)
    max_total_drawdown_percent: float = Field(default=10.0)
    challenge_duration_days: int = Field(default=30)
    min_trading_days: int = Field(default=10)
    correlation_threshold: float = Field(default=0.7, description="Max allowed strategy correlation")
    num_simulations: int = Field(default=1000)


class StrategyWeight(BaseModel):
    """Weight allocation for a strategy in the portfolio"""
    strategy_id: str
    strategy_name: str
    weight: float = Field(default=0.0, ge=0.0, le=1.0)
    expected_return: float = 0.0
    expected_drawdown: float = 0.0
    sharpe_ratio: float = 0.0


class PortfolioMetrics(BaseModel):
    """Portfolio-level metrics"""
    # Return metrics
    total_return_percent: float = 0.0
    annualized_return: float = 0.0
    avg_daily_return: float = 0.0
    return_std: float = 0.0
    
    # Risk metrics
    max_drawdown_percent: float = 0.0
    avg_drawdown_percent: float = 0.0
    max_daily_loss_percent: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # Portfolio stats
    num_strategies: int = 0
    avg_correlation: float = 0.0
    diversification_ratio: float = 0.0
    
    # Combined trading stats
    total_trades: int = 0
    combined_win_rate: float = 0.0
    combined_profit_factor: float = 0.0


class ChallengeMetrics(BaseModel):
    """Prop firm challenge metrics"""
    # Pass/Fail status
    passed: bool = False
    pass_probability: float = 0.0
    fail_reason: Optional[str] = None
    
    # Challenge progress
    profit_achieved_percent: float = 0.0
    profit_target_reached: bool = False
    days_to_target: Optional[int] = None
    
    # Rule violations
    daily_loss_violations: int = 0
    total_dd_violations: int = 0
    min_days_met: bool = False
    
    # Monte Carlo results
    mc_pass_rate: float = 0.0
    mc_avg_profit: float = 0.0
    mc_worst_drawdown: float = 0.0


class PortfolioScore(BaseModel):
    """Portfolio scoring"""
    total_score: float = 0.0
    return_score: float = 0.0
    risk_score: float = 0.0
    diversification_score: float = 0.0
    challenge_score: float = 0.0
    grade: str = "F"
    is_challenge_ready: bool = False
    strengths: List[str] = []
    weaknesses: List[str] = []
    recommendations: List[str] = []


class PortfolioResult(BaseModel):
    """Complete portfolio analysis result"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    portfolio_name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Configuration
    config: PortfolioConfig = Field(default_factory=PortfolioConfig)
    
    # Strategy allocations
    strategies: List[StrategyWeight] = []
    
    # Results
    metrics: PortfolioMetrics = Field(default_factory=PortfolioMetrics)
    challenge_metrics: ChallengeMetrics = Field(default_factory=ChallengeMetrics)
    portfolio_score: PortfolioScore = Field(default_factory=PortfolioScore)
    
    # Equity curve data
    combined_equity_curve: List[float] = []
    combined_drawdown_curve: List[float] = []
    daily_pnl: List[float] = []
    
    # Correlation matrix
    correlation_matrix: Dict[str, Dict[str, float]] = {}
    
    execution_time_seconds: float = 0.0


class ChallengePortfolioEngine:
    """
    Portfolio Engine for Prop Firm Challenge Optimization
    
    Combines multiple strategies to maximize challenge pass probability
    while respecting risk constraints.
    """
    
    def __init__(
        self,
        config: PortfolioConfig,
        strategies: List[Dict]
    ):
        self.config = config
        self.strategies = strategies
        self.strategy_trades = {}
        self.strategy_equity = {}
        
        # Extract trades and equity curves for each strategy
        for strategy in strategies:
            sid = strategy.get('id', strategy.get('strategy_id', str(uuid.uuid4())))
            trades = strategy.get('trades', [])
            self.strategy_trades[sid] = trades
            self.strategy_equity[sid] = self._calculate_equity_curve(trades)
    
    def run(self) -> PortfolioResult:
        """
        Run portfolio analysis and challenge simulation
        """
        start_time = datetime.now()
        
        result = PortfolioResult(config=self.config)
        
        if len(self.strategies) < 1:
            logger.warning("No strategies provided")
            return result
        
        # Calculate optimal weights
        weights = self._calculate_optimal_weights()
        result.strategies = weights
        
        # Calculate correlation matrix
        result.correlation_matrix = self._calculate_correlation_matrix()
        
        # Generate combined equity curve
        combined_equity, combined_dd, daily_pnl = self._generate_combined_curves(weights)
        result.combined_equity_curve = combined_equity
        result.combined_drawdown_curve = combined_dd
        result.daily_pnl = daily_pnl
        
        # Calculate portfolio metrics
        result.metrics = self._calculate_portfolio_metrics(combined_equity, combined_dd, daily_pnl, weights)
        
        # Simulate challenge
        result.challenge_metrics = self._simulate_challenge(weights)
        
        # Calculate score
        result.portfolio_score = self._calculate_score(result.metrics, result.challenge_metrics)
        
        result.execution_time_seconds = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Portfolio analysis complete: {result.challenge_metrics.pass_probability:.1%} pass probability")
        
        return result
    
    def _calculate_equity_curve(self, trades: List[Dict]) -> List[float]:
        """Calculate equity curve from trades"""
        if not trades:
            return [self.config.initial_balance]
        
        equity = [self.config.initial_balance]
        balance = self.config.initial_balance
        
        for trade in trades:
            pnl = trade.get('profit_loss', trade.get('pnl', 0))
            balance += pnl
            equity.append(balance)
        
        return equity
    
    def _calculate_optimal_weights(self) -> List[StrategyWeight]:
        """
        Calculate optimal strategy weights using mean-variance optimization
        """
        weights = []
        n_strategies = len(self.strategies)
        
        if n_strategies == 1:
            # Single strategy gets 100%
            strategy = self.strategies[0]
            sid = strategy.get('id', strategy.get('strategy_id', ''))
            equity = self.strategy_equity.get(sid, [])
            
            return [StrategyWeight(
                strategy_id=sid,
                strategy_name=strategy.get('name', strategy.get('strategy_name', 'Strategy 1')),
                weight=1.0,
                expected_return=self._calculate_return(equity),
                expected_drawdown=self._calculate_max_dd(equity),
                sharpe_ratio=self._calculate_sharpe(equity)
            )]
        
        # Calculate returns and risks for each strategy
        returns = []
        risks = []
        sharpes = []
        
        for strategy in self.strategies:
            sid = strategy.get('id', strategy.get('strategy_id', ''))
            equity = self.strategy_equity.get(sid, [])
            ret = self._calculate_return(equity)
            risk = self._calculate_risk(equity)
            sharpe = self._calculate_sharpe(equity)
            returns.append(ret)
            risks.append(risk)
            sharpes.append(sharpe)
        
        # Simple weight allocation based on Sharpe ratios
        total_sharpe = sum(max(0, s) for s in sharpes) or 1
        
        for i, strategy in enumerate(self.strategies):
            sid = strategy.get('id', strategy.get('strategy_id', ''))
            name = strategy.get('name', strategy.get('strategy_name', f'Strategy {i+1}'))
            equity = self.strategy_equity.get(sid, [])
            
            # Weight based on Sharpe ratio (positive only)
            weight = max(0, sharpes[i]) / total_sharpe if total_sharpe > 0 else 1 / n_strategies
            
            weights.append(StrategyWeight(
                strategy_id=sid,
                strategy_name=name,
                weight=round(weight, 4),
                expected_return=returns[i],
                expected_drawdown=self._calculate_max_dd(equity),
                sharpe_ratio=sharpes[i]
            ))
        
        # Normalize weights to sum to 1
        total_weight = sum(w.weight for w in weights)
        if total_weight > 0:
            for w in weights:
                w.weight = round(w.weight / total_weight, 4)
        
        return weights
    
    def _calculate_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        """Calculate correlation between strategy returns"""
        if len(self.strategies) < 2:
            return {}
        
        # Get daily returns for each strategy
        daily_returns = {}
        for strategy in self.strategies:
            sid = strategy.get('id', strategy.get('strategy_id', ''))
            equity = self.strategy_equity.get(sid, [])
            if len(equity) > 1:
                returns = np.diff(equity) / np.array(equity[:-1])
                daily_returns[sid] = returns
        
        # Calculate correlations
        correlation_matrix = {}
        sids = list(daily_returns.keys())
        
        for i, sid1 in enumerate(sids):
            correlation_matrix[sid1] = {}
            for j, sid2 in enumerate(sids):
                if i == j:
                    correlation_matrix[sid1][sid2] = 1.0
                else:
                    r1 = daily_returns[sid1]
                    r2 = daily_returns[sid2]
                    min_len = min(len(r1), len(r2))
                    if min_len > 5:
                        corr = np.corrcoef(r1[:min_len], r2[:min_len])[0, 1]
                        correlation_matrix[sid1][sid2] = round(float(corr) if not np.isnan(corr) else 0, 3)
                    else:
                        correlation_matrix[sid1][sid2] = 0.0
        
        return correlation_matrix
    
    def _generate_combined_curves(self, weights: List[StrategyWeight]) -> Tuple[List[float], List[float], List[float]]:
        """Generate combined equity and drawdown curves"""
        if not weights:
            return [self.config.initial_balance], [0.0], [0.0]
        
        # Find the minimum equity curve length
        min_length = min(
            len(self.strategy_equity.get(w.strategy_id, [self.config.initial_balance]))
            for w in weights
        )
        
        # Combine equity curves based on weights
        combined_equity = [self.config.initial_balance]
        
        for i in range(1, min_length):
            portfolio_return = 0
            for w in weights:
                equity = self.strategy_equity.get(w.strategy_id, [])
                if len(equity) > i:
                    strategy_return = (equity[i] - equity[i-1]) / equity[i-1] if equity[i-1] > 0 else 0
                    portfolio_return += strategy_return * w.weight
            
            new_balance = combined_equity[-1] * (1 + portfolio_return)
            combined_equity.append(new_balance)
        
        # Calculate drawdown curve
        peak = combined_equity[0]
        combined_dd = []
        daily_pnl = []
        
        for i, eq in enumerate(combined_equity):
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100 if peak > 0 else 0
            combined_dd.append(dd)
            
            if i > 0:
                daily_pnl.append(eq - combined_equity[i-1])
            else:
                daily_pnl.append(0)
        
        return combined_equity, combined_dd, daily_pnl
    
    def _calculate_portfolio_metrics(
        self,
        equity: List[float],
        dd: List[float],
        daily_pnl: List[float],
        weights: List[StrategyWeight]
    ) -> PortfolioMetrics:
        """Calculate portfolio-level metrics"""
        if len(equity) < 2:
            return PortfolioMetrics()
        
        initial = equity[0]
        final = equity[-1]
        total_return = (final - initial) / initial * 100 if initial > 0 else 0
        
        # Daily returns
        daily_returns = np.diff(equity) / np.array(equity[:-1])
        daily_returns = daily_returns[~np.isnan(daily_returns)]
        
        # Risk metrics
        max_dd = max(dd) if dd else 0
        avg_dd = np.mean(dd) if dd else 0
        max_daily_loss = max(-min(daily_pnl), 0) / initial * 100 if daily_pnl and initial > 0 else 0
        
        # Sharpe ratio
        if len(daily_returns) > 1 and np.std(daily_returns) > 0:
            sharpe = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)
        else:
            sharpe = 0
        
        # Sortino ratio (downside deviation)
        negative_returns = daily_returns[daily_returns < 0]
        if len(negative_returns) > 1:
            downside_std = np.std(negative_returns)
            sortino = np.mean(daily_returns) / downside_std * np.sqrt(252) if downside_std > 0 else 0
        else:
            sortino = sharpe
        
        # Calmar ratio
        calmar = total_return / max_dd if max_dd > 0 else 0
        
        # Average correlation
        corr_values = []
        for sid1, corrs in self._calculate_correlation_matrix().items():
            for sid2, corr in corrs.items():
                if sid1 != sid2:
                    corr_values.append(abs(corr))
        avg_corr = np.mean(corr_values) if corr_values else 0
        
        # Diversification ratio
        weighted_vols = sum(
            w.expected_drawdown * w.weight
            for w in weights
        )
        portfolio_vol = max_dd
        div_ratio = weighted_vols / portfolio_vol if portfolio_vol > 0 else 1
        
        # Combined trading stats
        total_trades = sum(len(self.strategy_trades.get(w.strategy_id, [])) for w in weights)
        
        all_pnls = []
        for w in weights:
            trades = self.strategy_trades.get(w.strategy_id, [])
            for t in trades:
                all_pnls.append(t.get('profit_loss', t.get('pnl', 0)) * w.weight)
        
        if all_pnls:
            wins = sum(1 for p in all_pnls if p > 0)
            combined_wr = wins / len(all_pnls) * 100
            total_profit = sum(p for p in all_pnls if p > 0)
            total_loss = abs(sum(p for p in all_pnls if p < 0))
            combined_pf = total_profit / total_loss if total_loss > 0 else 10.0
        else:
            combined_wr = 0
            combined_pf = 0
        
        return PortfolioMetrics(
            total_return_percent=round(total_return, 2),
            annualized_return=round(total_return * 12, 2),  # Assuming monthly data
            avg_daily_return=round(np.mean(daily_returns) * 100, 4) if len(daily_returns) > 0 else 0,
            return_std=round(np.std(daily_returns) * 100, 4) if len(daily_returns) > 0 else 0,
            max_drawdown_percent=round(max_dd, 2),
            avg_drawdown_percent=round(avg_dd, 2),
            max_daily_loss_percent=round(max_daily_loss, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            calmar_ratio=round(calmar, 2),
            num_strategies=len(weights),
            avg_correlation=round(avg_corr, 3),
            diversification_ratio=round(div_ratio, 2),
            total_trades=total_trades,
            combined_win_rate=round(combined_wr, 1),
            combined_profit_factor=round(combined_pf, 2)
        )
    
    def _simulate_challenge(self, weights: List[StrategyWeight]) -> ChallengeMetrics:
        """
        Simulate prop firm challenge with Monte Carlo
        """
        metrics = ChallengeMetrics()
        
        if not weights:
            return metrics
        
        # Get combined equity curve
        equity, dd, daily_pnl = self._generate_combined_curves(weights)
        
        initial = self.config.initial_balance
        target = initial * (1 + self.config.profit_target_percent / 100)
        max_daily_loss = initial * self.config.max_daily_loss_percent / 100
        max_total_dd = self.config.max_total_drawdown_percent
        
        # Check single simulation
        profit_percent = (equity[-1] - initial) / initial * 100 if initial > 0 else 0
        metrics.profit_achieved_percent = round(profit_percent, 2)
        metrics.profit_target_reached = profit_percent >= self.config.profit_target_percent
        
        # Count violations
        for i, pnl in enumerate(daily_pnl):
            if -pnl > max_daily_loss:
                metrics.daily_loss_violations += 1
        
        for d in dd:
            if d > max_total_dd:
                metrics.total_dd_violations += 1
                break
        
        # Check min trading days
        trading_days = len([p for p in daily_pnl if p != 0])
        metrics.min_days_met = trading_days >= self.config.min_trading_days
        
        # Determine pass/fail
        passed = (
            metrics.profit_target_reached and
            metrics.daily_loss_violations == 0 and
            metrics.total_dd_violations == 0 and
            metrics.min_days_met
        )
        metrics.passed = passed
        
        if not passed:
            if not metrics.profit_target_reached:
                metrics.fail_reason = "Profit target not reached"
            elif metrics.daily_loss_violations > 0:
                metrics.fail_reason = "Daily loss limit breached"
            elif metrics.total_dd_violations > 0:
                metrics.fail_reason = "Max drawdown limit breached"
            elif not metrics.min_days_met:
                metrics.fail_reason = "Minimum trading days not met"
        
        # Monte Carlo simulation for pass probability
        mc_results = self._monte_carlo_challenge(weights)
        metrics.mc_pass_rate = mc_results['pass_rate']
        metrics.mc_avg_profit = mc_results['avg_profit']
        metrics.mc_worst_drawdown = mc_results['worst_dd']
        metrics.pass_probability = mc_results['pass_rate']
        
        return metrics
    
    def _monte_carlo_challenge(self, weights: List[StrategyWeight]) -> Dict:
        """
        Run Monte Carlo simulation for challenge pass probability
        """
        # Collect all daily returns from all strategies
        all_daily_returns = []
        for w in weights:
            equity = self.strategy_equity.get(w.strategy_id, [])
            if len(equity) > 1:
                returns = np.diff(equity) / np.array(equity[:-1])
                weighted_returns = returns * w.weight
                all_daily_returns.extend(weighted_returns)
        
        if len(all_daily_returns) < 10:
            return {'pass_rate': 0, 'avg_profit': 0, 'worst_dd': 100}
        
        passes = 0
        profits = []
        worst_dds = []
        
        initial = self.config.initial_balance
        target_return = self.config.profit_target_percent / 100
        max_daily_loss_pct = self.config.max_daily_loss_percent / 100
        max_dd_pct = self.config.max_total_drawdown_percent / 100
        
        for _ in range(self.config.num_simulations):
            # Resample daily returns
            sim_returns = np.random.choice(
                all_daily_returns,
                size=self.config.challenge_duration_days,
                replace=True
            )
            
            # Simulate equity curve
            balance = initial
            peak = initial
            passed = True
            daily_loss_breach = False
            dd_breach = False
            
            for ret in sim_returns:
                daily_pnl = balance * ret
                
                # Check daily loss
                if -daily_pnl / initial > max_daily_loss_pct:
                    daily_loss_breach = True
                    passed = False
                    break
                
                balance += daily_pnl
                
                if balance > peak:
                    peak = balance
                
                # Check drawdown
                current_dd = (peak - balance) / peak if peak > 0 else 0
                if current_dd > max_dd_pct:
                    dd_breach = True
                    passed = False
                    break
            
            final_return = (balance - initial) / initial
            
            # Check profit target
            if passed and final_return < target_return:
                passed = False
            
            if passed:
                passes += 1
            
            profits.append(final_return * 100)
            worst_dds.append((peak - balance) / peak * 100 if peak > 0 else 0)
        
        return {
            'pass_rate': passes / self.config.num_simulations,
            'avg_profit': np.mean(profits),
            'worst_dd': np.percentile(worst_dds, 95)
        }
    
    def _calculate_return(self, equity: List[float]) -> float:
        """Calculate total return percentage"""
        if len(equity) < 2:
            return 0
        return (equity[-1] - equity[0]) / equity[0] * 100 if equity[0] > 0 else 0
    
    def _calculate_risk(self, equity: List[float]) -> float:
        """Calculate risk (standard deviation of returns)"""
        if len(equity) < 2:
            return 0
        returns = np.diff(equity) / np.array(equity[:-1])
        return np.std(returns) * np.sqrt(252) * 100 if len(returns) > 0 else 0
    
    def _calculate_max_dd(self, equity: List[float]) -> float:
        """Calculate maximum drawdown"""
        if len(equity) < 2:
            return 0
        peak = equity[0]
        max_dd = 0
        for eq in equity:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)
        return max_dd
    
    def _calculate_sharpe(self, equity: List[float]) -> float:
        """Calculate Sharpe ratio"""
        if len(equity) < 2:
            return 0
        returns = np.diff(equity) / np.array(equity[:-1])
        if len(returns) > 0 and np.std(returns) > 0:
            return np.mean(returns) / np.std(returns) * np.sqrt(252)
        return 0
    
    def _calculate_score(self, metrics: PortfolioMetrics, challenge: ChallengeMetrics) -> PortfolioScore:
        """Calculate portfolio score"""
        score = PortfolioScore()
        strengths = []
        weaknesses = []
        recommendations = []
        
        # Return score (0-25)
        if metrics.total_return_percent >= 15:
            return_score = 25
            strengths.append(f"Strong returns: {metrics.total_return_percent:.1f}%")
        elif metrics.total_return_percent >= 10:
            return_score = 20
        elif metrics.total_return_percent >= 5:
            return_score = 15
        else:
            return_score = max(0, metrics.total_return_percent * 2)
            if metrics.total_return_percent < 5:
                weaknesses.append(f"Low returns: {metrics.total_return_percent:.1f}%")
        score.return_score = return_score
        
        # Risk score (0-25)
        if metrics.max_drawdown_percent < 5:
            risk_score = 25
            strengths.append(f"Excellent risk control: {metrics.max_drawdown_percent:.1f}% max DD")
        elif metrics.max_drawdown_percent < 10:
            risk_score = 20
        elif metrics.max_drawdown_percent < 15:
            risk_score = 15
        else:
            risk_score = max(0, 25 - metrics.max_drawdown_percent)
            weaknesses.append(f"High drawdown: {metrics.max_drawdown_percent:.1f}%")
        score.risk_score = risk_score
        
        # Diversification score (0-25)
        if metrics.num_strategies >= 3 and metrics.avg_correlation < 0.5:
            div_score = 25
            strengths.append("Well diversified portfolio")
        elif metrics.num_strategies >= 2 and metrics.avg_correlation < 0.7:
            div_score = 20
        elif metrics.num_strategies >= 2:
            div_score = 15
            if metrics.avg_correlation > 0.7:
                weaknesses.append(f"High strategy correlation: {metrics.avg_correlation:.2f}")
                recommendations.append("Add uncorrelated strategies")
        else:
            div_score = 10
            recommendations.append("Consider adding more strategies for diversification")
        score.diversification_score = div_score
        
        # Challenge score (0-25)
        if challenge.pass_probability >= 0.8:
            challenge_score = 25
            strengths.append(f"High challenge pass probability: {challenge.pass_probability:.0%}")
        elif challenge.pass_probability >= 0.6:
            challenge_score = 20
        elif challenge.pass_probability >= 0.4:
            challenge_score = 15
        else:
            challenge_score = max(0, challenge.pass_probability * 25)
            weaknesses.append(f"Low pass probability: {challenge.pass_probability:.0%}")
            recommendations.append("Reduce risk or increase edge to improve pass rate")
        score.challenge_score = challenge_score
        
        # Total score
        score.total_score = return_score + risk_score + div_score + challenge_score
        
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
        
        # Challenge ready check
        score.is_challenge_ready = (
            score.total_score >= 55 and
            challenge.pass_probability >= 0.5 and
            metrics.max_drawdown_percent < self.config.max_total_drawdown_percent
        )
        
        if not score.is_challenge_ready and challenge.fail_reason:
            recommendations.append(f"Address: {challenge.fail_reason}")
        
        score.strengths = strengths
        score.weaknesses = weaknesses
        score.recommendations = recommendations
        
        return score


def create_challenge_portfolio_engine(
    config: PortfolioConfig,
    strategies: List[Dict]
) -> ChallengePortfolioEngine:
    """Factory function to create portfolio engine"""
    return ChallengePortfolioEngine(config, strategies)
