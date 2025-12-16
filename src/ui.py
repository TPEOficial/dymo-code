"""
Terminal UI components for Dymo Code
"""

import os
import sys
from typing import List, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax
from rich.box import ROUNDED, SIMPLE, DOUBLE
from rich.columns import Columns
from rich.padding import Padding

from .config import COLORS, AVAILABLE_MODELS, ModelProvider, PROVIDER_CONFIGS
from .lib.prompts import mode_manager

# ═══════════════════════════════════════════════════════════════════════════════
# Console Setup
# ═══════════════════════════════════════════════════════════════════════════════

# Fix encoding for Windows terminals
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

console = Console(force_terminal=True)

# ═══════════════════════════════════════════════════════════════════════════════
# Banner and Branding
# ═══════════════════════════════════════════════════════════════════════════════

def print_banner():
    """Print the welcome banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║    ██████╗ ██╗   ██╗███╗   ███╗ ██████╗                       ║
    ║    ██╔══██╗╚██╗ ██╔╝████╗ ████║██╔═══██╗                      ║
    ║    ██║  ██║ ╚████╔╝ ██╔████╔██║██║   ██║                      ║
    ║    ██║  ██║  ╚██╔╝  ██║╚██╔╝██║██║   ██║                      ║
    ║    ██████╔╝   ██║   ██║ ╚═╝ ██║╚██████╔╝                      ║
    ║    ╚═════╝    ╚═╝   ╚═╝     ╚═╝ ╚═════╝                       ║
    ║                                                               ║
    ║     ██████╗ ██████╗ ██████╗ ███████╗                          ║
    ║    ██╔════╝██╔═══██╗██╔══██╗██╔════╝                          ║
    ║    ██║     ██║   ██║██║  ██║█████╗                            ║
    ║    ██║     ██║   ██║██║  ██║██╔══╝                            ║
    ║    ╚██████╗╚██████╔╝██████╔╝███████╗                          ║
    ║     ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝                          ║
    ║                                                               ║
    ║           Your AI-Powered Terminal Assistant                  ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style=f"bold {COLORS['primary']}")

# ═══════════════════════════════════════════════════════════════════════════════
# Help and Information
# ═══════════════════════════════════════════════════════════════════════════════

def print_help():
    """Print available commands"""
    table = Table(
        title="Available Commands",
        box=ROUNDED,
        title_style=f"bold {COLORS['primary']}",
        header_style=f"bold {COLORS['secondary']}"
    )
    table.add_column("Command", style=f"{COLORS['accent']}")
    table.add_column("Description", style="white")

    commands = [
        ("/help", "Show this help message"),
        ("/model", "Show current model"),
        ("/model <name>", "Switch model (llama, gpt-oss)"),
        ("/models", "List all available models"),
        ("/resume", "List and resume previous conversations"),
        ("/resume <id>", "Resume a specific conversation by ID"),
        ("/queue", "Show pending messages in queue"),
        ("/clearqueue", "Clear all queued messages"),
        ("/clear", "Clear conversation history"),
        ("/exit, /quit", "Exit the agent"),
    ]

    for cmd, desc in commands:
        table.add_row(cmd, desc)

    console.print()
    console.print(table)
    console.print()

def print_models(current_model: str, provider_availability: Dict[str, Any] = None):
    """Print available models grouped by provider"""
    # Group models by provider
    models_by_provider: Dict[ModelProvider, List] = {}
    for key, config in AVAILABLE_MODELS.items():
        if config.provider not in models_by_provider: models_by_provider[config.provider] = []
        models_by_provider[config.provider].append((key, config))

    console.print()

    for provider in ModelProvider:
        if provider not in models_by_provider: continue

        models = models_by_provider[provider]
        provider_config = PROVIDER_CONFIGS.get(provider)
        provider_name = provider_config.name if provider_config else provider.value

        # Check availability
        is_available = True
        if provider_availability:
            is_available = provider_availability.get(provider, False)

        availability_icon = "[green]●[/green]" if is_available else "[red]○[/red]"

        table = Table(
            title=f"{availability_icon} {provider_name}",
            box=ROUNDED,
            title_style=f"bold {COLORS['secondary']}",
            header_style=f"bold {COLORS['muted']}",
            show_header=True
        )
        table.add_column("Key", style=f"{COLORS['accent']}", width=18)
        table.add_column("Model", style="white", width=25)
        table.add_column("Description", style=f"{COLORS['muted']}")
        table.add_column("", width=8)

        for key, config in models:
            status = "[green]● Active[/green]" if key == current_model else ""
            features = ""
            if config.supports_code_execution: features += "🐍"
            if config.supports_web_search: features += "🔍"
            if not config.supports_tools: features += "⚠️"

            table.add_row(key, config.name, config.description[:40], status)

        console.print(table)
        console.print()

    console.print(f"[{COLORS['muted']}]Use /model <key> to switch models[/]")
    console.print(f"[{COLORS['muted']}]Legend: 🐍=Code Exec, 🔍=Web Search, ⚠️=No Tools[/]")
    console.print()

def show_status(model_key: str):
    """Show current status bar"""
    config = AVAILABLE_MODELS[model_key]
    mode_config = mode_manager.current_config

    status = Text()
    status.append("Model: ", style=f"{COLORS['muted']}")
    status.append(f"{config.name}", style=f"bold {COLORS['secondary']}")
    status.append(" │ ", style=f"{COLORS['muted']}")
    status.append("Provider: ", style=f"{COLORS['muted']}")
    status.append(f"{config.provider.value}", style=f"{COLORS['accent']}")
    status.append(" │ ", style=f"{COLORS['muted']}")
    status.append("Mode: ", style=f"{COLORS['muted']}")
    status.append(f"{mode_config.icon} {mode_config.display_name}", style=f"bold {COLORS['warning']}")
    status.append(" │ ", style=f"{COLORS['muted']}")
    status.append("CWD: ", style=f"{COLORS['muted']}")
    status.append(f"{os.getcwd()}", style=f"{COLORS['success']}")

    console.print(Panel(status, box=ROUNDED, border_style=f"{COLORS['muted']}"))

# ═══════════════════════════════════════════════════════════════════════════════
# Output Display
# ═══════════════════════════════════════════════════════════════════════════════

def display_tool_call(name: str, args: dict, verbose: bool = True):
    """Display a tool call in the terminal"""
    import json

    # Skip display for folder creation (it's usually just a preparatory step)
    if name == "create_folder" and not verbose: return

    tool_text = Text()
    tool_text.append("⚡ ", style=f"{COLORS['warning']}")
    tool_text.append("Tool: ", style=f"{COLORS['muted']}")
    tool_text.append(f"{name}", style=f"bold {COLORS['accent']}")

    if args:
        args_str = json.dumps(args, indent=2)
        console.print(tool_text)
        console.print(
            Syntax(args_str, "json", theme="monokai", line_numbers=False),
            style="dim"
        )
    else:
        console.print(tool_text)

def display_tool_result(result: str, tool_name: str = None):
    """Display a tool result with diff support for file operations"""
    from .tools import get_last_file_change, clear_last_file_change

    file_change = get_last_file_change()

    # Use diff display for file operations
    if file_change and file_change.success:
        if file_change.change_type == "create":
            # New file - show all lines as additions
            display_file_creation(file_change.file_path, file_change.new_content or "")
            clear_last_file_change()
            return
        elif file_change.change_type == "modify":
            # Modified file - show unified diff
            if file_change.old_content is not None and file_change.new_content is not None:
                display_file_diff(
                    file_change.file_path,
                    file_change.old_content,
                    file_change.new_content
                )
                # Also show summary
                old_lines = len(file_change.old_content.splitlines())
                new_lines = len(file_change.new_content.splitlines())
                additions = max(0, new_lines - old_lines)
                deletions = max(0, old_lines - new_lines)
                display_edit_summary(file_change.file_path, additions, deletions)
                clear_last_file_change()
                return
        elif file_change.change_type == "read":
            # File read - show with line numbers
            if file_change.new_content:
                display_file_read(file_change.file_path, file_change.new_content)
                clear_last_file_change()
                return

    clear_last_file_change()

    # Default display for other results
    if len(result) > 500: display_result = result[:500] + "\n... (truncated)"
    else: display_result = result

    console.print(
        Panel(
            display_result,
            title="Tool Result",
            title_align="left",
            border_style=f"{COLORS['success']}",
            box=ROUNDED
        )
    )

def display_executed_tool(tool_type: str, arguments: str, output: str):
    """Display a tool that was executed by Groq's built-in system (code_interpreter, web_search)"""
    from rich.markdown import Markdown

    # Icon based on tool type
    icons = {
        "code_interpreter": "🐍",
        "browser_search": "🔍",
        "web_search": "🔍",
        "search": "🔍",
        "visit_website": "🌐",
        "browser_automation": "🤖",
        "wolfram_alpha": "📊"
    }
    icon = icons.get(tool_type, "⚙️")

    # Format the header
    header = Text()
    header.append(f"{icon} ", style=f"{COLORS['warning']}")
    header.append("Executed: ", style=f"{COLORS['muted']}")
    header.append(f"{tool_type}", style=f"bold {COLORS['accent']}")

    console.print(header)

    # Show arguments if present
    if arguments:
        try:
            import json
            args_dict = json.loads(arguments)
            args_str = json.dumps(args_dict, indent=2)
            console.print(
                Syntax(args_str, "json", theme="monokai", line_numbers=False),
                style="dim"
            )
        except: console.print(f"  [dim]{arguments}[/dim]")

    # Show output
    if output:
        # Truncate if too long
        if len(output) > 1000: display_output = output[:1000] + "\n... (truncated)"
        else: display_output = output

        console.print(
            Panel(
                display_output,
                title=f"{tool_type} Output",
                title_align="left",
                border_style=f"{COLORS['secondary']}",
                box=ROUNDED
            )
        )

def display_code_execution_result(code: str, output: str, has_error: bool = False):
    """Display code execution result with syntax highlighting"""
    from rich.markdown import Markdown

    # Show the code that was executed
    console.print()
    console.print(
        Panel(
            Syntax(code, "python", theme="monokai", line_numbers=True),
            title="🐍 Code Executed",
            title_align="left",
            border_style=f"{COLORS['accent']}",
            box=ROUNDED
        )
    )

    # Show the output
    border_color = COLORS['error'] if has_error else COLORS['success']
    title = "❌ Execution Error" if has_error else "✓ Output"

    if output:
        console.print(
            Panel(
                output,
                title=title,
                title_align="left",
                border_style=border_color,
                box=ROUNDED
            )
        )

def display_error(message: str):
    """Display an error message"""
    console.print(
        Panel(message, border_style=f"{COLORS['error']}", box=ROUNDED)
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Diff Display (Git-style with line numbers)
# ═══════════════════════════════════════════════════════════════════════════════

def display_file_diff(
    file_path: str,
    old_content: str,
    new_content: str,
    context_lines: int = 3
):
    """
    Display a git-style diff with:
    - Line numbers in gray
    - + green for additions
    - - red for deletions
    - Context lines in normal color
    """
    import difflib

    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    # Generate unified diff
    diff = list(difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm=""
    ))

    if not diff:
        console.print(f"[{COLORS['muted']}]No changes[/]")
        return

    content = Text()

    # Header
    content.append("─" * 60 + "\n", style=f"{COLORS['muted']}")

    old_line_num = 0
    new_line_num = 0

    for line in diff:
        # File headers
        if line.startswith("---"):
            content.append(line.rstrip() + "\n", style=f"bold {COLORS['error']}")
        elif line.startswith("+++"):
            content.append(line.rstrip() + "\n", style=f"bold {COLORS['success']}")
        # Hunk header (@@ -1,5 +1,6 @@)
        elif line.startswith("@@"):
            content.append(line.rstrip() + "\n", style=f"bold {COLORS['secondary']}")
            # Parse line numbers from hunk header
            import re
            match = re.match(r"@@ -(\d+)", line)
            if match:
                old_line_num = int(match.group(1)) - 1
                new_line_num = old_line_num
        # Removed line
        elif line.startswith("-"):
            old_line_num += 1
            line_num_str = f"{old_line_num:4d}"
            content.append(f"{line_num_str} ", style=f"dim {COLORS['muted']}")
            content.append("- ", style=f"bold {COLORS['error']}")
            content.append(line[1:].rstrip() + "\n", style=f"{COLORS['error']}")
        # Added line
        elif line.startswith("+"):
            new_line_num += 1
            line_num_str = f"{new_line_num:4d}"
            content.append(f"{line_num_str} ", style=f"dim {COLORS['muted']}")
            content.append("+ ", style=f"bold {COLORS['success']}")
            content.append(line[1:].rstrip() + "\n", style=f"{COLORS['success']}")
        # Context line
        else:
            old_line_num += 1
            new_line_num += 1
            line_num_str = f"{new_line_num:4d}"
            content.append(f"{line_num_str} ", style=f"dim {COLORS['muted']}")
            content.append("  ", style="white")
            content.append(line.rstrip() + "\n", style="white")

    content.append("─" * 60, style=f"{COLORS['muted']}")

    console.print(Panel(
        content,
        title=f"[bold]📝 {file_path}[/bold]",
        title_align="left",
        border_style=f"{COLORS['secondary']}",
        box=ROUNDED,
        padding=(0, 1)
    ))


def display_file_creation(file_path: str, content: str, max_lines: int = 30):
    """
    Display a new file being created with line numbers
    All lines shown as additions (+) in green
    """
    lines = content.splitlines()
    total_lines = len(lines)
    display_lines = lines[:max_lines]

    text = Text()

    # Header
    text.append("─" * 60 + "\n", style=f"{COLORS['muted']}")
    text.append(f"+++ b/{file_path}\n", style=f"bold {COLORS['success']}")
    text.append("─" * 60 + "\n", style=f"{COLORS['muted']}")

    for i, line in enumerate(display_lines, 1):
        line_num_str = f"{i:4d}"
        text.append(f"{line_num_str} ", style=f"dim {COLORS['muted']}")
        text.append("+ ", style=f"bold {COLORS['success']}")
        text.append(line + "\n", style=f"{COLORS['success']}")

    if total_lines > max_lines:
        text.append(f"\n... and {total_lines - max_lines} more lines\n", style=f"dim {COLORS['muted']}")

    text.append("─" * 60, style=f"{COLORS['muted']}")

    console.print(Panel(
        text,
        title=f"[bold]✨ New file: {file_path}[/bold]",
        title_align="left",
        border_style=f"{COLORS['success']}",
        box=ROUNDED,
        padding=(0, 1)
    ))


def display_file_deletion(file_path: str, content: str, max_lines: int = 20):
    """
    Display a file being deleted with line numbers
    All lines shown as deletions (-) in red
    """
    lines = content.splitlines()
    total_lines = len(lines)
    display_lines = lines[:max_lines]

    text = Text()

    # Header
    text.append("─" * 60 + "\n", style=f"{COLORS['muted']}")
    text.append(f"--- a/{file_path}\n", style=f"bold {COLORS['error']}")
    text.append("─" * 60 + "\n", style=f"{COLORS['muted']}")

    for i, line in enumerate(display_lines, 1):
        line_num_str = f"{i:4d}"
        text.append(f"{line_num_str} ", style=f"dim {COLORS['muted']}")
        text.append("- ", style=f"bold {COLORS['error']}")
        text.append(line + "\n", style=f"{COLORS['error']}")

    if total_lines > max_lines:
        text.append(f"\n... and {total_lines - max_lines} more lines\n", style=f"dim {COLORS['muted']}")

    text.append("─" * 60, style=f"{COLORS['muted']}")

    console.print(Panel(
        text,
        title=f"[bold]🗑️ Deleted: {file_path}[/bold]",
        title_align="left",
        border_style=f"{COLORS['error']}",
        box=ROUNDED,
        padding=(0, 1)
    ))


def display_file_read(file_path: str, content: str, start_line: int = 1, max_lines: int = 50):
    """
    Display file contents with line numbers (like a code snippet)
    """
    lines = content.splitlines()
    total_lines = len(lines)
    display_lines = lines[:max_lines]

    # Detect language from extension
    ext = file_path.split(".")[-1] if "." in file_path else ""
    lang_map = {
        "py": "python", "js": "javascript", "ts": "typescript",
        "jsx": "jsx", "tsx": "tsx", "json": "json", "md": "markdown",
        "html": "html", "css": "css", "yaml": "yaml", "yml": "yaml",
        "sh": "bash", "bash": "bash", "sql": "sql", "rs": "rust",
        "go": "go", "java": "java", "c": "c", "cpp": "cpp", "h": "c",
        "rb": "ruby", "php": "php", "swift": "swift", "kt": "kotlin"
    }
    language = lang_map.get(ext, "text")

    text = Text()

    for i, line in enumerate(display_lines, start_line):
        line_num_str = f"{i:4d}"
        text.append(f"{line_num_str} ", style=f"dim {COLORS['muted']}")
        text.append("│ ", style=f"dim {COLORS['muted']}")
        text.append(line + "\n", style="white")

    if total_lines > max_lines:
        text.append(f"\n... {total_lines - max_lines} more lines\n", style=f"dim {COLORS['muted']}")

    console.print(Panel(
        text,
        title=f"[bold]📄 {file_path}[/bold] [{COLORS['muted']}]{total_lines} lines[/]",
        title_align="left",
        border_style=f"{COLORS['secondary']}",
        box=ROUNDED,
        padding=(0, 1)
    ))


def display_inline_diff(old_text: str, new_text: str, context: str = ""):
    """
    Display an inline diff for small changes (single line or word changes)
    Shows old and new on separate lines
    """
    text = Text()

    if context:
        text.append(f"{context}\n", style=f"dim {COLORS['muted']}")

    text.append("- ", style=f"bold {COLORS['error']}")
    text.append(old_text + "\n", style=f"{COLORS['error']}")
    text.append("+ ", style=f"bold {COLORS['success']}")
    text.append(new_text, style=f"{COLORS['success']}")

    console.print(text)


def display_edit_summary(file_path: str, additions: int, deletions: int):
    """Display a summary of edits made to a file"""
    text = Text()
    text.append("📝 ", style=f"{COLORS['accent']}")
    text.append(f"{file_path} ", style="white bold")
    text.append("| ", style=f"{COLORS['muted']}")

    if additions > 0:
        text.append(f"+{additions} ", style=f"bold {COLORS['success']}")
    if deletions > 0:
        text.append(f"-{deletions}", style=f"bold {COLORS['error']}")

    console.print(text)

def display_success(message: str):
    """Display a success message"""
    console.print(f"\n[{COLORS['success']}]✓[/] {message}\n")

def display_info(message: str):
    """Display an info message"""
    console.print(f"\n[{COLORS['muted']}]{message}[/]\n")

def display_warning(message: str):
    """Display a warning message"""
    console.print(f"\n[{COLORS['warning']}]⚠[/] {message}\n")

def get_prompt_text() -> Text:
    """Get the input prompt text"""
    prompt_text = Text()
    prompt_text.append("❯ ", style=f"bold {COLORS['primary']}")
    return prompt_text

# ═══════════════════════════════════════════════════════════════════════════════
# Conversation History Display
# ═══════════════════════════════════════════════════════════════════════════════

def print_conversations(conversations: list):
    """Print a list of recent conversations"""
    if not conversations:
        console.print(f"\n[{COLORS['muted']}]No previous conversations found.[/]\n")
        return

    table = Table(
        title="Recent Conversations",
        box=ROUNDED,
        title_style=f"bold {COLORS['primary']}",
        header_style=f"bold {COLORS['secondary']}"
    )
    table.add_column("ID", style=f"{COLORS['accent']}", width=10)
    table.add_column("Title", style="white", max_width=40)
    table.add_column("Messages", style=f"{COLORS['muted']}", justify="center", width=10)
    table.add_column("Last Updated", style=f"{COLORS['muted']}", width=20)

    for conv in conversations:
        # Format the date
        updated = conv.get("updated_at", "")
        if updated:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(updated)
                updated = dt.strftime("%Y-%m-%d %H:%M")
            except:
                pass

        table.add_row(
            conv.get("id", ""),
            conv.get("title", "Untitled")[:40],
            str(conv.get("message_count", 0)),
            updated
        )

    console.print()
    console.print(table)
    console.print(f"\n[{COLORS['muted']}]Use /resume <id> to continue a conversation[/]\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Memory Display Components
# ═══════════════════════════════════════════════════════════════════════════════

def print_user_profile(profile: Dict[str, Any]):
    """Print user profile information"""
    if not profile:
        console.print(f"\n[{COLORS['muted']}]No profile information saved.[/]")
        console.print(f"[{COLORS['muted']}]Use /setname <name> to set your name.[/]\n")
        return

    table = Table(
        title="Your Profile",
        box=ROUNDED,
        title_style=f"bold {COLORS['primary']}",
        header_style=f"bold {COLORS['secondary']}"
    )
    table.add_column("Field", style=f"{COLORS['accent']}")
    table.add_column("Value", style="white")
    table.add_column("Category", style=f"{COLORS['muted']}")

    for key, data in profile.items():
        table.add_row(
            key.replace("_", " ").title(),
            data["value"],
            data["category"]
        )

    console.print()
    console.print(table)
    console.print()


def print_facts(facts: List[Dict]):
    """Print stored facts"""
    if not facts:
        console.print(f"\n[{COLORS['muted']}]No facts saved.[/]")
        console.print(f"[{COLORS['muted']}]Use /remember <information> to save something.[/]\n")
        return

    table = Table(
        title="Saved Facts",
        box=ROUNDED,
        title_style=f"bold {COLORS['primary']}",
        header_style=f"bold {COLORS['secondary']}"
    )
    table.add_column("ID", style=f"{COLORS['muted']}", width=5)
    table.add_column("Fact", style="white", ratio=2)
    table.add_column("Category", style=f"{COLORS['accent']}", width=12)
    table.add_column("Date", style=f"{COLORS['muted']}", width=12)

    for fact in facts:
        created = fact.get("created_at", "")
        if created:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(created)
                created = dt.strftime("%Y-%m-%d")
            except:
                pass

        table.add_row(
            str(fact["id"]),
            fact["fact"],
            fact.get("category", "general"),
            created
        )

    console.print()
    console.print(table)
    console.print(f"\n[{COLORS['muted']}]Use /forget <id> to delete a fact.[/]\n")


def print_notes(notes: List[Dict]):
    """Print stored notes"""
    if not notes:
        console.print(f"\n[{COLORS['muted']}]No notes saved.[/]")
        console.print(f"[{COLORS['muted']}]Use /note <title> | <content> to create a note.[/]\n")
        return

    console.print()
    for note in notes:
        priority_icon = "⭐" if note.get("priority", 0) > 0 else "📝"
        tags = note.get("tags", [])
        tags_str = " ".join(f"[{COLORS['accent']}]#{t}[/]" for t in tags) if tags else ""

        title_text = Text()
        title_text.append(f"{priority_icon} ", style=f"{COLORS['warning']}")
        title_text.append(f"#{note['id']} ", style=f"{COLORS['muted']}")
        title_text.append(note["title"], style=f"bold {COLORS['secondary']}")

        console.print(Panel(
            f"{note['content']}\n\n{tags_str}",
            title=title_text,
            title_align="left",
            border_style=f"{COLORS['primary']}",
            box=ROUNDED,
            padding=(0, 1)
        ))

    console.print()


def print_projects(projects: List[Dict]):
    """Print stored projects"""
    if not projects:
        console.print(f"\n[{COLORS['muted']}]No projects saved.[/]")
        console.print(f"[{COLORS['muted']}]Use /addproject <name> to add current project.[/]\n")
        return

    table = Table(
        title="Your Projects",
        box=ROUNDED,
        title_style=f"bold {COLORS['primary']}",
        header_style=f"bold {COLORS['secondary']}"
    )
    table.add_column("Name", style=f"{COLORS['accent']}")
    table.add_column("Path", style=f"{COLORS['muted']}")
    table.add_column("Technologies", style="white")
    table.add_column("Description", style=f"{COLORS['muted']}")

    for proj in projects:
        tech = ", ".join(proj.get("tech_stack", [])) if proj.get("tech_stack") else "-"
        path = proj.get("path", "-")
        if len(path) > 30:
            path = "..." + path[-27:]

        table.add_row(
            proj["name"],
            path,
            tech,
            proj.get("description", "-")[:40]
        )

    console.print()
    console.print(table)
    console.print()


def print_preferences(preferences: Dict[str, Dict]):
    """Print user preferences"""
    if not preferences:
        console.print(f"\n[{COLORS['muted']}]No preferences saved.[/]")
        console.print(f"[{COLORS['muted']}]Use /setpref <key> <value> to set one.[/]\n")
        return

    table = Table(
        title="Your Preferences",
        box=ROUNDED,
        title_style=f"bold {COLORS['primary']}",
        header_style=f"bold {COLORS['secondary']}"
    )
    table.add_column("Preference", style=f"{COLORS['accent']}")
    table.add_column("Value", style="white")
    table.add_column("Description", style=f"{COLORS['muted']}")

    for key, data in preferences.items():
        table.add_row(
            key,
            data["value"],
            data.get("description", "-") or "-"
        )

    console.print()
    console.print(table)
    console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Status Display
# ═══════════════════════════════════════════════════════════════════════════════

def print_agents_status(agents: List[Dict]):
    """Print status of running agents"""
    if not agents:
        console.print(f"\n[{COLORS['muted']}]No agents running.[/]\n")
        return

    table = Table(
        title="Active Agents",
        box=ROUNDED,
        title_style=f"bold {COLORS['primary']}",
        header_style=f"bold {COLORS['secondary']}"
    )
    table.add_column("ID", style=f"{COLORS['accent']}", width=8)
    table.add_column("Task", style="white", ratio=2)
    table.add_column("Status", style=f"{COLORS['muted']}", width=12)
    table.add_column("Progress", style=f"{COLORS['secondary']}", width=10)

    for agent in agents:
        status_icon = {
            "running": f"[{COLORS['warning']}]⟳ Running[/]",
            "completed": f"[{COLORS['success']}]✓ Completed[/]",
            "failed": f"[{COLORS['error']}]✗ Failed[/]",
            "queued": f"[{COLORS['muted']}]◯ Queued[/]"
        }.get(agent.get("status", ""), agent.get("status", ""))

        progress = agent.get("progress", 0)
        progress_bar = f"[{COLORS['primary']}]{'█' * (progress // 10)}{'░' * (10 - progress // 10)}[/] {progress}%"

        table.add_row(
            agent.get("id", "")[:8],
            agent.get("task", "No description")[:50],
            status_icon,
            progress_bar
        )

    console.print()
    console.print(table)
    console.print()


def print_welcome_with_memory(username: str = None):
    """Print welcome message with user's name if known"""
    if username:
        greeting = f"Hello, {username}!"
    else:
        greeting = "Hello!"

    welcome_text = Text()
    welcome_text.append(f"\n{greeting}\n", style=f"bold {COLORS['secondary']}")
    welcome_text.append("Type ", style=f"{COLORS['muted']}")
    welcome_text.append("/", style=f"bold {COLORS['primary']}")
    welcome_text.append(" to see available commands or start chatting.\n", style=f"{COLORS['muted']}")

    console.print(welcome_text)


# ═══════════════════════════════════════════════════════════════════════════════
# Provider and MCP Display
# ═══════════════════════════════════════════════════════════════════════════════

def print_providers(provider_availability: Dict = None):
    """Print available API providers and their status"""
    table = Table(
        title="API Providers",
        box=ROUNDED,
        title_style=f"bold {COLORS['primary']}",
        header_style=f"bold {COLORS['secondary']}"
    )
    table.add_column("Provider", style=f"{COLORS['accent']}")
    table.add_column("Status", style="white", width=12)
    table.add_column("Description", style=f"{COLORS['muted']}")
    table.add_column("ENV Key", style=f"{COLORS['muted']}")

    for provider, config in PROVIDER_CONFIGS.items():
        is_available = False
        if provider_availability:
            is_available = provider_availability.get(provider, False)

        status = "[green]● Connected[/green]" if is_available else "[red]○ Not configured[/red]"
        table.add_row(config.name, status, config.description, config.env_key)

    console.print()
    console.print(table)
    console.print()


def print_mcp_servers(server_status: Dict[str, Dict] = None):
    """Print MCP server status"""
    if not server_status:
        console.print(f"\n[{COLORS['muted']}]No MCP servers configured.[/]")
        console.print(f"[{COLORS['muted']}]Use /mcp add <name> <command> to add one.[/]\n")
        return

    table = Table(
        title="MCP Servers",
        box=ROUNDED,
        title_style=f"bold {COLORS['primary']}",
        header_style=f"bold {COLORS['secondary']}"
    )
    table.add_column("Name", style=f"{COLORS['accent']}")
    table.add_column("Status", style="white", width=12)
    table.add_column("Tools", style=f"{COLORS['secondary']}", width=8)
    table.add_column("Command", style=f"{COLORS['muted']}")

    for name, info in server_status.items():
        if info["connected"]:
            status = "[green]● Running[/green]"
        elif info["enabled"]:
            status = "[yellow]○ Disconnected[/yellow]"
        else:
            status = "[red]○ Disabled[/red]"

        table.add_row(
            name,
            status,
            str(info["tool_count"]),
            info["command"][:30] + ("..." if len(info["command"]) > 30 else "")
        )

    console.print()
    console.print(table)
    console.print()


def print_mcp_tools(tools: List[Dict] = None):
    """Print available MCP tools"""
    if not tools:
        console.print(f"\n[{COLORS['muted']}]No MCP tools available.[/]\n")
        return

    table = Table(
        title="MCP Tools",
        box=ROUNDED,
        title_style=f"bold {COLORS['primary']}",
        header_style=f"bold {COLORS['secondary']}"
    )
    table.add_column("Tool", style=f"{COLORS['accent']}")
    table.add_column("Server", style=f"{COLORS['secondary']}")
    table.add_column("Description", style=f"{COLORS['muted']}")

    for tool in tools:
        table.add_row(
            tool.name,
            tool.server_name,
            tool.description[:50] + ("..." if len(tool.description) > 50 else "")
        )

    console.print()
    console.print(table)
    console.print()


def print_ollama_models(models: List[str], current_model: str = None):
    """Print locally available Ollama models"""
    if not models:
        console.print(f"\n[{COLORS['muted']}]No Ollama models found.[/]")
        console.print(f"[{COLORS['muted']}]Make sure Ollama is running and you have models pulled.[/]\n")
        return

    table = Table(
        title="Local Ollama Models",
        box=ROUNDED,
        title_style=f"bold {COLORS['primary']}",
        header_style=f"bold {COLORS['secondary']}"
    )
    table.add_column("Model", style=f"{COLORS['accent']}")
    table.add_column("Status", style="white")

    for model in models:
        status = "[green]● Active[/green]" if model == current_model else ""
        table.add_row(model, status)

    console.print()
    console.print(table)
    console.print(f"\n[{COLORS['muted']}]Use /ollama use <model> to switch to a local model[/]\n")
