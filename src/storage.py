"""
Cross-platform Storage System for Dymo Code
Handles user data directory and persistent storage across all operating systems
"""

import os, sys, json
from pathlib import Path
from typing import Optional
from datetime import datetime

from .lib.providers import API_KEY_PROVIDERS, get_providers_string

# ═══════════════════════════════════════════════════════════════════════════════
# Cross-Platform Data Directory
# ═══════════════════════════════════════════════════════════════════════════════

APP_NAME = "dymo-code"

def get_data_directory() -> Path:
    """
    Get the appropriate data directory for the current OS.

    - Windows: C:\\Users\\<user>\\AppData\\Local\\dymo-code
    - macOS: ~/Library/Application Support/dymo-code
    - Linux: ~/.local/share/dymo-code

    Falls back to ~/.dymo-code if standard paths are not available.
    """
    home = Path.home()

    if sys.platform == "win32":
        # Windows: Use LOCALAPPDATA or fallback to APPDATA
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_NAME
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data) / APP_NAME
        return home / "AppData" / "Local" / APP_NAME

    elif sys.platform == "darwin":
        # macOS: Use Application Support
        return home / "Library" / "Application Support" / APP_NAME

    else:
        # Linux/Unix: Use XDG_DATA_HOME or ~/.local/share
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            return Path(xdg_data) / APP_NAME
        return home / ".local" / "share" / APP_NAME


def get_config_directory() -> Path:
    """
    Get the appropriate config directory for the current OS.

    - Windows: Same as data directory
    - macOS: ~/Library/Preferences/dymo-code
    - Linux: ~/.config/dymo-code
    """
    home = Path.home()

    if sys.platform == "win32":
        return get_data_directory()

    elif sys.platform == "darwin":
        return home / "Library" / "Preferences" / APP_NAME

    else:
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config) / APP_NAME
        return home / ".config" / APP_NAME


def ensure_directories():
    """Ensure all required directories exist"""
    data_dir = get_data_directory()
    config_dir = get_config_directory()

    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (data_dir / "history").mkdir(exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)

    return data_dir, config_dir


# ═══════════════════════════════════════════════════════════════════════════════
# User Configuration
# ═══════════════════════════════════════════════════════════════════════════════

class UserConfig:
    """
    Manages user configuration including first-run setup.
    Stored in a simple JSON file for easy access.
    """

    def __init__(self):
        self._config_dir = get_config_directory()
        self._config_file = self._config_dir / "user_config.json"
        self._api_keys_file = self._config_dir / "api_keys.json"
        self._config = self._load_config()
        self._api_keys = self._load_api_keys()

    def _load_config(self) -> dict:
        """Load configuration from file"""
        ensure_directories()

        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return self._default_config()
        return self._default_config()

    def _default_config(self) -> dict:
        """Return default configuration"""
        return {
            "first_run": True,
            "user_name": None,
            "created_at": None,
            "last_seen": None,
            "theme": "default",
            "language": "en"
        }

    def _save_config(self):
        """Save configuration to file"""
        ensure_directories()
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def _load_api_keys(self) -> dict:
        """Load API keys from file"""
        ensure_directories()
        if self._api_keys_file.exists():
            try:
                with open(self._api_keys_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_api_keys(self):
        """Save API keys to file"""
        ensure_directories()
        with open(self._api_keys_file, "w", encoding="utf-8") as f:
            json.dump(self._api_keys, f, indent=2, ensure_ascii=False)

    @property
    def is_first_run(self) -> bool:
        """Check if this is the first run"""
        return self._config.get("first_run", True)

    @property
    def user_name(self) -> Optional[str]:
        """Get the user's name"""
        return self._config.get("user_name")

    @user_name.setter
    def user_name(self, name: str):
        """Set the user's name"""
        self._config["user_name"] = name
        self._save_config()

    def complete_first_run(self, name: str):
        """Complete the first-run setup"""
        now = datetime.now().isoformat()
        self._config["first_run"] = False
        self._config["user_name"] = name
        self._config["created_at"] = now
        self._config["last_seen"] = now
        self._save_config()

    def update_last_seen(self):
        """Update the last seen timestamp"""
        self._config["last_seen"] = datetime.now().isoformat()
        self._save_config()

    def get(self, key: str, default=None):
        """Get a configuration value"""
        return self._config.get(key, default)

    def set(self, key: str, value):
        """Set a configuration value"""
        self._config[key] = value
        self._save_config()

    @property
    def data_directory(self) -> Path:
        """Get the data directory path"""
        return get_data_directory()

    @property
    def config_directory(self) -> Path:
        """Get the config directory path"""
        return get_config_directory()

    # ═══════════════════════════════════════════════════════════════════════════
    # API Keys Management (Single Key - Legacy)
    # ═══════════════════════════════════════════════════════════════════════════

    def set_api_key(self, provider: str, api_key: str):
        """
        Set an API key for a provider (legacy single-key method).
        For multi-key support, use add_api_key instead.
        Valid providers: see API_KEY_PROVIDERS in lib/providers.py
        """
        key_name = f"{provider.upper()}_API_KEY"
        self._api_keys[key_name] = api_key
        self._save_api_keys()

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get primary API key for a provider (first key in list or single key)"""
        # First check multi-key list
        keys_list = self.get_api_keys_list(provider)
        if keys_list:
            return keys_list[0]
        # Fallback to legacy single key
        key_name = f"{provider.upper()}_API_KEY"
        return self._api_keys.get(key_name)

    def delete_api_key(self, provider: str):
        """Delete all API keys for a provider"""
        key_name = f"{provider.upper()}_API_KEY"
        list_key = f"{provider.upper()}_API_KEYS"
        if key_name in self._api_keys:
            del self._api_keys[key_name]
        if list_key in self._api_keys:
            del self._api_keys[list_key]
        self._save_api_keys()

    def get_all_api_keys(self) -> dict:
        """Get all configured API keys (masked)"""
        masked = {}
        for key, value in self._api_keys.items():
            if value and not key.endswith("_KEYS"):  # Skip list keys
                # Show only first 4 and last 4 characters
                if isinstance(value, str):
                    if len(value) > 12:
                        masked[key] = f"{value[:4]}...{value[-4:]}"
                    else:
                        masked[key] = "****"
        return masked

    def get_raw_api_key(self, key_name: str) -> Optional[str]:
        """Get raw API key by exact key name (e.g., GROQ_API_KEY)"""
        return self._api_keys.get(key_name)

    def load_api_keys_to_env(self):
        """Load all stored API keys into environment variables"""
        import os
        for key, value in self._api_keys.items():
            if value and key not in os.environ and not key.endswith("_KEYS"):
                if isinstance(value, str):
                    os.environ[key] = value

    # ═══════════════════════════════════════════════════════════════════════════
    # Multi-API Keys Management (New)
    # ═══════════════════════════════════════════════════════════════════════════

    def add_api_key(self, provider: str, api_key: str) -> bool:
        """
        Add an API key to a provider's key list.
        Returns True if key was added, False if already exists.
        """
        list_key = f"{provider.upper()}_API_KEYS"

        if list_key not in self._api_keys:
            self._api_keys[list_key] = []

        # Migrate legacy single key if exists
        legacy_key = f"{provider.upper()}_API_KEY"
        if legacy_key in self._api_keys and self._api_keys[legacy_key]:
            legacy_val = self._api_keys[legacy_key]
            if legacy_val not in self._api_keys[list_key]:
                self._api_keys[list_key].append(legacy_val)

        # Check if key already exists
        if api_key in self._api_keys[list_key]:
            return False

        self._api_keys[list_key].append(api_key)

        # Also set as primary for backward compatibility
        self._api_keys[legacy_key] = self._api_keys[list_key][0]

        self._save_api_keys()
        return True

    def remove_api_key_by_index(self, provider: str, index: int) -> bool:
        """Remove an API key by index from provider's list"""
        list_key = f"{provider.upper()}_API_KEYS"

        if list_key not in self._api_keys:
            return False

        keys_list = self._api_keys[list_key]
        if not isinstance(keys_list, list) or index < 0 or index >= len(keys_list):
            return False

        keys_list.pop(index)

        # Update primary key
        legacy_key = f"{provider.upper()}_API_KEY"
        if keys_list:
            self._api_keys[legacy_key] = keys_list[0]
        else:
            if legacy_key in self._api_keys:
                del self._api_keys[legacy_key]

        self._save_api_keys()
        return True

    def get_api_keys_list(self, provider: str) -> list:
        """Get list of all API keys for a provider"""
        list_key = f"{provider.upper()}_API_KEYS"
        keys = self._api_keys.get(list_key, [])

        if isinstance(keys, list):
            return keys

        # Fallback to legacy single key
        legacy_key = f"{provider.upper()}_API_KEY"
        single_key = self._api_keys.get(legacy_key)
        if single_key:
            return [single_key]

        return []

    def set_api_keys_list(self, provider: str, keys: list):
        """Set the full list of API keys for a provider"""
        list_key = f"{provider.upper()}_API_KEYS"
        legacy_key = f"{provider.upper()}_API_KEY"

        self._api_keys[list_key] = keys

        # Update primary for backward compatibility
        if keys:
            self._api_keys[legacy_key] = keys[0]
        elif legacy_key in self._api_keys:
            del self._api_keys[legacy_key]

        self._save_api_keys()

    def get_api_key_count(self, provider: str) -> int:
        """Get number of API keys configured for a provider"""
        return len(self.get_api_keys_list(provider))

    def get_all_providers_keys_info(self) -> dict:
        """Get information about all configured API keys per provider"""
        info = {}

        for provider in API_KEY_PROVIDERS:
            keys = self.get_api_keys_list(provider)
            masked_keys = []
            for key in keys:
                if len(key) > 12:
                    masked_keys.append(f"{key[:4]}...{key[-4:]}")
                else:
                    masked_keys.append("****")
            info[provider] = {
                "count": len(keys),
                "keys": masked_keys
            }

        return info


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

user_config = UserConfig()


# ═══════════════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_db_path() -> Path:
    """Get the path to the SQLite database"""
    return get_data_directory() / "memory.db"


def get_history_directory() -> Path:
    """Get the path to the conversation history directory"""
    return get_data_directory() / "history"


def get_logs_directory() -> Path:
    """Get the path to the logs directory"""
    return get_data_directory() / "logs"


def get_mcp_config_path() -> Path:
    """Get the path to MCP configuration file"""
    return get_config_directory() / "mcp.json"
