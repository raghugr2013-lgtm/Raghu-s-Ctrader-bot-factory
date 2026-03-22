"""
Advanced Validation API Router
Phase 2-3: Professional Quant-Grade Validation System

Endpoints:
- POST /api/advanced/bootstrap - Bootstrap trade resampling analysis
- POST /api/advanced/sensitivity - Parameter sensitivity testing
- POST /api/advanced/risk-of-ruin - Risk of ruin calculation
- POST /api/advanced/slippage - Execution reality simulation
- POST /api/advanced/full-validation - Complete advanced validation suite
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from advanced_validation import (
    BootstrapEngine, BootstrapConfig, BootstrapResult, create_bootstrap_engine,
    SensitivityAnalyzer, SensitivityConfig, SensitivityResult, create_sensitivity_analyzer,
    RiskOfRuinCalculator, RiskOfRuinConfig, RiskOfRuinResult, create_risk_of_ruin_calculator,
    SlippageSimulator, SlippageConfig, SlippageResult, create_slippage_simulator
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/advanced")

# Global database reference
_db = None


def init_advanced_validation_router(db):
    """Initialize router with database connection"""
    global _db
    _db = db
    logger.info("Advanced validation router initialized")


# Request Models
class BootstrapRequest(BaseModel):
    """Request for bootstrap analysis"""
    session_id: Optional[str] = None
    strategy_name: Optional[str] = None
    backtest_id: Optional[str] = None  # Get trades from existing backtest
    trades: Optional[List[Dict]] = None  # Or provide trades directly
    num_simulations: int = Field(default=1000, ge=100, le=10000)
    initial_balance: float = Field(default=10000.0)
    ruin_threshold_percent: float = Field(default=10.0)
    confidence_level: float = Field(default=0.95)
    use_block_bootstrap: bool = Field(default=True)


class SensitivityRequest(BaseModel):
    """Request for sensitivity analysis"""
    session_id: Optional[str] = None
    strategy_name: Optional[str] = None
    backtest_id: Optional[str] = None
    trades: Optional[List[Dict]] = None
    parameters: Dict[str, float] = Field(
        default={"fast_ma": 10, "slow_ma": 20, "atr_period": 14, "risk_percent": 2.0}
    )
    variation_percent: float = Field(default=20.0)
    variation_steps: int = Field(default=5)


class RiskOfRuinRequest(BaseModel):
    """Request for risk of ruin calculation"""
    session_id: Optional[str] = None
    strategy_name: Optional[str] = None
    backtest_id: Optional[str] = None
    trades: Optional[List[Dict]] = None
    initial_balance: float = Field(default=10000.0)
    ruin_threshold_percent: float = Field(default=50.0)
    risk_per_trade_percent: float = Field(default=2.0)
    num_simulations: int = Field(default=10000)
    trade_horizon: int = Field(default=500)


class SlippageRequest(BaseModel):
    """Request for slippage simulation"""
    session_id: Optional[str] = None
    strategy_name: Optional[str] = None
    backtest_id: Optional[str] = None
    trades: Optional[List[Dict]] = None
    base_spread_pips: float = Field(default=1.0)
    avg_slippage_pips: float = Field(default=0.3)
    avg_latency_ms: float = Field(default=50.0)
    initial_balance: float = Field(default=10000.0)


class FullValidationRequest(BaseModel):
    """Request for complete advanced validation suite"""
    session_id: Optional[str] = None
    strategy_name: Optional[str] = None
    backtest_id: Optional[str] = None
    trades: Optional[List[Dict]] = None
    parameters: Optional[Dict[str, float]] = None
    initial_balance: float = Field(default=10000.0)
    risk_per_trade_percent: float = Field(default=2.0)


# API Endpoints
@router.post("/bootstrap")
async def run_bootstrap_analysis(request: BootstrapRequest):
    """
    Run bootstrap trade resampling analysis
    
    Resamples trades with replacement to estimate:
    - Survival probability
    - Confidence intervals for returns
    - Strategy consistency
    """
    try:
        # Get trades
        trades = await _get_trades(request.backtest_id, request.trades)
        if not trades:
            raise HTTPException(status_code=400, detail="No trades provided")
        
        # Create config
        config = BootstrapConfig(
            num_simulations=request.num_simulations,
            initial_balance=request.initial_balance,
            ruin_threshold_percent=request.ruin_threshold_percent,
            confidence_level=request.confidence_level,
            use_block_bootstrap=request.use_block_bootstrap
        )
        
        # Run analysis
        engine = create_bootstrap_engine(config, trades)
        result = engine.run()
        result.session_id = request.session_id
        result.strategy_name = request.strategy_name
        
        # Save to database
        if _db is not None:
            result_doc = result.model_dump()
            result_doc['created_at'] = result_doc['created_at'].isoformat()
            await _db.bootstrap_results.insert_one(result_doc)
        
        logger.info(f"Bootstrap analysis complete: {result.metrics.survival_rate:.1%} survival")
        
        return {
            "success": True,
            "bootstrap_id": result.id,
            "summary": {
                "simulations": result.total_simulations,
                "original_trades": result.original_trades,
                "survival_rate": round(result.metrics.survival_rate * 100, 1),
                "profit_probability": round(result.metrics.profit_probability * 100, 1),
                "mean_return_percent": round(result.metrics.mean_return_percent, 2),
                "return_ci_95": [
                    round(result.metrics.return_ci_lower, 2),
                    round(result.metrics.return_ci_upper, 2)
                ],
                "mean_max_drawdown": round(result.metrics.mean_max_drawdown, 2),
                "worst_case_drawdown": round(result.metrics.worst_case_drawdown, 2),
                "score": round(result.bootstrap_score.total_score, 1),
                "grade": result.bootstrap_score.grade,
                "is_robust": result.bootstrap_score.is_robust
            },
            "insights": {
                "strengths": result.bootstrap_score.strengths,
                "weaknesses": result.bootstrap_score.weaknesses,
                "recommendations": result.bootstrap_score.recommendations
            },
            "execution_time": round(result.execution_time_seconds, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bootstrap analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bootstrap analysis failed: {str(e)}")


@router.post("/sensitivity")
async def run_sensitivity_analysis(request: SensitivityRequest):
    """
    Run parameter sensitivity analysis
    
    Tests how strategy performance varies with parameter changes
    to identify robustness and potential overfitting.
    """
    try:
        # Get trades
        trades = await _get_trades(request.backtest_id, request.trades)
        
        # Create config
        config = SensitivityConfig(
            variation_percent=request.variation_percent,
            variation_steps=request.variation_steps
        )
        
        # Run analysis
        analyzer = create_sensitivity_analyzer(config, request.parameters)
        result = analyzer.run(trades)
        result.session_id = request.session_id
        result.strategy_name = request.strategy_name
        
        # Save to database
        if _db is not None:
            result_doc = result.model_dump()
            result_doc['created_at'] = result_doc['created_at'].isoformat()
            await _db.sensitivity_results.insert_one(result_doc)
        
        logger.info(f"Sensitivity analysis complete: {result.metrics.robustness_score:.1f} robustness")
        
        # Summarize parameter sensitivities
        param_summary = []
        for ps in result.parameter_sensitivities:
            param_summary.append({
                "name": ps.parameter_name,
                "original": ps.original_value,
                "optimal": round(ps.optimal_value, 4),
                "sensitivity_score": round(ps.sensitivity_score, 1),
                "is_sensitive": ps.is_sensitive,
                "is_overfitted": ps.is_overfitted
            })
        
        return {
            "success": True,
            "sensitivity_id": result.id,
            "summary": {
                "parameters_analyzed": result.parameters_analyzed,
                "combinations_tested": result.total_combinations_tested,
                "overall_sensitivity": round(result.metrics.overall_sensitivity, 1),
                "robustness_score": round(result.metrics.robustness_score, 1),
                "overfitting_risk": round(result.metrics.overfitting_risk, 1),
                "most_sensitive": result.metrics.most_sensitive_param,
                "least_sensitive": result.metrics.least_sensitive_param,
                "score": round(result.sensitivity_score.total_score, 1),
                "grade": result.sensitivity_score.grade,
                "is_robust": result.sensitivity_score.is_robust
            },
            "parameters": param_summary,
            "insights": {
                "strengths": result.sensitivity_score.strengths,
                "weaknesses": result.sensitivity_score.weaknesses,
                "recommendations": result.sensitivity_score.recommendations
            },
            "execution_time": round(result.execution_time_seconds, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sensitivity analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sensitivity analysis failed: {str(e)}")


@router.post("/risk-of-ruin")
async def run_risk_of_ruin(request: RiskOfRuinRequest):
    """
    Calculate risk of ruin probability
    
    Estimates probability of account ruin based on
    trading statistics and position sizing.
    """
    try:
        # Get trades
        trades = await _get_trades(request.backtest_id, request.trades)
        if not trades:
            raise HTTPException(status_code=400, detail="No trades provided")
        
        # Create config
        config = RiskOfRuinConfig(
            initial_balance=request.initial_balance,
            ruin_threshold_percent=request.ruin_threshold_percent,
            risk_per_trade_percent=request.risk_per_trade_percent,
            num_simulations=request.num_simulations,
            trade_horizon=request.trade_horizon
        )
        
        # Run analysis
        calculator = create_risk_of_ruin_calculator(config, trades)
        result = calculator.run()
        result.session_id = request.session_id
        result.strategy_name = request.strategy_name
        
        # Save to database
        if _db is not None:
            result_doc = result.model_dump()
            result_doc['created_at'] = result_doc['created_at'].isoformat()
            await _db.risk_of_ruin_results.insert_one(result_doc)
        
        logger.info(f"Risk of ruin complete: {result.metrics.ruin_probability:.1%} ruin probability")
        
        return {
            "success": True,
            "ror_id": result.id,
            "summary": {
                "ruin_probability": round(result.metrics.ruin_probability * 100, 2),
                "survival_probability": round(result.metrics.survival_probability * 100, 2),
                "theoretical_ruin_prob": round(result.metrics.theoretical_ruin_prob * 100, 2),
                "kelly_fraction": round(result.metrics.kelly_fraction * 100, 2),
                "expected_max_drawdown": round(result.metrics.expected_max_drawdown, 2),
                "drawdown_95_percentile": round(result.metrics.drawdown_95_percentile, 2),
                "observed_win_rate": round(result.metrics.observed_win_rate, 1),
                "observed_risk_reward": round(result.metrics.observed_risk_reward, 2),
                "score": round(result.risk_score.total_score, 1),
                "grade": result.risk_score.grade,
                "risk_level": result.risk_score.risk_level,
                "is_acceptable": result.risk_score.is_acceptable
            },
            "risk_curve": result.risk_vs_ruin_curve,
            "insights": {
                "strengths": result.risk_score.strengths,
                "weaknesses": result.risk_score.weaknesses,
                "recommendations": result.risk_score.recommendations
            },
            "execution_time": round(result.execution_time_seconds, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Risk of ruin error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Risk of ruin failed: {str(e)}")


@router.post("/slippage")
async def run_slippage_simulation(request: SlippageRequest):
    """
    Simulate execution reality (spread, slippage, latency)
    
    Estimates real-world profit after accounting for
    execution costs and market impact.
    """
    try:
        # Get trades
        trades = await _get_trades(request.backtest_id, request.trades)
        if not trades:
            raise HTTPException(status_code=400, detail="No trades provided")
        
        # Create config
        config = SlippageConfig(
            base_spread_pips=request.base_spread_pips,
            avg_slippage_pips=request.avg_slippage_pips,
            avg_latency_ms=request.avg_latency_ms,
            initial_balance=request.initial_balance
        )
        
        # Run simulation
        simulator = create_slippage_simulator(config, trades)
        result = simulator.run()
        result.session_id = request.session_id
        result.strategy_name = request.strategy_name
        
        # Save to database
        if _db is not None:
            result_doc = result.model_dump()
            result_doc['created_at'] = result_doc['created_at'].isoformat()
            await _db.slippage_results.insert_one(result_doc)
        
        logger.info(f"Slippage simulation complete: {result.metrics.profit_degradation_percent:.1f}% profit degradation")
        
        return {
            "success": True,
            "slippage_id": result.id,
            "summary": {
                "trades_simulated": result.total_trades_simulated,
                "gross_profit": round(result.metrics.gross_profit, 2),
                "net_profit": round(result.metrics.net_profit, 2),
                "profit_degradation_percent": round(result.metrics.profit_degradation_percent, 2),
                "avg_spread_pips": round(result.metrics.avg_spread_pips, 2),
                "avg_slippage_per_trade": round(result.metrics.avg_slippage_per_trade, 2),
                "avg_latency_ms": round(result.metrics.avg_latency_ms, 1),
                "ideal_profit_factor": round(result.metrics.ideal_profit_factor, 2),
                "realistic_profit_factor": round(result.metrics.realistic_profit_factor, 2),
                "ideal_win_rate": round(result.metrics.ideal_win_rate, 1),
                "realistic_win_rate": round(result.metrics.realistic_win_rate, 1),
                "score": round(result.slippage_score.total_score, 1),
                "grade": result.slippage_score.grade,
                "impact_level": result.slippage_score.impact_level,
                "is_viable": result.slippage_score.is_viable
            },
            "sensitivity": {
                "spread_curve": result.profit_vs_spread_curve,
                "slippage_curve": result.profit_vs_slippage_curve
            },
            "insights": {
                "strengths": result.slippage_score.strengths,
                "weaknesses": result.slippage_score.weaknesses,
                "recommendations": result.slippage_score.recommendations
            },
            "execution_time": round(result.execution_time_seconds, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Slippage simulation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Slippage simulation failed: {str(e)}")


@router.post("/full-validation")
async def run_full_validation(request: FullValidationRequest):
    """
    Run complete advanced validation suite
    
    Combines all validation methods:
    - Bootstrap analysis
    - Sensitivity testing
    - Risk of ruin
    - Slippage simulation
    
    Returns comprehensive strategy assessment.
    """
    try:
        # Get trades
        trades = await _get_trades(request.backtest_id, request.trades)
        if not trades:
            raise HTTPException(status_code=400, detail="No trades provided")
        
        results = {
            "bootstrap": None,
            "sensitivity": None,
            "risk_of_ruin": None,
            "slippage": None
        }
        scores = []
        
        # 1. Bootstrap Analysis
        try:
            bootstrap_config = BootstrapConfig(
                initial_balance=request.initial_balance,
                num_simulations=1000
            )
            bootstrap_engine = create_bootstrap_engine(bootstrap_config, trades)
            bootstrap_result = bootstrap_engine.run()
            results["bootstrap"] = {
                "survival_rate": round(bootstrap_result.metrics.survival_rate * 100, 1),
                "profit_probability": round(bootstrap_result.metrics.profit_probability * 100, 1),
                "score": round(bootstrap_result.bootstrap_score.total_score, 1),
                "grade": bootstrap_result.bootstrap_score.grade,
                "is_robust": bootstrap_result.bootstrap_score.is_robust
            }
            scores.append(bootstrap_result.bootstrap_score.total_score)
        except Exception as e:
            logger.error(f"Bootstrap failed: {str(e)}")
        
        # 2. Sensitivity Analysis
        if request.parameters:
            try:
                sensitivity_config = SensitivityConfig()
                analyzer = create_sensitivity_analyzer(sensitivity_config, request.parameters)
                sensitivity_result = analyzer.run(trades)
                results["sensitivity"] = {
                    "robustness_score": round(sensitivity_result.metrics.robustness_score, 1),
                    "overfitting_risk": round(sensitivity_result.metrics.overfitting_risk, 1),
                    "score": round(sensitivity_result.sensitivity_score.total_score, 1),
                    "grade": sensitivity_result.sensitivity_score.grade,
                    "is_robust": sensitivity_result.sensitivity_score.is_robust
                }
                scores.append(sensitivity_result.sensitivity_score.total_score)
            except Exception as e:
                logger.error(f"Sensitivity failed: {str(e)}")
        
        # 3. Risk of Ruin
        try:
            ror_config = RiskOfRuinConfig(
                initial_balance=request.initial_balance,
                risk_per_trade_percent=request.risk_per_trade_percent,
                num_simulations=5000
            )
            ror_calculator = create_risk_of_ruin_calculator(ror_config, trades)
            ror_result = ror_calculator.run()
            results["risk_of_ruin"] = {
                "ruin_probability": round(ror_result.metrics.ruin_probability * 100, 2),
                "survival_probability": round(ror_result.metrics.survival_probability * 100, 2),
                "kelly_fraction": round(ror_result.metrics.kelly_fraction * 100, 2),
                "score": round(ror_result.risk_score.total_score, 1),
                "grade": ror_result.risk_score.grade,
                "risk_level": ror_result.risk_score.risk_level,
                "is_acceptable": ror_result.risk_score.is_acceptable
            }
            scores.append(ror_result.risk_score.total_score)
        except Exception as e:
            logger.error(f"Risk of ruin failed: {str(e)}")
        
        # 4. Slippage Simulation
        try:
            slippage_config = SlippageConfig(initial_balance=request.initial_balance)
            simulator = create_slippage_simulator(slippage_config, trades)
            slippage_result = simulator.run()
            results["slippage"] = {
                "profit_degradation": round(slippage_result.metrics.profit_degradation_percent, 1),
                "realistic_pf": round(slippage_result.metrics.realistic_profit_factor, 2),
                "score": round(slippage_result.slippage_score.total_score, 1),
                "grade": slippage_result.slippage_score.grade,
                "impact_level": slippage_result.slippage_score.impact_level,
                "is_viable": slippage_result.slippage_score.is_viable
            }
            scores.append(slippage_result.slippage_score.total_score)
        except Exception as e:
            logger.error(f"Slippage failed: {str(e)}")
        
        # Calculate composite score
        composite_score = sum(scores) / len(scores) if scores else 0
        
        # Determine overall grade
        if composite_score >= 85:
            overall_grade = "A"
            verdict = "EXCELLENT - Strategy is highly robust and ready for live trading"
        elif composite_score >= 70:
            overall_grade = "B"
            verdict = "GOOD - Strategy shows solid robustness with minor concerns"
        elif composite_score >= 55:
            overall_grade = "C"
            verdict = "MODERATE - Strategy has some robustness issues to address"
        elif composite_score >= 40:
            overall_grade = "D"
            verdict = "POOR - Strategy has significant weaknesses"
        else:
            overall_grade = "F"
            verdict = "FAIL - Strategy is not suitable for live trading"
        
        # Determine if strategy is deployable
        is_deployable = (
            composite_score >= 55 and
            results.get("bootstrap", {}).get("is_robust", False) and
            results.get("risk_of_ruin", {}).get("is_acceptable", False) and
            results.get("slippage", {}).get("is_viable", False)
        )
        
        return {
            "success": True,
            "session_id": request.session_id,
            "strategy_name": request.strategy_name,
            "trades_analyzed": len(trades),
            "composite_score": round(composite_score, 1),
            "overall_grade": overall_grade,
            "verdict": verdict,
            "is_deployable": is_deployable,
            "results": results,
            "recommendations": _generate_recommendations(results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Full validation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Full validation failed: {str(e)}")


# Helper functions
async def _get_trades(backtest_id: Optional[str], trades: Optional[List[Dict]]) -> List[Dict]:
    """Get trades from backtest or provided list"""
    if trades:
        return trades
    
    if backtest_id and _db is not None:
        backtest = await _db.backtests.find_one({"id": backtest_id}, {"_id": 0})
        if backtest and "trades" in backtest:
            return backtest["trades"]
    
    return []


def _generate_recommendations(results: Dict) -> List[str]:
    """Generate recommendations based on validation results"""
    recommendations = []
    
    if results.get("bootstrap"):
        if not results["bootstrap"].get("is_robust"):
            recommendations.append("Bootstrap analysis shows inconsistency - review strategy logic")
        if results["bootstrap"].get("survival_rate", 0) < 80:
            recommendations.append("Low survival rate - reduce position sizing")
    
    if results.get("sensitivity"):
        if results["sensitivity"].get("overfitting_risk", 0) > 40:
            recommendations.append("High overfitting risk - widen parameter search range")
        if not results["sensitivity"].get("is_robust"):
            recommendations.append("Parameters are sensitive - use conservative values")
    
    if results.get("risk_of_ruin"):
        if not results["risk_of_ruin"].get("is_acceptable"):
            recommendations.append(f"Ruin risk too high - reduce risk per trade")
        kelly = results["risk_of_ruin"].get("kelly_fraction", 0)
        if kelly > 0:
            recommendations.append(f"Consider Kelly sizing: {kelly:.1f}% per trade (use half-Kelly)")
    
    if results.get("slippage"):
        if not results["slippage"].get("is_viable"):
            recommendations.append("Strategy may not survive execution costs - need higher edge")
        if results["slippage"].get("profit_degradation", 0) > 20:
            recommendations.append("High execution cost impact - target lower-spread instruments")
    
    if not recommendations:
        recommendations.append("Strategy passed all validation checks - suitable for live deployment")
    
    return recommendations


@router.get("/results/{result_type}/{result_id}")
async def get_validation_result(result_type: str, result_id: str):
    """Get a previous validation result by type and ID"""
    try:
        if _db is None:
            raise HTTPException(status_code=500, detail="Database not initialized")
        
        collection_map = {
            "bootstrap": "bootstrap_results",
            "sensitivity": "sensitivity_results",
            "risk-of-ruin": "risk_of_ruin_results",
            "slippage": "slippage_results"
        }
        
        collection = collection_map.get(result_type)
        if not collection:
            raise HTTPException(status_code=400, detail=f"Invalid result type: {result_type}")
        
        result = await _db[collection].find_one({"id": result_id}, {"_id": 0})
        
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        
        return {"success": True, "result": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get result error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get result: {str(e)}")
