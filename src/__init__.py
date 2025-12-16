"""
Dymo Code - AI-powered terminal coding assistant
"""

__version__ = "2.0.0"
__author__ = "Dymo"

from .memory import memory, MemoryManager
from .commands import COMMANDS, get_command_suggestions, parse_command
from .agents import AgentManager, AgentType, AgentStatus, init_agent_manager
from .async_input import async_input, ThreadedInputHandler
from .command_handler import CommandHandler
from .name_detector import detect_and_save_name, get_saved_name
from .storage import (
    user_config,
    UserConfig,
    get_data_directory,
    get_config_directory,
    get_db_path,
    get_history_directory,
    get_logs_directory,
    ensure_directories
)

__all__ = [
    "memory",
    "MemoryManager",
    "COMMANDS",
    "get_command_suggestions",
    "parse_command",
    "AgentManager",
    "AgentType",
    "AgentStatus",
    "init_agent_manager",
    "async_input",
    "ThreadedInputHandler",
    "CommandHandler",
    "detect_and_save_name",
    "get_saved_name",
    "user_config",
    "UserConfig",
    "get_data_directory",
    "get_config_directory",
    "get_db_path",
    "get_history_directory",
    "get_logs_directory",
    "ensure_directories",
]