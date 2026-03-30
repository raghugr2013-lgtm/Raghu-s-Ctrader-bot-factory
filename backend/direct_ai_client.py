"""
Direct AI Client - Uses native OpenAI, Anthropic, DeepSeek APIs
Also supports Emergent Universal Key via emergentintegrations

Features:
- Direct API calls to OpenAI, DeepSeek, Anthropic
- Emergent Universal Key support
- Automatic fallback: OpenAI → DeepSeek → Claude
- Clear error messages for insufficient credits
- Startup logging for key detection
"""

import os
import logging
from typing import Optional, List, Tuple
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

# Try to import emergentintegrations for Universal Key support
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    EMERGENT_AVAILABLE = True
except ImportError:
    EMERGENT_AVAILABLE = False

logger = logging.getLogger(__name__)


# Error messages for insufficient credits
CREDIT_ERROR_PATTERNS = [
    "exceeded your current quota",
    "insufficient_quota",
    "Insufficient Balance",
    "credit balance is too low",
    "rate_limit_exceeded",
    "billing",
    "payment required",
    "402"
]


def _get_api_keys():
    """Get API keys from environment (called at runtime, not import time)"""
    return {
        'openai': os.environ.get('OPENAI_API_KEY'),
        'deepseek': os.environ.get('DEEPSEEK_API_KEY'),
        'anthropic': os.environ.get('ANTHROPIC_API_KEY'),
        'emergent': os.environ.get('EMERGENT_LLM_KEY')
    }


def _is_credit_error(error_message: str) -> bool:
    """Check if error is related to insufficient credits"""
    error_lower = str(error_message).lower()
    return any(pattern.lower() in error_lower for pattern in CREDIT_ERROR_PATTERNS)


class AIProviderError(Exception):
    """Custom exception for AI provider errors"""
    def __init__(self, provider: str, message: str, is_credit_error: bool = False):
        self.provider = provider
        self.is_credit_error = is_credit_error
        super().__init__(message)


class DirectAIClient:
    """Direct AI client using native SDKs with fallback support"""
    
    # Fallback order: OpenAI → DeepSeek → Claude
    FALLBACK_ORDER = ["openai", "deepseek", "claude"]
    
    def __init__(self):
        self.openai_client = None
        self.deepseek_client = None
        self.anthropic_client = None
        self.available_providers: List[str] = []
        
        # Get API keys at initialization time (after dotenv loads)
        keys = _get_api_keys()
        
        # Log startup status
        logger.info("=" * 50)
        logger.info("AI PROVIDER CONFIGURATION")
        logger.info("=" * 50)
        
        # Initialize OpenAI client
        if keys['openai']:
            # Use direct OpenAI API
            self.openai_client = AsyncOpenAI(api_key=keys['openai'])
            self.available_providers.append("openai")
            logger.info("✅ OpenAI: FOUND (using direct API key)")
        else:
            logger.warning("❌ OpenAI: MISSING (OPENAI_API_KEY not set)")
        
        # Initialize DeepSeek client (OpenAI-compatible API)
        if keys['deepseek']:
            self.deepseek_client = AsyncOpenAI(
                api_key=keys['deepseek'],
                base_url="https://api.deepseek.com/v1"
            )
            self.available_providers.append("deepseek")
            logger.info("✅ DeepSeek: FOUND (key configured)")
        else:
            logger.warning("❌ DeepSeek: MISSING (DEEPSEEK_API_KEY not set)")
        
        # Initialize Anthropic client
        if keys['anthropic']:
            # Use direct Anthropic API with real key
            self.anthropic_client = AsyncAnthropic(api_key=keys['anthropic'])
            self.available_providers.append("claude")
            logger.info("✅ Claude: FOUND (using direct API key)")
        else:
            logger.warning("❌ Claude: MISSING (ANTHROPIC_API_KEY not set)")
        
        logger.info("=" * 50)
        logger.info(f"Available providers: {self.available_providers}")
        logger.info("=" * 50)
    
    async def generate(
        self,
        provider: str,
        prompt: str,
        system_message: str = "You are an expert cTrader cBot developer. Return ONLY C# code, no markdown or explanations.",
        model: Optional[str] = None,
        enable_fallback: bool = True
    ) -> str:
        """
        Generate text using specified provider with optional fallback
        
        Args:
            provider: 'openai', 'deepseek', or 'claude'
            prompt: The user prompt
            system_message: System message for context
            model: Optional model override
            enable_fallback: Try other providers if primary fails
        
        Returns:
            Generated text response
            
        Raises:
            AIProviderError: If all providers fail
        """
        errors = []
        
        # Build provider order (requested first, then fallbacks)
        providers_to_try = [provider]
        if enable_fallback:
            for p in self.FALLBACK_ORDER:
                if p != provider and p in self.available_providers:
                    providers_to_try.append(p)
        
        for p in providers_to_try:
            if p not in self.available_providers:
                continue
                
            try:
                logger.info(f"Attempting generation with provider: {p}")
                
                if p == "openai":
                    return await self._generate_openai(prompt, system_message, model or "gpt-4o")
                elif p == "deepseek":
                    return await self._generate_deepseek(prompt, system_message, model or "deepseek-chat")
                elif p == "claude":
                    return await self._generate_claude(prompt, system_message, model or "claude-sonnet-4-20250514")
                    
            except Exception as e:
                error_msg = str(e)
                is_credit = _is_credit_error(error_msg)
                
                if is_credit:
                    logger.warning(f"⚠️ {p.upper()}: API key present but INSUFFICIENT CREDITS")
                    errors.append(f"{p}: Insufficient credits - {error_msg[:100]}")
                else:
                    logger.error(f"❌ {p.upper()} API error: {error_msg[:200]}")
                    errors.append(f"{p}: {error_msg[:100]}")
                
                # Continue to next provider if fallback enabled
                if enable_fallback:
                    continue
                else:
                    raise AIProviderError(p, error_msg, is_credit)
        
        # All providers failed
        error_summary = "; ".join(errors)
        
        # Check if all failures were credit-related
        all_credit_errors = all("Insufficient credits" in e or "insufficient" in e.lower() for e in errors)
        
        if all_credit_errors:
            raise AIProviderError(
                provider="all",
                message=f"All AI providers have insufficient credits. Please add credits to your API accounts. Details: {error_summary}",
                is_credit_error=True
            )
        else:
            raise AIProviderError(
                provider="all",
                message=f"All AI providers failed. Errors: {error_summary}",
                is_credit_error=False
            )
    
    async def generate_with_fallback(
        self,
        prompt: str,
        system_message: str = "You are an expert cTrader cBot developer. Return ONLY C# code, no markdown or explanations.",
    ) -> Tuple[str, str]:
        """
        Generate using automatic provider selection with fallback
        
        Returns:
            Tuple of (generated_text, provider_used)
        """
        for provider in self.FALLBACK_ORDER:
            if provider not in self.available_providers:
                continue
            
            try:
                result = await self.generate(
                    provider=provider,
                    prompt=prompt,
                    system_message=system_message,
                    enable_fallback=False
                )
                return result, provider
            except Exception as e:
                logger.warning(f"Provider {provider} failed: {str(e)[:100]}")
                continue
        
        raise AIProviderError(
            provider="all",
            message="No AI providers available or all failed",
            is_credit_error=False
        )
    
    async def _generate_openai(self, prompt: str, system_message: str, model: str) -> str:
        """Generate using OpenAI API"""
        if not self.openai_client:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in environment.")
        
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
    
    async def _generate_deepseek(self, prompt: str, system_message: str, model: str) -> str:
        """Generate using DeepSeek API (OpenAI-compatible)"""
        if not self.deepseek_client:
            raise ValueError("DeepSeek API key not configured. Set DEEPSEEK_API_KEY in environment.")
        
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
    
    async def _generate_claude(self, prompt: str, system_message: str, model: str) -> str:
        """Generate using Anthropic Claude API"""
        if not self.anthropic_client:
            raise ValueError("Anthropic API key not configured. Set ANTHROPIC_API_KEY in environment.")
        
        response = await self.anthropic_client.messages.create(
            model=model,
            max_tokens=8000,
            system=system_message,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.content[0].text
    
    def get_available_providers(self) -> dict:
        """Get status of available AI providers"""
        return {
            "openai": {
                "available": self.openai_client is not None,
                "key_configured": "openai" in self.available_providers,
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"] if self.openai_client else []
            },
            "deepseek": {
                "available": self.deepseek_client is not None,
                "key_configured": "deepseek" in self.available_providers,
                "models": ["deepseek-chat", "deepseek-coder"] if self.deepseek_client else []
            },
            "claude": {
                "available": self.anthropic_client is not None,
                "key_configured": "claude" in self.available_providers,
                "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022"] if self.anthropic_client else []
            }
        }
    
    def get_status_summary(self) -> dict:
        """Get a summary of AI provider status"""
        return {
            "total_providers": 3,
            "configured_providers": len(self.available_providers),
            "available_providers": self.available_providers,
            "fallback_enabled": True,
            "fallback_order": self.FALLBACK_ORDER
        }


# Singleton instance
_ai_client = None


def get_ai_client() -> DirectAIClient:
    """Get or create the AI client singleton"""
    global _ai_client
    if _ai_client is None:
        _ai_client = DirectAIClient()
    return _ai_client


def reload_ai_client() -> DirectAIClient:
    """Reload the AI client (useful after env changes)"""
    global _ai_client
    _ai_client = DirectAIClient()
    return _ai_client


def log_ai_status():
    """Log the current AI provider status"""
    client = get_ai_client()
    status = client.get_status_summary()
    logger.info(f"AI Status: {status['configured_providers']}/3 providers configured")
    logger.info(f"Available: {status['available_providers']}")
