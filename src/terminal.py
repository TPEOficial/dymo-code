"""
Terminal utilities for Dymo Code
- Dynamic terminal title
- Screen management
- Terminal capabilities detection
"""

import os
import sys
import platform
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# Terminal Title Management
# ═══════════════════════════════════════════════════════════════════════════════

class TerminalTitle:
    """
    Manages dynamic terminal title updates.
    Inspired by OpenCode's terminal title system.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._base_title = "Dymo Code"
        self._current_model = None
        self._current_session = None
        self._status = None
        self._enabled = True
        self._initialized = True

        # Detect if terminal supports title changes
        self._supports_title = self._detect_title_support()

    def _detect_title_support(self) -> bool:
        """Detect if terminal supports title changes"""
        # Most modern terminals support OSC title sequences
        term = os.environ.get("TERM", "")
        colorterm = os.environ.get("COLORTERM", "")

        # Windows Terminal, iTerm2, modern terminals
        if colorterm in ["truecolor", "24bit"]:
            return True

        # xterm-compatible terminals
        if term.startswith(("xterm", "screen", "tmux", "vt100", "linux")):
            return True

        # Windows conhost and newer Windows Terminal
        if sys.platform == "win32":
            return True

        # Check if we're in a real terminal
        return sys.stdout.isatty()

    def set_title(self, title: str):
        """Set the terminal title directly"""
        if not self._enabled or not self._supports_title:
            return

        try:
            if sys.platform == "win32":
                # Windows - use ctypes for native title change
                import ctypes
                ctypes.windll.kernel32.SetConsoleTitleW(title)
            else:
                # Unix - use OSC escape sequence
                sys.stdout.write(f"\x1b]0;{title}\x07")
                sys.stdout.flush()
        except Exception:
            pass  # Silently fail if title change not supported

    def update(
        self,
        model: Optional[str] = None,
        session: Optional[str] = None,
        status: Optional[str] = None
    ):
        """
        Update terminal title with current state.

        Args:
            model: Current model name
            session: Current session/conversation title
            status: Current status (thinking, generating, etc.)
        """
        if model is not None:
            self._current_model = model
        if session is not None:
            self._current_session = session
        if status is not None:
            self._status = status

        self._refresh_title()

    def _refresh_title(self):
        """Refresh the terminal title based on current state"""
        parts = [self._base_title]

        if self._current_model:
            parts.append(f"[{self._current_model}]")

        if self._current_session:
            # Truncate long session names
            session = self._current_session[:30]
            if len(self._current_session) > 30:
                session += "..."
            parts.append(f"- {session}")

        if self._status:
            parts.append(f"({self._status})")

        title = " ".join(parts)
        self.set_title(title)

    def set_status(self, status: Optional[str]):
        """Update just the status portion"""
        self._status = status
        self._refresh_title()

    def clear_status(self):
        """Clear the status portion"""
        self._status = None
        self._refresh_title()

    def set_session(self, session: Optional[str]):
        """Update the session/conversation title"""
        self._current_session = session
        self._refresh_title()

    def set_model(self, model: str):
        """Update the current model"""
        self._current_model = model
        self._refresh_title()

    def reset(self):
        """Reset to base title"""
        self._current_model = None
        self._current_session = None
        self._status = None
        self.set_title(self._base_title)

    def enable(self):
        """Enable title updates"""
        self._enabled = True

    def disable(self):
        """Disable title updates"""
        self._enabled = False


# ═══════════════════════════════════════════════════════════════════════════════
# Terminal Capabilities
# ═══════════════════════════════════════════════════════════════════════════════

class TerminalCapabilities:
    """Detect terminal capabilities"""

    @staticmethod
    def supports_unicode() -> bool:
        """Check if terminal supports unicode"""
        try:
            # Try to encode a unicode character
            "✓".encode(sys.stdout.encoding or "utf-8")
            return True
        except (UnicodeEncodeError, LookupError):
            return False

    @staticmethod
    def supports_256_colors() -> bool:
        """Check if terminal supports 256 colors"""
        term = os.environ.get("TERM", "")
        colorterm = os.environ.get("COLORTERM", "")

        if colorterm in ["truecolor", "24bit"]:
            return True
        if "256color" in term:
            return True
        if sys.platform == "win32":
            # Windows 10+ supports 256 colors
            return True
        return False

    @staticmethod
    def supports_truecolor() -> bool:
        """Check if terminal supports 24-bit true color"""
        colorterm = os.environ.get("COLORTERM", "")
        return colorterm in ["truecolor", "24bit"]

    @staticmethod
    def get_size() -> tuple:
        """Get terminal size (columns, rows)"""
        try:
            import shutil
            size = shutil.get_terminal_size()
            return (size.columns, size.lines)
        except Exception:
            return (80, 24)  # Default fallback

    @staticmethod
    def is_interactive() -> bool:
        """Check if running in an interactive terminal"""
        return sys.stdin.isatty() and sys.stdout.isatty()


# ═══════════════════════════════════════════════════════════════════════════════
# Screen Management
# ═══════════════════════════════════════════════════════════════════════════════

def clear_screen():
    """Clear the terminal screen"""
    if sys.platform == "win32":
        os.system("cls")
    else:
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.flush()


def clear_line():
    """Clear the current line"""
    sys.stdout.write("\r\x1b[K")
    sys.stdout.flush()


def move_cursor_up(lines: int = 1):
    """Move cursor up n lines"""
    sys.stdout.write(f"\x1b[{lines}A")
    sys.stdout.flush()


def move_cursor_down(lines: int = 1):
    """Move cursor down n lines"""
    sys.stdout.write(f"\x1b[{lines}B")
    sys.stdout.flush()


def hide_cursor():
    """Hide the cursor"""
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()


def show_cursor():
    """Show the cursor"""
    sys.stdout.write("\x1b[?25h")
    sys.stdout.flush()


def save_cursor_position():
    """Save current cursor position"""
    sys.stdout.write("\x1b[s")
    sys.stdout.flush()


def restore_cursor_position():
    """Restore saved cursor position"""
    sys.stdout.write("\x1b[u")
    sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════════════════
# Bell/Notification
# ═══════════════════════════════════════════════════════════════════════════════

def bell():
    """Ring the terminal bell"""
    sys.stdout.write("\a")
    sys.stdout.flush()


def notify_done():
    """Notify user that a task is done (bell + title flash)"""
    bell()
    terminal_title.set_status("Done!")


# ═══════════════════════════════════════════════════════════════════════════════
# Clipboard (OSC 52)
# ═══════════════════════════════════════════════════════════════════════════════

def copy_to_clipboard_osc52(text: str) -> bool:
    """
    Copy text to clipboard using OSC 52 escape sequence.
    Works in terminals that support it (tmux, iTerm2, kitty, etc.)
    """
    try:
        import base64
        encoded = base64.b64encode(text.encode()).decode()
        sys.stdout.write(f"\x1b]52;c;{encoded}\x07")
        sys.stdout.flush()
        return True
    except Exception:
        return False


def copy_to_clipboard(text: str) -> bool:
    """
    Copy text to clipboard using the best available method.
    """
    # Try platform-specific clipboard first
    try:
        import subprocess

        if sys.platform == "darwin":
            # macOS
            process = subprocess.Popen(
                ["pbcopy"],
                stdin=subprocess.PIPE
            )
            process.communicate(text.encode())
            return process.returncode == 0

        elif sys.platform == "win32":
            # Windows
            import ctypes
            from ctypes import wintypes

            CF_UNICODETEXT = 13
            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32

            user32.OpenClipboard(0)
            user32.EmptyClipboard()

            hglob = kernel32.GlobalAlloc(0x0042, len(text) * 2 + 2)
            pglob = kernel32.GlobalLock(hglob)
            ctypes.cdll.msvcrt.wcscpy(ctypes.c_wchar_p(pglob), text)
            kernel32.GlobalUnlock(hglob)
            user32.SetClipboardData(CF_UNICODETEXT, hglob)
            user32.CloseClipboard()
            return True

        else:
            # Linux - try xclip or xsel
            for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
                try:
                    process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                    process.communicate(text.encode())
                    if process.returncode == 0:
                        return True
                except FileNotFoundError:
                    continue

    except Exception:
        pass

    # Fallback to OSC 52
    return copy_to_clipboard_osc52(text)


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instances
# ═══════════════════════════════════════════════════════════════════════════════

terminal_title = TerminalTitle()
terminal_caps = TerminalCapabilities()
