import ctypes, platform

def set_terminal_title(title: str):
    system = platform.system()
    if system == "Windows": ctypes.windll.kernel32.SetConsoleTitleW(title)
    elif system in ["Linux", "Darwin"]: print(f"\033]0;{title}\007", end="", flush=True)
    else: raise OSError(f"Unsupported OS: {system}")