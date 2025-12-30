#!/usr/bin/env python3
"""
Build script for Dymo Code
Creates standalone executables for Windows, macOS, and Linux

Usage:
    python build.py          # Build for current platform
    python build.py --clean  # Clean build artifacts before building
    python build.py --help   # Show help
"""

import subprocess
import sys
import shutil
import platform
from pathlib import Path

def get_platform_info():
    """Get current platform information"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows": return "windows", "exe", f"dymo-code-windows-{machine}.exe"
    elif system == "darwin": return "macos", "", f"dymo-code-macos-{machine}"
    else: return "linux", "", f"dymo-code-linux-{machine}"

def clean_build():
    """Clean build artifacts"""
    project_root = Path(__file__).parent

    dirs_to_clean = ["build", "dist", "__pycache__"]
    files_to_clean = ["*.pyc", "*.pyo", "*.spec.bak"]

    for dir_name in dirs_to_clean:
        dir_path = project_root / dir_name
        if dir_path.exists():
            print(f"Removing {dir_path}...")
            shutil.rmtree(dir_path)

    # Clean __pycache__ in subdirectories
    for pycache in project_root.rglob("__pycache__"):
        print(f"Removing {pycache}...")
        shutil.rmtree(pycache)

    print("Clean complete!")

def check_dependencies():
    """Check if required build dependencies are installed"""
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
        return True
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return True

def build():
    """Build the executable"""
    project_root = Path(__file__).parent
    spec_file = project_root / "dymo-code.spec"

    platform_name, ext, output_name = get_platform_info()

    print(f"\n{'='*60}")
    print(f"Building Dymo Code for {platform_name.upper()}")
    print(f"{'='*60}\n")

    # Check dependencies.
    check_dependencies()

    # Run PyInstaller.
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file)
    ]

    print(f"Running: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=str(project_root))

    if result.returncode != 0:
        print(f"\nBuild failed with return code {result.returncode}")
        sys.exit(1)

    # Rename output to platform-specific name
    dist_dir = project_root / "dist"
    if platform_name == "windows":
        original = dist_dir / "dymo-code.exe"
        renamed = dist_dir / output_name
    else:
        original = dist_dir / "dymo-code"
        renamed = dist_dir / output_name

    if original.exists():
        if renamed.exists(): renamed.unlink()
        original.rename(renamed)
        print(f"\n{'='*60}")
        print(f"Build successful!")
        print(f"Output: {renamed}")
        print(f"Size: {renamed.stat().st_size / (1024*1024):.2f} MB")
        print(f"{'='*60}\n")
    else: print(f"\nWarning: Expected output file not found at {original}")

def show_help():
    """Show help message"""
    print(__doc__)
    print("\nPlatform-specific notes:")
    print("  - Windows: Produces .exe file")
    print("  - macOS: Produces Unix executable")
    print("  - Linux: Produces Unix executable")
    print("\nNote: Cross-compilation is not supported.")
    print("      Build on each target platform separately.")

def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        show_help()
        return

    if "--clean" in args:
        clean_build()
        args.remove("--clean")

    if "--clean-only" in args:
        clean_build()
        return

    build()

if __name__ == "__main__": main()