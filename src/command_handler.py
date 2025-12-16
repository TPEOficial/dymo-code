"""
Command Handler for Dymo Code
Handles all slash commands and their execution
"""

import webbrowser
from typing import Optional, Tuple, Any

from rich.console import Console
from rich.table import Table
from rich.box import ROUNDED

from .config import COLORS, AVAILABLE_MODELS
from .commands import parse_command, Command, CommandCategory, get_commands_by_category, CATEGORY_ICONS, CATEGORY_NAMES
from .memory import memory
from .storage import user_config
from .lib.prompts import mode_manager, MODE_CONFIGS, AgentMode
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
# Provider API Key URLs
# ═══════════════════════════════════════════════════════════════════════════════

PROVIDER_API_KEY_URLS = {
    "groq": {
        "name": "Groq",
        "url": "https://console.groq.com/keys",
        "description": "Fast inference API for LLMs"
    },
    "openrouter": {
        "name": "OpenRouter",
        "url": "https://openrouter.ai/keys",
        "description": "Access to multiple AI models"
    },
    "anthropic": {
        "name": "Anthropic",
        "url": "https://console.anthropic.com/settings/keys",
        "description": "Claude models API"
    },
    "openai": {
        "name": "OpenAI",
        "url": "https://platform.openai.com/api-keys",
        "description": "GPT models API"
    }
}


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
            if cmd.has_args and cmd.arg_hint: usage += f" <{cmd.arg_hint}>"

            aliases = ""
            if cmd.aliases: aliases = f" ({', '.join('/' + a for a in cmd.aliases)})"

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

        elif name == "version":
            from .main import get_version, get_remote_version
            local_version = get_version()
            console.print(f"\n[bold {COLORS['primary']}]Dymo Code[/]")
            console.print(f"[{COLORS['muted']}]https://github.com/TPEOficial/dymo-code[/]\n")
            console.print(f"  [bold]Local version:[/]  v{local_version}")

            # Fetch remote version
            console.print(f"  [{COLORS['muted']}]Checking remote...[/]", end="\r")
            remote_version = get_remote_version()

            if remote_version:
                if remote_version != local_version:
                    console.print(f"  [bold]Remote version:[/] v{remote_version} [{COLORS['warning']}](update available)[/]")
                    console.print(f"\n  [{COLORS['muted']}]Download: https://github.com/TPEOficial/dymo-code/releases[/]")
                else:
                    console.print(f"  [bold]Remote version:[/] v{remote_version} [{COLORS['success']}](up to date)[/]    ")
            else:
                console.print(f"  [bold]Remote version:[/] [{COLORS['error']}]Could not fetch[/]              ")

            console.print()
            return True, None

        elif name == "update":
            from .main import perform_auto_update
            if perform_auto_update():
                console.print(f"\n[{COLORS['warning']}]Please restart Dymo Code to apply the update.[/]\n")
            return True, None

        elif name == "clear":
            self.agent.clear_history()
            if self.queue_manager: self.queue_manager.clear_queue()
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
            user_config.user_name = args
            display_success(f"Your name has been saved as: {args}")
            return True, None

        elif name == "forget":
            if not args:
                display_error("Usage: /forget <id>")
                return True, None

            try:
                fact_id = int(args)
                if memory.delete_fact(fact_id): display_success(f"Fact #{fact_id} deleted.")
                else: display_error(f"Fact #{fact_id} not found")
            except ValueError: display_error("ID must be a number.")
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
                else: display_error(f"Unknown model. Use /models to see options.")
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

        elif name == "mode":
            if args:
                # Change mode
                mode_name = args.strip().lower()
                if mode_manager.set_mode_by_name(mode_name):
                    config = mode_manager.current_config
                    # Apply mode to agent
                    self.agent.apply_mode(mode_manager.get_mode_prompt())
                    display_success(f"Switched to {config.icon} {config.display_name} mode")
                    show_status(self.agent.model_key)
                else:
                    display_error(f"Unknown mode. Use /modes to see options.")
            else:
                # Show current mode
                config = mode_manager.current_config
                console.print(
                    f"\n[{COLORS['muted']}]Current mode:[/] "
                    f"[bold {COLORS['secondary']}]{config.icon} {config.display_name}[/] "
                    f"[{COLORS['muted']}]({config.description})[/]\n"
                )
            return True, None

        elif name == "modes":
            console.print(f"\n[bold {COLORS['secondary']}]Available Agent Modes[/]\n")

            table = Table(box=ROUNDED, header_style=f"bold {COLORS['muted']}")
            table.add_column("Mode", style=f"{COLORS['accent']}", width=15)
            table.add_column("Description", style="white")
            table.add_column("Status", width=10)

            current = mode_manager.current_mode
            for mode, config in MODE_CONFIGS.items():
                status = f"[{COLORS['success']}]Active[/]" if mode == current else ""
                table.add_row(
                    f"{config.icon} {config.display_name}",
                    config.description,
                    status
                )

            console.print(table)
            console.print(f"\n[{COLORS['muted']}]Use /mode <name> to switch modes[/]\n")
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
                    else: display_error(f"Failed to switch to model: {model_id}")

                else: display_error("Unknown ollama command. Use: list, use")
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

                else: display_error("Unknown mcp command. Use: list, tools, add, remove, connect, disconnect")
            else:
                status = mcp_manager.get_server_status()
                print_mcp_servers(status)

            return True, None

        # ═══════════════════════════════════════════════════════════════════════
        # API Keys Commands
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "setapikey":
            if not args:
                display_error("Usage: /setapikey <provider> <key>")
                console.print(f"[{COLORS['muted']}]Providers: groq, openrouter, anthropic, openai[/]")
                return True, None

            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                display_error("Usage: /setapikey <provider> <key>")
                return True, None

            provider = parts[0].lower()
            api_key = parts[1].strip()

            valid_providers = ["groq", "openrouter", "anthropic", "openai"]
            if provider not in valid_providers:
                display_error(f"Invalid provider. Use: {', '.join(valid_providers)}")
                return True, None

            user_config.set_api_key(provider, api_key)
            # Also set in current environment so it takes effect immediately
            import os
            os.environ[f"{provider.upper()}_API_KEY"] = api_key
            display_success(f"API key for {provider.upper()} saved successfully")
            return True, None

        elif name == "apikeys":
            keys = user_config.get_all_api_keys()
            if not keys:
                display_info("No API keys configured. Use /setapikey <provider> <key>")
            else:
                console.print(f"\n[bold {COLORS['secondary']}]Configured API Keys[/]\n")
                for key_name, masked_value in keys.items():
                    provider = key_name.replace("_API_KEY", "")
                    console.print(f"  [{COLORS['accent']}]{provider}[/]: {masked_value}")
                console.print()
            return True, None

        elif name == "delapikey":
            if not args:
                display_error("Usage: /delapikey <provider>")
                return True, None

            provider = args.strip().lower()
            valid_providers = ["groq", "openrouter", "anthropic", "openai"]
            if provider not in valid_providers:
                display_error(f"Invalid provider. Use: {', '.join(valid_providers)}")
                return True, None

            user_config.delete_api_key(provider)
            # Also remove from current environment
            import os
            key_name = f"{provider.upper()}_API_KEY"
            if key_name in os.environ:
                del os.environ[key_name]
            display_success(f"API key for {provider.upper()} deleted")
            return True, None

        elif name == "getapikey":
            valid_providers = list(PROVIDER_API_KEY_URLS.keys())

            if not args:
                # Show all providers with their URLs
                console.print(f"\n[bold {COLORS['secondary']}]Available Providers[/]\n")
                for provider, info in PROVIDER_API_KEY_URLS.items():
                    console.print(f"  [{COLORS['accent']}]{provider}[/] - {info['description']}")
                    console.print(f"    [{COLORS['muted']}]{info['url']}[/]")
                console.print(f"\n[{COLORS['muted']}]Usage: /getapikey <provider>[/]\n")
                return True, None

            provider = args.strip().lower()
            if provider not in valid_providers:
                display_error(f"Invalid provider. Use: {', '.join(valid_providers)}")
                return True, None

            provider_info = PROVIDER_API_KEY_URLS[provider]

            # Show provider info
            console.print(f"\n[bold {COLORS['secondary']}]{provider_info['name']} API Key[/]\n")
            console.print(f"  [{COLORS['muted']}]{provider_info['description']}[/]")
            console.print(f"  URL: [{COLORS['accent']}]{provider_info['url']}[/]\n")

            # Ask to open browser
            console.print(f"[{COLORS['primary']}]Press Enter to open the URL in your browser, or Ctrl+C to cancel[/]")

            try:
                input()
                webbrowser.open(provider_info['url'])
                console.print(f"[{COLORS['success']}]Browser opened![/]\n")

                # Wait for API key input
                console.print(f"[{COLORS['primary']}]Paste your API key below (Ctrl+C to cancel):[/]")
                console.print(f"[{COLORS['muted']}]Your key will be saved securely[/]\n")

                api_key = input(f"  {provider_info['name']} API Key: ").strip()

                if api_key:
                    user_config.set_api_key(provider, api_key)
                    os.environ[f"{provider.upper()}_API_KEY"] = api_key
                    display_success(f"API key for {provider.upper()} saved successfully!")
                else:
                    display_info("No API key provided. Operation cancelled.")

            except KeyboardInterrupt:
                console.print(f"\n[{COLORS['muted']}]Cancelled.[/]\n")
            except EOFError:
                console.print(f"\n[{COLORS['muted']}]Cancelled.[/]\n")

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

        elif name == "context":
            from .context_manager import context_manager
            state = context_manager.get_state(self.agent.messages, self.agent.model_key)

            console.print(f"\n[bold {COLORS['secondary']}]Context Status[/]\n")

            # Progress bar visual
            bar_width = 40
            filled = int(bar_width * state.usage_percent)
            bar = "█" * filled + "░" * (bar_width - filled)

            # Color based on usage
            if state.usage_percent >= 0.8:
                bar_color = COLORS['error']
            elif state.usage_percent >= 0.6:
                bar_color = COLORS['warning']
            else:
                bar_color = COLORS['success']

            console.print(f"  [{bar_color}]{bar}[/] {state.usage_percent:.1%}")
            console.print(f"\n  [bold]Tokens:[/] ~{state.total_tokens:,} / {state.max_tokens:,}")
            console.print(f"  [bold]Messages:[/] {state.message_count}")
            console.print(f"  [bold]Summary active:[/] {'Yes' if state.summary_active else 'No'}")

            if state.needs_compression:
                console.print(f"\n  [{COLORS['warning']}]Context will be compressed on next message[/]")
            console.print()
            return True, None

        # Unknown command
        display_error(f"Unknown command: /{command.name}")
        return True, None
