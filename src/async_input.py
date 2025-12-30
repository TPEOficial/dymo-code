"""
Asynchronous Input System for Dymo Code
Allows typing while the agent is processing, with message queuing
Uses separate thread for non-blocking input
"""

import os
import sys
import threading
import queue
import time
from typing import Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from rich.console import Console
from rich.text import Text

from .config import COLORS
from .commands import get_command_suggestions, COMMANDS, Command
from .terminal_ui import get_path_suggestions

# ═══════════════════════════════════════════════════════════════════════════════
# Windows-specific imports
# ═══════════════════════════════════════════════════════════════════════════════

if sys.platform == "win32":
    import msvcrt
else:
    import select
    import tty
    import termios


# ═══════════════════════════════════════════════════════════════════════════════
# Message Queue Item
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class QueuedMessage:
    """A message waiting in the queue"""
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Non-blocking Input Reader
# ═══════════════════════════════════════════════════════════════════════════════

class NonBlockingInput:
    """
    Non-blocking input handler that works on both Windows and Unix.
    Runs in a separate thread and allows typing during agent processing.
    """

    def __init__(self):
        self.console = Console(force_terminal=True)
        self.message_queue: List[QueuedMessage] = []
        self.input_queue: queue.Queue = queue.Queue()
        self.is_processing = False
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        # Current input buffer
        self.buffer = ""
        self.buffer_lock = threading.Lock()

        # Input thread
        self.input_thread: Optional[threading.Thread] = None
        self.running = False

        # For command suggestions
        self.selected_index = 0

    def start(self):
        """Start the input thread"""
        if self.running:
            return

        self.running = True
        self.stop_event.clear()
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.input_thread.start()

    def stop(self):
        """Stop the input thread"""
        self.running = False
        self.stop_event.set()

    def set_processing(self, value: bool):
        """Set whether the agent is currently processing"""
        with self.lock:
            was_processing = self.is_processing
            self.is_processing = value

            if value and not was_processing: pass
            elif not value and was_processing: pass

    def is_agent_processing(self) -> bool:
        """Check if agent is processing"""
        with self.lock:
            return self.is_processing

    # ═══════════════════════════════════════════════════════════════════════════
    # Queue Management
    # ═══════════════════════════════════════════════════════════════════════════

    def add_to_queue(self, message: str):
        """Add a message to the queue"""
        with self.lock:
            self.message_queue.append(QueuedMessage(content=message))
            queue_size = len(self.message_queue)

        self.console.print(
            f"\n[{COLORS['warning']}]📥 Mensaje en cola[/] "
            f"[{COLORS['muted']}](cola: {queue_size})[/]"
        )

    def get_next_queued(self) -> Optional[str]:
        """Get and remove the next queued message"""
        with self.lock:
            if self.message_queue:
                msg = self.message_queue.pop(0)
                return msg.content
        return None

    def has_queued_messages(self) -> bool:
        """Check if there are queued messages"""
        with self.lock:
            return len(self.message_queue) > 0

    def get_queue_size(self) -> int:
        """Get number of queued messages"""
        with self.lock:
            return len(self.message_queue)

    def clear_queue(self):
        """Clear all queued messages"""
        with self.lock:
            self.message_queue.clear()

    def show_queue(self):
        """Display queued messages"""
        with self.lock:
            messages = self.message_queue.copy()

        if not messages:
            self.console.print(f"\n[{COLORS['muted']}]Cola vacía.[/]\n")
            return

        self.console.print()
        for i, msg in enumerate(messages, 1):
            time_str = msg.timestamp.strftime("%H:%M:%S")
            preview = msg.content[:50] + ("..." if len(msg.content) > 50 else "")
            self.console.print(
                f"[{COLORS['muted']}]{i}.[/] "
                f"[{COLORS['accent']}]{preview}[/] "
                f"[{COLORS['muted']}]({time_str})[/]"
            )
        self.console.print()

    # ═══════════════════════════════════════════════════════════════════════════
    # Input Thread Loop
    # ═══════════════════════════════════════════════════════════════════════════

    def _input_loop(self):
        """Background thread that reads input character by character"""
        if sys.platform == "win32": self._windows_input_loop()
        else: self._unix_input_loop()

    def _windows_input_loop(self):
        """Windows-specific input loop using msvcrt"""
        buffer = ""

        while self.running and not self.stop_event.is_set():
            try:
                if msvcrt.kbhit():
                    char = msvcrt.getwch()

                    # Enter - submit
                    if char == '\r':
                        result = buffer.strip()
                        buffer = ""

                        if result:
                            if self.is_agent_processing(): self.add_to_queue(result)
                            else: self.input_queue.put(result)
                        continue

                    # Escape - clear buffer
                    elif char == '\x1b':
                        buffer = ""
                        self._clear_line()
                        self._show_prompt()
                        continue

                    # Backspace
                    elif char == '\x08':
                        if buffer:
                            buffer = buffer[:-1]
                            self._clear_line()
                            self._show_prompt()
                            sys.stdout.write(buffer)
                            sys.stdout.flush()
                        continue

                    # Ctrl+C
                    elif char == '\x03':
                        self.input_queue.put("/exit")
                        continue

                    # Tab - autocomplete
                    elif char == '\t':
                        if buffer.startswith("/"):
                            # Command autocomplete
                            suggestions = get_command_suggestions(buffer[1:])[:6]
                            if suggestions:
                                cmd = suggestions[0]
                                buffer = f"/{cmd.name}"
                                if cmd.has_args:
                                    buffer += " "
                                self._clear_line()
                                self._show_prompt()
                                sys.stdout.write(buffer)
                                sys.stdout.flush()
                        elif "@" in buffer:
                            # Path autocomplete
                            path_suggestions = get_path_suggestions(buffer)
                            if path_suggestions:
                                # Find @ position and replace path part
                                at_index = buffer.rfind("@")
                                new_path = path_suggestions[0]["path"]
                                buffer = buffer[:at_index + 1] + new_path
                                self._clear_line()
                                self._show_prompt()
                                sys.stdout.write(buffer)
                                sys.stdout.flush()
                        continue

                    # Special keys (arrows)
                    elif char == '\x00' or char == '\xe0':
                        msvcrt.getwch()  # Skip special key
                        continue

                    # Regular character
                    elif char.isprintable():
                        buffer += char
                        sys.stdout.write(char)
                        sys.stdout.flush()

                else: time.sleep(0.01)

            except Exception:
                time.sleep(0.01)

    def _unix_input_loop(self):
        """Unix-specific input loop"""
        buffer = ""
        old_settings = None

        try:
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

            while self.running and not self.stop_event.is_set():
                if select.select([sys.stdin], [], [], 0.01)[0]:
                    char = sys.stdin.read(1)

                    # Enter
                    if char == '\n':
                        result = buffer.strip()
                        buffer = ""

                        if result:
                            if self.is_agent_processing():
                                self.add_to_queue(result)
                            else:
                                self.input_queue.put(result)
                        continue

                    # Backspace
                    elif char == '\x7f':
                        if buffer:
                            buffer = buffer[:-1]
                            sys.stdout.write('\b \b')
                            sys.stdout.flush()
                        continue

                    # Ctrl+C
                    elif char == '\x03':
                        self.input_queue.put("/exit")
                        continue

                    # Regular character
                    elif char.isprintable():
                        buffer += char
                        sys.stdout.write(char)
                        sys.stdout.flush()

        finally:
            if old_settings: termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    def _show_prompt(self):
        """Show the input prompt"""
        if self.is_agent_processing():
            prompt = f"[{COLORS['warning']}]📥[/] [{COLORS['muted']}](cola)[/] [{COLORS['primary']}]❯[/] "
        else:
            prompt = f"[{COLORS['primary']}]❯[/] "

        self.console.print(prompt, end="")

    def _clear_line(self):
        """Clear the current line"""
        sys.stdout.write('\r' + ' ' * 100 + '\r')
        sys.stdout.flush()

    # ═══════════════════════════════════════════════════════════════════════════
    # Main Input Method
    # ═══════════════════════════════════════════════════════════════════════════

    def get_input(self) -> str:
        """
        Get input from user. This is non-blocking when agent is processing.
        Returns immediately if there's input in the queue.
        """
        # Show prompt
        self._show_prompt()

        # Wait for input from queue
        while True:
            try:
                result = self.input_queue.get(timeout=0.1)
                return result
            except queue.Empty:
                # Check if we should stop
                if self.stop_event.is_set():
                    return "/exit"
                continue


# ═══════════════════════════════════════════════════════════════════════════════
# Simple Synchronous Input (Fallback)
# ═══════════════════════════════════════════════════════════════════════════════

class SimpleInputHandler:
    """
    Simple input handler that supports queuing but uses blocking input.
    More reliable on Windows terminals.
    """

    def __init__(self):
        self.console = Console(force_terminal=True)
        self.message_queue: List[QueuedMessage] = []
        self.is_processing = False
        self.lock = threading.Lock()

    def start(self):
        """No-op for compatibility"""
        pass

    def stop(self):
        """No-op for compatibility"""
        pass

    def set_processing(self, value: bool):
        with self.lock:
            self.is_processing = value

    def is_agent_processing(self) -> bool:
        with self.lock:
            return self.is_processing

    def add_to_queue(self, message: str):
        with self.lock:
            self.message_queue.append(QueuedMessage(content=message))
            queue_size = len(self.message_queue)
        self.console.print(
            f"\n[{COLORS['warning']}]📥 Mensaje en cola[/] "
            f"[{COLORS['muted']}](cola: {queue_size})[/]"
        )

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
            self.console.print(f"\n[{COLORS['muted']}]Cola vacía.[/]\n")
            return

        self.console.print()
        for i, msg in enumerate(messages, 1):
            time_str = msg.timestamp.strftime("%H:%M:%S")
            preview = msg.content[:50] + ("..." if len(msg.content) > 50 else "")
            self.console.print(
                f"[{COLORS['muted']}]{i}.[/] "
                f"[{COLORS['accent']}]{preview}[/] "
                f"[{COLORS['muted']}]({time_str})[/]"
            )
        self.console.print()

    def get_input(self) -> str:
        """Get input using standard blocking input"""
        try:
            # Show prompt
            prompt_text = Text()
            prompt_text.append("❯ ", style=f"bold {COLORS['primary']}")
            self.console.print(prompt_text, end="")

            # Standard blocking input
            result = input().strip()
            return result

        except EOFError:
            return "/exit"
        except KeyboardInterrupt:
            return ""


# ═══════════════════════════════════════════════════════════════════════════════
# Threaded Input with Background Reading
# ═══════════════════════════════════════════════════════════════════════════════

class ThreadedInputHandler:
    """
    Input handler with background thread for reading input.
    Allows typing during agent processing with visual feedback.
    """

    def __init__(self):
        self.console = Console(force_terminal=True)
        self.message_queue: List[QueuedMessage] = []
        self.pending_input: Optional[str] = None
        self.is_processing = False
        self.lock = threading.Lock()

        # Background input collection
        self.input_buffer = ""
        self.input_ready = threading.Event()
        self.stop_event = threading.Event()
        self.reader_thread: Optional[threading.Thread] = None

    def start(self):
        """Start the background reader thread"""
        self.stop_event.clear()
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

    def stop(self):
        """Stop the background reader"""
        self.stop_event.set()

    def set_processing(self, value: bool):
        with self.lock:
            self.is_processing = value

    def is_agent_processing(self) -> bool:
        with self.lock:
            return self.is_processing

    def add_to_queue(self, message: str):
        with self.lock:
            self.message_queue.append(QueuedMessage(content=message))
            size = len(self.message_queue)
        self.console.print(
            f"\n[{COLORS['warning']}]📥 Mensaje en cola ({size})[/]"
        )

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
            self.console.print(f"\n[{COLORS['muted']}]Cola vacía.[/]\n")
            return

        for i, msg in enumerate(messages, 1):
            preview = msg.content[:50] + ("..." if len(msg.content) > 50 else "")
            self.console.print(f"[{COLORS['muted']}]{i}.[/] [{COLORS['accent']}]{preview}[/]")

    def _reader_loop(self):
        """Background loop that collects characters"""
        if sys.platform == "win32":
            self._windows_reader()
        else:
            self._unix_reader()

    def _windows_reader(self):
        """Windows character-by-character reader"""
        buffer = ""

        while not self.stop_event.is_set():
            try:
                if msvcrt.kbhit():
                    char = msvcrt.getwch()

                    if char == '\r':  # Enter
                        result = buffer.strip()
                        buffer = ""

                        if result:
                            with self.lock:
                                if self.is_processing:
                                    self.message_queue.append(QueuedMessage(content=result))
                                    size = len(self.message_queue)
                                    # Print queue notification
                                    sys.stdout.write(f"\n📥 En cola ({size})\n")
                                    sys.stdout.flush()
                                else:
                                    self.pending_input = result
                                    self.input_ready.set()

                    elif char == '\x08':  # Backspace
                        if buffer:
                            buffer = buffer[:-1]
                            sys.stdout.write('\b \b')
                            sys.stdout.flush()

                    elif char == '\x03':  # Ctrl+C
                        with self.lock:
                            self.pending_input = "/exit"
                            self.input_ready.set()

                    elif char == '\x1b':  # Escape
                        buffer = ""
                        sys.stdout.write('\r' + ' ' * 80 + '\r❯ ')
                        sys.stdout.flush()

                    elif char.isprintable():
                        buffer += char
                        sys.stdout.write(char)
                        sys.stdout.flush()

                else:
                    time.sleep(0.01)

            except Exception:
                time.sleep(0.01)

    def _unix_reader(self):
        """Unix character-by-character reader"""
        buffer = ""
        old_settings = None

        try:
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

            while not self.stop_event.is_set():
                if select.select([sys.stdin], [], [], 0.01)[0]:
                    char = sys.stdin.read(1)

                    if char == '\n':
                        result = buffer.strip()
                        buffer = ""

                        if result:
                            with self.lock:
                                if self.is_processing:
                                    self.message_queue.append(QueuedMessage(content=result))
                                else:
                                    self.pending_input = result
                                    self.input_ready.set()

                    elif char == '\x7f':  # Backspace
                        if buffer:
                            buffer = buffer[:-1]
                            sys.stdout.write('\b \b')
                            sys.stdout.flush()

                    elif char.isprintable():
                        buffer += char
                        sys.stdout.write(char)
                        sys.stdout.flush()

        finally:
            if old_settings: termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    def get_input(self) -> str:
        """Get input - waits for user to press Enter"""
        # Show prompt
        self.console.print(f"[{COLORS['primary']}]❯[/] ", end="")
        sys.stdout.flush()

        # Clear any previous input state
        self.input_ready.clear()
        with self.lock:
            self.pending_input = None

        # Wait for input
        while True:
            if self.input_ready.wait(timeout=0.1):
                with self.lock:
                    result = self.pending_input
                    self.pending_input = None
                self.input_ready.clear()
                if result: return result

            if self.stop_event.is_set(): return "/exit"


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance - Use threaded handler
# ═══════════════════════════════════════════════════════════════════════════════

# Use threaded input for better async support
async_input = ThreadedInputHandler()
