"""
Data Ingestion Router V2 - Enhanced with Bulk Upload and Export

Endpoints:
- POST /api/v2/data/upload/csv - Upload M1 CSV
- POST /api/v2/data/upload/bi5 - Upload single BI5 file
- POST /api/v2/data/upload/bi5-zip - Upload ZIP of BI5 files (BULK)
- GET  /api/v2/data/export/m1/{symbol} - Export M1 data as CSV
- GET  /api/v2/data/export/{timeframe}/{symbol} - Export aggregated data
- GET  /api/v2/data/candles/{symbol}/{timeframe} - Get candles
- GET  /api/v2/data/coverage/{symbol} - Get coverage report
- GET  /api/v2/data/gaps/{symbol}/detect - Detect gaps
- POST /api/v2/data/gaps/{symbol}/fix - Fix gaps with real data
- DELETE /api/v2/data/purge/{symbol}/low-confidence - Purge low confidence
- DELETE /api/v2/data/delete/{symbol} - Delete all symbol data
"""

import logging
import io
import zipfile
import tempfile
import os
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import asyncio

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


class BulkIngestionResponse(BaseModel):
    """Response for bulk BI5 ZIP upload"""
    success: bool
    message: str
    upload_batch_id: str
    symbol: str
    files_processed: int = 0
    files_successful: int = 0
    files_failed: int = 0
    total_candles_stored: int = 0
    file_results: List[Dict[str, Any]] = []
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


# ========== INITIALIZATION ==========

def init_data_ingestion_router(service):
    """Initialize router with data service."""
    global data_service
    data_service = service
    logger.info("Data Ingestion Router V2 initialized with full features")


# ========== CSV UPLOAD (FIXED) ==========

@router.post("/upload/csv", response_model=IngestionResponse)
async def upload_csv(
    file: UploadFile = File(..., description="CSV file with OHLCV data"),
    symbol: str = Form(..., description="Trading symbol (e.g., EURUSD)"),
    declared_timeframe: Optional[str] = Form(None, description="Declared timeframe (optional)"),
    research_override: bool = Form(False, description="Allow higher TF for research only")
):
    """
    Upload CSV file - M1 ONLY accepted.
    
    STRICT RULES:
    - M1 CSV → Accepted with HIGH confidence
    - Higher TF CSV (M5, H1, D1) → REJECTED by default
    - research_override=true → Accepts with LOW confidence (research only)
    
    Returns detailed error for non-M1 data.
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        # Validate file
        if not file.filename:
            return IngestionResponse(
                success=False,
                message="No file provided",
                upload_batch_id="",
                symbol=symbol,
                errors=["No file uploaded"]
            )
        
        if not file.filename.lower().endswith('.csv'):
            return IngestionResponse(
                success=False,
                message="Invalid file type",
                upload_batch_id="",
                symbol=symbol,
                errors=["Only CSV files accepted"]
            )
        
        # Read file content
        file_content = await file.read()
        
        if len(file_content) == 0:
            return IngestionResponse(
                success=False,
                message="Empty file",
                upload_batch_id="",
                symbol=symbol,
                errors=["CSV file is empty"]
            )
        
        logger.info(f"CSV upload: {file.filename}, size={len(file_content)}, symbol={symbol}")
        
        # Process CSV via data service
        result = await data_service.ingest_csv(
            file_content=file_content,
            symbol=symbol,
            declared_timeframe=declared_timeframe,
            research_override=research_override
        )
        
        # Build response message
        if result.success:
            message = f"Successfully uploaded {result.candles_stored} M1 candles"
        elif result.rejected_reason:
            message = f"REJECTED: {result.rejected_reason}"
        else:
            message = "Upload failed"
        
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
        return IngestionResponse(
            success=False,
            message=f"Upload error: {str(e)}",
            upload_batch_id="",
            symbol=symbol,
            errors=[str(e)]
        )


# ========== BI5 SINGLE UPLOAD ==========

@router.post("/upload/bi5", response_model=IngestionResponse)
async def upload_bi5(
    file: UploadFile = File(..., description="BI5 tick data file"),
    symbol: str = Form(..., description="Trading symbol (e.g., EURUSD)"),
    hour: str = Form(..., description="Hour timestamp (e.g., 2024-01-15T10:00:00)")
):
    """
    Upload single BI5 tick data file.
    
    Converts Dukascopy tick data to M1 candles.
    Assigns HIGH confidence.
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        # Parse hour timestamp
        try:
            base_hour = datetime.fromisoformat(hour.replace("Z", "+00:00"))
            if base_hour.tzinfo is None:
                base_hour = base_hour.replace(tzinfo=timezone.utc)
        except ValueError as e:
            return IngestionResponse(
                success=False,
                message=f"Invalid hour format: {hour}",
                upload_batch_id="",
                symbol=symbol,
                errors=[f"Hour format error: {str(e)}. Use ISO format: 2024-01-15T10:00:00"]
            )
        
        # Read file
        file_bytes = await file.read()
        
        if len(file_bytes) == 0:
            return IngestionResponse(
                success=False,
                message="Empty BI5 file",
                upload_batch_id="",
                symbol=symbol,
                errors=["BI5 file is empty"]
            )
        
        logger.info(f"BI5 upload: {file.filename}, size={len(file_bytes)}, symbol={symbol}, hour={hour}")
        
        # Process BI5
        result = await data_service.ingest_bi5(
            file_bytes=file_bytes,
            symbol=symbol,
            base_datetime=base_hour
        )
        
        return IngestionResponse(
            success=result.success,
            message=f"Processed {result.candles_stored} M1 candles from tick data" if result.success else "Processing failed",
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
        return IngestionResponse(
            success=False,
            message=f"BI5 upload error: {str(e)}",
            upload_batch_id="",
            symbol=symbol,
            errors=[str(e)]
        )


# ========== BI5 ZIP BULK UPLOAD (NEW) ==========

@router.post("/upload/bi5-zip", response_model=BulkIngestionResponse)
async def upload_bi5_zip(
    file: UploadFile = File(..., description="ZIP file containing BI5 files"),
    symbol: str = Form(..., description="Trading symbol (e.g., EURUSD)")
):
    """
    Bulk upload BI5 files via ZIP.
    
    ZIP file should contain .bi5 files named with date/hour info:
    - EURUSD_2024_01_15_10.bi5
    - 2024-01-15T10.bi5
    - Any format with parseable date/hour
    
    Files are processed sequentially and merged into M1 candles.
    Partial success is allowed - failed files are reported.
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    batch_id = str(uuid.uuid4())
    
    try:
        # Validate ZIP file
        if not file.filename or not file.filename.lower().endswith('.zip'):
            return BulkIngestionResponse(
                success=False,
                message="Invalid file type - must be ZIP",
                upload_batch_id=batch_id,
                symbol=symbol,
                errors=["Only ZIP files accepted"]
            )
        
        # Read ZIP content
        zip_content = await file.read()
        
        if len(zip_content) == 0:
            return BulkIngestionResponse(
                success=False,
                message="Empty ZIP file",
                upload_batch_id=batch_id,
                symbol=symbol,
                errors=["ZIP file is empty"]
            )
        
        logger.info(f"BI5 ZIP upload: {file.filename}, size={len(zip_content)}, symbol={symbol}")
        
        # Extract and process BI5 files
        file_results = []
        files_processed = 0
        files_successful = 0
        files_failed = 0
        total_candles = 0
        warnings = []
        errors = []
        
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zf:
                # Get list of BI5 files
                bi5_files = [f for f in zf.namelist() if f.lower().endswith('.bi5')]
                
                if not bi5_files:
                    return BulkIngestionResponse(
                        success=False,
                        message="No BI5 files found in ZIP",
                        upload_batch_id=batch_id,
                        symbol=symbol,
                        errors=["ZIP contains no .bi5 files"]
                    )
                
                logger.info(f"Found {len(bi5_files)} BI5 files in ZIP")
                
                # Sort files by name (should give chronological order)
                bi5_files.sort()
                
                for bi5_filename in bi5_files:
                    files_processed += 1
                    
                    try:
                        # Extract hour from filename
                        base_hour = parse_bi5_filename(bi5_filename)
                        
                        if base_hour is None:
                            file_results.append({
                                "filename": bi5_filename,
                                "success": False,
                                "error": "Could not parse date/hour from filename",
                                "candles": 0
                            })
                            files_failed += 1
                            continue
                        
                        # Read BI5 content
                        bi5_content = zf.read(bi5_filename)
                        
                        if len(bi5_content) == 0:
                            file_results.append({
                                "filename": bi5_filename,
                                "success": False,
                                "error": "Empty file",
                                "candles": 0
                            })
                            files_failed += 1
                            continue
                        
                        # Process BI5 file
                        result = await data_service.ingest_bi5(
                            file_bytes=bi5_content,
                            symbol=symbol,
                            base_datetime=base_hour,
                            upload_batch_id=batch_id
                        )
                        
                        if result.success:
                            files_successful += 1
                            total_candles += result.candles_stored
                            file_results.append({
                                "filename": bi5_filename,
                                "success": True,
                                "hour": base_hour.isoformat(),
                                "candles": result.candles_stored,
                                "warnings": result.warnings
                            })
                        else:
                            files_failed += 1
                            file_results.append({
                                "filename": bi5_filename,
                                "success": False,
                                "error": result.errors[0] if result.errors else "Unknown error",
                                "candles": 0
                            })
                            
                    except Exception as file_error:
                        files_failed += 1
                        file_results.append({
                            "filename": bi5_filename,
                            "success": False,
                            "error": str(file_error),
                            "candles": 0
                        })
                        
        except zipfile.BadZipFile:
            return BulkIngestionResponse(
                success=False,
                message="Invalid ZIP file",
                upload_batch_id=batch_id,
                symbol=symbol,
                errors=["File is not a valid ZIP archive"]
            )
        
        # Build response
        success = files_successful > 0
        
        if files_successful == files_processed:
            message = f"All {files_processed} BI5 files processed successfully - {total_candles} M1 candles"
        elif files_successful > 0:
            message = f"Partial success: {files_successful}/{files_processed} files - {total_candles} M1 candles"
        else:
            message = f"All {files_processed} files failed"
        
        return BulkIngestionResponse(
            success=success,
            message=message,
            upload_batch_id=batch_id,
            symbol=symbol,
            files_processed=files_processed,
            files_successful=files_successful,
            files_failed=files_failed,
            total_candles_stored=total_candles,
            file_results=file_results[:50],  # Limit results to prevent huge response
            warnings=warnings,
            errors=errors
        )
        
    except Exception as e:
        logger.error(f"BI5 ZIP upload error: {str(e)}", exc_info=True)
        return BulkIngestionResponse(
            success=False,
            message=f"ZIP processing error: {str(e)}",
            upload_batch_id=batch_id,
            symbol=symbol,
            errors=[str(e)]
        )


def parse_bi5_filename(filename: str) -> Optional[datetime]:
    """
    Parse date/hour from BI5 filename.
    
    Supported formats:
    - EURUSD_2024_01_15_10.bi5
    - 2024-01-15T10.bi5
    - 2024_01_15_10h00.bi5
    - 01h_15012024.bi5 (Dukascopy format)
    """
    import re
    
    # Remove path and extension
    basename = os.path.basename(filename)
    name = basename.rsplit('.', 1)[0]
    
    # Try different patterns
    patterns = [
        # SYMBOL_YYYY_MM_DD_HH
        r'_?(\d{4})_(\d{2})_(\d{2})_(\d{2})',
        # YYYY-MM-DDTHH or YYYY-MM-DD_HH
        r'(\d{4})-(\d{2})-(\d{2})[T_](\d{2})',
        # YYYY_MM_DD_HHh
        r'(\d{4})_(\d{2})_(\d{2})_(\d{2})h',
        # HHh_DDMMYYYY (Dukascopy)
        r'(\d{2})h_(\d{2})(\d{2})(\d{4})',
    ]
    
    for i, pattern in enumerate(patterns):
        match = re.search(pattern, name)
        if match:
            groups = match.groups()
            try:
                if i == 3:  # Dukascopy format
                    hour, day, month, year = groups
                    return datetime(int(year), int(month), int(day), int(hour), tzinfo=timezone.utc)
                else:
                    year, month, day, hour = groups
                    return datetime(int(year), int(month), int(day), int(hour), tzinfo=timezone.utc)
            except (ValueError, IndexError):
                continue
    
    # Try to find any 4 consecutive numbers that could be YYYY, MM, DD, HH
    numbers = re.findall(r'\d+', name)
    if len(numbers) >= 4:
        try:
            # Assume first 4 numbers are year, month, day, hour
            year = int(numbers[0]) if int(numbers[0]) > 1900 else int(numbers[3])
            month = int(numbers[1]) if int(numbers[0]) > 1900 else int(numbers[2])
            day = int(numbers[2]) if int(numbers[0]) > 1900 else int(numbers[1])
            hour = int(numbers[3]) if int(numbers[0]) > 1900 else int(numbers[0])
            
            if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour <= 23:
                return datetime(year, month, day, hour, tzinfo=timezone.utc)
        except (ValueError, IndexError):
            pass
    
    return None


# ========== EXPORT/DOWNLOAD ENDPOINTS (NEW) ==========

@router.get("/export/m1/{symbol}")
async def export_m1_csv(
    symbol: str,
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    min_confidence: str = Query("high", description="Minimum confidence filter")
):
    """
    Export M1 data as CSV download.
    
    This is the raw stored M1 data (SSOT).
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        # Parse dates
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00")) if start_date else None
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00")) if end_date else None
        
        # If no dates, get full range from coverage
        if not start or not end:
            coverage = await data_service.get_coverage(symbol)
            if not coverage.first_timestamp:
                raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
            start = start or coverage.first_timestamp
            end = end or coverage.last_timestamp
        
        # Get M1 data directly
        candles = await data_service.get_m1_direct(
            symbol=symbol,
            start_date=start,
            end_date=end,
            min_confidence=min_confidence
        )
        
        if not candles:
            raise HTTPException(status_code=404, detail=f"No M1 data found for {symbol} in date range")
        
        # Build CSV
        csv_content = generate_csv(candles, symbol, "M1")
        
        # Return as download
        filename = f"{symbol}_M1_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv"
        
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"M1 export error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{timeframe}/{symbol}")
async def export_aggregated_csv(
    symbol: str,
    timeframe: str,
    start_date: str = Query(..., description="Start date (ISO format)"),
    end_date: str = Query(..., description="End date (ISO format)"),
    min_confidence: str = Query("high", description="Minimum confidence filter")
):
    """
    Export aggregated data as CSV download.
    
    Data is ALWAYS derived from M1 (SSOT principle).
    Supported timeframes: M1, M5, M15, M30, H1, H4, D1
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    # Validate timeframe
    valid_tfs = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
    if timeframe.upper() not in valid_tfs:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid timeframe: {timeframe}. Valid: {valid_tfs}"
        )
    
    try:
        # Parse dates
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        
        # Get aggregated data
        result = await data_service.get_candles(
            symbol=symbol,
            timeframe=timeframe.upper(),
            start_date=start,
            end_date=end,
            min_confidence=min_confidence,
            use_case="research_backtest" if min_confidence != "high" else "production_backtest"
        )
        
        if not result.candles:
            raise HTTPException(
                status_code=404, 
                detail=f"No {timeframe} data found for {symbol} in date range"
            )
        
        # Convert aggregated candles to dict format
        candles = [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume
            }
            for c in result.candles
        ]
        
        # Build CSV
        csv_content = generate_csv(candles, symbol, timeframe.upper())
        
        # Add quality info as comment
        quality_header = f"# Quality Score: {result.quality_score:.2%}, Gaps: {result.gaps_detected}, Source M1: {result.source_m1_count}\n"
        csv_content = quality_header + csv_content
        
        # Return as download
        filename = f"{symbol}_{timeframe}_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv"
        
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def generate_csv(candles: List[Dict], symbol: str, timeframe: str) -> str:
    """Generate CSV content from candles."""
    lines = ["timestamp,open,high,low,close,volume"]
    
    for c in candles:
        ts = c["timestamp"]
        if isinstance(ts, datetime):
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        else:
            ts_str = str(ts)
        
        lines.append(f"{ts_str},{c['open']},{c['high']},{c['low']},{c['close']},{c['volume']}")
    
    return "\n".join(lines)


# ========== CANDLE RETRIEVAL ==========

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
    Higher TF = aggregated on-demand from M1
    """
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        
        result = await data_service.get_candles(
            symbol=symbol,
            timeframe=timeframe.upper(),
            start_date=start,
            end_date=end,
            min_confidence=min_confidence,
            use_case=use_case
        )
        
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
            timeframe=timeframe.upper(),
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


# ========== COVERAGE & QUALITY ==========

@router.get("/coverage/{symbol}", response_model=CoverageResponse)
async def get_coverage(symbol: str):
    """Get data coverage report for a symbol."""
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
    """Get detailed quality report for a date range."""
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        
        report = await data_service.get_quality_report(
            symbol=symbol,
            timeframe=timeframe.upper(),
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


# ========== GAP MANAGEMENT ==========

@router.get("/gaps/{symbol}/detect", response_model=GapDetectionResponse)
async def detect_gaps(
    symbol: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Detect gaps in M1 data."""
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
    """Fix gaps with real Dukascopy data (NO interpolation)."""
    if data_service is None:
        raise HTTPException(status_code=500, detail="Data service not initialized")
    
    try:
        gaps = await data_service.detect_gaps(symbol)
        
        if not gaps:
            return {
                "success": True,
                "message": "No gaps detected",
                "gaps_fixed": 0,
                "candles_added": 0
            }
        
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


# ========== MAINTENANCE ==========

@router.delete("/purge/{symbol}/low-confidence")
async def purge_low_confidence(symbol: str):
    """Remove LOW confidence data from database."""
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
async def delete_symbol_data(symbol: str, confirm: bool = Query(False)):
    """Delete ALL data for a symbol (requires confirm=true)."""
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
    """Health check for data ingestion system."""
    return {
        "status": "healthy",
        "service": "Data Ingestion V2",
        "architecture": "M1 SSOT",
        "features": [
            "CSV upload (M1 only)",
            "BI5 single file upload",
            "BI5 ZIP bulk upload",
            "M1 export download",
            "Aggregated TF export",
            "On-demand timeframe aggregation",
            "Confidence-based filtering",
            "Gap detection and real-data filling"
        ],
        "rules": [
            "ONLY M1 data stored",
            "NO interpolation or synthetic data",
            "Higher TF CSV REJECTED by default",
            "All timeframes derived from M1",
            "Exports always from M1 source"
        ]
    }
