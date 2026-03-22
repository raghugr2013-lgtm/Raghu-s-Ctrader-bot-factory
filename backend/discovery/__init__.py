# Bot Discovery System
# Fetch, analyze, refine, score, and store high-quality trading strategies

from .bot_fetcher import GitHubBotFetcher, FetchedBot
from .scoring_engine import ScoringEngine, StrategyScore
from .pipeline import DiscoveryPipeline, PipelineResult
from .database import StrategyLibraryDB

__all__ = [
    'GitHubBotFetcher',
    'FetchedBot', 
    'ScoringEngine',
    'StrategyScore',
    'DiscoveryPipeline',
    'PipelineResult',
    'StrategyLibraryDB'
]
