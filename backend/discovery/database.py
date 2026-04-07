"""
Database Module - Phase 4
MongoDB integration for strategy library storage
"""

import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection


logger = logging.getLogger(__name__)


class StrategyLibraryDB:
    """
    MongoDB database handler for strategy library
    
    Collections:
    - strategy_library: Approved strategies
    - pending_strategies: Strategies awaiting review
    - rejected_strategies: Rejected strategies (for reference)
    - discovery_logs: Processing logs
    """
    
    COLLECTION_LIBRARY = "strategy_library"
    COLLECTION_PENDING = "pending_strategies"
    COLLECTION_REJECTED = "rejected_strategies"
    COLLECTION_LOGS = "discovery_logs"
    
    # Approval thresholds
    MIN_PROP_SCORE = 80
    MAX_DRAWDOWN = 6.0
    MAX_RISK_OF_RUIN = 5.0
    
    def __init__(self, mongo_url: Optional[str] = None, db_name: Optional[str] = None):
        """
        Initialize database connection
        
        Args:
            mongo_url: MongoDB connection URL
            db_name: Database name
        """
        self.mongo_url = mongo_url or os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        self.db_name = db_name or os.environ.get('DB_NAME', 'cbot_analyzer')
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None
    
    async def connect(self):
        """Establish database connection"""
        if self._client is None:
            self._client = AsyncIOMotorClient(self.mongo_url)
            self._db = self._client[self.db_name]
            
            # Ensure indexes
            await self._ensure_indexes()
            
            logger.info(f"Connected to MongoDB: {self.db_name}")
    
    async def close(self):
        """Close database connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
    
    async def _ensure_indexes(self):
        """Create necessary indexes"""
        library = self._db[self.COLLECTION_LIBRARY]
        
        # Compound index for sorting and filtering
        await library.create_index([("score.total_score", -1)])
        await library.create_index([("score.grade", 1)])
        await library.create_index([("source.repo_full_name", 1)])
        await library.create_index([("metadata.category", 1)])
        await library.create_index([("created_at", -1)])
        
        # Text index for search
        await library.create_index([
            ("strategy_name", "text"),
            ("source.description", "text"),
            ("metadata.category", "text")
        ])
    
    @property
    def library(self) -> AsyncIOMotorCollection:
        """Get strategy library collection"""
        return self._db[self.COLLECTION_LIBRARY]
    
    @property
    def pending(self) -> AsyncIOMotorCollection:
        """Get pending strategies collection"""
        return self._db[self.COLLECTION_PENDING]
    
    @property
    def rejected(self) -> AsyncIOMotorCollection:
        """Get rejected strategies collection"""
        return self._db[self.COLLECTION_REJECTED]
    
    @property
    def logs(self) -> AsyncIOMotorCollection:
        """Get discovery logs collection"""
        return self._db[self.COLLECTION_LOGS]
    
    def _should_approve(self, score: Dict) -> bool:
        """Check if strategy meets approval criteria"""
        return (
            score.get('prop_score', 0) >= self.MIN_PROP_SCORE and
            score.get('max_drawdown', 100) < self.MAX_DRAWDOWN and
            score.get('risk_of_ruin', 100) < self.MAX_RISK_OF_RUIN
        )
    
    async def save_strategy(
        self,
        strategy_name: str,
        original_code: str,
        parsed_data: Dict,
        improved_strategy: Dict,
        generated_bot: Optional[Dict],
        score: Dict,
        source: Dict,
        force_save: bool = False
    ) -> Dict[str, Any]:
        """
        Save a processed strategy to appropriate collection
        
        Args:
            strategy_name: Name of the strategy
            original_code: Original C# code
            parsed_data: Parsed bot data
            improved_strategy: Refined strategy
            generated_bot: Generated optimized bot code
            score: Scoring results
            source: Source information (GitHub repo, etc.)
            force_save: Save regardless of approval status
        
        Returns:
            Dict with save result and strategy ID
        """
        await self.connect()
        
        # Determine approval status
        approved = self._should_approve(score)
        
        # Prepare document
        doc = {
            "strategy_name": strategy_name,
            "original_code": original_code,
            "parsed_data": parsed_data,
            "improved_strategy": improved_strategy,
            "generated_bot": generated_bot,
            "score": score,
            "source": source,
            "metadata": {
                "category": improved_strategy.get('category', 'unknown'),
                "indicators_count": len(improved_strategy.get('indicators', [])),
                "filters_count": len(improved_strategy.get('filters', [])),
                "has_risk_management": score.get('prop_score', 0) >= 70
            },
            "status": "approved" if approved else "rejected",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Remove _id fields to avoid serialization issues
        self._clean_object_ids(doc)
        
        if approved or force_save:
            # Save to library
            result = await self.library.insert_one(doc)
            strategy_id = str(result.inserted_id)
            
            logger.info(f"Strategy approved and saved: {strategy_name} (ID: {strategy_id})")
            
            return {
                "saved": True,
                "approved": True,
                "collection": self.COLLECTION_LIBRARY,
                "strategy_id": strategy_id,
                "score": score.get('total_score'),
                "grade": score.get('grade')
            }
        else:
            # Save to rejected for reference
            result = await self.rejected.insert_one(doc)
            strategy_id = str(result.inserted_id)
            
            logger.info(f"Strategy rejected: {strategy_name} (ID: {strategy_id})")
            
            return {
                "saved": True,
                "approved": False,
                "collection": self.COLLECTION_REJECTED,
                "strategy_id": strategy_id,
                "score": score.get('total_score'),
                "grade": score.get('grade'),
                "rejection_reasons": score.get('rejection_reasons', [])
            }
    
    def _clean_object_ids(self, doc: Dict):
        """Remove or convert ObjectId fields for JSON compatibility"""
        if '_id' in doc:
            del doc['_id']
        for key, value in doc.items():
            if isinstance(value, dict):
                self._clean_object_ids(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._clean_object_ids(item)
    
    async def get_top_strategies(
        self,
        limit: int = 10,
        category: Optional[str] = None,
        min_score: float = 0
    ) -> List[Dict]:
        """
        Get top ranked strategies
        
        Args:
            limit: Maximum number of results
            category: Filter by category (optional)
            min_score: Minimum total score (optional)
        
        Returns:
            List of strategy documents
        """
        await self.connect()
        
        query = {"status": "approved"}
        if category:
            query["metadata.category"] = category
        if min_score > 0:
            query["score.total_score"] = {"$gte": min_score}
        
        cursor = self.library.find(
            query,
            {"original_code": 0}  # Exclude large code field for list view
        ).sort("score.total_score", -1).limit(limit)
        
        strategies = []
        async for doc in cursor:
            doc['_id'] = str(doc['_id'])
            strategies.append(doc)
        
        return strategies
    
    async def get_strategy_by_id(self, strategy_id: str) -> Optional[Dict]:
        """
        Get a specific strategy by ID
        
        Args:
            strategy_id: MongoDB ObjectId as string
        
        Returns:
            Strategy document or None
        """
        await self.connect()
        
        try:
            doc = await self.library.find_one({"_id": ObjectId(strategy_id)})
            if doc:
                doc['_id'] = str(doc['_id'])
                return doc
        except Exception as e:
            logger.error(f"Error fetching strategy {strategy_id}: {e}")
        
        return None
    
    async def search_strategies(
        self,
        query: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Search strategies by text
        
        Args:
            query: Search query
            limit: Maximum results
        
        Returns:
            List of matching strategies
        """
        await self.connect()
        
        cursor = self.library.find(
            {"$text": {"$search": query}, "status": "approved"},
            {"score": {"$meta": "textScore"}, "original_code": 0}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        
        strategies = []
        async for doc in cursor:
            doc['_id'] = str(doc['_id'])
            strategies.append(doc)
        
        return strategies
    
    async def get_statistics(self) -> Dict:
        """Get library statistics"""
        await self.connect()
        
        total_approved = await self.library.count_documents({"status": "approved"})
        total_rejected = await self.rejected.count_documents({})
        
        # Category breakdown
        pipeline = [
            {"$match": {"status": "approved"}},
            {"$group": {"_id": "$metadata.category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        categories = {}
        async for doc in self.library.aggregate(pipeline):
            categories[doc['_id']] = doc['count']
        
        # Grade breakdown
        pipeline = [
            {"$match": {"status": "approved"}},
            {"$group": {"_id": "$score.grade", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        grades = {}
        async for doc in self.library.aggregate(pipeline):
            grades[doc['_id']] = doc['count']
        
        # Average score
        pipeline = [
            {"$match": {"status": "approved"}},
            {"$group": {"_id": None, "avg_score": {"$avg": "$score.total_score"}}}
        ]
        avg_score = 0
        async for doc in self.library.aggregate(pipeline):
            avg_score = doc['avg_score']
        
        return {
            "total_approved": total_approved,
            "total_rejected": total_rejected,
            "categories": categories,
            "grades": grades,
            "average_score": round(avg_score, 2) if avg_score else 0
        }
    
    async def log_discovery_run(
        self,
        bots_fetched: int,
        bots_analyzed: int,
        bots_approved: int,
        bots_rejected: int,
        duration_seconds: float,
        errors: List[str]
    ):
        """Log a discovery run for tracking"""
        await self.connect()
        
        doc = {
            "timestamp": datetime.utcnow(),
            "bots_fetched": bots_fetched,
            "bots_analyzed": bots_analyzed,
            "bots_approved": bots_approved,
            "bots_rejected": bots_rejected,
            "duration_seconds": duration_seconds,
            "errors": errors
        }
        
        await self.logs.insert_one(doc)
    
    async def delete_strategy(self, strategy_id: str) -> bool:
        """Delete a strategy by ID"""
        await self.connect()
        
        try:
            result = await self.library.delete_one({"_id": ObjectId(strategy_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting strategy {strategy_id}: {e}")
            return False


def create_strategy_db(mongo_url: Optional[str] = None, db_name: Optional[str] = None) -> StrategyLibraryDB:
    """Factory function to create database handler"""
    return StrategyLibraryDB(mongo_url=mongo_url, db_name=db_name)
