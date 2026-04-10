"""
Data Ingestion Router - API Endpoints for M1 SSOT Architecture

All data operations go through these endpoints.
Strict M1 enforcement with no interpolation.
"""

import logging
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Body
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/data", tags=["Data Ingestion V2"])

# Will be set by init function
data_service = None


# ========== REQUEST/RESPONSE MODELS ==========

class CandleResponse(BaseModel):
    """Single candle in response"""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    confidence: str = "high"
    has_gaps: bool = False


class GetCandlesResponse(BaseModel):
    """Response for candle requests"""
    success: bool
    symbol: str
    timeframe: str
    candles: List[CandleResponse]
    total_count: int
    
    # Quality metrics
    quality_score: float
    usable_for_backtest: bool
    usable_for_research: bool
    gaps_detected: int
    confidence_distribution: dict
    
    warnings: List[str] = []


class IngestionResponse(BaseModel):
    """Response for ingestion operations"""
    success: bool
    message: str
    upload_batch_id: str
    symbol: str
    
    candles_processed: int = 0
    candles_stored: int = 0
    candles_rejected: int = 0
    
    detected_timeframe: Optional[str] = None
    confidence_assigned: str = "high"
    
    warnings: List[str] = []
    errors: List[str] = []


class CoverageResponse(BaseModel):
    """Data coverage response"""
    symbol: str
    total_m1_candles: int
    first_timestamp: Optional[str]
    last_timestamp: Optional[str]
    coverage_percentage: float
    
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    
    source_breakdown: dict


class GapResponse(BaseModel):
    """Single gap info"""
    start: str
    end: str
    missing_minutes: int
    is_market_closed: bool


class GapDetectionResponse(BaseModel):
    """Gap detection response"""
    symbol: str
    gaps: List[GapResponse]
    total_gaps: int
    total_missing_minutes: int


class GapFixRequest(BaseModel):
    """Request to fix specific gaps"""
    gaps: List[dict] = Field(..., description="List of gaps to fix (start, end)")


# ========== INITIALIZATION ==========

def init_data_ingestion_router(service):
    """
    Initialize router with data service.
    
    Args:
        service: DataServiceV2 instance
    """
    global data_service
    data_service = service
    logger.info("Data Ingestion Router V2 initialized")


# ========== INGESTION ENDPOINTS ==========

@router.post("/upload/bi5", response_model=IngestionResponse)
async def upload_bi5(
    file: UploadFile = File(..., description="BI5 tick data file"),
    symbol: str = Form(..., description="Trading symbol (e.g., EURUSD)"),
    hour: str = Form(..., description="Hour timestamp ISO format (e.g., 2024-01-15T10:00:00Z)")
):
    """
    Upload BI5 tick data file.
    
    Converts Dukascopy tick data to M1 candles.
    Assigns HIGH confidence.
    
    No interpolation - missing minutes are gaps.
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        # Parse hour timestamp
        base_hour = datetime.fromisoformat(hour.replace("Z", "+00:00"))
        
        # Read file
        file_bytes = await file.read()
        
        # Process BI5
        result = await data_service.ingest_bi5(
            file_bytes=file_bytes,
            symbol=symbol,
            base_datetime=base_hour
        )
        
        return IngestionResponse(
            success=result.success,
            message="BI5 file processed successfully" if result.success else "Processing failed",
            upload_batch_id=result.upload_batch_id,
            symbol=result.symbol,
            candles_processed=result.candles_processed,
            candles_stored=result.candles_stored,
            candles_rejected=result.candles_rejected,
            detected_timeframe="M1",
            confidence_assigned=result.confidence_assigned,
            warnings=result.warnings,
            errors=result.errors
        )
        
    except Exception as e:
        logger.error(f"BI5 upload error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/csv", response_model=IngestionResponse)
async def upload_csv(
    file: UploadFile = File(..., description="CSV file with OHLCV data"),
    symbol: str = Form(..., description="Trading symbol (e.g., EURUSD)"),
    declared_timeframe: Optional[str] = Form(None, description="Declared timeframe (optional, auto-detected)"),
    research_override: bool = Form(False, description="Allow higher TF for research only (NOT for backtest)")
):
    """
    Upload CSV file.
    
    STRICT RULES:
    - M1 CSV → Accepted with HIGH confidence
    - Higher TF CSV (M5, H1, D1) → REJECTED by default
    - research_override=true → Accepts but marks LOW confidence
    
    NO INTERPOLATION - Higher TF cannot be converted to M1.
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        # Read file
        file_content = await file.read()
        
        # Process CSV
        result = await data_service.ingest_csv(
            file_content=file_content,
            symbol=symbol,
            declared_timeframe=declared_timeframe,
            research_override=research_override
        )
        
        message = "CSV processed successfully" if result.success else "Processing failed"
        if result.rejected_reason:
            message = f"REJECTED: {result.rejected_reason}"
        
        return IngestionResponse(
            success=result.success,
            message=message,
            upload_batch_id=result.upload_batch_id,
            symbol=result.symbol,
            candles_processed=result.candles_processed,
            candles_stored=result.candles_stored,
            candles_rejected=result.candles_rejected,
            detected_timeframe=result.detected_timeframe,
            confidence_assigned=result.confidence_assigned,
            warnings=result.warnings,
            errors=result.errors
        )
        
    except Exception as e:
        logger.error(f"CSV upload error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== RETRIEVAL ENDPOINTS ==========

@router.get("/candles/{symbol}/{timeframe}", response_model=GetCandlesResponse)
async def get_candles(
    symbol: str,
    timeframe: str,
    start_date: str = Query(..., description="Start date ISO format"),
    end_date: str = Query(..., description="End date ISO format"),
    min_confidence: str = Query("high", description="Minimum confidence: high, medium, low"),
    use_case: str = Query("production_backtest", description="Use case for validation")
):
    """
    Get candles for any timeframe.
    
    M1 = direct from SSOT database
    Higher TF (M5, M15, H1, etc.) = aggregated on-demand from M1
    
    Respects confidence filter - LOW confidence never used in production backtest.
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        # Parse dates
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        
        # Get candles via aggregator
        result = await data_service.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start,
            end_date=end,
            min_confidence=min_confidence,
            use_case=use_case
        )
        
        # Convert to response format
        candles = [
            CandleResponse(
                timestamp=c.timestamp.isoformat(),
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
                confidence=c.confidence,
                has_gaps=c.has_gaps
            )
            for c in result.candles
        ]
        
        return GetCandlesResponse(
            success=True,
            symbol=symbol.upper(),
            timeframe=timeframe,
            candles=candles,
            total_count=len(candles),
            quality_score=result.quality_score,
            usable_for_backtest=result.usable_for_backtest,
            usable_for_research=result.usable_for_research,
            gaps_detected=result.gaps_detected,
            confidence_distribution=result.confidence_distribution,
            warnings=result.warnings
        )
        
    except Exception as e:
        logger.error(f"Get candles error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== COVERAGE & QUALITY ENDPOINTS ==========

@router.get("/coverage/{symbol}", response_model=CoverageResponse)
async def get_coverage(symbol: str):
    """
    Get data coverage report for a symbol.
    
    Shows:
    - Total M1 candles
    - Date range
    - Coverage percentage
    - Confidence breakdown
    - Source breakdown
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        report = await data_service.get_coverage(symbol)
        
        return CoverageResponse(
            symbol=report.symbol,
            total_m1_candles=report.total_m1_candles,
            first_timestamp=report.first_timestamp.isoformat() if report.first_timestamp else None,
            last_timestamp=report.last_timestamp.isoformat() if report.last_timestamp else None,
            coverage_percentage=report.coverage_percentage,
            high_confidence_count=report.high_confidence_count,
            medium_confidence_count=report.medium_confidence_count,
            low_confidence_count=report.low_confidence_count,
            source_breakdown=report.source_breakdown
        )
        
    except Exception as e:
        logger.error(f"Coverage error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quality/{symbol}")
async def get_quality_report(
    symbol: str,
    timeframe: str = Query("H1", description="Timeframe for quality report"),
    start_date: str = Query(..., description="Start date ISO format"),
    end_date: str = Query(..., description="End date ISO format")
):
    """
    Get detailed quality report for a date range.
    
    Includes:
    - Quality score
    - Usability flags
    - Gap analysis
    - Confidence distribution
    - Recommendations
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        
        report = await data_service.get_quality_report(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start,
            end_date=end
        )
        
        return {
            "symbol": report.symbol,
            "timeframe": report.timeframe,
            "start_date": report.start_date.isoformat(),
            "end_date": report.end_date.isoformat(),
            "quality_score": report.quality_score,
            "usable_for_backtest": report.usable_for_backtest,
            "usable_for_research": report.usable_for_research,
            "total_candles": report.total_candles,
            "gaps_detected": report.gaps_detected,
            "confidence_distribution": report.confidence_distribution,
            "issues": report.issues,
            "recommendations": report.recommendations
        }
        
    except Exception as e:
        logger.error(f"Quality report error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== GAP MANAGEMENT ENDPOINTS ==========

@router.get("/gaps/{symbol}/detect", response_model=GapDetectionResponse)
async def detect_gaps(
    symbol: str,
    start_date: Optional[str] = Query(None, description="Start date (optional)"),
    end_date: Optional[str] = Query(None, description="End date (optional)")
):
    """
    Detect gaps in M1 data.
    
    Returns list of periods with missing data.
    Weekend gaps (forex market closed) are excluded.
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00")) if start_date else None
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00")) if end_date else None
        
        gaps = await data_service.detect_gaps(symbol, start, end)
        
        total_minutes = sum(g.missing_minutes for g in gaps if not g.is_market_closed)
        
        return GapDetectionResponse(
            symbol=symbol.upper(),
            gaps=[
                GapResponse(
                    start=g.start.isoformat(),
                    end=g.end.isoformat(),
                    missing_minutes=g.missing_minutes,
                    is_market_closed=g.is_market_closed
                )
                for g in gaps
            ],
            total_gaps=len(gaps),
            total_missing_minutes=total_minutes
        )
        
    except Exception as e:
        logger.error(f"Gap detection error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gaps/{symbol}/fix")
async def fix_gaps(symbol: str):
    """
    Fix gaps by downloading REAL M1 data from Dukascopy.
    
    STRICT: Only real data used - NO interpolation.
    Gaps can only be filled with actual market data.
    
    NOTE: Requires Dukascopy downloader to be configured.
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        # Detect gaps first
        gaps = await data_service.detect_gaps(symbol)
        
        if not gaps:
            return {
                "success": True,
                "message": "No gaps detected",
                "gaps_fixed": 0,
                "candles_added": 0
            }
        
        # Filter out weekend gaps
        fixable_gaps = [g for g in gaps if not g.is_market_closed]
        
        if not fixable_gaps:
            return {
                "success": True,
                "message": "All gaps are weekend/market-closed periods (expected)",
                "gaps_fixed": 0,
                "candles_added": 0
            }
        
        # Try to get downloader
        try:
            from dukascopy_downloader import DukascopyDownloader
            downloader = DukascopyDownloader()
        except ImportError:
            return {
                "success": False,
                "message": "Dukascopy downloader not available. Gaps can only be filled with REAL data.",
                "gaps_to_fix": len(fixable_gaps),
                "suggestion": "Upload M1 CSV or BI5 files for the missing periods"
            }
        
        # Fix gaps
        result = await data_service.fix_gaps(
            symbol=symbol,
            gaps=fixable_gaps,
            downloader=downloader
        )
        
        return {
            "success": result.success,
            "message": f"Fixed {len(fixable_gaps)} gaps with {result.candles_stored} M1 candles",
            "gaps_fixed": len(fixable_gaps),
            "candles_added": result.candles_stored,
            "warnings": result.warnings
        }
        
    except Exception as e:
        logger.error(f"Gap fix error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== MAINTENANCE ENDPOINTS ==========

@router.delete("/purge/{symbol}/low-confidence")
async def purge_low_confidence(symbol: str):
    """
    Remove LOW confidence data from database.
    
    Use before production backtesting to ensure only HIGH quality data.
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        deleted = await data_service.purge_low_confidence(symbol)
        
        return {
            "success": True,
            "message": f"Purged {deleted} low confidence candles",
            "deleted_count": deleted
        }
        
    except Exception as e:
        logger.error(f"Purge error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{symbol}")
async def delete_symbol_data(symbol: str, confirm: bool = Query(False, description="Confirm deletion")):
    """
    Delete ALL data for a symbol.
    
    Requires confirm=true to execute.
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    if not confirm:
        return {
            "success": False,
            "message": "Deletion requires confirm=true parameter",
            "warning": f"This will delete ALL data for {symbol.upper()}"
        }
    
    try:
        deleted = await data_service.delete_symbol_data(symbol)
        
        return {
            "success": True,
            "message": f"Deleted {deleted} candles for {symbol.upper()}",
            "deleted_count": deleted
        }
        
    except Exception as e:
        logger.error(f"Delete error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== HEALTH CHECK ==========

@router.get("/health")
async def health_check():
    """
    Health check for data ingestion system.
    """
    return {
        "status": "healthy",
        "service": "Data Ingestion V2",
        "architecture": "M1 SSOT",
        "features": [
            "BI5 tick data ingestion",
            "M1 CSV ingestion",
            "On-demand timeframe aggregation",
            "Confidence-based filtering",
            "Gap detection and real-data filling"
        ],
        "rules": [
            "ONLY M1 data stored",
            "NO interpolation or synthetic data",
            "Higher TF CSV REJECTED by default",
            "All timeframes derived from M1"
        ]
    }
