"""
Terminal UI with command autocomplete using prompt_toolkit
- Command suggestions with arrow key navigation
- Works on Windows, macOS, and Linux
- Can type while agent processes
- Animated spinner with contextual status
- Smart placeholder suggestions based on context
"""

import sys
import os
import threading
import time
from typing import Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rich.console import Console
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

# Import ignore patterns for filtering
try:
    from .ignore_patterns import is_path_component_ignored
except ImportError:
    def is_path_component_ignored(name): return False

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

# Global spinner pause flag - used by StreamingConsole to pause spinner output
_spinner_paused = False

def pause_spinner():
    """Pause the global spinner (called by StreamingConsole)"""
    global _spinner_paused
    _spinner_paused = True

def resume_spinner():
    """Resume the global spinner"""
    global _spinner_paused
    _spinner_paused = False

def is_spinner_paused() -> bool:
    """Check if spinner is paused"""
    return _spinner_paused


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
                # Skip output when paused (e.g., during StreamingConsole)
                if _spinner_paused:
                    time.sleep(0.15)
                    continue

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
                time.sleep(0.15)
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
                # Use #B4B4B4 instead of #888 for better visibility
                display_meta=HTML(f'<style fg="#B4B4B4">{icon} {cmd.description[:40]}</style>')
            )


class PathCompleter(Completer):
    """Custom completer for @ path references"""

    # File type icons
    FILE_ICONS = {
        ".py": "🐍",
        ".js": "📜",
        ".ts": "📘",
        ".tsx": "⚛️",
        ".jsx": "⚛️",
        ".json": "📋",
        ".md": "📝",
        ".txt": "📄",
        ".yml": "⚙️",
        ".yaml": "⚙️",
        ".toml": "⚙️",
        ".html": "🌐",
        ".css": "🎨",
        ".scss": "🎨",
        ".sql": "🗃️",
        ".sh": "🖥️",
        ".bat": "🖥️",
        ".ps1": "🖥️",
        ".env": "🔐",
        ".gitignore": "🔧",
        ".dockerfile": "🐳",
    }

    def __init__(self, base_path: str = None):
        self.base_path = base_path or os.getcwd()

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Find the last @ symbol
        at_index = text.rfind("@")
        if at_index == -1:
            return

        # Get the path part after @
        path_part = text[at_index + 1:]

        # Don't complete if there's a space after the path (path is complete)
        # But allow spaces in paths if they're in quotes
        if " " in path_part and not (path_part.startswith('"') or path_part.startswith("'")):
            # Check if this looks like a complete path followed by more text
            if not os.path.exists(os.path.join(self.base_path, path_part.split()[0])):
                return

        # Handle empty path - show root directory contents
        if not path_part:
            search_dir = self.base_path
            prefix = ""
        else:
            # Determine search directory and prefix
            full_path = os.path.join(self.base_path, path_part)

            if os.path.isdir(full_path):
                # Path is a complete directory - show its contents
                search_dir = full_path
                prefix = path_part.rstrip("/\\") + "/"
            else:
                # Path is partial - search in parent directory
                parent_dir = os.path.dirname(full_path)
                if parent_dir and os.path.isdir(parent_dir):
                    search_dir = parent_dir
                    prefix = os.path.dirname(path_part)
                    if prefix:
                        prefix = prefix.rstrip("/\\") + "/"
                else:
                    search_dir = self.base_path
                    prefix = ""

        # Get matching files and directories
        try:
            entries = list(os.scandir(search_dir))
        except (PermissionError, FileNotFoundError):
            return

        # Filter by partial name if typing
        filter_name = os.path.basename(path_part).lower() if path_part else ""

        matches = []
        for entry in entries:
            # Skip hidden files unless explicitly typing a dot
            if entry.name.startswith(".") and not filter_name.startswith("."):
                continue

            # Skip files/folders matching .dmcodeignore patterns
            if is_path_component_ignored(entry.name):
                continue

            if not filter_name or entry.name.lower().startswith(filter_name):
                matches.append(entry)

        # Sort: directories first, then files, alphabetically
        matches.sort(key=lambda e: (not e.is_dir(), e.name.lower()))

        # Generate completions
        for entry in matches[:15]:
            is_dir = entry.is_dir()
            name = entry.name

            # Build completion path
            if is_dir:
                completion_path = prefix + name + "/"
                icon = "📁"
                # Count files inside directory
                try:
                    dir_contents = list(os.scandir(entry.path))
                    file_count = sum(1 for e in dir_contents if e.is_file() and not e.name.startswith('.'))
                    dir_count = sum(1 for e in dir_contents if e.is_dir() and not e.name.startswith('.'))
                    if file_count > 0 and dir_count > 0:
                        meta = f"{file_count} files, {dir_count} dirs"
                    elif file_count > 0:
                        meta = f"{file_count} files"
                    elif dir_count > 0:
                        meta = f"{dir_count} dirs"
                    else:
                        meta = "empty"
                except (OSError, PermissionError):
                    meta = "directory"
            else:
                completion_path = prefix + name
                ext = os.path.splitext(name)[1].lower()
                icon = self.FILE_ICONS.get(ext, "📄")

                # Get file size for meta
                try:
                    size = entry.stat().st_size
                    if size < 1024:
                        meta = f"{size} B"
                    elif size < 1024 * 1024:
                        meta = f"{size // 1024} KB"
                    else:
                        meta = f"{size // (1024 * 1024)} MB"
                except OSError:
                    meta = "file"

            # Calculate start position (replace from after @)
            start_pos = -len(path_part)

            yield Completion(
                completion_path,
                start_position=start_pos,
                display=HTML(f'<b>{icon} {name}</b>{"/" if is_dir else ""}'),
                display_meta=HTML(f'<style fg="#B4B4B4">{meta}</style>')
            )


class CombinedCompleter(Completer):
    """Combines multiple completers (commands and paths)"""

    def __init__(self, base_path: str = None):
        self.command_completer = CommandCompleter()
        self.path_completer = PathCompleter(base_path)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Check for slash commands first
        if text.startswith("/"):
            yield from self.command_completer.get_completions(document, complete_event)
            return

        # Check for @ path references
        if "@" in text:
            yield from self.path_completer.get_completions(document, complete_event)
            return


def get_path_suggestions(text: str, base_path: str = None) -> List[dict]:
    """
    Get path suggestions for @ path references.
    Returns a list of dicts with: name, path, is_dir, icon, size

    Used by async_input and interactive_input for simple Tab completion.
    """
    base_path = base_path or os.getcwd()

    # Find the path part after @
    at_index = text.rfind("@")
    if at_index == -1:
        return []

    path_part = text[at_index + 1:]

    # Don't complete if there's a space after the path
    if " " in path_part:
        return []

    # Determine search directory
    if not path_part:
        search_dir = base_path
        prefix = ""
    else:
        full_path = os.path.join(base_path, path_part)

        if os.path.isdir(full_path):
            search_dir = full_path
            prefix = path_part.rstrip("/\\") + "/"
        else:
            parent_dir = os.path.dirname(full_path)
            if parent_dir and os.path.isdir(parent_dir):
                search_dir = parent_dir
                prefix = os.path.dirname(path_part)
                if prefix:
                    prefix = prefix.rstrip("/\\") + "/"
            else:
                search_dir = base_path
                prefix = ""

    # Get matching entries
    try:
        entries = list(os.scandir(search_dir))
    except (PermissionError, FileNotFoundError):
        return []

    # Filter
    filter_name = os.path.basename(path_part).lower() if path_part else ""

    matches = []
    for entry in entries:
        if entry.name.startswith(".") and not filter_name.startswith("."):
            continue

        # Skip files/folders matching .dmcodeignore patterns
        if is_path_component_ignored(entry.name):
            continue

        if not filter_name or entry.name.lower().startswith(filter_name):
            is_dir = entry.is_dir()
            match_info = {
                "name": entry.name,
                "path": prefix + entry.name + ("/" if is_dir else ""),
                "is_dir": is_dir,
                "icon": "📁" if is_dir else PathCompleter.FILE_ICONS.get(
                    os.path.splitext(entry.name)[1].lower(), "📄"
                ),
            }

            # Add content info for directories
            if is_dir:
                try:
                    dir_contents = list(os.scandir(entry.path))
                    file_count = sum(1 for e in dir_contents if e.is_file() and not e.name.startswith('.'))
                    dir_count = sum(1 for e in dir_contents if e.is_dir() and not e.name.startswith('.'))
                    match_info["file_count"] = file_count
                    match_info["dir_count"] = dir_count
                    if file_count > 0 and dir_count > 0:
                        match_info["meta"] = f"{file_count} files, {dir_count} dirs"
                    elif file_count > 0:
                        match_info["meta"] = f"{file_count} files"
                    elif dir_count > 0:
                        match_info["meta"] = f"{dir_count} dirs"
                    else:
                        match_info["meta"] = "empty"
                except (OSError, PermissionError):
                    match_info["file_count"] = 0
                    match_info["dir_count"] = 0
                    match_info["meta"] = "directory"
            else:
                # Get file size
                try:
                    size = entry.stat().st_size
                    if size < 1024:
                        match_info["meta"] = f"{size} B"
                    elif size < 1024 * 1024:
                        match_info["meta"] = f"{size // 1024} KB"
                    else:
                        match_info["meta"] = f"{size // (1024 * 1024)} MB"
                except OSError:
                    match_info["meta"] = "file"

            matches.append(match_info)

    # Sort: directories first, then alphabetically
    matches.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))

    return matches[:15]


# ═══════════════════════════════════════════════════════════════════════════════
# Dynamic Style Factory
# ═══════════════════════════════════════════════════════════════════════════════

def get_prompt_style() -> Style:
    """Get prompt style with current theme colors"""
    # Use current theme colors for better visibility
    try:
        from .themes import theme_manager
        colors = theme_manager.colors
        primary = colors.get("primary", "#7C3AED")
        bg = colors.get("background", "#1a1a2e")
    except ImportError:
        primary = COLORS["primary"]
        bg = "#1a1a2e"

    return Style.from_dict({
        # Prompt
        'prompt': f'bold {primary}',
        'warning': f'bold #F59E0B',
        # Completion menu - improved contrast
        'completion-menu': f'bg:#252536 #E5E5E5',
        'completion-menu.completion': f'bg:#252536 #E5E5E5',
        'completion-menu.completion.current': f'bg:{primary} #ffffff bold',
        # Meta/description - MUCH better visibility than #888
        'completion-menu.meta': '#B4B4B4',  # Lighter gray for visibility
        'completion-menu.meta.current': '#ffffff',
        # Scrollbar
        'scrollbar.background': '#252536',
        'scrollbar.button': primary,
    })


# Legacy constant for compatibility
PROMPT_STYLE = get_prompt_style()


# ═══════════════════════════════════════════════════════════════════════════════
# Smart Placeholder Suggestions
# ═══════════════════════════════════════════════════════════════════════════════

# Context-based suggestions - varied and specific
CONTEXT_SUGGESTIONS = {
    "greeting": [
        "What can you help me with?",
        "Tell me about your capabilities",
        "Help me get started",
    ],
    "code": [
        "Explain this code",
        "Add tests for this",
        "Optimize the performance",
        "Refactor this code",
        "Fix the bugs here",
    ],
    "error": [
        "Fix this error",
        "Why is this happening?",
        "How do I debug this?",
        "Show me the solution",
    ],
    "file": [
        "Show me the file",
        "Edit this file",
        "What does this file do?",
        "Create a similar file",
    ],
    "general": [
        "Continue",
        "Tell me more",
        "Can you elaborate?",
        "What else should I know?",
        "Show me an example",
    ],
    "project": [
        "Analyze the structure",
        "Find potential issues",
        "Suggest improvements",
        "Show dependencies",
    ],
    "question": [
        "Thanks, that helps!",
        "Can you give more details?",
        "What about edge cases?",
        "How would you improve this?",
    ],
    "task_complete": [
        "Perfect, now do...",
        "Great! What's next?",
        "Thanks! Now help me with...",
        "Excellent! Can you also...",
    ],
    "analysis": [
        "What do you recommend?",
        "Implement the suggestion",
        "Show me how",
        "Let's do it",
    ],
}

# Default suggestions for empty context
DEFAULT_SUGGESTIONS = [
    "What would you like to do?",
    "Ask me anything...",
    "Describe your task...",
]

# Suggestion rotation counter
_suggestion_counter = 0


class SmartSuggester(AutoSuggest):
    """
    Smart auto-suggester that provides context-aware placeholders.
    Generates suggestions synchronously for immediate feedback.
    """

    def __init__(self):
        self._current_suggestion: Optional[str] = None
        self._last_response: str = ""
        self._last_context: str = "general"
        self._lock = threading.Lock()
        self._suggestion_index: int = 0

    def set_context(self, last_response: str, context_type: str = "general"):
        """Set context for next suggestion (called after AI responds)"""
        with self._lock:
            self._last_response = last_response[:800] if last_response else ""
            self._last_context = context_type
            # Generate suggestion immediately (fast operation)
            self._current_suggestion = self._generate_suggestion_sync()

    def _detect_context(self, response: str) -> str:
        """Detect context type from response content"""
        response_lower = response.lower()

        # Priority-ordered context detection
        if any(w in response_lower for w in ["error", "exception", "failed", "traceback", "bug"]):
            return "error"

        if any(w in response_lower for w in ["completed", "done", "created", "finished", "success"]):
            return "task_complete"

        if any(w in response_lower for w in ["```", "def ", "class ", "function ", "import ", "const ", "let ", "var "]):
            return "code"

        if any(w in response_lower for w in ["analyze", "review", "suggest", "recommend", "consider"]):
            return "analysis"

        if response_lower.endswith("?") or "what" in response_lower or "how" in response_lower:
            return "question"

        if any(w in response_lower for w in ["file", "directory", "folder", "path", ".py", ".js", ".ts"]):
            return "file"

        if any(w in response_lower for w in ["project", "structure", "architecture", "codebase"]):
            return "project"

        if any(w in response_lower for w in ["hello", "hi ", "welcome", "nice to meet"]):
            return "greeting"

        return "general"

    def _generate_suggestion_sync(self) -> str:
        """Generate suggestion synchronously - fast operation"""
        global _suggestion_counter

        response = self._last_response
        context = self._detect_context(response)

        # Get suggestions for detected context
        suggestions = CONTEXT_SUGGESTIONS.get(context, CONTEXT_SUGGESTIONS["general"])

        # Rotate through suggestions deterministically
        _suggestion_counter += 1
        idx = _suggestion_counter % len(suggestions)

        return suggestions[idx]

    def get_suggestion(self, buffer, document) -> Optional[Suggestion]:
        """Get suggestion for current input"""
        text = document.text

        # Don't suggest if typing more than 2 chars
        if len(text) > 2:
            return None

        # Don't suggest for commands
        if text.startswith("/"):
            return None

        # Return current suggestion when input is empty
        with self._lock:
            if self._current_suggestion and not text:
                return Suggestion(self._current_suggestion)

        # Default suggestion if no context set yet
        if not text:
            global _suggestion_counter
            idx = _suggestion_counter % len(DEFAULT_SUGGESTIONS)
            return Suggestion(DEFAULT_SUGGESTIONS[idx])

        return None


# Global suggester instance
smart_suggester = SmartSuggester()


# ═══════════════════════════════════════════════════════════════════════════════
# Key Bindings for Tab completion
# ═══════════════════════════════════════════════════════════════════════════════

def create_key_bindings():
    """Create custom key bindings for Tab to accept suggestion and ! for shell mode"""
    kb = KeyBindings()

    @kb.add(Keys.Tab)
    def accept_suggestion(event):
        """Accept the current suggestion with Tab"""
        buff = event.app.current_buffer
        suggestion = buff.suggestion

        if suggestion:
            buff.insert_text(suggestion.text)
        else:
            # Default tab behavior - insert spaces
            buff.insert_text("    ")

    @kb.add(Keys.Right)
    def accept_suggestion_right(event):
        """Accept suggestion with Right arrow when at end of line"""
        buff = event.app.current_buffer
        if buff.cursor_position == len(buff.text) and buff.suggestion:
            buff.insert_text(buff.suggestion.text)
        else:
            buff.cursor_right()

    @kb.add('!')
    def enter_shell_mode(event):
        """Enter shell mode when ! is pressed on empty buffer"""
        buff = event.app.current_buffer
        if not buff.text:
            # Exit prompt with special marker to trigger shell mode
            event.app.exit(result='!SHELL_MODE!')
        else:
            # Normal ! character
            buff.insert_text('!')

    return kb


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

        # Shell mode
        self.shell_mode: bool = False
        self._shell_session: Optional[PromptSession] = None

    def _execute_shell_command(self, command: str) -> bool:
        """Execute a shell command directly. Returns True if command was executed."""
        if not command.strip():
            return False

        import subprocess

        self.console.print(f"[{COLORS['muted']}]$ {command}[/]")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
                timeout=120
            )

            if result.stdout:
                self.console.print(result.stdout.rstrip())
            if result.stderr:
                self.console.print(f"[red]{result.stderr.rstrip()}[/]")
            if result.returncode != 0:
                self.console.print(f"[{COLORS['muted']}]Exit code: {result.returncode}[/]")

        except subprocess.TimeoutExpired:
            self.console.print(f"[{COLORS['error']}]Command timed out after 120s[/]")
        except Exception as e:
            self.console.print(f"[{COLORS['error']}]Error: {e}[/]")

        return True

    def _get_shell_session(self) -> PromptSession:
        """Get or create shell mode session"""
        if self._shell_session is None:
            self._shell_session = PromptSession(
                style=Style.from_dict({
                    'prompt': '#ffcc00 bold',  # Yellow for shell mode
                    'shell-indicator': '#888888',
                }),
            )
        return self._shell_session

    def _run_shell_mode(self):
        """Run interactive shell mode until user exits"""
        self.shell_mode = True
        self.console.print(f"[yellow][SHELL MODE][/] [dim]Esc or empty input to exit[/]")

        shell_session = self._get_shell_session()

        while self.shell_mode:
            try:
                # Shell prompt
                cmd = shell_session.prompt([('class:prompt', '! ')])

                if not cmd or not cmd.strip():
                    # Empty input exits shell mode
                    self.shell_mode = False
                    self.console.print(f"[dim][SHELL EXIT][/]")
                    break

                self._execute_shell_command(cmd.strip())

            except KeyboardInterrupt:
                # Ctrl+C exits shell mode
                self.shell_mode = False
                self.console.print(f"\n[dim][SHELL EXIT][/]")
                break
            except EOFError:
                # Ctrl+D exits shell mode
                self.shell_mode = False
                self.console.print(f"[dim][SHELL EXIT][/]")
                break

    @property
    def session(self) -> PromptSession:
        """Lazy initialization of prompt session"""
        if self._session is None:
            self._session = PromptSession(
                completer=CombinedCompleter(),
                style=get_prompt_style(),
                complete_while_typing=True,
                complete_in_thread=True,
                auto_suggest=smart_suggester,  # Smart placeholder
                key_bindings=create_key_bindings(),  # Tab to accept
            )
        return self._session

    def set_suggestion_context(self, last_response: str, context_type: str = "general"):
        """Update the suggestion context after AI responds"""
        smart_suggester.set_context(last_response, context_type)

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
        """Print the user's submitted input, truncating if too long"""
        if not user_input:
            return

        lines = user_input.split('\n')
        total_lines = len(lines)
        total_chars = len(user_input)

        # Truncate long input (similar to Claude Code)
        max_display_lines = 3
        max_display_chars = 200

        if total_lines > max_display_lines or total_chars > max_display_chars:
            # Show truncated preview
            if total_lines > 1:
                # Multi-line: show first few lines
                preview_lines = lines[:max_display_lines]
                preview = '\n'.join(line[:80] + ('...' if len(line) > 80 else '') for line in preview_lines)
                if total_lines > max_display_lines:
                    truncation_info = f"... +{total_lines - max_display_lines} more lines"
                else:
                    truncation_info = f"... +{total_chars - len(preview)} chars"
            else:
                # Single long line
                preview = user_input[:max_display_chars]
                truncation_info = f"... +{total_chars - max_display_chars} chars"

            self.console.print(f"[{COLORS['primary']}]❯[/] {preview}")
            self.console.print(f"[{COLORS['muted']}]  ({truncation_info})[/]")
        else:
            # Short input - show as is
            self.console.print(f"[{COLORS['primary']}]❯[/] {user_input}")

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
                result = result.strip()

                # Check for shell mode trigger (from key binding)
                if result == "!SHELL_MODE!":
                    # Enter interactive shell mode immediately
                    self._run_shell_mode()
                    return ""  # Return empty to continue main loop

                # Check for shell mode trigger (typed with Enter)
                if result == "!":
                    # Enter interactive shell mode
                    self._run_shell_mode()
                    return ""  # Return empty to continue main loop

                elif result.startswith("!"):
                    # Execute single shell command
                    cmd = result[1:].strip()
                    if cmd:
                        self._execute_shell_command(cmd)
                    return ""  # Return empty to continue main loop

                self.history.append(result)

            return result if result else ""

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
