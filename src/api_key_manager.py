"""
Multi-API Key Manager for Dymo Code
Handles multiple API keys per provider with automatic rotation on rate limits or credit exhaustion
"""

import os
import time
import threading
from typing import Dict, List, Optional, Tuple
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


@dataclass
class APIKeyInfo:
    """Information about an API key"""
    key: str
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

    def is_available(self) -> bool:
        """Check if key is currently available for use"""
        if self.status == KeyStatus.INVALID:
            return False
        if self.status == KeyStatus.EXHAUSTED:
            return False
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False
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

    def __init__(self, provider: str):
        self.provider = provider
        self.keys: List[APIKeyInfo] = []
        self._current_index = 0
        self._lock = threading.Lock()
        self._cooldown_duration = timedelta(seconds=60)  # 1 minute cooldown
        self._rate_limit_cooldown = timedelta(minutes=5)  # 5 minutes for rate limits

    def add_key(self, key: str) -> bool:
        """Add a new API key to the pool"""
        with self._lock:
            # Check if key already exists
            for existing in self.keys:
                if existing.key == key:
                    return False

            self.keys.append(APIKeyInfo(key=key))
            log_debug(f"Added new API key to {self.provider} pool (total: {len(self.keys)})")
            return True

    def remove_key(self, key: str) -> bool:
        """Remove an API key from the pool"""
        with self._lock:
            for i, key_info in enumerate(self.keys):
                if key_info.key == key or key_info.masked_key == key:
                    self.keys.pop(i)
                    if self._current_index >= len(self.keys):
                        self._current_index = 0
                    log_debug(f"Removed API key from {self.provider} pool (remaining: {len(self.keys)})")
                    return True
            return False

    def get_current_key(self) -> Optional[str]:
        """Get the current active API key"""
        with self._lock:
            if not self.keys:
                return None

            # Try to find an available key starting from current index
            attempts = len(self.keys)
            for _ in range(attempts):
                key_info = self.keys[self._current_index]

                # Reset cooldown if expired
                if key_info.cooldown_until and datetime.now() >= key_info.cooldown_until:
                    key_info.status = KeyStatus.ACTIVE
                    key_info.cooldown_until = None

                if key_info.is_available():
                    key_info.last_used = datetime.now()
                    key_info.requests_count += 1
                    return key_info.key

                # Move to next key
                self._current_index = (self._current_index + 1) % len(self.keys)

            return None

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
    with automatic rotation and fallback
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
        }
        self._provider_lock = threading.Lock()
        self._initialized = True

        # Load keys from storage on init
        self._load_from_storage()

    def _load_from_storage(self):
        """Load API keys from storage"""
        try:
            from .storage import user_config

            for provider in self._env_key_map.keys():
                pool = self._get_or_create_pool(provider)

                # Load multi-keys if available
                multi_keys = user_config.get_api_keys_list(provider)
                if multi_keys:
                    for key in multi_keys:
                        pool.add_key(key)
                else:
                    # Fallback to single key (backward compatibility)
                    single_key = user_config.get_api_key(provider)
                    if single_key:
                        pool.add_key(single_key)

                # Also check environment variable
                env_key = os.environ.get(self._env_key_map[provider])
                if env_key:
                    pool.add_key(env_key)

        except Exception as e:
            log_error("Failed to load API keys from storage", e)

    def _get_or_create_pool(self, provider: str) -> ProviderKeyPool:
        """Get or create a key pool for a provider"""
        provider = provider.lower()
        with self._provider_lock:
            if provider not in self._pools:
                self._pools[provider] = ProviderKeyPool(provider)
            return self._pools[provider]

    def add_key(self, provider: str, key: str) -> bool:
        """Add an API key for a provider"""
        provider = provider.lower()
        pool = self._get_or_create_pool(provider)
        success = pool.add_key(key)

        if success:
            # Also update environment for immediate use
            env_var = self._env_key_map.get(provider)
            if env_var and not os.environ.get(env_var):
                os.environ[env_var] = key

            # Save to storage
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
        """Save keys to storage"""
        try:
            from .storage import user_config

            pool = self._pools.get(provider)
            if pool:
                keys = [k.key for k in pool.keys]
                user_config.set_api_keys_list(provider, keys)
        except Exception as e:
            log_error("Failed to save API keys to storage", e)

    def get_key(self, provider: str) -> Optional[str]:
        """Get the current active API key for a provider"""
        provider = provider.lower()
        pool = self._pools.get(provider)
        if not pool:
            # Try to get from environment as fallback
            env_var = self._env_key_map.get(provider)
            if env_var:
                return os.environ.get(env_var)
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

    def get_all_providers_info(self) -> List[Dict]:
        """Get information about all providers"""
        info = []
        for provider in self._env_key_map.keys():
            info.append(self.get_provider_info(provider))
        return info

    def has_available_key(self, provider: str) -> bool:
        """Check if provider has any available keys"""
        provider = provider.lower()
        pool = self._pools.get(provider)
        if not pool:
            # Check environment as fallback
            env_var = self._env_key_map.get(provider)
            if env_var:
                return bool(os.environ.get(env_var))
            return False
        return pool.has_available_keys()

    def get_fallback_providers(self, current_provider: str) -> List[str]:
        """Get list of other providers that have available keys"""
        current = current_provider.lower()
        fallbacks = []

        for provider in self._env_key_map.keys():
            if provider != current and self.has_available_key(provider):
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
