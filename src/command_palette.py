"""
Command Palette for Dymo Code
Inspired by VSCode/OpenCode command palette (Ctrl+P)
"""

from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion, FuzzyCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style

from .commands import COMMANDS, Command, CommandCategory, CATEGORY_ICONS
from .keybindings import keybind_manager, get_keybind_display


# ═══════════════════════════════════════════════════════════════════════════════
# Palette Item
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PaletteItem:
    """An item in the command palette"""
    id: str
    title: str
    description: str
    category: str
    icon: str = ""
    keybind: Optional[str] = None
    action: Optional[Callable] = None
    command: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Fuzzy Matching
# ═══════════════════════════════════════════════════════════════════════════════

def fuzzy_match(query: str, text: str) -> tuple[bool, int]:
    """
    Check if query fuzzy matches text.
    Returns (matches, score) where lower score is better.
    """
    if not query:
        return True, 0

    query = query.lower()
    text = text.lower()

    # Exact match
    if query == text:
        return True, 0

    # Prefix match
    if text.startswith(query):
        return True, 1

    # Contains match
    if query in text:
        return True, 2

    # Fuzzy match
    query_idx = 0
    score = 0
    last_match_idx = -1

    for i, char in enumerate(text):
        if query_idx < len(query) and char == query[query_idx]:
            # Penalize gaps
            if last_match_idx >= 0:
                score += (i - last_match_idx - 1) * 0.5
            last_match_idx = i
            query_idx += 1

    if query_idx == len(query):
        return True, 3 + score

    return False, float('inf')


# ═══════════════════════════════════════════════════════════════════════════════
# Palette Completer
# ═══════════════════════════════════════════════════════════════════════════════

class PaletteCompleter(Completer):
    """Completer for command palette with fuzzy matching"""

    def __init__(self, items: List[PaletteItem]):
        self.items = items

    def get_completions(self, document, complete_event):
        query = document.text_before_cursor.strip()

        # Score and filter items
        scored_items = []
        for item in self.items:
            # Check title and description
            title_match, title_score = fuzzy_match(query, item.title)
            desc_match, desc_score = fuzzy_match(query, item.description)
            cmd_match, cmd_score = fuzzy_match(query, item.command or "")

            if title_match or desc_match or cmd_match:
                best_score = min(
                    title_score if title_match else float('inf'),
                    desc_score + 0.5 if desc_match else float('inf'),
                    cmd_score + 0.3 if cmd_match else float('inf')
                )
                scored_items.append((best_score, item))

        # Sort by score
        scored_items.sort(key=lambda x: x[0])

        # Yield completions
        for score, item in scored_items[:15]:
            # Build display text
            keybind_str = f"  [{item.keybind}]" if item.keybind else ""

            yield Completion(
                item.id,
                start_position=-len(query),
                display=HTML(f'<b>{item.icon} {item.title}</b>{keybind_str}'),
                # Use #B4B4B4 instead of #888 for better visibility
                display_meta=HTML(f'<style fg="#B4B4B4">{item.description[:50]}</style>')
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Command Palette
# ═══════════════════════════════════════════════════════════════════════════════

class CommandPalette:
    """
    Interactive command palette with fuzzy search.
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console(force_terminal=True)
        self._items: List[PaletteItem] = []
        self._custom_items: List[PaletteItem] = []

        # Build items from commands
        self._build_items()

    def _get_colors(self):
        """Get colors from theme"""
        try:
            from .themes import theme_manager
            return theme_manager.colors
        except ImportError:
            return {
                "primary": "#7C3AED",
                "secondary": "#06B6D4",
                "muted": "#6B7280",
            }

    def _build_items(self):
        """Build palette items from registered commands"""
        self._items.clear()

        for name, cmd in COMMANDS.items():
            icon = CATEGORY_ICONS.get(cmd.category, "•")
            keybind = get_keybind_display(name)

            self._items.append(PaletteItem(
                id=name,
                title=f"/{cmd.name}",
                description=cmd.description,
                category=cmd.category.value,
                icon=icon,
                keybind=keybind,
                command=cmd.name
            ))

    def add_item(self, item: PaletteItem):
        """Add a custom item to the palette"""
        self._custom_items.append(item)

    def remove_item(self, item_id: str):
        """Remove a custom item from the palette"""
        self._custom_items = [i for i in self._custom_items if i.id != item_id]

    def get_all_items(self) -> List[PaletteItem]:
        """Get all palette items"""
        return self._items + self._custom_items

    def show(self) -> Optional[str]:
        """
        Show the command palette and return selected command.
        Returns command name or None if cancelled.
        """
        colors = self._get_colors()
        items = self.get_all_items()

        # Custom style - improved contrast for visibility
        style = Style.from_dict({
            'prompt': f'{colors["primary"]}',
            # Better background for contrast
            'completion-menu': 'bg:#252536 #E5E5E5',
            'completion-menu.completion': 'bg:#252536 #E5E5E5',
            'completion-menu.completion.current': f'bg:{colors["primary"]} #ffffff bold',
            # Much lighter meta text for visibility
            'completion-menu.meta': '#B4B4B4',
            'completion-menu.meta.current': '#ffffff',
        })

        # Show header
        self.console.print()
        header = Text()
        header.append("❯ ", style=f"bold {colors['primary']}")
        header.append("Command Palette", style=f"bold {colors['secondary']}")
        header.append(" (type to search, Enter to select, Esc to cancel)", style=f"{colors['muted']}")
        self.console.print(header)

        try:
            result = prompt(
                HTML(f'<style fg="{colors["primary"]}">❯ </style>'),
                completer=PaletteCompleter(items),
                style=style,
                complete_while_typing=True,
            )

            if result:
                result = result.strip()
                # Check if result is a palette item id
                for item in items:
                    if item.id == result or item.command == result:
                        return f"/{item.command}" if item.command else None
                # If not found, treat as direct command
                if result.startswith("/"):
                    return result
                return f"/{result}"

        except KeyboardInterrupt:
            pass
        except EOFError:
            pass

        return None

    def print_all_commands(self):
        """Print all commands in a formatted table"""
        colors = self._get_colors()

        # Group by category
        by_category: Dict[str, List[PaletteItem]] = {}
        for item in self.get_all_items():
            if item.category not in by_category:
                by_category[item.category] = []
            by_category[item.category].append(item)

        self.console.print()

        for category, items in by_category.items():
            table = Table(
                title=f"{category.title()} Commands",
                box=ROUNDED,
                title_style=f"bold {colors['primary']}",
                header_style=f"bold {colors['secondary']}",
                show_header=True
            )
            table.add_column("Command", style=f"{colors['accent']}", width=20)
            table.add_column("Keybind", style=f"{colors['muted']}", width=12)
            table.add_column("Description", style="white")

            for item in sorted(items, key=lambda x: x.title):
                keybind = item.keybind or ""
                table.add_row(item.title, keybind, item.description)

            self.console.print(table)
            self.console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# Quick Actions Palette
# ═══════════════════════════════════════════════════════════════════════════════

class QuickActionsPalette:
    """
    Simplified palette for quick actions (model switch, theme change, etc.)
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console(force_terminal=True)

    def _get_colors(self):
        try:
            from .themes import theme_manager
            return theme_manager.colors
        except ImportError:
            return {"primary": "#7C3AED", "secondary": "#06B6D4", "muted": "#6B7280"}

    def show_model_picker(self, current_model: str) -> Optional[str]:
        """Show a quick model picker"""
        from .config import AVAILABLE_MODELS

        colors = self._get_colors()
        items = []

        for key, config in AVAILABLE_MODELS.items():
            is_current = key == current_model
            icon = "●" if is_current else "○"
            items.append(PaletteItem(
                id=key,
                title=f"{icon} {config.name}",
                description=f"{config.provider.value} - {config.description}",
                category="models",
                icon="🤖"
            ))

        self.console.print()
        header = Text()
        header.append("🤖 ", style=f"bold {colors['warning']}")
        header.append("Select Model", style=f"bold {colors['secondary']}")
        self.console.print(header)

        try:
            result = prompt(
                HTML(f'<style fg="{colors["primary"]}">❯ </style>'),
                completer=PaletteCompleter(items),
                complete_while_typing=True,
            )
            return result.strip() if result else None
        except (KeyboardInterrupt, EOFError):
            return None

    def show_theme_picker(self, current_theme: str) -> Optional[str]:
        """Show a quick theme picker"""
        try:
            from .themes import theme_manager
        except ImportError:
            return None

        colors = self._get_colors()
        items = []

        for theme_info in theme_manager.list_themes():
            is_current = theme_info["is_current"]
            icon = "●" if is_current else "○"
            items.append(PaletteItem(
                id=theme_info["name"],
                title=f"{icon} {theme_info['display_name']}",
                description=theme_info["description"],
                category="themes",
                icon="🎨"
            ))

        self.console.print()
        header = Text()
        header.append("🎨 ", style=f"bold {colors['warning']}")
        header.append("Select Theme", style=f"bold {colors['secondary']}")
        self.console.print(header)

        try:
            result = prompt(
                HTML(f'<style fg="{colors["primary"]}">❯ </style>'),
                completer=PaletteCompleter(items),
                complete_while_typing=True,
            )
            return result.strip() if result else None
        except (KeyboardInterrupt, EOFError):
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

command_palette = CommandPalette()
quick_actions = QuickActionsPalette()
