"""
Bot Validation API Router
Phase 8: Bot Testing & Validation System

Endpoints:
- POST /api/bot/validate - Validate bot code
- POST /api/bot/test - Run sandbox backtest
- POST /api/bot/inject-safety - Inject safety code
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from bot_generation import (
    BotValidationEngine,
    ValidationResult,
    SafetyInjector,
    SafetyConfig,
    InjectionResult,
    create_validation_engine,
    create_safety_injector
)

# Phase 2 Integration
from phase2_integration import (
    Phase2Validator,
    Phase2Pipeline,
    check_bot_generation_eligibility,
    validate_and_format_response
)

logger = logging.getLogger(__name__)

# Create router with /api prefix
router = APIRouter(prefix="/api/bot")

# Global database reference (set during initialization)
_db = None


def init_bot_validation_router(db):
    """Initialize router with database connection"""
    global _db
    _db = db
    logger.info("Bot validation router initialized")


# Request/Response Models
class BotValidateRequest(BaseModel):
    """Request to validate bot code"""
    code: str = Field(..., description="C# bot code to validate")
    session_id: Optional[str] = None
    prop_firm: str = Field(default="none", description="Prop firm profile for validation")
    min_backtest_score: float = Field(default=50.0, description="Minimum backtest score to pass")
    min_risk_score: float = Field(default=60.0, description="Minimum risk score to pass")


class BotTestRequest(BaseModel):
    """Request to run sandbox backtest"""
    code: str = Field(..., description="C# bot code to test")
    session_id: Optional[str] = None
    symbol: str = Field(default="EURUSD", description="Trading symbol")
    timeframe: str = Field(default="H1", description="Timeframe for testing")
    duration_days: int = Field(default=30, description="Test duration in days")
    initial_balance: float = Field(default=10000.0, description="Starting balance")


class SafetyInjectRequest(BaseModel):
    """Request to inject safety code"""
    code: str = Field(..., description="C# bot code to enhance")
    prop_firm: str = Field(default="none", description="Prop firm profile")
    max_daily_loss_percent: float = Field(default=5.0)
    max_drawdown_percent: float = Field(default=10.0)
    max_open_positions: int = Field(default=10)
    max_risk_per_trade_percent: float = Field(default=2.0)
    default_stop_loss_pips: int = Field(default=20)
    max_spread_pips: float = Field(default=3.0)
    trading_start_hour: int = Field(default=8)
    trading_end_hour: int = Field(default=20)
    # API Logging Configuration
    enable_api_logging: bool = Field(default=True, description="Enable real-time trade logging")
    api_base_url: str = Field(default="", description="API base URL for logging")
    bot_id: str = Field(default="", description="Unique bot identifier")
    bot_name: str = Field(default="PropBot", description="Human readable name")
    strategy_type: str = Field(default="EMA Crossover", description="Strategy type")
    execution_mode: str = Field(default="forward_test", description="backtest, forward_test, or live")
    max_trades_per_day: int = Field(default=5)


class ValidationResponse(BaseModel):
    """Validation response with full results"""
    success: bool
    validation_id: str
    is_deployable: bool
    overall_status: str
    
    compilation: Dict[str, Any]
    backtest: Dict[str, Any]
    risk_safety: Dict[str, Any]
    
    summary: str
    recommendations: List[str]
    
    total_checks: int
    passed_checks: int
    failed_checks: int


class SafetyInjectResponse(BaseModel):
    """Safety injection response"""
    success: bool
    injection_id: str
    modified_code: str
    injections_applied: List[str]
    injections_skipped: List[str]
    message: str


# API Endpoints
@router.post("/validate", response_model=ValidationResponse)
async def validate_bot(request: BotValidateRequest):
    """
    Validate bot code before allowing download
    
    Runs three validation stages:
    1. Compilation - C# syntax and API checks
    2. Backtest - Sandbox performance simulation
    3. Risk Safety - Risk management feature checks
    
    Returns pass/fail for each stage with recommendations.
    """
    try:
        logger.info(f"Validating bot code (prop_firm={request.prop_firm})")
        
        # Create validation engine
        engine = create_validation_engine(
            min_backtest_score=request.min_backtest_score,
            min_risk_score=request.min_risk_score,
            prop_firm=request.prop_firm
        )
        
        # Run validation
        result = engine.validate_bot(request.code, request.session_id)
        
        # Save to database if available
        if _db is not None:
            result_doc = result.model_dump()
            result_doc['timestamp'] = result_doc['timestamp'].isoformat()
            await _db.bot_validations.insert_one(result_doc)
        
        # Build response
        return ValidationResponse(
            success=True,
            validation_id=result.id,
            is_deployable=result.is_deployable,
            overall_status=result.overall_status.value,
            compilation={
                "status": result.compilation.status.value,
                "is_valid": result.compilation.is_valid,
                "error_count": result.compilation.error_count,
                "warning_count": result.compilation.warning_count,
                "errors": result.compilation.errors[:5],  # Limit to first 5
                "warnings": result.compilation.warnings[:5],
                "message": result.compilation.message
            },
            backtest={
                "status": result.backtest.status.value,
                "is_valid": result.backtest.is_valid,
                "trades_executed": result.backtest.trades_executed,
                "win_rate": round(result.backtest.win_rate, 2),
                "profit_factor": round(result.backtest.profit_factor, 2),
                "max_drawdown_percent": round(result.backtest.max_drawdown_percent, 2),
                "strategy_score": round(result.backtest.strategy_score, 1),
                "issues": result.backtest.issues[:5],
                "message": result.backtest.message
            },
            risk_safety={
                "status": result.risk_safety.status.value,
                "is_valid": result.risk_safety.is_valid,
                "score": round(result.risk_safety.score, 1),
                "has_stop_loss": result.risk_safety.has_stop_loss,
                "has_take_profit": result.risk_safety.has_take_profit,
                "has_position_limit": result.risk_safety.has_position_limit,
                "has_daily_loss_limit": result.risk_safety.has_daily_loss_limit,
                "has_drawdown_protection": result.risk_safety.has_drawdown_protection,
                "has_risk_per_trade": result.risk_safety.has_risk_per_trade,
                "violations": result.risk_safety.violations[:5],
                "message": result.risk_safety.message
            },
            summary=result.summary,
            recommendations=result.recommendations,
            total_checks=result.total_checks,
            passed_checks=result.passed_checks,
            failed_checks=result.failed_checks
        )
        
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/test")
async def test_bot(request: BotTestRequest):
    """
    Run sandbox backtest on bot code
    
    Performs a quick simulation to estimate bot performance
    without actual market data execution.
    """
    try:
        logger.info(f"Running sandbox test for {request.symbol} {request.timeframe}")
        
        # Create validation engine (focused on backtest)
        engine = create_validation_engine()
        
        # Run full validation to get backtest results
        result = engine.validate_bot(request.code, request.session_id)
        
        # Return backtest-focused response
        return {
            "success": True,
            "test_id": result.id,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "duration_days": request.duration_days,
            "initial_balance": request.initial_balance,
            "results": {
                "compilation_passed": result.compilation.is_valid,
                "backtest_passed": result.backtest.is_valid,
                "trades_executed": result.backtest.trades_executed,
                "win_rate": round(result.backtest.win_rate, 2),
                "profit_factor": round(result.backtest.profit_factor, 2),
                "max_drawdown_percent": round(result.backtest.max_drawdown_percent, 2),
                "net_profit": round(result.backtest.net_profit, 2),
                "sharpe_ratio": round(result.backtest.sharpe_ratio, 2),
                "strategy_score": round(result.backtest.strategy_score, 1)
            },
            "issues": result.backtest.issues,
            "message": result.backtest.message
        }
        
    except Exception as e:
        logger.error(f"Test error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


@router.post("/inject-safety", response_model=SafetyInjectResponse)
async def inject_safety_code(request: SafetyInjectRequest):
    """
    Inject safety features into bot code
    
    Automatically adds:
    - Daily loss limit monitoring
    - Max drawdown protection
    - Position limit enforcement
    - Risk per trade calculation
    - Spread filter
    - Session filter
    """
    try:
        logger.info(f"Injecting safety code (prop_firm={request.prop_firm})")
        
        # Create config
        config = SafetyConfig(
            max_daily_loss_percent=request.max_daily_loss_percent,
            max_drawdown_percent=request.max_drawdown_percent,
            max_open_positions=request.max_open_positions,
            max_risk_per_trade_percent=request.max_risk_per_trade_percent,
            default_stop_loss_pips=request.default_stop_loss_pips,
            max_spread_pips=request.max_spread_pips,
            trading_start_hour=request.trading_start_hour,
            trading_end_hour=request.trading_end_hour,
            prop_firm=request.prop_firm,
            enable_api_logging=request.enable_api_logging,
            api_base_url=request.api_base_url,
            bot_id=request.bot_id,
            bot_name=request.bot_name,
            strategy_type=request.strategy_type,
            execution_mode=request.execution_mode,
            max_trades_per_day=request.max_trades_per_day
        )
        
        # Create injector
        injector = create_safety_injector(config)
        
        # Inject safety code
        result = injector.inject_safety_code(request.code)
        
        # Save to database if available
        if _db is not None:
            result_doc = result.model_dump()
            result_doc['timestamp'] = result_doc['timestamp'].isoformat()
            if result_doc.get('config_used'):
                result_doc['config_used'] = result_doc['config_used']
            await _db.safety_injections.insert_one(result_doc)
        
        return SafetyInjectResponse(
            success=result.success,
            injection_id=result.id,
            modified_code=result.modified_code if result.success else result.original_code,
            injections_applied=result.injections_applied,
            injections_skipped=result.injections_skipped,
            message=result.message
        )
        
    except Exception as e:
        logger.error(f"Safety injection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Safety injection failed: {str(e)}")


@router.get("/validation/{validation_id}")
async def get_validation_result(validation_id: str):
    """Get a previous validation result by ID"""
    try:
        if _db is None:
            raise HTTPException(status_code=500, detail="Database not initialized")
        
        result = await _db.bot_validations.find_one({"id": validation_id}, {"_id": 0})
        
        if not result:
            raise HTTPException(status_code=404, detail="Validation not found")
        
        return {
            "success": True,
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get validation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get validation: {str(e)}")


@router.get("/validations/session/{session_id}")
async def list_session_validations(session_id: str):
    """Get all validations for a session"""
    try:
        if _db is None:
            raise HTTPException(status_code=500, detail="Database not initialized")
        
        validations = await _db.bot_validations.find(
            {"session_id": session_id},
            {"_id": 0}
        ).sort("timestamp", -1).to_list(50)
        
        return {
            "success": True,
            "validations": validations,
            "count": len(validations)
        }
        
    except Exception as e:
        logger.error(f"List validations error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list validations: {str(e)}")



# ========== PHASE 2 QUALITY ENGINE ENDPOINTS (NEW) ==========

class Phase2ValidationRequest(BaseModel):
    """Request for Phase 2 strategy validation"""
    strategy_name: str
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    total_trades: int
    stability_score: float = 0.0
    win_rate: float = 0.0
    net_profit: float = 0.0
    composite_score: Optional[float] = None


class Phase2ValidationResponse(BaseModel):
    """Phase 2 validation response"""
    success: bool
    status: str  # "accepted" | "rejected"
    grade: str  # A-F
    grade_emoji: str
    grade_description: str
    composite_score: float
    is_tradeable: bool
    passes_all_filters: bool
    rejection_reasons: List[str]
    detailed_failures: List[Dict[str, Any]]
    recommendation: str
    quality: str
    metrics: Dict[str, Any]


class BotGenerationEligibilityRequest(BaseModel):
    """Request to check bot generation eligibility"""
    strategy_name: str
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    total_trades: int
    stability_score: float = 0.0
    win_rate: float = 0.0


class BotGenerationEligibilityResponse(BaseModel):
    """Bot generation eligibility response"""
    eligible: bool
    message: str
    grade: str
    grade_emoji: str
    validation: Dict[str, Any]


@router.post("/phase2/validate", response_model=Phase2ValidationResponse)
async def validate_strategy_phase2(request: Phase2ValidationRequest):
    """
    Phase 2: Validate strategy against strict quality standards.
    
    Returns comprehensive validation with:
    - A-F letter grade
    - Composite score
    - Pass/fail status
    - Detailed rejection reasons (if rejected)
    - Trading recommendation
    
    New in Phase 2:
    - Profit Factor ≥ 1.5 (was 1.2)
    - Max Drawdown ≤ 15% (was 20%)
    - Sharpe Ratio ≥ 1.0 (new)
    - Minimum Trades ≥ 100 (was 50)
    - Stability ≥ 70% (was 60%)
    """
    try:
        # Convert request to strategy dict
        strategy = {
            'strategy_name': request.strategy_name,
            'profit_factor': request.profit_factor,
            'max_drawdown_pct': request.max_drawdown_pct,
            'sharpe_ratio': request.sharpe_ratio,
            'total_trades': request.total_trades,
            'stability_score': request.stability_score,
            'win_rate': request.win_rate,
            'net_profit': request.net_profit,
            'composite_score': request.composite_score or 0
        }
        
        # Run Phase 2 validation
        is_valid, validation = Phase2Validator.validate_strategy(strategy)
        
        logger.info(
            f"Phase 2 validation - {request.strategy_name}: "
            f"Grade {validation['grade']}, Score {validation['composite_score']:.1f}, "
            f"Status: {validation['status']}"
        )
        
        return Phase2ValidationResponse(
            success=True,
            status=validation['status'],
            grade=validation['grade'],
            grade_emoji=validation['grade_emoji'],
            grade_description=validation['grade_description'],
            composite_score=validation['composite_score'],
            is_tradeable=validation['is_tradeable'],
            passes_all_filters=validation['passes_all_filters'],
            rejection_reasons=validation['rejection_reasons'],
            detailed_failures=validation['detailed_failures'],
            recommendation=validation['recommendation'],
            quality=validation['quality'],
            metrics=validation['metrics']
        )
        
    except Exception as e:
        logger.error(f"Phase 2 validation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/phase2/check-eligibility", response_model=BotGenerationEligibilityResponse)
async def check_bot_generation_eligibility_endpoint(request: BotGenerationEligibilityRequest):
    """
    Phase 2: Check if strategy is eligible for bot generation.
    
    CRITICAL GATE: Only grades A, B, C are allowed.
    Grades D and F are BLOCKED from bot generation.
    
    Returns:
    - eligible: True/False
    - message: Human-readable reason
    - grade: Strategy grade
    - validation: Full validation details
    """
    try:
        # Convert request to strategy dict
        strategy = {
            'strategy_name': request.strategy_name,
            'profit_factor': request.profit_factor,
            'max_drawdown_pct': request.max_drawdown_pct,
            'sharpe_ratio': request.sharpe_ratio,
            'total_trades': request.total_trades,
            'stability_score': request.stability_score,
            'win_rate': request.win_rate
        }
        
        # Check eligibility
        result = check_bot_generation_eligibility(strategy)
        
        logger.info(
            f"Bot generation eligibility - {request.strategy_name}: "
            f"{'APPROVED' if result['eligible'] else 'BLOCKED'} "
            f"(Grade {result['grade']})"
        )
        
        return BotGenerationEligibilityResponse(**result)
        
    except Exception as e:
        logger.error(f"Eligibility check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Check failed: {str(e)}")


@router.get("/phase2/config")
async def get_phase2_config():
    """
    Get Phase 2 configuration and filter rules.
    
    Returns current filter thresholds and grading criteria.
    """
    try:
        from scoring_engine import QualityFilters
        
        filters = QualityFilters._get_config()
        
        return {
            "success": True,
            "version": "2.0.0",
            "filters": {
                "min_profit_factor": filters.min_profit_factor,
                "max_drawdown_pct": filters.max_drawdown_pct,
                "min_sharpe_ratio": filters.min_sharpe_ratio,
                "min_trades": filters.min_trades,
                "min_stability_pct": filters.min_stability_pct,
                "min_win_rate": filters.min_win_rate
            },
            "grading": {
                "A": "90-100 (Excellent - Production ready)",
                "B": "80-89 (Good - Solid performance)",
                "C": "70-79 (Acceptable - Minimum requirements)",
                "D": "60-69 (Weak - Paper trade only)",
                "F": "<60 (Fail - Do not trade)"
            },
            "tradeable_grades": ["A", "B", "C"],
            "blocked_grades": ["D", "F"],
            "message": "Phase 2 enforces strict quality standards. Only 30-45% of strategies are expected to pass."
        }
        
    except Exception as e:
        logger.error(f"Config error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
