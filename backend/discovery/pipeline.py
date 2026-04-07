"""
Discovery Pipeline - Phase 2
Orchestrates the full Fetch → Analyze → Refine → Validate → Score flow
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

from .bot_fetcher import GitHubBotFetcher, FetchedBot, create_bot_fetcher
from .scoring_engine import ScoringEngine, StrategyScore, create_scoring_engine
from .database import StrategyLibraryDB, create_strategy_db

# Import analyzer modules
import sys
sys.path.insert(0, '..')
from analyzer.csharp_parser import CSharpBotParser
from analyzer.strategy_parser import StrategyParser
from analyzer.refinement_engine import create_refinement_engine
from analyzer.improved_bot_generator import create_bot_generator


logger = logging.getLogger(__name__)


@dataclass
class ProcessedBot:
    """Result of processing a single bot"""
    source: Dict[str, Any]
    parsed: Optional[Dict[str, Any]] = None
    strategy: Optional[Dict[str, Any]] = None
    improved_strategy: Optional[Dict[str, Any]] = None
    generated_bot: Optional[Dict[str, Any]] = None
    score: Optional[Dict[str, Any]] = None
    issues: List[Dict[str, Any]] = field(default_factory=list)
    changes_made: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    error: Optional[str] = None
    processing_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineResult:
    """Result of running the discovery pipeline"""
    total_fetched: int
    total_processed: int
    total_approved: int
    total_rejected: int
    total_errors: int
    processed_bots: List[ProcessedBot]
    approved_strategies: List[Dict[str, Any]]
    errors: List[str]
    duration_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_fetched": self.total_fetched,
            "total_processed": self.total_processed,
            "total_approved": self.total_approved,
            "total_rejected": self.total_rejected,
            "total_errors": self.total_errors,
            "approved_strategies": self.approved_strategies,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 2),
            "timestamp": self.timestamp
        }
    
    def summary(self) -> Dict[str, Any]:
        """Get summary without full processed_bots list"""
        return {
            "total_fetched": self.total_fetched,
            "total_processed": self.total_processed,
            "total_approved": self.total_approved,
            "total_rejected": self.total_rejected,
            "total_errors": self.total_errors,
            "approval_rate": f"{(self.total_approved / max(self.total_processed, 1)) * 100:.1f}%",
            "duration_seconds": round(self.duration_seconds, 2),
            "timestamp": self.timestamp
        }


class DiscoveryPipeline:
    """
    Orchestrates the full bot discovery pipeline:
    Fetch → Analyze → Refine → Validate → Score → Store
    """
    
    def __init__(
        self,
        github_token: Optional[str] = None,
        min_stars: int = 10,
        mongo_url: Optional[str] = None,
        db_name: Optional[str] = None,
        generate_bots: bool = True,
        save_to_db: bool = True
    ):
        """
        Initialize the pipeline
        
        Args:
            github_token: GitHub API token
            min_stars: Minimum stars for repo filter
            mongo_url: MongoDB connection URL
            db_name: Database name
            generate_bots: Whether to generate optimized bot code
            save_to_db: Whether to save results to database
        """
        self.github_token = github_token
        self.min_stars = min_stars
        self.mongo_url = mongo_url
        self.db_name = db_name
        self.generate_bots = generate_bots
        self.save_to_db = save_to_db
        
        # Initialize components lazily
        self._fetcher: Optional[GitHubBotFetcher] = None
        self._scoring_engine: Optional[ScoringEngine] = None
        self._db: Optional[StrategyLibraryDB] = None
    
    @property
    def fetcher(self) -> GitHubBotFetcher:
        if self._fetcher is None:
            self._fetcher = create_bot_fetcher(
                github_token=self.github_token,
                min_stars=self.min_stars
            )
        return self._fetcher
    
    @property
    def scoring_engine(self) -> ScoringEngine:
        if self._scoring_engine is None:
            self._scoring_engine = create_scoring_engine()
        return self._scoring_engine
    
    @property
    def db(self) -> StrategyLibraryDB:
        if self._db is None:
            self._db = create_strategy_db(
                mongo_url=self.mongo_url,
                db_name=self.db_name
            )
        return self._db
    
    async def run(
        self,
        max_repos: int = 20,
        max_bots_per_repo: int = 5
    ) -> PipelineResult:
        """
        Run the full discovery pipeline
        
        Args:
            max_repos: Maximum repositories to search
            max_bots_per_repo: Maximum bots per repository
        
        Returns:
            PipelineResult with all processing results
        """
        start_time = time.time()
        errors = []
        processed_bots = []
        approved_strategies = []
        
        # Phase 1: Fetch bots from GitHub
        logger.info("Phase 1: Fetching bots from GitHub...")
        try:
            fetched_bots = await self.fetcher.fetch_bots(
                max_repos=max_repos,
                max_bots_per_repo=max_bots_per_repo
            )
            logger.info(f"Fetched {len(fetched_bots)} bots")
        except Exception as e:
            error_msg = f"Fetch failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            fetched_bots = []
        
        # Process each bot
        for idx, bot in enumerate(fetched_bots):
            logger.info(f"Processing bot {idx + 1}/{len(fetched_bots)}: {bot.repo_full_name}/{bot.file_path}")
            
            try:
                processed = await self._process_single_bot(bot)
                processed_bots.append(processed)
                
                if processed.status == "approved":
                    approved_strategies.append({
                        "strategy_name": processed.improved_strategy.get('name', 'Unknown'),
                        "source": processed.source,
                        "score": processed.score,
                        "grade": processed.score.get('grade') if processed.score else 'N/A'
                    })
                elif processed.error:
                    errors.append(f"{bot.repo_full_name}: {processed.error}")
                    
            except Exception as e:
                error_msg = f"Error processing {bot.repo_full_name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                processed_bots.append(ProcessedBot(
                    source=bot.to_dict(),
                    status="error",
                    error=str(e)
                ))
        
        # Calculate stats
        total_approved = sum(1 for p in processed_bots if p.status == "approved")
        total_rejected = sum(1 for p in processed_bots if p.status == "rejected")
        total_errors = sum(1 for p in processed_bots if p.status == "error")
        
        duration = time.time() - start_time
        
        # Log discovery run
        if self.save_to_db:
            try:
                await self.db.log_discovery_run(
                    bots_fetched=len(fetched_bots),
                    bots_analyzed=len(processed_bots),
                    bots_approved=total_approved,
                    bots_rejected=total_rejected,
                    duration_seconds=duration,
                    errors=errors[:10]  # Limit stored errors
                )
            except Exception as e:
                logger.error(f"Failed to log discovery run: {e}")
        
        # Close connections
        await self.fetcher.close()
        if self._db:
            await self._db.close()
        
        logger.info(f"Pipeline complete: {total_approved} approved, {total_rejected} rejected, {total_errors} errors in {duration:.1f}s")
        
        return PipelineResult(
            total_fetched=len(fetched_bots),
            total_processed=len(processed_bots),
            total_approved=total_approved,
            total_rejected=total_rejected,
            total_errors=total_errors,
            processed_bots=processed_bots,
            approved_strategies=approved_strategies,
            errors=errors,
            duration_seconds=duration
        )
    
    async def _process_single_bot(self, bot: FetchedBot) -> ProcessedBot:
        """
        Process a single fetched bot through the full pipeline
        """
        start_time = time.time()
        result = ProcessedBot(source=bot.to_dict())
        
        try:
            # Phase 2a: Parse C# code
            parser = CSharpBotParser()
            parsed_bot = parser.parse(bot.code)
            result.parsed = parsed_bot.to_dict()
            
            # Check if parsing found anything useful
            if not parsed_bot.indicators and not parsed_bot.entry_conditions:
                result.status = "rejected"
                result.error = "No trading logic detected"
                result.processing_time = time.time() - start_time
                return result
            
            # Phase 2b: Convert to strategy
            strategy_parser = StrategyParser()
            strategy = strategy_parser.parse(parsed_bot)
            result.strategy = strategy.to_dict()
            
            # Phase 2c: Refine strategy
            refinement_engine = create_refinement_engine()
            refinement_result = refinement_engine.refine(
                result.parsed,
                result.strategy
            )
            
            result.improved_strategy = refinement_result.improved_strategy
            result.issues = [asdict(i) for i in refinement_result.issues]
            result.changes_made = [asdict(c) for c in refinement_result.changes_made]
            
            # Phase 2d: Generate optimized bot (optional)
            if self.generate_bots:
                generator = create_bot_generator()
                generated = generator.generate(
                    result.improved_strategy,
                    result.parsed
                )
                result.generated_bot = generated.to_dict()
            
            # Phase 3: Score strategy
            score = self.scoring_engine.score(
                result.improved_strategy,
                result.parsed
            )
            result.score = score.to_dict()
            
            # Determine approval status
            if score.status == "approved":
                result.status = "approved"
            elif score.status == "conditional":
                result.status = "conditional"
            else:
                result.status = "rejected"
            
            # Phase 4: Save to database (if approved and enabled)
            if self.save_to_db:
                save_result = await self.db.save_strategy(
                    strategy_name=result.improved_strategy.get('name', bot.repo_name),
                    original_code=bot.code,
                    parsed_data=result.parsed,
                    improved_strategy=result.improved_strategy,
                    generated_bot=result.generated_bot,
                    score=result.score,
                    source={
                        "repo_full_name": bot.repo_full_name,
                        "repo_owner": bot.repo_owner,
                        "stars": bot.stars,
                        "source_url": bot.source_url,
                        "file_path": bot.file_path,
                        "description": bot.description,
                        "license": bot.license
                    }
                )
                
                if save_result.get('approved'):
                    result.status = "approved"
                    logger.info(f"  ✓ Approved: {result.improved_strategy.get('name')} (Score: {score.total_score:.1f})")
                else:
                    result.status = "rejected"
                    logger.info(f"  ✗ Rejected: {result.improved_strategy.get('name')} (Score: {score.total_score:.1f})")
            
        except Exception as e:
            result.status = "error"
            result.error = str(e)
            logger.error(f"  Error: {str(e)}")
        
        result.processing_time = time.time() - start_time
        return result
    
    async def process_code(self, code: str, source_info: Optional[Dict] = None) -> ProcessedBot:
        """
        Process a single code snippet (not from GitHub)
        
        Args:
            code: C# cBot code
            source_info: Optional source metadata
        
        Returns:
            ProcessedBot result
        """
        bot = FetchedBot(
            repo_name="manual_input",
            repo_owner="user",
            repo_full_name="user/manual_input",
            stars=0,
            forks=0,
            description="Manually submitted code",
            code=code,
            file_path="manual.cs",
            source_url="",
            raw_url="",
            last_updated=datetime.utcnow().isoformat()
        )
        
        if source_info:
            for key, value in source_info.items():
                if hasattr(bot, key):
                    setattr(bot, key, value)
        
        return await self._process_single_bot(bot)
    
    async def process_repo(self, repo_url: str) -> PipelineResult:
        """
        Process a single GitHub repository
        
        Args:
            repo_url: GitHub repository URL
        
        Returns:
            PipelineResult for the repository
        """
        start_time = time.time()
        errors = []
        processed_bots = []
        approved_strategies = []
        
        try:
            # Fetch bots from repo
            fetched_bots = await self.fetcher.fetch_single_repo(repo_url)
            
            # Process each bot
            for bot in fetched_bots:
                try:
                    processed = await self._process_single_bot(bot)
                    processed_bots.append(processed)
                    
                    if processed.status == "approved":
                        approved_strategies.append({
                            "strategy_name": processed.improved_strategy.get('name', 'Unknown'),
                            "source": processed.source,
                            "score": processed.score
                        })
                except Exception as e:
                    errors.append(str(e))
                    processed_bots.append(ProcessedBot(
                        source=bot.to_dict(),
                        status="error",
                        error=str(e)
                    ))
                    
        except Exception as e:
            errors.append(f"Failed to process repo: {str(e)}")
        
        duration = time.time() - start_time
        
        return PipelineResult(
            total_fetched=len(processed_bots),
            total_processed=len(processed_bots),
            total_approved=sum(1 for p in processed_bots if p.status == "approved"),
            total_rejected=sum(1 for p in processed_bots if p.status == "rejected"),
            total_errors=sum(1 for p in processed_bots if p.status == "error"),
            processed_bots=processed_bots,
            approved_strategies=approved_strategies,
            errors=errors,
            duration_seconds=duration
        )


def create_pipeline(
    github_token: Optional[str] = None,
    min_stars: int = 10,
    mongo_url: Optional[str] = None,
    generate_bots: bool = True,
    save_to_db: bool = True
) -> DiscoveryPipeline:
    """Factory function to create discovery pipeline"""
    return DiscoveryPipeline(
        github_token=github_token,
        min_stars=min_stars,
        mongo_url=mongo_url,
        generate_bots=generate_bots,
        save_to_db=save_to_db
    )
