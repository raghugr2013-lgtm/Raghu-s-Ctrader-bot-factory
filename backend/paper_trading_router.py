"""
Paper Trading API Router
Provides status endpoint for monitoring paper trading engine
"""
import logging
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/paper-trading", tags=["Paper Trading"])

# Path to status file (updated by background service)
STATUS_FILE = Path("/app/backend/paper_trading/status.json")
TRADES_FILE = Path("/app/backend/paper_trading/trades_backup.json")


class PaperTradingStatus(BaseModel):
    """Paper trading status response"""
    running: bool
    current_pnl: float
    drawdown_pct: float
    total_trades: int
    total_equity: float
    total_return_pct: float
    risk_status: Dict[str, Any]
    portfolio_details: Dict[str, Any]


@router.get("/status", response_model=PaperTradingStatus)
async def get_paper_trading_status():
    """
    Get current paper trading status
    
    Returns:
    - current_pnl: Total profit/loss
    - drawdown_pct: Current drawdown percentage
    - total_trades: Number of trades executed
    - total_equity: Current total equity
    - total_return_pct: Return percentage
    """
    try:
        # Read status from file
        if not STATUS_FILE.exists():
            # Return initial status if engine hasn't started yet
            return PaperTradingStatus(
                running=False,
                current_pnl=0.0,
                drawdown_pct=0.0,
                total_trades=0,
                total_equity=10000.0,
                total_return_pct=0.0,
                risk_status={
                    'trading_enabled': True,
                    'stop_reason': None,
                    'current_drawdown_pct': 0.0,
                    'daily_loss_pct': 0.0
                },
                portfolio_details={
                    'initial_capital': 10000.0,
                    'current_capital': 10000.0,
                    'open_positions': 0
                }
            )
        
        with open(STATUS_FILE, 'r') as f:
            status = json.load(f)
        
        return PaperTradingStatus(
            running=status.get('running', False),
            current_pnl=status.get('portfolio', {}).get('total_pnl', 0.0),
            drawdown_pct=status.get('portfolio', {}).get('drawdown_pct', 0.0),
            total_trades=status.get('total_trades', 0),
            total_equity=status.get('portfolio', {}).get('total_equity', 10000.0),
            total_return_pct=status.get('portfolio', {}).get('total_return_pct', 0.0),
            risk_status=status.get('risk', {}),
            portfolio_details=status.get('portfolio', {})
        )
        
    except Exception as e:
        logger.error(f"Failed to read paper trading status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read status: {str(e)}"
        )


@router.get("/trades")
async def get_paper_trades():
    """
    Get all paper trades
    
    Returns:
        List of trade records
    """
    try:
        if not TRADES_FILE.exists():
            return []
        
        with open(TRADES_FILE, 'r') as f:
            trades = json.load(f)
        
        return trades
        
    except Exception as e:
        logger.error(f"Failed to read trades: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read trades: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "service": "paper-trading",
        "status_file_exists": STATUS_FILE.exists(),
        "trades_file_exists": TRADES_FILE.exists()
    }
