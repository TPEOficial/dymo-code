"""
Enhanced Session Manager for Dymo Code
Provides improved conversation management with previews and quick resume
Inspired by OpenCode's session handling
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED

from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML


# ═══════════════════════════════════════════════════════════════════════════════
# Session Data
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SessionInfo:
    """Information about a conversation session"""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    model: str = ""
    first_message: str = ""
    last_message: str = ""
    tags: List[str] = field(default_factory=list)

    @property
    def age(self) -> str:
        """Get human-readable age"""
        now = datetime.now()
        delta = now - self.updated_at

        if delta.days > 30:
            return f"{delta.days // 30}mo ago"
        elif delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds > 3600:
            return f"{delta.seconds // 3600}h ago"
        elif delta.seconds > 60:
            return f"{delta.seconds // 60}m ago"
        else:
            return "just now"


# ═══════════════════════════════════════════════════════════════════════════════
# Session Manager
# ═══════════════════════════════════════════════════════════════════════════════

class SessionManager:
    """
    Enhanced session manager with preview and quick resume.
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
                "accent": "#EC4899",
            }

    def _get_sessions(self) -> List[SessionInfo]:
        """Get all sessions from history manager"""
        try:
            from .history import history_manager

            conversations = history_manager.get_recent_conversations(50)
            sessions = []

            for conv in conversations:
                # Extract first and last messages
                messages = conv.get("messages", [])
                first_msg = ""
                last_msg = ""

                for msg in messages:
                    if msg.get("role") == "user":
                        if not first_msg:
                            first_msg = msg.get("content", "")[:100]
                        last_msg = msg.get("content", "")[:100]

                # Parse dates
                try:
                    created = datetime.fromisoformat(conv.get("created_at", ""))
                except:
                    created = datetime.now()

                try:
                    updated = datetime.fromisoformat(conv.get("updated_at", ""))
                except:
                    updated = created

                sessions.append(SessionInfo(
                    id=conv.get("id", ""),
                    title=conv.get("title", "Untitled"),
                    created_at=created,
                    updated_at=updated,
                    message_count=conv.get("message_count", len(messages)),
                    model=conv.get("model", ""),
                    first_message=first_msg,
                    last_message=last_msg,
                ))

            return sessions

        except ImportError:
            return []

    def list_sessions(self, limit: int = 10, show_preview: bool = True):
        """List recent sessions with optional preview"""
        colors = self._colors
        sessions = self._get_sessions()[:limit]

        if not sessions:
            self.console.print(f"\n[{colors['muted']}]No previous sessions found.[/]\n")
            return

        self.console.print(f"\n[bold {colors['secondary']}]Recent Sessions[/]\n")

        for i, session in enumerate(sessions, 1):
            # Session header
            header = Text()
            header.append(f"{i}. ", style=f"bold {colors['accent']}")
            header.append(session.title[:40], style=f"bold {colors['primary']}")
            header.append(f" [{session.age}]", style=colors['muted'])

            self.console.print(header)

            if show_preview and session.first_message:
                preview = session.first_message[:60]
                if len(session.first_message) > 60:
                    preview += "..."
                self.console.print(f"   [{colors['muted']}]> {preview}[/]")

            # Stats
            stats = f"   [{colors['muted']}]{session.message_count} messages"
            if session.model:
                stats += f" • {session.model}"
            stats += f"[/]"
            self.console.print(stats)
            self.console.print()

        self.console.print(f"[{colors['muted']}]Use /resume <number> or /resume <id> to continue[/]")
        self.console.print(f"[{colors['muted']}]Use /history delete <id> to delete • /history rename <id> <name> to rename[/]\n")

    def show_session_detail(self, session_id: str):
        """Show detailed information about a session"""
        colors = self._colors

        try:
            from .history import history_manager

            conv = history_manager.get_conversation(session_id)
            if not conv:
                self.console.print(f"[{colors['error']}]Session not found: {session_id}[/]")
                return

            # Header
            title = conv.get("title", "Untitled")
            self.console.print(f"\n[bold {colors['primary']}]{title}[/]")
            self.console.print("─" * 50, style=colors['muted'])

            # Metadata
            messages = conv.get("messages", [])
            created = conv.get("created_at", "")
            updated = conv.get("updated_at", "")

            self.console.print(f"[{colors['muted']}]ID:[/] {session_id}")
            self.console.print(f"[{colors['muted']}]Messages:[/] {len(messages)}")
            self.console.print(f"[{colors['muted']}]Created:[/] {created}")
            self.console.print(f"[{colors['muted']}]Updated:[/] {updated}")
            self.console.print()

            # Show last few messages
            self.console.print(f"[bold {colors['secondary']}]Recent messages:[/]")
            user_messages = [m for m in messages if m.get("role") == "user"]

            for msg in user_messages[-3:]:
                content = msg.get("content", "")[:80]
                if len(msg.get("content", "")) > 80:
                    content += "..."
                self.console.print(f"  [{colors['accent']}]>[/] {content}")

            self.console.print()

        except ImportError:
            self.console.print(f"[{colors['error']}]History manager not available.[/]")

    def interactive_resume(self) -> Optional[str]:
        """Interactive session selection"""
        colors = self._colors
        sessions = self._get_sessions()

        if not sessions:
            self.console.print(f"\n[{colors['muted']}]No previous sessions found.[/]\n")
            return None

        self.console.print(f"\n[bold {colors['secondary']}]Resume Session[/]")
        self.console.print(f"[{colors['muted']}]Select a session to continue:[/]\n")

        # Show sessions
        for i, session in enumerate(sessions[:10], 1):
            header = Text()
            header.append(f"{i:2}. ", style=f"bold {colors['accent']}")
            header.append(session.title[:35], style=f"bold white")
            header.append(f" ({session.age})", style=colors['muted'])
            self.console.print(header)

        self.console.print()

        try:
            choice = prompt(
                HTML(f'<style fg="{colors["primary"]}">Select (1-10 or q): </style>')
            ).strip()

            if choice.lower() in ['q', 'quit', '']:
                return None

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(sessions):
                    return sessions[idx].id
            except ValueError:
                # Try matching by title
                choice_lower = choice.lower()
                for session in sessions:
                    if choice_lower in session.title.lower():
                        return session.id

            return None

        except (KeyboardInterrupt, EOFError):
            return None

    def get_last_session(self) -> Optional[str]:
        """Get the most recent session ID"""
        sessions = self._get_sessions()
        if sessions:
            return sessions[0].id
        return None

    def quick_resume_last(self) -> Optional[str]:
        """Quickly resume the last session with confirmation"""
        colors = self._colors
        sessions = self._get_sessions()

        if not sessions:
            return None

        last = sessions[0]

        self.console.print()
        self.console.print(f"[{colors['muted']}]Last session:[/] [bold]{last.title}[/]")
        self.console.print(f"[{colors['muted']}]{last.message_count} messages • {last.age}[/]")

        if last.first_message:
            preview = last.first_message[:50]
            if len(last.first_message) > 50:
                preview += "..."
            self.console.print(f"[{colors['muted']}]> {preview}[/]")

        self.console.print()

        try:
            choice = prompt(
                HTML(f'<style fg="{colors["primary"]}">Resume? (Y/n): </style>')
            ).strip().lower()

            if choice in ['', 'y', 'yes', 's', 'si']:
                return last.id

        except (KeyboardInterrupt, EOFError):
            pass

        return None

    def search_sessions(self, query: str) -> List[SessionInfo]:
        """Search sessions by title or content"""
        sessions = self._get_sessions()
        query_lower = query.lower()

        results = []
        for session in sessions:
            if (query_lower in session.title.lower() or
                query_lower in session.first_message.lower() or
                query_lower in session.last_message.lower()):
                results.append(session)

        return results

    def show_search_results(self, query: str):
        """Search and display results"""
        colors = self._colors
        results = self.search_sessions(query)

        if not results:
            self.console.print(f"\n[{colors['muted']}]No sessions found matching '{query}'[/]\n")
            return

        self.console.print(f"\n[bold {colors['secondary']}]Found {len(results)} sessions:[/]\n")

        for i, session in enumerate(results[:10], 1):
            header = Text()
            header.append(f"{i}. ", style=f"bold {colors['accent']}")
            header.append(session.title[:40], style="bold white")
            header.append(f" [{session.age}]", style=colors['muted'])
            self.console.print(header)

            if session.first_message:
                preview = session.first_message[:50]
                self.console.print(f"   [{colors['muted']}]> {preview}...[/]")

        self.console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# Export View (for sharing/saving)
# ═══════════════════════════════════════════════════════════════════════════════

class SessionExporter:
    """Export sessions to various formats"""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console(force_terminal=True)

    def to_markdown(self, session_id: str) -> Optional[str]:
        """Export session to markdown"""
        try:
            from .history import history_manager

            conv = history_manager.get_conversation(session_id)
            if not conv:
                return None

            lines = []
            lines.append(f"# {conv.get('title', 'Untitled')}")
            lines.append("")
            lines.append(f"*Created: {conv.get('created_at', '')}*")
            lines.append("")
            lines.append("---")
            lines.append("")

            for msg in conv.get("messages", []):
                role = msg.get("role", "")
                content = msg.get("content", "")

                if role == "user":
                    lines.append(f"## User")
                    lines.append("")
                    lines.append(content)
                    lines.append("")
                elif role == "assistant":
                    lines.append(f"## Assistant")
                    lines.append("")
                    lines.append(content)
                    lines.append("")

            return "\n".join(lines)

        except ImportError:
            return None

    def save_to_file(self, session_id: str, file_path: str) -> bool:
        """Save session to file"""
        content = self.to_markdown(session_id)
        if content:
            try:
                Path(file_path).write_text(content, encoding='utf-8')
                return True
            except Exception:
                pass
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instances
# ═══════════════════════════════════════════════════════════════════════════════

session_manager = SessionManager()
session_exporter = SessionExporter()
