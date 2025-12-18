"""
Enhanced Selector Components for Dymo Code
Inspired by OpenCode's model picker with better contrast and visibility
"""

import sys
from typing import List, Optional, Callable, Dict, Any, Tuple
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED, HEAVY, SIMPLE
from rich.style import Style
from rich.live import Live
from rich.layout import Layout

# For keyboard input
if sys.platform == "win32":
    import msvcrt
else:
    import tty
    import termios
    import select


# ═══════════════════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SelectorItem:
    """An item in the selector"""
    id: str
    title: str
    description: str
    category: str = ""
    icon: str = ""
    is_current: bool = False
    meta: str = ""  # Additional info like provider name


@dataclass
class SelectorCategory:
    """A category group in the selector"""
    name: str
    items: List[SelectorItem]
    icon: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Theme Colors
# ═══════════════════════════════════════════════════════════════════════════════

def get_selector_colors() -> Dict[str, str]:
    """Get colors optimized for selector visibility"""
    try:
        from .themes import theme_manager
        colors = theme_manager.colors
        return {
            "primary": colors.get("primary", "#7C3AED"),
            "secondary": colors.get("secondary", "#06B6D4"),
            "accent": colors.get("accent", "#EC4899"),
            "success": colors.get("success", "#10B981"),
            "warning": colors.get("warning", "#F59E0B"),
            "error": colors.get("error", "#EF4444"),
            "muted": colors.get("muted", "#9CA3AF"),  # Lighter for better visibility
            "text": "#FFFFFF",
            "text_dim": "#B4B4B4",  # Visible but dimmer
            "bg": colors.get("background", "#1a1a2e"),
            "bg_selected": colors.get("primary", "#7C3AED"),
            "bg_hover": "#2d2d44",
            "border": colors.get("border", "#374151"),
        }
    except ImportError:
        return {
            "primary": "#7C3AED",
            "secondary": "#06B6D4",
            "accent": "#EC4899",
            "success": "#10B981",
            "warning": "#F59E0B",
            "error": "#EF4444",
            "muted": "#9CA3AF",
            "text": "#FFFFFF",
            "text_dim": "#B4B4B4",
            "bg": "#1a1a2e",
            "bg_selected": "#7C3AED",
            "bg_hover": "#2d2d44",
            "border": "#374151",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Keyboard Input
# ═══════════════════════════════════════════════════════════════════════════════

def get_key() -> str:
    """Get a single keypress cross-platform"""
    if sys.platform == "win32":
        key = msvcrt.getwch()
        if key == '\xe0':  # Special key prefix on Windows
            key2 = msvcrt.getwch()
            if key2 == 'H': return 'up'
            if key2 == 'P': return 'down'
            if key2 == 'K': return 'left'
            if key2 == 'M': return 'right'
        if key == '\r': return 'enter'
        if key == '\x1b': return 'esc'
        if key == '\x03': return 'ctrl+c'
        return key
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':  # Escape sequence
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch2 = sys.stdin.read(1)
                    if ch2 == '[':
                        ch3 = sys.stdin.read(1)
                        if ch3 == 'A': return 'up'
                        if ch3 == 'B': return 'down'
                        if ch3 == 'C': return 'right'
                        if ch3 == 'D': return 'left'
                return 'esc'
            if ch == '\r' or ch == '\n': return 'enter'
            if ch == '\x03': return 'ctrl+c'
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# ═══════════════════════════════════════════════════════════════════════════════
# Enhanced Selector
# ═══════════════════════════════════════════════════════════════════════════════

class EnhancedSelector:
    """
    Enhanced selector with visual styling inspired by OpenCode.
    Features:
    - Category grouping
    - Highlighted descriptions
    - Current item indicator
    - Keyboard navigation
    - Search/filter support
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console(force_terminal=True)
        self.colors = get_selector_colors()

    def _build_item_text(
        self,
        item: SelectorItem,
        is_selected: bool,
        max_title_width: int = 30,
        max_desc_width: int = 45
    ) -> Text:
        """Build rich text for a selector item"""
        colors = self.colors
        text = Text()

        # Selection indicator
        if is_selected:
            text.append(" > ", style=f"bold {colors['primary']}")
        else:
            text.append("   ", style=colors['muted'])

        # Current marker
        if item.is_current:
            text.append("● ", style=f"bold {colors['success']}")
        else:
            text.append("○ ", style=colors['muted'])

        # Icon
        if item.icon:
            text.append(f"{item.icon} ", style=colors['secondary'])

        # Title - truncate if needed
        title = item.title
        if len(title) > max_title_width:
            title = title[:max_title_width-2] + ".."

        if is_selected:
            text.append(title.ljust(max_title_width), style=f"bold {colors['text']}")
        else:
            text.append(title.ljust(max_title_width), style=colors['text'])

        text.append("  ", style="")

        # Description - this is the key improvement: visible contrast
        desc = item.description
        if len(desc) > max_desc_width:
            desc = desc[:max_desc_width-2] + ".."

        if is_selected:
            # Selected: bright description
            text.append(desc, style=f"{colors['secondary']}")
        else:
            # Not selected: visible but dimmer (NOT #888!)
            text.append(desc, style=colors['text_dim'])

        # Meta info (provider) on the right
        if item.meta:
            meta = f" [{item.meta}]"
            if is_selected:
                text.append(meta, style=f"italic {colors['accent']}")
            else:
                text.append(meta, style=f"italic {colors['muted']}")

        return text

    def _build_category_header(self, category: str, icon: str = "") -> Text:
        """Build category header"""
        colors = self.colors
        text = Text()
        text.append("   ", style="")  # Indent
        if icon:
            text.append(f"{icon} ", style=colors['warning'])
        text.append(category.upper(), style=f"bold {colors['warning']}")
        return text

    def show(
        self,
        items: List[SelectorItem],
        title: str = "Select",
        subtitle: str = "",
        allow_search: bool = True,
        categories: bool = True
    ) -> Optional[str]:
        """
        Show the selector and return selected item id.

        Args:
            items: List of items to select from
            title: Dialog title
            subtitle: Optional subtitle/instructions
            allow_search: Enable search filtering
            categories: Group items by category

        Returns:
            Selected item id or None if cancelled
        """
        if not items:
            return None

        colors = self.colors
        selected_idx = 0
        search_query = ""
        filtered_items = items.copy()

        # Find current item if any
        for i, item in enumerate(filtered_items):
            if item.is_current:
                selected_idx = i
                break

        def filter_items(query: str) -> List[SelectorItem]:
            if not query:
                return items.copy()
            query = query.lower()
            return [
                item for item in items
                if query in item.title.lower()
                or query in item.description.lower()
                or query in item.category.lower()
            ]

        def render() -> Panel:
            """Render the selector panel"""
            lines = []

            # Search box
            if allow_search:
                search_text = Text()
                search_text.append("  🔍 ", style=colors['muted'])
                if search_query:
                    search_text.append(search_query, style=f"bold {colors['text']}")
                    search_text.append("_", style=f"blink {colors['primary']}")
                else:
                    search_text.append("Type to search...", style=colors['muted'])
                lines.append(search_text)
                lines.append(Text(""))  # Spacer

            # Group by category if enabled
            if categories and filtered_items:
                current_category = None
                item_idx = 0

                for item in filtered_items:
                    # Category header
                    if item.category and item.category != current_category:
                        if current_category is not None:
                            lines.append(Text(""))  # Spacer between categories
                        lines.append(self._build_category_header(item.category))
                        current_category = item.category

                    # Item
                    is_selected = (item_idx == selected_idx)
                    lines.append(self._build_item_text(item, is_selected))
                    item_idx += 1
            else:
                # No categories - flat list
                for i, item in enumerate(filtered_items):
                    is_selected = (i == selected_idx)
                    lines.append(self._build_item_text(item, is_selected))

            # Empty state
            if not filtered_items:
                empty = Text()
                empty.append("  No items match '", style=colors['muted'])
                empty.append(search_query, style=colors['warning'])
                empty.append("'", style=colors['muted'])
                lines.append(empty)

            # Footer
            lines.append(Text(""))
            footer = Text()
            footer.append("  ↑↓", style=f"bold {colors['muted']}")
            footer.append(" Navigate  ", style=colors['muted'])
            footer.append("Enter", style=f"bold {colors['muted']}")
            footer.append(" Select  ", style=colors['muted'])
            footer.append("Esc", style=f"bold {colors['muted']}")
            footer.append(" Cancel", style=colors['muted'])
            lines.append(footer)

            # Build content
            content = Text("\n").join(lines)

            # Subtitle
            panel_subtitle = None
            if subtitle:
                panel_subtitle = Text(subtitle, style=colors['muted'])

            return Panel(
                content,
                title=f"[bold {colors['secondary']}]{title}[/]",
                subtitle=panel_subtitle,
                border_style=colors['border'],
                box=ROUNDED,
                padding=(1, 2)
            )

        # Clear screen area and show selector
        self.console.print()

        try:
            with Live(render(), console=self.console, refresh_per_second=30, transient=True) as live:
                while True:
                    key = get_key()

                    if key == 'up':
                        if selected_idx > 0:
                            selected_idx -= 1
                        else:
                            selected_idx = len(filtered_items) - 1 if filtered_items else 0

                    elif key == 'down':
                        if selected_idx < len(filtered_items) - 1:
                            selected_idx += 1
                        else:
                            selected_idx = 0

                    elif key == 'enter':
                        if filtered_items and 0 <= selected_idx < len(filtered_items):
                            return filtered_items[selected_idx].id
                        return None

                    elif key in ('esc', 'ctrl+c'):
                        return None

                    elif key == '\x7f' or key == '\x08':  # Backspace
                        if search_query:
                            search_query = search_query[:-1]
                            filtered_items = filter_items(search_query)
                            selected_idx = min(selected_idx, len(filtered_items) - 1)
                            if selected_idx < 0:
                                selected_idx = 0

                    elif allow_search and key.isprintable() and len(key) == 1:
                        search_query += key
                        filtered_items = filter_items(search_query)
                        selected_idx = 0

                    live.update(render())

        except Exception as e:
            self.console.print(f"[red]Selector error: {e}[/]")
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# Specialized Selectors
# ═══════════════════════════════════════════════════════════════════════════════

class ModelSelector(EnhancedSelector):
    """Model picker with provider grouping"""

    def show_models(self, current_model: str = "") -> Optional[str]:
        """Show model selection dialog"""
        try:
            from .config import AVAILABLE_MODELS
        except ImportError:
            return None

        items = []

        # Group by provider
        for key, config in AVAILABLE_MODELS.items():
            items.append(SelectorItem(
                id=key,
                title=config.name,
                description=config.description[:50] if config.description else "",
                category=config.provider.value.title(),
                icon="🤖",
                is_current=(key == current_model),
                meta=config.provider.value
            ))

        # Sort by category then name
        items.sort(key=lambda x: (x.category, x.title))

        return self.show(
            items=items,
            title="Select Model",
            subtitle="Choose an AI model",
            allow_search=True,
            categories=True
        )


class ThemeSelector(EnhancedSelector):
    """Theme picker"""

    def show_themes(self, current_theme: str = "") -> Optional[str]:
        """Show theme selection dialog"""
        try:
            from .themes import theme_manager
        except ImportError:
            return None

        items = []

        for theme_info in theme_manager.list_themes():
            items.append(SelectorItem(
                id=theme_info["name"],
                title=theme_info["display_name"],
                description=theme_info["description"],
                category="Themes",
                icon="🎨",
                is_current=theme_info["is_current"]
            ))

        return self.show(
            items=items,
            title="Select Theme",
            subtitle="Choose a color theme",
            allow_search=True,
            categories=False  # Single category
        )


class ProviderSelector(EnhancedSelector):
    """Provider/API picker"""

    def show_providers(self) -> Optional[str]:
        """Show provider selection dialog"""
        providers = [
            SelectorItem(
                id="groq",
                title="Groq",
                description="Fast inference with Llama models",
                category="Popular",
                icon="⚡"
            ),
            SelectorItem(
                id="openrouter",
                title="OpenRouter",
                description="Access to multiple AI models",
                category="Popular",
                icon="🌐"
            ),
            SelectorItem(
                id="anthropic",
                title="Anthropic",
                description="Claude models",
                category="Popular",
                icon="🧠"
            ),
            SelectorItem(
                id="openai",
                title="OpenAI",
                description="GPT models",
                category="Other",
                icon="💚"
            ),
            SelectorItem(
                id="ollama",
                title="Ollama",
                description="Local models (no API key)",
                category="Local",
                icon="🏠"
            ),
        ]

        return self.show(
            items=items,
            title="Select Provider",
            subtitle="Choose an API provider",
            allow_search=True,
            categories=True
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Quick Input Dialog
# ═══════════════════════════════════════════════════════════════════════════════

class QuickInput:
    """Simple input dialog with styled prompt"""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console(force_terminal=True)
        self.colors = get_selector_colors()

    def show(
        self,
        title: str,
        placeholder: str = "",
        default: str = ""
    ) -> Optional[str]:
        """Show input dialog and return entered text"""
        from prompt_toolkit import prompt
        from prompt_toolkit.formatted_text import HTML
        from prompt_toolkit.styles import Style as PTStyle

        colors = self.colors

        # Custom style with better visibility
        style = PTStyle.from_dict({
            'prompt': f'bold {colors["primary"]}',
        })

        self.console.print()
        header = Text()
        header.append("  ", style="")
        header.append(title, style=f"bold {colors['secondary']}")
        if placeholder:
            header.append(f"  ({placeholder})", style=colors['muted'])
        self.console.print(header)

        try:
            result = prompt(
                HTML(f'<style fg="{colors["primary"]}">  ❯ </style>'),
                default=default,
                style=style
            )
            return result.strip() if result else None
        except (KeyboardInterrupt, EOFError):
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instances
# ═══════════════════════════════════════════════════════════════════════════════

enhanced_selector = EnhancedSelector()
model_selector = ModelSelector()
theme_selector = ThemeSelector()
quick_input = QuickInput()
