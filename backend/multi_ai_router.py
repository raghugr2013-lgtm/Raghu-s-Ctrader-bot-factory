"""
Multi-AI Collaboration Engine - API Router
Endpoints for multi-AI bot generation, collaboration logs, and quality gates
"""

from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from typing import Optional
import logging
import os
import uuid
import time

from multi_ai_models import (
    MultiAIGenerationRequest,
    MultiAIGenerationResult,
    AIMode,
    AIModel,
    CollaborationStage,
    AICollaborationLog,
)
from multi_ai_engine import create_multi_ai_orchestrator, create_warning_optimizer
from quality_gates import create_quality_gates_evaluator
from roslyn_validator import validate_csharp_code as regex_validate_csharp  # Fallback
from real_csharp_compiler import compile_csharp_code, get_real_compiler  # Real compiler
from compliance_engine import get_compliance_engine
from market_selection_engine import evaluate_strategy_markets, MarketType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Will be set during app startup
db = None
EMERGENT_LLM_KEY = None


def init_multi_ai_router(database, llm_key: str):
    """Initialize router with database and API key"""
    global db, EMERGENT_LLM_KEY
    db = database
    EMERGENT_LLM_KEY = llm_key


@router.post("/bot/generate-multi-ai")
async def generate_multi_ai(request: MultiAIGenerationRequest):
    """
    Generate cBot using selected AI mode:
    - single: one AI model generates the bot
    - collaboration: sequential pipeline (Generator -> Reviewer -> Optimizer)
    - competition: all AIs compete, best wins
    """
    start_time = time.time()

    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="LLM API key not configured")

    session_id = request.session_id or str(uuid.uuid4())
    orchestrator = create_multi_ai_orchestrator(EMERGENT_LLM_KEY)
    warning_optimizer = create_warning_optimizer(EMERGENT_LLM_KEY)

    try:
        final_code = ""
        competition_entries = None
        winning_model = None

        # ---- GENERATION PHASE ----
        if request.ai_mode == AIMode.SINGLE:
            model = request.single_ai_model or AIModel.OPENAI_GPT52
            final_code = await orchestrator.single_ai_generation(
                strategy_prompt=request.strategy_prompt,
                ai_model=model,
                session_id=session_id,
                prop_firm=request.prop_firm,
            )

        elif request.ai_mode == AIMode.COLLABORATION:
            gen_model = request.strategy_generator_model or AIModel.DEEPSEEK
            rev_model = request.code_reviewer_model or AIModel.OPENAI_GPT52
            opt_model = request.optimizer_model or AIModel.CLAUDE_SONNET

            final_code = await orchestrator.collaboration_pipeline(
                strategy_prompt=request.strategy_prompt,
                generator_model=gen_model,
                reviewer_model=rev_model,
                optimizer_model=opt_model,
                session_id=session_id,
                prop_firm=request.prop_firm,
            )

        elif request.ai_mode == AIMode.COMPETITION:
            models = request.competition_models or [
                AIModel.DEEPSEEK,
                AIModel.OPENAI_GPT52,
                AIModel.CLAUDE_SONNET,
            ]
            final_code, competition_entries = await orchestrator.competition_mode(
                strategy_prompt=request.strategy_prompt,
                models=models,
                session_id=session_id,
                prop_firm=request.prop_firm,
            )
            winning_model = competition_entries[0].ai_model if competition_entries else None

        # ---- VALIDATION PHASE (REAL C# COMPILATION) ----
        orchestrator.log_stage(
            CollaborationStage.COMPILATION,
            AIModel.OPENAI_GPT52,
            "Running REAL .NET C# compilation...",
        )
        
        # Use REAL .NET compiler for accurate validation
        validation = compile_csharp_code(final_code, "GeneratedBot")
        compilation_errors = validation.get("error_count", 0)
        compilation_warnings = validation.get("warning_count", 0)
        
        # Log detailed error info
        if compilation_errors > 0:
            logger.info(f"REAL Compilation errors: {validation.get('errors', [])}")
        if compilation_warnings > 0:
            logger.info(f"REAL Compilation warnings: {validation.get('warnings', [])}")
        
        orchestrator.log_stage(
            CollaborationStage.COMPILATION,
            AIModel.OPENAI_GPT52,
            f"REAL Compilation: {compilation_errors} errors, {compilation_warnings} warnings",
        )

        # ---- ERROR FIX LOOP ----
        fix_attempts = 0
        fix_model = request.single_ai_model or AIModel.OPENAI_GPT52
        while compilation_errors > 0 and fix_attempts < request.max_error_fix_attempts:
            fix_attempts += 1
            orchestrator.log_stage(
                CollaborationStage.COMPILATION,
                fix_model,
                f"AI fixing errors (attempt {fix_attempts}/{request.max_error_fix_attempts})...",
            )
            
            # Format errors for AI with line numbers
            error_details = validation.get("details", [])
            error_text = "\n".join([
                f"[{e['type'].upper()} {e['code']}] Line {e['line']}: {e['message']}"
                for e in error_details if e['type'] == 'error'
            ])
            warning_text = "\n".join([
                f"[{e['type'].upper()} {e['code']}] Line {e['line']}: {e['message']}"
                for e in error_details if e['type'] == 'warning'
            ])
            
            prompt = f"""Fix ALL the following cTrader cBot C# compilation errors detected by the REAL .NET compiler.

EXACT ERRORS FROM COMPILER:
{error_text}

WARNINGS TO FIX:
{warning_text}

CRITICAL cTrader API FIXES:
1. OBSOLETE API - Replace these:
   - MarketSeries.Close → Bars.ClosePrices
   - MarketSeries.Open → Bars.OpenPrices  
   - MarketSeries.High → Bars.HighPrices
   - MarketSeries.Low → Bars.LowPrices
   - MarketSeries → Bars
   - QuantityToVolume → QuantityToVolumeInUnits
   - Indicators.XXX(MarketSeries, ...) → Indicators.XXX(Bars, ...)

2. UNDEFINED - Fix these:
   - 'Label' undefined → Add: private const string Label = "MyBot";
   - 'EquityWithdrawn' → Use Account.Equity or Account.Balance
   - MarketSeries.Symbol → Use Symbol directly

3. REQUIRED using statements:
   using System;
   using cAlgo.API;
   using cAlgo.API.Internals;
   using cAlgo.API.Indicators;

4. Volume handling:
   double volume = Symbol.NormalizeVolumeInUnits(Symbol.VolumeInUnitsMin * lots);

5. TradeType: Use TradeType.Buy and TradeType.Sell (NOT Long/Short)

CURRENT CODE:
{final_code}

Return ONLY the complete fixed C# code. No markdown, no explanations, no code blocks."""
            
            final_code = await orchestrator.generate_code(fix_model, prompt, session_id)
            
            # Recompile with REAL compiler
            validation = compile_csharp_code(final_code, "GeneratedBot")
            compilation_errors = validation.get("error_count", 0)
            compilation_warnings = validation.get("warning_count", 0)
            
            orchestrator.log_stage(
                CollaborationStage.COMPILATION,
                fix_model,
                f"After fix: {compilation_errors} errors, {compilation_warnings} warnings",
            )

        # ---- WARNING OPTIMIZATION ----
        if compilation_errors == 0 and compilation_warnings > request.max_warning_threshold:
            orchestrator.log_stage(
                CollaborationStage.WARNING_OPTIMIZATION,
                fix_model,
                f"Optimizing {compilation_warnings} warnings...",
            )
            final_code, compilation_warnings = await warning_optimizer.optimize_warnings(
                code=final_code,
                warnings=validation.get("warnings", []),
                ai_model=fix_model,
                session_id=session_id,
                max_attempts=request.max_warning_optimization_attempts,
            )
            orchestrator.log_stage(
                CollaborationStage.WARNING_OPTIMIZATION,
                fix_model,
                f"After optimization: {compilation_warnings} warnings remaining",
            )

        # ---- COMPLIANCE CHECK ----
        compliance_score = None
        if request.prop_firm and request.prop_firm != "none":
            orchestrator.log_stage(
                CollaborationStage.COMPLIANCE,
                AIModel.OPENAI_GPT52,
                f"Running {request.prop_firm} compliance check...",
            )
            try:
                engine = get_compliance_engine(request.prop_firm)
                compliance_result = engine.validate(final_code)
                compliance_score = compliance_result.compliance_score if hasattr(compliance_result, "compliance_score") else (100.0 if compliance_result.is_compliant else 40.0)
                orchestrator.log_stage(
                    CollaborationStage.COMPLIANCE,
                    AIModel.OPENAI_GPT52,
                    f"Compliance score: {compliance_score:.1f}",
                )
            except Exception as e:
                logger.warning(f"Compliance check error: {e}")
                orchestrator.log_stage(
                    CollaborationStage.COMPLIANCE,
                    AIModel.OPENAI_GPT52,
                    f"Compliance check skipped: {str(e)}",
                )

        # ---- QUALITY GATES ----
        orchestrator.log_stage(
            CollaborationStage.QUALITY_GATES,
            AIModel.OPENAI_GPT52,
            "Evaluating quality gates...",
        )
        gates_evaluator = create_quality_gates_evaluator(
            warning_threshold=request.max_warning_threshold
        )
        quality_result = gates_evaluator.evaluate_all_gates(
            compilation_errors=compilation_errors,
            compilation_warnings=compilation_warnings,
            compliance_score=compliance_score,
        )
        deployment_status = gates_evaluator.get_deployment_status(quality_result)

        orchestrator.log_stage(
            CollaborationStage.QUALITY_GATES,
            AIModel.OPENAI_GPT52,
            quality_result.summary,
        )

        # ---- MARKET SELECTION (NEW) ----
        market_selection = None
        best_pair = None
        best_timeframe = None
        market_type = None
        
        if compilation_errors == 0 and request.run_backtest:
            orchestrator.log_stage(
                CollaborationStage.QUALITY_GATES,
                AIModel.OPENAI_GPT52,
                "Running market selection across pairs/timeframes...",
            )
            try:
                market_selection = await evaluate_strategy_markets(
                    strategy_code=final_code,
                    strategy_name=f"Strategy_{session_id[:8]}",
                    pairs=["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"],
                    timeframes=["M5", "M15", "M30", "H1"]
                )
                
                if market_selection and market_selection.get("best_config"):
                    best_config = market_selection["best_config"]
                    best_pair = best_config.get("pair")
                    best_timeframe = best_config.get("timeframe")
                    market_type = best_config.get("market_type")
                    
                    orchestrator.log_stage(
                        CollaborationStage.QUALITY_GATES,
                        AIModel.OPENAI_GPT52,
                        f"Best config: {best_pair}/{best_timeframe} ({market_type}) - Score: {best_config.get('prop_score', 0):.1f}",
                    )
                else:
                    orchestrator.log_stage(
                        CollaborationStage.QUALITY_GATES,
                        AIModel.OPENAI_GPT52,
                        "No optimal market configuration found",
                    )
            except Exception as e:
                logger.warning(f"Market selection error: {e}")
                orchestrator.log_stage(
                    CollaborationStage.QUALITY_GATES,
                    AIModel.OPENAI_GPT52,
                    f"Market selection skipped: {str(e)}",
                )

        # ---- MARK COMPLETE ----
        orchestrator.log_stage(
            CollaborationStage.COMPLETE,
            AIModel.OPENAI_GPT52,
            f"Pipeline complete. Deployable: {quality_result.is_deployable}",
        )

        execution_time = time.time() - start_time

        # Build result
        result = MultiAIGenerationResult(
            session_id=session_id,
            ai_mode=request.ai_mode,
            final_code=final_code,
            collaboration_logs=orchestrator.collaboration_logs,
            competition_entries=[e.model_dump() for e in competition_entries] if competition_entries else None,
            winning_model=winning_model,
            compilation_errors=compilation_errors,
            compilation_warnings=compilation_warnings,
            compliance_score=compliance_score,
            quality_gates_result=quality_result,
            total_ai_calls=orchestrator.total_ai_calls,
            total_iterations=fix_attempts,
            execution_time_seconds=round(execution_time, 2),
        )

        # Persist to DB
        result_doc = result.model_dump()
        result_doc["created_at"] = result_doc["created_at"].isoformat()
        for log_entry in result_doc["collaboration_logs"]:
            log_entry["timestamp"] = log_entry["timestamp"].isoformat()
        await db.multi_ai_results.insert_one(result_doc)

        return {
            "success": True,
            "session_id": session_id,
            "ai_mode": request.ai_mode.value,
            "code": final_code,
            "collaboration_logs": [
                {
                    "stage": entry.stage.value,
                    "ai_model": entry.ai_model.value,
                    "ai_role": entry.ai_role.value if entry.ai_role else None,
                    "message": entry.message,
                    "improvements": entry.improvements,
                    "timestamp": entry.timestamp.isoformat(),
                }
                for entry in orchestrator.collaboration_logs
            ],
            "validation": {
                "compilation_errors": compilation_errors,
                "compilation_warnings": compilation_warnings,
                "is_valid": compilation_errors == 0,
                "compliance_score": compliance_score,
                "compiler_version": validation.get("compiler_version", "unknown"),
                "compilation_time_ms": validation.get("compilation_time_ms", 0),
                "error_details": validation.get("details", []),  # Detailed errors for UI
            },
            "quality_gates": deployment_status,
            "competition": (
                {
                    "entries": [
                        {
                            "ai_model": e.ai_model.value,
                            "validation_errors": e.validation_errors,
                            "validation_warnings": e.validation_warnings,
                            "rank": e.rank,
                        }
                        for e in competition_entries
                    ],
                    "winner": winning_model.value if winning_model else None,
                }
                if competition_entries
                else None
            ),
            "metadata": {
                "total_ai_calls": orchestrator.total_ai_calls,
                "total_fix_attempts": fix_attempts,
                "execution_time_seconds": round(execution_time, 2),
            },
            # Market Selection Results (NEW)
            "market_selection": {
                "best_pair": best_pair,
                "best_timeframe": best_timeframe,
                "market_type": market_type,
                "top_configs": market_selection.get("top_configs", [])[:3] if market_selection else [],
                "total_tested": market_selection.get("total_combinations_tested", 0) if market_selection else 0,
                "passed_threshold": market_selection.get("passed_threshold_count", 0) if market_selection else 0,
            } if market_selection else None,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Multi-AI generation error: {error_msg}")
        import traceback
        traceback.print_exc()
        if "budget" in error_msg.lower() or "exceeded" in error_msg.lower():
            raise HTTPException(
                status_code=402,
                detail="LLM budget exceeded. Please add balance at Profile > Universal Key > Add Balance."
            )
        raise HTTPException(status_code=500, detail=f"Multi-AI generation failed: {error_msg}")


@router.get("/bot/collaboration-logs/{session_id}")
async def get_collaboration_logs(session_id: str):
    """Get collaboration logs for a session"""
    try:
        result = await db.multi_ai_results.find_one(
            {"session_id": session_id},
            {"_id": 0, "collaboration_logs": 1, "ai_mode": 1, "quality_gates_result": 1},
        )

        if not result:
            raise HTTPException(status_code=404, detail="No collaboration logs found for this session")

        return {
            "success": True,
            "session_id": session_id,
            "ai_mode": result.get("ai_mode"),
            "logs": result.get("collaboration_logs", []),
            "quality_gates": result.get("quality_gates_result"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get collaboration logs error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch logs: {str(e)}")


@router.get("/bot/multi-ai-result/{session_id}")
async def get_multi_ai_result(session_id: str):
    """Get full multi-AI generation result"""
    try:
        result = await db.multi_ai_results.find_one(
            {"session_id": session_id},
            {"_id": 0},
        )

        if not result:
            raise HTTPException(status_code=404, detail="No result found for this session")

        return {"success": True, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get multi-AI result error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch result: {str(e)}")
