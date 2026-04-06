"""
cTrader Export Router
API endpoints for generating and downloading cTrader cBot files.
"""

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging
import io

from ctrader_bot_generator import CTraderBotGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ctrader", tags=["ctrader"])

# In-memory storage (in production, use MongoDB)
generated_bots = {}


class BotGenerationRequest(BaseModel):
    """Request to generate cTrader bot"""
    strategy_id: str = Field(..., description="Strategy ID")
    strategy: Dict[str, Any] = Field(..., description="Strategy configuration")
    include_comments: bool = Field(True, description="Include explanatory comments")
    include_risk_params: bool = Field(True, description="Include risk management parameters")


class BotGenerationResponse(BaseModel):
    """Response from bot generation"""
    success: bool
    bot_id: str
    bot_name: str
    file_size: int
    generated_at: str
    download_url: str
    preview: Optional[str] = None


class GeneratedBotInfo(BaseModel):
    """Information about a generated bot"""
    bot_id: str
    bot_name: str
    strategy_id: str
    strategy_name: str
    file_size: int
    generated_at: str
    code: str


@router.post("/generate-bot")
async def generate_bot(request: BotGenerationRequest):
    """
    Generate cTrader cBot C# code for a strategy.
    
    Returns bot_id for downloading the .cs file.
    """
    try:
        logger.info(f"[CTRADER API] Generating bot for strategy {request.strategy_id}")
        
        # Generate C# code
        generator = CTraderBotGenerator()
        cs_code = generator.generate_bot(
            strategy=request.strategy,
            include_comments=request.include_comments,
            include_risk_params=request.include_risk_params
        )
        
        # Create bot ID
        bot_id = str(uuid.uuid4())
        
        # Store in memory (in production, store in MongoDB)
        bot_name = request.strategy.get("name", "Strategy").replace(" ", "_").replace("-", "_")
        generated_bots[bot_id] = GeneratedBotInfo(
            bot_id=bot_id,
            bot_name=bot_name,
            strategy_id=request.strategy_id,
            strategy_name=request.strategy.get("name", "Unknown"),
            file_size=len(cs_code),
            generated_at=datetime.now().isoformat(),
            code=cs_code
        )
        
        # Create response
        response = BotGenerationResponse(
            success=True,
            bot_id=bot_id,
            bot_name=f"{bot_name}.cs",
            file_size=len(cs_code),
            generated_at=datetime.now().isoformat(),
            download_url=f"/api/ctrader/download/{bot_id}",
            preview=cs_code[:500] + "..." if len(cs_code) > 500 else cs_code
        )
        
        logger.info(f"[CTRADER API] ✓ Bot generated: {bot_id} ({len(cs_code)} bytes)")
        
        return response
        
    except Exception as e:
        logger.error(f"[CTRADER API] Failed to generate bot: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate bot: {str(e)}")


@router.get("/download/{bot_id}")
async def download_bot(bot_id: str):
    """
    Download generated cTrader bot as .cs file.
    """
    if bot_id not in generated_bots:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    bot_info = generated_bots[bot_id]
    
    logger.info(f"[CTRADER API] Downloading bot {bot_id}: {bot_info.bot_name}")
    
    # Create file response
    cs_code = bot_info.code
    filename = f"{bot_info.bot_name}.cs"
    
    # Return as downloadable file
    return Response(
        content=cs_code,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
            "Content-Type": "text/plain; charset=utf-8"
        }
    )


@router.get("/bot-info/{bot_id}")
async def get_bot_info(bot_id: str):
    """
    Get information about a generated bot.
    """
    if bot_id not in generated_bots:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    bot_info = generated_bots[bot_id]
    
    return {
        "success": True,
        "bot": {
            "bot_id": bot_info.bot_id,
            "bot_name": bot_info.bot_name,
            "strategy_id": bot_info.strategy_id,
            "strategy_name": bot_info.strategy_name,
            "file_size": bot_info.file_size,
            "generated_at": bot_info.generated_at,
            "download_url": f"/api/ctrader/download/{bot_id}"
        }
    }


@router.get("/list-bots")
async def list_generated_bots():
    """
    List all generated bots.
    """
    bots = [
        {
            "bot_id": bot.bot_id,
            "bot_name": bot.bot_name,
            "strategy_name": bot.strategy_name,
            "file_size": bot.file_size,
            "generated_at": bot.generated_at,
            "download_url": f"/api/ctrader/download/{bot.bot_id}"
        }
        for bot in generated_bots.values()
    ]
    
    return {
        "success": True,
        "count": len(bots),
        "bots": bots
    }


@router.post("/batch-generate")
async def batch_generate_bots(strategies: List[Dict[str, Any]]):
    """
    Generate cTrader bots for multiple strategies at once.
    """
    try:
        logger.info(f"[CTRADER API] Batch generating {len(strategies)} bots")
        
        generator = CTraderBotGenerator()
        results = []
        
        for strategy in strategies:
            try:
                # Generate C# code
                cs_code = generator.generate_bot(
                    strategy=strategy,
                    include_comments=True,
                    include_risk_params=True
                )
                
                # Create bot ID
                bot_id = str(uuid.uuid4())
                bot_name = strategy.get("name", "Strategy").replace(" ", "_").replace("-", "_")
                
                # Store
                generated_bots[bot_id] = GeneratedBotInfo(
                    bot_id=bot_id,
                    bot_name=bot_name,
                    strategy_id=strategy.get("id", "unknown"),
                    strategy_name=strategy.get("name", "Unknown"),
                    file_size=len(cs_code),
                    generated_at=datetime.now().isoformat(),
                    code=cs_code
                )
                
                results.append({
                    "success": True,
                    "bot_id": bot_id,
                    "bot_name": f"{bot_name}.cs",
                    "strategy_id": strategy.get("id"),
                    "download_url": f"/api/ctrader/download/{bot_id}"
                })
                
            except Exception as e:
                logger.error(f"[CTRADER API] Failed to generate bot for {strategy.get('name')}: {e}")
                results.append({
                    "success": False,
                    "strategy_id": strategy.get("id"),
                    "error": str(e)
                })
        
        successful = sum(1 for r in results if r.get("success"))
        logger.info(f"[CTRADER API] ✓ Batch complete: {successful}/{len(strategies)} successful")
        
        return {
            "success": True,
            "total": len(strategies),
            "successful": successful,
            "failed": len(strategies) - successful,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"[CTRADER API] Batch generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch generation failed: {str(e)}")


def init_ctrader_router(db):
    """Initialize router with database connection"""
    # Future: Use MongoDB to store generated bots
    pass
