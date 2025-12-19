"""
Tool definitions and implementations for Dymo Code
"""

import os, subprocess, shutil
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass

# Import web tools
from .web_tools import (
    web_search,
    fetch_url,
    WEB_TOOL_DEFINITIONS,
    execute_web_tool
)

# Import multi-agent tools
from .multi_agent import (
    MULTI_AGENT_TOOL_DEFINITIONS,
    execute_multi_agent_tool,
    agent_pool
)

# ═══════════════════════════════════════════════════════════════════════════════
# File Change Tracking for Diff Display
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FileChange:
    """Represents a file change for diff display"""
    file_path: str
    change_type: str  # "create", "modify", "delete", "read"
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None

# Store the last file change for display
_last_file_change: Optional[FileChange] = None

def get_last_file_change() -> Optional[FileChange]:
    """Get the last file change for diff display"""
    global _last_file_change
    return _last_file_change

def clear_last_file_change():
    """Clear the last file change"""
    global _last_file_change
    _last_file_change = None

# ═══════════════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════════════

def format_size(size: int) -> str:
    """Format file size in human-readable format"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}" if unit != "B" else f"{size}{unit}"
        size /= 1024
    return f"{size:.1f}TB"

# ═══════════════════════════════════════════════════════════════════════════════
# Tool Implementations
# ═══════════════════════════════════════════════════════════════════════════════

def list_files_in_dir(directory: str = ".") -> str:
    """List all files and folders in a directory"""
    try:
        # Default to current directory if empty
        if not directory: directory = "."

        items = os.listdir(directory)
        if not items: return "Directory is empty."

        files = []
        dirs = []
        for item in items:
            path = os.path.join(directory, item)
            if os.path.isdir(path):
                dirs.append(f"[dir] {item}/")
            else:
                try:
                    size = os.path.getsize(path)
                    files.append(f"[file] {item} ({format_size(size)})")
                except OSError: files.append(f"[file] {item}")

        result = []
        if dirs: result.extend(sorted(dirs))
        if files: result.extend(sorted(files))

        return "\n".join(result)
    except FileNotFoundError: return f"Error: Directory '{directory}' not found."
    except PermissionError: return f"Error: Permission denied to access '{directory}'."
    except Exception as e: return f"Error: {str(e)}"

def read_file(file_path: str = "") -> str:
    """Read the contents of a file"""
    global _last_file_change

    if not file_path: return "Error: file_path is required"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Track the read operation for display
        _last_file_change = FileChange(
            file_path=file_path,
            change_type="read",
            new_content=content,
            success=True
        )

        return content if content else "(Empty file)"
    except FileNotFoundError:
        _last_file_change = FileChange(
            file_path=file_path,
            change_type="read",
            success=False,
            error_message=f"File '{file_path}' not found."
        )
        return f"Error: File '{file_path}' not found."
    except PermissionError:
        _last_file_change = FileChange(
            file_path=file_path,
            change_type="read",
            success=False,
            error_message=f"Permission denied to read '{file_path}'."
        )
        return f"Error: Permission denied to read '{file_path}'."
    except UnicodeDecodeError:
        _last_file_change = FileChange(
            file_path=file_path,
            change_type="read",
            success=False,
            error_message=f"File '{file_path}' is not a text file or has encoding issues."
        )
        return f"Error: File '{file_path}' is not a text file or has encoding issues."
    except Exception as e:
        _last_file_change = FileChange(
            file_path=file_path,
            change_type="read",
            success=False,
            error_message=str(e)
        )
        return f"Error: {str(e)}"


def create_folder(folder_path: str = "") -> str:
    """Create a new folder"""
    if not folder_path: return "Error: folder_path is required"

    try:
        os.makedirs(folder_path, exist_ok=True)
        return f"Successfully created folder: {folder_path}"
    except PermissionError: return f"Error: Permission denied to create '{folder_path}'."
    except Exception as e: return f"Error: {str(e)}"

def create_file(file_path: str = "", content: str = "") -> str:
    """Create or overwrite a file with given content"""
    global _last_file_change

    if not file_path: return "Error: file_path is required"

    try:
        # Check if file exists and read old content for diff
        old_content = None
        file_exists = os.path.exists(file_path)
        if file_exists:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    old_content = f.read()
            except: old_content = None

        # Ensure parent directory exists
        parent_dir = os.path.dirname(file_path)
        if parent_dir: os.makedirs(parent_dir, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Track the change for diff display
        _last_file_change = FileChange(
            file_path=file_path,
            change_type="modify" if file_exists else "create",
            old_content=old_content,
            new_content=content,
            success=True
        )

        return f"Successfully {'modified' if file_exists else 'created'} file: {file_path} ({len(content)} chars)"
    except PermissionError:
        _last_file_change = FileChange(
            file_path=file_path,
            change_type="create",
            new_content=content,
            success=False,
            error_message=f"Permission denied to write '{file_path}'."
        )
        return f"Error: Permission denied to write '{file_path}'."
    except Exception as e:
        _last_file_change = FileChange(
            file_path=file_path,
            change_type="create",
            new_content=content,
            success=False,
            error_message=str(e)
        )
        return f"Error: {str(e)}"


def run_command(command: str = "") -> str:
    """Execute a shell command and return output"""
    if not command: return "Error: command is required"

    # Check command permissions before executing
    try:
        from .command_permissions import check_and_request_permission
        if not check_and_request_permission(command):
            return "Error: Command execution denied by user."
    except ImportError:
        pass  # If module not available, allow execution

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.getcwd()
        )
        output = ""
        if result.stdout: output += result.stdout
        if result.stderr: output += f"\n[stderr]\n{result.stderr}" if output else result.stderr
        if result.returncode != 0: output += f"\n[exit code: {result.returncode}]"
        return output.strip() if output.strip() else "(No output)"
    except subprocess.TimeoutExpired: return "Error: Command timed out after 30 seconds."
    except Exception as e: return f"Error: {str(e)}"


def move_path(source: str = "", destination: str = "") -> str:
    """Move a file or folder from source to destination"""
    global _last_file_change

    if not source: return "Error: source path is required"
    if not destination: return "Error: destination path is required"

    try:
        # Check if source exists
        if not os.path.exists(source):
            return f"Error: Source '{source}' does not exist."

        # Determine if source is file or directory
        is_dir = os.path.isdir(source)
        item_type = "folder" if is_dir else "file"

        # If destination is a directory, move source into it
        if os.path.isdir(destination):
            dest_path = os.path.join(destination, os.path.basename(source))
        else:
            dest_path = destination
            # Ensure parent directory exists
            parent_dir = os.path.dirname(dest_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

        # Check if destination already exists
        if os.path.exists(dest_path):
            return f"Error: Destination '{dest_path}' already exists. Remove it first or choose a different name."

        # Perform the move
        shutil.move(source, dest_path)

        # Track the change
        _last_file_change = FileChange(
            file_path=source,
            change_type="move",
            new_content=f"Moved to: {dest_path}",
            success=True
        )

        return f"Successfully moved {item_type}: '{source}' → '{dest_path}'"

    except PermissionError:
        return f"Error: Permission denied to move '{source}'."
    except Exception as e:
        return f"Error: {str(e)}"


def delete_path(path: str = "", force: bool = False) -> str:
    """Delete a file or folder (requires user confirmation)"""
    global _last_file_change

    if not path: return "Error: path is required"

    try:
        # Check if path exists
        if not os.path.exists(path):
            return f"Error: Path '{path}' does not exist."

        # Determine if it's a file or directory
        is_dir = os.path.isdir(path)
        item_type = "folder" if is_dir else "file"

        # Get size/count info for confirmation message
        if is_dir:
            # Count items in directory
            item_count = sum(len(files) + len(dirs) for _, dirs, files in os.walk(path))
            size_info = f"containing {item_count} items"
        else:
            size = os.path.getsize(path)
            size_info = f"({_format_delete_size(size)})"

        # Request permission before deleting
        if not force:
            try:
                from .delete_permissions import check_and_request_delete_permission
                delete_info = f"{item_type.capitalize()}: {path} {size_info}"
                if not check_and_request_delete_permission(path, delete_info, is_dir):
                    return f"Delete operation cancelled by user."
            except ImportError:
                # Fallback if permission module not available - deny by default for safety
                return "Error: Delete permission system not available. Operation cancelled for safety."

        # Perform the deletion
        if is_dir:
            shutil.rmtree(path)
        else:
            os.remove(path)

        # Track the change
        _last_file_change = FileChange(
            file_path=path,
            change_type="delete",
            success=True
        )

        return f"Successfully deleted {item_type}: '{path}'"

    except PermissionError:
        return f"Error: Permission denied to delete '{path}'."
    except Exception as e:
        return f"Error: {str(e)}"


def _format_delete_size(size: int) -> str:
    """Format file size for delete confirmation"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}" if unit != "B" else f"{size}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Registry
# ═══════════════════════════════════════════════════════════════════════════════

TOOLS: Dict[str, Callable] = {
    "list_files_in_dir": list_files_in_dir,
    "read_file": read_file,
    "create_folder": create_folder,
    "create_file": create_file,
    "run_command": run_command,
    "move_path": move_path,
    "delete_path": delete_path,
    # Web tools
    "web_search": web_search,
    "fetch_url": fetch_url,
    # Aliases - some models use different names for the same tools
    "replace_file": create_file,      # Alias for create_file
    "write_file": create_file,        # Alias for create_file
    "edit_file": create_file,         # Alias for create_file
    "update_file": create_file,       # Alias for create_file
    "save_file": create_file,         # Alias for create_file
    "mkdir": create_folder,           # Alias for create_folder
    "execute": run_command,           # Alias for run_command
    "shell": run_command,             # Alias for run_command
    "ls": list_files_in_dir,          # Alias for list_files_in_dir
    "cat": read_file,                 # Alias for read_file
    "search": web_search,             # Alias for web_search
    "browse": fetch_url,              # Alias for fetch_url
    "mv": move_path,                  # Alias for move_path
    "rename": move_path,              # Alias for move_path (rename is just move)
    "rm": delete_path,                # Alias for delete_path
    "remove": delete_path,            # Alias for delete_path
    "del": delete_path                # Alias for delete_path (Windows style)
}

# ═══════════════════════════════════════════════════════════════════════════════
# Tool Definitions for API
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files_in_dir",
            "description": "List all files and folders in a directory with their types and sizes",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "The directory path to list (default: current directory)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read and return the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to read"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a new folder (and parent directories if needed)",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "The path of the folder to create"
                    }
                },
                "required": ["folder_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create or overwrite a file with the given content",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path of the file to create"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file"
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command and return its output. Use with caution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_path",
            "description": "Move or rename a file or folder from source to destination. Works for both files and directories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "The current path of the file or folder to move"
                    },
                    "destination": {
                        "type": "string",
                        "description": "The new path where the file or folder should be moved to"
                    }
                },
                "required": ["source", "destination"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_path",
            "description": "Delete a file or folder. Requires user confirmation before deletion for safety. Works for both files and directories (recursively deletes folder contents).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path of the file or folder to delete"
                    }
                },
                "required": ["path"]
            }
        }
    }
]


def execute_tool(name: str, args: Dict[str, Any]) -> str:
    """Execute a tool by name with given arguments"""
    # Strip common prefixes that some models add incorrectly
    # e.g., "repo_browser.list_files_in_dir" -> "list_files_in_dir"
    original_name = name
    prefixes_to_strip = ["repo_browser.", "functions.", "tools.", "file_ops.", "system."]
    for prefix in prefixes_to_strip:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    # Normalize argument names per tool (some models use different names)
    tool_arg_aliases = {
        "list_files_in_dir": {"path": "directory", "dir": "directory", "folder": "directory"},
        "read_file": {"path": "file_path", "filepath": "file_path", "filename": "file_path", "file": "file_path"},
        "create_file": {"path": "file_path", "filepath": "file_path", "filename": "file_path", "file": "file_path"},
        "create_folder": {"path": "folder_path", "directory": "folder_path", "dir": "folder_path"},
        "move_path": {"src": "source", "from": "source", "dst": "destination", "to": "destination", "dest": "destination"},
        "delete_path": {"file": "path", "filepath": "path", "file_path": "path", "target": "path"},
        "run_command": {"cmd": "command", "shell": "command", "exec": "command"},
    }

    # Apply argument normalization if tool has aliases defined
    if name in tool_arg_aliases:
        aliases = tool_arg_aliases[name]
        normalized_args = {}
        for key, value in args.items():
            new_key = aliases.get(key, key)
            # Avoid overwriting if the correct key already exists
            if new_key not in args and new_key not in normalized_args:
                normalized_args[new_key] = value
            else:
                normalized_args[key] = value
        args = normalized_args

    # Check if it's an MCP tool
    if name.startswith("mcp_"):
        try:
            from .mcp import execute_mcp_tool
            return execute_mcp_tool(name, args)
        except Exception as e: return f"Error executing MCP tool {name}: {str(e)}"

    # Check if it's a multi-agent tool
    if name in ("spawn_agents", "check_agent_tasks"):
        try:
            return execute_multi_agent_tool(name, args)
        except Exception as e: return f"Error executing multi-agent tool {name}: {str(e)}"

    if name not in TOOLS: return f"Error: Unknown tool '{name}'"

    try: return str(TOOLS[name](**args))
    except TypeError as e: return f"Error: Invalid arguments for {name}: {str(e)}"
    except Exception as e: return f"Error executing {name}: {str(e)}"

def get_all_tool_definitions() -> List[Dict[str, Any]]:
    """Get all tool definitions including web, multi-agent, and MCP tools"""
    all_tools = TOOL_DEFINITIONS.copy()

    # Add web tools
    all_tools.extend(WEB_TOOL_DEFINITIONS)

    # Add multi-agent tools
    all_tools.extend(MULTI_AGENT_TOOL_DEFINITIONS)

    # Add MCP tools if available
    try:
        from .mcp import get_mcp_tool_definitions
        mcp_tools = get_mcp_tool_definitions()
        all_tools.extend(mcp_tools)
    except Exception: pass

    return all_tools