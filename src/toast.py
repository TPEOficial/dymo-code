"""
Toast notification system for Dymo Code
Inspired by OpenCode's toast notifications
"""

import threading
import time
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Callable
from enum import Enum
from queue import Queue

from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.box import ROUNDED


# ═══════════════════════════════════════════════════════════════════════════════
# Toast Types
# ═══════════════════════════════════════════════════════════════════════════════

class ToastType(Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


# ═══════════════════════════════════════════════════════════════════════════════
# Toast Data
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Toast:
    """A toast notification"""
    message: str
    type: ToastType = ToastType.INFO
    title: Optional[str] = None
    duration: float = 3.0  # seconds
    created_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: f"toast_{time.time()}")


# ═══════════════════════════════════════════════════════════════════════════════
# Toast Icons and Colors
# ═══════════════════════════════════════════════════════════════════════════════

TOAST_CONFIG = {
    ToastType.INFO: {
        "icon": "i",
        "color_key": "secondary",
        "default_title": "Info",
    },
    ToastType.SUCCESS: {
        "icon": "v",
        "color_key": "success",
        "default_title": "Success",
    },
    ToastType.WARNING: {
        "icon": "!",
        "color_key": "warning",
        "default_title": "Warning",
    },
    ToastType.ERROR: {
        "icon": "x",
        "color_key": "error",
        "default_title": "Error",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# Toast Manager
# ═══════════════════════════════════════════════════════════════════════════════

class ToastManager:
    """
    Manages toast notifications display.
    Shows temporary notifications that auto-dismiss.
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

        self.console = Console(force_terminal=True, stderr=True)
        self._queue: Queue[Toast] = Queue()
        self._active_toasts: List[Toast] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._enabled = True
        self._initialized = True

    def start(self):
        """Start the toast display thread"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._display_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the toast display thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
            self._thread = None

    def enable(self):
        """Enable toast notifications"""
        self._enabled = True

    def disable(self):
        """Disable toast notifications"""
        self._enabled = False

    def _get_colors(self):
        """Get colors from theme manager"""
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

    def show(
        self,
        message: str,
        type: ToastType = ToastType.INFO,
        title: Optional[str] = None,
        duration: float = 3.0
    ):
        """
        Show a toast notification.

        Args:
            message: The message to display
            type: Type of toast (info, success, warning, error)
            title: Optional title (defaults based on type)
            duration: How long to show the toast (seconds)
        """
        if not self._enabled:
            return

        toast = Toast(
            message=message,
            type=type,
            title=title,
            duration=duration
        )
        self._queue.put(toast)

    def info(self, message: str, title: Optional[str] = None, duration: float = 3.0):
        """Show an info toast"""
        self.show(message, ToastType.INFO, title, duration)

    def success(self, message: str, title: Optional[str] = None, duration: float = 3.0):
        """Show a success toast"""
        self.show(message, ToastType.SUCCESS, title, duration)

    def warning(self, message: str, title: Optional[str] = None, duration: float = 3.0):
        """Show a warning toast"""
        self.show(message, ToastType.WARNING, title, duration)

    def error(self, message: str, title: Optional[str] = None, duration: float = 4.0):
        """Show an error toast"""
        self.show(message, ToastType.ERROR, title, duration)

    def _render_toast(self, toast: Toast) -> str:
        """Render a toast to a string"""
        colors = self._get_colors()
        config = TOAST_CONFIG[toast.type]

        icon = config["icon"]
        color = colors.get(config["color_key"], "#FFFFFF")
        title = toast.title or config["default_title"]

        # Build the toast text
        text = Text()
        text.append(f" [{icon}] ", style=f"bold {color}")
        text.append(f"{title}: ", style=f"bold {color}")
        text.append(toast.message, style="white")

        return text

    def _display_loop(self):
        """Main loop for displaying toasts"""
        while self._running:
            try:
                # Check for new toasts
                while not self._queue.empty():
                    toast = self._queue.get_nowait()
                    with self._lock:
                        self._active_toasts.append(toast)
                        self._show_toast(toast)

                # Remove expired toasts
                now = datetime.now()
                with self._lock:
                    self._active_toasts = [
                        t for t in self._active_toasts
                        if (now - t.created_at).total_seconds() < t.duration
                    ]

                time.sleep(0.1)

            except Exception:
                time.sleep(0.1)

    def _show_toast(self, toast: Toast):
        """Display a single toast"""
        try:
            colors = self._get_colors()
            config = TOAST_CONFIG[toast.type]
            color = colors.get(config["color_key"], "#FFFFFF")
            icon = config["icon"]
            title = toast.title or config["default_title"]

            # Use ANSI codes for inline display
            # Clear line, show toast, then restore cursor
            output = f"\r\033[K[{icon}] {title}: {toast.message}"

            # Print to stderr to avoid interfering with main output
            sys.stderr.write(f"\n{output}\n")
            sys.stderr.flush()

            # Schedule removal after duration
            def clear_toast():
                time.sleep(toast.duration)
                # Toast auto-clears when the user types next

            threading.Thread(target=clear_toast, daemon=True).start()

        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# Inline Toast Display (Alternative for simpler notifications)
# ═══════════════════════════════════════════════════════════════════════════════

def show_inline_toast(
    message: str,
    type: str = "info",
    console: Optional[Console] = None
):
    """
    Show a simple inline toast notification.
    This is a synchronous, simpler alternative to the ToastManager.

    Args:
        message: The message to display
        type: Type of toast (info, success, warning, error)
        console: Rich console to use (optional)
    """
    try:
        from .themes import theme_manager
        colors = theme_manager.colors
    except ImportError:
        colors = {
            "secondary": "#06B6D4",
            "success": "#10B981",
            "warning": "#F59E0B",
            "error": "#EF4444",
        }

    if console is None:
        console = Console(force_terminal=True)

    icons = {
        "info": ("i", "secondary"),
        "success": ("v", "success"),
        "warning": ("!", "warning"),
        "error": ("x", "error"),
    }

    icon, color_key = icons.get(type, ("i", "secondary"))
    color = colors.get(color_key, "#FFFFFF")

    text = Text()
    text.append(f" [{icon}] ", style=f"bold {color}")
    text.append(message, style="white")

    console.print(text)


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

toast_manager = ToastManager()


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience Functions
# ═══════════════════════════════════════════════════════════════════════════════

def toast_info(message: str, title: Optional[str] = None):
    """Show an info toast"""
    toast_manager.info(message, title)

def toast_success(message: str, title: Optional[str] = None):
    """Show a success toast"""
    toast_manager.success(message, title)

def toast_warning(message: str, title: Optional[str] = None):
    """Show a warning toast"""
    toast_manager.warning(message, title)

def toast_error(message: str, title: Optional[str] = None):
    """Show an error toast"""
    toast_manager.error(message, title)
