"""
Delete Permissions System for Dymo Code
Handles permission prompts before deleting files or folders.
"""

import sys
from typing import Optional, Set, Dict
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


class DeletePermissionLevel(Enum):
    """Permission levels for delete operations"""
    DENY = "deny"
    ONCE = "once"
    SESSION = "session"


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
class DeletePermissionOption:
    """Option for delete permission selector"""
    id: str
    label: str
    description: str
    icon: str
    level: DeletePermissionLevel


DELETE_PERMISSION_OPTIONS = [
    DeletePermissionOption(
        id="once",
        label="Delete once",
        description="Delete this item only",
        icon="1",
        level=DeletePermissionLevel.ONCE
    ),
    DeletePermissionOption(
        id="session",
        label="Allow deletes this session",
        description="Allow all delete operations for this session",
        icon="S",
        level=DeletePermissionLevel.SESSION
    ),
    DeletePermissionOption(
        id="deny",
        label="Cancel",
        description="Don't delete this item",
        icon="C",
        level=DeletePermissionLevel.DENY
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


def show_delete_permission_selector(
    path: str,
    delete_info: str,
    is_directory: bool = False,
    console: Optional[Console] = None
) -> DeletePermissionLevel:
    """
    Show an interactive selector for delete permission.
    Returns the selected permission level.
    """
    console = console or Console(force_terminal=True)
    colors = _get_colors()
    selected_idx = 0
    options = DELETE_PERMISSION_OPTIONS

    # Stop any running spinner
    spinner_was_running = False
    try:
        from .terminal_ui import terminal_ui
        if terminal_ui.spinner._running:
            spinner_was_running = True
            terminal_ui.spinner.stop()
            import time
            time.sleep(0.1)
    except:
        pass

    def render() -> Panel:
        lines = []

        # Warning icon for directories
        if is_directory:
            warn_text = Text()
            warn_text.append("  ⚠ ", style=f"bold {colors['error']}")
            warn_text.append("WARNING: This will delete a folder and ALL its contents!", style=f"bold {colors['error']}")
            lines.append(warn_text)
            lines.append(Text(""))

        # Item to delete display
        item_text = Text()
        item_text.append("  Target: ", style=f"bold {colors['muted']}")
        # Truncate long paths
        display_path = path if len(path) <= 55 else "..." + path[-52:]
        item_text.append(display_path, style=f"bold {colors['error']}")
        lines.append(item_text)

        # Size/info
        info_text = Text()
        info_text.append("  Info: ", style=f"bold {colors['muted']}")
        info_text.append(delete_info, style=colors['warning'])
        lines.append(info_text)
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
        footer.append("1/S/C", style=f"bold {colors['muted']}")
        footer.append(" Quick select", style=colors['muted'])
        lines.append(footer)

        content = Text("\n").join(lines)

        return Panel(
            content,
            title=f"[bold {colors['error']}]Delete Confirmation Required[/]",
            border_style=colors['error'],
            box=ROUNDED,
            padding=(1, 2)
        )

    # Clear line and show selector
    console.print("\r\033[K", end="")

    result = DeletePermissionLevel.DENY
    try:
        with Live(
            render(),
            console=console,
            refresh_per_second=10,
            transient=True,
            vertical_overflow="visible",
            auto_refresh=False
        ) as live:
            live.refresh()
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
                    result = DeletePermissionLevel.DENY
                    break
                # Quick select shortcuts
                elif key == '1':
                    result = DeletePermissionLevel.ONCE
                    break
                elif key.lower() == 's':
                    result = DeletePermissionLevel.SESSION
                    break
                elif key.lower() == 'c' or key.lower() == 'n' or key.lower() == 'd':
                    result = DeletePermissionLevel.DENY
                    break

        return result

    except Exception as e:
        console.print(f"[red]Delete permission selector error: {e}[/]")
        return DeletePermissionLevel.DENY
    finally:
        if spinner_was_running:
            try:
                from .terminal_ui import terminal_ui
                terminal_ui.start_processing("executing")
            except:
                pass


# ═══════════════════════════════════════════════════════════════════════════════
# Delete Permissions Manager
# ═══════════════════════════════════════════════════════════════════════════════

class DeletePermissions:
    """
    Manages delete permissions for the session.
    Note: Delete operations never have permanent "always allow" for safety.
    """

    def __init__(self):
        self._session_allowed: bool = False
        self._console = Console(force_terminal=True)

    def check_permission(self, path: str) -> bool:
        """Check if delete is allowed for this session"""
        return self._session_allowed

    def request_permission(self, path: str, delete_info: str, is_directory: bool = False) -> bool:
        """
        Request permission for a delete operation.
        Returns True if allowed, False if denied.
        """
        permission = show_delete_permission_selector(
            path, delete_info, is_directory, self._console
        )

        if permission == DeletePermissionLevel.ONCE:
            return True

        elif permission == DeletePermissionLevel.SESSION:
            self._session_allowed = True
            return True

        else:  # DENY
            return False

    def clear_session_permissions(self):
        """Clear session permissions"""
        self._session_allowed = False

    def is_enabled(self) -> bool:
        """Check if delete permission system is enabled"""
        try:
            from .storage import user_config
            return user_config.get("delete_permissions_enabled", True)
        except:
            return True

    def set_enabled(self, enabled: bool):
        """Enable or disable the permission system"""
        try:
            from .storage import user_config
            user_config.set("delete_permissions_enabled", enabled)
        except:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

delete_permissions = DeletePermissions()


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════

def check_and_request_delete_permission(path: str, delete_info: str, is_directory: bool = False) -> bool:
    """
    Check if delete is allowed, and request permission if needed.

    This is the main function to use before deleting any file or folder.

    Returns:
        True if delete should proceed, False otherwise
    """
    if not delete_permissions.is_enabled():
        return True

    # If session permission already granted, allow
    if delete_permissions.check_permission(path):
        return True

    # Need to request permission
    return delete_permissions.request_permission(path, delete_info, is_directory)
