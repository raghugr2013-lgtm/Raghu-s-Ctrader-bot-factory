"""
Strategy Generation Job Tracker
Real-time progress updates for long-running strategy generation jobs.

Stages:
1. FETCHING_DATA - Loading market data
2. PREPARING_DATA - Validating and preparing data
3. GENERATING_STRATEGIES - AI strategy generation  
4. BACKTESTING - Running backtests on strategies
5. VALIDATING_RESULTS - Filtering and scoring
6. FINALIZING - Packaging results
7. COMPLETED - Job done
"""

import logging
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class JobStage(str, Enum):
    """Strategy generation job stages"""
    INITIALIZING = "initializing"
    FETCHING_DATA = "fetching_data"
    PREPARING_DATA = "preparing_data"
    GENERATING_STRATEGIES = "generating_strategies"
    BACKTESTING = "backtesting"
    VALIDATING_RESULTS = "validating_results"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionMode(str, Enum):
    """Strategy execution modes"""
    FAST = "fast"      # Parallel, lighter validation
    QUALITY = "quality"  # Slower, deeper validation


class StrategyType(str, Enum):
    """Strategy types"""
    SCALPING = "scalping"
    INTRADAY = "intraday"
    SWING = "swing"


class RiskLevel(str, Enum):
    """Risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StrategyJobRequest(BaseModel):
    """Request model for strategy generation job"""
    symbol: str
    timeframe: str
    strategy_count: int = 100
    strategy_type: str = "intraday"
    risk_level: str = "medium"
    execution_mode: str = "fast"
    ai_model: str = "openai"
    # Backtest period
    backtest_start: Optional[str] = None
    backtest_end: Optional[str] = None
    # Batch config
    batch_size: int = 50
    
    class Config:
        use_enum_values = True


@dataclass
class JobProgress:
    """Progress state for a job"""
    job_id: str
    stage: str = JobStage.INITIALIZING.value
    percent: float = 0.0
    current_item: int = 0
    total_items: int = 0
    message: str = "Initializing..."
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Batch tracking
    current_batch: int = 0
    total_batches: int = 1
    # Results tracking
    strategies_generated: int = 0
    strategies_passed: int = 0
    errors: List[str] = field(default_factory=list)
    # Final results
    result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            "job_id": self.job_id,
            "stage": self.stage,
            "percent": round(self.percent, 1),
            "current_item": self.current_item,
            "total_items": self.total_items,
            "message": self.message,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_batch": self.current_batch,
            "total_batches": self.total_batches,
            "strategies_generated": self.strategies_generated,
            "strategies_passed": self.strategies_passed,
            "errors": self.errors[-5:],  # Last 5 errors
            "elapsed_seconds": (datetime.now(timezone.utc) - self.started_at).total_seconds(),
            "has_result": self.result is not None
        }


class StrategyJobTracker:
    """
    Singleton tracker for strategy generation jobs.
    Stores job progress and results.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._jobs: Dict[str, JobProgress] = {}
            cls._instance._configs: Dict[str, StrategyJobRequest] = {}
        return cls._instance
    
    def create_job(self, config: StrategyJobRequest) -> str:
        """Create a new job and return job_id"""
        job_id = str(uuid.uuid4())
        
        # Calculate batches
        total_batches = (config.strategy_count + config.batch_size - 1) // config.batch_size
        
        self._jobs[job_id] = JobProgress(
            job_id=job_id,
            total_items=config.strategy_count,
            total_batches=total_batches
        )
        self._configs[job_id] = config
        
        logger.info(f"[JOB TRACKER] Created job {job_id}: {config.strategy_count} strategies, {total_batches} batches")
        
        return job_id
    
    def update(
        self,
        job_id: str,
        stage: Optional[str] = None,
        percent: Optional[float] = None,
        current_item: Optional[int] = None,
        total_items: Optional[int] = None,
        message: Optional[str] = None,
        current_batch: Optional[int] = None,
        strategies_generated: Optional[int] = None,
        strategies_passed: Optional[int] = None,
        error: Optional[str] = None
    ):
        """Update job progress"""
        if job_id not in self._jobs:
            logger.warning(f"[JOB TRACKER] Job {job_id} not found")
            return
        
        job = self._jobs[job_id]
        
        if stage is not None:
            job.stage = stage
        if percent is not None:
            job.percent = min(100.0, max(0.0, percent))
        if current_item is not None:
            job.current_item = current_item
        if total_items is not None:
            job.total_items = total_items
        if message is not None:
            job.message = message
        if current_batch is not None:
            job.current_batch = current_batch
        if strategies_generated is not None:
            job.strategies_generated = strategies_generated
        if strategies_passed is not None:
            job.strategies_passed = strategies_passed
        if error is not None:
            job.errors.append(error)
        
        job.updated_at = datetime.now(timezone.utc)
        
        logger.info(
            f"[JOB] {job_id[:8]} | {job.stage} | {job.percent:.1f}% | "
            f"Batch {job.current_batch}/{job.total_batches} | {job.message}"
        )
    
    def complete(self, job_id: str, result: Dict[str, Any]):
        """Mark job as completed with results"""
        if job_id not in self._jobs:
            return
        
        job = self._jobs[job_id]
        job.stage = JobStage.COMPLETED.value
        job.percent = 100.0
        job.message = "Job completed successfully"
        job.result = result
        job.updated_at = datetime.now(timezone.utc)
        
        logger.info(f"[JOB TRACKER] Job {job_id} completed")
    
    def fail(self, job_id: str, error: str):
        """Mark job as failed"""
        if job_id not in self._jobs:
            return
        
        job = self._jobs[job_id]
        job.stage = JobStage.FAILED.value
        job.message = f"Job failed: {error}"
        job.errors.append(error)
        job.updated_at = datetime.now(timezone.utc)
        
        logger.error(f"[JOB TRACKER] Job {job_id} failed: {error}")
    
    def get_progress(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job progress"""
        if job_id not in self._jobs:
            return None
        return self._jobs[job_id].to_dict()
    
    def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job result if completed"""
        if job_id not in self._jobs:
            return None
        job = self._jobs[job_id]
        if job.result:
            return job.result
        return None
    
    def get_config(self, job_id: str) -> Optional[StrategyJobRequest]:
        """Get job configuration"""
        return self._configs.get(job_id)
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs older than max_age_hours"""
        now = datetime.now(timezone.utc)
        to_remove = []
        
        for job_id, job in self._jobs.items():
            age_hours = (now - job.started_at).total_seconds() / 3600
            if age_hours > max_age_hours:
                to_remove.append(job_id)
        
        for job_id in to_remove:
            del self._jobs[job_id]
            if job_id in self._configs:
                del self._configs[job_id]
        
        if to_remove:
            logger.info(f"[JOB TRACKER] Cleaned up {len(to_remove)} old jobs")


# Singleton instance
job_tracker = StrategyJobTracker()


def get_job_tracker() -> StrategyJobTracker:
    """Get the singleton job tracker instance"""
    return job_tracker
