"""
Scoring Engine - Phase 3
Scores and ranks trading strategies based on multiple criteria
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import math
import logging


logger = logging.getLogger(__name__)


class Grade(Enum):
    """Strategy grade levels"""
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class ApprovalStatus(Enum):
    """Strategy approval status"""
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    REJECTED = "rejected"


@dataclass
class ScoreComponent:
    """Individual score component"""
    name: str
    weight: float
    raw_value: float
    normalized_score: float  # 0-100
    weighted_score: float
    description: str = ""


@dataclass
class StrategyScore:
    """Complete strategy scoring result"""
    total_score: float
    grade: str
    status: str
    components: List[ScoreComponent]
    prop_score: float
    max_drawdown: float
    risk_of_ruin: float
    stability_score: float
    simplicity_score: float
    approval_reasons: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_score": round(self.total_score, 2),
            "grade": self.grade,
            "status": self.status,
            "components": [asdict(c) for c in self.components],
            "prop_score": round(self.prop_score, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "risk_of_ruin": round(self.risk_of_ruin, 4),
            "stability_score": round(self.stability_score, 2),
            "simplicity_score": round(self.simplicity_score, 2),
            "approval_reasons": self.approval_reasons,
            "rejection_reasons": self.rejection_reasons,
            "recommendations": self.recommendations
        }


class ScoringEngine:
    """
    Scores trading strategies based on multiple criteria
    
    Scoring Weights:
    - Prop Score: 30%
    - Max Drawdown: 25%
    - Risk of Ruin: 20%
    - Stability: 15%
    - Simplicity: 10%
    
    Approval Thresholds:
    - Prop Score >= 80
    - Max DD < 6%
    - Risk of Ruin < 5%
    """
    
    # Scoring weights (must sum to 1.0)
    WEIGHTS = {
        'prop_score': 0.30,
        'max_drawdown': 0.25,
        'risk_of_ruin': 0.20,
        'stability': 0.15,
        'simplicity': 0.10
    }
    
    # Approval thresholds
    MIN_PROP_SCORE = 80
    MAX_DRAWDOWN = 6.0  # percent
    MAX_RISK_OF_RUIN = 5.0  # percent
    
    # Grade thresholds
    GRADE_THRESHOLDS = {
        95: Grade.A_PLUS,
        85: Grade.A,
        70: Grade.B,
        55: Grade.C,
        40: Grade.D,
        0: Grade.F
    }
    
    def __init__(self):
        pass
    
    def score(
        self,
        improved_strategy: Dict[str, Any],
        parsed_data: Dict[str, Any],
        validation_results: Optional[Dict[str, Any]] = None
    ) -> StrategyScore:
        """
        Score a strategy based on all criteria
        
        Args:
            improved_strategy: Output from refinement engine
            parsed_data: Original parsed bot data
            validation_results: Optional validation engine results
        
        Returns:
            StrategyScore with complete scoring breakdown
        """
        components = []
        
        # 1. Prop Score (30%)
        prop_score, prop_component = self._calculate_prop_score(improved_strategy, validation_results)
        components.append(prop_component)
        
        # 2. Max Drawdown Score (25%)
        max_dd, dd_component = self._calculate_drawdown_score(improved_strategy, validation_results)
        components.append(dd_component)
        
        # 3. Risk of Ruin Score (20%)
        ror, ror_component = self._calculate_risk_of_ruin(improved_strategy, validation_results)
        components.append(ror_component)
        
        # 4. Stability Score (15%)
        stability, stability_component = self._calculate_stability_score(improved_strategy, validation_results)
        components.append(stability_component)
        
        # 5. Simplicity Score (10%)
        simplicity, simplicity_component = self._calculate_simplicity_score(improved_strategy, parsed_data)
        components.append(simplicity_component)
        
        # Calculate total weighted score
        total_score = sum(c.weighted_score for c in components)
        
        # Determine grade
        grade = self._determine_grade(total_score)
        
        # Determine approval status
        status, approval_reasons, rejection_reasons = self._determine_approval(
            prop_score, max_dd, ror, total_score
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            prop_score, max_dd, ror, stability, simplicity, improved_strategy
        )
        
        return StrategyScore(
            total_score=total_score,
            grade=grade.value,
            status=status.value,
            components=components,
            prop_score=prop_score,
            max_drawdown=max_dd,
            risk_of_ruin=ror,
            stability_score=stability,
            simplicity_score=simplicity,
            approval_reasons=approval_reasons,
            rejection_reasons=rejection_reasons,
            recommendations=recommendations
        )
    
    def _calculate_prop_score(
        self, 
        strategy: Dict, 
        validation: Optional[Dict]
    ) -> Tuple[float, ScoreComponent]:
        """
        Calculate prop firm compatibility score
        Based on risk management, profit factor, and trading rules
        """
        score = 0.0
        max_score = 100.0
        
        risk_config = strategy.get('risk_config', {})
        filters = strategy.get('filters', [])
        analysis = strategy.get('analysis', {})
        
        # Stop loss check (20 points)
        if risk_config.get('stop_loss_type') != 'none':
            sl_value = risk_config.get('stop_loss_value', 0)
            if 15 <= sl_value <= 50:
                score += 20
            elif sl_value > 0:
                score += 10
        
        # Take profit check (15 points)
        if risk_config.get('take_profit_type') != 'none':
            tp_value = risk_config.get('take_profit_value', 0)
            sl_value = risk_config.get('stop_loss_value', 1)
            rr_ratio = tp_value / sl_value if sl_value > 0 else 0
            if 1.5 <= rr_ratio <= 3.0:
                score += 15
            elif rr_ratio > 0:
                score += 7
        
        # Position sizing (15 points)
        if risk_config.get('position_sizing') == 'percent_risk':
            risk_pct = risk_config.get('size_value', 0)
            if 0.5 <= risk_pct <= 2.0:
                score += 15
            elif risk_pct > 0:
                score += 8
        
        # Daily trade limit (10 points)
        has_daily_limit = any(f.get('type') == 'daily_limit' for f in filters)
        if has_daily_limit:
            score += 10
        
        # Loss streak protection (15 points)
        has_loss_protection = any(f.get('type') == 'loss_streak' for f in filters)
        if has_loss_protection:
            score += 15
        
        # Completeness from analysis (15 points)
        completeness = analysis.get('completeness', {}).get('score', 0)
        score += (completeness / 100) * 15
        
        # Risk score from analysis (10 points)
        risk_score = analysis.get('risk_score', {}).get('score', 50)
        score += (risk_score / 100) * 10
        
        # Add validation results if available
        if validation:
            prop_compliance = validation.get('prop_compliance', {})
            if prop_compliance.get('passed'):
                score = min(score + 10, max_score)
        
        # Normalize to 0-100
        normalized = min(score, max_score)
        weighted = normalized * self.WEIGHTS['prop_score']
        
        return normalized, ScoreComponent(
            name="Prop Score",
            weight=self.WEIGHTS['prop_score'],
            raw_value=score,
            normalized_score=normalized,
            weighted_score=weighted,
            description="Prop firm trading rules compliance"
        )
    
    def _calculate_drawdown_score(
        self, 
        strategy: Dict, 
        validation: Optional[Dict]
    ) -> Tuple[float, ScoreComponent]:
        """
        Calculate max drawdown score
        Lower DD = higher score
        """
        # Estimate max drawdown based on risk config
        risk_config = strategy.get('risk_config', {})
        
        # Base DD estimation from risk parameters
        sl_pips = risk_config.get('stop_loss_value', 30)
        risk_pct = risk_config.get('size_value', 1.0) if risk_config.get('position_sizing') == 'percent_risk' else 2.0
        
        # Estimated max consecutive losses before recovery
        max_losses = 2  # From loss streak protection
        for f in strategy.get('filters', []):
            if f.get('type') == 'loss_streak':
                max_losses = f.get('parameters', {}).get('max_consecutive_losses', 2)
                break
        
        # Estimate max DD (simplified model)
        # DD ≈ risk_per_trade * max_consecutive_losses * safety_factor
        estimated_dd = risk_pct * max_losses * 1.5
        
        # Use validation results if available
        if validation and 'max_drawdown' in validation:
            estimated_dd = validation['max_drawdown']
        
        # Score: lower DD = higher score
        # 0% DD = 100, 10% DD = 0
        normalized = max(0, 100 - (estimated_dd * 10))
        weighted = normalized * self.WEIGHTS['max_drawdown']
        
        return estimated_dd, ScoreComponent(
            name="Max Drawdown",
            weight=self.WEIGHTS['max_drawdown'],
            raw_value=estimated_dd,
            normalized_score=normalized,
            weighted_score=weighted,
            description=f"Estimated max drawdown: {estimated_dd:.2f}%"
        )
    
    def _calculate_risk_of_ruin(
        self, 
        strategy: Dict, 
        validation: Optional[Dict]
    ) -> Tuple[float, ScoreComponent]:
        """
        Calculate risk of ruin score
        Based on win rate, risk per trade, and R:R ratio
        """
        risk_config = strategy.get('risk_config', {})
        
        # Get parameters
        risk_pct = risk_config.get('size_value', 1.0) if risk_config.get('position_sizing') == 'percent_risk' else 2.0
        sl = risk_config.get('stop_loss_value', 25)
        tp = risk_config.get('take_profit_value', 50)
        rr_ratio = tp / sl if sl > 0 else 1.5
        
        # Estimate win rate based on strategy category
        category = strategy.get('category', 'trend_following')
        if category == 'mean_reversion':
            estimated_win_rate = 0.60  # Higher win rate, lower RR
        elif category == 'trend_following':
            estimated_win_rate = 0.40  # Lower win rate, higher RR
        else:
            estimated_win_rate = 0.50
        
        # Use validation results if available
        if validation and 'win_rate' in validation:
            estimated_win_rate = validation['win_rate']
        
        # Risk of Ruin formula (simplified)
        # RoR = ((1 - edge) / (1 + edge)) ^ units_to_ruin
        # where edge = (win_rate * rr_ratio) - (1 - win_rate)
        edge = (estimated_win_rate * rr_ratio) - (1 - estimated_win_rate)
        
        if edge <= 0:
            ror = 50.0  # High risk if no edge
        else:
            # Units to ruin (assuming 100% drawdown limit / risk per trade)
            units_to_ruin = 100 / risk_pct
            if edge < 1:
                ror = ((1 - edge) / (1 + edge)) ** units_to_ruin * 100
            else:
                ror = 0.01  # Very low RoR with positive edge
        
        # Cap at reasonable values
        ror = min(ror, 100.0)
        
        # Score: lower RoR = higher score
        normalized = max(0, 100 - (ror * 2))  # 50% RoR = 0 score
        weighted = normalized * self.WEIGHTS['risk_of_ruin']
        
        return ror, ScoreComponent(
            name="Risk of Ruin",
            weight=self.WEIGHTS['risk_of_ruin'],
            raw_value=ror,
            normalized_score=normalized,
            weighted_score=weighted,
            description=f"Estimated risk of ruin: {ror:.2f}%"
        )
    
    def _calculate_stability_score(
        self, 
        strategy: Dict, 
        validation: Optional[Dict]
    ) -> Tuple[float, ScoreComponent]:
        """
        Calculate strategy stability score
        Based on filters, consistency measures
        """
        score = 0.0
        filters = strategy.get('filters', [])
        risk_config = strategy.get('risk_config', {})
        
        # Session filter (20 points)
        if any(f.get('type') == 'time' for f in filters):
            score += 20
        
        # Spread filter (15 points)
        if any(f.get('type') == 'spread' for f in filters):
            score += 15
        
        # Volatility filter (20 points)
        if any(f.get('type') == 'volatility' for f in filters):
            score += 20
        
        # Trend filter (15 points)
        if any(f.get('type') == 'trend' for f in filters):
            score += 15
        
        # Max concurrent trades = 1 (15 points)
        if risk_config.get('max_concurrent_trades', 10) <= 1:
            score += 15
        
        # Daily limit exists (15 points)
        if any(f.get('type') == 'daily_limit' for f in filters):
            score += 15
        
        normalized = min(score, 100)
        weighted = normalized * self.WEIGHTS['stability']
        
        return normalized, ScoreComponent(
            name="Stability",
            weight=self.WEIGHTS['stability'],
            raw_value=score,
            normalized_score=normalized,
            weighted_score=weighted,
            description="Trading stability and consistency measures"
        )
    
    def _calculate_simplicity_score(
        self, 
        strategy: Dict, 
        parsed: Dict
    ) -> Tuple[float, ScoreComponent]:
        """
        Calculate simplicity score
        Simpler strategies are often more robust
        """
        score = 100.0
        
        # Penalize too many indicators
        indicators = strategy.get('indicators', [])
        if len(indicators) > 5:
            score -= (len(indicators) - 5) * 10
        elif len(indicators) > 3:
            score -= (len(indicators) - 3) * 5
        
        # Penalize complex entry conditions
        entry_signals = strategy.get('entry_signals', [])
        for signal in entry_signals:
            conditions = signal.get('conditions', [])
            if len(conditions) > 3:
                score -= (len(conditions) - 3) * 5
        
        # Check complexity from analysis
        analysis = strategy.get('analysis', {})
        complexity = analysis.get('complexity', 'simple')
        if complexity == 'complex':
            score -= 20
        elif complexity == 'moderate':
            score -= 10
        
        # Bonus for using standard indicators
        standard_indicators = ['RSI', 'SMA', 'EMA', 'MACD', 'ATR', 'BollingerBands']
        for ind in indicators:
            if ind.get('type') in standard_indicators:
                score += 2
        
        normalized = max(0, min(score, 100))
        weighted = normalized * self.WEIGHTS['simplicity']
        
        return normalized, ScoreComponent(
            name="Simplicity",
            weight=self.WEIGHTS['simplicity'],
            raw_value=score,
            normalized_score=normalized,
            weighted_score=weighted,
            description="Strategy simplicity and robustness"
        )
    
    def _determine_grade(self, total_score: float) -> Grade:
        """Determine letter grade from total score"""
        for threshold, grade in sorted(self.GRADE_THRESHOLDS.items(), reverse=True):
            if total_score >= threshold:
                return grade
        return Grade.F
    
    def _determine_approval(
        self, 
        prop_score: float, 
        max_dd: float, 
        ror: float,
        total_score: float
    ) -> Tuple[ApprovalStatus, List[str], List[str]]:
        """
        Determine approval status based on thresholds
        """
        approval_reasons = []
        rejection_reasons = []
        
        # Check prop score
        if prop_score >= self.MIN_PROP_SCORE:
            approval_reasons.append(f"Prop score {prop_score:.1f} >= {self.MIN_PROP_SCORE}")
        else:
            rejection_reasons.append(f"Prop score {prop_score:.1f} < {self.MIN_PROP_SCORE}")
        
        # Check max drawdown
        if max_dd < self.MAX_DRAWDOWN:
            approval_reasons.append(f"Max DD {max_dd:.2f}% < {self.MAX_DRAWDOWN}%")
        else:
            rejection_reasons.append(f"Max DD {max_dd:.2f}% >= {self.MAX_DRAWDOWN}%")
        
        # Check risk of ruin
        if ror < self.MAX_RISK_OF_RUIN:
            approval_reasons.append(f"Risk of Ruin {ror:.2f}% < {self.MAX_RISK_OF_RUIN}%")
        else:
            rejection_reasons.append(f"Risk of Ruin {ror:.2f}% >= {self.MAX_RISK_OF_RUIN}%")
        
        # Determine final status
        if len(rejection_reasons) == 0:
            return ApprovalStatus.APPROVED, approval_reasons, rejection_reasons
        elif len(rejection_reasons) == 1 and total_score >= 70:
            return ApprovalStatus.CONDITIONAL, approval_reasons, rejection_reasons
        else:
            return ApprovalStatus.REJECTED, approval_reasons, rejection_reasons
    
    def _generate_recommendations(
        self,
        prop_score: float,
        max_dd: float,
        ror: float,
        stability: float,
        simplicity: float,
        strategy: Dict
    ) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []
        
        if prop_score < 80:
            recommendations.append("Improve risk management for prop firm compliance")
        
        if max_dd >= 6:
            recommendations.append("Reduce position size or add tighter stops to lower drawdown")
        
        if ror >= 5:
            recommendations.append("Improve risk-reward ratio or reduce risk per trade")
        
        if stability < 70:
            recommendations.append("Add more filters (session, spread, volatility) for stability")
        
        if simplicity < 60:
            recommendations.append("Simplify strategy logic - fewer indicators may improve robustness")
        
        # Check specific missing elements
        risk_config = strategy.get('risk_config', {})
        if not risk_config.get('trailing_stop') and strategy.get('category') == 'trend_following':
            recommendations.append("Consider adding trailing stop for trend strategy")
        
        if risk_config.get('position_sizing') == 'fixed':
            recommendations.append("Switch to percentage-based position sizing")
        
        return recommendations


def create_scoring_engine() -> ScoringEngine:
    """Factory function to create scoring engine"""
    return ScoringEngine()
