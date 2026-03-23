"""
Direct AI Client - Uses native OpenAI, Anthropic, and DeepSeek APIs
NO dependency on emergentintegrations
"""

import os
import logging
from typing import Optional
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


def _get_api_keys():
    """Get API keys from environment (called at runtime, not import time)"""
    return {
        'openai': os.environ.get('OPENAI_API_KEY'),
        'deepseek': os.environ.get('DEEPSEEK_API_KEY'),
        'anthropic': os.environ.get('ANTHROPIC_API_KEY')
    }


class DirectAIClient:
    """Direct AI client using native SDKs"""
    
    def __init__(self):
        self.openai_client = None
        self.deepseek_client = None
        self.anthropic_client = None
        
        # Get API keys at initialization time (after dotenv loads)
        keys = _get_api_keys()
        
        # Initialize OpenAI client
        if keys['openai']:
            self.openai_client = AsyncOpenAI(api_key=keys['openai'])
            logger.info("OpenAI client initialized")
        else:
            logger.warning("OPENAI_API_KEY not configured")
        
        # Initialize DeepSeek client (OpenAI-compatible API)
        if keys['deepseek']:
            self.deepseek_client = AsyncOpenAI(
                api_key=keys['deepseek'],
                base_url="https://api.deepseek.com/v1"
            )
            logger.info("DeepSeek client initialized")
        else:
            logger.warning("DEEPSEEK_API_KEY not configured")
        
        # Initialize Anthropic client
        if keys['anthropic']:
            self.anthropic_client = AsyncAnthropic(api_key=keys['anthropic'])
            logger.info("Anthropic client initialized")
        else:
            logger.warning("ANTHROPIC_API_KEY not configured")
    
    async def generate(
        self,
        provider: str,
        prompt: str,
        system_message: str = "You are an expert cTrader cBot developer. Return ONLY C# code, no markdown or explanations.",
        model: Optional[str] = None
    ) -> str:
        """
        Generate text using specified provider
        
        Args:
            provider: 'openai', 'deepseek', or 'claude'
            prompt: The user prompt
            system_message: System message for context
            model: Optional model override
        
        Returns:
            Generated text response
        """
        
        if provider == "openai":
            return await self._generate_openai(prompt, system_message, model or "gpt-4o")
        elif provider == "deepseek":
            return await self._generate_deepseek(prompt, system_message, model or "deepseek-chat")
        elif provider == "claude":
            return await self._generate_claude(prompt, system_message, model or "claude-sonnet-4-20250514")
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'openai', 'deepseek', or 'claude'")
    
    async def _generate_openai(self, prompt: str, system_message: str, model: str) -> str:
        """Generate using OpenAI API"""
        if not self.openai_client:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in environment.")
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=8000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise
    
    async def _generate_deepseek(self, prompt: str, system_message: str, model: str) -> str:
        """Generate using DeepSeek API (OpenAI-compatible)"""
        if not self.deepseek_client:
            raise ValueError("DeepSeek API key not configured. Set DEEPSEEK_API_KEY in environment.")
        
        try:
            response = await self.deepseek_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=8000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"DeepSeek API error: {str(e)}")
            raise
    
    async def _generate_claude(self, prompt: str, system_message: str, model: str) -> str:
        """Generate using Anthropic Claude API"""
        if not self.anthropic_client:
            raise ValueError("Anthropic API key not configured. Set ANTHROPIC_API_KEY in environment.")
        
        try:
            response = await self.anthropic_client.messages.create(
                model=model,
                max_tokens=8000,
                system=system_message,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise
    
    def get_available_providers(self) -> dict:
        """Get status of available AI providers"""
        return {
            "openai": {
                "available": self.openai_client is not None,
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"] if self.openai_client else []
            },
            "deepseek": {
                "available": self.deepseek_client is not None,
                "models": ["deepseek-chat", "deepseek-coder"] if self.deepseek_client else []
            },
            "claude": {
                "available": self.anthropic_client is not None,
                "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022"] if self.anthropic_client else []
            }
        }


# Singleton instance
_ai_client = None

def get_ai_client() -> DirectAIClient:
    """Get or create the AI client singleton"""
    global _ai_client
    if _ai_client is None:
        _ai_client = DirectAIClient()
    return _ai_client


def reload_ai_client():
    """Reload the AI client (useful after env changes)"""
    global _ai_client
    _ai_client = DirectAIClient()
    return _ai_client
