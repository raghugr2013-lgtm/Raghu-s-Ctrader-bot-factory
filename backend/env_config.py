"""
Environment Configuration Loader
Loads and validates environment variables from .env file.
Provides secure access to API keys with fallback handling.
"""

import os
import logging
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class EnvironmentConfig:
    """
    Centralized environment configuration management.
    Loads .env file and provides secure access to API keys.
    """
    
    _loaded = False
    
    @classmethod
    def load(cls, env_path: Optional[str] = None):
        """
        Load environment variables from .env file.
        
        Args:
            env_path: Optional path to .env file (defaults to backend/.env)
        """
        if cls._loaded:
            return
        
        if env_path is None:
            # Default to backend/.env
            backend_dir = Path(__file__).parent
            env_path = backend_dir / ".env"
        
        if os.path.exists(env_path):
            load_dotenv(env_path)
            logger.info(f"✓ Loaded environment variables from {env_path}")
            cls._loaded = True
        else:
            logger.warning(f"⚠ .env file not found at {env_path}")
    
    @classmethod
    def get_openai_key(cls) -> Optional[str]:
        """
        Get OpenAI API key from environment.
        
        Returns:
            API key string or None if not found
        """
        cls.load()
        key = os.getenv('OPENAI_API_KEY')
        if key:
            logger.debug("✓ OpenAI API key loaded")
        else:
            logger.warning("⚠ OPENAI_API_KEY not found in environment")
        return key
    
    @classmethod
    def get_deepseek_key(cls) -> Optional[str]:
        """
        Get DeepSeek API key from environment.
        
        Returns:
            API key string or None if not found
        """
        cls.load()
        key = os.getenv('DEEPSEEK_API_KEY')
        if key:
            logger.debug("✓ DeepSeek API key loaded")
        else:
            logger.warning("⚠ DEEPSEEK_API_KEY not found in environment")
        return key
    
    @classmethod
    def get_anthropic_key(cls) -> Optional[str]:
        """
        Get Anthropic (Claude) API key from environment.
        
        Returns:
            API key string or None if not found
        """
        cls.load()
        key = os.getenv('ANTHROPIC_API_KEY')
        if key:
            logger.debug("✓ Anthropic API key loaded")
        else:
            logger.warning("⚠ ANTHROPIC_API_KEY not found in environment")
        return key
    
    @classmethod
    def get_all_keys(cls) -> dict:
        """
        Get all available API keys.
        
        Returns:
            Dict with provider names as keys, API keys as values (only non-None)
        """
        cls.load()
        keys = {}
        
        openai_key = cls.get_openai_key()
        if openai_key:
            keys['openai'] = openai_key
        
        deepseek_key = cls.get_deepseek_key()
        if deepseek_key:
            keys['deepseek'] = deepseek_key
        
        anthropic_key = cls.get_anthropic_key()
        if anthropic_key:
            keys['anthropic'] = anthropic_key
        
        return keys
    
    @classmethod
    def get_config(cls, key: str, default: any = None) -> any:
        """
        Get any configuration value from environment.
        
        Args:
            key: Environment variable name
            default: Default value if not found
            
        Returns:
            Value from environment or default
        """
        cls.load()
        return os.getenv(key, default)
    
    @classmethod
    def mask_key(cls, key: Optional[str]) -> str:
        """
        Mask API key for safe logging.
        
        Args:
            key: API key string
            
        Returns:
            Masked key (e.g., "sk-...t0AA")
        """
        if not key:
            return "None"
        if len(key) < 8:
            return "***"
        return f"{key[:3]}...{key[-4:]}"


# Auto-load on module import
EnvironmentConfig.load()
