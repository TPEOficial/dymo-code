"""
File Explorer / Tree View for Dymo Code
Provides interactive file navigation and preview
Inspired by OpenCode's file handling
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from pathlib import Path
from enum import Enum

from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.table import Table
from rich.box import ROUNDED

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.formatted_text import HTML


# ═══════════════════════════════════════════════════════════════════════════════
# File Types and Icons
# ═══════════════════════════════════════════════════════════════════════════════

FILE_ICONS = {
    # Folders
    "folder": "📁",
    "folder_open": "📂",

    # Programming Languages
    ".py": "🐍",
    ".js": "📜",
    ".ts": "📘",
    ".jsx": "⚛️",
    ".tsx": "⚛️",
    ".html": "🌐",
    ".css": "🎨",
    ".scss": "🎨",
    ".json": "📋",
    ".yaml": "📋",
    ".yml": "📋",
    ".xml": "📋",
    ".md": "📝",
    ".txt": "📄",
    ".rs": "🦀",
    ".go": "🐹",
    ".java": "☕",
    ".c": "🔧",
    ".cpp": "🔧",
    ".h": "🔧",
    ".rb": "💎",
    ".php": "🐘",
    ".swift": "🦅",
    ".kt": "🎯",
    ".sh": "🖥️",
    ".bash": "🖥️",
    ".zsh": "🖥️",
    ".ps1": "🖥️",
    ".bat": "🖥️",
    ".sql": "🗃️",

    # Config files
    ".env": "🔐",
    ".gitignore": "🚫",
    ".dockerignore": "🐳",
    "Dockerfile": "🐳",
    "docker-compose.yml": "🐳",
    "package.json": "📦",
    "requirements.txt": "📦",
    "Cargo.toml": "📦",
    "go.mod": "📦",

    # Images
    ".png": "🖼️",
    ".jpg": "🖼️",
    ".jpeg": "🖼️",
    ".gif": "🖼️",
    ".svg": "🖼️",
    ".ico": "🖼️",

    # Documents
    ".pdf": "📕",
    ".doc": "📘",
    ".docx": "📘",
    ".xls": "📗",
    ".xlsx": "📗",

    # Archives
    ".zip": "📦",
    ".tar": "📦",
    ".gz": "📦",
    ".rar": "📦",

    # Default
    "default": "📄",
}

# Files/folders to ignore
IGNORE_PATTERNS = {
    "__pycache__",
    ".git",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "Thumbs.db",
}


# ═══════════════════════════════════════════════════════════════════════════════
# File Node
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FileNode:
    """Represents a file or directory in the tree"""
    name: str
    path: Path
    is_dir: bool
    children: List['FileNode'] = field(default_factory=list)
    size: int = 0
    is_expanded: bool = False

    @property
    def icon(self) -> str:
        if self.is_dir:
            return FILE_ICONS["folder_open"] if self.is_expanded else FILE_ICONS["folder"]

        # Check full filename first (for special files)
        if self.name in FILE_ICONS:
            return FILE_ICONS[self.name]

        # Then check extension
        ext = self.path.suffix.lower()
        return FILE_ICONS.get(ext, FILE_ICONS["default"])

    @property
    def display_name(self) -> str:
        if self.is_dir:
            return f"{self.name}/"
        return self.name


# ═══════════════════════════════════════════════════════════════════════════════
# File Tree Builder
# ═══════════════════════════════════════════════════════════════════════════════

class FileTreeBuilder:
    """Builds a file tree from a directory"""

    def __init__(
        self,
        ignore_patterns: set = None,
        max_depth: int = 5,
        show_hidden: bool = False
    ):
        self.ignore_patterns = ignore_patterns or IGNORE_PATTERNS
        self.max_depth = max_depth
        self.show_hidden = show_hidden

    def should_ignore(self, name: str) -> bool:
        """Check if a file/folder should be ignored"""
        if not self.show_hidden and name.startswith('.'):
            return True

        for pattern in self.ignore_patterns:
            if pattern.startswith('*'):
                if name.endswith(pattern[1:]):
                    return True
            elif name == pattern:
                return True

        return False

    def build(self, root_path: str, depth: int = 0) -> FileNode:
        """Build a file tree from a root path"""
        root = Path(root_path)

        node = FileNode(
            name=root.name or str(root),
            path=root,
            is_dir=root.is_dir()
        )

        if not root.is_dir() or depth >= self.max_depth:
            if root.is_file():
                try:
                    node.size = root.stat().st_size
                except OSError:
                    pass
            return node

        try:
            items = sorted(root.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))

            for item in items:
                if self.should_ignore(item.name):
                    continue

                child = self.build(str(item), depth + 1)
                node.children.append(child)

        except PermissionError:
            pass

        return node


# ═══════════════════════════════════════════════════════════════════════════════
# File Explorer
# ═══════════════════════════════════════════════════════════════════════════════

class FileExplorer:
    """
    Interactive file explorer with tree view.
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console(force_terminal=True)
        self.tree_builder = FileTreeBuilder()
        self._colors = self._get_colors()

    def _get_colors(self) -> Dict[str, str]:
        try:
            from .themes import theme_manager
            return theme_manager.colors
        except ImportError:
            return {
                "primary": "#7C3AED",
                "secondary": "#06B6D4",
                "success": "#10B981",
                "warning": "#F59E0B",
                "error": "#EF4444",
                "muted": "#6B7280",
                "accent": "#EC4899",
            }

    def show_tree(
        self,
        root_path: str = ".",
        max_depth: int = 3,
        show_hidden: bool = False
    ):
        """Display a tree view of the directory"""
        colors = self._colors

        self.tree_builder.max_depth = max_depth
        self.tree_builder.show_hidden = show_hidden

        root = Path(root_path).resolve()
        file_tree = self.tree_builder.build(str(root))

        # Build Rich tree
        rich_tree = Tree(
            f"[bold {colors['primary']}]{file_tree.icon} {root.name or root}[/]",
            guide_style=colors['muted']
        )

        self._add_to_tree(rich_tree, file_tree)

        # Stats
        stats = self._count_files(file_tree)

        self.console.print()
        self.console.print(rich_tree)
        self.console.print()
        self.console.print(
            f"[{colors['muted']}]{stats['dirs']} directories, {stats['files']} files[/]"
        )
        self.console.print()

    def _add_to_tree(self, rich_tree: Tree, node: FileNode):
        """Recursively add nodes to the Rich tree"""
        colors = self._colors

        for child in node.children:
            if child.is_dir:
                style = f"bold {colors['secondary']}"
                label = f"[{style}]{child.icon} {child.display_name}[/]"
                branch = rich_tree.add(label)
                self._add_to_tree(branch, child)
            else:
                # Format size
                size_str = self._format_size(child.size)
                style = colors['accent'] if self._is_code_file(child.path) else "white"
                label = f"[{style}]{child.icon} {child.name}[/]"
                if size_str:
                    label += f" [{colors['muted']}]({size_str})[/]"
                rich_tree.add(label)

    def _count_files(self, node: FileNode) -> Dict[str, int]:
        """Count files and directories"""
        stats = {"files": 0, "dirs": 0}

        if node.is_dir:
            stats["dirs"] += 1
            for child in node.children:
                child_stats = self._count_files(child)
                stats["files"] += child_stats["files"]
                stats["dirs"] += child_stats["dirs"]
        else:
            stats["files"] += 1

        return stats

    def _format_size(self, size: int) -> str:
        """Format file size"""
        if size == 0:
            return ""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}" if unit != 'B' else f"{size}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def _is_code_file(self, path: Path) -> bool:
        """Check if file is a code file"""
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h',
            '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.cs', '.scala'
        }
        return path.suffix.lower() in code_extensions

    def preview_file(self, file_path: str, max_lines: int = 50):
        """Show a preview of a file with syntax highlighting"""
        colors = self._colors
        path = Path(file_path)

        if not path.exists():
            self.console.print(f"[{colors['error']}]File not found: {file_path}[/]")
            return

        if not path.is_file():
            self.console.print(f"[{colors['error']}]Not a file: {file_path}[/]")
            return

        # Get file info
        size = path.stat().st_size
        size_str = self._format_size(size)

        # Try to read content
        try:
            content = path.read_text(encoding='utf-8', errors='replace')
            lines = content.splitlines()
            total_lines = len(lines)

            # Truncate if needed
            if total_lines > max_lines:
                content = '\n'.join(lines[:max_lines])
                truncated = True
            else:
                truncated = False

            # Detect language
            ext = path.suffix.lower().lstrip('.')
            lang_map = {
                'py': 'python', 'js': 'javascript', 'ts': 'typescript',
                'jsx': 'jsx', 'tsx': 'tsx', 'json': 'json', 'md': 'markdown',
                'html': 'html', 'css': 'css', 'yaml': 'yaml', 'yml': 'yaml',
                'sh': 'bash', 'bash': 'bash', 'sql': 'sql', 'rs': 'rust',
                'go': 'go', 'java': 'java', 'c': 'c', 'cpp': 'cpp',
                'rb': 'ruby', 'php': 'php', 'swift': 'swift', 'kt': 'kotlin'
            }
            language = lang_map.get(ext, 'text')

            # Display
            icon = FILE_ICONS.get(path.suffix.lower(), FILE_ICONS['default'])
            title = f"{icon} {path.name} [{colors['muted']}]{size_str} - {total_lines} lines[/]"

            syntax = Syntax(
                content,
                language,
                theme="monokai",
                line_numbers=True,
                word_wrap=True
            )

            self.console.print()
            self.console.print(Panel(
                syntax,
                title=title,
                title_align="left",
                border_style=colors['secondary'],
                box=ROUNDED
            ))

            if truncated:
                self.console.print(
                    f"[{colors['muted']}]... {total_lines - max_lines} more lines[/]"
                )

            self.console.print()

        except UnicodeDecodeError:
            self.console.print(f"[{colors['warning']}]Binary file: {file_path}[/]")
        except Exception as e:
            self.console.print(f"[{colors['error']}]Error reading file: {e}[/]")

    def fuzzy_find(self, pattern: str, root_path: str = ".") -> List[str]:
        """Find files matching a fuzzy pattern"""
        results = []
        root = Path(root_path).resolve()
        pattern_lower = pattern.lower()

        def search(path: Path, depth: int = 0):
            if depth > 10:  # Max depth
                return

            try:
                for item in path.iterdir():
                    if self.tree_builder.should_ignore(item.name):
                        continue

                    name_lower = item.name.lower()

                    # Fuzzy match
                    if self._fuzzy_match(pattern_lower, name_lower):
                        rel_path = str(item.relative_to(root))
                        results.append(rel_path)

                    if item.is_dir() and len(results) < 50:
                        search(item, depth + 1)

            except PermissionError:
                pass

        search(root)
        return sorted(results, key=lambda x: (len(x), x))[:20]

    def _fuzzy_match(self, pattern: str, text: str) -> bool:
        """Simple fuzzy matching"""
        if not pattern:
            return True

        pattern_idx = 0
        for char in text:
            if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
                pattern_idx += 1

        return pattern_idx == len(pattern)

    def interactive_browse(self, start_path: str = ".") -> Optional[str]:
        """Interactive file browser"""
        colors = self._colors
        current_path = Path(start_path).resolve()

        self.console.print()
        self.console.print(f"[bold {colors['secondary']}]File Explorer[/]")
        self.console.print(f"[{colors['muted']}]Commands: [Enter] select, [..] parent, [/] search, [q] quit[/]")

        while True:
            # Show current location
            self.console.print(f"\n[{colors['primary']}]📂 {current_path}[/]")

            # List contents
            try:
                items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                items = [i for i in items if not self.tree_builder.should_ignore(i.name)]
            except PermissionError:
                self.console.print(f"[{colors['error']}]Permission denied[/]")
                current_path = current_path.parent
                continue

            # Display items
            for i, item in enumerate(items[:20], 1):
                icon = FILE_ICONS["folder"] if item.is_dir() else FILE_ICONS.get(item.suffix.lower(), FILE_ICONS["default"])
                style = colors['secondary'] if item.is_dir() else "white"
                suffix = "/" if item.is_dir() else ""
                self.console.print(f"  [{colors['muted']}]{i:2}.[/] [{style}]{icon} {item.name}{suffix}[/]")

            if len(items) > 20:
                self.console.print(f"  [{colors['muted']}]... and {len(items) - 20} more[/]")

            # Get input
            try:
                choice = prompt(
                    HTML(f'<style fg="{colors["primary"]}">Select (number/name/..): </style>')
                ).strip()

                if choice.lower() in ['q', 'quit', 'exit']:
                    return None

                if choice == '..':
                    current_path = current_path.parent
                    continue

                if choice.startswith('/'):
                    # Search mode
                    pattern = choice[1:]
                    results = self.fuzzy_find(pattern, str(current_path))
                    if results:
                        self.console.print(f"\n[{colors['secondary']}]Search results:[/]")
                        for i, r in enumerate(results[:10], 1):
                            self.console.print(f"  [{colors['muted']}]{i}.[/] {r}")
                    continue

                # Try as number
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(items):
                        selected = items[idx]
                        if selected.is_dir():
                            current_path = selected
                        else:
                            return str(selected)
                    continue
                except ValueError:
                    pass

                # Try as name
                for item in items:
                    if item.name.lower() == choice.lower() or item.name.lower().startswith(choice.lower()):
                        if item.is_dir():
                            current_path = item
                        else:
                            return str(item)
                        break

            except (KeyboardInterrupt, EOFError):
                return None


# ═══════════════════════════════════════════════════════════════════════════════
# Quick Functions
# ═══════════════════════════════════════════════════════════════════════════════

def show_tree(path: str = ".", max_depth: int = 3):
    """Quick function to show a directory tree"""
    explorer = FileExplorer()
    explorer.show_tree(path, max_depth)


def preview_file(path: str, max_lines: int = 50):
    """Quick function to preview a file"""
    explorer = FileExplorer()
    explorer.preview_file(path, max_lines)


def find_files(pattern: str, root: str = ".") -> List[str]:
    """Quick function to find files"""
    explorer = FileExplorer()
    return explorer.fuzzy_find(pattern, root)


def browse_files(start: str = ".") -> Optional[str]:
    """Quick function to browse files interactively"""
    explorer = FileExplorer()
    return explorer.interactive_browse(start)


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

file_explorer = FileExplorer()
