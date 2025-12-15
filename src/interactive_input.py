"""
Interactive Input Handler for Dymo Code
Provides real-time command suggestions and visual feedback
"""

import os
import sys
import msvcrt
from typing import List, Optional, Callable

from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.box import ROUNDED, SIMPLE
from rich.live import Live
from rich.layout import Layout

from .commands import (
    Command, CommandCategory, COMMANDS,
    get_command_suggestions, get_commands_by_category,
    CATEGORY_ICONS, CATEGORY_NAMES
)
from .config import COLORS

# ═══════════════════════════════════════════════════════════════════════════════
# Console Setup
# ═══════════════════════════════════════════════════════════════════════════════

console = Console(force_terminal=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Command Suggestion Display
# ═══════════════════════════════════════════════════════════════════════════════

def render_command_suggestions(suggestions: List[Command], selected_index: int = 0, max_show: int = 8) -> Panel:
    """
    Render command suggestions as a styled panel.
    """
    if not suggestions:
        return Panel(
            Text("No se encontraron comandos", style=f"{COLORS['muted']}"),
            border_style=f"{COLORS['muted']}",
            box=ROUNDED,
            padding=(0, 1)
        )

    # Limit displayed suggestions
    suggestions = suggestions[:max_show]

    table = Table(
        show_header=False,
        box=None,
        padding=(0, 1),
        expand=True
    )
    table.add_column("Icon", width=2)
    table.add_column("Command", width=15)
    table.add_column("Description", ratio=1)

    for i, cmd in enumerate(suggestions):
        icon = CATEGORY_ICONS.get(cmd.category, "•")
        is_selected = i == selected_index

        if is_selected:
            # Highlighted row
            icon_style = f"bold {COLORS['primary']}"
            cmd_style = f"bold {COLORS['primary']}"
            desc_style = f"{COLORS['secondary']}"
            prefix = "▶ "
        else:
            icon_style = f"{COLORS['muted']}"
            cmd_style = f"{COLORS['accent']}"
            desc_style = f"{COLORS['muted']}"
            prefix = "  "

        cmd_text = Text()
        cmd_text.append(prefix)
        cmd_text.append(f"/{cmd.name}", style=cmd_style)

        if cmd.has_args and cmd.arg_hint:
            cmd_text.append(f" <{cmd.arg_hint}>", style=f"dim {COLORS['muted']}")

        table.add_row(
            Text(icon, style=icon_style),
            cmd_text,
            Text(cmd.description, style=desc_style)
        )

    return Panel(
        table,
        title="[bold]Comandos[/bold]",
        title_align="left",
        border_style=f"{COLORS['primary']}",
        box=ROUNDED,
        padding=(0, 0)
    )


def render_help_panel() -> Panel:
    """Render the full help panel with all commands grouped by category"""
    categories = get_commands_by_category()

    main_table = Table(
        show_header=False,
        box=None,
        padding=(0, 1),
        expand=True
    )
    main_table.add_column(ratio=1)

    for category in CommandCategory:
        if category not in categories:
            continue

        commands = categories[category]
        icon = CATEGORY_ICONS.get(category, "•")
        name = CATEGORY_NAMES.get(category, category.value)

        # Category header
        header = Text()
        header.append(f"\n{icon} ", style=f"{COLORS['warning']}")
        header.append(f"{name}", style=f"bold {COLORS['secondary']}")
        main_table.add_row(header)

        # Commands in this category
        for cmd in commands:
            cmd_text = Text()
            cmd_text.append(f"  /{cmd.name}", style=f"{COLORS['accent']}")

            if cmd.aliases:
                aliases = ", ".join(f"/{a}" for a in cmd.aliases)
                cmd_text.append(f" ({aliases})", style=f"dim {COLORS['muted']}")

            cmd_text.append(f"  {cmd.description}", style=f"{COLORS['muted']}")

            main_table.add_row(cmd_text)

    return Panel(
        main_table,
        title="[bold]Ayuda - Todos los Comandos[/bold]",
        title_align="left",
        border_style=f"{COLORS['primary']}",
        box=ROUNDED,
        padding=(1, 2)
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Interactive Input Handler
# ═══════════════════════════════════════════════════════════════════════════════

class InteractiveInput:
    """
    Handles interactive input with real-time command suggestions.
    Works on Windows using msvcrt.
    """

    def __init__(self):
        self.buffer = ""
        self.cursor_pos = 0
        self.suggestions: List[Command] = []
        self.selected_index = 0
        self.showing_suggestions = False
        self.history: List[str] = []
        self.history_index = -1

    def _clear_line(self):
        """Clear the current line"""
        sys.stdout.write('\r' + ' ' * 120 + '\r')
        sys.stdout.flush()

    def _render_input_line(self):
        """Render the current input line with prompt"""
        self._clear_line()

        # Build prompt
        prompt = Text()
        prompt.append("❯ ", style=f"bold {COLORS['primary']}")

        # Build input text with cursor
        input_text = Text()
        input_text.append(self.buffer, style="white")

        # Render to console without newline
        console.print(prompt, end="")
        console.print(input_text, end="")
        sys.stdout.flush()

    def _update_suggestions(self):
        """Update command suggestions based on current buffer"""
        if self.buffer.startswith("/"):
            partial = self.buffer[1:]  # Remove the /
            self.suggestions = get_command_suggestions(partial)
            self.showing_suggestions = len(self.suggestions) > 0
            self.selected_index = 0
        else:
            self.suggestions = []
            self.showing_suggestions = False

    def _render_suggestions(self):
        """Render the suggestions panel below the input"""
        if self.showing_suggestions and self.suggestions:
            console.print()  # New line after input
            console.print(render_command_suggestions(self.suggestions, self.selected_index))

    def _complete_selected(self):
        """Complete input with selected suggestion"""
        if self.suggestions and 0 <= self.selected_index < len(self.suggestions):
            cmd = self.suggestions[self.selected_index]
            self.buffer = f"/{cmd.name}"
            if cmd.has_args:
                self.buffer += " "
            self.cursor_pos = len(self.buffer)
            self.showing_suggestions = False

    def get_input(self, prompt_prefix: str = "") -> str:
        """
        Get input from user with interactive command suggestions.
        Returns the final input string.
        """
        self.buffer = ""
        self.cursor_pos = 0
        self.showing_suggestions = False
        self.selected_index = 0

        # Initial render
        self._render_input_line()

        while True:
            if msvcrt.kbhit():
                char = msvcrt.getwch()

                # Enter - submit
                if char == '\r':
                    console.print()  # New line
                    result = self.buffer.strip()
                    if result:
                        self.history.append(result)
                        self.history_index = len(self.history)
                    return result

                # Escape - cancel suggestions
                elif char == '\x1b':
                    self.showing_suggestions = False
                    self._clear_line()
                    self._render_input_line()

                # Tab - complete suggestion
                elif char == '\t':
                    if self.showing_suggestions:
                        self._complete_selected()
                        self._clear_line()
                        self._render_input_line()

                # Backspace
                elif char == '\x08':
                    if self.buffer:
                        self.buffer = self.buffer[:-1]
                        self.cursor_pos = max(0, self.cursor_pos - 1)
                        self._update_suggestions()
                        self._clear_line()
                        self._render_input_line()
                        if self.showing_suggestions:
                            self._render_suggestions()

                # Special keys (arrows, etc.)
                elif char == '\x00' or char == '\xe0':
                    special = msvcrt.getwch()

                    # Up arrow
                    if special == 'H':
                        if self.showing_suggestions:
                            self.selected_index = max(0, self.selected_index - 1)
                            self._clear_line()
                            self._render_input_line()
                            self._render_suggestions()
                        elif self.history and self.history_index > 0:
                            self.history_index -= 1
                            self.buffer = self.history[self.history_index]
                            self.cursor_pos = len(self.buffer)
                            self._update_suggestions()
                            self._clear_line()
                            self._render_input_line()

                    # Down arrow
                    elif special == 'P':
                        if self.showing_suggestions:
                            self.selected_index = min(len(self.suggestions) - 1, self.selected_index + 1)
                            self._clear_line()
                            self._render_input_line()
                            self._render_suggestions()
                        elif self.history_index < len(self.history) - 1:
                            self.history_index += 1
                            self.buffer = self.history[self.history_index]
                            self.cursor_pos = len(self.buffer)
                            self._update_suggestions()
                            self._clear_line()
                            self._render_input_line()

                # Regular character
                elif char.isprintable():
                    self.buffer += char
                    self.cursor_pos += 1
                    self._update_suggestions()
                    self._clear_line()
                    self._render_input_line()

                    # Show suggestions if typing a command
                    if self.showing_suggestions:
                        self._render_suggestions()


# ═══════════════════════════════════════════════════════════════════════════════
# Simple Input (Fallback)
# ═══════════════════════════════════════════════════════════════════════════════

def simple_input_with_suggestions() -> str:
    """
    Simpler input that shows suggestions when / is typed.
    Works as a fallback for environments where msvcrt doesn't work well.
    """
    # Show prompt
    prompt = Text()
    prompt.append("❯ ", style=f"bold {COLORS['primary']}")
    console.print(prompt, end="")

    try:
        user_input = input().strip()
    except EOFError:
        return "/exit"

    # If starts with /, show suggestions
    if user_input == "/":
        console.print()
        console.print(render_help_panel())
        return simple_input_with_suggestions()

    return user_input


# ═══════════════════════════════════════════════════════════════════════════════
# Exported Function
# ═══════════════════════════════════════════════════════════════════════════════

def get_user_input() -> str:
    """
    Get user input with command suggestions.
    Uses interactive input on Windows, falls back to simple input elsewhere.
    """
    if sys.platform == "win32":
        try:
            handler = InteractiveInput()
            return handler.get_input()
        except Exception:
            return simple_input_with_suggestions()
    else:
        return simple_input_with_suggestions()
