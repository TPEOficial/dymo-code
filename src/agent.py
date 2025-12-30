"""
Main Agent class for Dymo Code
"""

import json
import re
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass
from pathlib import Path

from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED
from rich.markdown import Markdown

from .config import COLORS, AVAILABLE_MODELS, DEFAULT_MODEL, get_system_prompt, ModelProvider
from .clients import ClientManager, StreamChunk, ToolCall, ExecutedTool
from .lib.prompts import mode_manager
from .api_key_manager import (
    api_key_manager, is_rate_limit_error, is_credit_error,
    set_rotation_callbacks, model_fallback_manager
)
from .tools import TOOL_DEFINITIONS, execute_tool, TOOLS, get_all_tool_definitions
from .terminal import terminal_title
from .ui import (
    console, display_tool_call, display_tool_result, display_executed_tool,
    display_code_execution_result, display_info, display_warning,
    display_key_rotation_notice, display_model_fallback_notice, display_provider_exhausted_notice
)
from .logger import log_error, log_api_error, log_tool_error, log_debug
from .history import history_manager
from .name_detector import detect_and_save_name
from .context_manager import context_manager

# ═══════════════════════════════════════════════════════════════════════════════
# Error Detection Patterns
# ═══════════════════════════════════════════════════════════════════════════════

TOKEN_LIMIT_ERROR_PATTERNS = [
    "request too large",
    "too many tokens",
    "token limit",
    "context length exceeded",
    "maximum context length",
    "reduce your message size",
    "tokens per minute",
    "rate_limit_exceeded",
    "413",
    "context_length_exceeded",
    "max_tokens",
]

def is_token_limit_error(error: Exception) -> bool:
    """Check if an error is related to token/context limits"""
    error_str = str(error).lower()
    return any(pattern in error_str for pattern in TOKEN_LIMIT_ERROR_PATTERNS)


def is_quota_or_rate_error(error: str) -> bool:
    """Check if an error is a quota exhausted or rate limit error"""
    return is_rate_limit_error(error) or is_credit_error(error)


def get_friendly_quota_message(provider: str) -> str:
    """Get user-friendly message for quota errors"""
    from .lib.providers import get_provider_name
    name = get_provider_name(provider)
    return f"Your {name} credits have been exhausted or rate limited."


# Type for status callback
StatusCallback = Optional[Callable[[str, str], None]]

# Maximum number of tool call rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 3

# Pattern to detect file references with @ symbol
# Matches @path/to/file or @./relative/path or @C:\windows\path
FILE_REFERENCE_PATTERN = re.compile(r'@((?:[A-Za-z]:)?[^\s@]+)')

def process_file_references(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Process @ file references in text.
    Returns (processed_text, list_of_file_contents)

    Examples:
        @src/main.py -> reads src/main.py
        @./config.json -> reads ./config.json
        @C:\\path\\file.txt -> reads C:\\path\\file.txt
    """
    file_contents = []
    matches = FILE_REFERENCE_PATTERN.findall(text)

    for match in matches:
        file_path = match.strip()

        # Skip if it looks like an email
        if '@' in file_path or file_path.startswith('http'):
            continue

        # Resolve the path
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = Path(os.getcwd()) / path

            if path.exists():
                if path.is_file():
                    # Read file content
                    try:
                        content = path.read_text(encoding='utf-8', errors='replace')
                        file_contents.append({
                            "path": str(path),
                            "type": "file",
                            "content": content
                        })
                    except Exception as e:
                        file_contents.append({
                            "path": str(path),
                            "type": "file",
                            "error": f"Could not read file: {str(e)}"
                        })
                elif path.is_dir():
                    # List directory contents
                    try:
                        items = []
                        for item in path.iterdir():
                            item_type = "dir" if item.is_dir() else "file"
                            items.append(f"{'[DIR]' if item.is_dir() else '[FILE]'} {item.name}")
                        file_contents.append({
                            "path": str(path),
                            "type": "directory",
                            "content": "\n".join(sorted(items))
                        })
                    except Exception as e:
                        file_contents.append({
                            "path": str(path),
                            "type": "directory",
                            "error": f"Could not list directory: {str(e)}"
                        })
            else:
                file_contents.append({
                    "path": file_path,
                    "type": "unknown",
                    "error": "Path does not exist"
                })
        except Exception as e:
            file_contents.append({
                "path": file_path,
                "type": "unknown",
                "error": f"Invalid path: {str(e)}"
            })

    return text, file_contents


def format_file_context(file_contents: List[Dict[str, str]]) -> str:
    """Format file contents into context string for the AI"""
    if not file_contents:
        return ""

    context_parts = ["\n\n--- Referenced Files/Paths ---"]

    for item in file_contents:
        path = item.get("path", "unknown")
        item_type = item.get("type", "unknown")

        if "error" in item:
            context_parts.append(f"\n[{path}] Error: {item['error']}")
        elif item_type == "file":
            content = item.get("content", "")
            # Truncate very long files
            if len(content) > 10000:
                content = content[:10000] + "\n... [truncated, file too long]"
            context_parts.append(f"\n[{path}]\n```\n{content}\n```")
        elif item_type == "directory":
            content = item.get("content", "")
            context_parts.append(f"\n[{path}] (directory contents):\n{content}")

    context_parts.append("\n--- End Referenced Files ---\n")
    return "\n".join(context_parts)

# Patterns to detect tool calls in text responses
TOOL_CALL_PATTERNS = [
    # Pattern: <function/name>{"arg": "value"}</function
    r'<function/(\w+)>\s*(\{[^}]*\})\s*</function',
    # Pattern: <function name="name">{"arg": "value"}</function>
    r'<function\s+name="(\w+)">\s*(\{[^}]*\})\s*</function>',
    # Pattern: ```json\n{"name": "func", "arguments": {...}}```
    r'```json\s*\{\s*"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*(\{[^}]*\})\s*\}\s*```',
]

# ═══════════════════════════════════════════════════════════════════════════════
# Agent Class
# ═══════════════════════════════════════════════════════════════════════════════

class Agent:
    """Main AI agent that handles conversations and tool execution"""

    def __init__(self, model_key: str = DEFAULT_MODEL):
        self.model_key = model_key
        self.messages: List[Dict[str, Any]] = []
        self.client_manager = ClientManager()
        self.is_first_message = True
        self._status_callback: StatusCallback = None
        self._init_system_prompt()
        # Start a new conversation
        history_manager.start_new_conversation()
        # Set up rotation and fallback callbacks for user notifications
        self._setup_rotation_callbacks()

    def set_status_callback(self, callback: StatusCallback):
        """Set a callback function for status updates"""
        self._status_callback = callback

    def _setup_rotation_callbacks(self):
        """Set up callbacks for API key rotation and model fallback notifications"""
        def on_key_rotated(provider: str, old_key: str, new_key: str):
            display_key_rotation_notice(provider, "rate limit or quota exceeded")

        def on_model_fallback(provider: str, old_model: str, new_model: str):
            display_model_fallback_notice(provider, old_model, new_model)

        def on_provider_exhausted(provider: str):
            display_provider_exhausted_notice(provider)

        set_rotation_callbacks(
            on_key_rotated=on_key_rotated,
            on_model_fallback=on_model_fallback,
            on_provider_exhausted=on_provider_exhausted
        )

    def _update_status(self, status: str, detail: str = ""):
        """Send a status update if callback is set"""
        if self._status_callback:
            self._status_callback(status, detail)

    def _init_system_prompt(self):
        """Initialize the system prompt"""
        self.messages = [{"role": "system", "content": get_system_prompt()}]
        self.is_first_message = True

    def set_model(self, model_key: str) -> bool:
        """Switch to a different model"""
        if model_key not in AVAILABLE_MODELS:
            return False
        self.model_key = model_key
        log_debug(f"Model switched to {model_key}")
        return True

    def clear_history(self):
        """Clear conversation history and start new conversation"""
        self._init_system_prompt()
        history_manager.start_new_conversation()
        context_manager.reset()
        log_debug("Conversation cleared, new conversation started")

    def load_conversation(self, conversation_id: str) -> bool:
        """Load a previous conversation"""
        messages = history_manager.load_conversation(conversation_id)
        if messages:
            self.messages = messages
            self.is_first_message = False
            log_debug(f"Loaded conversation {conversation_id}")
            return True
        return False

    def add_memory_context(self, context: str):
        """
        Add memory context to the system prompt.
        This includes user information, facts, preferences, etc.
        """
        if not context:
            return

        # Find the system message and append memory context
        for msg in self.messages:
            if msg.get("role") == "system":
                msg["content"] = msg["content"] + f"\n\n# User Memory Context\n{context}"
                log_debug("Added memory context to system prompt")
                break

    def apply_mode(self, mode_prompt: str = None):
        """
        Apply a mode to the agent by modifying the system prompt.
        If mode_prompt is None, resets to default system prompt.
        """
        # Get the base system prompt
        base_prompt = get_system_prompt()

        if mode_prompt:
            # Prepend mode prompt to the system prompt
            new_prompt = f"{mode_prompt}\n\n---\n\n{base_prompt}"
        else:
            new_prompt = base_prompt

        # Update the system message
        for msg in self.messages:
            if msg.get("role") == "system":
                msg["content"] = new_prompt
                log_debug(f"Applied mode prompt to agent")
                break

        # Also store the mode prompt for reinitialization
        self._mode_prompt = mode_prompt

    def _emergency_context_reduction(self, keep_last: int = 4) -> bool:
        """
        Emergency context reduction when token limit is hit.
        More aggressive than normal compression - keeps only the most recent messages.

        Returns True if reduction was possible, False if already at minimum.
        """
        # Separate system prompt from conversation
        system_msg = None
        conversation_msgs = []

        for msg in self.messages:
            if msg.get("role") == "system":
                system_msg = msg
            else:
                conversation_msgs.append(msg)

        # If we don't have enough messages to reduce, we can't help
        if len(conversation_msgs) <= keep_last: return False

        # Keep only the last N messages (user + assistant pairs)
        messages_to_keep = conversation_msgs[-keep_last:]

        # Rebuild messages list
        new_messages = []
        if system_msg:
            new_messages.append(system_msg)

        # Add a context note about the reduction
        new_messages.append({
            "role": "user",
            "content": "[Context was reduced due to token limits. Previous conversation history has been cleared to continue.]"
        })
        new_messages.append({
            "role": "assistant",
            "content": "Understood. I'll continue with the available context."
        })

        new_messages.extend(messages_to_keep)

        old_count = len(self.messages)
        self.messages = new_messages
        log_debug(f"Emergency context reduction: {old_count} -> {len(self.messages)} messages")

        return True

    def _find_fallback_model(self, current_provider: str) -> Optional[str]:
        """
        Find an alternative model from a different provider that has available API keys.
        Returns the model key if found, None otherwise.
        """
        from .lib.providers import get_default_model

        # Get list of providers with available keys
        fallback_providers = api_key_manager.get_fallback_providers(current_provider)

        if not fallback_providers:
            return None

        # Priority order for fallback (prefer faster/cheaper options)
        priority_order = ["groq", "google", "openai", "anthropic", "openrouter"]

        # Sort fallback providers by priority
        fallback_providers.sort(key=lambda p: priority_order.index(p) if p in priority_order else 99)

        # Find the best model from fallback providers
        for provider in fallback_providers:
            # Check if the client for this provider is actually available (package installed)
            client = self.client_manager.get_client_for_provider(provider)
            if client and not client.is_available():
                continue  # Skip if client package not installed or not configured

            # First try the default model for this provider
            default_model = get_default_model(provider)
            if default_model and default_model in AVAILABLE_MODELS:
                return default_model

            # Fallback: find any model from this provider
            for model_key, model_config in AVAILABLE_MODELS.items():
                if model_config.provider.value == provider:
                    return model_key

        return None

    def _generate_title_async(self, first_message: str):
        """Generate title for the conversation in a background thread"""
        def _generate():
            try:
                title = self.client_manager.generate_title(first_message)
                history_manager.set_title(title)
                terminal_title.set_session(title)
                log_debug(f"Generated title: {title}")
            except Exception as e:
                log_error("Failed to generate title", e)

        # Run in background thread to not block the main flow
        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()

    def _save_conversation(self):
        """Save the current conversation state"""
        history_manager.update_conversation(self.messages)

    def _parse_tool_calls_from_text(self, text: str) -> List[ToolCall]:
        """
        Parse tool calls that appear as text in the response.
        Some models return tool calls as text instead of using the proper API.
        """
        tool_calls = []
        call_id = 0

        for pattern in TOOL_CALL_PATTERNS:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                func_name = match[0]
                args_str = match[1]

                # Validate that it's a known tool
                if func_name in TOOLS:
                    call_id += 1
                    tool_calls.append(ToolCall(
                        id=f"text_call_{call_id}",
                        name=func_name,
                        arguments=args_str
                    ))
                    log_debug(f"Parsed tool call from text: {func_name}")

        return tool_calls

    def _repair_json(self, json_str: str) -> str:
        """Attempt to repair malformed JSON from LLM responses"""
        if not json_str or not json_str.strip():
            return "{}"

        s = json_str.strip()

        # Extract JSON if wrapped in markdown code blocks
        if "```json" in s:
            start = s.find("```json") + 7
            end = s.find("```", start)
            if end > start:
                s = s[start:end].strip()
        elif "```" in s:
            start = s.find("```") + 3
            end = s.find("```", start)
            if end > start:
                s = s[start:end].strip()

        # Find the actual JSON object/array
        first_brace = s.find('{')
        first_bracket = s.find('[')
        if first_brace == -1 and first_bracket == -1:
            return "{}"

        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            s = s[first_brace:]
            # Find matching closing brace
            depth = 0
            in_string = False
            escape = False
            end_idx = len(s)
            for i, c in enumerate(s):
                if escape:
                    escape = False
                    continue
                if c == '\\':
                    escape = True
                    continue
                if c == '"' and not escape:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        end_idx = i + 1
                        break
            s = s[:end_idx]
        elif first_bracket != -1:
            s = s[first_bracket:]

        # Fix common JSON issues
        # Remove trailing commas before } or ]
        s = re.sub(r',\s*([}\]])', r'\1', s)

        # Balance braces if needed
        open_braces = s.count('{') - s.count('}')
        open_brackets = s.count('[') - s.count(']')
        s = s + '}' * max(0, open_braces) + ']' * max(0, open_brackets)

        return s

    def _parse_tool_args(self, tc) -> dict:
        """Parse tool call arguments with JSON repair for malformed responses"""
        try:
            if isinstance(tc.arguments, dict):
                return tc.arguments
            elif isinstance(tc.arguments, str) and tc.arguments.strip():
                return json.loads(tc.arguments)
            else:
                return {}
        except json.JSONDecodeError:
            # Try to repair the JSON
            try:
                repaired = self._repair_json(tc.arguments)
                result = json.loads(repaired)
                log_debug(f"Repaired malformed JSON for tool {tc.name}")
                return result
            except json.JSONDecodeError as e:
                log_error("Failed to parse tool arguments", e, {"tool": tc.name, "args": tc.arguments[:200] if tc.arguments else ""})
                return {}

    def _execute_tool_only(self, tc, args: dict) -> tuple:
        """Execute a tool without UI - for parallel execution"""
        result = execute_tool(tc.name, args)

        # Check if result indicates an error
        has_error = (
            result.startswith("Error") or
            "[exit code:" in result or
            "not recognized" in result.lower() or
            "command not found" in result.lower() or
            "no se reconoce" in result.lower() or
            "is not recognized" in result.lower()
        )

        if has_error:
            log_tool_error(tc.name, args, result)

        return tc, args, result, has_error

    def _execute_single_tool(self, tc, tool_call_id: int) -> tuple:
        """Execute a single tool call and return results (with UI)"""
        args = self._parse_tool_args(tc)

        # Get detail for status update
        detail = ""
        if tc.name == "create_folder":
            detail = args.get("folder_path", args.get("path", ""))
        elif tc.name == "create_file":
            detail = args.get("file_path", args.get("path", ""))
        elif tc.name == "read_file":
            detail = args.get("file_path", args.get("path", ""))
        elif tc.name == "run_command":
            cmd = args.get("command", "")
            detail = cmd[:40] + "..." if len(cmd) > 40 else cmd
        elif tc.name == "list_files_in_dir":
            detail = args.get("directory", args.get("path", "."))

        # Update status
        self._update_status(tc.name, detail)

        # Determine if we should show verbose tool info
        verbose = tc.name not in ["create_folder"]

        # Display and execute
        console.print()
        display_tool_call(tc.name, args, verbose=verbose)

        result = execute_tool(tc.name, args)

        # Check if result indicates an error
        has_error = (
            result.startswith("Error") or
            "[exit code:" in result or
            "not recognized" in result.lower() or
            "command not found" in result.lower() or
            "no se reconoce" in result.lower() or
            "is not recognized" in result.lower()
        )

        if has_error:
            log_tool_error(tc.name, args, result)

        # Only show result panel for verbose operations
        if verbose or has_error:
            display_tool_result(result, tc.name)

        return tc, args, result, has_error

    def _process_tool_calls_with_retry(
        self,
        tool_calls: List[Any],
        client,
        model_id: str,
        round_num: int = 1
    ) -> str:
        """Process tool calls with automatic retry on errors"""
        all_results = []
        has_any_error = False

        # For single tool call, use normal sequential execution with UI
        if len(tool_calls) == 1:
            tc_result = self._execute_single_tool(tool_calls[0], 0)
            all_results.append(tc_result)
            if tc_result[3]:
                has_any_error = True
        else:
            # For multiple tool calls, execute in parallel for speed
            self._update_status("executing", f"{len(tool_calls)} tools in parallel")

            # Parse all arguments first
            parsed_tools = [(tc, self._parse_tool_args(tc)) for tc in tool_calls]

            # Show what we're about to execute
            for tc, args in parsed_tools:
                verbose = tc.name not in ["create_folder"]
                console.print()
                display_tool_call(tc.name, args, verbose=verbose)

            # Execute all tools in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(len(tool_calls), 5)) as executor:
                futures = {
                    executor.submit(self._execute_tool_only, tc, args): (tc, args)
                    for tc, args in parsed_tools
                }

                # Collect results in order
                results_map = {}
                for future in as_completed(futures):
                    tc, args = futures[future]
                    try:
                        result = future.result()
                        results_map[tc.id] = result
                    except Exception as e:
                        results_map[tc.id] = (tc, args, f"Error: {str(e)}", True)

            # Maintain original order and show results
            for tc, args in parsed_tools:
                tc_result = results_map.get(tc.id, (tc, args, "Error: Unknown", True))
                all_results.append(tc_result)
                if tc_result[3]:
                    has_any_error = True

                # Show result
                verbose = tc.name not in ["create_folder"]
                if verbose or tc_result[3]:
                    display_tool_result(tc_result[2], tc.name)

        # Add tool calls to messages
        tool_calls_data = []
        for tc, args, result, has_error in all_results:
            tool_calls_data.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(args)
                }
            })

        self.messages.append({
            "role": "assistant",
            "tool_calls": tool_calls_data
        })

        # Add tool results with error context
        for tc, args, result, has_error in all_results:
            if has_error:
                result_content = f"[COMMAND FAILED]\n{result}\n\nPlease analyze this error and try an alternative approach."
            else:
                result_content = result

            self.messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_content
            })

        # Get follow-up response - ALWAYS allow more tool calls until MAX_TOOL_ROUNDS
        # This ensures the model can complete multi-step tasks (folder + file, etc.)
        allow_more_tools = round_num < MAX_TOOL_ROUNDS
        tools_for_followup = get_all_tool_definitions() if allow_more_tools else None

        # Reset status after tool execution to avoid spinner staying on "Writing file"
        self._update_status("thinking", "")

        console.print()
        follow_up_response = ""
        pending_tool_calls = []
        has_content = False
        live_display = None
        chunk_count = 0  # Buffer: only update display every N chunks

        # Stream with Live panel for smooth updates
        for chunk in client.stream_chat(
            messages=self.messages,
            model=model_id,
            tools=tools_for_followup
        ):
            if chunk.content:
                if not has_content:
                    has_content = True
                    # Stop spinner and start Live display
                    self._update_status("streaming", "")
                    live_display = Live(
                        Panel(Markdown(follow_up_response or "..."), title="Assistant", title_align="left", border_style=COLORS['secondary'], box=ROUNDED),
                        console=console,
                        refresh_per_second=4,
                        transient=True
                    )
                    live_display.start()

                follow_up_response += chunk.content
                chunk_count += 1
                # Update the live panel only every 5 chunks to reduce re-renders
                if live_display and chunk_count % 5 == 0:
                    live_display.update(
                        Panel(Markdown(follow_up_response), title="Assistant", title_align="left", border_style=COLORS['secondary'], box=ROUNDED)
                    )

            if chunk.tool_calls:
                pending_tool_calls.extend(chunk.tool_calls)

        # Stop live display and show final panel
        if live_display:
            live_display.stop()
        if has_content and follow_up_response:
            console.print(Panel(Markdown(follow_up_response), title="Assistant", title_align="left", border_style=COLORS['secondary'], box=ROUNDED))

        # Check for tool calls in text response
        if not pending_tool_calls and follow_up_response:
            text_tool_calls = self._parse_tool_calls_from_text(follow_up_response)
            if text_tool_calls:
                pending_tool_calls.extend(text_tool_calls)

        # If the model wants to use more tools, process them (for multi-step tasks)
        if pending_tool_calls and allow_more_tools:
            log_debug(f"Processing additional tools (round {round_num + 1})")
            if follow_up_response:
                self.messages.append({"role": "assistant", "content": follow_up_response})

            return self._process_tool_calls_with_retry(
                pending_tool_calls,
                client,
                model_id,
                round_num + 1
            )

        return follow_up_response

    def chat(self, user_input: str, _retry_count: int = 0) -> str:
        """Send a message and get a response"""
        # Only add user message on first attempt (not on retries)
        if _retry_count == 0:
            # Process @ file references
            processed_input, file_contents = process_file_references(user_input)
            file_context = format_file_context(file_contents)

            # Show info about referenced files
            if file_contents:
                valid_refs = [f for f in file_contents if "error" not in f]
                error_refs = [f for f in file_contents if "error" in f]
                if valid_refs:
                    display_info(f"Referenced {len(valid_refs)} file(s)/path(s)")
                for err_ref in error_refs:
                    display_warning(f"@{err_ref['path']}: {err_ref.get('error', 'unknown error')}")

            # Append file context to user input if any files were referenced
            final_input = user_input + file_context if file_context else user_input

            self.messages.append({"role": "user", "content": final_input})

            # Auto-detect and save user name if mentioned
            detected_name = detect_and_save_name(user_input)
            if detected_name:
                display_info(f"Nice to meet you, {detected_name}! I'll remember your name.")

            # Generate title on first message
            if self.is_first_message:
                self.is_first_message = False
                self._generate_title_async(user_input)

        try:
            client = self.client_manager.get_client(self.model_key)
            model_id = self.client_manager.get_model_id(self.model_key)
        except (RuntimeError, ValueError) as e:
            error_msg = str(e)
            log_error("Client initialization error", e)
            console.print()
            console.print(Panel(f"Error: {error_msg}", border_style=f"{COLORS['error']}", box=ROUNDED))
            return error_msg

        # Compress context if needed (prevents token limit errors)
        # Get state once and check if compression is needed
        context_state = context_manager.get_state(self.messages, self.model_key)
        if context_state.needs_compression:
            display_info(f"Compressing conversation context ({context_state.usage_percent:.0%} used)...")
            self.messages = context_manager.compress_context(
                self.messages,
                self.model_key,
                self.client_manager
            )

        response_text = ""
        pending_tool_calls = []
        executed_tools_list = []

        try:
            console.print()

            # Get all tools including MCP tools
            all_tools = get_all_tool_definitions()
            has_started_streaming = False
            live_display = None
            chunk_count = 0  # Buffer: only update display every N chunks

            # Update status to generating
            self._update_status("generating", "")

            for chunk in client.stream_chat(
                messages=self.messages,
                model=model_id,
                tools=all_tools
            ):
                # Handle content
                if chunk.content:
                    if not has_started_streaming:
                        has_started_streaming = True
                        # Stop spinner before showing content
                        self._update_status("streaming", "")
                        # Start Live display for streaming
                        live_display = Live(
                            Panel(Markdown(response_text or "..."), title="Assistant", title_align="left", border_style=COLORS['secondary'], box=ROUNDED),
                            console=console,
                            refresh_per_second=4,
                            transient=True
                        )
                        live_display.start()

                    response_text += chunk.content
                    chunk_count += 1
                    # Update the live panel only every 5 chunks to reduce re-renders
                    if live_display and chunk_count % 5 == 0:
                        live_display.update(
                            Panel(Markdown(response_text), title="Assistant", title_align="left", border_style=COLORS['secondary'], box=ROUNDED)
                        )

                # Collect tool calls
                if chunk.tool_calls:
                    pending_tool_calls.extend(chunk.tool_calls)

                # Collect executed tools (from Groq built-in tools like code_interpreter)
                if chunk.executed_tools:
                    executed_tools_list.extend(chunk.executed_tools)

                # Handle reasoning from model
                if chunk.reasoning:
                    log_debug(f"Model reasoning: {chunk.reasoning[:200]}...")

            # Stop live display and show final panel
            if live_display:
                live_display.stop()
            if has_started_streaming and response_text:
                console.print(Panel(Markdown(response_text), title="Assistant", title_align="left", border_style=COLORS['secondary'], box=ROUNDED))

            # Display executed tools (code execution, web search, etc.)
            if executed_tools_list:
                console.print()
                for et in executed_tools_list:
                    display_executed_tool(et.type, et.arguments, et.output)
                    # Check for errors in code execution
                    if et.type == "code_interpreter" and et.output:
                        if "error" in et.output.lower() or "traceback" in et.output.lower():
                            log_debug(f"Code execution had errors, model should auto-fix")

            # Check for tool calls embedded in text response
            if not pending_tool_calls and response_text:
                text_tool_calls = self._parse_tool_calls_from_text(response_text)
                if text_tool_calls:
                    log_debug(f"Found {len(text_tool_calls)} tool call(s) in text response")
                    pending_tool_calls.extend(text_tool_calls)

            # Process tool calls if any
            if pending_tool_calls:
                follow_up = self._process_tool_calls_with_retry(
                    pending_tool_calls,
                    client,
                    model_id,
                    round_num=1
                )
                response_text = follow_up

            self.messages.append({"role": "assistant", "content": response_text})

            # Save conversation after each exchange
            self._save_conversation()

            return response_text

        except Exception as e:
            error_str = str(e)

            # Check if this is a token limit error and we can retry
            if is_token_limit_error(e) and _retry_count < 3:
                log_debug(f"Token limit error detected (attempt {_retry_count + 1})")

                # Try emergency context reduction
                if self._emergency_context_reduction(keep_last=4 if _retry_count == 0 else 2):
                    display_warning(
                        f"Token limit exceeded. Reducing context and retrying... "
                        f"(attempt {_retry_count + 1}/3)"
                    )
                    # Retry with reduced context
                    return self.chat(user_input, _retry_count=_retry_count + 1)
                else:
                    # Can't reduce further - clear everything except system prompt and current message
                    display_warning("Token limit exceeded. Clearing conversation history to continue...")
                    self._init_system_prompt()
                    self.messages.append({"role": "user", "content": user_input})
                    return self.chat(user_input, _retry_count=_retry_count + 1)

            # Check if this is a quota/rate limit error - try model fallback first, then provider switch
            current_provider = AVAILABLE_MODELS[self.model_key].provider.value
            if is_quota_or_rate_error(error_str):
                log_debug(f"Quota/rate error detected for {current_provider}")

                # First, try to fallback to a simpler model within the same provider (if enabled)
                if model_fallback_manager.is_enabled() and _retry_count < 2:
                    fallback_model_id = model_fallback_manager.get_fallback_model(current_provider, model_id)
                    if fallback_model_id:
                        # Find the model key for this fallback model
                        for key, config in AVAILABLE_MODELS.items():
                            if config.id == fallback_model_id and config.provider.value == current_provider:
                                # Activate the fallback with notification
                                model_fallback_manager.activate_fallback(
                                    current_provider,
                                    model_id,
                                    fallback_model_id,
                                    duration_minutes=5
                                )
                                old_model_key = self.model_key
                                self.model_key = key
                                log_debug(f"Model fallback: {model_id} -> {fallback_model_id}")
                                # Retry with simpler model
                                return self.chat(user_input, _retry_count=_retry_count + 1)

                # Show friendly message
                friendly_msg = get_friendly_quota_message(current_provider)
                console.print()
                console.print(Panel(
                    friendly_msg,
                    border_style=f"{COLORS['warning']}",
                    box=ROUNDED
                ))

                # Try to find another available provider
                fallback_model = self._find_fallback_model(current_provider)
                if fallback_model:
                    old_model = self.model_key
                    self.model_key = fallback_model
                    new_provider = AVAILABLE_MODELS[fallback_model].provider.value
                    from .lib.providers import get_provider_name
                    console.print(f"[{COLORS['success']}]Switching to {get_provider_name(new_provider)} ({fallback_model})...[/]\n")
                    # Retry with new provider
                    return self.chat(user_input, _retry_count=0)
                else:
                    console.print(f"[{COLORS['error']}]No other providers available. Configure more API keys with /setapikey[/]")
                    return friendly_msg

            # Not a token error or quota error - show full error
            error_msg = f"Error: {error_str}"
            log_api_error(
                provider=current_provider,
                model=model_id,
                error=error_str,
                request_context={"message_count": len(self.messages)}
            )
            console.print()
            console.print(Panel(error_msg, border_style=f"{COLORS['error']}", box=ROUNDED))
            return error_msg
