"""
Master Pipeline API Router
Exposes the master pipeline controller via REST API.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from master_pipeline_controller import (
    MasterPipelineController,
    PipelineConfig,
    PipelineRun
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["Master Pipeline"])

# Global pipeline controller instance
controller = MasterPipelineController()


# Request/Response Models
class MasterPipelineRequest(BaseModel):
    """Request to run master pipeline"""
    # Generation config
    generation_mode: str = "factory"
    templates: List[str] = ["EMA_CROSSOVER", "RSI_MEAN_REVERSION", "MACD_TREND"]
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
    allocation_method: str = "MAX_SHARPE"
    
    # Advanced options
    enable_regime_filter: bool = True
    enable_monitoring: bool = True
    enable_auto_retrain: bool = True
    retrain_threshold_days: int = 30


class PipelineStageInfo(BaseModel):
    """Information about a pipeline stage"""
    stage: str
    success: bool
    message: str
    timestamp: str
    execution_time: float


class MasterPipelineResponse(BaseModel):
    """Response from master pipeline execution"""
    success: bool
    run_id: str
    status: str
    current_stage: str
    started_at: str
    completed_at: Optional[str]
    
    # Stage results
    stage_results: List[PipelineStageInfo]
    
    # Summary metrics
    generated_count: int
    backtested_count: int
    validated_count: int
    selected_count: int
    deployable_count: int
    
    # Outputs
    selected_portfolio: List[Dict[str, Any]]
    portfolio_metrics: Dict[str, Any]
    deployable_bots: List[Dict[str, Any]]
    
    # Execution
    total_execution_time: float
    error_message: Optional[str]


class PipelineStatusResponse(BaseModel):
    """Status response for a running pipeline"""
    run_id: str
    status: str
    current_stage: str
    started_at: str
    completed_at: Optional[str]
    stage_results: List[Dict[str, Any]]
    generated_count: int
    backtested_count: int
    validated_count: int
    selected_count: int
    deployable_count: int
    total_execution_time: float
    error_message: Optional[str]


# Endpoints

@router.post("/master-run", response_model=MasterPipelineResponse)
async def run_master_pipeline(
    request: MasterPipelineRequest,
    background_tasks: BackgroundTasks = None
):
    """
    Execute the complete master pipeline.
    
    This endpoint orchestrates the full trading strategy pipeline:
    1. Generation (AI/Factory)
    2. Diversity Filter
    3. Backtesting
    4. Validation (Walk-Forward + Monte Carlo)
    5. Correlation Filter
    6. Market Regime Adaptation
    7. Portfolio Selection
    8. Risk & Capital Allocation
    9. Capital Scaling
    10. cBot Generation & Compilation
    11. Monitoring Setup
    12. Auto-Retrain Scheduling
    
    Returns complete pipeline results with deployable strategies.
    """
    try:
        logger.info("[MASTER PIPELINE API] Received pipeline run request")
        logger.info(f"[MASTER PIPELINE API] Config: {request.dict()}")
        
        # Create pipeline config
        config = PipelineConfig(
            generation_mode=request.generation_mode,
            templates=request.templates,
            strategies_per_template=request.strategies_per_template,
            symbol=request.symbol,
            timeframe=request.timeframe,
            initial_balance=request.initial_balance,
            duration_days=request.duration_days,
            diversity_min_score=request.diversity_min_score,
            correlation_max_threshold=request.correlation_max_threshold,
            min_sharpe_ratio=request.min_sharpe_ratio,
            max_drawdown_pct=request.max_drawdown_pct,
            min_win_rate=request.min_win_rate,
            portfolio_size=request.portfolio_size,
            max_risk_per_strategy=request.max_risk_per_strategy,
            max_portfolio_risk=request.max_portfolio_risk,
            allocation_method=request.allocation_method,
            enable_regime_filter=request.enable_regime_filter,
            enable_monitoring=request.enable_monitoring,
            enable_auto_retrain=request.enable_auto_retrain,
            retrain_threshold_days=request.retrain_threshold_days,
        )
        
        # Run pipeline
        pipeline_run = await controller.run_full_pipeline(config)
        
        # Build response
        stage_results = [
            PipelineStageInfo(
                stage=r.stage.value,
                success=r.success,
                message=r.message,
                timestamp=r.timestamp.isoformat(),
                execution_time=r.execution_time_seconds,
            )
            for r in pipeline_run.stage_results
        ]
        
        response = MasterPipelineResponse(
            success=(pipeline_run.status == "completed"),
            run_id=pipeline_run.run_id,
            status=pipeline_run.status,
            current_stage=pipeline_run.current_stage.value,
            started_at=pipeline_run.started_at.isoformat(),
            completed_at=pipeline_run.completed_at.isoformat() if pipeline_run.completed_at else None,
            stage_results=stage_results,
            generated_count=len(pipeline_run.generated_strategies),
            backtested_count=len(pipeline_run.backtested_strategies),
            validated_count=len(pipeline_run.validated_strategies),
            selected_count=len(pipeline_run.selected_portfolio),
            deployable_count=len(pipeline_run.deployable_bots),
            selected_portfolio=pipeline_run.selected_portfolio,
            portfolio_metrics=pipeline_run.portfolio_metrics,
            deployable_bots=pipeline_run.deployable_bots,
            total_execution_time=pipeline_run.total_execution_time_seconds,
            error_message=pipeline_run.error_message,
        )
        
        logger.info(f"[MASTER PIPELINE API] ✓ Pipeline completed: {pipeline_run.status}")
        logger.info(f"[MASTER PIPELINE API] Deployable bots: {len(pipeline_run.deployable_bots)}")
        
        return response
        
    except Exception as e:
        logger.error(f"[MASTER PIPELINE API] ❌ Pipeline failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")


@router.get("/status/{run_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(run_id: str):
    """
    Get the status of a pipeline run.
    
    Returns real-time status of the pipeline execution including:
    - Current stage
    - Completed stages
    - Intermediate results
    - Execution time
    """
    try:
        status = controller.get_run_status(run_id)
        
        if not status:
            raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")
        
        return PipelineStatusResponse(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MASTER PIPELINE API] Failed to get status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs", response_model=List[Dict[str, Any]])
async def list_pipeline_runs():
    """
    List all active pipeline runs.
    
    Returns summary information for all pipeline runs in memory.
    """
    try:
        runs = []
        for run_id, run in controller.active_runs.items():
            runs.append({
                "run_id": run_id,
                "status": run.status,
                "current_stage": run.current_stage.value,
                "started_at": run.started_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "deployable_count": len(run.deployable_bots),
            })
        
        return runs
        
    except Exception as e:
        logger.error(f"[MASTER PIPELINE API] Failed to list runs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def pipeline_health():
    """
    Health check endpoint for the master pipeline.
    """
    return {
        "status": "healthy",
        "service": "master_pipeline_controller",
        "active_runs": len(controller.active_runs),
        "version": "2.2.0"
    }
