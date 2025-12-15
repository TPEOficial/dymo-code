"""
Logger module for Dymo Code
Handles logging errors and debug information to files
"""

import os
import logging
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# Logger Configuration
# ═══════════════════════════════════════════════════════════════════════════════

# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Log file paths
ERROR_LOG = LOGS_DIR / "errors.log"
DEBUG_LOG = LOGS_DIR / "debug.log"

# ═══════════════════════════════════════════════════════════════════════════════
# Logger Setup
# ═══════════════════════════════════════════════════════════════════════════════

def setup_logger(name: str, log_file: Path, level=logging.DEBUG) -> logging.Logger:
    """Set up a logger with file and optional console handlers"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)

    # Format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger

# Create loggers
error_logger = setup_logger('dymo.error', ERROR_LOG, logging.ERROR)
debug_logger = setup_logger('dymo.debug', DEBUG_LOG, logging.DEBUG)

# ═══════════════════════════════════════════════════════════════════════════════
# Logging Functions
# ═══════════════════════════════════════════════════════════════════════════════

def log_error(message: str, exception: Exception = None, context: dict = None):
    """Log an error with optional exception and context"""
    log_parts = [message]

    if exception:
        log_parts.append(f"Exception: {type(exception).__name__}: {str(exception)}")

    if context:
        log_parts.append(f"Context: {context}")

    error_logger.error(" | ".join(log_parts))


def log_debug(message: str, context: dict = None):
    """Log a debug message"""
    if context:
        debug_logger.debug(f"{message} | Context: {context}")
    else:
        debug_logger.debug(message)


def log_api_error(provider: str, model: str, error: str, request_context: dict = None):
    """Log an API error with relevant details"""
    log_parts = [
        f"API Error",
        f"Provider: {provider}",
        f"Model: {model}",
        f"Error: {error}"
    ]

    if request_context:
        log_parts.append(f"Request: {request_context}")

    error_logger.error(" | ".join(log_parts))


def log_tool_error(tool_name: str, args: dict, error: str):
    """Log a tool execution error"""
    error_logger.error(
        f"Tool Error | Tool: {tool_name} | Args: {args} | Error: {error}"
    )


def get_recent_errors(n: int = 10) -> list:
    """Get the last n errors from the log file"""
    if not ERROR_LOG.exists():
        return []

    try:
        with open(ERROR_LOG, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        return lines[-n:] if len(lines) >= n else lines
    except Exception:
        return []


def clear_logs():
    """Clear all log files"""
    for log_file in [ERROR_LOG, DEBUG_LOG]:
        if log_file.exists():
            log_file.unlink()
