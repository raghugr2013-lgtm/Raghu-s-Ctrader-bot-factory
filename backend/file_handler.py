"""
File and Image Upload Handler
Supports trading bot files, documents, and images
"""

import os
import base64
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Allowed file extensions
ALLOWED_CODE_FILES = {'.cs', '.algo', '.csbots'}
ALLOWED_DOC_FILES = {'.pdf', '.txt', '.md'}
ALLOWED_DATA_FILES = {'.csv', '.xlsx', '.json', '.xml'}
ALLOWED_IMAGE_FILES = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}

ALL_ALLOWED_FILES = ALLOWED_CODE_FILES | ALLOWED_DOC_FILES | ALLOWED_DATA_FILES | ALLOWED_IMAGE_FILES

# Increased file size limits for large datasets
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB (was 10MB)
MAX_DATA_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB for data files specifically


class FileUploadHandler:
    """Handle file uploads and processing"""
    
    @staticmethod
    def validate_file(filename: str, file_size: int) -> tuple[bool, str]:
        """
        Validate file extension and size
        Returns: (is_valid, error_message)
        """
        file_ext = Path(filename).suffix.lower()
        
        if file_ext not in ALL_ALLOWED_FILES:
            return False, f"File type {file_ext} not allowed. Allowed: {', '.join(ALL_ALLOWED_FILES)}"
        
        # Use larger limit for data files
        max_size = MAX_DATA_FILE_SIZE if file_ext in ALLOWED_DATA_FILES else MAX_FILE_SIZE
        
        if file_size > max_size:
            return False, f"File size {file_size / (1024*1024):.1f}MB exceeds maximum {max_size / (1024*1024):.0f}MB"
        
        return True, ""
    
    @staticmethod
    def get_file_type(filename: str) -> str:
        """Determine file type category"""
        file_ext = Path(filename).suffix.lower()
        
        if file_ext in ALLOWED_CODE_FILES:
            return "code"
        elif file_ext in ALLOWED_DOC_FILES:
            return "document"
        elif file_ext in ALLOWED_DATA_FILES:
            return "data"
        elif file_ext in ALLOWED_IMAGE_FILES:
            return "image"
        else:
            return "unknown"
    
    @staticmethod
    def process_code_file(content: str, filename: str) -> Dict[str, Any]:
        """Process code files (.cs, .algo)"""
        lines = content.split('\n')
        
        analysis = {
            "filename": filename,
            "type": "code",
            "lines": len(lines),
            "has_robot_class": "Robot" in content,
            "has_ontick": "OnTick" in content,
            "has_onbar": "OnBar" in content,
            "has_onstart": "OnStart" in content,
            "has_trading_ops": any(op in content for op in ["ExecuteMarketOrder", "PlaceStopOrder", "PlaceLimitOrder"]),
            "summary": f"C# cTrader bot file with {len(lines)} lines"
        }
        
        return analysis
    
    @staticmethod
    def process_data_file(content: str, filename: str) -> Dict[str, Any]:
        """Process data files (.csv, .json, .xlsx)"""
        file_ext = Path(filename).suffix.lower()
        
        if file_ext == '.json':
            import json
            try:
                data = json.loads(content)
                return {
                    "filename": filename,
                    "type": "data",
                    "format": "json",
                    "keys": list(data.keys()) if isinstance(data, dict) else None,
                    "summary": f"JSON data file"
                }
            except json.JSONDecodeError:
                return {"filename": filename, "type": "data", "error": "Invalid JSON"}
        
        elif file_ext == '.csv':
            lines = content.split('\n')
            return {
                "filename": filename,
                "type": "data",
                "format": "csv",
                "rows": len(lines),
                "summary": f"CSV file with {len(lines)} rows"
            }
        
        return {
            "filename": filename,
            "type": "data",
            "summary": f"Data file: {filename}"
        }
    
    @staticmethod
    def encode_image_base64(content: bytes) -> str:
        """Encode image to base64 for vision APIs"""
        return base64.b64encode(content).decode('utf-8')
    
    @staticmethod
    def get_mime_type(filename: str) -> str:
        """Get MIME type for file"""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or 'application/octet-stream'


# Helper functions
def create_file_context(filename: str, content: str, file_type: str) -> str:
    """Create context string for AI from file"""
    
    if file_type == "code":
        return f"""
File: {filename}
Type: cTrader Bot Code
Content:
```csharp
{content[:5000]}  # Truncate to 5000 chars
{'... (truncated)' if len(content) > 5000 else ''}
```
"""
    
    elif file_type == "document":
        return f"""
File: {filename}
Type: Document
Content:
{content[:3000]}  # Truncate to 3000 chars
{'... (truncated)' if len(content) > 3000 else ''}
"""
    
    elif file_type == "data":
        return f"""
File: {filename}
Type: Data File
Content Preview:
{content[:2000]}  # Truncate to 2000 chars
{'... (truncated)' if len(content) > 2000 else ''}
"""
    
    return f"File: {filename}\nContent: {content[:1000]}"


def analyze_trading_image(image_description: str) -> Dict[str, str]:
    """Analyze trading image context"""
    keywords = {
        "equity": "Equity curve or balance chart",
        "chart": "Price chart or technical analysis",
        "backtest": "Backtesting results",
        "drawdown": "Drawdown analysis",
        "profit": "Profit/loss visualization",
        "trade": "Trade history or log"
    }
    
    image_type = "Trading screenshot"
    for keyword, description in keywords.items():
        if keyword.lower() in image_description.lower():
            image_type = description
            break
    
    return {
        "type": image_type,
        "context": "User uploaded a trading-related image for analysis"
    }
