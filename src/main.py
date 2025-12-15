"""
Main entry point for Dymo Code
Enhanced with memory system, command autocomplete, and multi-agent support
"""
from typing import Optional
import os, sys, time, threading, json, ssl
from urllib.request import urlopen, Request
from urllib.error import URLError
from pathlib import Path

# Add parent directory to path for imports when running directly
if __name__ == "__main__": sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.config import COLORS, AVAILABLE_MODELS
from src.agent import Agent
from src.history import history_manager
from src.queue_manager import MessageQueueManager
from src.memory import memory
from src.command_handler import CommandHandler
from src.terminal_ui import terminal_ui as async_input
from src.storage import user_config, get_data_directory
from src.utils.basics import set_terminal_title, get_resource_path
from src.ui import (
    console,
    print_banner,
    print_help,
    print_models,
    print_conversations,
    show_status,
    get_prompt_text,
    display_success,
    display_info,
    print_welcome_with_memory
)

# ═══════════════════════════════════════════════════════════════════════════════
# Version Check
# ═══════════════════════════════════════════════════════════════════════════════

VERSION_CHECK_URL = "https://github.com/TPEOficial/dymo-code/raw/refs/heads/main/static-api/version.json"
_update_available: Optional[str] = None

def get_version() -> str:
    """Get the current version of Dymo Code"""
    try:
        version_file = get_resource_path("static-api/version.json")
        if version_file.exists():
            with open(version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("version", "unknown")
    except Exception:
        pass
    return "unknown"

def get_remote_version() -> Optional[str]:
    """Get the remote version from GitHub (synchronous)"""
    try:
        request = Request(
            VERSION_CHECK_URL,
            headers={"User-Agent": "Dymo-Code-Update-Checker"}
        )
        ssl_context = _create_ssl_context()

        with urlopen(request, timeout=5, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("version")
    except Exception:
        return None

def _create_ssl_context():
    """Create SSL context that works in compiled mode"""
    try:
        # Try to use certifi certificates if available
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass

    # Fallback: create unverified context (less secure but works)
    # This is acceptable for a simple version check
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def _check_for_updates():
    """Check for updates in background and store result"""
    global _update_available
    try:
        local_version = get_version()
        if local_version == "unknown": return

        # Create request with headers (GitHub sometimes blocks bare requests)
        request = Request(
            VERSION_CHECK_URL,
            headers={"User-Agent": "Dymo-Code-Update-Checker"}
        )

        # Use SSL context that works in compiled mode
        ssl_context = _create_ssl_context()

        with urlopen(request, timeout=10, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            remote_version = data.get("version")

            if remote_version and remote_version != local_version: _update_available = remote_version
    except Exception: pass

def start_version_check():
    """Start version check in background thread"""
    thread = threading.Thread(target=_check_for_updates, daemon=True)
    thread.start()

def show_update_notification():
    """Show update notification if available"""
    if _update_available:
        local_version = get_version()
        console.print(
            f"[{COLORS['warning']}]Update available: v{_update_available} "
            f"(current: v{local_version})[/]"
        )
        console.print(
            f"[{COLORS['muted']}]  Download: https://github.com/TPEOficial/dymo-code/releases[/]"
        )
        console.print()

# ═══════════════════════════════════════════════════════════════════════════════
# Input Handler with Queue Support
# ═══════════════════════════════════════════════════════════════════════════════

class InputHandler:
    """Handles user input with queue support for async message submission"""

    def __init__(self, queue_manager: MessageQueueManager):
        self.queue_manager = queue_manager
        self.current_input: Optional[str] = None
        self.input_ready = threading.Event()
        self.should_stop = False
        self.input_thread: Optional[threading.Thread] = None

    def start_input_thread(self):
        """Start the background input thread"""
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.input_thread.start()

    def _input_loop(self):
        """Background loop that reads input"""
        while not self.should_stop:
            try:
                # Show prompt
                console.print(get_prompt_text(), end="")
                user_input = input().strip()

                if user_input:
                    # If agent is processing, add to queue
                    if self.queue_manager.is_agent_processing(): self.queue_manager.add_message(user_input)
                    else:
                        # Set as current input for main thread to process
                        self.current_input = user_input
                        self.input_ready.set()

            except EOFError:
                self.should_stop = True
                self.input_ready.set()
                break
            except KeyboardInterrupt: continue

    def get_input(self, timeout: float = None) -> Optional[str]:
        """Get the next input (blocking)"""
        self.input_ready.wait(timeout)
        self.input_ready.clear()
        result = self.current_input
        self.current_input = None
        return result

    def stop(self):
        """Stop the input handler"""
        self.should_stop = True
        self.input_ready.set()

# ═══════════════════════════════════════════════════════════════════════════════
# Command Handlers (Now delegated to CommandHandler class)
# ═══════════════════════════════════════════════════════════════════════════════

def handle_command(user_input: str, agent: Agent, queue_manager: MessageQueueManager, command_handler: CommandHandler) -> bool:
    """
    Handle a command and return True if it was a command (not regular chat).
    Returns False if the input should be processed as chat.
    Returns None to signal exit.
    """
    is_command, result = command_handler.handle(user_input)
    if not is_command: return False
    if result == "exit": return None
    return True

# ═══════════════════════════════════════════════════════════════════════════════
# First Run Setup
# ═══════════════════════════════════════════════════════════════════════════════

def run_first_time_setup() -> str:
    """Run the first-time setup to get user's name"""
    from rich.panel import Panel
    from rich.text import Text

    console.print()
    console.print(
        Panel(
            "[bold]Welcome to Dymo Code![/bold]\n\n"
            "This appears to be your first time running Dymo Code.\n"
            "Let's get you set up with a quick question.",
            border_style=f"{COLORS['primary']}",
            padding=(1, 2)
        )
    )
    console.print()

    # Ask for name
    console.print(f"[{COLORS['secondary']}]What's your name?[/]")
    console.print(f"[{COLORS['muted']}](This will be used to personalize your experience)[/]")
    console.print()

    prompt = Text()
    prompt.append("Your name: ", style=f"bold {COLORS['primary']}")
    console.print(prompt, end="")

    try:
        name = input().strip()
        if not name: name = "User"
    except (EOFError, KeyboardInterrupt): name = "User"

    # Save the configuration
    user_config.complete_first_run(name)

    # Also save to memory for AI context
    memory.set_profile("name", name, "identity")

    console.print()
    console.print(
        f"[{COLORS['success']}]Nice to meet you, {name}![/]"
    )
    console.print(
        f"[{COLORS['muted']}]Your data will be stored in: {get_data_directory()}[/]"
    )
    console.print()

    return name


# ═══════════════════════════════════════════════════════════════════════════════
# Main Loop
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point"""
    console.clear()
    print_banner()
    set_terminal_title("💬 Dymo Code")

    # Start version check in background (non-blocking)
    start_version_check()

    # Load stored API keys into environment
    user_config.load_api_keys_to_env()

    # Check for first run and do setup if needed
    if user_config.is_first_run:
        username = run_first_time_setup()
    else:
        # Get username from user config (primary) or memory (fallback)
        username = user_config.user_name or memory.get_profile("name")
        # Update last seen
        user_config.update_last_seen()

    # Initialize components
    agent = Agent()
    queue_manager = MessageQueueManager(console)

    # Initialize command handler
    command_handler = CommandHandler(agent, queue_manager)

    # Add memory context to agent's system prompt
    memory_context = memory.get_context_for_ai()
    if memory_context:
        agent.add_memory_context(memory_context)

    # Start the async input handler thread
    async_input.start()

    # Welcome message - different for returning users
    if not user_config.is_first_run:
        console.print()
        console.print(f"[bold {COLORS['secondary']}]Welcome back, {username}![/]")
    console.print(f"[{COLORS['muted']}]Type [bold]/[/bold] to see commands or start chatting.[/]")
    console.print(f"[{COLORS['muted']}]You can type while the agent processes - messages will be queued.[/]")
    console.print()
    show_status(agent.model_key)
    console.print()

    # Show update notification if available (version check runs in background)
    time.sleep(0.3)  # Small delay to allow version check to complete
    show_update_notification()

    while True:
        try:
            # Check for queued messages first
            if async_input.has_queued_messages():
                queued_content = async_input.get_next_queued()
                if queued_content:
                    console.print(f"\n[{COLORS['muted']}]Processing queued message...[/]")
                    user_input = queued_content
                    # Show the queued input
                    async_input.print_submitted_input(user_input)
            elif queue_manager.has_pending_messages():
                queued_msg = queue_manager.get_next_message()
                if queued_msg:
                    queue_manager.show_processing_next(queued_msg)
                    user_input = queued_msg.content
                    # Show the queued input
                    async_input.print_submitted_input(user_input)
            else:
                # Get input from user using async input handler
                user_input = async_input.get_input()

            if not user_input: continue

            # Show the user's input so it stays visible in chat history
            async_input.print_submitted_input(user_input)

            # Handle commands
            command_result = handle_command(user_input, agent, queue_manager, command_handler)

            if command_result is None: break
            elif command_result: continue

            # Regular chat - show processing and set state
            queue_manager.set_processing(True)
            async_input.set_processing(True)

            # Connect status callback to spinner
            def status_callback(status: str, detail: str = ""):
                async_input.update_status(status, detail)

            agent.set_status_callback(status_callback)

            # Start spinner with initial status
            async_input.start_processing("thinking")

            try: agent.chat(user_input)
            finally:
                async_input.stop_processing()
                queue_manager.set_processing(False)
                async_input.set_processing(False)

            console.print()

            # Check if there are more messages in the queue
            total_queued = queue_manager.get_queue_size() + async_input.get_queue_size()
            if total_queued > 0:
                console.print(f"[{COLORS['muted']}]({total_queued} message{'s' if total_queued > 1 else ''} in queue)[/]\n")

        except KeyboardInterrupt:
            # If interrupted while processing, show queue option
            if queue_manager.is_agent_processing():
                console.print(f"\n\n[{COLORS['warning']}]Processing interrupted.[/]")
                queue_manager.set_processing(False)
                async_input.set_processing(False)
            else: console.print(f"\n\n[{COLORS['muted']}]Interrupted. Type /exit to quit.[/]\n")
            continue
        except EOFError: break

    # Cleanup
    async_input.stop()
    memory.close()


if __name__ == "__main__": main()