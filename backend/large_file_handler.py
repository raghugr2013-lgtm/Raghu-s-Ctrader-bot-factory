"""
Large File Upload Handler
Implements chunked upload and streaming processing for large datasets (1m/5m Dukascopy data).
"""

import os
import logging
import asyncio
from pathlib import Path
from typing import Optional, AsyncIterator
from fastapi import UploadFile
import pandas as pd
from io import StringIO

logger = logging.getLogger(__name__)

# Configuration
MAX_CHUNK_SIZE = 50 * 1024 * 1024  # 50MB chunks
MAX_TOTAL_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB total limit
STREAMING_THRESHOLD = 100 * 1024 * 1024  # 100MB - use streaming above this


class ChunkedFileProcessor:
    """
    Processes large files in chunks to avoid memory issues.
    Supports streaming CSV parsing for Dukascopy/MT4/MT5 data.
    """
    
    @staticmethod
    async def save_upload_chunked(
        file: UploadFile,
        destination: str,
        chunk_size: int = 10 * 1024 * 1024  # 10MB chunks
    ) -> dict:
        """
        Save uploaded file in chunks to avoid loading entire file into memory.
        
        Args:
            file: FastAPI UploadFile object
            destination: Path to save file
            chunk_size: Size of each chunk in bytes
            
        Returns:
            Dict with file info (size, path, chunks_processed)
        """
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        total_size = 0
        chunks_processed = 0
        
        try:
            with open(destination, 'wb') as f:
                while True:
                    # Read chunk
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    
                    # Write chunk
                    f.write(chunk)
                    total_size += len(chunk)
                    chunks_processed += 1
                    
                    # Check total size limit
                    if total_size > MAX_TOTAL_FILE_SIZE:
                        raise ValueError(f"File exceeds maximum size limit of {MAX_TOTAL_FILE_SIZE} bytes")
                    
                    # Log progress every 10 chunks
                    if chunks_processed % 10 == 0:
                        logger.info(f"Progress: {total_size / (1024*1024):.1f}MB uploaded ({chunks_processed} chunks)")
            
            logger.info(f"✓ File saved: {destination} ({total_size / (1024*1024):.1f}MB)")
            
            return {
                "success": True,
                "path": destination,
                "size_bytes": total_size,
                "size_mb": round(total_size / (1024*1024), 2),
                "chunks_processed": chunks_processed
            }
            
        except Exception as e:
            logger.error(f"Chunked upload failed: {str(e)}")
            # Cleanup partial file
            if os.path.exists(destination):
                os.remove(destination)
            raise
    
    @staticmethod
    def stream_csv_reader(
        file_path: str,
        chunksize: int = 10000  # Process 10k rows at a time
    ) -> AsyncIterator[pd.DataFrame]:
        """
        Stream large CSV file in chunks using pandas.
        
        Args:
            file_path: Path to CSV file
            chunksize: Number of rows per chunk
            
        Yields:
            DataFrame chunks
        """
        try:
            # Use pandas read_csv with chunksize for memory-efficient streaming
            for chunk in pd.read_csv(file_path, chunksize=chunksize):
                yield chunk
                
        except Exception as e:
            logger.error(f"CSV streaming failed: {str(e)}")
            raise
    
    @staticmethod
    def process_csv_streaming(
        file_path: str,
        processor_func: callable,
        chunksize: int = 10000
    ) -> dict:
        """
        Process large CSV file in streaming mode.
        
        Args:
            file_path: Path to CSV file
            processor_func: Function to process each chunk (receives DataFrame, returns stats)
            chunksize: Rows per chunk
            
        Returns:
            Aggregated processing results
        """
        total_rows = 0
        chunks_processed = 0
        aggregated_result = {}
        
        try:
            for chunk_df in pd.read_csv(file_path, chunksize=chunksize):
                # Process chunk
                chunk_result = processor_func(chunk_df)
                
                # Aggregate results
                if chunks_processed == 0:
                    aggregated_result = chunk_result
                else:
                    # Merge results (custom logic per use case)
                    for key, value in chunk_result.items():
                        if isinstance(value, (int, float)):
                            aggregated_result[key] = aggregated_result.get(key, 0) + value
                
                total_rows += len(chunk_df)
                chunks_processed += 1
                
                if chunks_processed % 10 == 0:
                    logger.info(f"Processed {total_rows:,} rows ({chunks_processed} chunks)")
            
            logger.info(f"✓ CSV processing complete: {total_rows:,} rows")
            
            return {
                "success": True,
                "total_rows": total_rows,
                "chunks_processed": chunks_processed,
                "results": aggregated_result
            }
            
        except Exception as e:
            logger.error(f"CSV processing failed: {str(e)}")
            raise
    
    @staticmethod
    def validate_csv_structure(file_path: str, required_columns: list = None) -> dict:
        """
        Validate CSV structure without loading entire file.
        Reads only first 1000 rows.
        
        Args:
            file_path: Path to CSV file
            required_columns: List of required column names
            
        Returns:
            Validation result dict
        """
        try:
            # Read only first chunk
            sample_df = pd.read_csv(file_path, nrows=1000)
            
            columns = list(sample_df.columns)
            dtypes = {col: str(dtype) for col, dtype in sample_df.dtypes.items()}
            
            # Check required columns
            missing_columns = []
            if required_columns:
                missing_columns = [col for col in required_columns if col not in columns]
            
            is_valid = len(missing_columns) == 0
            
            return {
                "valid": is_valid,
                "columns": columns,
                "dtypes": dtypes,
                "sample_rows": len(sample_df),
                "missing_columns": missing_columns,
                "has_timestamp": any('time' in col.lower() or 'date' in col.lower() for col in columns),
                "has_ohlc": all(col.upper() in columns or col.lower() in columns for col in ['open', 'high', 'low', 'close'])
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }


class DataUploadManager:
    """
    Manages data uploads with progress tracking and validation.
    """
    
    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = data_dir
        self.processor = ChunkedFileProcessor()
        os.makedirs(data_dir, exist_ok=True)
    
    async def upload_market_data(
        self,
        file: UploadFile,
        symbol: str,
        timeframe: str,
        year: Optional[int] = None
    ) -> dict:
        """
        Upload market data CSV with chunked processing.
        
        Args:
            file: Uploaded file
            symbol: Trading symbol (e.g., EURUSD)
            timeframe: Timeframe (e.g., 1m, 5m, 1h)
            year: Optional year for organization
            
        Returns:
            Upload result with file info
        """
        try:
            # Validate filename
            if not file.filename.endswith('.csv'):
                raise ValueError("Only CSV files are supported")
            
            # Construct destination path
            symbol_dir = os.path.join(self.data_dir, symbol, timeframe)
            os.makedirs(symbol_dir, exist_ok=True)
            
            filename = f"{year}.csv" if year else file.filename
            destination = os.path.join(symbol_dir, filename)
            
            logger.info(f"Uploading {file.filename} → {destination}")
            
            # Save file in chunks
            upload_result = await self.processor.save_upload_chunked(file, destination)
            
            # Validate CSV structure
            validation = self.processor.validate_csv_structure(
                destination,
                required_columns=['time', 'open', 'high', 'low', 'close']  # Flexible validation
            )
            
            if not validation.get('has_ohlc', False):
                logger.warning(f"CSV may not have OHLC columns: {validation.get('columns', [])}")
            
            return {
                "success": True,
                "symbol": symbol,
                "timeframe": timeframe,
                "file_path": destination,
                "size_mb": upload_result["size_mb"],
                "chunks_processed": upload_result["chunks_processed"],
                "validation": validation
            }
            
        except Exception as e:
            logger.error(f"Market data upload failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
