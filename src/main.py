"""
Main entry point for Dymo Code
Enhanced with memory system, command autocomplete, and multi-agent support
"""
from typing import Optional
import os, sys, time, threading, json, ssl, tempfile, shutil, zipfile, subprocess
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

# New UI enhancement imports
from src.terminal import terminal_title
from src.toast import toast_manager
from src.setup_command import setup_command, is_command_available

# ═══════════════════════════════════════════════════════════════════════════════
# Version Check & Auto-Setup (Parallel Initialization)
# ═══════════════════════════════════════════════════════════════════════════════

VERSION_CHECK_URL = "https://github.com/TPEOficial/dymo-code/raw/refs/heads/main/static-api/version.json"
_update_available: Optional[str] = None
_setup_result: Optional[tuple] = None  # (success, message)

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


def _auto_setup_command():
    """Run setup command in background if not already configured"""
    global _setup_result
    try:
        if not is_command_available():
            success, msg = setup_command(show_output=False)
            _setup_result = (success, msg)
        else:
            _setup_result = (True, "Command already available")
    except Exception as e:
        _setup_result = (False, str(e))


def start_auto_setup():
    """Start auto-setup in background thread"""
    thread = threading.Thread(target=_auto_setup_command, daemon=True)
    thread.start()


def start_parallel_initialization():
    """
    Start all background initialization tasks in parallel.
    This includes:
    - Version check (fetches remote version for update notification)
    - Auto-setup (configures dymo-code command if not available)
    """
    threads = []

    # Version check thread
    version_thread = threading.Thread(target=_check_for_updates, daemon=True, name="version_check")
    threads.append(version_thread)

    # Auto-setup thread
    setup_thread = threading.Thread(target=_auto_setup_command, daemon=True, name="auto_setup")
    threads.append(setup_thread)

    # Start all threads
    for thread in threads:
        thread.start()

    return threads


def get_setup_result() -> Optional[tuple]:
    """Get the result of auto-setup (success, message) or None if not completed"""
    return _setup_result

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
# Auto-Update System
# ═══════════════════════════════════════════════════════════════════════════════

RELEASES_API_URL = "https://api.github.com/repos/TPEOficial/dymo-code/releases/latest"
_auto_update_info: Optional[dict] = None

def _fetch_latest_release_info() -> Optional[dict]:
    """Fetch latest release information from GitHub API"""
    try:
        request = Request(
            RELEASES_API_URL,
            headers={
                "User-Agent": "Dymo-Code-Update-Checker",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        ssl_context = _create_ssl_context()

        with urlopen(request, timeout=10, context=ssl_context) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

def _get_download_url_for_platform(release_info: dict) -> Optional[str]:
    """Get the appropriate download URL for the current platform"""
    if not release_info or "assets" not in release_info:
        return None

    platform = sys.platform
    assets = release_info.get("assets", [])

    # Determine file patterns based on platform
    if platform == "win32":
        patterns = ["windows", "win", ".exe", ".zip"]
    elif platform == "darwin":
        patterns = ["macos", "mac", "darwin", ".dmg", ".zip"]
    else:  # Linux and others
        patterns = ["linux", ".tar.gz", ".zip"]

    # Find matching asset
    for asset in assets:
        name = asset.get("name", "").lower()
        for pattern in patterns:
            if pattern in name:
                return asset.get("browser_download_url")

    # Fallback: try zipball URL
    return release_info.get("zipball_url")

def _download_file(url: str, dest_path: Path, progress_callback=None) -> bool:
    """Download a file from URL to destination path"""
    try:
        request = Request(url, headers={"User-Agent": "Dymo-Code-Updater"})
        ssl_context = _create_ssl_context()

        with urlopen(request, timeout=120, context=ssl_context) as response:
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 8192

            with open(dest_path, "wb") as f:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback and total_size > 0:
                        progress = downloaded / total_size
                        progress_callback(progress)

        return True
    except Exception as e:
        return False

def perform_auto_update() -> bool:
    """
    Perform automatic update:
    1. Download latest release
    2. Extract to temp location
    3. Replace current executable
    4. Return True if restart needed
    """
    global _auto_update_info

    console.print(f"\n[{COLORS['primary']}]Checking for updates...[/]")

    # Fetch release info
    release_info = _fetch_latest_release_info()
    if not release_info:
        console.print(f"[{COLORS['error']}]Could not fetch release information[/]")
        return False

    remote_version = release_info.get("tag_name", "").lstrip("v")
    local_version = get_version()

    if remote_version == local_version:
        console.print(f"[{COLORS['success']}]Already up to date (v{local_version})[/]")
        return False

    console.print(f"[{COLORS['warning']}]Update available: v{local_version} -> v{remote_version}[/]")

    # Get download URL
    download_url = _get_download_url_for_platform(release_info)
    if not download_url:
        console.print(f"[{COLORS['error']}]No download available for your platform[/]")
        console.print(f"[{COLORS['muted']}]Download manually: https://github.com/TPEOficial/dymo-code/releases[/]")
        return False

    console.print(f"[{COLORS['muted']}]Downloading update...[/]")

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp(prefix="dymo_update_"))

    try:
        # Determine file extension from URL
        url_path = download_url.split("?")[0]
        if ".zip" in url_path:
            ext = ".zip"
        elif ".tar.gz" in url_path:
            ext = ".tar.gz"
        elif ".exe" in url_path:
            ext = ".exe"
        else:
            ext = ".zip"

        download_path = temp_dir / f"dymo_update{ext}"

        # Download with progress
        def show_progress(progress):
            bar_width = 30
            filled = int(bar_width * progress)
            bar = "█" * filled + "░" * (bar_width - filled)
            sys.stdout.write(f"\r  [{bar}] {progress:.0%}")
            sys.stdout.flush()

        if not _download_file(download_url, download_path, show_progress):
            console.print(f"\n[{COLORS['error']}]Download failed[/]")
            return False

        console.print(f"\n[{COLORS['success']}]Download complete![/]")

        # Get current executable path
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            current_exe = Path(sys.executable)
        else:
            # Running as script - update the source
            current_exe = Path(__file__).parent.parent

        # Extract and update
        console.print(f"[{COLORS['muted']}]Installing update...[/]")

        if ext == ".zip":
            extract_dir = temp_dir / "extracted"
            with zipfile.ZipFile(download_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # Find the executable or main directory in extracted files
            extracted_items = list(extract_dir.iterdir())

            if getattr(sys, 'frozen', False):
                # For compiled exe: find new exe and replace
                new_exe = None
                for item in extract_dir.rglob("*"):
                    if item.is_file() and item.suffix == ".exe":
                        new_exe = item
                        break

                if new_exe:
                    # Create update script to replace exe after exit
                    update_script = temp_dir / "update.bat" if sys.platform == "win32" else temp_dir / "update.sh"

                    if sys.platform == "win32":
                        script_content = f'''@echo off
timeout /t 2 /nobreak >nul
copy /Y "{new_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
'''
                    else:
                        script_content = f'''#!/bin/bash
sleep 2
cp -f "{new_exe}" "{current_exe}"
chmod +x "{current_exe}"
"{current_exe}" &
rm "$0"
'''

                    with open(update_script, "w") as f:
                        f.write(script_content)

                    if sys.platform != "win32":
                        os.chmod(update_script, 0o755)

                    _auto_update_info = {"script": str(update_script), "version": remote_version}
                    console.print(f"[{COLORS['success']}]Update ready! Restart to apply v{remote_version}[/]")
                    return True
            else:
                # For source: update version.json
                for item in extract_dir.rglob("version.json"):
                    static_api_dir = current_exe / "static-api"
                    if static_api_dir.exists():
                        shutil.copy(item, static_api_dir / "version.json")

                console.print(f"[{COLORS['success']}]Updated to v{remote_version}![/]")
                return False

        elif ext == ".exe":
            # Direct exe download
            if getattr(sys, 'frozen', False):
                update_script = temp_dir / "update.bat"
                script_content = f'''@echo off
timeout /t 2 /nobreak >nul
copy /Y "{download_path}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
'''
                with open(update_script, "w") as f:
                    f.write(script_content)

                _auto_update_info = {"script": str(update_script), "version": remote_version}
                console.print(f"[{COLORS['success']}]Update ready! Restart to apply v{remote_version}[/]")
                return True

    except Exception as e:
        console.print(f"[{COLORS['error']}]Update failed: {str(e)}[/]")
        return False
    finally:
        # Cleanup temp files (except update script if needed)
        if _auto_update_info is None:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    return False

def apply_update_on_exit():
    """Run the update script on exit if an update was downloaded"""
    global _auto_update_info
    if _auto_update_info and "script" in _auto_update_info:
        script = _auto_update_info["script"]
        if os.path.exists(script):
            if sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", script], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.Popen(["bash", script])

def check_and_prompt_update() -> bool:
    """Check for updates and prompt user if available. Returns True if user wants to update."""
    if not _update_available:
        return False

    local_version = get_version()
    console.print(
        f"\n[{COLORS['warning']}]╔══════════════════════════════════════════════╗[/]"
    )
    console.print(
        f"[{COLORS['warning']}]║[/]  [bold]Update available![/] v{local_version} -> v{_update_available}       [{COLORS['warning']}]║[/]"
    )
    console.print(
        f"[{COLORS['warning']}]╚══════════════════════════════════════════════╝[/]\n"
    )

    console.print(f"[{COLORS['primary']}]Would you like to update now? (y/n):[/] ", end="")

    try:
        response = input().strip().lower()
        if response in ["y", "yes", "s", "si"]:
            return perform_auto_update()
    except (EOFError, KeyboardInterrupt):
        pass

    return False

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
    """Run the first-time setup to get user's name and configure the command"""
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

    # Setup command-line access - check if auto-setup already did it
    setup_result = get_setup_result()
    if setup_result:
        success, msg = setup_result
        if success and "already" not in msg.lower():
            console.print(f"[{COLORS['success']}]{msg}[/]")
            console.print(f"[{COLORS['muted']}]You can now use 'dymo-code' from any terminal.[/]")
            console.print()
        elif not success:
            console.print(f"[{COLORS['warning']}]Could not setup command: {msg}[/]")
            console.print(f"[{COLORS['muted']}]You can run setup later with /setup[/]")
            console.print()
    elif not is_command_available():
        # Auto-setup didn't run or hasn't finished, do it now
        console.print(f"[{COLORS['secondary']}]Setting up command-line access...[/]")
        success, msg = setup_command(show_output=False)
        if success:
            console.print(f"[{COLORS['success']}]{msg}[/]")
            console.print(f"[{COLORS['muted']}]You can now use 'dymo-code' from any terminal.[/]")
        else:
            console.print(f"[{COLORS['warning']}]Could not setup command: {msg}[/]")
            console.print(f"[{COLORS['muted']}]You can run setup later with /setup[/]")
        console.print()

    return name


# ═══════════════════════════════════════════════════════════════════════════════
# Main Loop
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point"""
    console.clear()
    print_banner()

    # Initialize dynamic terminal title
    terminal_title.set_title("Dymo Code")
    terminal_title.update(model=None, session=None, status="Starting...")

    # Start toast notification manager
    toast_manager.start()

    # Start parallel background tasks (version check + auto-setup)
    # This runs in separate threads so it doesn't block startup
    start_parallel_initialization()

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

    # Update terminal title with current model
    model_config = AVAILABLE_MODELS.get(agent.model_key)
    if model_config:
        terminal_title.update(model=model_config.name, status=None)

    # Welcome message - different for returning users
    if not user_config.is_first_run:
        console.print()
        console.print(f"[bold {COLORS['secondary']}]Welcome back, {username}![/]")
    console.print(f"[{COLORS['muted']}]Type [bold]/[/bold] to see commands or start chatting.[/]")
    console.print(f"[{COLORS['muted']}]You can type while the agent processes - messages will be queued.[/]")
    console.print(f"[{COLORS['muted']}]Try [bold]/themes[/bold] for color themes, [bold]/commands[/bold] for command palette.[/]")
    console.print()
    show_status(agent.model_key)
    console.print()

    # Check for background initialization results
    time.sleep(0.3)  # Small delay to allow background tasks to complete

    # Show setup result if it was performed (not for first-run users, they already saw it)
    if not user_config.is_first_run:
        setup_result = get_setup_result()
        if setup_result:
            success, msg = setup_result
            if success and "installed" in msg.lower():
                console.print(f"[{COLORS['success']}]{msg}[/]")
                console.print()

    # Check for updates and prompt user
    if check_and_prompt_update():
        console.print(f"\n[{COLORS['muted']}]Update will be applied after restart.[/]\n")

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

            # Connect status callback to spinner and terminal title
            def status_callback(status: str, detail: str = ""):
                async_input.update_status(status, detail)
                # Update terminal title with status
                if status == "streaming":
                    terminal_title.set_status("Responding...")
                else:
                    terminal_title.set_status(status.replace("_", " ").title())

            agent.set_status_callback(status_callback)

            # Start spinner with initial status
            async_input.start_processing("thinking")
            terminal_title.set_status("Thinking...")

            try:
                response_text = agent.chat(user_input)
                # Update suggestion context based on AI response for smart placeholder
                if response_text:
                    async_input.set_suggestion_context(response_text)
            finally:
                async_input.stop_processing()
                queue_manager.set_processing(False)
                async_input.set_processing(False)
                terminal_title.clear_status()

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
    toast_manager.stop()
    terminal_title.reset()
    memory.close()

    # Apply update if downloaded
    apply_update_on_exit()


if __name__ == "__main__": main()