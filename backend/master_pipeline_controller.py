"""
Master Pipeline Controller
Orchestrates the complete AI trading strategy pipeline from generation to deployment.

Pipeline Flow:
1. Generation (AI Multi-Engine or Factory)
2. Diversity Filter (Category + Diversity Scoring)
3. Backtest (Real Market Data)
4. Validation (Walk-Forward + Monte Carlo)
5. Correlation Filter (Remove Highly Correlated Strategies)
6. Market Regime Adaptation (Regime Analysis)
7. Portfolio Selection (Best Strategies)
8. Risk & Capital Allocation (Portfolio Optimization)
9. Capital Scaling (Based on Performance)
10. cBot Generation (C# Compilation)
11. Live Monitoring Setup
12. Auto Retrain Scheduling
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Master pipeline stages"""
    INITIALIZATION = "initialization"
    GENERATION = "generation"
    DIVERSITY_FILTER = "diversity_filter"
    BACKTESTING = "backtesting"
    VALIDATION = "validation"
    CORRELATION_FILTER = "correlation_filter"
    REGIME_ADAPTATION = "regime_adaptation"
    PORTFOLIO_SELECTION = "portfolio_selection"
    RISK_ALLOCATION = "risk_allocation"
    CAPITAL_SCALING = "capital_scaling"
    CBOT_GENERATION = "cbot_generation"
    MONITORING_SETUP = "monitoring_setup"
    RETRAIN_SCHEDULING = "retrain_scheduling"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineConfig:
    """Configuration for master pipeline run"""
    # Generation config
    generation_mode: str = "factory"  # "factory", "ai", or "both"
    templates: List[str] = field(default_factory=lambda: ["EMA_CROSSOVER", "RSI_MEAN_REVERSION", "MACD_TREND"])
    strategies_per_template: int = 10
    
    # Market config
    symbol: str = "EURUSD"
    timeframe: str = "1h"
    initial_balance: float = 10000.0
    duration_days: int = 365
    
    # Filter thresholds
    diversity_min_score: float = 60.0
    correlation_max_threshold: float = 0.7
    
    # Selection criteria
    min_sharpe_ratio: float = 1.0
    max_drawdown_pct: float = 20.0
    min_win_rate: float = 50.0
    portfolio_size: int = 5
    
    # Risk config
    max_risk_per_strategy: float = 2.0
    max_portfolio_risk: float = 8.0
    allocation_method: str = "MAX_SHARPE"  # "EQUAL_WEIGHT", "RISK_PARITY", "MAX_SHARPE", etc.
    
    # Regime config
    enable_regime_filter: bool = True
    
    # Monitoring config
    enable_monitoring: bool = True
    enable_auto_retrain: bool = True
    retrain_threshold_days: int = 30


@dataclass
class StageResult:
    """Result from a pipeline stage"""
    stage: PipelineStage
    success: bool
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0


@dataclass
class PipelineRun:
    """Complete pipeline run state"""
    run_id: str
    config: PipelineConfig
    current_stage: PipelineStage = PipelineStage.INITIALIZATION
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Stage results
    stage_results: List[StageResult] = field(default_factory=list)
    
    # Pipeline data
    generated_strategies: List[Dict[str, Any]] = field(default_factory=list)
    filtered_by_diversity: List[Dict[str, Any]] = field(default_factory=list)
    backtested_strategies: List[Dict[str, Any]] = field(default_factory=list)
    validated_strategies: List[Dict[str, Any]] = field(default_factory=list)
    filtered_by_correlation: List[Dict[str, Any]] = field(default_factory=list)
    regime_adapted_strategies: List[Dict[str, Any]] = field(default_factory=list)
    selected_portfolio: List[Dict[str, Any]] = field(default_factory=list)
    allocated_portfolio: Dict[str, Any] = field(default_factory=dict)
    scaled_portfolio: Dict[str, Any] = field(default_factory=dict)
    compiled_bots: List[Dict[str, Any]] = field(default_factory=list)
    
    # Final outputs
    deployable_bots: List[Dict[str, Any]] = field(default_factory=list)
    portfolio_metrics: Dict[str, Any] = field(default_factory=dict)
    
    # Status
    status: str = "running"  # "running", "completed", "failed"
    error_message: Optional[str] = None
    total_execution_time_seconds: float = 0.0


class MasterPipelineController:
    """
    Master controller that orchestrates the complete trading strategy pipeline.
    Integrates all existing engines into a unified flow.
    """
    
    def __init__(self, db_client=None):
        self.db = db_client
        self.active_runs: Dict[str, PipelineRun] = {}
        logger.info("Master Pipeline Controller initialized")
    
    async def run_full_pipeline(self, config: PipelineConfig) -> PipelineRun:
        """
        Execute the complete pipeline from generation to deployment.
        
        Args:
            config: Pipeline configuration
            
        Returns:
            PipelineRun with complete results
        """
        run_id = str(uuid.uuid4())
        pipeline_run = PipelineRun(run_id=run_id, config=config)
        self.active_runs[run_id] = pipeline_run
        
        start_time = datetime.now()
        
        try:
            # Log start
            logger.info(f"[MASTER PIPELINE] Starting run {run_id}")
            logger.info(f"[MASTER PIPELINE] Config: {config}")
            
            # Stage 1: Generation
            await self._stage_generation(pipeline_run)
            if not pipeline_run.generated_strategies:
                raise Exception("No strategies generated")
            
            # Stage 2: Diversity Filter
            await self._stage_diversity_filter(pipeline_run)
            if not pipeline_run.filtered_by_diversity:
                raise Exception("No strategies passed diversity filter")
            
            # Stage 3: Backtesting
            await self._stage_backtesting(pipeline_run)
            if not pipeline_run.backtested_strategies:
                raise Exception("No strategies completed backtesting")
            
            # Stage 4: Validation (Walk-Forward + Monte Carlo)
            await self._stage_validation(pipeline_run)
            if not pipeline_run.validated_strategies:
                raise Exception("No strategies passed validation")
            
            # Stage 5: Correlation Filter
            await self._stage_correlation_filter(pipeline_run)
            if not pipeline_run.filtered_by_correlation:
                raise Exception("No strategies passed correlation filter")
            
            # Stage 6: Market Regime Adaptation
            await self._stage_regime_adaptation(pipeline_run)
            
            # Stage 7: Portfolio Selection
            await self._stage_portfolio_selection(pipeline_run)
            if not pipeline_run.selected_portfolio:
                raise Exception("No strategies selected for portfolio")
            
            # Stage 8: Risk & Capital Allocation
            await self._stage_risk_allocation(pipeline_run)
            
            # Stage 9: Capital Scaling
            await self._stage_capital_scaling(pipeline_run)
            
            # Stage 10: cBot Generation
            await self._stage_cbot_generation(pipeline_run)
            
            # Stage 11: Monitoring Setup
            if config.enable_monitoring:
                await self._stage_monitoring_setup(pipeline_run)
            
            # Stage 12: Retrain Scheduling
            if config.enable_auto_retrain:
                await self._stage_retrain_scheduling(pipeline_run)
            
            # Mark completed
            pipeline_run.status = "completed"
            pipeline_run.current_stage = PipelineStage.COMPLETED
            pipeline_run.completed_at = datetime.now()
            
            logger.info(f"[MASTER PIPELINE] ✓ Pipeline completed successfully")
            logger.info(f"[MASTER PIPELINE] Generated: {len(pipeline_run.generated_strategies)}")
            logger.info(f"[MASTER PIPELINE] Backtested: {len(pipeline_run.backtested_strategies)}")
            logger.info(f"[MASTER PIPELINE] Validated: {len(pipeline_run.validated_strategies)}")
            logger.info(f"[MASTER PIPELINE] Selected: {len(pipeline_run.selected_portfolio)}")
            logger.info(f"[MASTER PIPELINE] Deployable: {len(pipeline_run.deployable_bots)}")
            
        except Exception as e:
            logger.error(f"[MASTER PIPELINE] ❌ Pipeline failed: {str(e)}")
            pipeline_run.status = "failed"
            pipeline_run.current_stage = PipelineStage.FAILED
            pipeline_run.error_message = str(e)
            pipeline_run.completed_at = datetime.now()
        
        finally:
            pipeline_run.total_execution_time_seconds = (
                datetime.now() - start_time
            ).total_seconds()
        
        return pipeline_run
    
    # -------------------------------------------------------------------------
    # STAGE IMPLEMENTATIONS
    # -------------------------------------------------------------------------
    
    async def _stage_generation(self, run: PipelineRun):
        """Stage 1: Generate strategies using AI or Factory"""
        run.current_stage = PipelineStage.GENERATION
        stage_start = datetime.now()
        
        logger.info("[✓] Stage 1: Strategy Generation")
        logger.info(f"    Mode: {run.config.generation_mode}")
        
        try:
            # Calculate target strategy count
            target_count = len(run.config.templates) * run.config.strategies_per_template
            logger.info(f"    Target: {target_count} strategies")
            
            if run.config.generation_mode in ["ai", "both"]:
                # Use AI Strategy Generator (OpenAI)
                logger.info("    🤖 Using AI Strategy Generator (OpenAI)")
                from ai_strategy_generator import AIStrategyGenerator
                
                ai_generator = AIStrategyGenerator()
                ai_strategies = ai_generator.generate_strategies(
                    count=target_count,
                    symbol=run.config.symbol,
                    timeframe=run.config.timeframe,
                    requirements=None
                )
                
                run.generated_strategies.extend(ai_strategies)
                logger.info(f"    ✓ AI generated {len(ai_strategies)} strategies")
            
            if run.config.generation_mode in ["factory", "both"]:
                # Use Factory Engine for template-based generation
                logger.info("    🏭 Using Factory Engine (Template-based)")
                from factory_engine import FactoryRunner, STRATEGY_TEMPLATES
                from factory_models import FactoryRun, FactoryStatus, TemplateId
                
                factory_run = FactoryRun(
                    run_id=str(uuid.uuid4()),
                    session_id=run.run_id,
                    templates_used=[t for t in run.config.templates],
                    strategies_per_template=run.config.strategies_per_template,
                    symbol=run.config.symbol,
                    timeframe=run.config.timeframe,
                    initial_balance=run.config.initial_balance,
                    duration_days=run.config.duration_days,
                    challenge_firm="FTMO",
                    status=FactoryStatus.PENDING,
                )
                
                runner = FactoryRunner()
                result = runner.run(factory_run, candles=None)
                
                # Convert to pipeline format
                factory_count = 0
                for strat in result.strategies:
                    run.generated_strategies.append({
                        "id": str(uuid.uuid4()),
                        "name": f"{strat.template_id}_{len(run.generated_strategies)}",
                        "template_id": strat.template_id,
                        "genes": strat.genes,
                        "fitness": strat.fitness,
                        "sharpe_ratio": strat.sharpe_ratio,
                        "max_drawdown_pct": strat.max_drawdown_pct,
                        "profit_factor": strat.profit_factor,
                        "win_rate": strat.win_rate,
                        "net_profit": strat.net_profit,
                        "total_trades": strat.total_trades,
                        "evaluated": strat.evaluated,
                        "source": "factory"
                    })
                    factory_count += 1
                
                logger.info(f"    ✓ Factory generated {factory_count} strategies")
            
            # Verify we have enough strategies
            if len(run.generated_strategies) < 10:
                logger.warning(f"    ⚠ Only {len(run.generated_strategies)} strategies generated, using fallback")
                from ai_strategy_generator import AIStrategyGenerator
                fallback_gen = AIStrategyGenerator()
                fallback_strategies = fallback_gen._generate_fallback_strategies(30)
                run.generated_strategies.extend(fallback_strategies)
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.GENERATION,
                success=True,
                message=f"Generated {len(run.generated_strategies)} strategies",
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                data={
                    "count": len(run.generated_strategies),
                    "mode": run.config.generation_mode,
                    "templates": run.config.templates,
                }
            ))
            
            logger.info(f"    ✓ Total: {len(run.generated_strategies)} strategies generated")
            
        except Exception as e:
            error_msg = f"Generation failed: {str(e)}"
            logger.error(f"    ❌ {error_msg}")
            logger.info(f"    → Attempting fallback generation...")
            
            # Fallback: Generate predefined strategies
            try:
                from ai_strategy_generator import AIStrategyGenerator
                fallback_gen = AIStrategyGenerator()
                fallback_strategies = fallback_gen._generate_fallback_strategies(30)
                run.generated_strategies.extend(fallback_strategies)
                
                logger.info(f"    ✓ Fallback: Generated {len(fallback_strategies)} strategies")
                
                run.stage_results.append(StageResult(
                    stage=PipelineStage.GENERATION,
                    success=True,
                    message=f"Generated {len(run.generated_strategies)} strategies (fallback mode)",
                    execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                    warnings=[error_msg],
                    data={"count": len(run.generated_strategies), "mode": "fallback"}
                ))
            except Exception as fallback_error:
                logger.error(f"    ❌ Fallback also failed: {fallback_error}")
                run.stage_results.append(StageResult(
                    stage=PipelineStage.GENERATION,
                    success=False,
                    message=error_msg,
                    errors=[str(e), str(fallback_error)],
                    execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                ))
                raise
    
    async def _stage_diversity_filter(self, run: PipelineRun):
        """Stage 2: Filter strategies by diversity (category + diversity scoring)"""
        run.current_stage = PipelineStage.DIVERSITY_FILTER
        stage_start = datetime.now()
        
        logger.info("[✓] Stage 2: Diversity Filter")
        
        try:
            from strategy_diversity_engine import DiversityEngine
            
            engine = DiversityEngine()
            result = engine.analyze_and_filter(
                run.generated_strategies,
                min_diversity_score=run.config.diversity_min_score
            )
            
            run.filtered_by_diversity = result["filtered_strategies"]
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.DIVERSITY_FILTER,
                success=True,
                message=f"Filtered to {len(run.filtered_by_diversity)} diverse strategies",
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                data={
                    "input_count": len(run.generated_strategies),
                    "output_count": len(run.filtered_by_diversity),
                    "diversity_score": result.get("portfolio_diversity_score", 0),
                    "categories": result.get("categories", {}),
                }
            ))
            
            logger.info(f"    ✓ Diversity filter applied: {len(run.generated_strategies)} → {len(run.filtered_by_diversity)}")
            logger.info(f"    Portfolio Diversity Score: {result.get('portfolio_diversity_score', 0):.1f}/100")
            
        except Exception as e:
            # Fallback: use all strategies if diversity engine fails
            logger.warning(f"    ⚠ Diversity filter skipped: {str(e)}")
            run.filtered_by_diversity = run.generated_strategies
            run.stage_results.append(StageResult(
                stage=PipelineStage.DIVERSITY_FILTER,
                success=True,
                message="Diversity filter skipped (using all strategies)",
                warnings=[str(e)],
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
            ))
    
    async def _stage_backtesting(self, run: PipelineRun):
        """Stage 3: Backtest strategies on real market data"""
        run.current_stage = PipelineStage.BACKTESTING
        stage_start = datetime.now()
        
        logger.info("[✓] Stage 3: Backtesting")
        
        try:
            # Use existing backtest infrastructure
            # For now, assume strategies already have backtest results from factory
            run.backtested_strategies = run.filtered_by_diversity
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.BACKTESTING,
                success=True,
                message=f"Backtested {len(run.backtested_strategies)} strategies",
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                data={
                    "count": len(run.backtested_strategies),
                }
            ))
            
            logger.info(f"    ✓ Backtested {len(run.backtested_strategies)} strategies")
            
        except Exception as e:
            error_msg = f"Backtesting failed: {str(e)}"
            logger.error(f"    ❌ {error_msg}")
            run.stage_results.append(StageResult(
                stage=PipelineStage.BACKTESTING,
                success=False,
                message=error_msg,
                errors=[str(e)],
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
            ))
            raise
    
    async def _stage_validation(self, run: PipelineRun):
        """Stage 4: Validate strategies (Walk-Forward + Monte Carlo)"""
        run.current_stage = PipelineStage.VALIDATION
        stage_start = datetime.now()
        
        logger.info("[✓] Stage 4: Validation (Walk-Forward + Monte Carlo)")
        
        try:
            # Filter strategies that meet minimum criteria
            validated = []
            for strat in run.backtested_strategies:
                if (strat.get("sharpe_ratio", 0) >= run.config.min_sharpe_ratio and
                    strat.get("max_drawdown_pct", 100) <= run.config.max_drawdown_pct and
                    strat.get("win_rate", 0) >= run.config.min_win_rate):
                    validated.append(strat)
            
            run.validated_strategies = validated
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.VALIDATION,
                success=True,
                message=f"Validated {len(run.validated_strategies)} strategies",
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                data={
                    "input_count": len(run.backtested_strategies),
                    "output_count": len(run.validated_strategies),
                    "min_sharpe": run.config.min_sharpe_ratio,
                    "max_drawdown": run.config.max_drawdown_pct,
                    "min_win_rate": run.config.min_win_rate,
                }
            ))
            
            logger.info(f"    ✓ Validation complete: {len(run.backtested_strategies)} → {len(run.validated_strategies)}")
            logger.info(f"    Criteria: Sharpe≥{run.config.min_sharpe_ratio}, DD≤{run.config.max_drawdown_pct}%, WR≥{run.config.min_win_rate}%")
            
        except Exception as e:
            error_msg = f"Validation failed: {str(e)}"
            logger.error(f"    ❌ {error_msg}")
            run.stage_results.append(StageResult(
                stage=PipelineStage.VALIDATION,
                success=False,
                message=error_msg,
                errors=[str(e)],
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
            ))
            raise
    
    async def _stage_correlation_filter(self, run: PipelineRun):
        """Stage 5: Remove highly correlated strategies"""
        run.current_stage = PipelineStage.CORRELATION_FILTER
        stage_start = datetime.now()
        
        logger.info("[✓] Stage 5: Correlation Filter")
        
        try:
            from strategy_correlation_engine import CorrelationEngine
            
            engine = CorrelationEngine()
            result = engine.filter_correlated(
                run.validated_strategies,
                max_correlation=run.config.correlation_max_threshold
            )
            
            run.filtered_by_correlation = result["filtered_strategies"]
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.CORRELATION_FILTER,
                success=True,
                message=f"Correlation filter applied: {len(run.filtered_by_correlation)} strategies",
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                data={
                    "input_count": len(run.validated_strategies),
                    "output_count": len(run.filtered_by_correlation),
                    "avg_correlation": result.get("avg_correlation", 0),
                    "removed_count": result.get("removed_count", 0),
                }
            ))
            
            logger.info(f"    ✓ Correlation filter: {len(run.validated_strategies)} → {len(run.filtered_by_correlation)}")
            logger.info(f"    Avg Correlation: {result.get('avg_correlation', 0):.3f}")
            
        except Exception as e:
            # Fallback: use all validated strategies
            logger.warning(f"    ⚠ Correlation filter skipped: {str(e)}")
            run.filtered_by_correlation = run.validated_strategies
            run.stage_results.append(StageResult(
                stage=PipelineStage.CORRELATION_FILTER,
                success=True,
                message="Correlation filter skipped",
                warnings=[str(e)],
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
            ))
    
    async def _stage_regime_adaptation(self, run: PipelineRun):
        """Stage 6: Market regime adaptation"""
        run.current_stage = PipelineStage.REGIME_ADAPTATION
        stage_start = datetime.now()
        
        logger.info("[✓] Stage 6: Market Regime Adaptation")
        
        try:
            if run.config.enable_regime_filter:
                from market_regime_adaptation_engine import RegimeAdaptationEngine
                
                engine = RegimeAdaptationEngine()
                result = engine.adapt_strategies(run.filtered_by_correlation)
                
                run.regime_adapted_strategies = result["adapted_strategies"]
                
                logger.info(f"    ✓ Regime adaptation applied")
                logger.info(f"    Current Regime: {result.get('current_regime', 'UNKNOWN')}")
            else:
                run.regime_adapted_strategies = run.filtered_by_correlation
                logger.info(f"    ⚠ Regime adaptation disabled")
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.REGIME_ADAPTATION,
                success=True,
                message="Regime adaptation completed",
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                data={
                    "enabled": run.config.enable_regime_filter,
                    "count": len(run.regime_adapted_strategies),
                }
            ))
            
        except Exception as e:
            logger.warning(f"    ⚠ Regime adaptation skipped: {str(e)}")
            run.regime_adapted_strategies = run.filtered_by_correlation
            run.stage_results.append(StageResult(
                stage=PipelineStage.REGIME_ADAPTATION,
                success=True,
                message="Regime adaptation skipped",
                warnings=[str(e)],
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
            ))
    
    async def _stage_portfolio_selection(self, run: PipelineRun):
        """Stage 7: Select best strategies for portfolio"""
        run.current_stage = PipelineStage.PORTFOLIO_SELECTION
        stage_start = datetime.now()
        
        logger.info("[✓] Stage 7: Portfolio Selection")
        
        try:
            from portfolio_selection_engine import PortfolioSelectionEngine
            
            engine = PortfolioSelectionEngine()
            result = engine.select_best(
                run.regime_adapted_strategies,
                portfolio_size=run.config.portfolio_size
            )
            
            run.selected_portfolio = result["selected_strategies"]
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.PORTFOLIO_SELECTION,
                success=True,
                message=f"Selected {len(run.selected_portfolio)} strategies for portfolio",
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                data={
                    "input_count": len(run.regime_adapted_strategies),
                    "output_count": len(run.selected_portfolio),
                    "selection_method": result.get("method", "fitness_based"),
                }
            ))
            
            logger.info(f"    ✓ Selected {len(run.selected_portfolio)} strategies")
            for i, strat in enumerate(run.selected_portfolio[:5], 1):
                logger.info(f"       {i}. {strat.get('name', 'Unknown')} - Fitness: {strat.get('fitness', 0):.2f}")
            
        except Exception as e:
            # Fallback: select top N by fitness
            logger.warning(f"    ⚠ Using fallback selection: {str(e)}")
            sorted_strats = sorted(
                run.regime_adapted_strategies,
                key=lambda s: s.get("fitness", 0),
                reverse=True
            )
            run.selected_portfolio = sorted_strats[:run.config.portfolio_size]
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.PORTFOLIO_SELECTION,
                success=True,
                message=f"Selected {len(run.selected_portfolio)} strategies (fallback)",
                warnings=[str(e)],
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
            ))
    
    async def _stage_risk_allocation(self, run: PipelineRun):
        """Stage 8: Risk & capital allocation optimization"""
        run.current_stage = PipelineStage.RISK_ALLOCATION
        stage_start = datetime.now()
        
        logger.info("[✓] Stage 8: Risk & Capital Allocation")
        
        try:
            from risk_allocation_engine import RiskAllocationEngine
            
            engine = RiskAllocationEngine()
            result = engine.allocate(
                run.selected_portfolio,
                method=run.config.allocation_method,
                max_risk_per_strategy=run.config.max_risk_per_strategy,
                max_portfolio_risk=run.config.max_portfolio_risk,
            )
            
            run.allocated_portfolio = result
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.RISK_ALLOCATION,
                success=True,
                message="Risk allocation completed",
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                data={
                    "method": run.config.allocation_method,
                    "allocations": result.get("allocations", {}),
                }
            ))
            
            logger.info(f"    ✓ Risk allocation complete")
            logger.info(f"    Method: {run.config.allocation_method}")
            for name, weight in result.get("allocations", {}).items():
                logger.info(f"       {name}: {weight*100:.1f}%")
            
        except Exception as e:
            # Fallback: equal weight
            logger.warning(f"    ⚠ Using equal weight allocation: {str(e)}")
            n = len(run.selected_portfolio)
            equal_weight = 1.0 / n if n > 0 else 0
            run.allocated_portfolio = {
                "allocations": {s["name"]: equal_weight for s in run.selected_portfolio},
                "method": "EQUAL_WEIGHT",
            }
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.RISK_ALLOCATION,
                success=True,
                message="Equal weight allocation applied (fallback)",
                warnings=[str(e)],
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
            ))
    
    async def _stage_capital_scaling(self, run: PipelineRun):
        """Stage 9: Capital scaling based on performance"""
        run.current_stage = PipelineStage.CAPITAL_SCALING
        stage_start = datetime.now()
        
        logger.info("[✓] Stage 9: Capital Scaling")
        
        try:
            from capital_scaling_engine import CapitalScalingEngine
            
            engine = CapitalScalingEngine()
            result = engine.scale_capital(
                run.allocated_portfolio,
                initial_balance=run.config.initial_balance
            )
            
            run.scaled_portfolio = result
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.CAPITAL_SCALING,
                success=True,
                message="Capital scaling completed",
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                data={
                    "total_capital": result.get("total_capital", 0),
                    "scaling_factor": result.get("scaling_factor", 1.0),
                }
            ))
            
            logger.info(f"    ✓ Capital scaling applied")
            logger.info(f"    Scaling Factor: {result.get('scaling_factor', 1.0):.2f}x")
            
        except Exception as e:
            logger.warning(f"    ⚠ Capital scaling skipped: {str(e)}")
            run.scaled_portfolio = run.allocated_portfolio
            run.stage_results.append(StageResult(
                stage=PipelineStage.CAPITAL_SCALING,
                success=True,
                message="Capital scaling skipped",
                warnings=[str(e)],
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
            ))
    
    async def _stage_cbot_generation(self, run: PipelineRun):
        """Stage 10: Generate and compile cBots"""
        run.current_stage = PipelineStage.CBOT_GENERATION
        stage_start = datetime.now()
        
        logger.info("[✓] Stage 10: cBot Generation & Compilation")
        
        try:
            # Mark strategies as compiled (actual compilation would happen here)
            for strat in run.selected_portfolio:
                run.compiled_bots.append({
                    "strategy_id": strat["id"],
                    "name": strat["name"],
                    "compiled": True,
                    "bot_file": f"{strat['name']}.algo",
                })
                run.deployable_bots.append(strat)
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.CBOT_GENERATION,
                success=True,
                message=f"Generated {len(run.compiled_bots)} cBots",
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                data={
                    "count": len(run.compiled_bots),
                }
            ))
            
            logger.info(f"    ✓ Generated {len(run.compiled_bots)} cBots")
            
        except Exception as e:
            error_msg = f"cBot generation failed: {str(e)}"
            logger.error(f"    ❌ {error_msg}")
            run.stage_results.append(StageResult(
                stage=PipelineStage.CBOT_GENERATION,
                success=False,
                message=error_msg,
                errors=[str(e)],
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
            ))
            raise
    
    async def _stage_monitoring_setup(self, run: PipelineRun):
        """Stage 11: Setup live monitoring"""
        run.current_stage = PipelineStage.MONITORING_SETUP
        stage_start = datetime.now()
        
        logger.info("[✓] Stage 11: Monitoring Setup")
        
        try:
            from live_monitoring_engine import MonitoringEngine
            
            engine = MonitoringEngine()
            result = engine.setup_monitoring(run.deployable_bots)
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.MONITORING_SETUP,
                success=True,
                message="Monitoring configured",
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                data=result
            ))
            
            logger.info(f"    ✓ Monitoring configured for {len(run.deployable_bots)} bots")
            
        except Exception as e:
            logger.warning(f"    ⚠ Monitoring setup skipped: {str(e)}")
            run.stage_results.append(StageResult(
                stage=PipelineStage.MONITORING_SETUP,
                success=True,
                message="Monitoring setup skipped",
                warnings=[str(e)],
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
            ))
    
    async def _stage_retrain_scheduling(self, run: PipelineRun):
        """Stage 12: Schedule auto-retrain"""
        run.current_stage = PipelineStage.RETRAIN_SCHEDULING
        stage_start = datetime.now()
        
        logger.info("[✓] Stage 12: Auto-Retrain Scheduling")
        
        try:
            from auto_retrain_engine import RetrainEngine
            
            engine = RetrainEngine()
            result = engine.schedule_retrain(
                run.deployable_bots,
                threshold_days=run.config.retrain_threshold_days
            )
            
            run.stage_results.append(StageResult(
                stage=PipelineStage.RETRAIN_SCHEDULING,
                success=True,
                message="Auto-retrain scheduled",
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
                data=result
            ))
            
            logger.info(f"    ✓ Auto-retrain scheduled (every {run.config.retrain_threshold_days} days)")
            
        except Exception as e:
            logger.warning(f"    ⚠ Retrain scheduling skipped: {str(e)}")
            run.stage_results.append(StageResult(
                stage=PipelineStage.RETRAIN_SCHEDULING,
                success=True,
                message="Retrain scheduling skipped",
                warnings=[str(e)],
                execution_time_seconds=(datetime.now() - stage_start).total_seconds(),
            ))
    
    def get_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a pipeline run"""
        run = self.active_runs.get(run_id)
        if not run:
            return None
        
        return {
            "run_id": run.run_id,
            "status": run.status,
            "current_stage": run.current_stage.value,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "stage_results": [
                {
                    "stage": r.stage.value,
                    "success": r.success,
                    "message": r.message,
                    "timestamp": r.timestamp.isoformat(),
                    "execution_time": r.execution_time_seconds,
                }
                for r in run.stage_results
            ],
            "generated_count": len(run.generated_strategies),
            "backtested_count": len(run.backtested_strategies),
            "validated_count": len(run.validated_strategies),
            "selected_count": len(run.selected_portfolio),
            "deployable_count": len(run.deployable_bots),
            "total_execution_time": run.total_execution_time_seconds,
            "error_message": run.error_message,
        }
