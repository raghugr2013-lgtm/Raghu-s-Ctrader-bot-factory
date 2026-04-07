"""
Dukascopy Data Router
API endpoints for downloading and processing Dukascopy market data
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
import uuid
import asyncio
import logging

from dukascopy_downloader import DukascopyDownloader
from market_data_service import MarketDataService
from market_data_models import Candle, DataTimeframe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dukascopy", tags=["dukascopy"])

# In-memory task storage (in production, use Redis or database)
download_tasks = {}


class DukascopyDownloadRequest(BaseModel):
    """Request to download Dukascopy data"""
    symbols: List[str] = Field(..., description="List of symbols to download")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    timeframe: str = Field(..., description="Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d or M1, M5, M15, M30, H1, H4, D1)")


class DownloadTaskStatus(BaseModel):
    """Status of download task"""
    task_id: str
    status: str  # pending, running, completed, failed
    progress: float  # 0-100
    message: str
    results: Optional[Dict] = None
    error: Optional[str] = None


async def download_task_worker(
    task_id: str,
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    timeframe: str,
    market_data_service: MarketDataService
):
    """Background worker for downloading data"""
    downloader = DukascopyDownloader()
    
    try:
        # Update status to running
        download_tasks[task_id]['status'] = 'running'
        download_tasks[task_id]['message'] = 'Starting download...'
        
        all_results = {}
        total_symbols = len(symbols)
        
        for idx, symbol in enumerate(symbols):
            try:
                # Progress callback
                async def progress_cb(progress, msg):
                    download_tasks[task_id]['progress'] = (idx / total_symbols * 100) + (progress / total_symbols)
                    download_tasks[task_id]['message'] = f"[{symbol}] {msg}"
                
                # Download and process
                result = await downloader.download_range(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=timeframe,
                    progress_callback=progress_cb
                )
                
                # Save to CSV
                csv_path = await downloader.save_to_csv(
                    candles=result['candles'],
                    symbol=symbol,
                    timeframe=timeframe
                )
                
                # Store in database
                # Convert timeframe back to internal format if needed
                from dukascopy_downloader import map_timeframe_from_dukascopy
                db_timeframe = map_timeframe_from_dukascopy(timeframe)
                logger.info(f"[DUKASCOPY] Storing with timeframe: '{timeframe}' → DB format '{db_timeframe}'")
                
                candle_objects = []
                for candle_data in result['candles']:
                    candle = Candle(
                        timestamp=candle_data['timestamp'],
                        open=candle_data['open'],
                        high=candle_data['high'],
                        low=candle_data['low'],
                        close=candle_data['close'],
                        volume=candle_data['volume'],
                        symbol=symbol,
                        timeframe=DataTimeframe(db_timeframe)
                    )
                    candle_objects.append(candle)
                
                # Store candles
                if candle_objects:
                    await market_data_service.store_candles(candle_objects, provider="dukascopy")
                
                # Save results
                all_results[symbol] = {
                    **result['stats'],
                    'csv_path': csv_path,
                    'stored_in_db': len(candle_objects)
                }
                
                logger.info(f"Completed {symbol}: {len(candle_objects)} candles")
                
            except Exception as e:
                logger.error(f"Failed to download {symbol}: {str(e)}")
                all_results[symbol] = {
                    'error': str(e),
                    'status': 'failed'
                }
        
        # Mark as completed
        download_tasks[task_id]['status'] = 'completed'
        download_tasks[task_id]['progress'] = 100
        download_tasks[task_id]['message'] = f'Downloaded {len(symbols)} symbols'
        download_tasks[task_id]['results'] = all_results
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {str(e)}")
        download_tasks[task_id]['status'] = 'failed'
        download_tasks[task_id]['error'] = str(e)
        download_tasks[task_id]['message'] = f'Failed: {str(e)}'


@router.post("/download")
async def start_download(
    request: DukascopyDownloadRequest,
    background_tasks: BackgroundTasks
):
    """
    Start downloading Dukascopy data in background
    Returns task_id for tracking progress
    """
    try:
        # Parse dates
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)
        
        # Convert and validate timeframe
        from dukascopy_downloader import map_timeframe_to_dukascopy
        
        # Convert to Dukascopy format
        dukascopy_timeframe = map_timeframe_to_dukascopy(request.timeframe)
        
        # Validate supported timeframes
        supported = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
        if dukascopy_timeframe not in supported:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported timeframe '{request.timeframe}'. Supported: 1m, 5m, 15m, 30m, 1h, 4h, 1d"
            )
        
        logger.info(f"[DUKASCOPY] API request timeframe: '{request.timeframe}' → Dukascopy: '{dukascopy_timeframe}'")
        
        # Create task
        task_id = str(uuid.uuid4())
        download_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'progress': 0,
            'message': 'Task created',
            'symbols': request.symbols,
            'start_date': request.start_date,
            'end_date': request.end_date,
            'timeframe': dukascopy_timeframe,  # Use converted timeframe
            'results': None,
            'error': None
        }
        
        # Note: market_data_service needs to be passed from server.py
        # For now, this is a placeholder - will be initialized in init function
        from market_data_service import init_market_data_service
        from server import db
        market_data_service = init_market_data_service(db)
        
        # Start background task
        background_tasks.add_task(
            download_task_worker,
            task_id,
            request.symbols,
            start_date,
            end_date,
            dukascopy_timeframe,  # Use converted timeframe
            market_data_service
        )
        
        return {
            'success': True,
            'task_id': task_id,
            'message': 'Download started in background'
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to start download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start download: {str(e)}")


@router.get("/status/{task_id}")
async def get_download_status(task_id: str):
    """Get status of download task"""
    if task_id not in download_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = download_tasks[task_id]
    return {
        'success': True,
        'task': task
    }


@router.get("/results/{task_id}")
async def get_download_results(task_id: str):
    """Get results of completed download task"""
    if task_id not in download_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = download_tasks[task_id]
    
    if task['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Status: {task['status']}"
        )
    
    return {
        'success': True,
        'results': task['results']
    }


def init_dukascopy_router(db):
    """Initialize router with database connection"""
    # This will be called from server.py
    pass
