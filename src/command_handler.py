"""
Command Handler for Dymo Code
Handles all slash commands and their execution
"""

import os
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

            # Check if it looks like a command (starts with /)
            if user_input.strip().startswith("/"):
                # Extract the attempted command name
                parts = user_input.strip()[1:].split(maxsplit=1)
                if parts:
                    attempted_cmd = parts[0]
                    cmd_args = parts[1] if len(parts) > 1 else ""
                    from .commands import get_similar_commands, get_command
                    from difflib import SequenceMatcher

                    suggestions = get_similar_commands(attempted_cmd)

                    if suggestions:
                        # Check if the best match is very similar (likely a typo)
                        best_match = suggestions[0]
                        similarity = SequenceMatcher(None, attempted_cmd.lower(), best_match.lower()).ratio()

                        # If similarity is high (> 0.7), auto-correct and execute
                        if similarity > 0.7:
                            console.print(f"[{COLORS['muted']}]  Auto-correcting: /{attempted_cmd} → /{best_match}[/]")
                            corrected_cmd = get_command(best_match)
                            if corrected_cmd:
                                return self._execute_command(corrected_cmd, cmd_args)

                        # Otherwise show suggestions
                        display_error(f"Unknown command: /{attempted_cmd}")
                        if len(suggestions) == 1:
                            console.print(f"[{COLORS['muted']}]  Did you mean: [bold]/{suggestions[0]}[/bold]?[/]")
                        else:
                            formatted = ", ".join([f"[bold]/{s}[/bold]" for s in suggestions])
                            console.print(f"[{COLORS['muted']}]  Did you mean: {formatted}?[/]")
                    else:
                        display_error(f"Unknown command: /{attempted_cmd}")
                        console.print(f"[{COLORS['muted']}]  Type [bold]/[/bold] to see available commands.[/]")
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
            from .main import get_version, get_remote_version, _is_newer_version
            local_version = get_version()
            console.print(f"\n[bold {COLORS['primary']}]Dymo Code[/]")
            console.print(f"[{COLORS['muted']}]https://github.com/TPEOficial/dymo-code[/]\n")
            console.print(f"  [bold]Local version:[/]  v{local_version}")

            # Fetch remote version
            console.print(f"  [{COLORS['muted']}]Checking remote...[/]", end="\r")
            remote_version = get_remote_version()

            if remote_version:
                if _is_newer_version(remote_version, local_version):
                    console.print(f"  [bold]Remote version:[/] v{remote_version} [{COLORS['warning']}](update available)[/]")
                    console.print(f"\n  [{COLORS['muted']}]Download: https://github.com/TPEOficial/dymo-code/releases[/]")
                elif remote_version == local_version:
                    console.print(f"  [bold]Remote version:[/] v{remote_version} [{COLORS['success']}](up to date)[/]    ")
                else:
                    console.print(f"  [bold]Remote version:[/] v{remote_version} [{COLORS['secondary']}](you have a newer version)[/]")
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
            # Try enhanced selector first
            try:
                from .enhanced_selector import model_selector
                selected = model_selector.show_models(self.agent.model_key)
                if selected:
                    if self.agent.set_model(selected):
                        config = AVAILABLE_MODELS[selected]
                        display_success(f"Switched to {config.name}")
                        show_status(self.agent.model_key)
                    else:
                        display_error(f"Could not switch to model: {selected}")
            except ImportError:
                # Fallback to table view
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
        # API Keys Commands (Multi-Key Support)
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "setapikey":
            from .lib.providers import API_KEY_PROVIDERS, get_providers_string, is_valid_provider

            if not args:
                display_error("Usage: /setapikey <provider> <key> [--name \"friendly name\"]")
                console.print(f"[{COLORS['muted']}]Providers: {get_providers_string()}[/]")
                console.print(f"[{COLORS['muted']}]You can add multiple keys per provider for auto-rotation[/]")
                console.print(f"[{COLORS['muted']}]Optional: Add --name to label your keys (e.g., --name \"Personal\")[/]")
                return True, None

            # Parse args for optional --name parameter
            key_name = None
            if "--name" in args:
                import re
                # Match --name "value" or --name 'value' or --name value
                name_match = re.search(r'--name\s+["\']([^"\']+)["\']|--name\s+(\S+)', args)
                if name_match:
                    key_name = name_match.group(1) or name_match.group(2)
                    # Remove the --name part from args
                    args = re.sub(r'--name\s+["\'][^"\']+["\']|--name\s+\S+', '', args).strip()

            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                display_error("Usage: /setapikey <provider> <key> [--name \"friendly name\"]")
                return True, None

            provider = parts[0].lower()
            api_key = parts[1].strip()

            if not is_valid_provider(provider):
                display_error(f"Invalid provider. Use: {get_providers_string()}")
                return True, None

            # Add key to the pool (supports multiple keys)
            added = user_config.add_api_key(provider, api_key, key_name)
            if added:
                # Also set in current environment so it takes effect immediately
                os.environ[f"{provider.upper()}_API_KEY"] = api_key
                # Update the API key manager
                from .api_key_manager import api_key_manager
                api_key_manager.add_key(provider, api_key, key_name)

                key_count = user_config.get_api_key_count(provider)
                name_info = f" as \"{key_name}\"" if key_name else ""
                display_success(f"API key for {provider.upper()} added{name_info} (total: {key_count} key{'s' if key_count > 1 else ''})")
                if key_count > 1:
                    console.print(f"[{COLORS['muted']}]Keys will auto-rotate on rate limit errors[/]")
            else:
                display_info(f"This API key already exists for {provider.upper()}")
            return True, None

        elif name == "renameapikey":
            from .lib.providers import get_providers_string, is_valid_provider

            if not args:
                display_error("Usage: /renameapikey <provider> <index> <name>")
                console.print(f"[{COLORS['muted']}]Example: /renameapikey groq 1 \"Personal Key\"[/]")
                return True, None

            parts = args.split(maxsplit=2)
            if len(parts) < 3:
                display_error("Usage: /renameapikey <provider> <index> <name>")
                return True, None

            provider = parts[0].lower()
            if not is_valid_provider(provider):
                display_error(f"Invalid provider. Use: {get_providers_string()}")
                return True, None

            try:
                index = int(parts[1]) - 1  # Convert to 0-based index
                new_name = parts[2].strip().strip('"\'')

                # Get the key at this index
                keys = user_config.get_api_keys_list(provider)
                if index < 0 or index >= len(keys):
                    display_error(f"Invalid key index. Use /apikeys to see available keys.")
                    return True, None

                # Get the actual key
                key_data = keys[index]
                if isinstance(key_data, dict):
                    actual_key = key_data.get("key", "")
                else:
                    actual_key = key_data

                # Update the name in the manager
                from .api_key_manager import api_key_manager
                if api_key_manager.update_key_name(provider, actual_key, new_name):
                    display_success(f"API key #{index+1} for {provider.upper()} renamed to \"{new_name}\"")
                else:
                    display_error(f"Failed to rename key")
            except ValueError:
                display_error("Invalid index. Use a number (e.g., /renameapikey groq 1 \"My Key\")")

            return True, None

        elif name == "apikeys":
            from .api_key_manager import api_key_manager
            providers_info = user_config.get_all_providers_keys_info()

            has_keys = any(info['count'] > 0 for info in providers_info.values())

            if not has_keys:
                display_info("No API keys configured. Use /setapikey <provider> <key>")
                console.print(f"[{COLORS['muted']}]You can add multiple keys per provider for auto-rotation on rate limits[/]\n")
            else:
                console.print(f"\n[bold {COLORS['secondary']}]Configured API Keys (Multi-Key Pool)[/]\n")

                for provider, info in providers_info.items():
                    if info['count'] > 0:
                        # Get detailed info from key manager
                        manager_info = api_key_manager.get_provider_info(provider)
                        status_icon = "[green]●[/]" if manager_info.get('has_available') else "[red]●[/]"

                        console.print(f"  {status_icon} [{COLORS['accent']}]{provider.upper()}[/] ({info['count']} key{'s' if info['count'] > 1 else ''})")

                        # Show individual keys with status
                        keys_detail = manager_info.get('keys', [])
                        for i, key_info in enumerate(keys_detail):
                            current = " [cyan]◀ active[/]" if key_info.get('is_current') else ""
                            status = key_info.get('status', 'unknown')
                            status_color = {
                                'active': 'green',
                                'rate_limited': 'yellow',
                                'exhausted': 'red',
                                'invalid': 'red',
                                'cooldown': 'yellow'
                            }.get(status, 'white')

                            masked = key_info.get('masked_key', '****')
                            key_name = key_info.get('name')

                            # Show name if available, otherwise just masked key
                            if key_name:
                                display_text = f"\"{key_name}\" ({masked})"
                            else:
                                display_text = masked

                            console.print(f"      [{i+1}] {display_text} [{status_color}]({status})[/]{current}")

                        console.print()

                console.print(f"[{COLORS['muted']}]Keys auto-rotate on rate limit or credit errors[/]")
                console.print(f"[{COLORS['muted']}]Rename keys with: /renameapikey <provider> <index> <name>[/]")
                console.print(f"[{COLORS['muted']}]Delete keys with: /delapikey <provider> <index>[/]\n")
            return True, None

        elif name == "delapikey":
            if not args:
                display_error("Usage: /delapikey <provider> [index]")
                console.print(f"[{COLORS['muted']}]Use /apikeys to see key indices[/]")
                return True, None

            from .lib.providers import get_providers_string, is_valid_provider

            parts = args.strip().split()
            provider = parts[0].lower()

            if not is_valid_provider(provider):
                display_error(f"Invalid provider. Use: {get_providers_string()}")
                return True, None

            # Check if index is provided
            if len(parts) >= 2:
                try:
                    index = int(parts[1]) - 1  # Convert to 0-based index
                    if user_config.remove_api_key_by_index(provider, index):
                        display_success(f"API key #{index+1} for {provider.upper()} deleted")
                        # Update environment if needed
                        remaining_keys = user_config.get_api_keys_list(provider)
                        key_name = f"{provider.upper()}_API_KEY"
                        if remaining_keys:
                            os.environ[key_name] = remaining_keys[0]
                        elif key_name in os.environ:
                            del os.environ[key_name]
                    else:
                        display_error(f"Invalid key index. Use /apikeys to see available keys.")
                except ValueError:
                    display_error("Invalid index. Use a number (e.g., /delapikey groq 1)")
            else:
                # No index - delete all keys for provider
                user_config.delete_api_key(provider)
                key_name = f"{provider.upper()}_API_KEY"
                if key_name in os.environ:
                    del os.environ[key_name]
                display_success(f"All API keys for {provider.upper()} deleted")

            return True, None

        elif name == "keypool":
            from .api_key_manager import api_key_manager, RotationStrategy, model_fallback_manager

            if not args:
                # Show status
                console.print(f"\n[bold {COLORS['secondary']}]Multi-Key Pool Configuration[/]\n")

                # Rotation strategy
                strategy = user_config.get_rotation_strategy()
                strategy_display = "Sequential (use until limit)" if strategy == "sequential" else "Load Balancer (round-robin)"
                console.print(f"  [bold]Rotation Strategy:[/] [{COLORS['accent']}]{strategy_display}[/]")

                # Model fallback
                fallback_enabled = user_config.is_model_fallback_enabled()
                fallback_status = f"[{COLORS['success']}]Enabled[/]" if fallback_enabled else f"[{COLORS['muted']}]Disabled[/]"
                console.print(f"  [bold]Model Fallback:[/] {fallback_status}")

                # Show current fallback state if active
                if fallback_enabled:
                    fallback_info = model_fallback_manager.get_fallback_status()
                    if fallback_info.get('active_fallbacks'):
                        console.print(f"\n  [{COLORS['warning']}]Active Fallbacks:[/]")
                        for provider, info in fallback_info['active_fallbacks'].items():
                            console.print(f"    • {provider}: {info['original']} → {info['current']}")

                console.print(f"\n[{COLORS['muted']}]Commands:[/]")
                console.print(f"  /keypool sequential   - Use each key until rate limited")
                console.print(f"  /keypool loadbalancer - Distribute requests across keys")
                console.print(f"  /keypool fallback on  - Enable model fallback on rate limit")
                console.print(f"  /keypool fallback off - Disable model fallback")
                console.print()
                return True, None

            parts = args.strip().lower().split()
            subcommand = parts[0]

            if subcommand == "sequential":
                user_config.set_rotation_strategy("sequential")
                api_key_manager.set_rotation_strategy(RotationStrategy.SEQUENTIAL)
                display_success("Rotation strategy set to Sequential (use each key until rate limited)")

            elif subcommand in ["loadbalancer", "load-balancer", "lb"]:
                user_config.set_rotation_strategy("load_balancer")
                api_key_manager.set_rotation_strategy(RotationStrategy.LOAD_BALANCER)
                display_success("Rotation strategy set to Load Balancer (round-robin distribution)")

            elif subcommand == "fallback":
                if len(parts) < 2:
                    display_error("Usage: /keypool fallback <on|off>")
                    return True, None

                if parts[1] in ["on", "enable", "yes", "true"]:
                    user_config.set_model_fallback_enabled(True)
                    model_fallback_manager.set_enabled(True)
                    display_success("Model fallback enabled - will use simpler models when rate limited")
                elif parts[1] in ["off", "disable", "no", "false"]:
                    user_config.set_model_fallback_enabled(False)
                    model_fallback_manager.set_enabled(False)
                    display_success("Model fallback disabled")
                else:
                    display_error("Usage: /keypool fallback <on|off>")

            elif subcommand == "reset":
                # Reset all fallback states
                model_fallback_manager.reset_all_fallbacks()
                display_success("All model fallbacks have been reset to original models")

            else:
                display_error(f"Unknown keypool command: {subcommand}")
                console.print(f"[{COLORS['muted']}]Use /keypool to see available options[/]")

            return True, None

        elif name == "urlverify":
            from .web_tools import (
                set_url_verification,
                is_url_verification_enabled,
                is_url_verification_available
            )

            args_lower = args.strip().lower() if args else ""

            if args_lower in ("on", "enable", "true", "1"):
                if not is_url_verification_available():
                    display_error("Dymo API key not configured.")
                    console.print(f"[{COLORS['muted']}]Set it with: /setapikey dymo <key>[/]")
                    return True, None
                set_url_verification(True)
                display_success("URL verification enabled")

            elif args_lower in ("off", "disable", "false", "0"):
                set_url_verification(False)
                display_success("URL verification disabled")

            elif args_lower in ("status", ""):
                available = is_url_verification_available()
                enabled = is_url_verification_enabled()

                console.print(f"\n[bold {COLORS['secondary']}]URL Verification (Dymo API)[/]\n")

                if not available:
                    console.print(f"  [{COLORS['muted']}]Status: Not available (no Dymo API key)[/]")
                    console.print(f"\n[{COLORS['muted']}]Set API key with: /setapikey dymo <key>[/]")
                else:
                    status = "Enabled" if enabled else "Disabled"
                    status_color = COLORS['success'] if enabled else COLORS['muted']
                    console.print(f"  Status: [{status_color}]{status}[/]")
                    console.print(f"\n[{COLORS['muted']}]Commands:[/]")
                    console.print(f"  /urlverify on  - Enable URL verification")
                    console.print(f"  /urlverify off - Disable URL verification")

                console.print()

            else:
                display_error("Usage: /urlverify [on|off|status]")

            return True, None

        elif name == "getapikey":
            from .lib.providers import (
                API_KEY_PROVIDERS, PROVIDERS, get_provider,
                get_provider_name, get_provider_url, get_provider_description
            )

            if not args:
                # Show all providers with their URLs
                console.print(f"\n[bold {COLORS['secondary']}]Available Providers[/]\n")
                for provider_id in API_KEY_PROVIDERS:
                    provider_info = get_provider(provider_id)
                    console.print(f"  [{COLORS['accent']}]{provider_id}[/] - {provider_info.description}")
                    console.print(f"    [{COLORS['muted']}]{provider_info.api_key_url}[/]")
                console.print(f"\n[{COLORS['muted']}]Usage: /getapikey <provider>[/]\n")
                return True, None

            provider = args.strip().lower()
            if provider not in API_KEY_PROVIDERS:
                display_error(f"Invalid provider. Use: {', '.join(API_KEY_PROVIDERS)}")
                return True, None

            provider_info = get_provider(provider)

            # Show provider info
            console.print(f"\n[bold {COLORS['secondary']}]{provider_info.name} API Key[/]\n")
            console.print(f"  [{COLORS['muted']}]{provider_info.description}[/]")
            console.print(f"  URL: [{COLORS['accent']}]{provider_info.api_key_url}[/]\n")

            # Ask to open browser
            console.print(f"[{COLORS['primary']}]Press Enter to open the URL in your browser, or Ctrl+C to cancel[/]")

            try:
                input()
                webbrowser.open(provider_info.api_key_url)
                console.print(f"[{COLORS['success']}]Browser opened![/]\n")

                # Wait for API key input
                console.print(f"[{COLORS['primary']}]Paste your API key below (Ctrl+C to cancel):[/]")
                console.print(f"[{COLORS['muted']}]Your key will be saved securely[/]\n")

                api_key = input(f"  {provider_info.name} API Key: ").strip()

                if api_key:
                    # Add to multi-key pool
                    added = user_config.add_api_key(provider, api_key)
                    os.environ[provider_info.env_key] = api_key

                    # Update the API key manager
                    from .api_key_manager import api_key_manager
                    api_key_manager.add_key(provider, api_key)

                    if added:
                        key_count = user_config.get_api_key_count(provider)
                        display_success(f"API key for {provider_info.name} added (total: {key_count} key{'s' if key_count > 1 else ''})")
                    else:
                        display_info(f"This API key already exists for {provider_info.name}")
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
                # Check if it's a number (shortcut)
                try:
                    idx = int(args.strip()) - 1
                    conversations = history_manager.get_recent_conversations(10)
                    if 0 <= idx < len(conversations):
                        conv_id = conversations[idx].get("id", "")
                    else:
                        display_error("Invalid session number.")
                        return True, None
                except ValueError:
                    conv_id = args.strip()

                # Resume specific conversation
                if self.agent.load_conversation(conv_id):
                    conv = history_manager.get_current_conversation()
                    title = conv.get("title", "Untitled") if conv else "Untitled"
                    display_success(f"Conversation resumed: {title}")
                    show_status(self.agent.model_key)
                else:
                    display_error("Conversation not found.")

            elif name == "history" and args:
                # Parse subcommands: delete, rename
                parts = args.strip().split(maxsplit=2)
                subcommand = parts[0].lower() if parts else ""

                if subcommand == "delete" or subcommand == "del" or subcommand == "rm":
                    if len(parts) < 2:
                        display_error("Usage: /history delete <id or number>")
                        return True, None

                    target = parts[1]
                    # Check if it's a number
                    try:
                        idx = int(target) - 1
                        conversations = history_manager.get_recent_conversations(30)
                        if 0 <= idx < len(conversations):
                            conv_id = conversations[idx].get("id", "")
                            conv_title = conversations[idx].get("title", "Untitled")
                        else:
                            display_error("Invalid conversation number.")
                            return True, None
                    except ValueError:
                        conv_id = target
                        conv = history_manager.get_conversation(conv_id)
                        conv_title = conv.get("title", "Untitled") if conv else "Unknown"

                    if history_manager.delete_conversation(conv_id):
                        display_success(f"Deleted: {conv_title}")
                    else:
                        display_error("Conversation not found.")

                elif subcommand == "rename" or subcommand == "mv":
                    if len(parts) < 3:
                        display_error("Usage: /history rename <id or number> <new name>")
                        return True, None

                    target = parts[1]
                    new_name = parts[2]

                    # Check if it's a number
                    try:
                        idx = int(target) - 1
                        conversations = history_manager.get_recent_conversations(30)
                        if 0 <= idx < len(conversations):
                            conv_id = conversations[idx].get("id", "")
                        else:
                            display_error("Invalid conversation number.")
                            return True, None
                    except ValueError:
                        conv_id = target

                    if history_manager.rename_conversation(conv_id, new_name):
                        display_success(f"Renamed to: {new_name}")
                    else:
                        display_error("Conversation not found.")

                else:
                    # Unknown subcommand, show help
                    console.print(f"\n[bold {COLORS['secondary']}]History Commands[/]\n")
                    console.print(f"  [bold]/history[/]                    - List recent conversations")
                    console.print(f"  [bold]/history delete <n>[/]        - Delete conversation by number or ID")
                    console.print(f"  [bold]/history rename <n> <name>[/] - Rename conversation")
                    console.print(f"\n[{COLORS['muted']}]Aliases: delete=del=rm, rename=mv[/]\n")

            else:
                # Show conversations
                conversations = history_manager.get_recent_conversations(10)
                print_conversations(conversations)
            return True, None

        elif name == "sessions":
            try:
                from .session_manager import session_manager

                limit = 10
                if args:
                    try:
                        limit = int(args.strip())
                    except ValueError:
                        pass

                session_manager.list_sessions(limit=limit, show_preview=True)
            except ImportError:
                # Fallback to history
                from .history import history_manager
                conversations = history_manager.get_recent_conversations(10)
                print_conversations(conversations)
            return True, None

        elif name == "last":
            try:
                from .session_manager import session_manager
                from .history import history_manager

                conv_id = session_manager.quick_resume_last()
                if conv_id:
                    if self.agent.load_conversation(conv_id):
                        conv = history_manager.get_current_conversation()
                        title = conv.get("title", "Untitled") if conv else "Untitled"
                        display_success(f"Resumed: {title}")
                        show_status(self.agent.model_key)
                    else:
                        display_error("Failed to resume session.")
            except ImportError:
                display_error("Session manager not available.")
            return True, None

        elif name == "search":
            if not args:
                display_error("Usage: /search <query>")
                return True, None

            try:
                from .session_manager import session_manager
                session_manager.show_search_results(args.strip())
            except ImportError:
                display_error("Session manager not available.")
            return True, None

        elif name == "export":
            try:
                from .session_manager import session_exporter
                from .history import history_manager

                conv = history_manager.get_current_conversation()
                if not conv:
                    display_error("No active session to export.")
                    return True, None

                conv_id = conv.get("id", "")
                filename = args.strip() if args else f"session_{conv_id[:8]}.md"

                if not filename.endswith(".md"):
                    filename += ".md"

                if session_exporter.save_to_file(conv_id, filename):
                    display_success(f"Session exported to: {filename}")
                else:
                    display_error("Failed to export session.")
            except ImportError:
                display_error("Session exporter not available.")
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

        # ═══════════════════════════════════════════════════════════════════════
        # Theme Commands
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "theme":
            try:
                from .themes import theme_manager
                from .command_palette import quick_actions

                if args:
                    # Set theme directly
                    theme_name = args.strip().lower()
                    if theme_manager.set_theme(theme_name):
                        theme = theme_manager.current_theme
                        display_success(f"Theme changed to: {theme.display_name}")
                    else:
                        display_error(f"Unknown theme. Use /themes to see options.")
                else:
                    # Show theme picker
                    selected = quick_actions.show_theme_picker(theme_manager.current_theme_name)
                    if selected:
                        if theme_manager.set_theme(selected):
                            theme = theme_manager.current_theme
                            display_success(f"Theme changed to: {theme.display_name}")
            except ImportError:
                display_error("Theme system not available.")
            return True, None

        elif name == "themes":
            try:
                from .themes import theme_manager

                # Try enhanced selector
                try:
                    from .enhanced_selector import theme_selector
                    selected = theme_selector.show_themes(theme_manager.current_theme_name)
                    if selected:
                        if theme_manager.set_theme(selected):
                            theme = theme_manager.current_theme
                            display_success(f"Theme changed to: {theme.display_name}")
                except ImportError:
                    # Fallback to table view
                    console.print(f"\n[bold {COLORS['secondary']}]Available Themes[/]\n")

                    table = Table(box=ROUNDED, header_style=f"bold {COLORS['muted']}")
                    table.add_column("Name", style=f"{COLORS['accent']}", width=20)
                    table.add_column("Description", style="white")
                    table.add_column("Type", width=8)
                    table.add_column("Status", width=10)

                    for theme_info in theme_manager.list_themes():
                        status = f"[{COLORS['success']}]Active[/]" if theme_info["is_current"] else ""
                        theme_type = "Dark" if theme_info["is_dark"] else "Light"
                        table.add_row(
                            theme_info["display_name"],
                            theme_info["description"],
                            theme_type,
                            status
                        )

                    console.print(table)
                    console.print(f"\n[{COLORS['muted']}]Use /theme <name> to switch themes[/]\n")
            except ImportError:
                display_error("Theme system not available.")
            return True, None

        # ═══════════════════════════════════════════════════════════════════════
        # Command Palette
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "commands":
            try:
                from .command_palette import command_palette
                result = command_palette.show()
                if result:
                    # Execute the selected command
                    return self.handle(result)
            except ImportError:
                # Fallback to enhanced help
                print_enhanced_help()
            return True, None

        # ═══════════════════════════════════════════════════════════════════════
        # Keybindings
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "keybindings":
            try:
                from .keybindings import keybind_manager

                console.print(f"\n[bold {COLORS['secondary']}]Keyboard Shortcuts[/]\n")

                table = Table(box=ROUNDED, header_style=f"bold {COLORS['muted']}")
                table.add_column("Shortcut", style=f"{COLORS['accent']}", width=15)
                table.add_column("Command", style=f"{COLORS['secondary']}", width=15)
                table.add_column("Description", style="white")

                for kb in keybind_manager.list_keybindings():
                    if kb["enabled"] and kb["command"]:
                        table.add_row(
                            kb["display"],
                            f"/{kb['command']}",
                            kb["description"]
                        )

                console.print(table)
                console.print()
            except ImportError:
                display_info("Keybinding system not available.")
            return True, None

        # ═══════════════════════════════════════════════════════════════════════
        # Clipboard
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "copy":
            try:
                from .terminal import copy_to_clipboard

                # Get last assistant message
                last_response = None
                for msg in reversed(self.agent.messages):
                    if msg.get("role") == "assistant":
                        last_response = msg.get("content", "")
                        break

                if last_response:
                    if copy_to_clipboard(last_response):
                        display_success("Last response copied to clipboard!")
                    else:
                        display_error("Failed to copy to clipboard.")
                else:
                    display_info("No response to copy.")
            except ImportError:
                display_error("Clipboard functionality not available.")
            return True, None

        # ═══════════════════════════════════════════════════════════════════════
        # File Explorer Commands
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "tree":
            try:
                from .file_explorer import file_explorer

                # Parse arguments: /tree [path] [depth]
                parts = args.split() if args else []
                path = parts[0] if parts else "."
                depth = 3

                if len(parts) > 1:
                    try:
                        depth = int(parts[1])
                    except ValueError:
                        pass

                file_explorer.show_tree(path, max_depth=depth)
            except ImportError:
                display_error("File explorer not available.")
            return True, None

        elif name == "browse":
            try:
                from .file_explorer import file_explorer

                start_path = args.strip() if args else "."
                selected = file_explorer.interactive_browse(start_path)

                if selected:
                    display_success(f"Selected: {selected}")
                    # Optionally preview the file
                    console.print(f"[{COLORS['muted']}]Use /preview {selected} to view contents[/]")
            except ImportError:
                display_error("File explorer not available.")
            return True, None

        elif name == "preview":
            if not args:
                display_error("Usage: /preview <file>")
                return True, None

            try:
                from .file_explorer import file_explorer
                file_explorer.preview_file(args.strip())
            except ImportError:
                display_error("File explorer not available.")
            return True, None

        elif name == "find":
            if not args:
                display_error("Usage: /find <pattern>")
                return True, None

            try:
                from .file_explorer import file_explorer

                pattern = args.strip()
                results = file_explorer.fuzzy_find(pattern)

                if results:
                    console.print(f"\n[bold {COLORS['secondary']}]Found {len(results)} files:[/]\n")
                    for i, path in enumerate(results, 1):
                        console.print(f"  [{COLORS['muted']}]{i:2}.[/] {path}")
                    console.print()
                else:
                    display_info(f"No files found matching '{pattern}'")
            except ImportError:
                display_error("File explorer not available.")
            return True, None

        elif name == "setup":
            try:
                from .setup_command import setup_command, is_command_available, get_install_location

                if is_command_available():
                    location = get_install_location()
                    display_success(f"'dymo-code' command is already available at: {location}")
                else:
                    console.print(f"[{COLORS['secondary']}]Setting up 'dymo-code' command...[/]")
                    success, msg = setup_command(show_output=False)
                    if success:
                        display_success(msg)
                    else:
                        display_error(msg)
            except ImportError:
                display_error("Setup module not available.")
            return True, None

        elif name == "permissions":
            try:
                from .command_permissions import command_permissions

                action = args.strip().lower() if args else ""

                if action == "list":
                    # List all permanent permissions
                    perms = command_permissions.get_all_permanent_permissions()
                    if perms:
                        console.print(f"\n[bold {COLORS['secondary']}]Permanent Command Permissions[/]\n")
                        for cmd, status in sorted(perms.items()):
                            icon = "✓" if status == "allow" else "✗"
                            color = COLORS['success'] if status == "allow" else COLORS['error']
                            console.print(f"  [{color}]{icon}[/] {cmd} - [{color}]{status}[/]")
                        console.print()
                    else:
                        display_info("No permanent command permissions configured.")

                elif action == "clear":
                    command_permissions.clear_all_permissions()
                    display_success("All command permissions cleared.")

                elif action == "toggle":
                    enabled = command_permissions.is_enabled()
                    command_permissions.set_enabled(not enabled)
                    if not enabled:
                        display_success("Command permission system enabled.")
                    else:
                        display_info("Command permission system disabled. Commands will execute without prompts.")

                else:
                    # Show current status
                    enabled = command_permissions.is_enabled()
                    perms = command_permissions.get_all_permanent_permissions()
                    status = "enabled" if enabled else "disabled"
                    status_color = COLORS['success'] if enabled else COLORS['muted']

                    console.print(f"\n[bold {COLORS['secondary']}]Command Permission System[/]\n")
                    console.print(f"  Status: [{status_color}]{status}[/]")
                    console.print(f"  Permanent permissions: {len(perms)}")
                    console.print()
                    console.print(f"[{COLORS['muted']}]Usage:[/]")
                    console.print(f"  /permissions list   - Show all permanent permissions")
                    console.print(f"  /permissions clear  - Clear all permissions")
                    console.print(f"  /permissions toggle - Enable/disable permission prompts")
                    console.print()

            except ImportError:
                display_error("Command permissions module not available.")
            return True, None

        # ═══════════════════════════════════════════════════════════════════════
        # Multi-Agent Commands
        # ═══════════════════════════════════════════════════════════════════════

        elif name == "agents":
            try:
                from .multi_agent import agent_pool, TaskStatus

                active = agent_pool.get_active_tasks()
                if not active:
                    display_info("No active agent tasks running.")
                else:
                    console.print(f"\n[bold {COLORS['secondary']}]Active Agents ({len(active)})[/]\n")
                    for task in active:
                        status_color = COLORS['warning'] if task.status == TaskStatus.RUNNING else COLORS['muted']
                        progress = int(task.progress * 100)
                        console.print(f"  {task.status_icon} [{COLORS['accent']}]{task.id}[/] - {task.description}")
                        console.print(f"     [{status_color}]{task.status.value}[/] - {progress}% - {task.duration:.1f}s")
                    console.print()
            except ImportError:
                display_error("Multi-agent system not available.")
            return True, None

        elif name == "tasks":
            try:
                from .multi_agent import agent_pool
                agent_pool.show_tasks()
            except ImportError:
                display_error("Multi-agent system not available.")
            return True, None

        elif name == "task":
            if not args:
                display_error("Usage: /task <task_id>")
                return True, None

            try:
                from .multi_agent import agent_pool
                task_id = args.strip()
                agent_pool.show_task_result(task_id)
            except ImportError:
                display_error("Multi-agent system not available.")
            return True, None

        elif name == "cleartasks":
            try:
                from .multi_agent import agent_pool
                agent_pool.clear_completed()
                display_success("Cleared completed tasks.")
            except ImportError:
                display_error("Multi-agent system not available.")
            return True, None

        # Unknown command - try to suggest similar commands
        from .commands import get_similar_commands

        suggestions = get_similar_commands(command.name)
        if suggestions:
            display_error(f"Unknown command: /{command.name}")
            if len(suggestions) == 1:
                console.print(f"[{COLORS['muted']}]  Did you mean: [bold]/{suggestions[0]}[/bold]?[/]")
            else:
                formatted = ", ".join([f"[bold]/{s}[/bold]" for s in suggestions])
                console.print(f"[{COLORS['muted']}]  Did you mean: {formatted}?[/]")
        else:
            display_error(f"Unknown command: /{command.name}")
            console.print(f"[{COLORS['muted']}]  Type [bold]/[/bold] to see available commands.[/]")

        return True, None
