"""
Quality Gates System
Phase 7+: Comprehensive Validation Gate Enforcement
"""

from typing import List, Optional, Dict
import logging

from multi_ai_models import QualityGate, QualityGatesResult

logger = logging.getLogger(__name__)


class QualityGatesEvaluator:
    """
    Evaluates all quality gates for strategy deployment
    
    A strategy is deployable ONLY if ALL gates pass:
    - Compilation Errors = 0
    - Warnings ≤ threshold (default 1)
    - Compliance Score ≥ 70
    - Backtest Score ≥ 70
    - Walk-Forward Score ≥ 70 (if available)
    - Monte Carlo Score ≥ 70 (if available)
    """
    
    def __init__(
        self,
        warning_threshold: int = 1,
        score_threshold: float = 70.0
    ):
        self.warning_threshold = warning_threshold
        self.score_threshold = score_threshold
    
    def evaluate_all_gates(
        self,
        compilation_errors: int,
        compilation_warnings: int,
        compliance_score: Optional[float] = None,
        backtest_score: Optional[float] = None,
        walkforward_score: Optional[float] = None,
        montecarlo_score: Optional[float] = None
    ) -> QualityGatesResult:
        """
        Evaluate all quality gates
        
        Returns QualityGatesResult with pass/fail status for each gate
        """
        gates: List[QualityGate] = []
        
        # Gate 1: Compilation Errors
        errors_gate = QualityGate(
            name="Compilation Errors",
            passed=compilation_errors == 0,
            score=float(compilation_errors),
            threshold=0.0,
            message=f"Compilation errors: {compilation_errors}" if compilation_errors > 0 
                   else "✓ No compilation errors"
        )
        gates.append(errors_gate)
        
        # Gate 2: Compilation Warnings
        warnings_gate = QualityGate(
            name="Compilation Warnings",
            passed=compilation_warnings <= self.warning_threshold,
            score=float(compilation_warnings),
            threshold=float(self.warning_threshold),
            message=f"Warnings: {compilation_warnings} (threshold: {self.warning_threshold})"
                   if compilation_warnings > self.warning_threshold
                   else f"✓ Warnings within threshold: {compilation_warnings}/{self.warning_threshold}"
        )
        gates.append(warnings_gate)
        
        # Gate 3: Compliance Score
        if compliance_score is not None:
            compliance_gate = QualityGate(
                name="Prop Firm Compliance",
                passed=compliance_score >= self.score_threshold,
                score=compliance_score,
                threshold=self.score_threshold,
                message=f"Compliance score: {compliance_score:.1f} (threshold: {self.score_threshold})"
                       if compliance_score < self.score_threshold
                       else f"✓ Compliance passed: {compliance_score:.1f}/100"
            )
            gates.append(compliance_gate)
        
        # Gate 4: Backtest Score
        if backtest_score is not None:
            backtest_gate = QualityGate(
                name="Backtest Performance",
                passed=backtest_score >= self.score_threshold,
                score=backtest_score,
                threshold=self.score_threshold,
                message=f"Backtest score: {backtest_score:.1f} (threshold: {self.score_threshold})"
                       if backtest_score < self.score_threshold
                       else f"✓ Backtest passed: {backtest_score:.1f}/100"
            )
            gates.append(backtest_gate)
        
        # Gate 5: Walk-Forward Score (Optional)
        if walkforward_score is not None:
            walkforward_gate = QualityGate(
                name="Walk-Forward Stability",
                passed=walkforward_score >= self.score_threshold,
                score=walkforward_score,
                threshold=self.score_threshold,
                message=f"Walk-forward score: {walkforward_score:.1f} (threshold: {self.score_threshold})"
                       if walkforward_score < self.score_threshold
                       else f"✓ Walk-forward passed: {walkforward_score:.1f}/100"
            )
            gates.append(walkforward_gate)
        
        # Gate 6: Monte Carlo Score (Optional)
        if montecarlo_score is not None:
            montecarlo_gate = QualityGate(
                name="Monte Carlo Robustness",
                passed=montecarlo_score >= self.score_threshold,
                score=montecarlo_score,
                threshold=self.score_threshold,
                message=f"Monte Carlo score: {montecarlo_score:.1f} (threshold: {self.score_threshold})"
                       if montecarlo_score < self.score_threshold
                       else f"✓ Monte Carlo passed: {montecarlo_score:.1f}/100"
            )
            gates.append(montecarlo_gate)
        
        # Overall evaluation
        all_passed = all(gate.passed for gate in gates)
        failed_gates = [gate.name for gate in gates if not gate.passed]
        
        # Generate summary
        if all_passed:
            summary = f"✅ ALL QUALITY GATES PASSED - Strategy is DEPLOYABLE"
            is_deployable = True
        else:
            failed_count = len(failed_gates)
            summary = f"❌ {failed_count} QUALITY GATE(S) FAILED - Strategy is NOT DEPLOYABLE"
            is_deployable = False
        
        logger.info(f"Quality Gates Evaluation: {summary}")
        for gate in gates:
            status = "✓ PASS" if gate.passed else "✗ FAIL"
            logger.info(f"  [{status}] {gate.name}: {gate.message}")
        
        return QualityGatesResult(
            all_passed=all_passed,
            gates=gates,
            is_deployable=is_deployable,
            summary=summary,
            failed_gates=failed_gates
        )
    
    def get_deployment_status(self, result: QualityGatesResult) -> Dict:
        """Get human-readable deployment status"""
        
        status = {
            "is_deployable": result.is_deployable,
            "status": "DEPLOYABLE" if result.is_deployable else "NOT DEPLOYABLE",
            "summary": result.summary,
            "gates_passed": len([g for g in result.gates if g.passed]),
            "gates_total": len(result.gates),
            "gates_failed": len(result.failed_gates),
            "failed_gate_names": result.failed_gates
        }
        
        # Detailed gate results
        status["gate_results"] = [
            {
                "name": gate.name,
                "passed": gate.passed,
                "score": gate.score,
                "threshold": gate.threshold,
                "message": gate.message
            }
            for gate in result.gates
        ]
        
        # Recommendations
        recommendations = []
        
        for gate in result.gates:
            if not gate.passed:
                if gate.name == "Compilation Errors":
                    recommendations.append("Fix all compilation errors before proceeding")
                elif gate.name == "Compilation Warnings":
                    recommendations.append("Optimize code to reduce warnings")
                elif gate.name == "Prop Firm Compliance":
                    recommendations.append("Add missing risk management safeguards")
                elif gate.name == "Backtest Performance":
                    recommendations.append("Improve strategy parameters or logic")
                elif gate.name == "Walk-Forward Stability":
                    recommendations.append("Strategy may be overfitted - review parameters")
                elif gate.name == "Monte Carlo Robustness":
                    recommendations.append("Strategy has high risk variance - improve stability")
        
        status["recommendations"] = recommendations
        
        return status


class ValidationPipeline:
    """Complete validation pipeline with all stages"""
    
    def __init__(self, gates_evaluator: QualityGatesEvaluator):
        self.gates_evaluator = gates_evaluator
        self.stages_completed = []
    
    def mark_stage_complete(self, stage: str, passed: bool, details: str = ""):
        """Mark a validation stage as complete"""
        self.stages_completed.append({
            "stage": stage,
            "passed": passed,
            "details": details,
            "timestamp": str(datetime.now())
        })
        logger.info(f"Stage complete: {stage} - {'PASSED' if passed else 'FAILED'}")
    
    def get_pipeline_status(self) -> Dict:
        """Get current pipeline status"""
        return {
            "stages_completed": len(self.stages_completed),
            "stages": self.stages_completed,
            "all_stages_passed": all(s["passed"] for s in self.stages_completed)
        }


# Factory functions
def create_quality_gates_evaluator(
    warning_threshold: int = 1,
    score_threshold: float = 70.0
) -> QualityGatesEvaluator:
    """Create quality gates evaluator instance"""
    return QualityGatesEvaluator(warning_threshold, score_threshold)


def create_validation_pipeline(
    gates_evaluator: Optional[QualityGatesEvaluator] = None
) -> ValidationPipeline:
    """Create validation pipeline instance"""
    if gates_evaluator is None:
        gates_evaluator = create_quality_gates_evaluator()
    return ValidationPipeline(gates_evaluator)


# Import at bottom to avoid circular dependency
from datetime import datetime
