"""
AI Bot Builder Router
Core pipeline: Idea → AI Generate → Validate → Compile → Compliance Check
UPDATED: Direct API Integration (no emergentintegrations)
"""

import re
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient

from direct_ai_client import get_ai_client
from roslyn_validator import validate_csharp_code
from compile_gate import compile_and_verify, check_download_allowed
from compliance_engine import get_compliance_engine, get_prop_firm_profiles
from safety_injector import inject_safety_rules
from fix_suggester import suggest_fixes, apply_fix, apply_all_fixes

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Models ──────────────────────────────────────────────

class BotGenerationRequest(BaseModel):
    strategy_prompt: str
    ai_model: Literal["openai", "claude"] = "openai"
    session_id: Optional[str] = None
    prop_firm: Optional[str] = "none"
    risk_percent: Optional[float] = 2.0
    timeframe: Optional[str] = "H1"
    strategy_type: Optional[str] = "trend"

class CodeValidationRequest(BaseModel):
    code: str
    prop_firm: Optional[str] = "none"

class CompileGateRequest(BaseModel):
    code: str
    auto_fix: bool = True
    max_fix_attempts: int = 3

class ComplianceCheckRequest(BaseModel):
    code: str
    prop_firm: str

class CodeFixRequest(BaseModel):
    code: str
    error_message: str
    compliance_feedback: Optional[str] = None
    ai_model: Literal["openai", "claude"] = "openai"
    session_id: str
    prop_firm: Optional[str] = "none"

class SafetyInjectionRequest(BaseModel):
    code: str
    prop_firm: Optional[str] = "none"
    risk_percent: Optional[float] = 1.0

class FixSuggestionRequest(BaseModel):
    code: str
    validation_errors: Optional[list] = []
    compile_errors: Optional[list] = []

class ApplyFixRequest(BaseModel):
    code: str
    fix_id: str
    code_patch: Optional[str] = None

class ApplyAllFixesRequest(BaseModel):
    code: str
    suggestions: list


# ── Helpers ─────────────────────────────────────────────

EMERGENT_LLM_KEY = None

def _get_llm_key():
    global EMERGENT_LLM_KEY
    if EMERGENT_LLM_KEY is None:
        EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
        logger.info(f"Retrieved EMERGENT_LLM_KEY: {EMERGENT_LLM_KEY[:20] if EMERGENT_LLM_KEY else 'NONE'}...")
    return EMERGENT_LLM_KEY

_PROP_FIRM_PROFILES = None

def _get_profiles():
    global _PROP_FIRM_PROFILES
    if _PROP_FIRM_PROFILES is None:
        from compliance_engine import PROP_FIRM_PROFILES
        _PROP_FIRM_PROFILES = PROP_FIRM_PROFILES
    return _PROP_FIRM_PROFILES


def _build_system_message(prop_firm: str = "none") -> str:
    prop_ctx = ""
    if prop_firm and prop_firm != "none":
        rules = _get_profiles().get(prop_firm.lower())
        if rules:
            prop_ctx = (
                f"\n\nIMPORTANT – {rules.name} prop firm rules:\n"
                f"- Max Daily Loss: {rules.max_daily_loss}%\n"
                f"- Max Drawdown: {rules.max_total_drawdown}%\n"
                f"- Max Risk/Trade: {rules.max_risk_per_trade}%\n"
                f"- Max Open Trades: {rules.max_open_trades}\n"
                f"- Stop Loss: {'REQUIRED' if rules.stop_loss_required else 'Optional'}\n"
            )
    return (
        "You are an expert cTrader cBot developer. You write professional, clean C# code "
        "for cTrader Automate platform.\nWhen given a trading strategy, you generate complete, "
        "compilable cBot code.\nAlways return ONLY the C# code, no explanations or markdown."
        + prop_ctx
    )


def _get_provider(model: str) -> str:
    """Map model name to provider"""
    if model == "claude":
        return "claude"
    elif model == "deepseek":
        return "deepseek"
    return "openai"


def _strip_markdown(code: str) -> str:
    code = re.sub(r'^```(?:c#|csharp)?\s*\n', '', code)
    code = re.sub(r'\n```\s*$', '', code)
    return code.strip()


# ── DB handle (set from server.py) ─────────────────────
_db = None

def init_builder_router(db):
    global _db
    _db = db
    return router


# ── Endpoints ───────────────────────────────────────────

@router.post("/bot/generate")
async def generate_bot(req: BotGenerationRequest):
    """Generate cBot code using AI from a strategy description."""
    try:
        session_id = req.session_id or str(uuid.uuid4())

        # Get AI client and provider
        ai_client = get_ai_client()
        provider = _get_provider(req.ai_model)
        system_message = _build_system_message(req.prop_firm)

        extra = ""
        if req.risk_percent:
            extra += f"\n- Risk per trade: {req.risk_percent}% of balance"
        if req.timeframe:
            extra += f"\n- Timeframe: {req.timeframe}"
        if req.strategy_type:
            extra += f"\n- Strategy type: {req.strategy_type}"

        prompt = (
            f"Generate a complete cTrader cBot in C# for the following trading strategy:\n\n"
            f"{req.strategy_prompt}\n\n"
            f"Additional requirements:{extra}\n"
            f"- Must inherit from Robot class\n"
            f"- Include all necessary using statements\n"
            f"- Implement OnStart() and OnBar()\n"
            f"- Include proper error handling and comments\n"
            f"- Make it production-ready and compilable\n\n"
            f"Return ONLY the C# code."
        )

        # Generate using direct API
        response = await ai_client.generate(
            provider=provider,
            prompt=prompt,
            system_message=system_message
        )
        generated_code = _strip_markdown(response.strip())

        # Auto compile-gate
        compile_result = compile_and_verify(generated_code, max_attempts=3)
        final_code = compile_result["code"]

        # Persist session
        if _db is not None:
            doc = {
                "id": session_id,
                "strategy_prompt": req.strategy_prompt,
                "ai_model": req.ai_model,
                "prop_firm": req.prop_firm or "none",
                "generated_code": final_code,
                "validation_status": "verified" if compile_result["is_verified"] else "has_errors",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await _db.bot_sessions.update_one(
                {"id": session_id}, {"$set": doc}, upsert=True
            )

        return {
            "success": True,
            "session_id": session_id,
            "code": final_code,
            "ai_model": req.ai_model,
            "compile_status": compile_result["status"],
            "compile_verified": compile_result["is_verified"],
            "compile_errors": compile_result["errors"],
            "compile_warnings": compile_result["warnings"],
            "fixes_applied": compile_result["fixes_applied"],
        }

    except Exception as e:
        logger.exception("generate_bot error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/code/validate")
async def validate_code(req: CodeValidationRequest):
    """Validate C# cBot code (syntax + optional compliance)."""
    try:
        result = validate_csharp_code(req.code)

        compliance = None
        if req.prop_firm and req.prop_firm != "none":
            try:
                engine = get_compliance_engine(req.prop_firm)
                compliance = engine.validate(req.code)
                if not compliance.is_compliant:
                    for v in compliance.violations:
                        bucket = "errors" if v.severity in ("critical", "high") else "warnings"
                        result[bucket].append(f"[COMPLIANCE] {v.message}")
                compliance = compliance.model_dump()
            except Exception:
                logger.exception("compliance check in validate")

        return {**result, "compliance": compliance}

    except Exception as e:
        logger.exception("validate_code error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/code/compile-gate")
async def compile_gate_check(req: CompileGateRequest):
    """Strict compilation gate with auto-fix loop."""
    try:
        attempts = req.max_fix_attempts if req.auto_fix else 1
        result = compile_and_verify(req.code, max_attempts=attempts)
        return {
            "success": result["is_verified"],
            "status": result["status"],
            "is_verified": result["is_verified"],
            "code": result["code"],
            "errors": result["errors"],
            "warnings": result["warnings"],
            "fix_attempts": result["fix_attempts"],
            "fixes_applied": result["fixes_applied"],
            "message": result["message"],
        }
    except Exception as e:
        logger.exception("compile_gate error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance/check")
async def check_compliance(req: ComplianceCheckRequest):
    """Check code compliance against a specific prop firm's rules."""
    try:
        engine = get_compliance_engine(req.prop_firm)
        result = engine.validate(req.code)
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("compliance check error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compliance/profiles")
async def get_compliance_profiles():
    """List all available prop firm profiles."""
    profiles = get_prop_firm_profiles()
    return {
        "profiles": [
            {"id": k, "name": p.name, "description": p.description, "rules": p.model_dump()}
            for k, p in profiles.items()
        ]
    }


@router.post("/code/fix")
async def fix_code(req: CodeFixRequest):
    """Fix code errors using AI."""
    try:
        # Get AI client and provider
        ai_client = get_ai_client()
        provider = _get_provider(req.ai_model)
        system_message = _build_system_message(req.prop_firm)

        compliance_section = ""
        if req.compliance_feedback:
            compliance_section = f"\n\nCOMPLIANCE VIOLATIONS:\n{req.compliance_feedback}\nFix these too."

        prompt = (
            f"Fix the following cTrader cBot code.\n\n"
            f"ERRORS:\n{req.error_message}{compliance_section}\n\n"
            f"CODE:\n{req.code}\n\n"
            f"Return ONLY the fixed C# code."
        )

        # Generate using direct API
        response = await ai_client.generate(
            provider=provider,
            prompt=prompt,
            system_message=system_message
        )
        fixed_code = _strip_markdown(response.strip())

        return {"success": True, "code": fixed_code}

    except Exception as e:
        logger.exception("code fix error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/code/inject-safety")
async def inject_safety(req: SafetyInjectionRequest):
    """Inject comprehensive safety rules into bot code."""
    try:
        result = inject_safety_rules(
            code=req.code,
            prop_firm=req.prop_firm or "none",
            risk_percent=req.risk_percent or 1.0
        )
        return result
    except Exception as e:
        logger.exception("safety injection error")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/code/suggest-fixes")
async def suggest_code_fixes(req: FixSuggestionRequest):
    """Suggest fixes for validation and compilation errors."""
    try:
        result = suggest_fixes(
            code=req.code,
            validation_errors=req.validation_errors or [],
            compile_errors=req.compile_errors or []
        )
        return result
    except Exception as e:
        logger.exception("fix suggestion error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/code/apply-fix")
async def apply_single_fix(req: ApplyFixRequest):
    """Apply a single fix to the code."""
    try:
        result = apply_fix(
            code=req.code,
            fix_id=req.fix_id,
            code_patch=req.code_patch
        )
        return result
    except Exception as e:
        logger.exception("apply fix error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/code/apply-all-fixes")
async def apply_all_code_fixes(req: ApplyAllFixesRequest):
    """Apply all auto-fixable suggestions."""
    try:
        result = apply_all_fixes(
            code=req.code,
            suggestions=req.suggestions
        )
        return result
    except Exception as e:
        logger.exception("apply all fixes error")
        raise HTTPException(status_code=500, detail=str(e))
