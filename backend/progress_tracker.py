"""
Progress Tracking System
Real-time progress updates for long-running pipeline jobs.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class JobStage(Enum):
    """Pipeline job stages"""
    INITIALIZING = "initializing"
    GENERATION = "generation"
    BACKTESTING = "backtesting"
    VALIDATION = "validation"
    CODEX_FILTERING = "codex"
    OPTIMIZATION = "optimization"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProgressUpdate:
    """Progress update for a job"""
    job_id: str
    stage: str
    percent: float  # 0-100
    current: int    # Current item being processed
    total: int      # Total items to process
    message: str    # Human-readable status message
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    errors: list = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            "job_id": self.job_id,
            "stage": self.stage,
            "percent": round(self.percent, 1),
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "errors": self.errors
        }


class ProgressTracker:
    """
    Global progress tracker for pipeline jobs.
    Thread-safe storage and retrieval of job progress.
    """
    
    def __init__(self):
        self._progress_store: Dict[str, ProgressUpdate] = {}
        self._job_metadata: Dict[str, Dict[str, Any]] = {}
        logger.info("Progress Tracker initialized")
    
    def start_job(
        self, 
        job_id: str, 
        total_strategies: int,
        config: Dict[str, Any] = None
    ):
        """
        Initialize progress tracking for a new job.
        
        Args:
            job_id: Unique job identifier
            total_strategies: Total number of strategies to process
            config: Optional job configuration metadata
        """
        progress = ProgressUpdate(
            job_id=job_id,
            stage=JobStage.INITIALIZING.value,
            percent=0.0,
            current=0,
            total=total_strategies,
            message="Initializing pipeline..."
        )
        
        self._progress_store[job_id] = progress
        self._job_metadata[job_id] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "config": config or {},
            "total_strategies": total_strategies
        }
        
        logger.info(f"[PROGRESS] Job {job_id} started: {total_strategies} strategies")
    
    def update(
        self,
        job_id: str,
        stage: str = None,
        percent: float = None,
        current: int = None,
        total: int = None,
        message: str = None,
        error: str = None
    ):
        """
        Update progress for a job.
        
        Args:
            job_id: Job identifier
            stage: Current stage (optional, keeps previous if not provided)
            percent: Progress percentage 0-100 (optional)
            current: Current item index (optional)
            total: Total items (optional)
            message: Status message (optional)
            error: Error message to append (optional)
        """
        if job_id not in self._progress_store:
            logger.warning(f"[PROGRESS] Job {job_id} not found, creating new entry")
            self.start_job(job_id, total or 100)
        
        progress = self._progress_store[job_id]
        
        # Update fields if provided
        if stage is not None:
            progress.stage = stage
        if percent is not None:
            progress.percent = min(100.0, max(0.0, percent))
        if current is not None:
            progress.current = current
        if total is not None:
            progress.total = total
        if message is not None:
            progress.message = message
        if error is not None:
            progress.errors.append(error)
        
        progress.timestamp = datetime.now(timezone.utc)
        
        logger.info(
            f"[PROGRESS] {job_id} | {progress.stage} | "
            f"{progress.percent:.1f}% | {progress.current}/{progress.total} | "
            f"{progress.message}"
        )
    
    def get_progress(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current progress for a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Progress update dict or None if job not found
        """
        if job_id not in self._progress_store:
            return None
        
        progress = self._progress_store[job_id]
        metadata = self._job_metadata.get(job_id, {})
        
        # Combine progress + metadata
        result = progress.to_dict()
        result["started_at"] = metadata.get("started_at")
        result["total_strategies"] = metadata.get("total_strategies", progress.total)
        
        return result
    
    def complete_job(self, job_id: str, message: str = "Pipeline completed successfully"):
        """Mark job as completed."""
        self.update(
            job_id=job_id,
            stage=JobStage.COMPLETED.value,
            percent=100.0,
            message=message
        )
        
        if job_id in self._job_metadata:
            self._job_metadata[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"[PROGRESS] Job {job_id} completed")
    
    def fail_job(self, job_id: str, error: str):
        """Mark job as failed."""
        self.update(
            job_id=job_id,
            stage=JobStage.FAILED.value,
            message=f"Pipeline failed: {error}",
            error=error
        )
        
        if job_id in self._job_metadata:
            self._job_metadata[job_id]["failed_at"] = datetime.now(timezone.utc).isoformat()
            self._job_metadata[job_id]["error"] = error
        
        logger.error(f"[PROGRESS] Job {job_id} failed: {error}")
    
    def cleanup_job(self, job_id: str):
        """Remove job from tracker (call after completion/failure)."""
        if job_id in self._progress_store:
            del self._progress_store[job_id]
        if job_id in self._job_metadata:
            del self._job_metadata[job_id]
        
        logger.info(f"[PROGRESS] Job {job_id} cleaned up")
    
    def get_all_active_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get all active jobs."""
        return {
            job_id: progress.to_dict()
            for job_id, progress in self._progress_store.items()
            if progress.stage not in [JobStage.COMPLETED.value, JobStage.FAILED.value]
        }


# Global singleton instance
_progress_tracker = ProgressTracker()


def get_progress_tracker() -> ProgressTracker:
    """Get the global progress tracker instance."""
    return _progress_tracker
