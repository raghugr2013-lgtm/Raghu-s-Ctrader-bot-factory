"""
Optimization Executor - Backend API

Executes local Python optimization scripts and returns results.
Provides endpoints to trigger, monitor, and retrieve optimization runs.
"""

import os
import subprocess
import json
import asyncio
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/api/optimization", tags=["Optimization Execution"])

# Configuration
SCRIPT_DIR = os.environ.get('OPTIMIZATION_SCRIPT_DIR', '/app/trading_system/backend')
SCRIPT_NAME = "phase2a_optimizer.py"
RESULTS_FILE = "results.json"
PYTHON_CMD = "/root/.venv/bin/python3"
TIMEOUT_SECONDS = 300  # 5 minutes

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')

# Execution state (simple in-memory storage)
# For production, use Redis or similar
execution_state = {
    "running": False,
    "run_id": None,
    "start_time": None,
    "error": None
}


class OptimizationRequest(BaseModel):
    """Request to run optimization"""
    csv_path: str
    strategy: str = "trend_following"
    phase: str = "2A"


class OptimizationResponse(BaseModel):
    """Response from optimization run"""
    status: str
    run_id: str
    total_strategies: int
    viable_strategies: int
    best_profit_factor: float
    execution_time_seconds: float
    results: Dict


class ExecutionStatus(BaseModel):
    """Current execution status"""
    running: bool
    run_id: Optional[str]
    elapsed_seconds: Optional[float]
    error: Optional[str]


def validate_csv_path(csv_path: str) -> bool:
    """
    Validate CSV path for security
    
    Checks:
    - Path exists
    - Is a file
    - Has .csv extension
    - Is absolute path
    """
    try:
        path = Path(csv_path)
        
        # Must be absolute
        if not path.is_absolute():
            return False
        
        # Must exist
        if not path.exists():
            return False
        
        # Must be a file
        if not path.is_file():
            return False
        
        # Must be .csv
        if path.suffix.lower() != '.csv':
            return False
        
        return True
    except Exception:
        return False


@router.post("/run", response_model=OptimizationResponse)
async def run_optimization(request: OptimizationRequest):
    """
    Execute optimization script
    
    Flow:
    1. Validate inputs
    2. Check if already running
    3. Execute Python script via subprocess
    4. Wait for completion (with timeout)
    5. Read results JSON
    6. Store in MongoDB
    7. Return results
    """
    
    # Check if already running
    if execution_state["running"]:
        raise HTTPException(
            status_code=409,
            detail=f"Optimization already running. Run ID: {execution_state['run_id']}"
        )
    
    # Validate CSV path
    if not validate_csv_path(request.csv_path):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid CSV path: {request.csv_path}. File must exist and have .csv extension."
        )
    
    # Validate script exists
    script_path = Path(SCRIPT_DIR) / SCRIPT_NAME
    if not script_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Optimization script not found: {script_path}"
        )
    
    # Generate run ID
    run_id = datetime.utcnow().isoformat()
    start_time = datetime.utcnow()
    
    # Update state
    execution_state["running"] = True
    execution_state["run_id"] = run_id
    execution_state["start_time"] = start_time
    execution_state["error"] = None
    
    try:
        print(f"[{run_id}] Starting optimization...")
        print(f"  Script: {script_path}")
        print(f"  CSV: {request.csv_path}")
        print(f"  Strategy: {request.strategy}")
        print(f"  Phase: {request.phase}")
        
        # Execute Python script
        # IMPORTANT: Use list arguments to prevent command injection
        cmd = [
            PYTHON_CMD,
            str(script_path),
            "--csv", request.csv_path
        ]
        
        print(f"  Command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS
        )
        
        # Check for errors
        if result.returncode != 0:
            error_msg = result.stderr or "Script execution failed"
            print(f"[{run_id}] Error: {error_msg}")
            execution_state["error"] = error_msg
            execution_state["running"] = False
            raise HTTPException(
                status_code=500,
                detail=f"Script execution failed: {error_msg}"
            )
        
        # Print script output
        if result.stdout:
            print(f"[{run_id}] Script output:")
            print(result.stdout)
        
        # Read results JSON
        results_path = Path(SCRIPT_DIR) / RESULTS_FILE
        if not results_path.exists():
            execution_state["error"] = "Results file not generated"
            execution_state["running"] = False
            raise HTTPException(
                status_code=500,
                detail=f"Results file not found: {results_path}"
            )
        
        with open(results_path, 'r') as f:
            results = json.load(f)
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Store in MongoDB
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        
        result_doc = {
            "run_id": run_id,
            "executed_at": start_time,
            "execution_time_seconds": execution_time,
            "csv_path": request.csv_path,
            "strategy": request.strategy,
            "phase": request.phase,
            "executed_via": "api",
            "results": results
        }
        
        await db.optimization_runs.insert_one(result_doc)
        client.close()
        
        # Extract summary
        summary = results.get('summary_statistics', {})
        all_results = results.get('all_results', [])
        
        # Update state
        execution_state["running"] = False
        
        print(f"[{run_id}] Optimization complete!")
        print(f"  Total strategies: {len(all_results)}")
        print(f"  Viable: {summary.get('viable_strategies', 0)}")
        print(f"  Best PF: {summary.get('best_profit_factor', 0):.2f}")
        print(f"  Execution time: {execution_time:.1f}s")
        
        return OptimizationResponse(
            status="success",
            run_id=run_id,
            total_strategies=len(all_results),
            viable_strategies=summary.get('viable_strategies', 0),
            best_profit_factor=summary.get('best_profit_factor', 0),
            execution_time_seconds=execution_time,
            results=results
        )
    
    except subprocess.TimeoutExpired:
        execution_state["error"] = f"Script execution timed out (>{TIMEOUT_SECONDS}s)"
        execution_state["running"] = False
        raise HTTPException(
            status_code=504,
            detail=f"Script execution timed out after {TIMEOUT_SECONDS} seconds"
        )
    
    except Exception as e:
        execution_state["error"] = str(e)
        execution_state["running"] = False
        print(f"[{run_id}] Exception: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Execution error: {str(e)}"
        )


@router.get("/status", response_model=ExecutionStatus)
async def get_execution_status():
    """
    Get current execution status
    
    Returns:
    - running: bool
    - run_id: current run ID if running
    - elapsed_seconds: time elapsed if running
    - error: error message if failed
    """
    
    elapsed = None
    if execution_state["running"] and execution_state["start_time"]:
        elapsed = (datetime.utcnow() - execution_state["start_time"]).total_seconds()
    
    return ExecutionStatus(
        running=execution_state["running"],
        run_id=execution_state["run_id"],
        elapsed_seconds=elapsed,
        error=execution_state["error"]
    )


@router.post("/cancel")
async def cancel_optimization():
    """
    Cancel running optimization
    
    Note: This is a simplified implementation.
    Production would need process tracking and killing.
    """
    
    if not execution_state["running"]:
        raise HTTPException(
            status_code=400,
            detail="No optimization is currently running"
        )
    
    execution_state["running"] = False
    execution_state["error"] = "Cancelled by user"
    
    return {
        "status": "cancelled",
        "run_id": execution_state["run_id"]
    }


@router.get("/runs/list")
async def list_optimization_runs(limit: int = 20):
    """List recent optimization runs"""
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    cursor = db.optimization_runs.find().sort("executed_at", -1).limit(limit)
    runs = await cursor.to_list(length=limit)
    
    # Clean up MongoDB IDs
    for run in runs:
        run['_id'] = str(run['_id'])
    
    client.close()
    
    return runs


@router.get("/runs/{run_id}")
async def get_optimization_run(run_id: str):
    """Get specific optimization run by ID"""
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    run = await db.optimization_runs.find_one({"run_id": run_id})
    
    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Run not found: {run_id}"
        )
    
    run['_id'] = str(run['_id'])
    
    client.close()
    
    return run
