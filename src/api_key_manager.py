"""
Multi-API Key Manager for Dymo Code
Handles multiple API keys per provider with automatic rotation on rate limits or credit exhaustion
Supports two rotation strategies: Sequential and Load Balancer
"""

import os
import time
import random
import threading
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .logger import log_debug, log_error

class KeyStatus(Enum):
    """Status of an API key"""
    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    EXHAUSTED = "exhausted"  # Credits exhausted
    INVALID = "invalid"
    COOLDOWN = "cooldown"  # Temporary cooldown after error


class RotationStrategy(Enum):
    """Strategy for rotating API keys"""
    SEQUENTIAL = "sequential"      # Use one key until limit, then switch
    LOAD_BALANCER = "load_balancer"  # Distribute requests across all keys

# Callbacks for notifications
_on_key_rotated: Optional[Callable[[str, str, str], None]] = None  # provider, old_key, new_key
_on_model_fallback: Optional[Callable[[str, str, str], None]] = None  # provider, old_model, new_model
_on_provider_exhausted: Optional[Callable[[str], None]] = None  # provider

def set_rotation_callbacks(
    on_key_rotated: Optional[Callable] = None,
    on_model_fallback: Optional[Callable] = None,
    on_provider_exhausted: Optional[Callable] = None
):
    """Set callbacks for rotation events"""
    global _on_key_rotated, _on_model_fallback, _on_provider_exhausted
    _on_key_rotated = on_key_rotated
    _on_model_fallback = on_model_fallback
    _on_provider_exhausted = on_provider_exhausted

@dataclass
class APIKeyInfo:
    """Information about an API key"""
    key: str
    name: Optional[str] = None  # Optional friendly name for the key
    status: KeyStatus = KeyStatus.ACTIVE
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    cooldown_until: Optional[datetime] = None
    requests_count: int = 0

    @property
    def masked_key(self) -> str:
        """Return masked version of key"""
        if len(self.key) > 12:
            return f"{self.key[:4]}...{self.key[-4:]}"
        return "****"

    @property
    def display_name(self) -> str:
        """Return display name (custom name or masked key)"""
        return self.name if self.name else self.masked_key

    def is_available(self) -> bool:
        """Check if key is currently available for use"""
        if self.status == KeyStatus.INVALID: return False
        if self.status == KeyStatus.EXHAUSTED: return False
        if self.cooldown_until and datetime.now() < self.cooldown_until: return False
        return True


# Rate limit error patterns for different providers
RATE_LIMIT_PATTERNS = [
    "rate_limit",
    "rate limit",
    "too many requests",
    "429",
    "quota exceeded",
    "request limit",
    "ratelimit",
    "throttl",
]

CREDIT_EXHAUSTED_PATTERNS = [
    "insufficient_quota",
    "insufficient quota",
    "credit",
    "billing",
    "payment required",
    "402",
    "exceeded your current quota",
    "out of credits",
    "resource_exhausted",
    "quota failure",
]

INVALID_KEY_PATTERNS = [
    "invalid_api_key",
    "invalid api key",
    "authentication",
    "unauthorized",
    "401",
    "api key not found",
    "incorrect api key",
]


class ProviderKeyPool:
    """Manages multiple API keys for a single provider"""

    def __init__(self, provider: str, strategy: RotationStrategy = RotationStrategy.SEQUENTIAL):
        self.provider = provider
        self.keys: List[APIKeyInfo] = []
        self._current_index = 0
        self._lock = threading.Lock()
        self._cooldown_duration = timedelta(seconds=60)  # 1 minute cooldown
        self._rate_limit_cooldown = timedelta(minutes=5)  # 5 minutes for rate limits
        self._strategy = strategy
        self._request_counter = 0  # For round-robin in load balancer mode

    def add_key(self, key: str, name: Optional[str] = None) -> bool:
        """Add a new API key to the pool with optional name"""
        with self._lock:
            # Check if key already exists
            for existing in self.keys:
                if existing.key == key: return False

            self.keys.append(APIKeyInfo(key=key, name=name))
            display = name if name else f"{key[:4]}...{key[-4:]}" if len(key) > 12 else "****"
            log_debug(f"Added new API key '{display}' to {self.provider} pool (total: {len(self.keys)})")
            return True

    def update_key_name(self, key: str, name: Optional[str]) -> bool:
        """Update the name of an existing API key"""
        with self._lock:
            for key_info in self.keys:
                if key_info.key == key or key_info.masked_key == key:
                    key_info.name = name
                    return True
            return False

    def remove_key(self, key: str) -> bool:
        """Remove an API key from the pool"""
        with self._lock:
            for i, key_info in enumerate(self.keys):
                if key_info.key == key or key_info.masked_key == key:
                    self.keys.pop(i)
                    if self._current_index >= len(self.keys): self._current_index = 0
                    log_debug(f"Removed API key from {self.provider} pool (remaining: {len(self.keys)})")
                    return True
            return False

    def set_strategy(self, strategy: RotationStrategy):
        """Change the rotation strategy"""
        with self._lock:
            self._strategy = strategy
            log_debug(f"{self.provider}: Changed rotation strategy to {strategy.value}")

    def get_current_key(self) -> Optional[str]:
        """Get the current active API key based on rotation strategy"""
        with self._lock:
            if not self.keys:
                return None

            # Reset expired cooldowns first
            for key_info in self.keys:
                if key_info.cooldown_until and datetime.now() >= key_info.cooldown_until:
                    key_info.status = KeyStatus.ACTIVE
                    key_info.cooldown_until = None

            # Get available keys
            available_keys = [k for k in self.keys if k.is_available()]
            if not available_keys:
                return None

            if self._strategy == RotationStrategy.LOAD_BALANCER:
                # Round-robin distribution among available keys
                self._request_counter += 1
                key_info = available_keys[self._request_counter % len(available_keys)]
            else:
                # Sequential: use current key until it fails
                key_info = self.keys[self._current_index]
                if not key_info.is_available():
                    # Find next available
                    for i, k in enumerate(self.keys):
                        if k.is_available():
                            self._current_index = i
                            key_info = k
                            break
                    else:
                        return None

            key_info.last_used = datetime.now()
            key_info.requests_count += 1
            return key_info.key

    def report_error(self, key: str, error: str) -> bool:
        """Report an error for a specific key and handle rotation"""
        with self._lock:
            key_info = self._find_key(key)
            if not key_info:
                return False

            error_lower = error.lower()
            key_info.last_error = error
            key_info.error_count += 1

            # Detect error type
            if any(p in error_lower for p in INVALID_KEY_PATTERNS):
                key_info.status = KeyStatus.INVALID
                log_debug(f"{self.provider}: Key marked as INVALID")
                self._rotate_to_next()
                return True

            if any(p in error_lower for p in CREDIT_EXHAUSTED_PATTERNS):
                key_info.status = KeyStatus.EXHAUSTED
                log_debug(f"{self.provider}: Key marked as EXHAUSTED (credits)")
                self._rotate_to_next()
                return True

            if any(p in error_lower for p in RATE_LIMIT_PATTERNS):
                key_info.status = KeyStatus.RATE_LIMITED
                key_info.cooldown_until = datetime.now() + self._rate_limit_cooldown
                log_debug(f"{self.provider}: Key rate limited, cooldown until {key_info.cooldown_until}")
                self._rotate_to_next()
                return True

            # Generic error - short cooldown
            key_info.status = KeyStatus.COOLDOWN
            key_info.cooldown_until = datetime.now() + self._cooldown_duration

            # Only rotate if error count is high
            if key_info.error_count >= 3:
                self._rotate_to_next()
                return True

            return False

    def report_success(self, key: str):
        """Report successful use of a key"""
        with self._lock:
            key_info = self._find_key(key)
            if key_info:
                key_info.error_count = 0
                key_info.last_error = None
                if key_info.status in (KeyStatus.COOLDOWN, KeyStatus.RATE_LIMITED):
                    key_info.status = KeyStatus.ACTIVE
                    key_info.cooldown_until = None

    def _find_key(self, key: str) -> Optional[APIKeyInfo]:
        """Find a key info by key string"""
        for key_info in self.keys:
            if key_info.key == key:
                return key_info
        return None

    def _rotate_to_next(self):
        """Rotate to the next available key"""
        if len(self.keys) > 1:
            self._current_index = (self._current_index + 1) % len(self.keys)
            log_debug(f"{self.provider}: Rotated to key index {self._current_index}")

    def get_all_keys_info(self) -> List[Dict]:
        """Get info about all keys in the pool"""
        with self._lock:
            return [
                {
                    "masked_key": k.masked_key,
                    "name": k.name,
                    "display_name": k.display_name,
                    "status": k.status.value,
                    "requests": k.requests_count,
                    "errors": k.error_count,
                    "last_error": k.last_error,
                    "is_current": i == self._current_index,
                }
                for i, k in enumerate(self.keys)
            ]

    def has_available_keys(self) -> bool:
        """Check if any keys are available"""
        with self._lock:
            return any(k.is_available() for k in self.keys)

    @property
    def key_count(self) -> int:
        """Get number of keys in pool"""
        return len(self.keys)


class APIKeyManager:
    """
    Global API Key Manager that handles multiple keys per provider
    with automatic rotation and fallback.

    Supports two rotation strategies:
    - SEQUENTIAL: Use one key until rate limited, then switch to next
    - LOAD_BALANCER: Distribute requests across all available keys
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._pools: Dict[str, ProviderKeyPool] = {}
        self._env_key_map = {
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "cerebras": "CEREBRAS_API_KEY",
            "dymo": "DYMO_API_KEY",
        }
        self._provider_lock = threading.Lock()
        self._initialized = True

        # Default rotation strategy
        self._default_strategy = RotationStrategy.SEQUENTIAL

        # Model fallback configuration
        self._model_fallback_enabled = True
        self._current_fallback_model: Optional[str] = None
        self._original_model: Optional[str] = None
        self._fallback_expiry: Optional[datetime] = None

        # Load settings from storage
        self._load_settings()

        # Load keys from storage on init
        self._load_from_storage()

    def _load_settings(self):
        """Load rotation settings from storage"""
        try:
            from .storage import user_config
            settings = user_config.get_key_pool_settings()
            if settings:
                strategy = settings.get("rotation_strategy", "sequential")
                self._default_strategy = RotationStrategy(strategy)
                self._model_fallback_enabled = settings.get("model_fallback_enabled", True)
        except Exception:
            pass

    def _save_settings(self):
        """Save rotation settings to storage"""
        try:
            from .storage import user_config
            user_config.set_key_pool_settings({
                "rotation_strategy": self._default_strategy.value,
                "model_fallback_enabled": self._model_fallback_enabled
            })
        except Exception as e:
            log_error("Failed to save key pool settings", e)

    def set_rotation_strategy(self, strategy: RotationStrategy):
        """Set the rotation strategy for all providers"""
        self._default_strategy = strategy
        with self._provider_lock:
            for pool in self._pools.values():
                pool.set_strategy(strategy)
        self._save_settings()
        log_debug(f"Global rotation strategy set to: {strategy.value}")

    def get_rotation_strategy(self) -> RotationStrategy:
        """Get the current rotation strategy"""
        return self._default_strategy

    def set_model_fallback_enabled(self, enabled: bool):
        """Enable or disable automatic model fallback"""
        self._model_fallback_enabled = enabled
        self._save_settings()

    def is_model_fallback_enabled(self) -> bool:
        """Check if model fallback is enabled"""
        return self._model_fallback_enabled

    def _load_from_storage(self):
        """Load API keys from storage (filters out placeholders)"""
        try:
            from .storage import user_config

            for provider in self._env_key_map.keys():
                # Load multi-keys if available
                multi_keys = user_config.get_api_keys_list(provider)
                if multi_keys:
                    for key_data in multi_keys:
                        # Support both old format (string) and new format (dict with key/name)
                        if isinstance(key_data, dict):
                            key = key_data.get("key", "")
                            name = key_data.get("name")
                            self.add_key(provider, key, name)
                        else:
                            # Legacy format: just a string
                            self.add_key(provider, key_data)
                else:
                    # Fallback to single key (backward compatibility)
                    single_key = user_config.get_api_key(provider)
                    if single_key:
                        self.add_key(provider, single_key)

                # Also check environment variable
                env_key = os.environ.get(self._env_key_map[provider])
                if env_key:
                    self.add_key(provider, env_key)

        except Exception as e:
            log_error("Failed to load API keys from storage", e)

    def _get_or_create_pool(self, provider: str) -> ProviderKeyPool:
        """Get or create a key pool for a provider"""
        provider = provider.lower()
        with self._provider_lock:
            if provider not in self._pools:
                self._pools[provider] = ProviderKeyPool(provider, self._default_strategy)
            return self._pools[provider]

    def add_key(self, provider: str, key: str, name: Optional[str] = None) -> bool:
        """Add an API key for a provider with optional name (rejects placeholders)"""
        # Reject placeholder keys
        if self._is_placeholder_key(key):
            log_debug(f"Rejected placeholder key for {provider}")
            return False

        provider = provider.lower()
        pool = self._get_or_create_pool(provider)
        success = pool.add_key(key, name)

        if success:
            # Also update environment for immediate use
            env_var = self._env_key_map.get(provider)
            if env_var and not os.environ.get(env_var):
                os.environ[env_var] = key

            # Save to storage
            self._save_to_storage(provider)

        return success

    def update_key_name(self, provider: str, key: str, name: Optional[str]) -> bool:
        """Update the name of an existing API key"""
        provider = provider.lower()
        pool = self._pools.get(provider)
        if not pool:
            return False

        success = pool.update_key_name(key, name)
        if success:
            self._save_to_storage(provider)
        return success

    def remove_key(self, provider: str, key: str) -> bool:
        """Remove an API key for a provider"""
        provider = provider.lower()
        pool = self._pools.get(provider)
        if not pool:
            return False

        success = pool.remove_key(key)
        if success:
            self._save_to_storage(provider)
        return success

    def _save_to_storage(self, provider: str):
        """Save keys to storage with optional names"""
        try:
            from .storage import user_config

            pool = self._pools.get(provider)
            if pool:
                # Save as list of objects with key and optional name
                keys_data = []
                for k in pool.keys:
                    if k.name:
                        keys_data.append({"key": k.key, "name": k.name})
                    else:
                        keys_data.append(k.key)  # Simple string for backward compatibility
                user_config.set_api_keys_list(provider, keys_data)
        except Exception as e:
            log_error("Failed to save API keys to storage", e)

    def get_key(self, provider: str) -> Optional[str]:
        """Get the current active API key for a provider (excludes placeholders)"""
        provider = provider.lower()
        pool = self._pools.get(provider)
        if not pool:
            # Try to get from environment as fallback
            env_var = self._env_key_map.get(provider)
            if env_var:
                key = os.environ.get(env_var)
                # Don't return placeholder keys
                if key and not self._is_placeholder_key(key):
                    return key
            return None

        key = pool.get_current_key()

        # Update environment variable if we have a key
        if key:
            env_var = self._env_key_map.get(provider)
            if env_var:
                os.environ[env_var] = key

        return key

    def report_error(self, provider: str, error: str) -> Tuple[bool, Optional[str]]:
        """
        Report an error for the current key of a provider.
        Returns (rotated, new_key) where rotated indicates if rotation happened.
        """
        provider = provider.lower()
        pool = self._pools.get(provider)
        if not pool:
            return False, None

        # Get current key before rotation
        current_key = None
        for k in pool.keys:
            if k.last_used == max((ki.last_used for ki in pool.keys if ki.last_used), default=None):
                current_key = k.key
                break

        if current_key:
            rotated = pool.report_error(current_key, error)

            if rotated:
                new_key = pool.get_current_key()
                if new_key:
                    # Update environment
                    env_var = self._env_key_map.get(provider)
                    if env_var:
                        os.environ[env_var] = new_key
                    return True, new_key

        return False, None

    def report_success(self, provider: str):
        """Report successful API call for current key"""
        provider = provider.lower()
        pool = self._pools.get(provider)
        if pool and pool.keys:
            # Find the last used key
            for k in pool.keys:
                if k.last_used == max((ki.last_used for ki in pool.keys if ki.last_used), default=None):
                    pool.report_success(k.key)
                    break

    def get_provider_info(self, provider: str) -> Dict:
        """Get information about a provider's key pool"""
        provider = provider.lower()
        pool = self._pools.get(provider)
        if not pool:
            return {
                "provider": provider,
                "key_count": 0,
                "keys": [],
                "has_available": False,
            }

        return {
            "provider": provider,
            "key_count": pool.key_count,
            "keys": pool.get_all_keys_info(),
            "has_available": pool.has_available_keys(),
        }

    def get_all_providers_info(self, ai_only: bool = True) -> List[Dict]:
        """Get information about all providers (optionally filter to AI providers only)"""
        from .lib.providers import is_ai_provider

        info = []
        for provider in self._env_key_map.keys():
            if ai_only and not is_ai_provider(provider):
                continue
            info.append(self.get_provider_info(provider))
        return info

    def _is_placeholder_key(self, key: str) -> bool:
        """Check if a key appears to be a placeholder/example value"""
        if not key:
            return True
        key_lower = key.lower()
        placeholder_patterns = [
            "your_",
            "_here",
            "example",
            "placeholder",
            "xxx",
            "insert",
            "paste",
            "api_key",
            "apikey",
            "enter_",
            "put_",
            "add_",
            "<",
            ">",
        ]
        return any(pattern in key_lower for pattern in placeholder_patterns)

    def has_available_key(self, provider: str) -> bool:
        """Check if provider has any available keys (excluding placeholders)"""
        provider = provider.lower()
        pool = self._pools.get(provider)
        if not pool:
            # Check environment as fallback
            env_var = self._env_key_map.get(provider)
            if env_var:
                key = os.environ.get(env_var, "")
                # Make sure it's not a placeholder value
                return bool(key) and not self._is_placeholder_key(key)
            return False
        return pool.has_available_keys()

    def get_fallback_providers(self, current_provider: str) -> List[str]:
        """Get list of other AI providers that have available keys (excludes non-AI providers)"""
        from .lib.providers import is_ai_provider

        current = current_provider.lower()
        fallbacks = []

        for provider in self._env_key_map.keys():
            # Only include AI providers with available keys
            if provider != current and self.has_available_key(provider) and is_ai_provider(provider):
                fallbacks.append(provider)

        return fallbacks


# Global singleton instance
api_key_manager = APIKeyManager()


def is_rate_limit_error(error: str) -> bool:
    """Check if an error is a rate limit error"""
    error_lower = error.lower()
    return any(p in error_lower for p in RATE_LIMIT_PATTERNS)


def is_credit_error(error: str) -> bool:
    """Check if an error is a credit/quota error"""
    error_lower = error.lower()
    return any(p in error_lower for p in CREDIT_EXHAUSTED_PATTERNS)


def is_auth_error(error: str) -> bool:
    """Check if an error is an authentication error"""
    error_lower = error.lower()
    return any(p in error_lower for p in INVALID_KEY_PATTERNS)


# ═══════════════════════════════════════════════════════════════════════════════
# Model Fallback System
# ═══════════════════════════════════════════════════════════════════════════════

# Fallback model hierarchy per provider (from best to simpler)
MODEL_FALLBACK_HIERARCHY = {
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
        "llama3-8b-8192",
        "gemma2-9b-it",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
    "anthropic": [
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
        "claude-3-haiku-20240307",
    ],
    "google": [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
    ],
    "cerebras": [
        "llama-3.3-70b",
        "llama-4-scout-17b-16e-instruct",
    ],
    "openrouter": [
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4o",
        "meta-llama/llama-3.1-70b-instruct",
        "meta-llama/llama-3.1-8b-instruct",
    ],
}


class ModelFallbackManager:
    """
    Manages automatic model fallback when rate limits are hit.
    Falls back to simpler/smaller models until the rate limit expires.
    """

    def __init__(self):
        self._original_model: Optional[str] = None
        self._current_model: Optional[str] = None
        self._fallback_provider: Optional[str] = None
        self._fallback_expiry: Optional[datetime] = None
        self._fallback_duration = timedelta(minutes=5)  # Default 5 min
        self._lock = threading.Lock()
        self._enabled = True
        # Track active fallbacks per provider
        self._active_fallbacks: Dict[str, Dict] = {}

    def set_enabled(self, enabled: bool):
        """Enable or disable the model fallback system"""
        self._enabled = enabled
        if not enabled:
            self.reset_all_fallbacks()

    def is_enabled(self) -> bool:
        """Check if model fallback is enabled"""
        return self._enabled

    def get_fallback_model(self, provider: str, current_model: str) -> Optional[str]:
        """
        Get a fallback model for the given provider.
        Returns None if no fallback is available.
        """
        provider = provider.lower()
        hierarchy = MODEL_FALLBACK_HIERARCHY.get(provider, [])

        if not hierarchy:
            return None

        # Find current model position in hierarchy
        try:
            current_index = hierarchy.index(current_model)
            # Return next model in hierarchy if available
            if current_index + 1 < len(hierarchy):
                return hierarchy[current_index + 1]
        except ValueError:
            # Current model not in hierarchy, return first fallback
            if hierarchy:
                return hierarchy[0]

        return None

    def get_active_fallback(self, provider: str) -> Optional[Tuple[str, str, datetime]]:
        """
        Get active fallback for a provider if any.
        Returns (original_model, fallback_model, expiry) or None.
        """
        with self._lock:
            if self._fallback_provider != provider:
                return None

            if self._fallback_expiry and datetime.now() >= self._fallback_expiry:
                # Fallback expired, clear it
                self._clear_fallback_internal()
                return None

            if self._original_model and self._current_model:
                return (self._original_model, self._current_model, self._fallback_expiry)

            return None

    def clear_fallback(self, provider: str = None):
        """Clear active fallback"""
        with self._lock:
            if provider is None or self._fallback_provider == provider:
                self._clear_fallback_internal()

    def _clear_fallback_internal(self):
        """Internal method to clear fallback (must hold lock)"""
        if self._original_model:
            log_debug(f"Model fallback cleared, restored to: {self._original_model}")
        self._original_model = None
        self._current_model = None
        self._fallback_provider = None
        self._fallback_expiry = None

    def is_fallback_active(self, provider: str) -> bool:
        """Check if fallback is currently active for a provider"""
        return self.get_active_fallback(provider) is not None

    def get_effective_model(self, provider: str, requested_model: str) -> str:
        """
        Get the effective model to use, considering active fallbacks.
        Returns the fallback model if one is active, otherwise the requested model.
        """
        fallback = self.get_active_fallback(provider)
        if fallback and fallback[0] == requested_model:
            return fallback[1]  # Return fallback model
        return requested_model

    def get_fallback_info(self) -> Optional[Dict]:
        """Get information about current fallback state"""
        with self._lock:
            if not self._original_model:
                return None

            remaining = None
            if self._fallback_expiry:
                remaining = (self._fallback_expiry - datetime.now()).total_seconds()
                if remaining < 0:
                    remaining = 0

            return {
                "provider": self._fallback_provider,
                "original_model": self._original_model,
                "fallback_model": self._current_model,
                "expiry": self._fallback_expiry.isoformat() if self._fallback_expiry else None,
                "remaining_seconds": remaining
            }

    def get_fallback_status(self) -> Dict:
        """Get complete fallback status including all active fallbacks"""
        with self._lock:
            active_fallbacks = {}

            # Clean up expired fallbacks
            now = datetime.now()
            expired = []
            for provider, info in self._active_fallbacks.items():
                if info.get('expiry') and now >= info['expiry']:
                    expired.append(provider)
                else:
                    active_fallbacks[provider] = {
                        'original': info.get('original'),
                        'current': info.get('current'),
                        'remaining_seconds': (info['expiry'] - now).total_seconds() if info.get('expiry') else None
                    }

            for p in expired:
                del self._active_fallbacks[p]

            # Also include the main fallback state
            if self._fallback_provider and self._original_model:
                if self._fallback_expiry is None or now < self._fallback_expiry:
                    active_fallbacks[self._fallback_provider] = {
                        'original': self._original_model,
                        'current': self._current_model,
                        'remaining_seconds': (self._fallback_expiry - now).total_seconds() if self._fallback_expiry else None
                    }

            return {
                'enabled': self._enabled,
                'active_fallbacks': active_fallbacks,
                'has_active': len(active_fallbacks) > 0
            }

    def reset_all_fallbacks(self):
        """Reset all active fallbacks to original models"""
        with self._lock:
            self._original_model = None
            self._current_model = None
            self._fallback_provider = None
            self._fallback_expiry = None
            self._active_fallbacks.clear()
            log_debug("All model fallbacks have been reset")

    def activate_fallback(self, provider: str, original_model: str, fallback_model: str, duration_minutes: int = 5):
        """Activate a fallback model for a specified duration"""
        if not self._enabled:
            return

        with self._lock:
            self._original_model = original_model
            self._current_model = fallback_model
            self._fallback_provider = provider
            self._fallback_expiry = datetime.now() + timedelta(minutes=duration_minutes)

            # Also track in active_fallbacks dict
            self._active_fallbacks[provider] = {
                'original': original_model,
                'current': fallback_model,
                'expiry': self._fallback_expiry
            }

            log_debug(f"Model fallback activated: {original_model} -> {fallback_model} for {duration_minutes}min")

            # Notify via callback
            if _on_model_fallback:
                _on_model_fallback(provider, original_model, fallback_model)


# Global model fallback manager instance
model_fallback_manager = ModelFallbackManager()
