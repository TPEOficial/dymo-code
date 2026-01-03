"""
Module for handling .dmcodeignore patterns
Works similar to .gitignore - files/folders matching patterns are ignored by tools
"""

import os
import sys
import fnmatch
from pathlib import Path
from typing import List, Set, Optional

# Cache for loaded patterns
_ignore_patterns: Optional[List[str]] = None
_ignore_patterns_file_mtime: Optional[float] = None
_ignore_patterns_file_path: Optional[Path] = None
_bundled_patterns: Optional[List[str]] = None

IGNORE_FILE_NAME = ".dmcodeignore"


def _get_bundled_base_path() -> Optional[Path]:
    """Get the base path for bundled files (PyInstaller)"""
    # Check if running from PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return None


def _load_bundled_patterns() -> List[str]:
    """Load patterns from bundled .dmcodeignore (inside the executable)"""
    global _bundled_patterns

    if _bundled_patterns is not None:
        return _bundled_patterns

    _bundled_patterns = []
    bundled_path = _get_bundled_base_path()

    if bundled_path:
        ignore_file = bundled_path / IGNORE_FILE_NAME
        if ignore_file.exists():
            try:
                with open(ignore_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        _bundled_patterns.append(line)
            except Exception:
                pass

    return _bundled_patterns


def _find_project_ignore_file(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Find project-specific .dmcodeignore file by searching:
    1. In the start_path (if provided)
    2. In current working directory
    3. Walking up the directory tree from cwd
    """
    search_paths = []

    # Add start_path if provided
    if start_path:
        search_paths.append(Path(start_path).resolve())

    # Add cwd
    cwd = Path(os.getcwd()).resolve()
    if cwd not in search_paths:
        search_paths.append(cwd)

    # Check each location and walk up
    for base in search_paths:
        current = base
        while current != current.parent:
            ignore_file = current / IGNORE_FILE_NAME
            if ignore_file.exists():
                return ignore_file
            current = current.parent

    return None


def _load_ignore_patterns(force_reload: bool = False, search_path: Optional[Path] = None) -> List[str]:
    """
    Load patterns from .dmcodeignore files.
    Merges bundled patterns (from executable) with project-specific patterns.
    Caches the result and reloads if file was modified.
    """
    global _ignore_patterns, _ignore_patterns_file_mtime, _ignore_patterns_file_path

    project_ignore_file = _find_project_ignore_file(search_path)

    # Check if we need to reload project patterns
    if not force_reload and _ignore_patterns is not None:
        if project_ignore_file:
            # Check if same file and not modified
            if project_ignore_file == _ignore_patterns_file_path:
                current_mtime = project_ignore_file.stat().st_mtime
                if current_mtime == _ignore_patterns_file_mtime:
                    return _ignore_patterns
        elif _ignore_patterns_file_path is None:
            # No file before and still no file - return cached
            return _ignore_patterns

    # Start with bundled patterns (from inside the executable)
    patterns = _load_bundled_patterns().copy()

    # Add project-specific patterns if found
    if project_ignore_file and project_ignore_file.exists():
        try:
            with open(project_ignore_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue
                    # Avoid duplicates
                    if line not in patterns:
                        patterns.append(line)
            _ignore_patterns_file_mtime = project_ignore_file.stat().st_mtime
            _ignore_patterns_file_path = project_ignore_file
        except Exception:
            _ignore_patterns_file_mtime = None
            _ignore_patterns_file_path = None
    else:
        _ignore_patterns_file_mtime = None
        _ignore_patterns_file_path = None

    _ignore_patterns = patterns
    return patterns


def _normalize_path(path: str, base_path: Optional[Path] = None) -> str:
    """Normalize path for pattern matching"""
    # Convert to Path for consistent handling
    p = Path(path)

    # Try to make relative to base_path or cwd
    if base_path:
        try:
            p = p.relative_to(base_path)
        except ValueError:
            pass
    else:
        try:
            p = p.relative_to(_get_project_root())
        except ValueError:
            pass

    # Use forward slashes for consistent matching
    return str(p).replace("\\", "/")


def _matches_pattern(path: str, pattern: str) -> bool:
    """
    Check if a path matches a gitignore-style pattern.

    Supports:
    - Simple patterns: *.pyc, __pycache__
    - Directory patterns: node_modules/, .git/
    - Path patterns: src/temp/*, build/**
    - Negation patterns: !important.pyc (not implemented yet)
    """
    # Normalize pattern
    pattern = pattern.replace("\\", "/").rstrip("/")

    # Handle negation (for future use)
    if pattern.startswith("!"):
        return False  # Negation patterns don't match directly

    # Check if pattern is meant for directories only (ends with /)
    is_dir_pattern = pattern.endswith("/")
    if is_dir_pattern:
        pattern = pattern[:-1]

    # Split path into parts for matching
    path_parts = path.split("/")
    pattern_parts = pattern.split("/")

    # If pattern has no directory separators, match against any path component
    if len(pattern_parts) == 1:
        for part in path_parts:
            if fnmatch.fnmatch(part, pattern):
                return True
        # Also try matching the full path
        return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, f"**/{pattern}")

    # Pattern has directory separators - match as path
    # Handle ** (match any number of directories)
    if "**" in pattern:
        # Convert ** to regex-like matching
        # For now, use fnmatch with recursive support
        pattern_glob = pattern.replace("**", "*")
        if fnmatch.fnmatch(path, pattern_glob):
            return True
        # Try matching with any prefix
        return fnmatch.fnmatch(path, f"**/{pattern_glob}")

    # Direct path matching
    if fnmatch.fnmatch(path, pattern):
        return True

    # Match from any directory level
    for i in range(len(path_parts)):
        subpath = "/".join(path_parts[i:])
        if fnmatch.fnmatch(subpath, pattern):
            return True

    return False


def should_ignore(path: str, base_path: Optional[Path] = None) -> bool:
    """
    Check if a path should be ignored based on .dmcodeignore patterns.

    Args:
        path: The path to check (can be absolute or relative)
        base_path: Optional base path for relative path calculation

    Returns:
        True if the path should be ignored, False otherwise
    """
    patterns = _load_ignore_patterns()

    if not patterns:
        return False

    normalized = _normalize_path(path, base_path)

    for pattern in patterns:
        if _matches_pattern(normalized, pattern):
            return True

    return False


def filter_paths(paths: List[str], base_path: Optional[Path] = None) -> List[str]:
    """
    Filter a list of paths, removing those that should be ignored.

    Args:
        paths: List of paths to filter
        base_path: Optional base path for relative path calculation

    Returns:
        List of paths that should NOT be ignored
    """
    patterns = _load_ignore_patterns()

    if not patterns:
        return paths

    return [p for p in paths if not should_ignore(p, base_path)]


def get_ignore_patterns() -> List[str]:
    """Get the currently loaded ignore patterns"""
    return _load_ignore_patterns().copy()


def reload_patterns():
    """Force reload of ignore patterns from file"""
    _load_ignore_patterns(force_reload=True)


def is_path_component_ignored(component: str) -> bool:
    """
    Quick check if a single path component (file/folder name) should be ignored.
    Useful for filtering during directory traversal.

    Args:
        component: A single file or folder name (not a path)

    Returns:
        True if this component matches any ignore pattern
    """
    patterns = _load_ignore_patterns()

    if not patterns:
        return False

    for pattern in patterns:
        # Only check patterns that are simple (no directory separators)
        if "/" not in pattern and "\\" not in pattern:
            pattern_clean = pattern.rstrip("/")
            if fnmatch.fnmatch(component, pattern_clean):
                return True

    return False
