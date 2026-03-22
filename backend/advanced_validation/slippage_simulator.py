"""
Slippage & Execution Reality Simulator
Phase 3: Real-World Execution Simulation

Simulates realistic trading conditions:
- Spread variation (time-of-day, news events)
- Slippage (market vs limit orders)
- Execution delays (latency simulation)
- Partial fills and requotes
"""

import numpy as np
import uuid
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class ExecutionType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class SlippageConfig(BaseModel):
    """Configuration for slippage simulation"""
    # Spread settings
    base_spread_pips: float = Field(default=1.0)
    spread_volatility: float = Field(default=0.5, description="Spread variation factor")
    max_spread_multiplier: float = Field(default=5.0, description="Max spread during news")
    
    # Slippage settings
    avg_slippage_pips: float = Field(default=0.3)
    slippage_std: float = Field(default=0.5)
    positive_slippage_prob: float = Field(default=0.3, description="Probability of positive slippage")
    
    # Execution settings
    avg_latency_ms: float = Field(default=50.0)
    latency_std_ms: float = Field(default=20.0)
    requote_probability: float = Field(default=0.05)
    partial_fill_probability: float = Field(default=0.02)
    
    # Time-based factors
    session_spread_multipliers: Dict[str, float] = Field(
        default={
            "asian": 1.5,
            "london": 0.8,
            "new_york": 0.9,
            "overlap": 0.7,
            "off_hours": 2.0
        }
    )
    
    # Initial balance for impact calculation
    initial_balance: float = Field(default=10000.0)
    pip_value: float = Field(default=10.0, description="Value per pip per lot")


class ExecutionMetrics(BaseModel):
    """Metrics from execution simulation"""
    # Slippage impact
    total_slippage_pips: float = 0.0
    avg_slippage_per_trade: float = 0.0
    slippage_cost_percent: float = 0.0  # As % of profit
    
    # Spread impact
    total_spread_cost: float = 0.0
    avg_spread_pips: float = 0.0
    spread_cost_percent: float = 0.0
    
    # Execution quality
    avg_latency_ms: float = 0.0
    requote_rate: float = 0.0
    partial_fill_rate: float = 0.0
    
    # Performance impact
    gross_profit: float = 0.0  # Before costs
    net_profit: float = 0.0   # After costs
    profit_degradation_percent: float = 0.0
    
    # Comparison
    ideal_profit_factor: float = 0.0
    realistic_profit_factor: float = 0.0
    ideal_win_rate: float = 0.0
    realistic_win_rate: float = 0.0


class SlippageScore(BaseModel):
    """Slippage impact score"""
    total_score: float = 0.0
    execution_quality: float = 0.0
    cost_efficiency: float = 0.0
    robustness_to_costs: float = 0.0
    grade: str = "F"
    impact_level: str = "SEVERE"  # MINIMAL, MODERATE, SIGNIFICANT, SEVERE
    is_viable: bool = False
    strengths: List[str] = []
    weaknesses: List[str] = []
    recommendations: List[str] = []


class SlippageResult(BaseModel):
    """Complete slippage simulation result"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    strategy_name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Configuration
    config: SlippageConfig = Field(default_factory=SlippageConfig)
    
    # Results
    total_trades_simulated: int = 0
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics)
    slippage_score: SlippageScore = Field(default_factory=SlippageScore)
    
    # Trade-by-trade data
    trade_impacts: List[Dict[str, float]] = []  # Per-trade slippage/spread impact
    
    # Sensitivity analysis
    profit_vs_spread_curve: List[Dict[str, float]] = []  # spread -> profit impact
    profit_vs_slippage_curve: List[Dict[str, float]] = []  # slippage -> profit impact
    
    execution_time_seconds: float = 0.0


class SlippageSimulator:
    """
    Execution Reality Simulator
    
    Simulates real-world trading costs and execution quality
    to provide realistic performance expectations.
    """
    
    def __init__(self, config: SlippageConfig, trades: List[Dict]):
        self.config = config
        self.trades = trades
        self.trade_pnls = [t.get('profit_loss', t.get('pnl', 0)) for t in trades]
        
    def run(self) -> SlippageResult:
        """
        Run slippage simulation on trades
        """
        start_time = datetime.now()
        
        result = SlippageResult(
            config=self.config,
            total_trades_simulated=len(self.trades)
        )
        
        if not self.trades:
            logger.warning("No trades to simulate")
            return result
        
        # Simulate execution for each trade
        trade_impacts = []
        total_slippage = 0
        total_spread_cost = 0
        requotes = 0
        partial_fills = 0
        latencies = []
        
        realistic_pnls = []
        
        for trade in self.trades:
            impact = self._simulate_trade_execution(trade)
            trade_impacts.append(impact)
            
            total_slippage += impact['slippage_pips']
            total_spread_cost += impact['spread_cost']
            latencies.append(impact['latency_ms'])
            
            if impact['requote']:
                requotes += 1
            if impact['partial_fill']:
                partial_fills += 1
            
            realistic_pnls.append(impact['realistic_pnl'])
        
        result.trade_impacts = trade_impacts[:100]  # Limit storage
        
        # Calculate metrics
        result.metrics = self._calculate_metrics(
            trade_impacts, realistic_pnls, latencies, requotes, partial_fills
        )
        
        # Sensitivity curves
        result.profit_vs_spread_curve = self._calculate_spread_sensitivity()
        result.profit_vs_slippage_curve = self._calculate_slippage_sensitivity()
        
        # Calculate score
        result.slippage_score = self._calculate_score(result.metrics)
        
        result.execution_time_seconds = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Slippage simulation complete: {result.metrics.profit_degradation_percent:.1f}% profit degradation")
        
        return result
    
    def _simulate_trade_execution(self, trade: Dict) -> Dict:
        """
        Simulate execution for a single trade
        """
        original_pnl = trade.get('profit_loss', trade.get('pnl', 0))
        volume = trade.get('volume', trade.get('position_size', 1.0))
        
        # Simulate spread
        session = self._get_session(trade.get('entry_time'))
        session_multiplier = self.config.session_spread_multipliers.get(session, 1.0)
        
        spread = self.config.base_spread_pips * session_multiplier
        spread *= (1 + np.random.uniform(-self.config.spread_volatility, self.config.spread_volatility))
        spread = max(0.5, spread)  # Minimum spread
        
        spread_cost = spread * self.config.pip_value * volume
        
        # Simulate slippage
        if np.random.random() < self.config.positive_slippage_prob:
            # Positive slippage (price improved)
            slippage = -abs(np.random.normal(self.config.avg_slippage_pips * 0.5, self.config.slippage_std))
        else:
            # Negative slippage (price worsened)
            slippage = abs(np.random.normal(self.config.avg_slippage_pips, self.config.slippage_std))
        
        slippage_cost = slippage * self.config.pip_value * volume
        
        # Simulate latency
        latency = max(10, np.random.normal(self.config.avg_latency_ms, self.config.latency_std_ms))
        
        # Simulate requotes and partial fills
        requote = np.random.random() < self.config.requote_probability
        partial_fill = np.random.random() < self.config.partial_fill_probability
        
        # Additional cost for requote (assume worse price)
        requote_cost = spread_cost * 0.5 if requote else 0
        
        # Partial fill impact (assume only 70% filled)
        fill_factor = 0.7 if partial_fill else 1.0
        
        # Calculate realistic PnL
        total_cost = spread_cost + slippage_cost + requote_cost
        realistic_pnl = (original_pnl - total_cost) * fill_factor
        
        return {
            'original_pnl': original_pnl,
            'realistic_pnl': realistic_pnl,
            'spread_pips': spread,
            'spread_cost': spread_cost,
            'slippage_pips': slippage,
            'slippage_cost': slippage_cost,
            'latency_ms': latency,
            'requote': requote,
            'partial_fill': partial_fill,
            'total_cost': total_cost
        }
    
    def _get_session(self, entry_time) -> str:
        """
        Determine trading session from entry time
        """
        if entry_time is None:
            return "london"  # Default
        
        if isinstance(entry_time, str):
            try:
                entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
            except:
                return "london"
        
        hour = entry_time.hour
        
        if 0 <= hour < 7:
            return "asian"
        elif 7 <= hour < 12:
            return "london"
        elif 12 <= hour < 16:
            return "overlap"  # London/NY overlap
        elif 16 <= hour < 21:
            return "new_york"
        else:
            return "off_hours"
    
    def _calculate_metrics(self, impacts, realistic_pnls, latencies, requotes, partial_fills) -> ExecutionMetrics:
        """
        Calculate execution metrics
        """
        n_trades = len(impacts)
        if n_trades == 0:
            return ExecutionMetrics()
        
        gross_profit = sum(self.trade_pnls)
        net_profit = sum(realistic_pnls)
        
        total_slippage = sum(i['slippage_pips'] for i in impacts)
        total_spread = sum(i['spread_cost'] for i in impacts)
        
        # Calculate profit factors
        ideal_wins = sum(p for p in self.trade_pnls if p > 0)
        ideal_losses = abs(sum(p for p in self.trade_pnls if p < 0))
        ideal_pf = ideal_wins / ideal_losses if ideal_losses > 0 else 10.0
        
        realistic_wins = sum(p for p in realistic_pnls if p > 0)
        realistic_losses = abs(sum(p for p in realistic_pnls if p < 0))
        realistic_pf = realistic_wins / realistic_losses if realistic_losses > 0 else 10.0
        
        # Win rates
        ideal_wr = sum(1 for p in self.trade_pnls if p > 0) / n_trades * 100
        realistic_wr = sum(1 for p in realistic_pnls if p > 0) / n_trades * 100
        
        return ExecutionMetrics(
            total_slippage_pips=total_slippage,
            avg_slippage_per_trade=total_slippage / n_trades,
            slippage_cost_percent=abs(total_slippage * self.config.pip_value) / abs(gross_profit) * 100 if gross_profit != 0 else 0,
            
            total_spread_cost=total_spread,
            avg_spread_pips=np.mean([i['spread_pips'] for i in impacts]),
            spread_cost_percent=total_spread / abs(gross_profit) * 100 if gross_profit != 0 else 0,
            
            avg_latency_ms=np.mean(latencies),
            requote_rate=requotes / n_trades * 100,
            partial_fill_rate=partial_fills / n_trades * 100,
            
            gross_profit=gross_profit,
            net_profit=net_profit,
            profit_degradation_percent=abs(gross_profit - net_profit) / abs(gross_profit) * 100 if gross_profit != 0 else 0,
            
            ideal_profit_factor=ideal_pf,
            realistic_profit_factor=realistic_pf,
            ideal_win_rate=ideal_wr,
            realistic_win_rate=realistic_wr
        )
    
    def _calculate_spread_sensitivity(self) -> List[Dict[str, float]]:
        """
        Calculate profit impact at different spread levels
        """
        curve = []
        gross_profit = sum(self.trade_pnls)
        avg_volume = np.mean([t.get('volume', 1.0) for t in self.trades]) if self.trades else 1.0
        
        for spread in [0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]:
            spread_cost = spread * self.config.pip_value * avg_volume * len(self.trades)
            net_profit = gross_profit - spread_cost
            degradation = abs(spread_cost / gross_profit * 100) if gross_profit != 0 else 0
            
            curve.append({
                'spread_pips': spread,
                'net_profit': net_profit,
                'degradation_percent': degradation
            })
        
        return curve
    
    def _calculate_slippage_sensitivity(self) -> List[Dict[str, float]]:
        """
        Calculate profit impact at different slippage levels
        """
        curve = []
        gross_profit = sum(self.trade_pnls)
        avg_volume = np.mean([t.get('volume', 1.0) for t in self.trades]) if self.trades else 1.0
        
        for slippage in [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]:
            slippage_cost = slippage * self.config.pip_value * avg_volume * len(self.trades)
            net_profit = gross_profit - slippage_cost
            degradation = abs(slippage_cost / gross_profit * 100) if gross_profit != 0 else 0
            
            curve.append({
                'slippage_pips': slippage,
                'net_profit': net_profit,
                'degradation_percent': degradation
            })
        
        return curve
    
    def _calculate_score(self, metrics: ExecutionMetrics) -> SlippageScore:
        """
        Calculate slippage impact score
        """
        score = SlippageScore()
        strengths = []
        weaknesses = []
        recommendations = []
        
        # Execution quality score (0-35)
        latency_penalty = min(15, metrics.avg_latency_ms / 10)
        requote_penalty = min(10, metrics.requote_rate)
        partial_penalty = min(10, metrics.partial_fill_rate * 2)
        execution_score = max(0, 35 - latency_penalty - requote_penalty - partial_penalty)
        score.execution_quality = execution_score
        
        if metrics.avg_latency_ms < 30:
            strengths.append("Low execution latency")
        elif metrics.avg_latency_ms > 100:
            weaknesses.append(f"High latency ({metrics.avg_latency_ms:.0f}ms)")
            recommendations.append("Consider broker with lower latency")
        
        # Cost efficiency score (0-35)
        total_cost_percent = metrics.spread_cost_percent + metrics.slippage_cost_percent
        cost_score = max(0, 35 - total_cost_percent * 2)
        score.cost_efficiency = cost_score
        
        if total_cost_percent < 5:
            strengths.append("Low execution costs")
        elif total_cost_percent > 20:
            weaknesses.append(f"High execution costs ({total_cost_percent:.1f}% of profit)")
            recommendations.append("Strategy may not be viable with current spread/slippage")
        
        # Robustness to costs score (0-30)
        if metrics.ideal_profit_factor > 0:
            pf_degradation = (metrics.ideal_profit_factor - metrics.realistic_profit_factor) / metrics.ideal_profit_factor * 100
        else:
            pf_degradation = 100
        
        robustness_score = max(0, 30 - pf_degradation)
        score.robustness_to_costs = robustness_score
        
        if pf_degradation < 10:
            strengths.append("Strategy maintains edge after costs")
        elif pf_degradation > 30:
            weaknesses.append(f"Significant profit factor degradation ({pf_degradation:.0f}%)")
        
        # Total score
        score.total_score = execution_score + cost_score + robustness_score
        
        # Grade and impact level
        if score.total_score >= 85:
            score.grade = "A"
            score.impact_level = "MINIMAL"
        elif score.total_score >= 70:
            score.grade = "B"
            score.impact_level = "MODERATE"
        elif score.total_score >= 55:
            score.grade = "C"
            score.impact_level = "SIGNIFICANT"
        elif score.total_score >= 40:
            score.grade = "D"
            score.impact_level = "SIGNIFICANT"
        else:
            score.grade = "F"
            score.impact_level = "SEVERE"
        
        # Is viable check
        score.is_viable = (
            score.total_score >= 50 and
            metrics.realistic_profit_factor > 1.0 and
            metrics.profit_degradation_percent < 40
        )
        
        if not score.is_viable:
            recommendations.append("Strategy may not be profitable under realistic execution conditions")
        
        score.strengths = strengths
        score.weaknesses = weaknesses
        score.recommendations = recommendations
        
        return score


def create_slippage_simulator(
    config: SlippageConfig,
    trades: List[Dict]
) -> SlippageSimulator:
    """Factory function to create slippage simulator"""
    return SlippageSimulator(config, trades)
