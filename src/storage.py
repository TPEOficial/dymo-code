"""
Cross-platform Storage System for Dymo Code
Handles user data directory and persistent storage across all operating systems
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

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
        self._config = self._load_config()

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
