"""
Command Handler for Dymo Code
Handles all slash commands and their execution
"""

import os
from typing import Optional, Tuple, Any

from rich.console import Console
from rich.table import Table
from rich.box import ROUNDED

from .config import COLORS, AVAILABLE_MODELS
from .commands import parse_command, Command, CommandCategory, get_commands_by_category, CATEGORY_ICONS, CATEGORY_NAMES
from .memory import memory
from .ui import (
    console,
    print_help,
    print_models,
    print_conversations,
    print_user_profile,
    print_facts,
    print_notes,
    print_projects,
    print_preferences,
    print_agents_status,
    print_providers,
    print_mcp_servers,
    print_mcp_tools,
    print_ollama_models,
    show_status,
    display_success,
    display_error,
    display_info
)


# ═══════════════════════════════════════════════════════════════════════════════
# Enhanced Help Display
# ═══════════════════════════════════════════════════════════════════════════════

def print_enhanced_help():
    """Print enhanced help with all commands grouped by category"""
    categories = get_commands_by_category()

    console.print()

    for category in CommandCategory:
        if category not in categories:
            continue

        commands = categories[category]
        icon = CATEGORY_ICONS.get(category, "•")
        name = CATEGORY_NAMES.get(category, category.value)

        # Category table
        table = Table(
            title=f"{icon} {name}",
            box=ROUNDED,
            title_style=f"bold {COLORS['secondary']}",
            header_style=f"bold {COLORS['muted']}",
            show_header=False,
            padding=(0, 1)
        )
        table.add_column("Command", style=f"{COLORS['accent']}", width=20)
        table.add_column("Description", style="white")

        for cmd in commands:
            usage = f"/{cmd.name}"
            if cmd.has_args and cmd.arg_hint:
                usage += f" <{cmd.arg_hint}>"

            aliases = ""
            if cmd.aliases:
                aliases = f" ({', '.join('/' + a for a in cmd.aliases)})"

            table.add_row(usage, cmd.description + aliases)

        console.print(table)
        console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# Command Handler Class
# ═══════════════════════════════════════════════════════════════════════════════

class CommandHandler:
    """Handles execution of slash commands"""

    def __init__(self, agent, queue_manager, agent_manager=None):
        self.agent = agent
        self.queue_manager = queue_manager
        self.agent_manager = agent_manager

    def handle(self, user_input: str) -> Tuple[bool, Optional[str]]:
        """
        Handle a potential command.

        Returns:
            (is_command, result)
            - is_command: True if input was a command, False if regular chat
            - result: None for continue, "exit" to exit, or message to display
        """
        command, args = parse_command(user_input)

        if command is None:
            # Not a command - just "/" by itself shows help
            if user_input.strip() == "/":
                print_enhanced_help()
                return True, None
            return False, None

        # Execute the command
        return self._execute_command(command, args)

    def _execute_command(self, command: Command, args: str) -> Tuple[bool, Optional[str]]:
        """Execute a specific command"""
        name = command.name

        # ═══════════════════════════════════════════════════════════════════════
        # General Commands
        # ═══════════════════════════════════════════════════════════════════════

        if name in ["exit", "quit"]:
            console.print(f"\n[{COLORS['muted']}]Goodbye![/]\n")
            return True, "exit"

        elif name == "help":
            print_enhanced_help()
            return True, None

        elif name == "clear":
            self.agent.clear_history()
            if self.queue_manager:
                self.queue_manager.clear_queue()
            console.clear()
            display_success("Conversation cleared.")
            return True, None

        # ═══════════════════════════════════════════════════════════════════════
        # Memory Commands
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "remember":
            if not args:
                display_error("Usage: /remember <information>")
                return True, None

            fact_id = memory.add_fact(args, category="user_input", source="command")
            display_success(f"Saved with ID #{fact_id}: {args}")
            return True, None

        elif name == "whoami":
            profile = memory.get_all_profile()
            print_user_profile(profile)
            return True, None

        elif name == "setname":
            if not args:
                display_error("Usage: /setname <your name>")
                return True, None

            memory.set_profile("name", args, category="identity")
            display_success(f"Your name has been saved as: {args}")
            return True, None

        elif name == "forget":
            if not args:
                display_error("Usage: /forget <id>")
                return True, None

            try:
                fact_id = int(args)
                if memory.delete_fact(fact_id):
                    display_success(f"Fact #{fact_id} deleted.")
                else:
                    display_error(f"Fact #{fact_id} not found")
            except ValueError:
                display_error("ID must be a number.")
            return True, None

        elif name == "facts":
            facts = memory.get_facts()
            print_facts(facts)
            return True, None

        elif name == "notes":
            notes = memory.get_notes()
            print_notes(notes)
            return True, None

        elif name == "note":
            if not args or "|" not in args:
                display_error("Usage: /note <title> | <content>")
                return True, None

            parts = args.split("|", 1)
            title = parts[0].strip()
            content = parts[1].strip()

            note_id = memory.add_note(title, content)
            display_success(f"Note #{note_id} created: {title}")
            return True, None

        elif name == "projects":
            projects = memory.get_projects()
            print_projects(projects)
            return True, None

        elif name == "addproject":
            if not args:
                display_error("Usage: /addproject <name>")
                return True, None

            current_path = os.getcwd()
            memory.add_project(args, path=current_path)
            display_success(f"Project '{args}' added ({current_path})")
            return True, None

        elif name == "prefs":
            prefs = memory.get_all_preferences()
            print_preferences(prefs)
            return True, None

        elif name == "setpref":
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                display_error("Usage: /setpref <key> <value>")
                return True, None

            key, value = parts[0], parts[1]
            memory.set_preference(key, value)
            display_success(f"Preference '{key}' set to '{value}'")
            return True, None

        # ═══════════════════════════════════════════════════════════════════════
        # Model Commands
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "model":
            if args:
                # Change model
                model_key = args.strip().lower()
                if self.agent.set_model(model_key):
                    config = AVAILABLE_MODELS[model_key]
                    display_success(f"Switched to {config.name}")
                    show_status(self.agent.model_key)
                else:
                    display_error(f"Unknown model. Use /models to see options.")
            else:
                # Show current model
                config = AVAILABLE_MODELS[self.agent.model_key]
                console.print(
                    f"\n[{COLORS['muted']}]Current model:[/] "
                    f"[bold {COLORS['secondary']}]{config.name}[/] "
                    f"[{COLORS['muted']}]({config.id})[/]\n"
                )
            return True, None

        elif name == "models":
            provider_availability = self.agent.client_manager.get_available_providers()
            print_models(self.agent.model_key, provider_availability)
            return True, None

        elif name == "providers":
            provider_availability = self.agent.client_manager.get_available_providers()
            print_providers(provider_availability)
            return True, None

        # ═══════════════════════════════════════════════════════════════════════
        # Ollama Commands
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "ollama":
            if args:
                parts = args.split(maxsplit=1)
                subcommand = parts[0].lower()
                subargs = parts[1] if len(parts) > 1 else ""

                if subcommand == "list":
                    models = self.agent.client_manager.get_ollama_models()
                    current = AVAILABLE_MODELS.get(self.agent.model_key)
                    current_id = current.id if current else None
                    print_ollama_models(models, current_id)

                elif subcommand == "use":
                    if not subargs:
                        display_error("Usage: /ollama use <model>")
                        return True, None

                    model_id = subargs.strip()
                    key = self.agent.client_manager.add_custom_ollama_model(model_id)
                    if self.agent.set_model(key):
                        display_success(f"Switched to Ollama model: {model_id}")
                        show_status(self.agent.model_key)
                    else:
                        display_error(f"Failed to switch to model: {model_id}")

                else:
                    display_error("Unknown ollama command. Use: list, use")
            else:
                # Show ollama status and models
                models = self.agent.client_manager.get_ollama_models()
                print_ollama_models(models)

            return True, None

        # ═══════════════════════════════════════════════════════════════════════
        # MCP Commands
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "mcp":
            from .mcp import mcp_manager

            if args:
                parts = args.split(maxsplit=2)
                subcommand = parts[0].lower()

                if subcommand == "list":
                    status = mcp_manager.get_server_status()
                    print_mcp_servers(status)

                elif subcommand == "tools":
                    tools = mcp_manager.get_all_tools()
                    print_mcp_tools(tools)

                elif subcommand == "add":
                    if len(parts) < 3:
                        display_error("Usage: /mcp add <name> <command>")
                        return True, None

                    name = parts[1]
                    command = parts[2]
                    if mcp_manager.add_server(name, command):
                        display_success(f"MCP server '{name}' added and connected")
                    else:
                        display_error(f"Failed to connect to MCP server")

                elif subcommand == "remove":
                    if len(parts) < 2:
                        display_error("Usage: /mcp remove <name>")
                        return True, None

                    mcp_manager.remove_server(parts[1])
                    display_success(f"MCP server '{parts[1]}' removed")

                elif subcommand == "connect":
                    mcp_manager.connect_all()
                    display_success("Connected to all enabled MCP servers")

                elif subcommand == "disconnect":
                    mcp_manager.disconnect_all()
                    display_success("Disconnected from all MCP servers")

                else:
                    display_error("Unknown mcp command. Use: list, tools, add, remove, connect, disconnect")
            else:
                status = mcp_manager.get_server_status()
                print_mcp_servers(status)

            return True, None

        # ═══════════════════════════════════════════════════════════════════════
        # History Commands
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "resume" or name == "history":
            from .history import history_manager

            if name == "resume" and args:
                # Resume specific conversation
                conv_id = args.strip()
                if self.agent.load_conversation(conv_id):
                    conv = history_manager.get_current_conversation()
                    title = conv.get("title", "Untitled") if conv else "Untitled"
                    display_success(f"Conversation resumed: {title}")
                    show_status(self.agent.model_key)
                else:
                    display_error("Conversation not found.")
            else:
                # Show conversations
                conversations = history_manager.get_recent_conversations(10)
                print_conversations(conversations)
            return True, None

        # ═══════════════════════════════════════════════════════════════════════
        # System Commands
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "queue":
            if self.queue_manager:
                self.queue_manager.show_queue_status()
            else:
                display_info("Queue system not available.")
            return True, None

        elif name == "clearqueue":
            if self.queue_manager:
                self.queue_manager.clear_queue()
                display_success("Queue cleared.")
            return True, None

        elif name == "status":
            show_status(self.agent.model_key)

            # Show agent status if available
            if self.agent_manager:
                self.agent_manager.display_status()

            # Show queue status
            if self.queue_manager and self.queue_manager.has_pending_messages():
                console.print(
                    f"[{COLORS['warning']}]📥 {self.queue_manager.get_queue_size()} messages in queue[/]"
                )

            return True, None

        elif name == "debug":
            display_info("Debug mode toggled")
            return True, None

        # Unknown command
        display_error(f"Unknown command: /{command.name}")
        return True, None
