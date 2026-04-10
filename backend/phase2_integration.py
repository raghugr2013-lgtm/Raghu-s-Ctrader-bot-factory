"""
Phase 2 Integration Module
Enforces Phase 2 Quality Engine validation across all pipelines
"""

import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone

from scoring_engine import QualityFilters, StrategyGrader, Grade

logger = logging.getLogger(__name__)


class Phase2Validator:
    """
    Central Phase 2 validation enforcer.
    
    ALL strategies must pass through this validator before:
    - Bot generation
    - Live deployment
    - Strategy approval
    """
    
    @staticmethod
    def validate_strategy(strategy: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate strategy against Phase 2 quality standards.
        
        Args:
            strategy: Strategy metrics dictionary
        
        Returns:
            (is_valid, validation_result)
            
        validation_result contains:
            - status: "accepted" | "rejected"
            - grade: A-F letter grade
            - score: composite score (0-100)
            - rejection_reasons: List of reasons if rejected
            - detailed_failures: Detailed failure information
            - recommendation: What to do with this strategy
            - is_tradeable: Boolean - can this strategy be traded?
        """
        # Check if passes all filters
        passes, rejection_reasons = QualityFilters.passes_all(strategy)
        
        # Get detailed rejection report
        rejection_report = QualityFilters.get_detailed_rejection_report(strategy)
        
        # Calculate composite score (use existing or estimate)
        composite_score = strategy.get('composite_score', 0)
        if composite_score == 0:
            # Estimate from metrics
            composite_score = Phase2Validator._estimate_composite_score(strategy)
        
        # Calculate grade
        grade, description, details = StrategyGrader.calculate_grade(composite_score, strategy)
        
        # Check if tradeable
        is_tradeable = StrategyGrader.is_tradeable(grade)
        
        # Build validation result
        validation_result = {
            "status": "accepted" if passes else "rejected",
            "grade": grade.value,
            "grade_emoji": StrategyGrader.get_grade_emoji(grade),
            "grade_color": StrategyGrader.get_grade_color(grade),
            "grade_description": description,
            "composite_score": round(composite_score, 2),
            "is_tradeable": is_tradeable,
            "passes_all_filters": passes,
            "rejection_reasons": rejection_reasons if not passes else [],
            "detailed_failures": rejection_report.get('detailed_failures', []),
            "recommendation": details.get('recommendation', ''),
            "quality": details.get('quality', 'unknown'),
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "validation_version": "2.0.0",
            "metrics": {
                "profit_factor": strategy.get('profit_factor', 0),
                "max_drawdown_pct": abs(strategy.get('max_drawdown_pct', 0)),
                "sharpe_ratio": strategy.get('sharpe_ratio', 0),
                "total_trades": strategy.get('total_trades', 0),
                "stability_score": strategy.get('stability_score', 0),
                "win_rate": strategy.get('win_rate', 0)
            }
        }
        
        return passes and is_tradeable, validation_result
    
    @staticmethod
    def _estimate_composite_score(strategy: Dict[str, Any]) -> float:
        """
        Estimate composite score from available metrics if not provided.
        
        Simple estimation based on key metrics.
        """
        pf = strategy.get('profit_factor', 0)
        dd = abs(strategy.get('max_drawdown_pct', 100))
        sharpe = strategy.get('sharpe_ratio', 0)
        stability = strategy.get('stability_score', 0)
        
        # Simple weighted average
        # PF: 35%, DD: 25%, Sharpe: 20%, Stability: 20%
        
        # PF score (0-100)
        pf_score = min(100, (pf - 1.0) * 50) if pf >= 1.0 else 0
        
        # DD score (0-100) - lower is better
        dd_score = max(0, 100 - (dd * 5)) if dd <= 20 else 0
        
        # Sharpe score (0-100)
        sharpe_score = min(100, sharpe * 50) if sharpe > 0 else 0
        
        # Stability score is already 0-100
        
        composite = (
            pf_score * 0.35 +
            dd_score * 0.25 +
            sharpe_score * 0.20 +
            stability * 0.20
        )
        
        return min(100.0, max(0.0, composite))
    
    @staticmethod
    def can_generate_bot(strategy: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if strategy is allowed to generate bot.
        
        Returns:
            (allowed, reason)
        """
        is_valid, result = Phase2Validator.validate_strategy(strategy)
        
        if not is_valid:
            grade = result['grade']
            
            if grade in ['D', 'F']:
                return False, f"Grade {grade} strategies cannot generate bots. Only grades A, B, C are allowed."
            
            if not result['passes_all_filters']:
                reasons = ', '.join(result['rejection_reasons'])
                return False, f"Strategy failed quality filters: {reasons}"
            
            if not result['is_tradeable']:
                return False, f"Strategy is not tradeable (Grade {grade})"
        
        return True, "Strategy approved for bot generation"
    
    @staticmethod
    def format_validation_summary(result: Dict[str, Any]) -> str:
        """Format validation result as human-readable summary"""
        lines = []
        
        emoji = result['grade_emoji']
        grade = result['grade']
        score = result['composite_score']
        status = result['status'].upper()
        
        lines.append(f"{emoji} GRADE {grade} | Score: {score:.1f}/100 | Status: {status}")
        lines.append("")
        lines.append(f"Quality: {result['quality']}")
        lines.append(f"Tradeable: {'YES ✓' if result['is_tradeable'] else 'NO ✗'}")
        lines.append("")
        
        if result['status'] == 'rejected':
            lines.append("REJECTION REASONS:")
            for reason in result['rejection_reasons']:
                lines.append(f"  • {reason}")
            
            if result['detailed_failures']:
                lines.append("")
                lines.append("IMPROVEMENT NEEDED:")
                for failure in result['detailed_failures']:
                    lines.append(f"  • {failure['filter']}: {failure['improvement_needed']}")
        
        lines.append("")
        lines.append(f"Recommendation: {result['recommendation']}")
        
        return "\n".join(lines)


class Phase2Pipeline:
    """
    Phase 2 pipeline integration enforcer.
    
    Ensures all pipelines follow:
    Strategy → Backtest → Phase 2 Filters → Walk-forward → Monte Carlo → Final Selection
    """
    
    @staticmethod
    def validate_pipeline_stage(
        stage_name: str,
        strategy: Dict[str, Any],
        allow_grades: list = ['A', 'B', 'C']
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate strategy at pipeline stage.
        
        Args:
            stage_name: Pipeline stage name (e.g., "backtest", "bot_generation")
            strategy: Strategy data
            allow_grades: List of allowed grades for this stage
        
        Returns:
            (passes, validation_result)
        """
        logger.info(f"Phase 2 validation at stage: {stage_name}")
        
        # Run validation
        is_valid, result = Phase2Validator.validate_strategy(strategy)
        
        # Check grade allowance
        if result['grade'] not in allow_grades:
            is_valid = False
            result['status'] = 'rejected'
            result['rejection_reasons'].append(
                f"Grade {result['grade']} not allowed at stage '{stage_name}'. "
                f"Allowed grades: {', '.join(allow_grades)}"
            )
        
        # Log result
        if is_valid:
            logger.info(
                f"✓ Stage '{stage_name}' - Strategy APPROVED "
                f"(Grade {result['grade']}, Score {result['composite_score']:.1f})"
            )
        else:
            logger.warning(
                f"✗ Stage '{stage_name}' - Strategy REJECTED "
                f"(Grade {result['grade']}, Reasons: {', '.join(result['rejection_reasons'][:2])})"
            )
        
        return is_valid, result
    
    @staticmethod
    def enforce_bot_generation_gate(strategy: Dict[str, Any]) -> Tuple[bool, str, Dict]:
        """
        Final gate before bot generation.
        
        ONLY Grades A, B, C are allowed.
        Grades D and F are BLOCKED.
        
        Returns:
            (allowed, message, validation_result)
        """
        is_valid, result = Phase2Pipeline.validate_pipeline_stage(
            stage_name="bot_generation",
            strategy=strategy,
            allow_grades=['A', 'B', 'C']
        )
        
        if not is_valid:
            grade = result['grade']
            
            if grade in ['D', 'F']:
                message = (
                    f"🔴 BOT GENERATION BLOCKED - Grade {grade} strategies are NOT tradeable. "
                    f"Only grades A, B, C are approved for live trading."
                )
            else:
                message = f"🔴 BOT GENERATION BLOCKED - {', '.join(result['rejection_reasons'])}"
        else:
            grade = result['grade']
            emoji = result['grade_emoji']
            message = (
                f"{emoji} BOT GENERATION APPROVED - Grade {grade} strategy validated "
                f"(Score: {result['composite_score']:.1f}/100)"
            )
        
        return is_valid, message, result


def add_phase2_fields_to_strategy(strategy: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add Phase 2 validation fields to strategy document.
    
    Use this to enrich strategy data with Phase 2 validation results.
    """
    is_valid, validation = Phase2Validator.validate_strategy(strategy)
    
    # Add phase2 field
    strategy['phase2'] = validation
    
    # Also add top-level fields for easy querying
    strategy['grade'] = validation['grade']
    strategy['composite_score'] = validation['composite_score']
    strategy['is_tradeable'] = validation['is_tradeable']
    strategy['validation_status'] = validation['status']
    
    return strategy


# Convenience functions for API integration

def validate_and_format_response(strategy: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate strategy and return API-friendly response.
    
    Use this in API endpoints to ensure consistent Phase 2 response format.
    """
    is_valid, validation = Phase2Validator.validate_strategy(strategy)
    
    return {
        "strategy": strategy,
        "validation": validation,
        "grade": validation['grade'],
        "grade_emoji": validation['grade_emoji'],
        "score": validation['composite_score'],
        "is_tradeable": validation['is_tradeable'],
        "rejection_reason": (
            validation['rejection_reasons'][0] if validation['rejection_reasons'] else None
        ),
        "recommendation": validation['recommendation']
    }


def check_bot_generation_eligibility(strategy: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if strategy can generate bot.
    
    Returns API-friendly eligibility check result.
    """
    allowed, message, validation = Phase2Pipeline.enforce_bot_generation_gate(strategy)
    
    return {
        "eligible": allowed,
        "message": message,
        "grade": validation['grade'],
        "grade_emoji": validation['grade_emoji'],
        "validation": validation
    }
