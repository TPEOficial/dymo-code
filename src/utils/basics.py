import ctypes, platform, sys
from pathlib import Path

def get_project_root() -> Path:
    """
    Get the project root directory.
    Works both in development mode and when compiled with PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable (PyInstaller)
        return Path(sys._MEIPASS)
    else:
        # Running in development mode
        return Path(__file__).parent.parent.parent

def get_resource_path(relative_path: str) -> Path:
    """
    Get the absolute path to a resource file.
    Works both in development mode and when compiled with PyInstaller.

    Args:
        relative_path: Path relative to project root (e.g., 'static-api/version.json')

    Returns:
        Absolute path to the resource
    """
    return get_project_root() / relative_path

def set_terminal_title(title: str):
    system = platform.system()
    if system == "Windows": ctypes.windll.kernel32.SetConsoleTitleW(title)
    elif system in ["Linux", "Darwin"]: print(f"\033]0;{title}\007", end="", flush=True)
    else: raise OSError(f"Unsupported OS: {system}")