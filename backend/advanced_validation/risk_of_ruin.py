"""
Risk of Ruin Calculator
Phase 2: Statistical Ruin Probability Analysis

Calculates probability of account ruin based on:
- Win rate and risk/reward ratio
- Position sizing
- Maximum drawdown tolerance
- Account survival probability over N trades
"""

import numpy as np
import uuid
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from scipy import stats
import math

logger = logging.getLogger(__name__)


class RiskOfRuinConfig(BaseModel):
    """Configuration for risk of ruin calculation"""
    initial_balance: float = Field(default=10000.0)
    ruin_threshold_percent: float = Field(default=50.0, description="Account loss % considered ruin")
    risk_per_trade_percent: float = Field(default=2.0, ge=0.1, le=10.0)
    num_simulations: int = Field(default=10000, ge=1000, le=100000)
    trade_horizon: int = Field(default=500, description="Number of trades to simulate")


class RiskOfRuinMetrics(BaseModel):
    """Risk of ruin calculation metrics"""
    # Ruin probabilities
    ruin_probability: float = 0.0  # Probability of hitting ruin threshold
    survival_probability: float = 0.0
    
    # Time to ruin
    median_trades_to_ruin: float = 0.0  # Median trades before ruin (if ruined)
    avg_trades_to_ruin: float = 0.0
    
    # Analytical estimates
    theoretical_ruin_prob: float = 0.0  # From analytical formula
    kelly_fraction: float = 0.0  # Optimal Kelly bet size
    
    # Risk metrics
    expected_max_drawdown: float = 0.0
    drawdown_95_percentile: float = 0.0
    required_win_rate_for_survival: float = 0.0
    
    # Strategy statistics used
    observed_win_rate: float = 0.0
    observed_avg_win: float = 0.0
    observed_avg_loss: float = 0.0
    observed_risk_reward: float = 0.0


class RiskOfRuinScore(BaseModel):
    """Risk of ruin based score"""
    total_score: float = 0.0
    survival_score: float = 0.0
    kelly_score: float = 0.0
    drawdown_score: float = 0.0
    grade: str = "F"
    risk_level: str = "EXTREME"  # LOW, MODERATE, HIGH, EXTREME
    is_acceptable: bool = False
    strengths: List[str] = []
    weaknesses: List[str] = []
    recommendations: List[str] = []


class RiskOfRuinResult(BaseModel):
    """Complete risk of ruin analysis result"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    strategy_name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Configuration
    config: RiskOfRuinConfig = Field(default_factory=RiskOfRuinConfig)
    
    # Results
    metrics: RiskOfRuinMetrics = Field(default_factory=RiskOfRuinMetrics)
    risk_score: RiskOfRuinScore = Field(default_factory=RiskOfRuinScore)
    
    # Distribution data
    drawdown_distribution: List[float] = []
    trades_to_ruin_distribution: List[float] = []
    
    # Sensitivity analysis
    risk_vs_ruin_curve: List[Dict[str, float]] = []  # risk % -> ruin prob
    
    execution_time_seconds: float = 0.0


class RiskOfRuinCalculator:
    """
    Risk of Ruin Analysis Engine
    
    Calculates the probability of account ruin based on
    trading statistics and position sizing.
    """
    
    def __init__(self, config: RiskOfRuinConfig, trades: List[Dict]):
        self.config = config
        self.trades = trades
        self.trade_pnls = [t.get('profit_loss', t.get('pnl', 0)) for t in trades]
        
        # Calculate trade statistics
        self._calculate_trade_stats()
    
    def _calculate_trade_stats(self):
        """Calculate win rate, avg win/loss from trades"""
        if not self.trade_pnls:
            self.win_rate = 0.5
            self.avg_win = 100
            self.avg_loss = 100
            return
        
        wins = [p for p in self.trade_pnls if p > 0]
        losses = [abs(p) for p in self.trade_pnls if p < 0]
        
        self.win_rate = len(wins) / len(self.trade_pnls) if self.trade_pnls else 0.5
        self.avg_win = np.mean(wins) if wins else 100
        self.avg_loss = np.mean(losses) if losses else 100
        self.risk_reward = self.avg_win / self.avg_loss if self.avg_loss > 0 else 1.0
    
    def run(self) -> RiskOfRuinResult:
        """
        Run risk of ruin analysis
        """
        start_time = datetime.now()
        
        result = RiskOfRuinResult(config=self.config)
        
        # Run Monte Carlo simulation
        sim_results = self._run_simulations()
        
        # Calculate analytical estimates
        theoretical = self._calculate_theoretical_ruin()
        
        # Calculate metrics
        result.metrics = self._calculate_metrics(sim_results, theoretical)
        
        # Store distributions (subsample)
        sample_size = min(500, len(sim_results['max_drawdowns']))
        indices = np.random.choice(len(sim_results['max_drawdowns']), sample_size, replace=False)
        result.drawdown_distribution = [sim_results['max_drawdowns'][i] for i in indices]
        result.trades_to_ruin_distribution = [
            sim_results['trades_to_ruin'][i] 
            for i in indices 
            if sim_results['trades_to_ruin'][i] is not None
        ][:100]
        
        # Risk vs ruin curve
        result.risk_vs_ruin_curve = self._calculate_risk_curve()
        
        # Calculate score
        result.risk_score = self._calculate_score(result.metrics)
        
        result.execution_time_seconds = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Risk of ruin complete: {result.metrics.ruin_probability:.1%} ruin probability, "
                   f"Score: {result.risk_score.total_score:.1f}")
        
        return result
    
    def _run_simulations(self) -> Dict[str, List]:
        """
        Run Monte Carlo simulations for ruin probability
        """
        max_drawdowns = []
        trades_to_ruin = []
        final_balances = []
        ruined_count = 0
        
        ruin_threshold = self.config.initial_balance * (1 - self.config.ruin_threshold_percent / 100)
        risk_amount = self.config.initial_balance * self.config.risk_per_trade_percent / 100
        
        for _ in range(self.config.num_simulations):
            balance = self.config.initial_balance
            peak = balance
            max_dd = 0
            ruined = False
            ruin_trade = None
            
            for trade_num in range(self.config.trade_horizon):
                # Simulate trade outcome
                if np.random.random() < self.win_rate:
                    # Win
                    pnl = risk_amount * self.risk_reward
                else:
                    # Loss
                    pnl = -risk_amount
                
                balance += pnl
                
                if balance > peak:
                    peak = balance
                
                current_dd = (peak - balance) / peak * 100 if peak > 0 else 0
                max_dd = max(max_dd, current_dd)
                
                if balance <= ruin_threshold and not ruined:
                    ruined = True
                    ruin_trade = trade_num + 1
                    ruined_count += 1
                    break
            
            max_drawdowns.append(max_dd)
            trades_to_ruin.append(ruin_trade if ruined else None)
            final_balances.append(balance)
        
        return {
            'max_drawdowns': max_drawdowns,
            'trades_to_ruin': trades_to_ruin,
            'final_balances': final_balances,
            'ruined_count': ruined_count
        }
    
    def _calculate_theoretical_ruin(self) -> Dict[str, float]:
        """
        Calculate theoretical risk of ruin using analytical formulas
        """
        # Kelly Criterion
        # f* = (p * b - q) / b
        # where p = win rate, q = 1-p, b = risk/reward ratio
        p = self.win_rate
        q = 1 - p
        b = self.risk_reward
        
        if b > 0:
            kelly = (p * b - q) / b
        else:
            kelly = 0
        
        kelly = max(0, min(1, kelly))  # Clamp to [0, 1]
        
        # Risk of Ruin formula (approximate)
        # RoR ≈ ((1-edge)/(1+edge))^N
        # where edge = p*b - q, N = units to lose
        edge = p * b - q
        
        if edge > 0:
            units_to_ruin = self.config.ruin_threshold_percent / self.config.risk_per_trade_percent
            theoretical_ror = ((1 - edge) / (1 + edge)) ** units_to_ruin if edge < 1 else 0
        else:
            theoretical_ror = 1.0  # Negative edge = certain ruin eventually
        
        theoretical_ror = min(1.0, max(0, theoretical_ror))
        
        # Required win rate for positive expectancy
        # p * avg_win - (1-p) * avg_loss > 0
        # p > avg_loss / (avg_win + avg_loss)
        required_wr = self.avg_loss / (self.avg_win + self.avg_loss) if (self.avg_win + self.avg_loss) > 0 else 0.5
        
        return {
            'kelly': kelly,
            'theoretical_ror': theoretical_ror,
            'required_win_rate': required_wr,
            'edge': edge
        }
    
    def _calculate_metrics(self, sim_results: Dict, theoretical: Dict) -> RiskOfRuinMetrics:
        """
        Calculate risk of ruin metrics
        """
        n_sims = self.config.num_simulations
        max_drawdowns = np.array(sim_results['max_drawdowns'])
        trades_to_ruin = [t for t in sim_results['trades_to_ruin'] if t is not None]
        
        return RiskOfRuinMetrics(
            ruin_probability=sim_results['ruined_count'] / n_sims,
            survival_probability=1 - sim_results['ruined_count'] / n_sims,
            
            median_trades_to_ruin=float(np.median(trades_to_ruin)) if trades_to_ruin else self.config.trade_horizon,
            avg_trades_to_ruin=float(np.mean(trades_to_ruin)) if trades_to_ruin else self.config.trade_horizon,
            
            theoretical_ruin_prob=theoretical['theoretical_ror'],
            kelly_fraction=theoretical['kelly'],
            
            expected_max_drawdown=float(np.mean(max_drawdowns)),
            drawdown_95_percentile=float(np.percentile(max_drawdowns, 95)),
            required_win_rate_for_survival=theoretical['required_win_rate'] * 100,
            
            observed_win_rate=self.win_rate * 100,
            observed_avg_win=self.avg_win,
            observed_avg_loss=self.avg_loss,
            observed_risk_reward=self.risk_reward
        )
    
    def _calculate_risk_curve(self) -> List[Dict[str, float]]:
        """
        Calculate ruin probability at different risk levels
        """
        curve = []
        
        for risk_pct in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]:
            # Quick simulation at this risk level
            ruin_threshold = self.config.initial_balance * (1 - self.config.ruin_threshold_percent / 100)
            risk_amount = self.config.initial_balance * risk_pct / 100
            
            ruined = 0
            mini_sims = 1000
            
            for _ in range(mini_sims):
                balance = self.config.initial_balance
                
                for _ in range(200):  # Shorter horizon for speed
                    if np.random.random() < self.win_rate:
                        balance += risk_amount * self.risk_reward
                    else:
                        balance -= risk_amount
                    
                    if balance <= ruin_threshold:
                        ruined += 1
                        break
            
            curve.append({
                'risk_percent': risk_pct,
                'ruin_probability': ruined / mini_sims
            })
        
        return curve
    
    def _calculate_score(self, metrics: RiskOfRuinMetrics) -> RiskOfRuinScore:
        """
        Calculate risk of ruin score
        """
        score = RiskOfRuinScore()
        strengths = []
        weaknesses = []
        recommendations = []
        
        # Survival score (0-40)
        survival_score = min(40, metrics.survival_probability * 40)
        score.survival_score = survival_score
        
        if metrics.survival_probability >= 0.95:
            strengths.append(f"Excellent survival probability: {metrics.survival_probability:.1%}")
        elif metrics.survival_probability >= 0.80:
            strengths.append(f"Good survival probability: {metrics.survival_probability:.1%}")
        elif metrics.survival_probability < 0.50:
            weaknesses.append(f"High ruin risk: {metrics.ruin_probability:.1%} probability of ruin")
            recommendations.append("Reduce position size or improve win rate")
        
        # Kelly score (0-30) - how close to optimal sizing
        if metrics.kelly_fraction > 0:
            current_risk = self.config.risk_per_trade_percent / 100
            kelly_ratio = current_risk / metrics.kelly_fraction if metrics.kelly_fraction > 0 else 2
            
            # Optimal is around 0.5 * Kelly (half Kelly)
            if 0.3 <= kelly_ratio <= 0.7:
                kelly_score = 30
                strengths.append("Position sizing near optimal (half-Kelly)")
            elif kelly_ratio > 1:
                kelly_score = max(0, 30 - (kelly_ratio - 1) * 30)
                weaknesses.append(f"Over-betting vs Kelly criterion ({kelly_ratio:.1f}x Kelly)")
                recommendations.append(f"Reduce risk to {metrics.kelly_fraction * 50:.1f}% per trade")
            else:
                kelly_score = 30 * kelly_ratio / 0.3
        else:
            kelly_score = 0
            weaknesses.append("Negative expectancy - no Kelly optimal exists")
            recommendations.append("Strategy has negative edge - do not trade live")
        
        score.kelly_score = kelly_score
        
        # Drawdown score (0-30)
        drawdown_score = max(0, 30 - metrics.expected_max_drawdown * 0.6)
        score.drawdown_score = drawdown_score
        
        if metrics.expected_max_drawdown < 15:
            strengths.append(f"Low expected drawdown: {metrics.expected_max_drawdown:.1f}%")
        elif metrics.expected_max_drawdown > 30:
            weaknesses.append(f"High expected drawdown: {metrics.expected_max_drawdown:.1f}%")
        
        # Total score
        score.total_score = survival_score + kelly_score + drawdown_score
        
        # Grade
        if score.total_score >= 85:
            score.grade = "A"
            score.risk_level = "LOW"
        elif score.total_score >= 70:
            score.grade = "B"
            score.risk_level = "MODERATE"
        elif score.total_score >= 55:
            score.grade = "C"
            score.risk_level = "MODERATE"
        elif score.total_score >= 40:
            score.grade = "D"
            score.risk_level = "HIGH"
        else:
            score.grade = "F"
            score.risk_level = "EXTREME"
        
        score.is_acceptable = score.total_score >= 55 and metrics.ruin_probability < 0.20
        
        score.strengths = strengths
        score.weaknesses = weaknesses
        score.recommendations = recommendations
        
        return score


def create_risk_of_ruin_calculator(
    config: RiskOfRuinConfig,
    trades: List[Dict]
) -> RiskOfRuinCalculator:
    """Factory function to create risk of ruin calculator"""
    return RiskOfRuinCalculator(config, trades)
