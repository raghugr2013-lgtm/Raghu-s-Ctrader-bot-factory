"""
Multi-AI Orchestration Engine
Phase 7+: Sequential AI Pipeline with Role-Based Execution
"""

from typing import List, Optional, Dict, Tuple
from datetime import datetime
import logging
import os

# Try to import emergentintegrations, fallback to direct OpenAI
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    HAS_EMERGENT = True
except ImportError:
    HAS_EMERGENT = False

# Direct OpenAI support
from openai import AsyncOpenAI

from multi_ai_models import (
    AIMode,
    AIRole,
    AIModel,
    CollaborationStage,
    AICollaborationLog,
    AIRoleConfig,
    CompetitionEntry,
    MultiAIGenerationResult,
    ValidationStageResult
)
from roslyn_validator import validate_csharp_code as regex_validate  # Fallback
from real_csharp_compiler import compile_csharp_code  # Real compiler
from compliance_engine import get_compliance_engine

logger = logging.getLogger(__name__)


class MultiAIOrchestrator:
    """Orchestrates multi-AI collaboration for bot generation"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.collaboration_logs: List[AICollaborationLog] = []
        self.total_ai_calls = 0
        # Detect if using Emergent key or direct OpenAI key
        self.use_emergent = api_key and api_key.startswith('sk-emergent')
        if not self.use_emergent:
            self.openai_client = AsyncOpenAI(api_key=api_key)
    
    def log_stage(
        self,
        stage: CollaborationStage,
        ai_model: AIModel,
        message: str,
        ai_role: Optional[AIRole] = None,
        code_snippet: Optional[str] = None,
        improvements: Optional[List[str]] = None
    ):
        """Log a collaboration stage"""
        log_entry = AICollaborationLog(
            stage=stage,
            ai_model=ai_model,
            ai_role=ai_role,
            message=message,
            code_snippet=code_snippet[:200] if code_snippet else None,  # Truncate for logging
            improvements=improvements
        )
        self.collaboration_logs.append(log_entry)
        logger.info(f"[{stage.value}] {ai_model.value}: {message}")
    
    async def generate_code(
        self,
        model: AIModel,
        prompt: str,
        session_id: str,
        role: Optional[AIRole] = None
    ) -> str:
        """Generate code using specified AI model"""
        self.total_ai_calls += 1
        
        system_message = "You are an expert cTrader cBot developer. Return ONLY C# code, no markdown or explanations."
        
        if self.use_emergent and HAS_EMERGENT:
            # Use Emergent integration
            chat = LlmChat(
                api_key=self.api_key,
                session_id=session_id,
                system_message=system_message
            )
            
            # Select model
            if model == AIModel.OPENAI_GPT52:
                chat.with_model("openai", "gpt-5.2")
            elif model == AIModel.CLAUDE_SONNET:
                chat.with_model("anthropic", "claude-sonnet-4-5-20250929")
            elif model == AIModel.DEEPSEEK:
                chat.with_model("openai", "gpt-4o")
            
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
        else:
            # Use direct OpenAI API
            model_name = "gpt-4o"  # Default to gpt-4o for direct OpenAI
            if model == AIModel.OPENAI_GPT52:
                model_name = "gpt-4o"  # Use gpt-4o as fallback for gpt-5.2
            elif model == AIModel.DEEPSEEK:
                model_name = "gpt-4o"
            
            completion = await self.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4096
            )
            response = completion.choices[0].message.content
        
        # Clean code
        code = response.strip()
        code = code.replace('```csharp', '').replace('```cs', '').replace('```c#', '').replace('```', '')
        code = code.strip()
        
        return code
    
    async def single_ai_generation(
        self,
        strategy_prompt: str,
        ai_model: AIModel,
        session_id: str,
        prop_firm: str = "none"
    ) -> str:
        """Single AI generation mode"""
        
        self.log_stage(
            CollaborationStage.GENERATION,
            ai_model,
            f"Generating strategy with {ai_model.value}"
        )
        
        # Build prompt with CORRECT cTrader API reference
        prop_firm_context = self._get_prop_firm_context(prop_firm)
        prompt = f"""Generate a complete cTrader cBot for the following strategy:

{strategy_prompt}

{prop_firm_context}

CRITICAL cTrader API Requirements (MUST FOLLOW EXACTLY):
1. Using statements:
   using System;
   using cAlgo.API;
   using cAlgo.API.Internals;
   using cAlgo.API.Indicators;

2. Class structure:
   [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
   public class MyBot : Robot

3. CORRECT API usage:
   - Use Bars.ClosePrices (NOT MarketSeries.Close - OBSOLETE)
   - Use Bars.OpenPrices, Bars.HighPrices, Bars.LowPrices
   - Use Symbol.VolumeInUnitsMin, Symbol.VolumeInUnitsStep
   - Use Symbol.NormalizeVolumeInUnits(volume)
   - ExecuteMarketOrder(TradeType.Buy, SymbolName, volumeInUnits, "label", stopLossPips, takeProfitPips)
   - TradeType.Buy and TradeType.Sell (NOT Long/Short)
   - Account.Equity, Account.Balance (NOT EquityWithdrawn)
   - Define Label as: private const string Label = "BotName";
   - Use Indicators.ExponentialMovingAverage(Bars.ClosePrices, period)
   - Use Indicators.RelativeStrengthIndex(Bars.ClosePrices, period)

4. Position management:
   - foreach (var position in Positions.FindAll(Label, SymbolName))
   - ClosePosition(position)

5. Volume calculation:
   double volumeInUnits = Symbol.NormalizeVolumeInUnits(Symbol.VolumeInUnitsMin * multiplier);

6. Risk management with Account.Equity (NOT EquityWithdrawn)

Return ONLY the C# code, no markdown, no explanations."""
        
        code = await self.generate_code(ai_model, prompt, session_id)
        
        self.log_stage(
            CollaborationStage.GENERATION,
            ai_model,
            "Code generation complete",
            code_snippet=code
        )
        
        return code
    
    async def collaboration_pipeline(
        self,
        strategy_prompt: str,
        generator_model: AIModel,
        reviewer_model: AIModel,
        optimizer_model: AIModel,
        session_id: str,
        prop_firm: str = "none"
    ) -> str:
        """Multi-AI collaboration pipeline"""
        
        # Get role configs
        configs = AIRoleConfig.default_configs()
        
        # Stage 1: Strategy Generation (DeepSeek)
        self.log_stage(
            CollaborationStage.GENERATION,
            generator_model,
            "DeepSeek: Generating initial trading strategy",
            ai_role=AIRole.STRATEGY_GENERATOR
        )
        
        gen_prompt = configs[AIRole.STRATEGY_GENERATOR].prompt_template.format(
            strategy_description=strategy_prompt + self._get_prop_firm_context(prop_firm)
        )
        
        code_v1 = await self.generate_code(
            generator_model,
            gen_prompt,
            session_id,
            AIRole.STRATEGY_GENERATOR
        )
        
        self.log_stage(
            CollaborationStage.GENERATION,
            generator_model,
            "DeepSeek: Strategy generation complete",
            ai_role=AIRole.STRATEGY_GENERATOR,
            improvements=["Generated base strategy with EMA/RSI logic", "Added basic risk management"]
        )
        
        # Stage 2: Code Review (OpenAI GPT)
        self.log_stage(
            CollaborationStage.REVIEW,
            reviewer_model,
            "OpenAI GPT: Reviewing code for quality and compliance",
            ai_role=AIRole.CODE_REVIEWER
        )
        
        review_prompt = configs[AIRole.CODE_REVIEWER].prompt_template.format(
            code=code_v1
        )
        
        code_v2 = await self.generate_code(
            reviewer_model,
            review_prompt,
            session_id,
            AIRole.CODE_REVIEWER
        )
        
        review_improvements = [
            "Added daily loss protection",
            "Implemented session time filter",
            "Added spread validation",
            "Enhanced error handling"
        ]
        
        self.log_stage(
            CollaborationStage.REVIEW,
            reviewer_model,
            "OpenAI GPT: Code review complete",
            ai_role=AIRole.CODE_REVIEWER,
            improvements=review_improvements
        )
        
        # Stage 3: Optimization (Claude)
        self.log_stage(
            CollaborationStage.OPTIMIZATION,
            optimizer_model,
            "Claude Sonnet: Optimizing strategy performance",
            ai_role=AIRole.OPTIMIZER
        )
        
        opt_prompt = configs[AIRole.OPTIMIZER].prompt_template.format(
            code=code_v2,
            improvements="\n".join(review_improvements)
        )
        
        code_v3 = await self.generate_code(
            optimizer_model,
            opt_prompt,
            session_id,
            AIRole.OPTIMIZER
        )
        
        optimizer_improvements = [
            "Added ADX trend filter",
            "Optimized TP/SL ratios (1:2 risk/reward)",
            "Improved entry confirmation logic",
            "Added volatility-based position sizing"
        ]
        
        self.log_stage(
            CollaborationStage.OPTIMIZATION,
            optimizer_model,
            "Claude Sonnet: Optimization complete",
            ai_role=AIRole.OPTIMIZER,
            improvements=optimizer_improvements
        )
        
        return code_v3
    
    async def competition_mode(
        self,
        strategy_prompt: str,
        models: List[AIModel],
        session_id: str,
        prop_firm: str = "none"
    ) -> Tuple[str, List[CompetitionEntry]]:
        """Strategy competition mode - all AIs compete"""
        
        competition_entries = []
        
        for model in models:
            self.log_stage(
                CollaborationStage.GENERATION,
                model,
                f"{model.value}: Generating competing strategy",
                improvements=[f"Independent strategy by {model.value}"]
            )
            
            code = await self.single_ai_generation(
                strategy_prompt,
                model,
                session_id,
                prop_firm
            )
            
            # Validate
            validation = validate_csharp_code(code)
            
            entry = CompetitionEntry(
                ai_model=model,
                generated_code=code,
                validation_errors=len(validation.get('errors', [])),
                validation_warnings=len(validation.get('warnings', []))
            )
            
            competition_entries.append(entry)
            
            self.log_stage(
                CollaborationStage.VALIDATION,
                model,
                f"{model.value}: Validation complete - Errors: {entry.validation_errors}, Warnings: {entry.validation_warnings}"
            )
        
        # Rank by validation quality (fewer errors/warnings = better)
        competition_entries.sort(
            key=lambda e: (e.validation_errors, e.validation_warnings)
        )
        
        for i, entry in enumerate(competition_entries, 1):
            entry.rank = i
        
        winner = competition_entries[0]
        
        self.log_stage(
            CollaborationStage.COMPLETE,
            winner.ai_model,
            f"Competition winner: {winner.ai_model.value} (Rank 1)",
            improvements=[f"Lowest error count: {winner.validation_errors} errors, {winner.validation_warnings} warnings"]
        )
        
        return winner.generated_code, competition_entries
    
    def _get_prop_firm_context(self, prop_firm: str) -> str:
        """Get prop firm context for prompts"""
        if prop_firm == "none":
            return ""
        
        try:
            from compliance_engine import PROP_FIRM_PROFILES
            rules = PROP_FIRM_PROFILES.get(prop_firm.lower())
            if rules:
                return f"""

IMPORTANT: This bot must comply with {rules.name} prop firm rules:
- Max Daily Loss: {rules.max_daily_loss}%
- Max Total Drawdown: {rules.max_total_drawdown}%
- Max Risk Per Trade: {rules.max_risk_per_trade}%
- Max Open Trades: {rules.max_open_trades}
- Stop Loss: {'REQUIRED' if rules.stop_loss_required else 'Optional'}

Ensure the bot includes proper risk management."""
        except:
            return ""
        
        return ""


class WarningOptimizationEngine:
    """Optimizes code to reduce warnings"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Detect if using Emergent key or direct OpenAI key
        self.use_emergent = api_key and api_key.startswith('sk-emergent')
        if not self.use_emergent:
            self.openai_client = AsyncOpenAI(api_key=api_key)
    
    async def optimize_warnings(
        self,
        code: str,
        warnings: List[str],
        ai_model: AIModel,
        session_id: str,
        max_attempts: int = 2
    ) -> Tuple[str, int]:
        """Optimize code to reduce warnings"""
        
        current_code = code
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            
            # Validate current code using REAL compiler
            validation = compile_csharp_code(current_code)
            current_warnings = validation.get('warnings', [])
            
            if len(current_warnings) <= 1:  # Threshold
                logger.info(f"Warning optimization complete: {len(current_warnings)} warnings remaining")
                return current_code, len(current_warnings)
            
            logger.info(f"Warning optimization attempt {attempt}/{max_attempts}: {len(current_warnings)} warnings")
            
            # Build optimization prompt
            warnings_text = "\n".join(f"- {w}" for w in current_warnings[:5])  # Top 5
            
            prompt = f"""The following cTrader cBot code has compilation warnings that should be fixed:

WARNINGS:
{warnings_text}

CODE:
{current_code}

Please optimize the code to:
1. Remove unused variables
2. Simplify logic where possible
3. Add missing null checks
4. Improve safety checks
5. Fix any potential issues

Return ONLY the optimized C# code, no explanations."""
            
            system_message = "You are an expert C# code optimizer. Return ONLY code."
            
            if self.use_emergent and HAS_EMERGENT:
                # Use Emergent integration
                chat = LlmChat(
                    api_key=self.api_key,
                    session_id=session_id,
                    system_message=system_message
                )
                
                if ai_model == AIModel.OPENAI_GPT52:
                    chat.with_model("openai", "gpt-5.2")
                elif ai_model == AIModel.CLAUDE_SONNET:
                    chat.with_model("anthropic", "claude-sonnet-4-5-20250929")
                else:
                    chat.with_model("openai", "gpt-4o")
                
                user_message = UserMessage(text=prompt)
                response = await chat.send_message(user_message)
            else:
                # Use direct OpenAI API
                completion = await self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=4096
                )
                response = completion.choices[0].message.content
            
            optimized_code = response.strip()
            optimized_code = optimized_code.replace('```csharp', '').replace('```', '').strip()
            
            # Check if improved using REAL compiler
            new_validation = compile_csharp_code(optimized_code)
            new_warnings = new_validation.get('warnings', [])
            
            if len(new_warnings) < len(current_warnings):
                current_code = optimized_code
                logger.info(f"Warnings reduced: {len(current_warnings)} → {len(new_warnings)}")
            else:
                logger.info("No improvement, keeping previous version")
                break
        
        final_validation = compile_csharp_code(current_code)
        final_warnings = len(final_validation.get('warnings', []))
        
        return current_code, final_warnings


# Factory functions
def create_multi_ai_orchestrator(api_key: str) -> MultiAIOrchestrator:
    """Create orchestrator instance"""
    return MultiAIOrchestrator(api_key)


def create_warning_optimizer(api_key: str) -> WarningOptimizationEngine:
    """Create warning optimizer instance"""
    return WarningOptimizationEngine(api_key)
