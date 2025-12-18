"""
Centralized provider definitions for Dymo Code
All provider lists should import from here to maintain consistency
"""

from typing import List, Dict
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════════════════
# Provider Data Class
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ProviderInfo:
    """Complete information about a provider"""
    id: str
    name: str
    description: str
    api_key_url: str
    env_key: str

# ═══════════════════════════════════════════════════════════════════════════════
# Provider Definitions
# ═══════════════════════════════════════════════════════════════════════════════

PROVIDERS: Dict[str, ProviderInfo] = {
    "groq": ProviderInfo(
        id="groq",
        name="Groq",
        description="Fast inference API for LLMs",
        api_key_url="https://console.groq.com/keys",
        env_key="GROQ_API_KEY"
    ),
    "openrouter": ProviderInfo(
        id="openrouter",
        name="OpenRouter",
        description="Access to multiple AI models",
        api_key_url="https://openrouter.ai/keys",
        env_key="OPENROUTER_API_KEY"
    ),
    "anthropic": ProviderInfo(
        id="anthropic",
        name="Anthropic",
        description="Claude models API",
        api_key_url="https://console.anthropic.com/settings/keys",
        env_key="ANTHROPIC_API_KEY"
    ),
    "openai": ProviderInfo(
        id="openai",
        name="OpenAI",
        description="GPT models API",
        api_key_url="https://platform.openai.com/api-keys",
        env_key="OPENAI_API_KEY"
    ),
    "google": ProviderInfo(
        id="google",
        name="Google",
        description="Gemini models API",
        api_key_url="https://aistudio.google.com/apikey",
        env_key="GOOGLE_API_KEY"
    )
}

# Local providers (no API key required)
LOCAL_PROVIDERS: Dict[str, ProviderInfo] = {
    "ollama": ProviderInfo(
        id="ollama",
        name="Ollama",
        description="Local LLM inference",
        api_key_url="",
        env_key="OLLAMA_BASE_URL"
    )
}

# ═══════════════════════════════════════════════════════════════════════════════
# Default Models per Provider (for auto-switching)
# ═══════════════════════════════════════════════════════════════════════════════

# When auto-switching providers, use these models by default
# Keys are provider IDs, values are model keys from config.AVAILABLE_MODELS
DEFAULT_MODELS: Dict[str, str] = {
    "groq": "gpt-oss",           # GPT-OSS 120B - best for coding
    "google": "gemini-flash",    # Gemini 2.0 Flash - fast and capable
    "openai": "gpt-4o",          # GPT-4o - most capable
    "anthropic": "claude-sonnet", # Claude Sonnet - balanced
    "openrouter": "llama",       # Llama via OpenRouter
    "ollama": "ollama-qwen"      # Qwen 2.5 Coder - best local for coding
}


def get_default_model(provider: str) -> str:
    """Get the default model key for a provider"""
    return DEFAULT_MODELS.get(provider.lower())


# ═══════════════════════════════════════════════════════════════════════════════
# Provider Lists (for iteration)
# ═══════════════════════════════════════════════════════════════════════════════

# Providers that require API keys (in display order)
API_KEY_PROVIDERS: List[str] = list(PROVIDERS.keys())

# All providers including local ones
ALL_PROVIDERS: List[str] = list(PROVIDERS.keys()) + list(LOCAL_PROVIDERS.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_providers_string() -> str:
    """Get comma-separated string of API key providers"""
    return ", ".join(API_KEY_PROVIDERS)

def is_valid_provider(provider: str) -> bool:
    """Check if a provider name is valid (API key providers only)"""
    return provider.lower() in PROVIDERS

def is_any_provider(provider: str) -> bool:
    """Check if a provider name is valid (including local providers)"""
    return provider.lower() in PROVIDERS or provider.lower() in LOCAL_PROVIDERS

def get_provider(provider: str) -> ProviderInfo:
    """Get provider info by ID"""
    provider = provider.lower()
    if provider in PROVIDERS: return PROVIDERS[provider]
    if provider in LOCAL_PROVIDERS: return LOCAL_PROVIDERS[provider]
    return None

def get_provider_name(provider: str) -> str:
    """Get display name for a provider"""
    info = get_provider(provider)
    return info.name if info else provider.title()

def get_provider_env_key(provider: str) -> str:
    """Get environment variable key for a provider"""
    info = get_provider(provider)
    return info.env_key if info else f"{provider.upper()}_API_KEY"

def get_provider_url(provider: str) -> str:
    """Get API key URL for a provider"""
    info = get_provider(provider)
    return info.api_key_url if info else ""

def get_provider_description(provider: str) -> str:
    """Get description for a provider"""
    info = get_provider(provider)
    return info.description if info else ""