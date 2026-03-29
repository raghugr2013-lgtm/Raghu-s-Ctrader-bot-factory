"""
Unified Pipeline API Router
Exposes unified pipeline endpoints for all entry points.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from unified_pipeline import (
    UnifiedPipeline,
    EntryPoint,
    Strategy,
    PipelineStage
)

router = APIRouter(prefix="/api/pipeline", tags=["Unified Pipeline"])

# Global pipeline instance
pipeline = UnifiedPipeline()


# Request Models
class StrategySubmission(BaseModel):
    """Strategy submission from any entry point"""
    name: str
    code: str
    entry_point: str  # "ai_generation", "analyzer", or "discovery"
    description: Optional[str] = ""
    metadata: Optional[Dict[str, Any]] = {}


class StrategyResponse(BaseModel):
    """Strategy response"""
    id: str
    name: str
    entry_point: str
    current_stage: str
    created_at: datetime
    updated_at: datetime
    
    # Progress
    safety_injected: bool
    validated: bool
    backtest_completed: bool
    monte_carlo_completed: bool
    forward_test_completed: bool
    
    # Results
    overall_score: Optional[float] = None
    rank: Optional[int] = None
    deployed: bool
    
    # Status
    errors: List[str]
    warnings: List[str]
    logs: List[str]


class LibraryStrategy(BaseModel):
    """Strategy in library"""
    id: str
    name: str
    description: str
    entry_point: str
    overall_score: float
    rank: Optional[int]
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    deployed: bool
    created_at: datetime


# Endpoints

@router.post("/submit", response_model=StrategyResponse)
async def submit_strategy(
    submission: StrategySubmission,
    background_tasks: BackgroundTasks
):
    """
    Submit strategy to unified pipeline (any entry point).
    
    Entry Points:
    - ai_generation: From AI bot generator
    - analyzer: From existing bot analyzer
    - discovery: From GitHub discovery
    
    Pipeline automatically processes through all stages.
    """
    try:
        # Validate entry point
        entry_point_map = {
            "ai_generation": EntryPoint.AI_GENERATION,
            "analyzer": EntryPoint.ANALYZER,
            "discovery": EntryPoint.DISCOVERY
        }
        
        if submission.entry_point not in entry_point_map:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid entry point. Must be: {list(entry_point_map.keys())}"
            )
        
        entry_point = entry_point_map[submission.entry_point]
        
        # Process strategy through pipeline (async in background)
        background_tasks.add_task(
            pipeline.process_strategy,
            code=submission.code,
            name=submission.name,
            entry_point=entry_point,
            description=submission.description,
            **submission.metadata
        )
        
        # Return immediate response
        return {
            "id": "processing",
            "name": submission.name,
            "entry_point": submission.entry_point,
            "current_stage": "received",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "safety_injected": False,
            "validated": False,
            "backtest_completed": False,
            "monte_carlo_completed": False,
            "forward_test_completed": False,
            "overall_score": None,
            "rank": None,
            "deployed": False,
            "errors": [],
            "warnings": [],
            "logs": [f"Strategy received via {submission.entry_point}"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy/{strategy_id}", response_model=StrategyResponse)
async def get_strategy_status(strategy_id: str):
    """
    Get strategy status and progress through pipeline.
    """
    strategy = pipeline.get_strategy(strategy_id)
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return _strategy_to_response(strategy)


@router.get("/strategies", response_model=List[StrategyResponse])
async def get_all_strategies():
    """
    Get all strategies currently in pipeline.
    """
    strategies = pipeline.get_all_strategies()
    return [_strategy_to_response(s) for s in strategies]


@router.get("/library", response_model=List[LibraryStrategy])
async def get_strategy_library(
    sort_by: str = "score",  # score, return, sharpe, date
    limit: int = 50
):
    """
    Get strategies from library, sorted by performance.
    """
    strategies = pipeline.get_all_strategies()
    
    # Filter completed strategies only
    library_strategies = [
        s for s in strategies 
        if s.current_stage == PipelineStage.COMPLETED
    ]
    
    # Sort
    if sort_by == "score":
        library_strategies.sort(key=lambda x: x.metrics.overall_score, reverse=True)
    elif sort_by == "return":
        library_strategies.sort(key=lambda x: x.metrics.total_return, reverse=True)
    elif sort_by == "sharpe":
        library_strategies.sort(key=lambda x: x.metrics.sharpe_ratio, reverse=True)
    elif sort_by == "date":
        library_strategies.sort(key=lambda x: x.created_at, reverse=True)
    
    # Limit
    library_strategies = library_strategies[:limit]
    
    return [_strategy_to_library_response(s) for s in library_strategies]


@router.get("/deployed", response_model=Optional[StrategyResponse])
async def get_deployed_strategy():
    """
    Get currently deployed strategy in live paper trading.
    """
    strategy = pipeline.get_deployed_strategy()
    
    if not strategy:
        return None
    
    return _strategy_to_response(strategy)


@router.get("/best", response_model=Optional[LibraryStrategy])
async def get_best_strategy():
    """
    Get best performing strategy from library.
    """
    strategies = pipeline.get_all_strategies()
    
    # Filter completed strategies
    completed = [
        s for s in strategies 
        if s.current_stage == PipelineStage.COMPLETED
    ]
    
    if not completed:
        return None
    
    # Sort by score
    completed.sort(key=lambda x: x.metrics.overall_score, reverse=True)
    
    return _strategy_to_library_response(completed[0])


@router.post("/deploy/{strategy_id}")
async def deploy_strategy(strategy_id: str):
    """
    Manually deploy a specific strategy to live trading.
    """
    strategy = pipeline.get_strategy(strategy_id)
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    if strategy.current_stage != PipelineStage.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Strategy must complete pipeline before deployment"
        )
    
    # Deploy
    await pipeline._deploy_to_live(strategy)
    await pipeline._setup_monitoring(strategy)
    
    return {
        "success": True,
        "message": f"Strategy {strategy.name} deployed to live trading",
        "deployment_id": strategy.deployment_id
    }


@router.get("/stats")
async def get_pipeline_stats():
    """
    Get overall pipeline statistics.
    """
    strategies = pipeline.get_all_strategies()
    
    # Count by stage
    stage_counts = {}
    for stage in PipelineStage:
        stage_counts[stage.value] = sum(
            1 for s in strategies if s.current_stage == stage
        )
    
    # Count by entry point
    entry_counts = {}
    for entry in EntryPoint:
        entry_counts[entry.value] = sum(
            1 for s in strategies if s.entry_point == entry
        )
    
    # Performance stats
    completed = [s for s in strategies if s.current_stage == PipelineStage.COMPLETED]
    
    if completed:
        avg_score = sum(s.metrics.overall_score for s in completed) / len(completed)
        avg_return = sum(s.metrics.total_return for s in completed) / len(completed)
        avg_sharpe = sum(s.metrics.sharpe_ratio for s in completed) / len(completed)
    else:
        avg_score = avg_return = avg_sharpe = 0
    
    return {
        "total_strategies": len(strategies),
        "by_stage": stage_counts,
        "by_entry_point": entry_counts,
        "completed": len(completed),
        "deployed": sum(1 for s in strategies if s.deployed),
        "average_score": round(avg_score, 2),
        "average_return": round(avg_return, 2),
        "average_sharpe": round(avg_sharpe, 2)
    }


# Helper functions

def _strategy_to_response(strategy: Strategy) -> Dict[str, Any]:
    """Convert Strategy to API response"""
    return {
        "id": strategy.id,
        "name": strategy.name,
        "entry_point": strategy.entry_point.value,
        "current_stage": strategy.current_stage.value,
        "created_at": strategy.created_at,
        "updated_at": strategy.updated_at,
        "safety_injected": strategy.safety_injected,
        "validated": strategy.validated,
        "backtest_completed": strategy.backtest_completed,
        "monte_carlo_completed": strategy.monte_carlo_completed,
        "forward_test_completed": strategy.forward_test_completed,
        "overall_score": strategy.metrics.overall_score if strategy.metrics.overall_score > 0 else None,
        "rank": strategy.metrics.rank,
        "deployed": strategy.deployed,
        "errors": strategy.errors,
        "warnings": strategy.warnings,
        "logs": strategy.logs
    }


def _strategy_to_library_response(strategy: Strategy) -> Dict[str, Any]:
    """Convert Strategy to Library response"""
    return {
        "id": strategy.id,
        "name": strategy.name,
        "description": strategy.description,
        "entry_point": strategy.entry_point.value,
        "overall_score": strategy.metrics.overall_score,
        "rank": strategy.metrics.rank,
        "total_return": strategy.metrics.total_return,
        "sharpe_ratio": strategy.metrics.sharpe_ratio,
        "max_drawdown": strategy.metrics.max_drawdown,
        "win_rate": strategy.metrics.win_rate,
        "deployed": strategy.deployed,
        "created_at": strategy.created_at
    }
