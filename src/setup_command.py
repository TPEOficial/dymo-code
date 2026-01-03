"""
Multi-OS Command Setup for Dymo Code
Configures the 'dymo-code' command to be available system-wide
"""

import os
import sys
import subprocess
import ctypes
from pathlib import Path
from typing import Optional, Tuple

from rich.console import Console

console = Console(force_terminal=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Platform Detection
# ═══════════════════════════════════════════════════════════════════════════════

def get_platform() -> str:
    """Get the current platform"""
    if sys.platform == "win32": return "windows"
    elif sys.platform == "darwin": return "macos"
    else: return "linux"

def is_admin() -> bool:
    """Check if running with admin/root privileges"""
    if sys.platform == "win32":
        try: return ctypes.windll.shell32.IsUserAnAdmin()
        except: return False
    else: return os.geteuid() == 0


def get_executable_path() -> Path:
    """Get the path to the current executable"""
    if getattr(sys, 'frozen', False): return Path(sys.executable)
    else: return Path(__file__).parent / "main.py"

# ═══════════════════════════════════════════════════════════════════════════════
# Windows Setup
# ═══════════════════════════════════════════════════════════════════════════════

def setup_windows() -> Tuple[bool, str]:
    r"""
    Setup dymo-code command on Windows.

    Strategy:
    1. Create a batch file wrapper in %LOCALAPPDATA%\Dymo-Code\bin
    2. Add that directory to user PATH using Registry
    3. Broadcast the environment change to all windows

    Returns:
        (success, message)
    """
    try:
        # Create bin directory in local app data
        app_data = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local')))
        install_dir = app_data / "Dymo-Code"
        bin_dir = install_dir / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)

        # Determine the best executable path to use
        # Priority: 1. Compiled exe in install dir, 2. Current frozen exe, 3. Python script (fallback)
        installed_exe = install_dir / "dymo-code.exe"

        if installed_exe.exists():
            # Use the installed executable (relative path for portability)
            bat_content = f'@echo off\n"%~dp0..\\dymo-code.exe" %*'
        elif getattr(sys, 'frozen', False):
            # Running as compiled exe, use absolute path to current exe
            exe_path = get_executable_path()
            bat_content = f'@echo off\n"{exe_path}" %*'
        else:
            # Fallback: Python script (development mode only)
            python_exe = sys.executable
            project_root = Path(__file__).parent.parent
            run_script = project_root / "run.py"
            if run_script.exists():
                bat_content = f'@echo off\n"{python_exe}" "{run_script}" %*'
            else:
                exe_path = get_executable_path()
                bat_content = f'@echo off\n"{python_exe}" "{exe_path}" %*'

        # Remove any exe in bin directory (should only have bat/cmd)
        # This prevents conflicts where .exe takes priority over .bat/.cmd in PATHEXT
        bin_exe = bin_dir / "dymo-code.exe"
        if bin_exe.exists():
            try:
                bin_exe.unlink()
            except Exception:
                pass  # May be in use, will be cleaned up next time

        # Create batch file
        bat_path = bin_dir / "dymo-code.bat"
        bat_path.write_text(bat_content, encoding='utf-8')

        # Also create a cmd file for compatibility
        cmd_path = bin_dir / "dymo-code.cmd"
        cmd_path.write_text(bat_content, encoding='utf-8')

        # Add to PATH if not already there
        bin_dir_str = str(bin_dir)
        path_added = False

        # Get current user PATH using Registry
        try:
            import winreg

            # Open registry key for user environment
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Environment",
                0,
                winreg.KEY_READ | winreg.KEY_WRITE
            )

            try:
                current_path, reg_type = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                current_path = ""
                reg_type = winreg.REG_EXPAND_SZ

            # Check if already in PATH (case-insensitive comparison for Windows)
            path_entries = [p.strip() for p in current_path.split(';') if p.strip()]
            path_lower = [p.lower() for p in path_entries]

            if bin_dir_str.lower() not in path_lower:
                # Add to PATH
                if current_path:
                    # Remove any trailing semicolons and add our path
                    new_path = current_path.rstrip(';') + ';' + bin_dir_str
                else:
                    new_path = bin_dir_str

                # Use REG_EXPAND_SZ to preserve %VARIABLES%
                winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
                path_added = True

            winreg.CloseKey(key)

            # Broadcast environment change to all windows
            _broadcast_environment_change()

            if path_added:
                return True, f"Command 'dymo-code' installed at {bin_dir_str}. Restart terminal to use."
            else:
                return True, "Command 'dymo-code' is already configured."

        except ImportError:
            # winreg not available (shouldn't happen on Windows)
            # Fall back to setx but get current PATH properly
            try:
                # Get current user PATH from environment
                result = subprocess.run(
                    'reg query "HKEY_CURRENT_USER\\Environment" /v PATH',
                    capture_output=True,
                    shell=True,
                    text=True
                )

                current_path = ""
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if 'PATH' in line.upper() and 'REG_' in line.upper():
                            parts = line.split('REG_', 1)
                            if len(parts) > 1:
                                # Skip the type (EXPAND_SZ, SZ, etc.) and get the value
                                value_part = parts[1].split(None, 1)
                                if len(value_part) > 1:
                                    current_path = value_part[1].strip()
                                break

                # Check if already in PATH
                if bin_dir_str.lower() in current_path.lower():
                    return True, "Command 'dymo-code' is already configured."

                # Create new PATH
                if current_path:
                    new_path = current_path.rstrip(';') + ';' + bin_dir_str
                else:
                    new_path = bin_dir_str

                # Use setx to set the new PATH (max 1024 chars for setx)
                if len(new_path) > 1024:
                    return False, f"PATH too long. Add '{bin_dir_str}' to PATH manually."

                result = subprocess.run(
                    ['setx', 'PATH', new_path],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    return True, f"Command 'dymo-code' installed. Restart terminal to use."
                else:
                    return False, f"Could not update PATH. Add '{bin_dir_str}' to PATH manually."

            except Exception as e:
                return False, f"Could not update PATH: {str(e)}. Add '{bin_dir_str}' to PATH manually."

    except Exception as e:
        return False, f"Setup failed: {str(e)}"


def _broadcast_environment_change():
    """Broadcast environment change to all Windows applications"""
    try:
        # Try using ctypes directly (most reliable)
        import ctypes
        from ctypes import wintypes

        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002

        SendMessageTimeoutW = ctypes.windll.user32.SendMessageTimeoutW
        SendMessageTimeoutW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
            wintypes.LPCWSTR, wintypes.UINT, wintypes.UINT,
            ctypes.POINTER(wintypes.DWORD)
        ]
        SendMessageTimeoutW.restype = wintypes.LPARAM

        result = wintypes.DWORD()
        SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            5000,  # 5 second timeout
            ctypes.byref(result)
        )
    except Exception:
        # Fallback: try pywin32 if available
        try:
            import win32con
            import win32gui
            win32gui.SendMessageTimeout(
                win32con.HWND_BROADCAST,
                win32con.WM_SETTINGCHANGE,
                0,
                "Environment",
                win32con.SMTO_ABORTIFHUNG,
                5000
            )
        except ImportError:
            pass  # Can't broadcast, user will need to restart terminal


# ═══════════════════════════════════════════════════════════════════════════════
# macOS Setup
# ═══════════════════════════════════════════════════════════════════════════════

def setup_macos() -> Tuple[bool, str]:
    """
    Setup dymo-code command on macOS.

    Strategy:
    1. Try to create symlink in /usr/local/bin (if writable)
    2. Otherwise, create in ~/bin and add to PATH via shell profile

    Returns:
        (success, message)
    """
    try:
        exe_path = get_executable_path()
        home = Path.home()

        # Try /usr/local/bin first
        system_bin = Path("/usr/local/bin")
        link_path = system_bin / "dymo-code"

        if system_bin.exists() and os.access(system_bin, os.W_OK): return _create_symlink_or_script(exe_path, link_path)

        # Fall back to ~/bin
        user_bin = home / "bin"
        user_bin.mkdir(exist_ok=True)
        link_path = user_bin / "dymo-code"

        success, msg = _create_symlink_or_script(exe_path, link_path)

        if success:
            # Add ~/bin to PATH in shell profile
            shell = os.environ.get('SHELL', '/bin/bash')

            if 'zsh' in shell: profile = home / ".zshrc"
            else:
                profile = home / ".bash_profile"
                if not profile.exists(): profile = home / ".bashrc"

            path_line = f'\nexport PATH="$HOME/bin:$PATH"\n'

            if profile.exists():
                content = profile.read_text()
                if '$HOME/bin' not in content and '~/bin' not in content:
                    with open(profile, 'a') as f:
                        f.write(path_line)
                    return True, f"Command 'dymo-code' installed. Run 'source {profile}' or restart terminal."
            else:
                profile.write_text(path_line)
                return True, f"Command 'dymo-code' installed. Run 'source {profile}' or restart terminal."

            return True, "Command 'dymo-code' is ready to use."

        return success, msg

    except Exception as e: return False, f"Setup failed: {str(e)}"

# ═══════════════════════════════════════════════════════════════════════════════
# Linux Setup
# ═══════════════════════════════════════════════════════════════════════════════

def setup_linux() -> Tuple[bool, str]:
    """
    Setup dymo-code command on Linux.

    Strategy:
    1. Try to create symlink in /usr/local/bin (if writable or root)
    2. Otherwise, create in ~/.local/bin and add to PATH

    Returns:
        (success, message)
    """
    try:
        exe_path = get_executable_path()
        home = Path.home()

        # Try /usr/local/bin if we have permissions
        system_bin = Path("/usr/local/bin")

        if is_admin() or (system_bin.exists() and os.access(system_bin, os.W_OK)):
            link_path = system_bin / "dymo-code"
            return _create_symlink_or_script(exe_path, link_path)

        # Use ~/.local/bin (XDG standard)
        user_bin = home / ".local" / "bin"
        user_bin.mkdir(parents=True, exist_ok=True)
        link_path = user_bin / "dymo-code"

        success, msg = _create_symlink_or_script(exe_path, link_path)

        if success:
            # Check if ~/.local/bin is in PATH
            current_path = os.environ.get('PATH', '')
            user_bin_str = str(user_bin)

            if user_bin_str not in current_path:
                # Add to shell profile
                shell = os.environ.get('SHELL', '/bin/bash')

                if 'zsh' in shell: profile = home / ".zshrc"
                elif 'fish' in shell: profile = home / ".config" / "fish" / "config.fish"
                else: profile = home / ".bashrc"

                if 'fish' in shell: path_line = f'\nset -gx PATH $HOME/.local/bin $PATH\n'
                else: path_line = f'\nexport PATH="$HOME/.local/bin:$PATH"\n'

                if profile.exists():
                    content = profile.read_text()
                    if '.local/bin' not in content:
                        with open(profile, 'a') as f:
                            f.write(path_line)
                        return True, f"Command 'dymo-code' installed. Run 'source {profile}' or restart terminal."
                else:
                    profile.parent.mkdir(parents=True, exist_ok=True)
                    profile.write_text(path_line)
                    return True, f"Command 'dymo-code' installed. Run 'source {profile}' or restart terminal."

            return True, "Command 'dymo-code' is ready to use."

        return success, msg

    except Exception as e: return False, f"Setup failed: {str(e)}"

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _create_symlink_or_script(exe_path: Path, link_path: Path) -> Tuple[bool, str]:
    """Create a symlink or wrapper script"""
    try:
        # Remove existing if present
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()

        if getattr(sys, 'frozen', False):
            # For compiled exe, create symlink
            try:
                link_path.symlink_to(exe_path)
                return True, f"Command 'dymo-code' installed."
            except OSError: pass

        # Create wrapper script
        if sys.platform == "win32":
            script_content = f'@echo off\n"{exe_path}" %*'
        else:
            if getattr(sys, 'frozen', False): script_content = f'#!/bin/bash\nexec "{exe_path}" "$@"'
            else:
                python_exe = sys.executable
                script_content = f'#!/bin/bash\nexec "{python_exe}" "{exe_path}" "$@"'

        link_path.write_text(script_content)

        # Make executable on Unix
        if sys.platform != "win32":
            link_path.chmod(0o755)

        return True, f"Command 'dymo-code' installed."

    except PermissionError: return False, f"Permission denied. Run with sudo or as admin."
    except Exception as e: return False, f"Could not create command: {str(e)}"

def is_command_available() -> bool:
    """Check if dymo-code command is already available in PATH"""
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["where", "dymo-code"],
                capture_output=True,
                shell=True
            )
        else:
            result = subprocess.run(
                ["which", "dymo-code"],
                capture_output=True
            )
        return result.returncode == 0
    except: return False


def get_install_location() -> Optional[str]:
    """Get where dymo-code command is installed"""
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["where", "dymo-code"],
                capture_output=True,
                text=True,
                shell=True
            )
        else:
            result = subprocess.run(
                ["which", "dymo-code"],
                capture_output=True,
                text=True
            )

        if result.returncode == 0: return result.stdout.strip().split('\n')[0]
    except: pass
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# Main Setup Function
# ═══════════════════════════════════════════════════════════════════════════════

def setup_command(show_output: bool = True) -> Tuple[bool, str]:
    """
    Setup the dymo-code command for the current platform.

    Args:
        show_output: Whether to print status messages

    Returns:
        (success, message)
    """
    platform = get_platform()

    # Check if already set up
    if is_command_available():
        location = get_install_location()
        msg = f"Command 'dymo-code' is already available"
        if location: msg += f" at {location}"
        if show_output: console.print(f"[green]{msg}[/]")
        return True, msg

    if show_output:
        console.print(f"[cyan]Setting up 'dymo-code' command for {platform}...[/]")

    if platform == "windows": success, msg = setup_windows()
    elif platform == "macos": success, msg = setup_macos()
    else: success, msg = setup_linux()

    if show_output:
        if success: console.print(f"[green]{msg}[/]")
        else: console.print(f"[red]{msg}[/]")
    return success, msg

def uninstall_command() -> Tuple[bool, str]:
    """Remove the dymo-code command"""
    try:
        location = get_install_location()
        if location:
            path = Path(location)
            if path.exists():
                path.unlink()
                return True, f"Removed {location}"
        return True, "Command was not installed"
    except Exception as e: return False, f"Could not remove: {str(e)}"

# ═══════════════════════════════════════════════════════════════════════════════
# CLI Interface
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Setup dymo-code command")
    parser.add_argument("--uninstall", action="store_true", help="Remove the command")
    parser.add_argument("--check", action="store_true", help="Check if command is available")

    args = parser.parse_args()

    if args.check:
        if is_command_available(): print(f"dymo-code is available at: {get_install_location()}")
        else: print("dymo-code is not installed")
    elif args.uninstall:
        success, msg = uninstall_command()
        print(msg)
    else:
        success, msg = setup_command()
        sys.exit(0 if success else 1)