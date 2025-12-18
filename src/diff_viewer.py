"""
Interactive Diff Viewer for Dymo Code
Allows reviewing and accepting/rejecting changes line by line
Inspired by OpenCode's diff handling
"""

import difflib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED

from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.formatted_text import HTML


# ═══════════════════════════════════════════════════════════════════════════════
# Diff Types
# ═══════════════════════════════════════════════════════════════════════════════

class ChangeType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    CONTEXT = "context"


class ChangeStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


# ═══════════════════════════════════════════════════════════════════════════════
# Diff Line
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DiffLine:
    """Represents a single line in a diff"""
    line_number_old: Optional[int]
    line_number_new: Optional[int]
    content: str
    change_type: ChangeType
    status: ChangeStatus = ChangeStatus.PENDING


@dataclass
class DiffHunk:
    """A group of related changes"""
    start_old: int
    start_new: int
    lines: List[DiffLine] = field(default_factory=list)
    status: ChangeStatus = ChangeStatus.PENDING

    @property
    def additions(self) -> int:
        return sum(1 for l in self.lines if l.change_type == ChangeType.ADDED)

    @property
    def deletions(self) -> int:
        return sum(1 for l in self.lines if l.change_type == ChangeType.REMOVED)


@dataclass
class FileDiff:
    """Complete diff for a file"""
    file_path: str
    old_content: str
    new_content: str
    hunks: List[DiffHunk] = field(default_factory=list)
    is_new_file: bool = False
    is_deleted: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# Diff Generator
# ═══════════════════════════════════════════════════════════════════════════════

class DiffGenerator:
    """Generates structured diffs from content"""

    @staticmethod
    def generate(
        file_path: str,
        old_content: str,
        new_content: str,
        context_lines: int = 3
    ) -> FileDiff:
        """Generate a structured diff between old and new content"""

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        # Handle new file
        if not old_content:
            diff = FileDiff(
                file_path=file_path,
                old_content=old_content,
                new_content=new_content,
                is_new_file=True
            )
            hunk = DiffHunk(start_old=0, start_new=1)
            for i, line in enumerate(new_lines, 1):
                hunk.lines.append(DiffLine(
                    line_number_old=None,
                    line_number_new=i,
                    content=line.rstrip('\n\r'),
                    change_type=ChangeType.ADDED
                ))
            diff.hunks.append(hunk)
            return diff

        # Handle deleted file
        if not new_content:
            diff = FileDiff(
                file_path=file_path,
                old_content=old_content,
                new_content=new_content,
                is_deleted=True
            )
            hunk = DiffHunk(start_old=1, start_new=0)
            for i, line in enumerate(old_lines, 1):
                hunk.lines.append(DiffLine(
                    line_number_old=i,
                    line_number_new=None,
                    content=line.rstrip('\n\r'),
                    change_type=ChangeType.REMOVED
                ))
            diff.hunks.append(hunk)
            return diff

        # Generate unified diff
        diff = FileDiff(
            file_path=file_path,
            old_content=old_content,
            new_content=new_content
        )

        # Use difflib to get opcodes
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        opcodes = matcher.get_opcodes()

        current_hunk = None

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                # Context lines
                if current_hunk:
                    # Add trailing context
                    for k, (old_idx, new_idx) in enumerate(zip(range(i1, min(i1 + context_lines, i2)),
                                                               range(j1, min(j1 + context_lines, j2)))):
                        current_hunk.lines.append(DiffLine(
                            line_number_old=old_idx + 1,
                            line_number_new=new_idx + 1,
                            content=old_lines[old_idx].rstrip('\n\r'),
                            change_type=ChangeType.CONTEXT
                        ))
                    diff.hunks.append(current_hunk)
                    current_hunk = None
            else:
                # Start new hunk if needed
                if current_hunk is None:
                    current_hunk = DiffHunk(
                        start_old=max(1, i1 - context_lines + 1),
                        start_new=max(1, j1 - context_lines + 1)
                    )
                    # Add leading context
                    ctx_start_old = max(0, i1 - context_lines)
                    ctx_start_new = max(0, j1 - context_lines)
                    for k in range(context_lines):
                        old_idx = ctx_start_old + k
                        new_idx = ctx_start_new + k
                        if old_idx < i1 and old_idx < len(old_lines):
                            current_hunk.lines.append(DiffLine(
                                line_number_old=old_idx + 1,
                                line_number_new=new_idx + 1,
                                content=old_lines[old_idx].rstrip('\n\r'),
                                change_type=ChangeType.CONTEXT
                            ))

                if tag == 'replace':
                    # Show deletions then additions
                    for old_idx in range(i1, i2):
                        current_hunk.lines.append(DiffLine(
                            line_number_old=old_idx + 1,
                            line_number_new=None,
                            content=old_lines[old_idx].rstrip('\n\r'),
                            change_type=ChangeType.REMOVED
                        ))
                    for new_idx in range(j1, j2):
                        current_hunk.lines.append(DiffLine(
                            line_number_old=None,
                            line_number_new=new_idx + 1,
                            content=new_lines[new_idx].rstrip('\n\r'),
                            change_type=ChangeType.ADDED
                        ))

                elif tag == 'delete':
                    for old_idx in range(i1, i2):
                        current_hunk.lines.append(DiffLine(
                            line_number_old=old_idx + 1,
                            line_number_new=None,
                            content=old_lines[old_idx].rstrip('\n\r'),
                            change_type=ChangeType.REMOVED
                        ))

                elif tag == 'insert':
                    for new_idx in range(j1, j2):
                        current_hunk.lines.append(DiffLine(
                            line_number_old=None,
                            line_number_new=new_idx + 1,
                            content=new_lines[new_idx].rstrip('\n\r'),
                            change_type=ChangeType.ADDED
                        ))

        # Don't forget the last hunk
        if current_hunk:
            diff.hunks.append(current_hunk)

        return diff


# ═══════════════════════════════════════════════════════════════════════════════
# Interactive Diff Viewer
# ═══════════════════════════════════════════════════════════════════════════════

class InteractiveDiffViewer:
    """
    Interactive diff viewer that allows accepting/rejecting changes.
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console(force_terminal=True)
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
            }

    def display_diff(self, diff: FileDiff, interactive: bool = False) -> Optional[str]:
        """
        Display a diff with optional interactive review.

        Args:
            diff: The FileDiff to display
            interactive: If True, allow accepting/rejecting changes

        Returns:
            The final content after review, or None if cancelled
        """
        colors = self._colors

        # Header
        if diff.is_new_file:
            title = f"[bold {colors['success']}]New file: {diff.file_path}[/]"
        elif diff.is_deleted:
            title = f"[bold {colors['error']}]Deleted: {diff.file_path}[/]"
        else:
            total_add = sum(h.additions for h in diff.hunks)
            total_del = sum(h.deletions for h in diff.hunks)
            title = f"[bold]Modified: {diff.file_path}[/] "
            title += f"[{colors['success']}]+{total_add}[/] "
            title += f"[{colors['error']}]-{total_del}[/]"

        self.console.print()
        self.console.print(title)
        self.console.print("─" * 60, style=colors['muted'])

        # Display hunks
        for hunk_idx, hunk in enumerate(diff.hunks):
            self._display_hunk(hunk, hunk_idx, len(diff.hunks))

        if interactive:
            return self._interactive_review(diff)
        else:
            return diff.new_content

    def _display_hunk(self, hunk: DiffHunk, index: int, total: int):
        """Display a single hunk"""
        colors = self._colors

        # Hunk header
        header = Text()
        header.append(f"@@ ", style=f"bold {colors['secondary']}")
        header.append(f"Hunk {index + 1}/{total} ", style=colors['muted'])
        header.append(f"(+{hunk.additions} -{hunk.deletions})", style=colors['muted'])
        self.console.print(header)

        # Lines
        for line in hunk.lines:
            self._display_line(line)

        self.console.print()

    def _display_line(self, line: DiffLine):
        """Display a single diff line"""
        colors = self._colors

        text = Text()

        # Line number
        if line.line_number_old:
            text.append(f"{line.line_number_old:4d}", style=f"dim {colors['muted']}")
        else:
            text.append("    ", style="dim")

        text.append(" ", style="dim")

        if line.line_number_new:
            text.append(f"{line.line_number_new:4d}", style=f"dim {colors['muted']}")
        else:
            text.append("    ", style="dim")

        text.append(" ", style="dim")

        # Change indicator and content
        if line.change_type == ChangeType.ADDED:
            text.append("+ ", style=f"bold {colors['success']}")
            text.append(line.content, style=colors['success'])
        elif line.change_type == ChangeType.REMOVED:
            text.append("- ", style=f"bold {colors['error']}")
            text.append(line.content, style=colors['error'])
        else:
            text.append("  ", style="dim")
            text.append(line.content, style="white")

        # Status indicator
        if line.status == ChangeStatus.ACCEPTED:
            text.append(" [v]", style=f"bold {colors['success']}")
        elif line.status == ChangeStatus.REJECTED:
            text.append(" [x]", style=f"bold {colors['error']}")

        self.console.print(text)

    def _interactive_review(self, diff: FileDiff) -> Optional[str]:
        """Interactive review mode"""
        colors = self._colors

        self.console.print()
        self.console.print(f"[bold {colors['secondary']}]Interactive Review[/]")
        self.console.print(f"[{colors['muted']}]Commands: [a]ccept all, [r]eject all, [h]unk review, [q]uit[/]")
        self.console.print()

        try:
            choice = prompt(
                HTML(f'<style fg="{colors["primary"]}">Review action: </style>')
            ).strip().lower()

            if choice in ['a', 'accept']:
                # Accept all changes
                for hunk in diff.hunks:
                    hunk.status = ChangeStatus.ACCEPTED
                    for line in hunk.lines:
                        line.status = ChangeStatus.ACCEPTED
                self.console.print(f"[{colors['success']}]All changes accepted![/]")
                return diff.new_content

            elif choice in ['r', 'reject']:
                # Reject all changes
                for hunk in diff.hunks:
                    hunk.status = ChangeStatus.REJECTED
                    for line in hunk.lines:
                        line.status = ChangeStatus.REJECTED
                self.console.print(f"[{colors['warning']}]All changes rejected.[/]")
                return diff.old_content

            elif choice in ['h', 'hunk']:
                # Review hunk by hunk
                return self._review_hunks(diff)

            elif choice in ['q', 'quit']:
                self.console.print(f"[{colors['muted']}]Review cancelled.[/]")
                return None

            else:
                # Default: accept all
                return diff.new_content

        except (KeyboardInterrupt, EOFError):
            return None

    def _review_hunks(self, diff: FileDiff) -> str:
        """Review changes hunk by hunk"""
        colors = self._colors

        for idx, hunk in enumerate(diff.hunks):
            self.console.print(f"\n[bold]Hunk {idx + 1}/{len(diff.hunks)}[/]")
            self._display_hunk(hunk, idx, len(diff.hunks))

            try:
                choice = prompt(
                    HTML(f'<style fg="{colors["primary"]}">[a]ccept/[r]eject/[s]kip: </style>')
                ).strip().lower()

                if choice in ['a', 'accept', '']:
                    hunk.status = ChangeStatus.ACCEPTED
                    self.console.print(f"[{colors['success']}]Hunk accepted[/]")
                elif choice in ['r', 'reject']:
                    hunk.status = ChangeStatus.REJECTED
                    self.console.print(f"[{colors['warning']}]Hunk rejected[/]")
                else:
                    self.console.print(f"[{colors['muted']}]Skipped[/]")

            except (KeyboardInterrupt, EOFError):
                break

        # Build final content based on accepted/rejected hunks
        return self._build_result(diff)

    def _build_result(self, diff: FileDiff) -> str:
        """Build the final content based on hunk statuses"""
        if all(h.status == ChangeStatus.ACCEPTED for h in diff.hunks):
            return diff.new_content
        elif all(h.status == ChangeStatus.REJECTED for h in diff.hunks):
            return diff.old_content
        else:
            # Partial acceptance - need to merge
            # For simplicity, if any hunk is accepted, use new content
            # A more sophisticated implementation would merge line by line
            accepted_count = sum(1 for h in diff.hunks if h.status == ChangeStatus.ACCEPTED)
            if accepted_count > len(diff.hunks) // 2:
                return diff.new_content
            else:
                return diff.old_content


# ═══════════════════════════════════════════════════════════════════════════════
# Quick Diff Display (Non-interactive)
# ═══════════════════════════════════════════════════════════════════════════════

def show_diff(
    file_path: str,
    old_content: str,
    new_content: str,
    console: Optional[Console] = None
):
    """Quick function to display a diff"""
    diff = DiffGenerator.generate(file_path, old_content, new_content)
    viewer = InteractiveDiffViewer(console)
    viewer.display_diff(diff, interactive=False)


def review_diff(
    file_path: str,
    old_content: str,
    new_content: str,
    console: Optional[Console] = None
) -> Optional[str]:
    """Show diff with interactive review, returns final content"""
    diff = DiffGenerator.generate(file_path, old_content, new_content)
    viewer = InteractiveDiffViewer(console)
    return viewer.display_diff(diff, interactive=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

diff_viewer = InteractiveDiffViewer()
