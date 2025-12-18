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
    "version": Command(
        name="version",
        description="Show current version",
        category=CommandCategory.GENERAL,
        usage="/version",
        aliases=["v"]
    ),
    "update": Command(
        name="update",
        description="Check and install updates",
        category=CommandCategory.GENERAL,
        usage="/update"
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
    "mode": Command(
        name="mode",
        description="View or change agent mode (standard/jailbreak)",
        category=CommandCategory.MODEL,
        usage="/mode [mode]",
        has_args=True,
        arg_hint="standard|jailbreak"
    ),
    "modes": Command(
        name="modes",
        description="View all available agent modes",
        category=CommandCategory.MODEL,
        usage="/modes"
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
    "setapikey": Command(
        name="setapikey",
        description="Set API key for a provider",
        category=CommandCategory.PROVIDERS,
        usage="/setapikey <provider> <key>",
        has_args=True,
        arg_hint="provider key"
    ),
    "apikeys": Command(
        name="apikeys",
        description="View configured API keys",
        category=CommandCategory.PROVIDERS,
        usage="/apikeys"
    ),
    "delapikey": Command(
        name="delapikey",
        description="Delete an API key",
        category=CommandCategory.PROVIDERS,
        usage="/delapikey <provider>",
        has_args=True,
        arg_hint="provider"
    ),
    "getapikey": Command(
        name="getapikey",
        description="Get API key for a provider (interactive)",
        category=CommandCategory.PROVIDERS,
        usage="/getapikey <provider>",
        has_args=True,
        arg_hint="provider"
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
    "sessions": Command(
        name="sessions",
        description="List all sessions with preview",
        category=CommandCategory.HISTORY,
        usage="/sessions [limit]",
        has_args=True,
        arg_hint="limit"
    ),
    "last": Command(
        name="last",
        description="Quick resume last session",
        category=CommandCategory.HISTORY,
        usage="/last"
    ),
    "search": Command(
        name="search",
        description="Search sessions by content",
        category=CommandCategory.HISTORY,
        usage="/search <query>",
        has_args=True,
        arg_hint="search query"
    ),
    "export": Command(
        name="export",
        description="Export current session to markdown",
        category=CommandCategory.HISTORY,
        usage="/export [filename]",
        has_args=True,
        arg_hint="filename.md"
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
    "context": Command(
        name="context",
        description="View context/token usage",
        category=CommandCategory.SYSTEM,
        usage="/context"
    ),

    # Theme Commands
    "theme": Command(
        name="theme",
        description="Change the color theme",
        category=CommandCategory.SYSTEM,
        usage="/theme [name]",
        has_args=True,
        arg_hint="theme name"
    ),
    "themes": Command(
        name="themes",
        description="List all available themes",
        category=CommandCategory.SYSTEM,
        usage="/themes"
    ),

    # Palette Commands
    "commands": Command(
        name="commands",
        description="Open command palette",
        category=CommandCategory.GENERAL,
        usage="/commands",
        aliases=["palette", "cmd"]
    ),
    "keybindings": Command(
        name="keybindings",
        description="View keyboard shortcuts",
        category=CommandCategory.SYSTEM,
        usage="/keybindings",
        aliases=["keys", "shortcuts"]
    ),

    # Clipboard Commands
    "copy": Command(
        name="copy",
        description="Copy last response to clipboard",
        category=CommandCategory.SYSTEM,
        usage="/copy"
    ),

    # File Explorer Commands
    "tree": Command(
        name="tree",
        description="Show directory tree view",
        category=CommandCategory.SYSTEM,
        usage="/tree [path] [depth]",
        has_args=True,
        arg_hint="path depth"
    ),
    "browse": Command(
        name="browse",
        description="Interactive file browser",
        category=CommandCategory.SYSTEM,
        usage="/browse [path]",
        has_args=True,
        arg_hint="start path"
    ),
    "preview": Command(
        name="preview",
        description="Preview file with syntax highlighting",
        category=CommandCategory.SYSTEM,
        usage="/preview <file>",
        has_args=True,
        arg_hint="file path"
    ),
    "find": Command(
        name="find",
        description="Fuzzy find files",
        category=CommandCategory.SYSTEM,
        usage="/find <pattern>",
        has_args=True,
        arg_hint="search pattern"
    ),

    # Setup Command
    "setup": Command(
        name="setup",
        description="Setup 'dymo-code' command for terminal",
        category=CommandCategory.SYSTEM,
        usage="/setup"
    ),

    # Multi-Agent Commands
    "agents": Command(
        name="agents",
        description="View running agent tasks",
        category=CommandCategory.SYSTEM,
        usage="/agents"
    ),
    "tasks": Command(
        name="tasks",
        description="View all agent task history",
        category=CommandCategory.SYSTEM,
        usage="/tasks"
    ),
    "task": Command(
        name="task",
        description="View details of a specific task",
        category=CommandCategory.SYSTEM,
        usage="/task <task_id>",
        has_args=True,
        arg_hint="task_id"
    ),
    "cleartasks": Command(
        name="cleartasks",
        description="Clear completed agent tasks",
        category=CommandCategory.SYSTEM,
        usage="/cleartasks"
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
