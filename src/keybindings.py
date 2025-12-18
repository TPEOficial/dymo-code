"""
Global keybindings system for Dymo Code
Inspired by OpenCode's keybinding architecture
"""

import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# Key Modifiers
# ═══════════════════════════════════════════════════════════════════════════════

class KeyModifier(Enum):
    CTRL = "ctrl"
    ALT = "alt"
    SHIFT = "shift"
    META = "meta"  # Cmd on macOS, Win on Windows


# ═══════════════════════════════════════════════════════════════════════════════
# Keybind Definition
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Keybind:
    """Represents a keyboard shortcut"""
    key: str
    modifiers: List[KeyModifier] = field(default_factory=list)
    description: str = ""
    command: Optional[str] = None  # Associated command name
    action: Optional[Callable[[], Any]] = None  # Direct action
    enabled: bool = True
    context: str = "global"  # global, input, chat, etc.

    def __str__(self) -> str:
        """Return human-readable keybind string"""
        parts = []
        for mod in self.modifiers:
            if mod == KeyModifier.CTRL:
                parts.append("Ctrl")
            elif mod == KeyModifier.ALT:
                parts.append("Alt")
            elif mod == KeyModifier.SHIFT:
                parts.append("Shift")
            elif mod == KeyModifier.META:
                parts.append("Cmd" if sys.platform == "darwin" else "Win")
        parts.append(self.key.upper() if len(self.key) == 1 else self.key)
        return "+".join(parts)

    @property
    def display(self) -> str:
        """Return display string with symbols"""
        parts = []
        for mod in self.modifiers:
            if mod == KeyModifier.CTRL:
                parts.append("^")
            elif mod == KeyModifier.ALT:
                parts.append("⌥" if sys.platform == "darwin" else "Alt+")
            elif mod == KeyModifier.SHIFT:
                parts.append("⇧")
            elif mod == KeyModifier.META:
                parts.append("⌘" if sys.platform == "darwin" else "Win+")
        parts.append(self.key.upper() if len(self.key) == 1 else self.key)
        return "".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Default Keybindings
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_KEYBINDINGS: Dict[str, Keybind] = {
    # Session Management
    "new_session": Keybind(
        key="n",
        modifiers=[KeyModifier.CTRL],
        description="Start new conversation",
        command="clear"
    ),
    "exit": Keybind(
        key="q",
        modifiers=[KeyModifier.CTRL],
        description="Exit Dymo Code",
        command="exit"
    ),

    # Navigation
    "command_palette": Keybind(
        key="p",
        modifiers=[KeyModifier.CTRL],
        description="Open command palette",
        command="commands"
    ),
    "help": Keybind(
        key="h",
        modifiers=[KeyModifier.CTRL],
        description="Show help",
        command="help"
    ),

    # Model & Mode
    "toggle_model": Keybind(
        key="m",
        modifiers=[KeyModifier.CTRL],
        description="Quick switch model",
        command="models"
    ),
    "toggle_mode": Keybind(
        key="m",
        modifiers=[KeyModifier.CTRL, KeyModifier.SHIFT],
        description="Toggle agent mode",
        command="mode"
    ),

    # History
    "history": Keybind(
        key="r",
        modifiers=[KeyModifier.CTRL],
        description="Resume conversation",
        command="resume"
    ),

    # Display
    "clear_screen": Keybind(
        key="l",
        modifiers=[KeyModifier.CTRL],
        description="Clear screen",
        command="cls"
    ),
    "toggle_theme": Keybind(
        key="t",
        modifiers=[KeyModifier.CTRL],
        description="Change theme",
        command="theme"
    ),

    # Clipboard
    "copy_last": Keybind(
        key="c",
        modifiers=[KeyModifier.CTRL, KeyModifier.SHIFT],
        description="Copy last response",
        command="copy"
    ),

    # System
    "status": Keybind(
        key="s",
        modifiers=[KeyModifier.CTRL],
        description="Show status",
        command="status"
    ),
    "context": Keybind(
        key="i",
        modifiers=[KeyModifier.CTRL],
        description="Show context info",
        command="context"
    ),

    # Quick Actions
    "interrupt": Keybind(
        key="c",
        modifiers=[KeyModifier.CTRL],
        description="Interrupt current operation",
        context="processing"
    ),
    "submit": Keybind(
        key="Enter",
        modifiers=[],
        description="Submit input",
        context="input"
    ),
    "multiline": Keybind(
        key="Enter",
        modifiers=[KeyModifier.SHIFT],
        description="New line (multiline input)",
        context="input"
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Keybinding Manager
# ═══════════════════════════════════════════════════════════════════════════════

class KeybindManager:
    """
    Manages global keybindings.
    Singleton pattern for consistent state.
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

        self._keybindings: Dict[str, Keybind] = DEFAULT_KEYBINDINGS.copy()
        self._custom_keybindings: Dict[str, Keybind] = {}
        self._handlers: Dict[str, Callable] = {}
        self._initialized = True

    @property
    def keybindings(self) -> Dict[str, Keybind]:
        """Get all keybindings (default + custom)"""
        return {**self._keybindings, **self._custom_keybindings}

    def get_keybind(self, name: str) -> Optional[Keybind]:
        """Get a keybinding by name"""
        return self.keybindings.get(name)

    def get_keybind_for_command(self, command: str) -> Optional[Keybind]:
        """Get the keybinding associated with a command"""
        for keybind in self.keybindings.values():
            if keybind.command == command:
                return keybind
        return None

    def set_keybind(self, name: str, keybind: Keybind):
        """Set or override a keybinding"""
        self._custom_keybindings[name] = keybind

    def remove_keybind(self, name: str) -> bool:
        """Remove a custom keybinding"""
        if name in self._custom_keybindings:
            del self._custom_keybindings[name]
            return True
        return False

    def reset_keybind(self, name: str):
        """Reset a keybinding to default"""
        if name in self._custom_keybindings:
            del self._custom_keybindings[name]

    def reset_all(self):
        """Reset all keybindings to defaults"""
        self._custom_keybindings.clear()

    def register_handler(self, name: str, handler: Callable):
        """Register a handler function for a keybinding"""
        self._handlers[name] = handler

    def execute(self, name: str) -> bool:
        """Execute the handler for a keybinding"""
        if name in self._handlers:
            self._handlers[name]()
            return True
        return False

    def get_keybindings_for_context(self, context: str) -> List[Keybind]:
        """Get all keybindings for a specific context"""
        return [
            kb for kb in self.keybindings.values()
            if kb.context == context and kb.enabled
        ]

    def list_keybindings(self) -> List[dict]:
        """Get all keybindings as a list of dicts for display"""
        result = []
        for name, kb in self.keybindings.items():
            result.append({
                "name": name,
                "display": kb.display,
                "full": str(kb),
                "description": kb.description,
                "command": kb.command,
                "context": kb.context,
                "enabled": kb.enabled,
                "is_custom": name in self._custom_keybindings,
            })
        return sorted(result, key=lambda x: x["context"] + x["name"])


# ═══════════════════════════════════════════════════════════════════════════════
# Prompt Toolkit Key Bindings Integration
# ═══════════════════════════════════════════════════════════════════════════════

def create_prompt_keybindings(keybind_manager: KeybindManager, command_handler: Callable):
    """
    Create prompt_toolkit key bindings from KeybindManager.

    Args:
        keybind_manager: The keybinding manager instance
        command_handler: Function to handle commands (receives command string)

    Returns:
        prompt_toolkit KeyBindings object
    """
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys

    kb = KeyBindings()

    # Map our modifiers to prompt_toolkit
    def get_pt_key(keybind: Keybind) -> str:
        """Convert our Keybind to prompt_toolkit key string"""
        key = keybind.key.lower()

        # Handle special keys
        special_keys = {
            "enter": Keys.Enter,
            "escape": Keys.Escape,
            "tab": Keys.Tab,
            "backspace": Keys.Backspace,
            "delete": Keys.Delete,
            "up": Keys.Up,
            "down": Keys.Down,
            "left": Keys.Left,
            "right": Keys.Right,
            "home": Keys.Home,
            "end": Keys.End,
            "pageup": Keys.PageUp,
            "pagedown": Keys.PageDown,
        }

        if key in special_keys:
            return special_keys[key]

        # Build modifier prefix
        prefix = ""
        for mod in keybind.modifiers:
            if mod == KeyModifier.CTRL:
                prefix = "c-"
            elif mod == KeyModifier.ALT:
                prefix = "escape " if sys.platform != "win32" else "escape "
            elif mod == KeyModifier.SHIFT:
                key = key.upper()

        return prefix + key

    # Register keybindings that have commands
    for name, keybind in keybind_manager.keybindings.items():
        if not keybind.enabled or not keybind.command:
            continue

        if keybind.context not in ["global", "input"]:
            continue

        try:
            pt_key = get_pt_key(keybind)
            cmd = keybind.command

            # Create the handler
            @kb.add(pt_key)
            def handler(event, command=cmd):
                # Execute the command
                command_handler(f"/{command}")

        except Exception:
            # Skip invalid key combinations
            pass

    return kb


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

keybind_manager = KeybindManager()


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_keybind_display(command: str) -> Optional[str]:
    """Get the display string for a command's keybinding"""
    kb = keybind_manager.get_keybind_for_command(command)
    return kb.display if kb else None

def format_keybind_hint(command: str) -> str:
    """Format a keybinding hint for display in help text"""
    display = get_keybind_display(command)
    if display:
        return f" [{display}]"
    return ""
