"""
Theme system for Dymo Code
Inspired by OpenCode's dynamic theming approach
"""

import json
from dataclasses import dataclass, field
from typing import Dict, Optional
from pathlib import Path
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# Theme Definitions
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ThemeColors:
    """Color scheme for a theme"""
    primary: str
    secondary: str
    success: str
    warning: str
    error: str
    muted: str
    accent: str
    background: str = "#1e1e1e"
    foreground: str = "#ffffff"
    border: str = "#333333"
    selection: str = "#264f78"

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for compatibility"""
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "success": self.success,
            "warning": self.warning,
            "error": self.error,
            "muted": self.muted,
            "accent": self.accent,
            "background": self.background,
            "foreground": self.foreground,
            "border": self.border,
            "selection": self.selection,
        }


@dataclass
class Theme:
    """Complete theme definition"""
    name: str
    display_name: str
    colors: ThemeColors
    is_dark: bool = True
    description: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Built-in Themes
# ═══════════════════════════════════════════════════════════════════════════════

BUILTIN_THEMES: Dict[str, Theme] = {
    "default": Theme(
        name="default",
        display_name="Default Purple",
        description="The classic Dymo Code theme",
        is_dark=True,
        colors=ThemeColors(
            primary="#7C3AED",
            secondary="#06B6D4",
            success="#10B981",
            warning="#F59E0B",
            error="#EF4444",
            muted="#6B7280",
            accent="#EC4899",
        )
    ),

    "catppuccin-mocha": Theme(
        name="catppuccin-mocha",
        display_name="Catppuccin Mocha",
        description="Soothing pastel theme for dark mode",
        is_dark=True,
        colors=ThemeColors(
            primary="#CBA6F7",      # Mauve
            secondary="#89DCEB",    # Sky
            success="#A6E3A1",      # Green
            warning="#F9E2AF",      # Yellow
            error="#F38BA8",        # Red
            muted="#6C7086",        # Overlay0
            accent="#F5C2E7",       # Pink
            background="#1E1E2E",   # Base
            foreground="#CDD6F4",   # Text
            border="#313244",       # Surface0
            selection="#45475A",    # Surface1
        )
    ),

    "catppuccin-latte": Theme(
        name="catppuccin-latte",
        display_name="Catppuccin Latte",
        description="Soothing pastel theme for light mode",
        is_dark=False,
        colors=ThemeColors(
            primary="#8839EF",      # Mauve
            secondary="#04A5E5",    # Sky
            success="#40A02B",      # Green
            warning="#DF8E1D",      # Yellow
            error="#D20F39",        # Red
            muted="#9CA0B0",        # Overlay0
            accent="#EA76CB",       # Pink
            background="#EFF1F5",   # Base
            foreground="#4C4F69",   # Text
            border="#BCC0CC",       # Surface0
            selection="#ACB0BE",    # Surface1
        )
    ),

    "tokyo-night": Theme(
        name="tokyo-night",
        display_name="Tokyo Night",
        description="Dark theme inspired by Tokyo city lights",
        is_dark=True,
        colors=ThemeColors(
            primary="#7AA2F7",      # Blue
            secondary="#7DCFFF",    # Cyan
            success="#9ECE6A",      # Green
            warning="#E0AF68",      # Yellow
            error="#F7768E",        # Red
            muted="#565F89",        # Comment
            accent="#BB9AF7",       # Magenta
            background="#1A1B26",
            foreground="#C0CAF5",
            border="#292E42",
            selection="#33467C",
        )
    ),

    "dracula": Theme(
        name="dracula",
        display_name="Dracula",
        description="Dark theme with vibrant colors",
        is_dark=True,
        colors=ThemeColors(
            primary="#BD93F9",      # Purple
            secondary="#8BE9FD",    # Cyan
            success="#50FA7B",      # Green
            warning="#FFB86C",      # Orange
            error="#FF5555",        # Red
            muted="#6272A4",        # Comment
            accent="#FF79C6",       # Pink
            background="#282A36",
            foreground="#F8F8F2",
            border="#44475A",
            selection="#44475A",
        )
    ),

    "nord": Theme(
        name="nord",
        display_name="Nord",
        description="Arctic, north-bluish color palette",
        is_dark=True,
        colors=ThemeColors(
            primary="#81A1C1",      # Frost
            secondary="#88C0D0",    # Frost Light
            success="#A3BE8C",      # Aurora Green
            warning="#EBCB8B",      # Aurora Yellow
            error="#BF616A",        # Aurora Red
            muted="#4C566A",        # Polar Night
            accent="#B48EAD",       # Aurora Purple
            background="#2E3440",
            foreground="#ECEFF4",
            border="#3B4252",
            selection="#434C5E",
        )
    ),

    "gruvbox": Theme(
        name="gruvbox",
        display_name="Gruvbox Dark",
        description="Retro groove color scheme",
        is_dark=True,
        colors=ThemeColors(
            primary="#D3869B",      # Purple
            secondary="#83A598",    # Aqua
            success="#B8BB26",      # Green
            warning="#FABD2F",      # Yellow
            error="#FB4934",        # Red
            muted="#928374",        # Gray
            accent="#FE8019",       # Orange
            background="#282828",
            foreground="#EBDBB2",
            border="#3C3836",
            selection="#504945",
        )
    ),

    "one-dark": Theme(
        name="one-dark",
        display_name="One Dark",
        description="Atom's iconic One Dark theme",
        is_dark=True,
        colors=ThemeColors(
            primary="#61AFEF",      # Blue
            secondary="#56B6C2",    # Cyan
            success="#98C379",      # Green
            warning="#E5C07B",      # Yellow
            error="#E06C75",        # Red
            muted="#5C6370",        # Comment
            accent="#C678DD",       # Purple
            background="#282C34",
            foreground="#ABB2BF",
            border="#3E4451",
            selection="#3E4451",
        )
    ),

    "github-dark": Theme(
        name="github-dark",
        display_name="GitHub Dark",
        description="GitHub's dark mode theme",
        is_dark=True,
        colors=ThemeColors(
            primary="#58A6FF",      # Blue
            secondary="#79C0FF",    # Light Blue
            success="#3FB950",      # Green
            warning="#D29922",      # Yellow
            error="#F85149",        # Red
            muted="#8B949E",        # Gray
            accent="#D2A8FF",       # Purple
            background="#0D1117",
            foreground="#C9D1D9",
            border="#30363D",
            selection="#264F78",
        )
    ),

    "solarized-dark": Theme(
        name="solarized-dark",
        display_name="Solarized Dark",
        description="Precision colors for machines and people",
        is_dark=True,
        colors=ThemeColors(
            primary="#268BD2",      # Blue
            secondary="#2AA198",    # Cyan
            success="#859900",      # Green
            warning="#B58900",      # Yellow
            error="#DC322F",        # Red
            muted="#586E75",        # Base01
            accent="#D33682",       # Magenta
            background="#002B36",
            foreground="#839496",
            border="#073642",
            selection="#073642",
        )
    ),

    "monokai": Theme(
        name="monokai",
        display_name="Monokai",
        description="Classic Sublime Text theme",
        is_dark=True,
        colors=ThemeColors(
            primary="#66D9EF",      # Blue
            secondary="#A6E22E",    # Green
            success="#A6E22E",      # Green
            warning="#E6DB74",      # Yellow
            error="#F92672",        # Pink/Red
            muted="#75715E",        # Comment
            accent="#AE81FF",       # Purple
            background="#272822",
            foreground="#F8F8F2",
            border="#3E3D32",
            selection="#49483E",
        )
    ),

    "cyberpunk": Theme(
        name="cyberpunk",
        display_name="Cyberpunk",
        description="Neon-lit futuristic theme",
        is_dark=True,
        colors=ThemeColors(
            primary="#00F0FF",      # Neon Cyan
            secondary="#FF00FF",    # Neon Magenta
            success="#00FF00",      # Neon Green
            warning="#FFD700",      # Gold
            error="#FF0040",        # Neon Red
            muted="#666666",        # Gray
            accent="#FF00FF",       # Magenta
            background="#0A0A0F",
            foreground="#00F0FF",
            border="#1A1A2E",
            selection="#16213E",
        )
    ),

    "high-contrast": Theme(
        name="high-contrast",
        display_name="High Contrast",
        description="Maximum visibility theme",
        is_dark=True,
        colors=ThemeColors(
            primary="#00FFFF",      # Cyan
            secondary="#00FF00",    # Green
            success="#00FF00",      # Green
            warning="#FFFF00",      # Yellow
            error="#FF0000",        # Red
            muted="#AAAAAA",        # Light Gray
            accent="#FF00FF",       # Magenta
            background="#000000",
            foreground="#FFFFFF",
            border="#FFFFFF",
            selection="#0000FF",
        )
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Theme Manager
# ═══════════════════════════════════════════════════════════════════════════════

class ThemeManager:
    """
    Manages theme selection and persistence.
    Singleton pattern to ensure consistent theme state.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._current_theme_name = "default"
        self._custom_themes: Dict[str, Theme] = {}
        self._config_path: Optional[Path] = None
        self._initialized = True

        # Load saved theme preference
        self._load_preference()

    def _get_config_path(self) -> Path:
        """Get path to theme config file"""
        if self._config_path:
            return self._config_path

        from .storage import storage
        self._config_path = storage.data_dir / "theme.json"
        return self._config_path

    def _load_preference(self):
        """Load theme preference from disk"""
        try:
            config_path = self._get_config_path()
            if config_path.exists():
                data = json.loads(config_path.read_text())
                theme_name = data.get("theme", "default")
                if theme_name in self.available_themes:
                    self._current_theme_name = theme_name
        except Exception:
            pass  # Use default theme on error

    def _save_preference(self):
        """Save theme preference to disk"""
        try:
            config_path = self._get_config_path()
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps({
                "theme": self._current_theme_name
            }, indent=2))
        except Exception:
            pass  # Ignore save errors

    @property
    def available_themes(self) -> Dict[str, Theme]:
        """Get all available themes (built-in + custom)"""
        return {**BUILTIN_THEMES, **self._custom_themes}

    @property
    def current_theme(self) -> Theme:
        """Get the currently active theme"""
        return self.available_themes.get(self._current_theme_name, BUILTIN_THEMES["default"])

    @property
    def current_theme_name(self) -> str:
        """Get the name of the current theme"""
        return self._current_theme_name

    @property
    def colors(self) -> Dict[str, str]:
        """Get current theme colors as a dictionary (for backward compatibility)"""
        return self.current_theme.colors.to_dict()

    def set_theme(self, theme_name: str) -> bool:
        """
        Set the active theme by name.
        Returns True if successful, False if theme not found.
        """
        if theme_name not in self.available_themes:
            return False

        self._current_theme_name = theme_name
        self._save_preference()
        return True

    def add_custom_theme(self, theme: Theme):
        """Add a custom theme"""
        self._custom_themes[theme.name] = theme

    def remove_custom_theme(self, theme_name: str) -> bool:
        """Remove a custom theme"""
        if theme_name in self._custom_themes:
            del self._custom_themes[theme_name]
            if self._current_theme_name == theme_name:
                self._current_theme_name = "default"
                self._save_preference()
            return True
        return False

    def list_themes(self) -> list:
        """Get list of all theme names with their display names"""
        themes = []
        for name, theme in self.available_themes.items():
            themes.append({
                "name": name,
                "display_name": theme.display_name,
                "description": theme.description,
                "is_dark": theme.is_dark,
                "is_current": name == self._current_theme_name,
                "is_builtin": name in BUILTIN_THEMES,
            })
        return themes


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance and Helpers
# ═══════════════════════════════════════════════════════════════════════════════

theme_manager = ThemeManager()

def get_colors() -> Dict[str, str]:
    """Get current theme colors (for backward compatibility with COLORS constant)"""
    return theme_manager.colors

def get_color(name: str) -> str:
    """Get a specific color from the current theme"""
    return theme_manager.colors.get(name, "#FFFFFF")
