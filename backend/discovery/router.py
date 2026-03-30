"""
Discovery API Router - Phase 5
REST API endpoints for bot discovery system
"""

import os
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field

from .pipeline import DiscoveryPipeline, create_pipeline, PipelineResult
from .database import StrategyLibraryDB, create_strategy_db
from .scoring_engine import create_scoring_engine

# Import analyzer for code processing
from analyzer.csharp_parser import CSharpBotParser
from analyzer.strategy_parser import StrategyParser
from analyzer.refinement_engine import create_refinement_engine
from analyzer.improved_bot_generator import create_bot_generator


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/discovery", tags=["discovery"])


# ==================== REQUEST MODELS ====================

class DiscoverBotsRequest(BaseModel):
    """Request to start bot discovery"""
    max_repos: int = Field(default=10, ge=1, le=50, description="Maximum repositories to search")
    max_bots_per_repo: int = Field(default=3, ge=1, le=10, description="Maximum bots per repository")
    min_stars: int = Field(default=10, ge=0, description="Minimum stars filter")
    github_token: Optional[str] = Field(default=None, description="GitHub API token (optional)")
    generate_bots: bool = Field(default=True, description="Generate optimized bot code")
    save_to_db: bool = Field(default=True, description="Save results to database")


class ProcessRepoRequest(BaseModel):
    """Request to process a specific repository"""
    repo_url: str = Field(..., description="GitHub repository URL")
    github_token: Optional[str] = Field(default=None, description="GitHub API token")


class ProcessCodeRequest(BaseModel):
    """Request to process code directly"""
    code: str = Field(..., min_length=50, description="C# cBot code to process")
    strategy_name: Optional[str] = Field(default=None, description="Custom strategy name")
    save_to_db: bool = Field(default=False, description="Save to database")


# ==================== RESPONSE MODELS ====================

class DiscoverBotsResponse(BaseModel):
    """Response from discovery operation"""
    success: bool
    message: str
    total_fetched: int
    total_approved: int
    total_rejected: int
    total_errors: int
    approved_strategies: List[Dict[str, Any]]
    errors: List[str]
    duration_seconds: float


class StrategyListResponse(BaseModel):
    """Response for strategy list"""
    success: bool
    total: int
    strategies: List[Dict[str, Any]]


class StrategyDetailResponse(BaseModel):
    """Response for single strategy detail"""
    success: bool
    strategy: Optional[Dict[str, Any]]
    message: str = ""


class StatisticsResponse(BaseModel):
    """Response for library statistics"""
    success: bool
    statistics: Dict[str, Any]


class ProcessCodeResponse(BaseModel):
    """Response for code processing"""
    success: bool
    strategy_name: str
    score: Dict[str, Any]
    grade: str
    status: str
    issues_count: int
    changes_count: int
    improved_strategy: Dict[str, Any]
    generated_bot: Optional[Dict[str, Any]] = None
    saved: bool = False
    strategy_id: Optional[str] = None


# ==================== BACKGROUND TASK STORAGE ====================
# Simple in-memory storage for background task results
_discovery_tasks: Dict[str, Dict] = {}

async def _run_discovery_background(job_id: str, request: DiscoverBotsRequest):
    """Background task for discovery operation"""
    try:
        # Update status to running
        _discovery_tasks[job_id]["status"] = "running"
        _discovery_tasks[job_id]["message"] = "Discovery in progress..."
        
        # Create pipeline
        pipeline = create_pipeline(
            github_token=request.github_token or os.environ.get('GITHUB_TOKEN'),
            min_stars=request.min_stars,
            generate_bots=request.generate_bots,
            save_to_db=request.save_to_db
        )
        
        # Run discovery
        result = await pipeline.run(
            max_repos=request.max_repos,
            max_bots_per_repo=request.max_bots_per_repo
        )
        
        # Update task with results
        _discovery_tasks[job_id].update({
            "status": "completed",
            "message": f"Discovery complete. Found {result.total_fetched} bots, approved {result.total_approved}.",
            "total_fetched": result.total_fetched,
            "total_approved": result.total_approved,
            "total_rejected": result.total_rejected,
            "total_errors": result.total_errors,
            "approved_strategies": result.approved_strategies,
            "errors": result.errors[:10],
            "duration_seconds": result.duration_seconds
        })
        
        logger.info(f"Discovery job {job_id} complete: {result.total_approved} approved")
        
    except Exception as e:
        logger.error(f"Discovery job {job_id} failed: {str(e)}")
        _discovery_tasks[job_id].update({
            "status": "failed",
            "message": f"Discovery failed: {str(e)}",
            "error": str(e)
        })


# ==================== ENDPOINTS ====================

@router.post("/discover-bots")
async def discover_bots(request: DiscoverBotsRequest, background_tasks: BackgroundTasks):
    """
    Start bot discovery from GitHub (Async)
    
    Searches GitHub for cTrader/cAlgo bots, analyzes them,
    and stores high-quality strategies.
    
    Returns immediately with a job_id. Use /discovery/status/{job_id}
    to check progress and retrieve results.
    """
    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Initialize task tracking
        _discovery_tasks[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "message": "Discovery job queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_fetched": 0,
            "total_approved": 0,
            "total_rejected": 0,
            "total_errors": 0,
            "approved_strategies": [],
            "errors": [],
            "duration_seconds": 0
        }
        
        # Start background task
        background_tasks.add_task(_run_discovery_background, job_id, request)
        
        logger.info(f"Discovery job {job_id} started with max_repos={request.max_repos}")
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "Discovery job started. Use /discovery/status/{job_id} to check progress.",
            "status_url": f"/api/discovery/status/{job_id}"
        }
        
    except Exception as e:
        logger.error(f"Failed to start discovery: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start discovery: {str(e)}")


@router.get("/status/{job_id}")
async def get_discovery_status(job_id: str):
    """
    Check status of a discovery job
    
    Returns current status and results (if complete)
    """
    if job_id not in _discovery_tasks:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = _discovery_tasks[job_id]
    
    return {
        "success": True,
        "job_id": job_id,
        "status": job["status"],  # pending, running, completed, failed
        "message": job["message"],
        "created_at": job["created_at"],
        "total_fetched": job["total_fetched"],
        "total_approved": job["total_approved"],
        "total_rejected": job["total_rejected"],
        "total_errors": job["total_errors"],
        "approved_strategies": job["approved_strategies"] if job["status"] == "completed" else [],
        "errors": job.get("errors", []),
        "duration_seconds": job["duration_seconds"],
        "error": job.get("error")  # Present if status is "failed"
    }


@router.post("/process-repo")
async def process_repository(request: ProcessRepoRequest):
    """
    Process a specific GitHub repository
    
    Fetches all cBots from the repository, analyzes,
    refines, scores, and optionally stores them.
    """
    try:
        pipeline = create_pipeline(
            github_token=request.github_token or os.environ.get('GITHUB_TOKEN'),
            min_stars=0,  # Allow any repo
            generate_bots=True,
            save_to_db=True
        )
        
        result = await pipeline.process_repo(request.repo_url)
        
        return {
            "success": True,
            "repo_url": request.repo_url,
            "total_bots": result.total_fetched,
            "approved": result.total_approved,
            "rejected": result.total_rejected,
            "errors": result.total_errors,
            "approved_strategies": result.approved_strategies,
            "duration_seconds": result.duration_seconds
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to process repo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process repository: {str(e)}")


@router.post("/process-code", response_model=ProcessCodeResponse)
async def process_code(request: ProcessCodeRequest):
    """
    Process C# cBot code directly
    
    Analyzes the code, refines the strategy, generates
    an optimized bot, and scores it.
    """
    try:
        # Phase 1: Parse
        parser = CSharpBotParser()
        parsed_bot = parser.parse(request.code)
        parsed_dict = parsed_bot.to_dict()
        
        if not parsed_bot.indicators and not parsed_bot.entry_conditions:
            raise HTTPException(status_code=400, detail="No trading logic detected in code")
        
        # Phase 2: Convert to strategy
        strategy_parser = StrategyParser()
        strategy = strategy_parser.parse(parsed_bot)
        strategy_dict = strategy.to_dict()
        
        # Phase 3: Refine
        refinement_engine = create_refinement_engine()
        refinement_result = refinement_engine.refine(parsed_dict, strategy_dict)
        
        # Phase 4: Generate bot
        generator = create_bot_generator()
        generated = generator.generate(refinement_result.improved_strategy, parsed_dict)
        
        # Phase 5: Score
        scoring_engine = create_scoring_engine()
        score = scoring_engine.score(refinement_result.improved_strategy, parsed_dict)
        
        # Optional: Save to database
        strategy_id = None
        saved = False
        
        if request.save_to_db and score.status == "approved":
            db = create_strategy_db()
            save_result = await db.save_strategy(
                strategy_name=request.strategy_name or refinement_result.improved_strategy.get('name', 'Custom Bot'),
                original_code=request.code,
                parsed_data=parsed_dict,
                improved_strategy=refinement_result.improved_strategy,
                generated_bot=generated.to_dict(),
                score=score.to_dict(),
                source={
                    "repo_full_name": "user/submitted",
                    "source_url": "",
                    "description": "User submitted code"
                }
            )
            saved = save_result.get('saved', False)
            strategy_id = save_result.get('strategy_id')
            await db.close()
        
        return ProcessCodeResponse(
            success=True,
            strategy_name=refinement_result.improved_strategy.get('name', 'Unknown'),
            score=score.to_dict(),
            grade=score.grade,
            status=score.status,
            issues_count=len(refinement_result.issues),
            changes_count=len(refinement_result.changes_made),
            improved_strategy=refinement_result.improved_strategy,
            generated_bot=generated.to_dict(),
            saved=saved,
            strategy_id=strategy_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/top-strategies", response_model=StrategyListResponse)
async def get_top_strategies(
    limit: int = Query(default=10, ge=1, le=100, description="Maximum results"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    min_score: float = Query(default=0, ge=0, le=100, description="Minimum score")
):
    """
    Get top ranked strategies from the library
    
    Returns strategies sorted by total score descending.
    """
    try:
        db = create_strategy_db()
        strategies = await db.get_top_strategies(
            limit=limit,
            category=category,
            min_score=min_score
        )
        await db.close()
        
        return StrategyListResponse(
            success=True,
            total=len(strategies),
            strategies=strategies
        )
        
    except Exception as e:
        logger.error(f"Failed to get top strategies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch strategies: {str(e)}")


@router.get("/strategy/{strategy_id}", response_model=StrategyDetailResponse)
async def get_strategy(strategy_id: str):
    """
    Get detailed view of a specific strategy
    
    Includes full code, parsed data, improved strategy,
    generated bot, and scoring breakdown.
    """
    try:
        db = create_strategy_db()
        strategy = await db.get_strategy_by_id(strategy_id)
        await db.close()
        
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        
        return StrategyDetailResponse(
            success=True,
            strategy=strategy
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get strategy {strategy_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch strategy: {str(e)}")


@router.get("/search")
async def search_strategies(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100)
):
    """
    Search strategies by text
    
    Searches strategy names, descriptions, and categories.
    """
    try:
        db = create_strategy_db()
        strategies = await db.search_strategies(q, limit=limit)
        await db.close()
        
        return {
            "success": True,
            "query": q,
            "total": len(strategies),
            "strategies": strategies
        }
        
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics():
    """
    Get strategy library statistics
    
    Returns counts by category, grade, and overall stats.
    """
    try:
        db = create_strategy_db()
        stats = await db.get_statistics()
        await db.close()
        
        return StatisticsResponse(
            success=True,
            statistics=stats
        )
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch statistics: {str(e)}")


@router.delete("/strategy/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """
    Delete a strategy from the library
    """
    try:
        db = create_strategy_db()
        deleted = await db.delete_strategy(strategy_id)
        await db.close()
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Strategy not found")
        
        return {"success": True, "message": "Strategy deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete strategy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete strategy: {str(e)}")


def init_discovery_router():
    """Initialize the discovery router"""
    return router
