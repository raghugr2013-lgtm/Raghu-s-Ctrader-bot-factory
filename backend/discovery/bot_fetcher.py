"""
Bot Fetcher - Phase 1
Fetches cBot strategies from GitHub using the Search API
"""

import os
import re
import time
import base64
import logging
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import aiohttp


logger = logging.getLogger(__name__)


@dataclass
class FetchedBot:
    """Represents a fetched bot from GitHub"""
    repo_name: str
    repo_owner: str
    repo_full_name: str
    stars: int
    forks: int
    description: str
    code: str
    file_path: str
    source_url: str
    raw_url: str
    last_updated: str
    license: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    fetch_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GitHubBotFetcher:
    """
    Fetches cTrader/cAlgo bots from GitHub
    Uses GitHub Search API with rate limiting
    """
    
    # Search queries for finding cBots
    SEARCH_QUERIES = [
        "cAlgo Robot language:csharp",
        "cTrader bot language:csharp",
        "cAlgo.API.Indicators language:csharp",
        "cAlgo.Robots language:csharp",
        ": Robot language:csharp cTrader",
    ]
    
    # File patterns to identify cBot files
    CBOT_PATTERNS = [
        r':\s*Robot\b',           # Inherits from Robot
        r'using\s+cAlgo\.API',    # Uses cAlgo API
        r'\[Robot\(',             # Has Robot attribute
        r'ExecuteMarketOrder',    # Has trade execution
    ]
    
    # GitHub API endpoints
    GITHUB_API = "https://api.github.com"
    SEARCH_ENDPOINT = "/search/code"
    REPOS_ENDPOINT = "/search/repositories"
    
    def __init__(self, github_token: Optional[str] = None, min_stars: int = 10):
        """
        Initialize the fetcher
        
        Args:
            github_token: GitHub personal access token (optional but recommended)
            min_stars: Minimum stars for repository filter
        """
        self.github_token = github_token or os.environ.get('GITHUB_TOKEN')
        self.min_stars = min_stars
        self.rate_limit_remaining = 30
        self.rate_limit_reset = 0
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "cBot-Discovery-System"
            }
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session
    
    async def close(self):
        """Close the session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _check_rate_limit(self, response: aiohttp.ClientResponse):
        """Update rate limit tracking from response headers"""
        self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 30))
        self.rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', 0))
        
        if self.rate_limit_remaining < 5:
            wait_time = max(self.rate_limit_reset - time.time(), 60)
            logger.warning(f"Rate limit low ({self.rate_limit_remaining}), waiting {wait_time}s")
            await asyncio.sleep(min(wait_time, 120))
    
    async def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make a rate-limited request to GitHub API"""
        session = await self._get_session()
        
        try:
            async with session.get(url, params=params) as response:
                await self._check_rate_limit(response)
                
                if response.status == 200:
                    return await response.json()
                elif response.status == 403:
                    logger.error(f"Rate limited or forbidden: {url}")
                    return None
                elif response.status == 404:
                    logger.debug(f"Not found: {url}")
                    return None
                else:
                    logger.error(f"GitHub API error {response.status}: {url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    async def search_repositories(self, query: str, max_results: int = 30) -> List[Dict]:
        """
        Search for repositories matching query
        
        Args:
            query: Search query string
            max_results: Maximum number of results
        
        Returns:
            List of repository data
        """
        repos = []
        page = 1
        per_page = min(max_results, 30)
        
        while len(repos) < max_results:
            params = {
                "q": f"{query} stars:>={self.min_stars}",
                "sort": "stars",
                "order": "desc",
                "per_page": per_page,
                "page": page
            }
            
            url = f"{self.GITHUB_API}{self.REPOS_ENDPOINT}"
            data = await self._make_request(url, params)
            
            if not data or 'items' not in data:
                break
            
            items = data['items']
            if not items:
                break
            
            repos.extend(items)
            page += 1
            
            # Small delay between pages
            await asyncio.sleep(1)
        
        return repos[:max_results]
    
    async def get_repo_contents(self, owner: str, repo: str, path: str = "") -> List[Dict]:
        """Get contents of a repository directory"""
        url = f"{self.GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        data = await self._make_request(url)
        return data if isinstance(data, list) else []
    
    async def get_file_content(self, owner: str, repo: str, path: str) -> Optional[str]:
        """Get content of a specific file"""
        url = f"{self.GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        data = await self._make_request(url)
        
        if data and 'content' in data:
            try:
                # GitHub returns base64 encoded content
                content = base64.b64decode(data['content']).decode('utf-8')
                return content
            except Exception as e:
                logger.error(f"Failed to decode file content: {e}")
        
        return None
    
    async def find_cbot_files(self, owner: str, repo: str, path: str = "", depth: int = 3) -> List[Dict]:
        """
        Recursively find .cs files that look like cBots
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: Current path (for recursion)
            depth: Maximum recursion depth
        
        Returns:
            List of file info dicts
        """
        if depth <= 0:
            return []
        
        cbot_files = []
        contents = await self.get_repo_contents(owner, repo, path)
        
        for item in contents:
            if item['type'] == 'file' and item['name'].endswith('.cs'):
                # Check if file might be a cBot
                content = await self.get_file_content(owner, repo, item['path'])
                if content and self._is_cbot_code(content):
                    cbot_files.append({
                        'path': item['path'],
                        'name': item['name'],
                        'url': item['html_url'],
                        'download_url': item.get('download_url'),
                        'content': content
                    })
            
            elif item['type'] == 'dir' and depth > 1:
                # Skip common non-code directories
                if item['name'] not in ['.git', 'bin', 'obj', 'packages', 'node_modules', '.vs']:
                    sub_files = await self.find_cbot_files(owner, repo, item['path'], depth - 1)
                    cbot_files.extend(sub_files)
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        
        return cbot_files
    
    def _is_cbot_code(self, code: str) -> bool:
        """Check if code appears to be a cTrader cBot"""
        matches = sum(1 for pattern in self.CBOT_PATTERNS if re.search(pattern, code))
        return matches >= 2  # Need at least 2 patterns to match
    
    async def fetch_bots(self, max_repos: int = 20, max_bots_per_repo: int = 5) -> List[FetchedBot]:
        """
        Main method to fetch bots from GitHub
        
        Args:
            max_repos: Maximum number of repositories to search
            max_bots_per_repo: Maximum bots to extract per repository
        
        Returns:
            List of FetchedBot objects
        """
        all_bots = []
        seen_repos = set()
        
        for query in self.SEARCH_QUERIES:
            if len(all_bots) >= max_repos * max_bots_per_repo:
                break
            
            logger.info(f"Searching: {query}")
            repos = await self.search_repositories(query, max_results=max_repos)
            
            for repo in repos:
                repo_full = repo['full_name']
                
                # Skip already processed repos
                if repo_full in seen_repos:
                    continue
                seen_repos.add(repo_full)
                
                # Skip if below minimum stars
                if repo['stargazers_count'] < self.min_stars:
                    continue
                
                owner = repo['owner']['login']
                repo_name = repo['name']
                
                logger.info(f"Processing: {repo_full} ({repo['stargazers_count']} stars)")
                
                # Find cBot files in repository
                cbot_files = await self.find_cbot_files(owner, repo_name)
                
                for idx, file_info in enumerate(cbot_files[:max_bots_per_repo]):
                    bot = FetchedBot(
                        repo_name=repo_name,
                        repo_owner=owner,
                        repo_full_name=repo_full,
                        stars=repo['stargazers_count'],
                        forks=repo['forks_count'],
                        description=repo.get('description') or "",
                        code=file_info['content'],
                        file_path=file_info['path'],
                        source_url=file_info['url'],
                        raw_url=file_info.get('download_url') or file_info['url'],
                        last_updated=repo['updated_at'],
                        license=repo.get('license', {}).get('spdx_id') if repo.get('license') else None,
                        topics=repo.get('topics', [])
                    )
                    all_bots.append(bot)
                    logger.info(f"  Found bot: {file_info['name']}")
                
                # Rate limiting delay
                await asyncio.sleep(2)
        
        await self.close()
        logger.info(f"Total bots fetched: {len(all_bots)}")
        return all_bots
    
    async def fetch_single_repo(self, repo_url: str) -> List[FetchedBot]:
        """
        Fetch bots from a single repository URL
        
        Args:
            repo_url: GitHub repository URL (e.g., https://github.com/owner/repo)
        
        Returns:
            List of FetchedBot objects
        """
        # Parse URL
        match = re.match(r'https?://github\.com/([^/]+)/([^/]+)', repo_url)
        if not match:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")
        
        owner, repo_name = match.groups()
        
        # Get repo info
        url = f"{self.GITHUB_API}/repos/{owner}/{repo_name}"
        repo_data = await self._make_request(url)
        
        if not repo_data:
            raise ValueError(f"Repository not found: {repo_url}")
        
        # Find cBot files
        cbot_files = await self.find_cbot_files(owner, repo_name)
        
        bots = []
        for file_info in cbot_files:
            bot = FetchedBot(
                repo_name=repo_name,
                repo_owner=owner,
                repo_full_name=f"{owner}/{repo_name}",
                stars=repo_data['stargazers_count'],
                forks=repo_data['forks_count'],
                description=repo_data.get('description') or "",
                code=file_info['content'],
                file_path=file_info['path'],
                source_url=file_info['url'],
                raw_url=file_info.get('download_url') or file_info['url'],
                last_updated=repo_data['updated_at'],
                license=repo_data.get('license', {}).get('spdx_id') if repo_data.get('license') else None,
                topics=repo_data.get('topics', [])
            )
            bots.append(bot)
        
        await self.close()
        return bots


def create_bot_fetcher(github_token: Optional[str] = None, min_stars: int = 10) -> GitHubBotFetcher:
    """Factory function to create bot fetcher"""
    return GitHubBotFetcher(github_token=github_token, min_stars=min_stars)
