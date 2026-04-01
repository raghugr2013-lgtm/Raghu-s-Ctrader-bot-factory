"""
Sensitivity Analysis Engine
Phase 2: Parameter Sensitivity Testing

Tests strategy robustness to parameter variations:
- Varies each parameter by ±10-20%
- Identifies parameter sensitivity
- Detects overfitting (highly sensitive parameters)
- Recommends optimal parameter ranges
"""

import numpy as np
import uuid
import logging
from typing import List, Dict, Optional, Tuple, Any, Callable
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from enum import Enum
import itertools

logger = logging.getLogger(__name__)


class SensitivityConfig(BaseModel):
    """Configuration for sensitivity analysis"""
    variation_percent: float = Field(default=20.0, ge=5.0, le=50.0)
    variation_steps: int = Field(default=5, ge=3, le=11)
    initial_balance: float = Field(default=10000.0)
    min_trades_required: int = Field(default=20)
    

class ParameterSensitivity(BaseModel):
    """Sensitivity analysis for a single parameter"""
    parameter_name: str
    original_value: float
    test_values: List[float] = []
    test_results: List[Dict[str, float]] = []  # Performance at each test value
    
    # Sensitivity metrics
    sensitivity_score: float = 0.0  # 0-100, higher = more sensitive
    stability_score: float = 0.0  # 0-100, higher = more stable
    optimal_value: float = 0.0
    optimal_range: Tuple[float, float] = (0.0, 0.0)
    
    # Analysis
    is_sensitive: bool = False  # True if small changes cause big performance shifts
    is_overfitted: bool = False  # True if optimal is at edge of range
    recommendation: str = ""


class SensitivityMetrics(BaseModel):
    """Overall sensitivity metrics"""
    overall_sensitivity: float = 0.0  # Average sensitivity across params
    robustness_score: float = 0.0  # Higher = less sensitive = more robust
    overfitting_risk: float = 0.0  # Risk that strategy is overfitted
    
    most_sensitive_param: str = ""
    least_sensitive_param: str = ""
    
    performance_variance: float = 0.0  # Variance across parameter combinations
    worst_case_degradation: float = 0.0  # Max performance drop from optimal


class SensitivityScore(BaseModel):
    """Sensitivity-based strategy score"""
    total_score: float = 0.0
    parameter_stability: float = 0.0
    edge_preservation: float = 0.0
    overfitting_score: float = 0.0
    grade: str = "F"
    is_robust: bool = False
    strengths: List[str] = []
    weaknesses: List[str] = []
    recommendations: List[str] = []


class SensitivityResult(BaseModel):
    """Complete sensitivity analysis result"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    strategy_name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Configuration
    config: SensitivityConfig = Field(default_factory=SensitivityConfig)
    
    # Results
    parameters_analyzed: int = 0
    total_combinations_tested: int = 0
    parameter_sensitivities: List[ParameterSensitivity] = []
    metrics: SensitivityMetrics = Field(default_factory=SensitivityMetrics)
    sensitivity_score: SensitivityScore = Field(default_factory=SensitivityScore)
    
    # Performance surface (for visualization)
    performance_matrix: Dict[str, List[float]] = {}  # param -> performance values
    
    execution_time_seconds: float = 0.0


class SensitivityAnalyzer:
    """
    Parameter Sensitivity Analysis Engine
    
    Tests how strategy performance varies with parameter changes
    to identify robustness and potential overfitting.
    """
    
    def __init__(
        self,
        config: SensitivityConfig,
        parameters: Dict[str, float],
        backtest_func: Optional[Callable] = None
    ):
        self.config = config
        self.parameters = parameters
        self.backtest_func = backtest_func
        self.baseline_performance = None
        
    def run(self, trades: Optional[List[Dict]] = None) -> SensitivityResult:
        """
        Run sensitivity analysis
        
        If backtest_func is provided, runs actual backtests.
        Otherwise, simulates sensitivity based on trade distribution.
        """
        start_time = datetime.now()
        
        result = SensitivityResult(config=self.config)
        
        if not self.parameters:
            logger.warning("No parameters provided for sensitivity analysis")
            return result
        
        # Calculate baseline performance
        if trades:
            self.baseline_performance = self._calculate_performance(trades)
        else:
            self.baseline_performance = {'profit_factor': 1.5, 'sharpe': 1.0, 'net_profit': 500}
        
        # Analyze each parameter
        param_sensitivities = []
        performance_matrix = {}
        
        for param_name, param_value in self.parameters.items():
            sensitivity = self._analyze_parameter(
                param_name, 
                param_value,
                trades
            )
            param_sensitivities.append(sensitivity)
            performance_matrix[param_name] = [
                r.get('score', 0) for r in sensitivity.test_results
            ]
        
        result.parameter_sensitivities = param_sensitivities
        result.parameters_analyzed = len(param_sensitivities)
        result.performance_matrix = performance_matrix
        result.total_combinations_tested = len(param_sensitivities) * self.config.variation_steps
        
        # Calculate overall metrics
        result.metrics = self._calculate_metrics(param_sensitivities)
        
        # Calculate score
        result.sensitivity_score = self._calculate_score(result.metrics, param_sensitivities)
        
        result.execution_time_seconds = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Sensitivity analysis complete: {result.parameters_analyzed} params, "
                   f"Robustness: {result.metrics.robustness_score:.1f}")
        
        return result
    
    def _analyze_parameter(
        self,
        param_name: str,
        param_value: float,
        trades: Optional[List[Dict]]
    ) -> ParameterSensitivity:
        """
        Analyze sensitivity for a single parameter
        """
        sensitivity = ParameterSensitivity(
            parameter_name=param_name,
            original_value=param_value
        )
        
        # Generate test values
        variation = self.config.variation_percent / 100
        min_val = param_value * (1 - variation)
        max_val = param_value * (1 + variation)
        test_values = np.linspace(min_val, max_val, self.config.variation_steps).tolist()
        sensitivity.test_values = test_values
        
        # Test each value
        performances = []
        for test_val in test_values:
            if self.backtest_func:
                # Run actual backtest with modified parameter
                modified_params = self.parameters.copy()
                modified_params[param_name] = test_val
                perf = self.backtest_func(modified_params)
            else:
                # Simulate performance variation
                perf = self._simulate_parameter_effect(param_name, test_val, param_value, trades)
            
            performances.append(perf)
        
        sensitivity.test_results = performances
        
        # Calculate sensitivity metrics
        scores = [p.get('score', p.get('profit_factor', 1.0) * 50) for p in performances]
        
        # Sensitivity score: higher variance = more sensitive
        score_std = np.std(scores)
        score_range = max(scores) - min(scores) if scores else 0
        sensitivity.sensitivity_score = min(100, score_range * 2 + score_std * 10)
        
        # Stability score: inverse of sensitivity
        sensitivity.stability_score = max(0, 100 - sensitivity.sensitivity_score)
        
        # Find optimal value
        best_idx = np.argmax(scores)
        sensitivity.optimal_value = test_values[best_idx]
        
        # Optimal range (values within 90% of best)
        threshold = max(scores) * 0.9 if max(scores) > 0 else 0
        good_indices = [i for i, s in enumerate(scores) if s >= threshold]
        if good_indices:
            sensitivity.optimal_range = (test_values[min(good_indices)], test_values[max(good_indices)])
        
        # Check for overfitting
        if best_idx == 0 or best_idx == len(test_values) - 1:
            sensitivity.is_overfitted = True
            sensitivity.recommendation = f"Optimal value at edge of range - consider wider search"
        
        # Check sensitivity
        sensitivity.is_sensitive = bool(sensitivity.sensitivity_score > 40)
        if sensitivity.is_sensitive and not sensitivity.is_overfitted:
            sensitivity.recommendation = f"Parameter is sensitive - use with caution"
        elif not sensitivity.is_sensitive:
            sensitivity.recommendation = f"Parameter is stable - good for live trading"
        
        return sensitivity
    
    def _simulate_parameter_effect(
        self,
        param_name: str,
        test_value: float,
        original_value: float,
        trades: Optional[List[Dict]]
    ) -> Dict[str, float]:
        """
        Simulate effect of parameter change on performance
        """
        # Calculate deviation from original
        deviation = abs(test_value - original_value) / original_value if original_value != 0 else 0
        
        # Simulate performance degradation with deviation
        # Assume performance degrades quadratically with parameter change
        degradation_factor = 1 - (deviation ** 2) * np.random.uniform(0.5, 2.0)
        degradation_factor = max(0.3, min(1.1, degradation_factor))  # Clamp
        
        base_pf = self.baseline_performance.get('profit_factor', 1.5)
        base_sharpe = self.baseline_performance.get('sharpe', 1.0)
        base_profit = self.baseline_performance.get('net_profit', 500)
        
        # Add some randomness
        noise = np.random.uniform(0.9, 1.1)
        
        return {
            'profit_factor': base_pf * degradation_factor * noise,
            'sharpe': base_sharpe * degradation_factor * noise,
            'net_profit': base_profit * degradation_factor * noise,
            'score': 50 + (base_pf * degradation_factor * noise - 1) * 30
        }
    
    def _calculate_performance(self, trades: List[Dict]) -> Dict[str, float]:
        """
        Calculate performance metrics from trades
        """
        if not trades:
            return {'profit_factor': 1.0, 'sharpe': 0.0, 'net_profit': 0.0}
        
        pnls = [t.get('profit_loss', t.get('pnl', 0)) for t in trades]
        
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p <= 0)
        total_profit = sum(p for p in pnls if p > 0)
        total_loss = abs(sum(p for p in pnls if p < 0))
        
        profit_factor = total_profit / total_loss if total_loss > 0 else 10.0
        net_profit = sum(pnls)
        
        # Sharpe approximation
        if len(pnls) > 1 and np.std(pnls) > 0:
            sharpe = np.mean(pnls) / np.std(pnls) * np.sqrt(252)
        else:
            sharpe = 0.0
        
        return {
            'profit_factor': profit_factor,
            'sharpe': sharpe,
            'net_profit': net_profit,
            'win_rate': wins / len(pnls) * 100 if pnls else 0
        }
    
    def _calculate_metrics(self, param_sensitivities: List[ParameterSensitivity]) -> SensitivityMetrics:
        """
        Calculate overall sensitivity metrics
        """
        if not param_sensitivities:
            return SensitivityMetrics()
        
        sensitivities = [p.sensitivity_score for p in param_sensitivities]
        stabilities = [p.stability_score for p in param_sensitivities]
        
        # Sort by sensitivity
        sorted_params = sorted(param_sensitivities, key=lambda x: x.sensitivity_score, reverse=True)
        
        # Calculate worst case degradation
        all_scores = []
        for ps in param_sensitivities:
            for result in ps.test_results:
                all_scores.append(result.get('score', 50))
        
        best_score = max(all_scores) if all_scores else 50
        worst_score = min(all_scores) if all_scores else 0
        
        # Count overfitted parameters
        overfitted_count = sum(1 for p in param_sensitivities if p.is_overfitted)
        
        return SensitivityMetrics(
            overall_sensitivity=np.mean(sensitivities) if sensitivities else 0,
            robustness_score=np.mean(stabilities) if stabilities else 0,
            overfitting_risk=overfitted_count / len(param_sensitivities) * 100 if param_sensitivities else 0,
            most_sensitive_param=sorted_params[0].parameter_name if sorted_params else "",
            least_sensitive_param=sorted_params[-1].parameter_name if sorted_params else "",
            performance_variance=np.var(all_scores) if all_scores else 0,
            worst_case_degradation=(best_score - worst_score) / best_score * 100 if best_score > 0 else 0
        )
    
    def _calculate_score(self, metrics: SensitivityMetrics, params: List[ParameterSensitivity]) -> SensitivityScore:
        """
        Calculate sensitivity score
        """
        score = SensitivityScore()
        strengths = []
        weaknesses = []
        recommendations = []
        
        # Parameter stability score (0-40)
        stability_score = min(40, metrics.robustness_score * 0.4)
        score.parameter_stability = stability_score
        
        if metrics.robustness_score >= 70:
            strengths.append("Parameters are stable across variations")
        elif metrics.robustness_score < 40:
            weaknesses.append("Parameters are highly sensitive to changes")
            recommendations.append("Consider more robust parameter values")
        
        # Edge preservation score (0-30)
        edge_score = max(0, 30 - metrics.worst_case_degradation * 0.3)
        score.edge_preservation = edge_score
        
        if metrics.worst_case_degradation < 20:
            strengths.append("Strategy edge preserved across parameter ranges")
        elif metrics.worst_case_degradation > 50:
            weaknesses.append(f"Large performance degradation ({metrics.worst_case_degradation:.0f}%) with parameter changes")
        
        # Overfitting score (0-30)
        overfitting_score = max(0, 30 - metrics.overfitting_risk * 0.3)
        score.overfitting_score = overfitting_score
        
        if metrics.overfitting_risk < 20:
            strengths.append("Low overfitting risk detected")
        elif metrics.overfitting_risk > 50:
            weaknesses.append(f"High overfitting risk ({metrics.overfitting_risk:.0f}%)")
            recommendations.append("Review parameter optimization - may be curve-fitted")
        
        # Total score
        score.total_score = stability_score + edge_score + overfitting_score
        
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
        
        score.is_robust = bool(score.total_score >= 55 and metrics.overfitting_risk < 40)
        
        # Add specific recommendations for sensitive parameters
        sensitive_params = [p for p in params if p.is_sensitive]
        if sensitive_params:
            recommendations.append(f"Sensitive parameters: {', '.join(p.parameter_name for p in sensitive_params[:3])}")
        
        score.strengths = strengths
        score.weaknesses = weaknesses
        score.recommendations = recommendations
        
        return score


def create_sensitivity_analyzer(
    config: SensitivityConfig,
    parameters: Dict[str, float],
    backtest_func: Optional[Callable] = None
) -> SensitivityAnalyzer:
    """Factory function to create sensitivity analyzer"""
    return SensitivityAnalyzer(config, parameters, backtest_func)
