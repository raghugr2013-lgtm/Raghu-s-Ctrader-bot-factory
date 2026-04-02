"""
Analyzer API Router - Phase 1, 2 & 3
POST /api/analyze-cbot - Parse and analyze C# cBot code
POST /api/refine-strategy - Apply rule-based improvements to strategy
POST /api/analyze-and-refine - Combined analyze + refine (with optional bot generation)
POST /api/generate-bot - Generate optimized C# cBot from improved strategy
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from .csharp_parser import CSharpBotParser
from .strategy_parser import StrategyParser
from .refinement_engine import StrategyRefinementEngine, create_refinement_engine
from .improved_bot_generator import ImprovedBotGenerator, create_bot_generator

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["analyzer"])


class AnalyzeCBotRequest(BaseModel):
    """Request model for cBot analysis"""
    code: str = Field(..., description="C# cBot code to analyze", min_length=10)


class AnalyzeCBotResponse(BaseModel):
    """Response model for cBot analysis"""
    success: bool
    parsed: Dict[str, Any]
    strategy: Dict[str, Any]
    message: str = ""


class RefineStrategyRequest(BaseModel):
    """Request model for strategy refinement"""
    parsed: Dict[str, Any] = Field(..., description="Parsed bot data from analyze-cbot")
    strategy: Dict[str, Any] = Field(..., description="Strategy data from analyze-cbot")


class RefineStrategyResponse(BaseModel):
    """Response model for strategy refinement"""
    success: bool
    original_strategy: Dict[str, Any]
    issues: List[Dict[str, Any]]
    improved_strategy: Dict[str, Any]
    changes_made: List[Dict[str, Any]]
    improvement_score: float
    summary: str


class AnalyzeAndRefineRequest(BaseModel):
    """Request for combined analyze + refine in one call"""
    code: str = Field(..., description="C# cBot code to analyze and refine", min_length=10)
    include_generated_bot: bool = Field(default=False, description="Generate optimized C# bot code")


class AnalyzeAndRefineResponse(BaseModel):
    """Response for combined analyze + refine"""
    success: bool
    parsed: Dict[str, Any]
    original_strategy: Dict[str, Any]
    improved_strategy: Dict[str, Any]
    issues: List[Dict[str, Any]]
    changes_made: List[Dict[str, Any]]
    improvement_score: float
    summary: str
    generated_bot: Optional[Dict[str, Any]] = None


class GenerateBotRequest(BaseModel):
    """Request for bot generation"""
    improved_strategy: Dict[str, Any] = Field(..., description="Improved strategy from refinement")
    parsed: Optional[Dict[str, Any]] = Field(None, description="Original parsed data (for preserving logic)")


class GenerateBotResponse(BaseModel):
    """Response for bot generation"""
    success: bool
    generated_bot_code: str
    bot_name: str
    class_name: str
    indicators_count: int
    filters_count: int
    has_risk_management: bool


@router.post("/analyze-cbot", response_model=AnalyzeCBotResponse)
async def analyze_cbot(request: AnalyzeCBotRequest):
    """
    Analyze C# cBot code and extract trading strategy
    
    Phase 1 Features:
    - Extract indicators used
    - Parse entry conditions
    - Parse exit logic
    - Extract risk management settings
    - Identify filters
    - Convert to structured strategy format
    
    Returns:
    - parsed: Raw extracted components from C# code
    - strategy: Structured strategy representation
    """
    try:
        # Validate input
        if not request.code or len(request.code.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Invalid code: Code is too short or empty"
            )
        
        # Check if it looks like C# code
        if 'class' not in request.code and 'Robot' not in request.code:
            raise HTTPException(
                status_code=400,
                detail="Invalid code: Does not appear to be a cTrader cBot (missing class or Robot)"
            )
        
        # Parse C# code
        csharp_parser = CSharpBotParser()
        parsed_bot = csharp_parser.parse(request.code)
        
        # Convert to strategy format
        strategy_parser = StrategyParser()
        strategy = strategy_parser.parse(parsed_bot)
        
        # Prepare response
        parsed_dict = parsed_bot.to_dict()
        strategy_dict = strategy.to_dict()
        
        # Generate summary message
        message = _generate_summary(parsed_bot, strategy)
        
        logger.info(f"Successfully analyzed cBot: {parsed_bot.bot_name}")
        
        return AnalyzeCBotResponse(
            success=True,
            parsed=parsed_dict,
            strategy=strategy_dict,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing cBot: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


def _generate_summary(parsed_bot, strategy) -> str:
    """Generate a human-readable summary of the analysis"""
    parts = [f"Analyzed '{parsed_bot.bot_name}'"]
    
    # Indicators
    if parsed_bot.indicators:
        parts.append(f"{len(parsed_bot.indicators)} indicator(s) found")
    
    # Entry conditions
    long_count = sum(1 for e in parsed_bot.entry_conditions if e.direction == "long")
    short_count = sum(1 for e in parsed_bot.entry_conditions if e.direction == "short")
    if long_count or short_count:
        parts.append(f"{long_count} long, {short_count} short entry signal(s)")
    
    # Risk management
    risk = parsed_bot.risk_management
    risk_parts = []
    if risk.has_stop_loss:
        risk_parts.append("SL")
    if risk.has_take_profit:
        risk_parts.append("TP")
    if risk.has_trailing_stop:
        risk_parts.append("Trail")
    if risk_parts:
        parts.append(f"Risk: {', '.join(risk_parts)}")
    
    # Category
    parts.append(f"Category: {strategy.category}")
    
    # Warnings
    if parsed_bot.warnings:
        parts.append(f"{len(parsed_bot.warnings)} warning(s)")
    
    return " | ".join(parts)


# ==================== PHASE 2: REFINEMENT ENDPOINTS ====================

@router.post("/refine-strategy", response_model=RefineStrategyResponse)
async def refine_strategy(request: RefineStrategyRequest):
    """
    Phase 2: Refine a parsed strategy
    
    Takes parsed bot data and strategy from /analyze-cbot and applies
    rule-based improvements including:
    - Risk management fixes (SL/TP/trailing)
    - Filter additions (session, spread, volatility)
    - Overtrading protection (daily limits, loss streak)
    - Parameter optimization
    
    Returns:
    - original_strategy: The input strategy
    - issues: Detected issues with severity
    - improved_strategy: Strategy with fixes applied
    - changes_made: List of specific changes
    - improvement_score: 0-100 score
    """
    try:
        # Validate input
        if not request.parsed or not request.strategy:
            raise HTTPException(
                status_code=400,
                detail="Missing parsed or strategy data"
            )
        
        # Create refinement engine
        engine = create_refinement_engine()
        
        # Run refinement
        result = engine.refine(request.parsed, request.strategy)
        
        logger.info(f"Strategy refined: {len(result.issues)} issues found, {len(result.changes_made)} changes applied")
        
        return RefineStrategyResponse(
            success=True,
            original_strategy=result.original_strategy,
            issues=[{
                'category': i.category,
                'severity': i.severity,
                'title': i.title,
                'description': i.description,
                'impact': i.impact,
                'recommendation': i.recommendation,
                'auto_fixable': i.auto_fixable
            } for i in result.issues],
            improved_strategy=result.improved_strategy,
            changes_made=[{
                'change_type': c.change_type,
                'component': c.component,
                'description': c.description,
                'before': c.before,
                'after': c.after,
                'reason': c.reason
            } for c in result.changes_made],
            improvement_score=result.improvement_score,
            summary=result.summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refining strategy: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Refinement failed: {str(e)}"
        )


@router.post("/analyze-and-refine", response_model=AnalyzeAndRefineResponse)
async def analyze_and_refine(request: AnalyzeAndRefineRequest):
    """
    Combined endpoint: Analyze C# code AND refine strategy in one call
    
    This is the recommended endpoint for full pipeline:
    1. Parse C# cBot code
    2. Convert to structured strategy
    3. Detect issues
    4. Apply improvements
    5. Optionally generate optimized bot code (include_generated_bot=true)
    """
    try:
        # Validate input
        if not request.code or len(request.code.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Invalid code: Code is too short or empty"
            )
        
        if 'class' not in request.code and 'Robot' not in request.code:
            raise HTTPException(
                status_code=400,
                detail="Invalid code: Does not appear to be a cTrader cBot"
            )
        
        # Phase 1: Parse and analyze
        csharp_parser = CSharpBotParser()
        parsed_bot = csharp_parser.parse(request.code)
        
        strategy_parser = StrategyParser()
        strategy = strategy_parser.parse(parsed_bot)
        
        parsed_dict = parsed_bot.to_dict()
        strategy_dict = strategy.to_dict()
        
        # Phase 2: Refine
        engine = create_refinement_engine()
        result = engine.refine(parsed_dict, strategy_dict)
        
        # Phase 3: Generate bot (optional)
        generated_bot = None
        if request.include_generated_bot:
            generator = create_bot_generator()
            bot_result = generator.generate(result.improved_strategy, parsed_dict)
            generated_bot = bot_result.to_dict()
            logger.info(f"Generated optimized bot: {bot_result.bot_name}")
        
        logger.info(f"Analyzed and refined '{parsed_bot.bot_name}': {len(result.changes_made)} improvements")
        
        return AnalyzeAndRefineResponse(
            success=True,
            parsed=parsed_dict,
            original_strategy=result.original_strategy,
            improved_strategy=result.improved_strategy,
            issues=[{
                'category': i.category,
                'severity': i.severity,
                'title': i.title,
                'description': i.description,
                'impact': i.impact,
                'recommendation': i.recommendation,
                'auto_fixable': i.auto_fixable
            } for i in result.issues],
            changes_made=[{
                'change_type': c.change_type,
                'component': c.component,
                'description': c.description,
                'before': c.before,
                'after': c.after,
                'reason': c.reason
            } for c in result.changes_made],
            improvement_score=result.improvement_score,
            summary=result.summary,
            generated_bot=generated_bot
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in analyze-and-refine: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis and refinement failed: {str(e)}"
        )


@router.post("/generate-bot", response_model=GenerateBotResponse)
async def generate_bot(request: GenerateBotRequest):
    """
    Phase 3: Generate optimized C# cBot from improved strategy
    
    Takes the improved_strategy from refinement and generates
    production-ready C# code that:
    - Compiles without errors in cTrader
    - Includes all risk management (SL, TP, trailing)
    - Has all filters (session, spread, volatility, etc.)
    - Uses risk-based position sizing
    - Includes loss streak protection
    """
    try:
        if not request.improved_strategy:
            raise HTTPException(
                status_code=400,
                detail="Missing improved_strategy data"
            )
        
        # Generate bot
        generator = create_bot_generator()
        result = generator.generate(request.improved_strategy, request.parsed)
        
        logger.info(f"Generated bot: {result.bot_name} ({result.indicators_count} indicators, {result.filters_count} filters)")
        
        return GenerateBotResponse(
            success=True,
            generated_bot_code=result.code,
            bot_name=result.bot_name,
            class_name=result.class_name,
            indicators_count=result.indicators_count,
            filters_count=result.filters_count,
            has_risk_management=result.has_risk_management
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating bot: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Bot generation failed: {str(e)}"
        )


def init_analyzer_router():
    """Initialize the analyzer router (for dependency injection if needed)"""
    return router
