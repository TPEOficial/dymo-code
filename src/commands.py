"""
Interactive Command System for Dymo Code
Provides slash commands with real-time autocomplete and visual feedback
"""

from dataclasses import dataclass
from typing import List, Optional, Callable, Dict, Any
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
# Command Definitions
# ═══════════════════════════════════════════════════════════════════════════════

class CommandCategory(Enum):
    GENERAL = "general"
    MEMORY = "memory"
    MODEL = "model"
    PROVIDERS = "providers"
    HISTORY = "history"
    SYSTEM = "system"


@dataclass
class Command:
    """Represents a slash command"""
    name: str
    description: str
    category: CommandCategory
    usage: str
    aliases: List[str] = None
    has_args: bool = False
    arg_hint: str = None

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


# ═══════════════════════════════════════════════════════════════════════════════
# Command Registry
# ═══════════════════════════════════════════════════════════════════════════════

COMMANDS: Dict[str, Command] = {
    # General Commands
    "help": Command(
        name="help",
        description="Show all available commands",
        category=CommandCategory.GENERAL,
        usage="/help",
        aliases=["h", "?"]
    ),
    "exit": Command(
        name="exit",
        description="Exit the agent",
        category=CommandCategory.GENERAL,
        usage="/exit",
        aliases=["quit", "q"]
    ),
    "clear": Command(
        name="clear",
        description="Clear conversation history",
        category=CommandCategory.GENERAL,
        usage="/clear",
        aliases=["cls"]
    ),

    # Memory Commands
    "remember": Command(
        name="remember",
        description="Save information to remember",
        category=CommandCategory.MEMORY,
        usage="/remember <info>",
        has_args=True,
        arg_hint="information"
    ),
    "whoami": Command(
        name="whoami",
        description="View your saved profile",
        category=CommandCategory.MEMORY,
        usage="/whoami"
    ),
    "setname": Command(
        name="setname",
        description="Set your name",
        category=CommandCategory.MEMORY,
        usage="/setname <name>",
        has_args=True,
        arg_hint="your name"
    ),
    "forget": Command(
        name="forget",
        description="Forget specific information",
        category=CommandCategory.MEMORY,
        usage="/forget <id>",
        has_args=True,
        arg_hint="fact id"
    ),
    "facts": Command(
        name="facts",
        description="View all saved facts",
        category=CommandCategory.MEMORY,
        usage="/facts"
    ),
    "notes": Command(
        name="notes",
        description="View all saved notes",
        category=CommandCategory.MEMORY,
        usage="/notes"
    ),
    "note": Command(
        name="note",
        description="Create a new note",
        category=CommandCategory.MEMORY,
        usage="/note <title> | <content>",
        has_args=True,
        arg_hint="title | content"
    ),
    "projects": Command(
        name="projects",
        description="View saved projects",
        category=CommandCategory.MEMORY,
        usage="/projects"
    ),
    "addproject": Command(
        name="addproject",
        description="Add current project",
        category=CommandCategory.MEMORY,
        usage="/addproject <name>",
        has_args=True,
        arg_hint="project name"
    ),
    "prefs": Command(
        name="prefs",
        description="View saved preferences",
        category=CommandCategory.MEMORY,
        usage="/prefs"
    ),
    "setpref": Command(
        name="setpref",
        description="Set a preference",
        category=CommandCategory.MEMORY,
        usage="/setpref <key> <value>",
        has_args=True,
        arg_hint="key value"
    ),

    # Model Commands
    "model": Command(
        name="model",
        description="View or change current model",
        category=CommandCategory.MODEL,
        usage="/model [name]",
        has_args=True,
        arg_hint="model name"
    ),
    "models": Command(
        name="models",
        description="View all available models",
        category=CommandCategory.MODEL,
        usage="/models"
    ),

    # Provider Commands
    "providers": Command(
        name="providers",
        description="View API providers status",
        category=CommandCategory.PROVIDERS,
        usage="/providers"
    ),
    "ollama": Command(
        name="ollama",
        description="Manage local Ollama models",
        category=CommandCategory.PROVIDERS,
        usage="/ollama [list|use <model>]",
        has_args=True,
        arg_hint="list|use model"
    ),
    "mcp": Command(
        name="mcp",
        description="Manage MCP servers",
        category=CommandCategory.PROVIDERS,
        usage="/mcp [list|tools|add|remove|connect|disconnect]",
        has_args=True,
        arg_hint="command"
    ),

    # History Commands
    "resume": Command(
        name="resume",
        description="Resume a previous conversation",
        category=CommandCategory.HISTORY,
        usage="/resume [id]",
        has_args=True,
        arg_hint="conversation id"
    ),
    "history": Command(
        name="history",
        description="View conversation history",
        category=CommandCategory.HISTORY,
        usage="/history",
        aliases=["hist"]
    ),

    # System Commands
    "queue": Command(
        name="queue",
        description="View queued messages",
        category=CommandCategory.SYSTEM,
        usage="/queue"
    ),
    "clearqueue": Command(
        name="clearqueue",
        description="Clear message queue",
        category=CommandCategory.SYSTEM,
        usage="/clearqueue"
    ),
    "status": Command(
        name="status",
        description="View system status",
        category=CommandCategory.SYSTEM,
        usage="/status"
    ),
    "debug": Command(
        name="debug",
        description="Toggle debug mode",
        category=CommandCategory.SYSTEM,
        usage="/debug"
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Command Matching & Autocomplete
# ═══════════════════════════════════════════════════════════════════════════════

def get_command_suggestions(partial: str) -> List[Command]:
    """
    Get command suggestions based on partial input.
    Returns matching commands sorted by relevance.
    """
    if not partial:
        return list(COMMANDS.values())

    partial = partial.lower().lstrip("/")
    suggestions = []

    for name, cmd in COMMANDS.items():
        # Check main name
        if name.startswith(partial):
            suggestions.append((0, cmd))  # Highest priority
        elif partial in name:
            suggestions.append((1, cmd))  # Medium priority
        # Check aliases
        elif cmd.aliases:
            for alias in cmd.aliases:
                if alias.startswith(partial):
                    suggestions.append((0, cmd))
                    break
                elif partial in alias:
                    suggestions.append((1, cmd))
                    break

    # Sort by priority and return commands only
    suggestions.sort(key=lambda x: (x[0], x[1].name))
    return [cmd for _, cmd in suggestions]


def get_command(name: str) -> Optional[Command]:
    """Get a command by name or alias"""
    name = name.lower().lstrip("/")

    if name in COMMANDS:
        return COMMANDS[name]

    # Check aliases
    for cmd in COMMANDS.values():
        if cmd.aliases and name in cmd.aliases:
            return cmd

    return None


def parse_command(input_text: str) -> tuple[Optional[Command], str]:
    """
    Parse input text to extract command and arguments.
    Returns (command, args) or (None, "") if not a command.
    """
    if not input_text.startswith("/"):
        return None, ""

    parts = input_text[1:].split(maxsplit=1)
    if not parts:
        return None, ""

    cmd_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    command = get_command(cmd_name)
    return command, args


# ═══════════════════════════════════════════════════════════════════════════════
# Command Categories Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_commands_by_category() -> Dict[CommandCategory, List[Command]]:
    """Get commands grouped by category"""
    result = {}
    for cmd in COMMANDS.values():
        if cmd.category not in result:
            result[cmd.category] = []
        result[cmd.category].append(cmd)

    # Sort commands within each category
    for cat in result:
        result[cat].sort(key=lambda x: x.name)

    return result


CATEGORY_ICONS = {
    CommandCategory.GENERAL: "📌",
    CommandCategory.MEMORY: "🧠",
    CommandCategory.MODEL: "🤖",
    CommandCategory.PROVIDERS: "🔌",
    CommandCategory.HISTORY: "📜",
    CommandCategory.SYSTEM: "⚙️",
}

CATEGORY_NAMES = {
    CommandCategory.GENERAL: "General",
    CommandCategory.MEMORY: "Memory",
    CommandCategory.MODEL: "Model",
    CommandCategory.PROVIDERS: "Providers & MCP",
    CommandCategory.HISTORY: "History",
    CommandCategory.SYSTEM: "System",
}
