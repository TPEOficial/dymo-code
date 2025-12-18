"""
Command Permissions System for Dymo Code
Handles permission prompts before executing potentially dangerous commands.
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Optional, Set, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED
from rich.live import Live

# Keyboard input
if sys.platform == "win32":
    import msvcrt
else:
    import tty
    import termios
    import select


class PermissionLevel(Enum):
    """Permission levels for commands"""
    DENY = "deny"
    ONCE = "once"
    SESSION = "session"
    ALWAYS = "always"


# ═══════════════════════════════════════════════════════════════════════════════
# Safe Commands Configuration
# ═══════════════════════════════════════════════════════════════════════════════

# Commands that are considered safe and don't require permission
SAFE_COMMAND_PATTERNS = [
    # Directory listing
    r"^ls\b",
    r"^dir\b",
    r"^pwd\b",
    r"^cd\b",

    # File reading (read-only)
    r"^cat\b",
    r"^head\b",
    r"^tail\b",
    r"^less\b",
    r"^more\b",
    r"^type\b",  # Windows

    # Information commands
    r"^echo\b",
    r"^which\b",
    r"^where\b",  # Windows
    r"^whereis\b",
    r"^whoami\b",
    r"^hostname\b",
    r"^uname\b",
    r"^date\b",
    r"^time\b",
    r"^uptime\b",

    # Search/find (read-only)
    r"^find\b.*-name\b",
    r"^find\b.*-type\b",
    r"^grep\b",
    r"^rg\b",  # ripgrep
    r"^ag\b",  # silver searcher
    r"^ack\b",
    r"^fd\b",  # fd-find

    # Version/help
    r".*--version$",
    r".*-v$",
    r".*--help$",
    r".*-h$",
    r".*\?$",

    # Git (read-only)
    r"^git\s+status\b",
    r"^git\s+log\b",
    r"^git\s+diff\b",
    r"^git\s+branch\b",
    r"^git\s+remote\b",
    r"^git\s+show\b",
    r"^git\s+blame\b",
    r"^git\s+config\s+--list\b",
    r"^git\s+config\s+--get\b",

    # Node/NPM (read-only)
    r"^npm\s+list\b",
    r"^npm\s+ls\b",
    r"^npm\s+outdated\b",
    r"^npm\s+view\b",
    r"^npm\s+info\b",
    r"^npm\s+search\b",
    r"^npm\s+--version\b",
    r"^node\s+--version\b",
    r"^npx\s+--version\b",

    # Python (read-only)
    r"^python\s+--version\b",
    r"^python3\s+--version\b",
    r"^pip\s+list\b",
    r"^pip\s+show\b",
    r"^pip\s+freeze\b",
    r"^pip3\s+list\b",
    r"^pip3\s+show\b",

    # System info
    r"^df\b",
    r"^du\b",
    r"^free\b",
    r"^top\b",
    r"^htop\b",
    r"^ps\b",
    r"^env\b",
    r"^printenv\b",
    r"^set$",

    # Network info (read-only)
    r"^ping\b",
    r"^nslookup\b",
    r"^dig\b",
    r"^host\b",
    r"^traceroute\b",
    r"^tracert\b",
    r"^netstat\b",
    r"^ifconfig\b",
    r"^ipconfig\b",
    r"^ip\s+addr\b",
    r"^ip\s+link\b",
    r"^ip\s+route\b",

    # File info (read-only)
    r"^file\b",
    r"^stat\b",
    r"^wc\b",
    r"^md5sum\b",
    r"^sha256sum\b",
    r"^shasum\b",
]

# Dangerous command patterns that should ALWAYS require permission
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+\*",
    r"rm\s+-rf\s+~",
    r"mkfs\b",
    r"dd\s+if=",
    r":\(\)\{",  # fork bomb
    r">\s*/dev/sd",
    r"chmod\s+-R\s+777",
    r"curl.*\|\s*(ba)?sh",
    r"wget.*\|\s*(ba)?sh",
    r"eval\s*\(",
    r"\$\(\s*curl",
    r"\$\(\s*wget",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Keyboard Input
# ═══════════════════════════════════════════════════════════════════════════════

def _get_key() -> str:
    """Get a single keypress cross-platform"""
    if sys.platform == "win32":
        key = msvcrt.getwch()
        if key == '\xe0':
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
            if ch == '\x1b':
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
# Permission Selector UI
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PermissionOption:
    """Option for permission selector"""
    id: str
    label: str
    description: str
    icon: str
    level: PermissionLevel


PERMISSION_OPTIONS = [
    PermissionOption(
        id="once",
        label="Allow once",
        description="Execute this command only this time",
        icon="1",
        level=PermissionLevel.ONCE
    ),
    PermissionOption(
        id="session",
        label="Allow this session",
        description="Allow this command for the rest of the session",
        icon="S",
        level=PermissionLevel.SESSION
    ),
    PermissionOption(
        id="always",
        label="Always allow",
        description="Remember this permission permanently",
        icon="A",
        level=PermissionLevel.ALWAYS
    ),
    PermissionOption(
        id="deny",
        label="Deny",
        description="Don't execute this command",
        icon="D",
        level=PermissionLevel.DENY
    ),
]


def _get_colors() -> Dict[str, str]:
    """Get theme colors"""
    try:
        from .themes import theme_manager
        colors = theme_manager.colors
        return {
            "primary": colors.get("primary", "#7C3AED"),
            "secondary": colors.get("secondary", "#06B6D4"),
            "warning": colors.get("warning", "#F59E0B"),
            "error": colors.get("error", "#EF4444"),
            "success": colors.get("success", "#10B981"),
            "muted": colors.get("muted", "#9CA3AF"),
            "text": "#FFFFFF",
            "text_dim": "#B4B4B4",
            "border": colors.get("border", "#374151"),
        }
    except:
        return {
            "primary": "#7C3AED",
            "secondary": "#06B6D4",
            "warning": "#F59E0B",
            "error": "#EF4444",
            "success": "#10B981",
            "muted": "#9CA3AF",
            "text": "#FFFFFF",
            "text_dim": "#B4B4B4",
            "border": "#374151",
        }


def show_permission_selector(command: str, console: Optional[Console] = None) -> PermissionLevel:
    """
    Show an interactive selector for command permission.
    Returns the selected permission level.
    """
    console = console or Console(force_terminal=True)
    colors = _get_colors()
    selected_idx = 0
    options = PERMISSION_OPTIONS

    # Stop any running spinner to prevent conflicts with Live display
    spinner_was_running = False
    try:
        from .terminal_ui import terminal_ui
        # Check if spinner is running and stop it
        if terminal_ui.spinner._running:
            spinner_was_running = True
            terminal_ui.spinner.stop()
            # Small delay to ensure spinner thread has stopped
            import time
            time.sleep(0.1)
    except:
        pass

    def render() -> Panel:
        lines = []

        # Command display
        cmd_text = Text()
        cmd_text.append("  Command: ", style=f"bold {colors['muted']}")
        # Truncate long commands
        display_cmd = command if len(command) <= 60 else command[:57] + "..."
        cmd_text.append(display_cmd, style=f"bold {colors['warning']}")
        lines.append(cmd_text)
        lines.append(Text(""))

        # Options
        for i, opt in enumerate(options):
            is_selected = (i == selected_idx)
            opt_text = Text()

            # Selection indicator
            if is_selected:
                opt_text.append(" > ", style=f"bold {colors['primary']}")
            else:
                opt_text.append("   ", style="")

            # Shortcut key
            opt_text.append(f"[{opt.icon}] ", style=f"bold {colors['secondary']}")

            # Label
            if is_selected:
                opt_text.append(opt.label, style=f"bold {colors['text']}")
            else:
                opt_text.append(opt.label, style=colors['text_dim'])

            # Description
            opt_text.append(f"  {opt.description}", style=colors['muted'])

            lines.append(opt_text)

        # Footer
        lines.append(Text(""))
        footer = Text()
        footer.append("  ", style="")
        footer.append("^/v", style=f"bold {colors['muted']}")
        footer.append(" Navigate  ", style=colors['muted'])
        footer.append("Enter", style=f"bold {colors['muted']}")
        footer.append(" Select  ", style=colors['muted'])
        footer.append("1/S/A/D", style=f"bold {colors['muted']}")
        footer.append(" Quick select", style=colors['muted'])
        lines.append(footer)

        content = Text("\n").join(lines)

        return Panel(
            content,
            title=f"[bold {colors['warning']}]Command Permission Required[/]",
            border_style=colors['warning'],
            box=ROUNDED,
            padding=(1, 2)
        )

    # Clear the line and show selector
    console.print("\r\033[K", end="")  # Clear current line

    result = PermissionLevel.DENY  # Default result
    try:
        with Live(
            render(),
            console=console,
            refresh_per_second=10,
            transient=True,
            vertical_overflow="visible",
            auto_refresh=False  # Manual refresh only
        ) as live:
            live.refresh()  # Initial render
            while True:
                key = _get_key()

                if key == 'up':
                    selected_idx = (selected_idx - 1) % len(options)
                    live.update(render(), refresh=True)
                elif key == 'down':
                    selected_idx = (selected_idx + 1) % len(options)
                    live.update(render(), refresh=True)
                elif key == 'enter':
                    result = options[selected_idx].level
                    break
                elif key in ('esc', 'ctrl+c'):
                    result = PermissionLevel.DENY
                    break
                # Quick select shortcuts
                elif key == '1':
                    result = PermissionLevel.ONCE
                    break
                elif key.lower() == 's':
                    result = PermissionLevel.SESSION
                    break
                elif key.lower() == 'a':
                    result = PermissionLevel.ALWAYS
                    break
                elif key.lower() == 'd' or key.lower() == 'n':
                    result = PermissionLevel.DENY
                    break

        return result

    except Exception as e:
        console.print(f"[red]Permission selector error: {e}[/]")
        return PermissionLevel.DENY
    finally:
        # Restore spinner if it was running
        if spinner_was_running:
            try:
                from .terminal_ui import terminal_ui
                terminal_ui.start_processing("executing")
            except:
                pass


# ═══════════════════════════════════════════════════════════════════════════════
# Command Permissions Manager
# ═══════════════════════════════════════════════════════════════════════════════

class CommandPermissions:
    """
    Manages command permissions with persistent storage.
    """

    def __init__(self):
        self._permissions_file: Optional[Path] = None
        self._permanent_permissions: Dict[str, str] = {}  # command -> "allow" | "deny"
        self._session_permissions: Set[str] = set()  # commands allowed this session
        self._denied_session: Set[str] = set()  # commands denied this session
        self._console = Console(force_terminal=True)
        self._load_permissions()

    def _get_permissions_file(self) -> Path:
        """Get the permissions file path"""
        if self._permissions_file is None:
            try:
                from .storage import get_config_directory
                self._permissions_file = get_config_directory() / "command_permissions.json"
            except:
                self._permissions_file = Path.home() / ".dymo-code" / "command_permissions.json"
        return self._permissions_file

    def _load_permissions(self):
        """Load permanent permissions from file"""
        try:
            perm_file = self._get_permissions_file()
            if perm_file.exists():
                with open(perm_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._permanent_permissions = data.get("allowed", {})
        except Exception:
            self._permanent_permissions = {}

    def _save_permissions(self):
        """Save permanent permissions to file"""
        try:
            perm_file = self._get_permissions_file()
            perm_file.parent.mkdir(parents=True, exist_ok=True)
            with open(perm_file, "w", encoding="utf-8") as f:
                json.dump({"allowed": self._permanent_permissions}, f, indent=2)
        except Exception as e:
            pass  # Silent fail

    def _normalize_command(self, command: str) -> str:
        """Normalize a command for comparison"""
        # Strip and lowercase for comparison
        return command.strip()

    def _is_safe_command(self, command: str) -> bool:
        """Check if a command matches safe patterns"""
        cmd = command.strip()
        for pattern in SAFE_COMMAND_PATTERNS:
            if re.match(pattern, cmd, re.IGNORECASE):
                return True
        return False

    def _is_dangerous_command(self, command: str) -> bool:
        """Check if a command matches dangerous patterns"""
        cmd = command.strip()
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return True
        return False

    def _get_command_signature(self, command: str) -> str:
        """
        Get a signature for a command that can be used for permission matching.
        This extracts the base command pattern for comparison.
        """
        cmd = command.strip()
        # Get base command (first word)
        parts = cmd.split()
        if not parts:
            return cmd

        base = parts[0]

        # For some commands, include subcommands
        if base in ("git", "npm", "pip", "pip3", "docker", "kubectl"):
            if len(parts) > 1:
                return f"{base} {parts[1]}"

        return base

    def check_permission(self, command: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a command is allowed to execute.

        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
        """
        normalized = self._normalize_command(command)
        signature = self._get_command_signature(command)

        # Check if it's a safe command (always allowed)
        if self._is_safe_command(normalized):
            return (True, "safe_command")

        # Check session denied
        if normalized in self._denied_session or signature in self._denied_session:
            return (False, "denied_session")

        # Check session allowed
        if normalized in self._session_permissions or signature in self._session_permissions:
            return (True, "session")

        # Check permanent permissions
        if normalized in self._permanent_permissions:
            return (self._permanent_permissions[normalized] == "allow", "permanent")
        if signature in self._permanent_permissions:
            return (self._permanent_permissions[signature] == "allow", "permanent")

        # Not found - needs permission
        return (False, None)

    def request_permission(self, command: str) -> bool:
        """
        Request permission for a command using the interactive selector.

        Returns:
            True if allowed, False if denied
        """
        normalized = self._normalize_command(command)
        signature = self._get_command_signature(command)

        # Show danger warning for dangerous commands
        if self._is_dangerous_command(normalized):
            colors = _get_colors()
            self._console.print()
            self._console.print(Panel(
                f"[bold {colors['error']}]WARNING:[/] This command appears to be potentially dangerous!\n"
                f"Command: [bold]{command[:80]}[/]",
                border_style=colors['error'],
                title="Dangerous Command Detected"
            ))

        # Show permission selector
        permission = show_permission_selector(command, self._console)

        if permission == PermissionLevel.ONCE:
            return True

        elif permission == PermissionLevel.SESSION:
            self._session_permissions.add(signature)
            return True

        elif permission == PermissionLevel.ALWAYS:
            self._permanent_permissions[signature] = "allow"
            self._save_permissions()
            return True

        else:  # DENY
            self._denied_session.add(signature)
            return False

    def add_permanent_permission(self, command: str, allowed: bool = True):
        """Add a permanent permission for a command"""
        signature = self._get_command_signature(command)
        self._permanent_permissions[signature] = "allow" if allowed else "deny"
        self._save_permissions()

    def remove_permission(self, command: str):
        """Remove a permanent permission"""
        signature = self._get_command_signature(command)
        normalized = self._normalize_command(command)

        if signature in self._permanent_permissions:
            del self._permanent_permissions[signature]
        if normalized in self._permanent_permissions:
            del self._permanent_permissions[normalized]

        self._save_permissions()

    def clear_session_permissions(self):
        """Clear all session permissions"""
        self._session_permissions.clear()
        self._denied_session.clear()

    def clear_all_permissions(self):
        """Clear all permissions (permanent and session)"""
        self._permanent_permissions.clear()
        self._session_permissions.clear()
        self._denied_session.clear()
        self._save_permissions()

    def get_all_permanent_permissions(self) -> Dict[str, str]:
        """Get all permanent permissions"""
        return self._permanent_permissions.copy()

    def is_enabled(self) -> bool:
        """Check if permission system is enabled"""
        try:
            from .storage import user_config
            return user_config.get("command_permissions_enabled", True)
        except:
            return True

    def set_enabled(self, enabled: bool):
        """Enable or disable the permission system"""
        try:
            from .storage import user_config
            user_config.set("command_permissions_enabled", enabled)
        except:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

command_permissions = CommandPermissions()


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════

def check_and_request_permission(command: str) -> bool:
    """
    Check if command is allowed, and request permission if needed.

    This is the main function to use before executing any command.

    Returns:
        True if command should be executed, False otherwise
    """
    if not command_permissions.is_enabled():
        return True

    allowed, reason = command_permissions.check_permission(command)

    if allowed:
        return True

    if reason in ("denied_session",):
        return False

    # Need to request permission
    return command_permissions.request_permission(command)
