"""
Fixed Pipeline Router
Single endpoint to run the complete fixed pipeline.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from fixed_pipeline_controller import (
    FixedPipelineController,
    PipelineConfig,
    PipelineRun
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline-v2", tags=["Fixed Pipeline"])

# Global controller instance
controller = None


def init_fixed_pipeline_router(db_client):
    """Initialize router with database"""
    global controller
    controller = FixedPipelineController(db_client)
    logger.info("✅ Fixed Pipeline Router initialized")


class PipelineRequest(BaseModel):
    """Request to run pipeline"""
    num_strategies: int = 5
    symbol: str = "EURUSD"
    timeframe: str = "M1"
    initial_balance: float = 10000.0
    backtest_days: int = 365
    portfolio_size: int = 5


class PipelineResponse(BaseModel):
    """Pipeline execution response"""
    success: bool
    run_id: str
    status: str
    message: str
    
    # Counts at each stage
    generated_count: int
    safe_count: int
    compiled_count: int
    backtested_count: int
    optimized_count: int
    validated_count: int
    scored_count: int
    selected_count: int
    cbot_count: int
    
    # Results
    stage_results: List[Dict[str, Any]]
    selected_strategies: List[Dict[str, Any]]
    deployment_package: Dict[str, Any]
    
    # Execution stats
    total_execution_time: float
    error_message: Optional[str]


@router.post("/run", response_model=PipelineResponse)
async def run_fixed_pipeline(request: PipelineRequest):
    """
    Execute the FIXED end-to-end pipeline.
    
    Pipeline Order:
    1. Generate strategies (Intelligent Generator)
    2. Inject safety controls
    3. Validate compilation readiness
    4. Backtest with RealBacktester on M1 data (NO MOCK DATA)
    5. Optimize parameters
    6. Validate with Walk-Forward + Monte Carlo
    7. Score and rank by composite score
    8. Select best strategies
    9. Generate cBot code
    10. Prepare deployment package
    
    Returns:
        Complete pipeline results with deployable strategies
    """
    if controller is None:
        raise HTTPException(status_code=500, detail="Pipeline controller not initialized")
    
    try:
        logger.info(f"🚀 Pipeline run requested: {request.symbol}, {request.num_strategies} strategies")
        
        # Create config
        config = PipelineConfig(
            num_strategies=request.num_strategies,
            symbol=request.symbol,
            timeframe=request.timeframe,
            initial_balance=request.initial_balance,
            backtest_days=request.backtest_days,
            portfolio_size=request.portfolio_size
        )
        
        # Run pipeline
        run = await controller.run_pipeline(config)
        
        # Build response
        response = PipelineResponse(
            success=run.status == "completed",
            run_id=run.run_id,
            status=run.status,
            message=f"Pipeline {'completed' if run.status == 'completed' else 'failed'}",
            generated_count=len(run.generated_strategies),
            safe_count=len(run.safe_strategies),
            compiled_count=len(run.compiled_strategies),
            backtested_count=len(run.backtested_strategies),
            optimized_count=len(run.optimized_strategies),
            validated_count=len(run.validated_strategies),
            scored_count=len(run.scored_strategies),
            selected_count=len(run.selected_strategies),
            cbot_count=len(run.final_cbots),
            stage_results=[
                {
                    "stage": r.stage.value,
                    "success": r.success,
                    "message": r.message,
                    "execution_time": r.execution_time_seconds,
                    "data": r.data,
                    "errors": r.errors
                }
                for r in run.stage_results
            ],
            selected_strategies=run.final_cbots,  # Return strategies with cBot code attached
            deployment_package=run.deployment_package,
            total_execution_time=run.total_execution_time_seconds,
            error_message=run.error_message
        )
        
        logger.info(f"✅ Pipeline completed: {run.run_id}")
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Pipeline execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")


@router.get("/status/{run_id}")
async def get_pipeline_status(run_id: str):
    """Get status of a running pipeline"""
    if controller is None:
        raise HTTPException(status_code=500, detail="Pipeline controller not initialized")
    
    status = controller.get_run_status(run_id)
    
    if status is None:
        raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")
    
    return status


@router.get("/health")
async def pipeline_health():
    """Check if pipeline is ready"""
    return {
        "status": "healthy" if controller is not None else "not_initialized",
        "controller": "FixedPipelineController",
        "version": "2.0",
        "features": [
            "Real data (M1 SSOT)",
            "No mock data",
            "No synthetic candles",
            "RealBacktester integration",
            "10-stage pipeline"
        ]
    }
