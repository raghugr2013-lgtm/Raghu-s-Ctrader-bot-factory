"""
Multi-AI Collaboration Engine - Data Models
Phase 7+: Enhanced AI Collaboration System
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Literal
from datetime import datetime, timezone
from enum import Enum
import uuid


class AIMode(str, Enum):
    """AI collaboration mode"""
    SINGLE = "single"  # Single AI generates bot
    COLLABORATION = "collaboration"  # Sequential AI pipeline
    COMPETITION = "competition"  # All AIs compete, best wins


class AIRole(str, Enum):
    """AI role in collaboration pipeline"""
    STRATEGY_GENERATOR = "strategy_generator"
    CODE_REVIEWER = "code_reviewer"
    OPTIMIZER = "optimizer"


class AIModel(str, Enum):
    """Available AI models"""
    OPENAI_GPT52 = "openai"
    CLAUDE_SONNET = "claude"
    DEEPSEEK = "deepseek"


class CollaborationStage(str, Enum):
    """Stages in collaboration pipeline"""
    GENERATION = "generation"
    REVIEW = "review"
    OPTIMIZATION = "optimization"
    VALIDATION = "validation"
    COMPILATION = "compilation"
    WARNING_OPTIMIZATION = "warning_optimization"
    COMPLIANCE = "compliance"
    BACKTESTING = "backtesting"
    WALKFORWARD = "walkforward"
    MONTECARLO = "montecarlo"
    QUALITY_GATES = "quality_gates"
    COMPLETE = "complete"


class AICollaborationLog(BaseModel):
    """Log entry for AI collaboration"""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage: CollaborationStage
    ai_model: AIModel
    ai_role: Optional[AIRole] = None
    message: str
    code_snippet: Optional[str] = None
    improvements: Optional[List[str]] = None


class AIRoleConfig(BaseModel):
    """Configuration for AI role"""
    role: AIRole
    model: AIModel
    prompt_template: str
    
    @classmethod
    def default_configs(cls) -> Dict[AIRole, 'AIRoleConfig']:
        """Get default AI role configurations"""
        return {
            AIRole.STRATEGY_GENERATOR: cls(
                role=AIRole.STRATEGY_GENERATOR,
                model=AIModel.DEEPSEEK,
                prompt_template="""Generate a complete cTrader cBot for the following strategy:
{strategy_description}

Requirements:
- Professional C# code with proper error handling
- Include all necessary using statements
- Implement robust risk management
- Add daily loss protection
- Include spread filtering
- Add session time filtering
- Set appropriate stop loss and take profit
- Limit maximum open positions

Focus on creating a solid foundation with proper safeguards."""
            ),
            AIRole.CODE_REVIEWER: cls(
                role=AIRole.CODE_REVIEWER,
                model=AIModel.OPENAI_GPT52,
                prompt_template="""Review the following cTrader cBot code:

{code}

Check for:
1. Logic errors and bugs
2. Code quality and best practices
3. Prop firm compliance (daily loss limits, max drawdown, risk per trade)
4. Risk management implementation
5. Missing safeguards

Required safeguards:
- Daily loss protection (check if daily P&L exceeds limit)
- Maximum open trades limit
- Spread filter (avoid trading during high spreads)
- Trading session filter (trade only during specified hours)
- Proper stop loss on all trades
- Position sizing based on risk percentage

Provide improved code with review notes."""
            ),
            AIRole.OPTIMIZER: cls(
                role=AIRole.OPTIMIZER,
                model=AIModel.CLAUDE_SONNET,
                prompt_template="""Optimize the following cTrader cBot code:

{code}

Previous improvements:
{improvements}

Suggest and implement optimizations for:
1. Reducing drawdown (tighter stop losses, better entry timing)
2. Improving entry signals (add confirmation indicators)
3. Optimizing TP/SL ratios (risk/reward balance)
4. Adding indicator filters (trend filters, volatility filters)
5. Performance improvements (efficient calculations)

Provide optimized code with explanation of changes."""
            )
        }


class QualityGate(BaseModel):
    """Individual quality gate"""
    name: str
    passed: bool
    score: Optional[float] = None
    threshold: float
    message: str


class QualityGatesResult(BaseModel):
    """Complete quality gates evaluation"""
    all_passed: bool
    gates: List[QualityGate]
    is_deployable: bool
    summary: str
    failed_gates: List[str]


class MultiAIGenerationRequest(BaseModel):
    """Request for multi-AI bot generation"""
    session_id: Optional[str] = None
    strategy_prompt: str
    
    # AI Mode
    ai_mode: AIMode = AIMode.SINGLE
    
    # Single mode
    single_ai_model: Optional[AIModel] = AIModel.OPENAI_GPT52
    
    # Collaboration mode
    strategy_generator_model: Optional[AIModel] = AIModel.DEEPSEEK
    code_reviewer_model: Optional[AIModel] = AIModel.OPENAI_GPT52
    optimizer_model: Optional[AIModel] = AIModel.CLAUDE_SONNET
    
    # Competition mode
    competition_models: Optional[List[AIModel]] = [
        AIModel.DEEPSEEK,
        AIModel.OPENAI_GPT52,
        AIModel.CLAUDE_SONNET
    ]
    
    # Prop firm
    prop_firm: str = "none"
    
    # Quality settings - increased for real compiler accuracy
    max_warning_threshold: int = 3  # Allow some minor warnings
    max_error_fix_attempts: int = 5  # More attempts for complex errors
    max_warning_optimization_attempts: int = 3
    
    # Validation settings
    run_backtest: bool = True
    run_walkforward: bool = False
    run_montecarlo: bool = False


class CompetitionEntry(BaseModel):
    """Entry in strategy competition"""
    model_config = ConfigDict(extra="ignore")
    
    ai_model: AIModel
    generated_code: str
    validation_errors: int
    validation_warnings: int
    backtest_score: Optional[float] = None
    walkforward_score: Optional[float] = None
    montecarlo_score: Optional[float] = None
    combined_score: float = 0.0
    rank: int = 0


class MultiAIGenerationResult(BaseModel):
    """Result of multi-AI generation"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    ai_mode: AIMode
    
    # Final code
    final_code: str
    
    # Collaboration logs
    collaboration_logs: List[AICollaborationLog]
    
    # Competition results (if competition mode)
    competition_entries: Optional[List[CompetitionEntry]] = None
    winning_model: Optional[AIModel] = None
    
    # Validation results
    compilation_errors: int = 0
    compilation_warnings: int = 0
    compliance_score: Optional[float] = None
    backtest_score: Optional[float] = None
    walkforward_score: Optional[float] = None
    montecarlo_score: Optional[float] = None
    
    # Quality gates
    quality_gates_result: Optional[QualityGatesResult] = None
    
    # Metadata
    total_ai_calls: int = 0
    total_iterations: int = 0
    execution_time_seconds: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ValidationStageResult(BaseModel):
    """Result of a validation stage"""
    stage: CollaborationStage
    passed: bool
    errors: List[str]
    warnings: List[str]
    score: Optional[float] = None
    message: str
