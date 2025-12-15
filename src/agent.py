"""
Main Agent class for Dymo Code
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass

from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED

from .config import COLORS, AVAILABLE_MODELS, DEFAULT_MODEL, get_system_prompt
from .clients import ClientManager, StreamChunk, ToolCall, ExecutedTool
from .tools import TOOL_DEFINITIONS, execute_tool, TOOLS, get_all_tool_definitions
from .ui import console, display_tool_call, display_tool_result, display_executed_tool, display_code_execution_result, display_info, display_warning
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

# Type for status callback
StatusCallback = Optional[Callable[[str, str], None]]

# Maximum number of tool call rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 5

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

    def set_status_callback(self, callback: StatusCallback):
        """Set a callback function for status updates"""
        self._status_callback = callback

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
        if len(conversation_msgs) <= keep_last:
            return False

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

    def _generate_title_async(self, first_message: str):
        """Generate title for the conversation"""
        try:
            title = self.client_manager.generate_title(first_message)
            history_manager.set_title(title)
            log_debug(f"Generated title: {title}")
        except Exception as e:
            log_error("Failed to generate title", e)

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

    def _execute_single_tool(self, tc, tool_call_id: int) -> tuple:
        """Execute a single tool call and return results"""
        # Parse arguments
        try:
            args = json.loads(tc.arguments) if tc.arguments else {}
        except json.JSONDecodeError as e:
            log_error("Failed to parse tool arguments", e, {"tool": tc.name, "args": tc.arguments})
            args = {}

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
        # Hide folder creation display as it's usually just a prep step
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
        # File operations show their own diff display
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

        for i, tc in enumerate(tool_calls):
            tc_result = self._execute_single_tool(tc, i)
            all_results.append(tc_result)
            if tc_result[3]:  # has_error flag
                has_any_error = True

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

        console.print()
        follow_up_response = ""
        pending_tool_calls = []
        has_content = False

        # Stream without Live panel first to collect response
        for chunk in client.stream_chat(
            messages=self.messages,
            model=model_id,
            tools=tools_for_followup
        ):
            if chunk.content:
                if not has_content:
                    has_content = True
                    # Start the panel only when we have content
                    console.print(f"[{COLORS['secondary']}]╭─ Assistant {'─' * 70}╮[/]")

                follow_up_response += chunk.content
                # Print content directly (streaming effect)
                console.print(chunk.content, end="", highlight=False)

            if chunk.tool_calls:
                pending_tool_calls.extend(chunk.tool_calls)

        # Close the panel if we printed content
        if has_content:
            console.print()
            console.print(f"[{COLORS['secondary']}]╰{'─' * 78}╯[/]")

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
            self.messages.append({"role": "user", "content": user_input})

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
            console.print(Panel(error_msg, border_style=f"{COLORS['error']}", box=ROUNDED))
            return error_msg

        # Compress context if needed (prevents token limit errors)
        if context_manager.should_compress(self.messages, self.model_key):
            state = context_manager.get_state(self.messages, self.model_key)
            display_info(f"Compressing conversation context ({state.usage_percent:.0%} used)...")
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
            has_started_panel = False

            # Update status to generating
            self._update_status("generating", "")

            for chunk in client.stream_chat(
                messages=self.messages,
                model=model_id,
                tools=all_tools
            ):
                # Handle content
                if chunk.content:
                    if not has_started_panel:
                        has_started_panel = True
                        # Update status to show we're getting a response
                        self._update_status("generating", "response")
                        console.print(f"[{COLORS['secondary']}]╭─ Assistant {'─' * 70}╮[/]")

                    response_text += chunk.content
                    # Stream content directly
                    console.print(chunk.content, end="", highlight=False)

                # Collect tool calls
                if chunk.tool_calls:
                    pending_tool_calls.extend(chunk.tool_calls)

                # Collect executed tools (from Groq built-in tools like code_interpreter)
                if chunk.executed_tools:
                    executed_tools_list.extend(chunk.executed_tools)

                # Handle reasoning from model
                if chunk.reasoning:
                    log_debug(f"Model reasoning: {chunk.reasoning[:200]}...")

            # Close the panel if we printed content
            if has_started_panel:
                console.print()
                console.print(f"[{COLORS['secondary']}]╰{'─' * 78}╯[/]")

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

            # Not a token error or max retries reached
            error_msg = f"Error: {error_str}"
            log_api_error(
                provider=AVAILABLE_MODELS[self.model_key].provider.value,
                model=model_id,
                error=error_str,
                request_context={"message_count": len(self.messages)}
            )
            console.print(Panel(error_msg, border_style=f"{COLORS['error']}", box=ROUNDED))
            return error_msg
