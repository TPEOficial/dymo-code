"""
Terminal UI with command autocomplete using prompt_toolkit
- Command suggestions with arrow key navigation
- Works on Windows, macOS, and Linux
- Can type while agent processes
- Animated spinner with contextual status
"""

import sys
import threading
import time
from typing import Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime

from rich.console import Console
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style

from .config import COLORS
from .commands import Command, get_command_suggestions, CATEGORY_ICONS, COMMANDS


# ═══════════════════════════════════════════════════════════════════════════════
# Status Messages for Different Operations
# ═══════════════════════════════════════════════════════════════════════════════

STATUS_MESSAGES = {
    # Tool operations
    "create_folder": "Creating folder",
    "create_file": "Writing file",
    "read_file": "Reading file",
    "list_files_in_dir": "Listing directory",
    "run_command": "Executing command",
    # General states
    "thinking": "Thinking",
    "generating": "Generating response",
    "processing": "Processing",
    "analyzing": "Analyzing",
    "writing_code": "Writing code",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Animated Status Spinner
# ═══════════════════════════════════════════════════════════════════════════════

class StatusSpinner:
    """
    Animated spinner with contextual status messages.
    Uses simple terminal output to avoid conflicts with other console writes.
    """

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, console: Console):
        self.console = console
        self._status = "thinking"
        self._detail = ""
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_idx = 0
        self._last_line_len = 0

    def _get_message(self) -> str:
        """Get the current status message"""
        with self._lock:
            status = self._status
            detail = self._detail

        message = STATUS_MESSAGES.get(status, status.replace("_", " ").title())

        if detail:
            return f"{message}: {detail}"
        return message

    def start(self, status: str = "thinking", detail: str = ""):
        """Start the spinner"""
        with self._lock:
            self._status = status
            self._detail = detail
            self._running = True
            self._frame_idx = 0
            self._last_line_len = 0

        # Start animation thread
        self._thread = threading.Thread(target=self._animate_loop, daemon=True)
        self._thread.start()

    def _animate_loop(self):
        """Animation loop that updates spinner in place"""
        while self._running:
            try:
                frame = self.SPINNER_FRAMES[self._frame_idx % len(self.SPINNER_FRAMES)]
                message = self._get_message()
                line = f"\r{frame} {message}"

                # Clear previous line if it was longer
                clear_len = max(0, self._last_line_len - len(line))
                output = line + (" " * clear_len)

                sys.stdout.write(output)
                sys.stdout.flush()

                self._last_line_len = len(line)
                self._frame_idx += 1
                time.sleep(0.08)
            except Exception:
                break

    def update(self, status: str = None, detail: str = None):
        """Update the status message"""
        with self._lock:
            if status is not None:
                self._status = status
            if detail is not None:
                self._detail = detail

    def stop(self):
        """Stop the spinner and clear the line"""
        self._running = False

        if self._thread:
            self._thread.join(timeout=0.2)
            self._thread = None

        # Clear the spinner line completely
        # Use ANSI escape codes for reliable clearing
        sys.stdout.write("\r\033[K")  # Move to start of line and clear to end
        sys.stdout.flush()
        self._last_line_len = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Queued Message
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class QueuedMessage:
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


# ═══════════════════════════════════════════════════════════════════════════════
# Command Completer for prompt_toolkit
# ═══════════════════════════════════════════════════════════════════════════════

class CommandCompleter(Completer):
    """Custom completer for slash commands"""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Only complete if starts with /
        if not text.startswith("/"):
            return

        # Get the command part (without /)
        parts = text[1:].split(maxsplit=1)
        cmd_part = parts[0] if parts else ""

        # If there's a space, command is complete - don't suggest
        if " " in text[1:]:
            return

        # Get matching commands
        suggestions = get_command_suggestions(cmd_part)

        for cmd in suggestions[:8]:
            icon = CATEGORY_ICONS.get(cmd.category, "•")
            # Calculate what to insert (replace the partial command)
            completion_text = cmd.name

            yield Completion(
                completion_text,
                start_position=-len(cmd_part),
                display=HTML(f'<b>/{cmd.name}</b>'),
                display_meta=HTML(f'<style fg="#888">{icon} {cmd.description[:40]}</style>')
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Custom Style
# ═══════════════════════════════════════════════════════════════════════════════

PROMPT_STYLE = Style.from_dict({
    # Prompt
    'prompt': f'bold {COLORS["primary"]}',
    # Completion menu
    'completion-menu': 'bg:#1e1e1e #ffffff',
    'completion-menu.completion': 'bg:#1e1e1e #ffffff',
    'completion-menu.completion.current': f'bg:{COLORS["primary"]} #ffffff bold',
    'completion-menu.meta': '#888888',
    'completion-menu.meta.current': '#ffffff',
    # Scrollbar
    'scrollbar.background': '#1e1e1e',
    'scrollbar.button': COLORS['primary'],
})


# ═══════════════════════════════════════════════════════════════════════════════
# Terminal UI Class
# ═══════════════════════════════════════════════════════════════════════════════

class TerminalUI:
    """
    Terminal UI with input handling and command suggestions.
    Uses prompt_toolkit for robust cross-platform input.
    """

    def __init__(self):
        self.console = Console(force_terminal=True)

        # Lazy initialization of prompt session
        self._session: Optional[PromptSession] = None

        # Status spinner
        self.spinner = StatusSpinner(self.console)

        # Queue for async input
        self.message_queue: List[QueuedMessage] = []
        self.is_processing = False
        self.lock = threading.Lock()

        # Thread control
        self.stop_event = threading.Event()
        self.reader_thread: Optional[threading.Thread] = None

        # History
        self.history: List[str] = []

        # ESC tracking for double-ESC exit
        self._last_esc_time: float = 0
        self._esc_timeout: float = 1.0

    @property
    def session(self) -> PromptSession:
        """Lazy initialization of prompt session"""
        if self._session is None:
            self._session = PromptSession(
                completer=CommandCompleter(),
                style=PROMPT_STYLE,
                complete_while_typing=True,
                complete_in_thread=True,
            )
        return self._session

    def start(self):
        """Start background reader thread"""
        self.stop_event.clear()
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

    def stop(self):
        """Stop background reader"""
        self.stop_event.set()

    def set_processing(self, value: bool):
        """Set processing state"""
        with self.lock:
            self.is_processing = value

    def is_agent_processing(self) -> bool:
        with self.lock:
            return self.is_processing

    # ═══════════════════════════════════════════════════════════════════════════
    # Queue Management
    # ═══════════════════════════════════════════════════════════════════════════

    def add_to_queue(self, message: str):
        with self.lock:
            self.message_queue.append(QueuedMessage(content=message))

    def get_next_queued(self) -> Optional[str]:
        with self.lock:
            if self.message_queue:
                return self.message_queue.pop(0).content
        return None

    def has_queued_messages(self) -> bool:
        with self.lock:
            return len(self.message_queue) > 0

    def get_queue_size(self) -> int:
        with self.lock:
            return len(self.message_queue)

    def clear_queue(self):
        with self.lock:
            self.message_queue.clear()

    def show_queue(self):
        with self.lock:
            messages = self.message_queue.copy()

        if not messages:
            self.console.print(f"[{COLORS['muted']}]Queue is empty.[/]")
            return

        for i, msg in enumerate(messages, 1):
            preview = msg.content[:50] + ("..." if len(msg.content) > 50 else "")
            self.console.print(f"[{COLORS['muted']}]{i}.[/] [{COLORS['accent']}]{preview}[/]")

    # ═══════════════════════════════════════════════════════════════════════════
    # Display Helpers
    # ═══════════════════════════════════════════════════════════════════════════

    def print_submitted_input(self, user_input: str):
        """Print the user's submitted input so it stays visible"""
        # Don't print - prompt_toolkit already shows it
        pass

    def start_processing(self, status: str = "thinking", detail: str = ""):
        """Start the animated processing spinner"""
        self.spinner.start(status, detail)

    def update_status(self, status: str = None, detail: str = None):
        """Update the processing status message. Use status='streaming' to stop spinner."""
        if status == "streaming":
            # Stop spinner when streaming starts to avoid interference with output
            self.spinner.stop()
        else:
            self.spinner.update(status, detail)

    def stop_processing(self):
        """Stop the processing spinner"""
        self.spinner.stop()

    def print_processing(self):
        """Print a processing indicator (legacy - starts spinner)"""
        self.start_processing("thinking")

    # ═══════════════════════════════════════════════════════════════════════════
    # Background Reader (for input while processing)
    # ═══════════════════════════════════════════════════════════════════════════

    def _reader_loop(self):
        """Background loop that captures input while processing"""
        if sys.platform == "win32":
            import msvcrt
            self._win_reader(msvcrt)
        else:
            self._unix_reader()

    def _win_reader(self, msvcrt):
        """Windows background reader"""
        buffer = ""
        while not self.stop_event.is_set():
            try:
                with self.lock:
                    processing = self.is_processing

                if processing and msvcrt.kbhit():
                    char = msvcrt.getwch()
                    if char == '\r':  # Enter
                        if buffer.strip():
                            with self.lock:
                                self.message_queue.append(QueuedMessage(content=buffer.strip()))
                                size = len(self.message_queue)
                            self.console.print(f"\n[{COLORS['warning']}]📥 Queued ({size})[/]: {buffer.strip()[:40]}")
                            buffer = ""
                    elif char == '\x08':  # Backspace
                        if buffer:
                            buffer = buffer[:-1]
                            sys.stdout.write('\b \b')
                            sys.stdout.flush()
                    elif char.isprintable():
                        buffer += char
                        sys.stdout.write(char)
                        sys.stdout.flush()
                else:
                    time.sleep(0.02)
            except Exception:
                time.sleep(0.02)

    def _unix_reader(self):
        """Unix background reader"""
        import select
        buffer = ""

        while not self.stop_event.is_set():
            try:
                with self.lock:
                    processing = self.is_processing

                if processing:
                    if select.select([sys.stdin], [], [], 0.02)[0]:
                        char = sys.stdin.read(1)
                        if char == '\n':
                            if buffer.strip():
                                with self.lock:
                                    self.message_queue.append(QueuedMessage(content=buffer.strip()))
                                buffer = ""
                        elif char == '\x7f':
                            if buffer:
                                buffer = buffer[:-1]
                        elif char.isprintable():
                            buffer += char
                else:
                    time.sleep(0.02)
            except Exception:
                time.sleep(0.02)

    # ═══════════════════════════════════════════════════════════════════════════
    # Main Input Method
    # ═══════════════════════════════════════════════════════════════════════════

    def get_input(self) -> str:
        """Get input with command autocomplete"""
        try:
            # Build prompt with status indicators
            prompt_parts = []

            with self.lock:
                queue_size = len(self.message_queue)

            if queue_size > 0:
                prompt_parts.append(('class:warning', f'📥 {queue_size} '))

            prompt_parts.append(('class:prompt', '❯ '))

            # Get input using prompt_toolkit
            result = self.session.prompt(prompt_parts)

            if result:
                self.history.append(result)

            return result.strip() if result else ""

        except KeyboardInterrupt:
            # Ctrl+C pressed
            return "/exit"
        except EOFError:
            # Ctrl+D pressed
            return "/exit"


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

terminal_ui = TerminalUI()
