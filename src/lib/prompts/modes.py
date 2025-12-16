"""
Agent Mode System for Dymo Code
Manages different personality/behavior modes for the AI agent
"""

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum

from .dan import PROMPT as DAN_PROMPT


class AgentMode(Enum):
    """Available agent modes"""
    STANDARD = "standard"
    JAILBREAK = "jailbreak"

@dataclass
class ModeConfig:
    """Configuration for an agent mode"""
    name: str
    display_name: str
    description: str
    prompt_prefix: Optional[str] = None
    icon: str = ""


# Mode configurations
MODE_CONFIGS: Dict[AgentMode, ModeConfig] = {
    AgentMode.STANDARD: ModeConfig(
        name="standard",
        display_name="Standard",
        description="Default helpful AI coding assistant mode",
        prompt_prefix=None, # Uses default system prompt
        icon="*"
    ),
    AgentMode.JAILBREAK: ModeConfig(
        name="jailbreak",
        display_name="Jailbreak",
        description="Unrestricted DAN mode - use responsibly",
        prompt_prefix=DAN_PROMPT,
        icon="!"
    ),
}


class ModeManager:
    """
    Manages the current agent mode.
    Singleton pattern to maintain state across the application.
    """
    _instance = None
    _current_mode: AgentMode = AgentMode.STANDARD

    def __new__(cls):
        if cls._instance is None: cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def current_mode(self) -> AgentMode:
        """Get the current mode"""
        return self._current_mode

    @property
    def current_config(self) -> ModeConfig:
        """Get the current mode configuration"""
        return MODE_CONFIGS[self._current_mode]

    def set_mode(self, mode: AgentMode) -> bool:
        """
        Set the current mode.
        Returns True if mode changed, False if same mode.
        """
        if self._current_mode == mode: return False
        self._current_mode = mode
        return True

    def set_mode_by_name(self, name: str) -> bool:
        """
        Set mode by name string.
        Returns True if successful, False if mode not found.
        """
        name = name.lower().strip()
        for mode in AgentMode:
            if mode.value == name:
                self._current_mode = mode
                return True
        return False

    def get_mode_prompt(self) -> Optional[str]:
        """Get the prompt prefix for the current mode, or None for default"""
        return self.current_config.prompt_prefix

    def get_display_info(self) -> tuple:
        """Get (icon, display_name) for UI display"""
        config = self.current_config
        return config.icon, config.display_name

    @staticmethod
    def get_available_modes() -> list:
        """Get list of all available modes"""
        return [(mode.value, MODE_CONFIGS[mode]) for mode in AgentMode]

# Global mode manager instance
mode_manager = ModeManager()
