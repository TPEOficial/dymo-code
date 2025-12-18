"""
AI Client abstraction layer for Dymo Code
Supports multiple providers: Groq, OpenRouter, Anthropic (Claude), OpenAI, Ollama, Google Gemini
With automatic API key rotation on rate limits or credit exhaustion
"""

import os
import json
import httpx
from abc import ABC, abstractmethod
from typing import Iterator, Optional, Dict, Any, List
from dataclasses import dataclass

from .config import (
    ModelProvider, AVAILABLE_MODELS, UTILITY_MODEL, TITLE_GENERATION_PROMPT,
    ModelConfig, PROVIDER_CONFIGS
)
from .logger import log_api_error, log_error, log_debug
from .api_key_manager import (
    api_key_manager, is_rate_limit_error, is_credit_error, is_auth_error
)

# Groq built-in tools for code execution and web search
GROQ_BUILTIN_TOOLS = [
    {"type": "code_interpreter"},
    {"type": "browser_search"}
]

# ═══════════════════════════════════════════════════════════════════════════════
# Response Types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ToolCall:
    """Represents a tool call from the AI"""
    id: str
    name: str
    arguments: str

@dataclass
class ExecutedTool:
    """Represents a tool that was executed by Groq's built-in system"""
    index: int
    type: str
    arguments: str
    output: str

@dataclass
class StreamChunk:
    """Represents a chunk of streaming response"""
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    executed_tools: Optional[List[ExecutedTool]] = None
    reasoning: Optional[str] = None
    finish_reason: Optional[str] = None

# ═══════════════════════════════════════════════════════════════════════════════
# Base Client Interface
# ═══════════════════════════════════════════════════════════════════════════════

class BaseAIClient(ABC):
    """Abstract base class for AI clients"""

    @abstractmethod
    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Iterator[StreamChunk]:
        """Stream a chat completion"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this client is properly configured"""
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# Groq Client
# ═══════════════════════════════════════════════════════════════════════════════

class GroqClient(BaseAIClient):
    """Groq API client with automatic key rotation"""

    PROVIDER = "groq"

    def __init__(self):
        self._client = None
        self._current_api_key = None

    @property
    def api_key(self) -> Optional[str]:
        """Get API key from key manager (supports rotation)"""
        key = api_key_manager.get_key(self.PROVIDER)
        if key:
            return key
        # Fallback to environment
        return os.environ.get("GROQ_API_KEY")

    def _get_client(self):
        current_key = self.api_key
        # Recreate client if key changed
        if current_key != self._current_api_key:
            self._client = None
            self._current_api_key = current_key
        if self._client is None and current_key:
            from groq import Groq
            self._client = Groq(api_key=current_key)
        return self._client

    def is_available(self) -> bool:
        return api_key_manager.has_available_key(self.PROVIDER) or bool(os.environ.get("GROQ_API_KEY"))

    def _handle_error_and_retry(self, error: Exception, messages, model, tools, retry_count: int = 0):
        """Handle error with potential key rotation and retry"""
        error_str = str(error)
        max_retries = 3

        if retry_count >= max_retries:
            raise error

        # Check if error warrants key rotation
        if is_rate_limit_error(error_str) or is_credit_error(error_str) or is_auth_error(error_str):
            rotated, new_key = api_key_manager.report_error(self.PROVIDER, error_str)

            if rotated and new_key:
                log_debug(f"Groq: Rotated to new API key after error: {error_str[:50]}")
                # Reset client to use new key
                self._client = None
                self._current_api_key = None
                # Retry with new key
                return self.stream_chat(messages, model, tools, _retry_count=retry_count + 1)

        raise error

    def _is_compound_model(self, model: str) -> bool:
        """Check if the model is a Groq Compound model"""
        return model in ["compound", "compound-mini"]

    def _is_gpt_oss_model(self, model: str) -> bool:
        """Check if the model is a GPT-OSS model with built-in tools"""
        return model.startswith("openai/gpt-oss")

    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        _retry_count: int = 0
    ) -> Iterator[StreamChunk]:
        client = self._get_client()
        if not client:
            raise RuntimeError("GROQ_API_KEY not set. Use /setapikey groq <your-key>")

        # For Compound models, use non-streaming as they handle tools automatically
        if self._is_compound_model(model):
            yield from self._stream_compound_chat(client, messages, model)
            return

        # For GPT-OSS models, add built-in tools (code_interpreter, browser_search)
        if self._is_gpt_oss_model(model):
            yield from self._stream_gpt_oss_chat(client, messages, model, tools)
            return

        # Standard Groq models (Llama, etc.)
        kwargs = {
            "messages": messages,
            "model": model,
            "stream": True
        }
        if tools:
            kwargs["tools"] = tools

        try:
            stream = client.chat.completions.create(**kwargs)
        except Exception as e:
            error_str = str(e)
            log_api_error(
                provider="groq",
                model=model,
                error=error_str,
                request_context={
                    "message_count": len(messages),
                    "has_tools": bool(tools),
                    "tool_count": len(tools) if tools else 0
                }
            )
            # Try key rotation and retry
            if _retry_count < 3 and (is_rate_limit_error(error_str) or is_credit_error(error_str) or is_auth_error(error_str)):
                rotated, new_key = api_key_manager.report_error(self.PROVIDER, error_str)
                if rotated and new_key:
                    log_debug(f"Groq: Rotated to new API key, retrying...")
                    self._client = None
                    self._current_api_key = None
                    yield from self.stream_chat(messages, model, tools, _retry_count + 1)
                    return
            raise

        # Track tool calls across chunks
        current_tool_calls: Dict[int, Dict[str, str]] = {}

        for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta

            if delta.content:
                content = delta.content
                if "Failed to call a function" in content or "failed_generation" in content:
                    log_api_error(
                        provider="groq",
                        model=model,
                        error=content,
                        request_context={
                            "message_count": len(messages),
                            "has_tools": bool(tools),
                            "error_type": "function_call_failed"
                        }
                    )
                yield StreamChunk(content=content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in current_tool_calls:
                        current_tool_calls[idx] = {
                            "id": tc.id or f"call_{idx}",
                            "name": "",
                            "arguments": ""
                        }
                    if tc.function:
                        if tc.function.name:
                            current_tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            current_tool_calls[idx]["arguments"] += tc.function.arguments

            if choice.finish_reason:
                if choice.finish_reason == "error":
                    log_api_error(
                        provider="groq",
                        model=model,
                        error=f"Stream finished with error reason",
                        request_context={"finish_reason": choice.finish_reason}
                    )

                if current_tool_calls:
                    tool_calls = [
                        ToolCall(
                            id=tc["id"],
                            name=tc["name"],
                            arguments=tc["arguments"]
                        )
                        for tc in current_tool_calls.values()
                        if tc["name"]
                    ]
                    if tool_calls:
                        yield StreamChunk(tool_calls=tool_calls, finish_reason=choice.finish_reason)
                else:
                    yield StreamChunk(finish_reason=choice.finish_reason)

    def _stream_compound_chat(
        self,
        client,
        messages: List[Dict[str, Any]],
        model: str
    ) -> Iterator[StreamChunk]:
        """Handle Groq Compound models (automatic tool execution)"""
        try:
            # Compound models don't support streaming with tools
            response = client.chat.completions.create(
                messages=messages,
                model=model
            )

            message = response.choices[0].message

            # Yield content
            if message.content:
                yield StreamChunk(content=message.content)

            # Check for executed tools (code execution, web search, etc.)
            if hasattr(message, 'executed_tools') and message.executed_tools:
                executed = []
                for et in message.executed_tools:
                    executed.append(ExecutedTool(
                        index=et.get('index', 0),
                        type=et.get('type', 'unknown'),
                        arguments=et.get('arguments', ''),
                        output=et.get('output', '')
                    ))
                yield StreamChunk(executed_tools=executed)

            # Check for reasoning
            if hasattr(message, 'reasoning') and message.reasoning:
                yield StreamChunk(reasoning=message.reasoning)

            yield StreamChunk(finish_reason=response.choices[0].finish_reason or "stop")

        except Exception as e:
            log_api_error(
                provider="groq",
                model=model,
                error=str(e),
                request_context={"message_count": len(messages), "type": "compound"}
            )
            raise

    def _stream_gpt_oss_chat(
        self,
        client,
        messages: List[Dict[str, Any]],
        model: str,
        custom_tools: Optional[List[Dict[str, Any]]] = None
    ) -> Iterator[StreamChunk]:
        """Handle GPT-OSS models - always pass tools to avoid 'tool choice is none' error"""
        # GPT-OSS requires tools AND tool_choice to be passed, otherwise it errors

        # Import here to avoid circular imports
        from .tools import TOOL_DEFINITIONS

        try:
            kwargs = {
                "messages": messages,
                "model": model,
                "stream": True
            }

            # ALWAYS pass tools for GPT-OSS to avoid "tool choice is none" error
            # If no custom tools provided, use the default TOOL_DEFINITIONS
            tools_to_use = custom_tools if custom_tools else TOOL_DEFINITIONS
            kwargs["tools"] = tools_to_use
            kwargs["tool_choice"] = "auto"  # Let model decide when to use tools

            stream = client.chat.completions.create(**kwargs)

            # Track tool calls across chunks
            current_tool_calls: Dict[int, Dict[str, str]] = {}

            for chunk in stream:
                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    content = delta.content
                    if "Failed to call a function" in content or "failed_generation" in content:
                        log_api_error(
                            provider="groq",
                            model=model,
                            error=content,
                            request_context={
                                "message_count": len(messages),
                                "has_tools": bool(custom_tools),
                                "error_type": "function_call_failed"
                            }
                        )
                    yield StreamChunk(content=content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in current_tool_calls:
                            current_tool_calls[idx] = {
                                "id": tc.id or f"call_{idx}",
                                "name": "",
                                "arguments": ""
                            }
                        if tc.function:
                            if tc.function.name:
                                current_tool_calls[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                current_tool_calls[idx]["arguments"] += tc.function.arguments

                if choice.finish_reason:
                    if choice.finish_reason == "error":
                        log_api_error(
                            provider="groq",
                            model=model,
                            error=f"Stream finished with error reason",
                            request_context={"finish_reason": choice.finish_reason}
                        )

                    if current_tool_calls:
                        tool_calls = [
                            ToolCall(
                                id=tc["id"],
                                name=tc["name"],
                                arguments=tc["arguments"]
                            )
                            for tc in current_tool_calls.values()
                            if tc["name"]
                        ]
                        if tool_calls:
                            yield StreamChunk(tool_calls=tool_calls, finish_reason=choice.finish_reason)
                    else:
                        yield StreamChunk(finish_reason=choice.finish_reason)

        except Exception as e:
            error_str = str(e)
            # Check for known GPT-OSS errors and handle them
            if "repo_browser." in error_str or "tool_use_failed" in error_str:
                log_debug(f"GPT-OSS tool error, retrying with tools: {error_str[:100]}")
                # Retry with tools explicitly passed
                yield from self._retry_with_tools(client, messages, model, custom_tools)
            elif "Tool choice is none" in error_str:
                log_debug(f"Tool choice error, retrying with tool_choice=auto")
                yield from self._retry_with_tools(client, messages, model, custom_tools)
            else:
                log_api_error(
                    provider="groq",
                    model=model,
                    error=error_str,
                    request_context={
                        "message_count": len(messages),
                        "type": "gpt-oss",
                        "has_custom_tools": bool(custom_tools)
                    }
                )
                raise

    def _retry_with_tools(
        self,
        client,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Iterator[StreamChunk]:
        """Retry request with explicit tool configuration"""
        from .tools import TOOL_DEFINITIONS

        try:
            kwargs = {
                "messages": messages,
                "model": model,
                "stream": True
            }

            # ALWAYS pass tools for GPT-OSS
            tools_to_use = tools if tools else TOOL_DEFINITIONS
            kwargs["tools"] = tools_to_use
            kwargs["tool_choice"] = "auto"

            stream = client.chat.completions.create(**kwargs)

            current_tool_calls: Dict[int, Dict[str, str]] = {}

            for chunk in stream:
                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    yield StreamChunk(content=delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in current_tool_calls:
                            current_tool_calls[idx] = {
                                "id": tc.id or f"call_{idx}",
                                "name": "",
                                "arguments": ""
                            }
                        if tc.function:
                            if tc.function.name:
                                current_tool_calls[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                current_tool_calls[idx]["arguments"] += tc.function.arguments

                if choice.finish_reason:
                    if current_tool_calls:
                        tool_calls = [
                            ToolCall(
                                id=tc["id"],
                                name=tc["name"],
                                arguments=tc["arguments"]
                            )
                            for tc in current_tool_calls.values()
                            if tc["name"]
                        ]
                        if tool_calls:
                            yield StreamChunk(tool_calls=tool_calls, finish_reason=choice.finish_reason)
                    else:
                        yield StreamChunk(finish_reason=choice.finish_reason)

        except Exception as e:
            log_api_error(
                provider="groq",
                model=model,
                error=str(e),
                request_context={"message_count": len(messages), "type": "retry"}
            )
            raise

    def _fallback_stream(
        self,
        client,
        messages: List[Dict[str, Any]],
        model: str
    ) -> Iterator[StreamChunk]:
        """Fallback streaming without tools when model has issues"""
        try:
            stream = client.chat.completions.create(
                messages=messages,
                model=model,
                stream=True
            )

            for chunk in stream:
                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    yield StreamChunk(content=delta.content)

                if choice.finish_reason:
                    yield StreamChunk(finish_reason=choice.finish_reason)

        except Exception as e:
            log_api_error(
                provider="groq",
                model=model,
                error=str(e),
                request_context={"message_count": len(messages), "type": "fallback"}
            )
            raise

# ═══════════════════════════════════════════════════════════════════════════════
# OpenRouter Client
# ═══════════════════════════════════════════════════════════════════════════════

class OpenRouterClient(BaseAIClient):
    """OpenRouter API client (OpenAI-compatible) with automatic key rotation"""

    PROVIDER = "openrouter"

    def __init__(self):
        self._client = None
        self._current_api_key = None

    @property
    def api_key(self) -> Optional[str]:
        """Get API key from key manager (supports rotation)"""
        key = api_key_manager.get_key(self.PROVIDER)
        if key:
            return key
        return os.environ.get("OPENROUTER_API_KEY")

    def _get_client(self):
        current_key = self.api_key
        # Recreate client if key changed
        if current_key != self._current_api_key:
            self._client = None
            self._current_api_key = current_key
        if self._client is None and current_key:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=current_key,
                base_url="https://openrouter.ai/api/v1"
            )
        return self._client

    def is_available(self) -> bool:
        return api_key_manager.has_available_key(self.PROVIDER) or bool(os.environ.get("OPENROUTER_API_KEY"))

    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        _retry_count: int = 0
    ) -> Iterator[StreamChunk]:
        client = self._get_client()
        if not client:
            raise RuntimeError("OPENROUTER_API_KEY not set. Use /setapikey openrouter <your-key>")

        kwargs = {
            "messages": messages,
            "model": model,
            "stream": True
        }
        if tools:
            kwargs["tools"] = tools

        try:
            stream = client.chat.completions.create(**kwargs)
        except Exception as e:
            error_str = str(e)
            log_api_error(
                provider="openrouter",
                model=model,
                error=error_str,
                request_context={
                    "message_count": len(messages),
                    "has_tools": bool(tools),
                    "tool_count": len(tools) if tools else 0
                }
            )
            # Try key rotation and retry
            if _retry_count < 3 and (is_rate_limit_error(error_str) or is_credit_error(error_str) or is_auth_error(error_str)):
                rotated, new_key = api_key_manager.report_error(self.PROVIDER, error_str)
                if rotated and new_key:
                    log_debug(f"OpenRouter: Rotated to new API key, retrying...")
                    self._client = None
                    self._current_api_key = None
                    yield from self.stream_chat(messages, model, tools, _retry_count + 1)
                    return
            raise

        # Track tool calls across chunks
        current_tool_calls: Dict[int, Dict[str, str]] = {}

        for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta

            # Check for error content in the response
            if delta.content:
                content = delta.content
                if "Failed to call a function" in content or "failed_generation" in content:
                    log_api_error(
                        provider="openrouter",
                        model=model,
                        error=content,
                        request_context={
                            "message_count": len(messages),
                            "has_tools": bool(tools),
                            "error_type": "function_call_failed"
                        }
                    )
                yield StreamChunk(content=content)

            # Handle tool calls
            if hasattr(delta, 'tool_calls') and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in current_tool_calls:
                        current_tool_calls[idx] = {
                            "id": tc.id or f"call_{idx}",
                            "name": "",
                            "arguments": ""
                        }
                    if tc.function:
                        if tc.function.name:
                            current_tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            current_tool_calls[idx]["arguments"] += tc.function.arguments

            # Check for finish
            if choice.finish_reason:
                if choice.finish_reason == "error":
                    log_api_error(
                        provider="openrouter",
                        model=model,
                        error=f"Stream finished with error reason",
                        request_context={"finish_reason": choice.finish_reason}
                    )

                if current_tool_calls:
                    tool_calls = [
                        ToolCall(
                            id=tc["id"],
                            name=tc["name"],
                            arguments=tc["arguments"]
                        )
                        for tc in current_tool_calls.values()
                        if tc["name"]
                    ]
                    if tool_calls:
                        yield StreamChunk(tool_calls=tool_calls, finish_reason=choice.finish_reason)
                else:
                    yield StreamChunk(finish_reason=choice.finish_reason)

# ═══════════════════════════════════════════════════════════════════════════════
# Anthropic (Claude) Client
# ═══════════════════════════════════════════════════════════════════════════════

class AnthropicClient(BaseAIClient):
    """Anthropic Claude API client with automatic key rotation"""

    PROVIDER = "anthropic"

    def __init__(self):
        self._client = None
        self._current_api_key = None

    @property
    def api_key(self) -> Optional[str]:
        """Get API key from key manager (supports rotation)"""
        key = api_key_manager.get_key(self.PROVIDER)
        if key:
            return key
        return os.environ.get("ANTHROPIC_API_KEY")

    def _get_client(self):
        current_key = self.api_key
        # Recreate client if key changed
        if current_key != self._current_api_key:
            self._client = None
            self._current_api_key = current_key
        if self._client is None and current_key:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=current_key)
            except ImportError:
                raise RuntimeError("anthropic package not installed. Run: pip install anthropic")
        return self._client

    def is_available(self) -> bool:
        return api_key_manager.has_available_key(self.PROVIDER) or bool(os.environ.get("ANTHROPIC_API_KEY"))

    def _convert_tools_to_anthropic_format(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI-style tools to Anthropic format"""
        anthropic_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}})
                })
        return anthropic_tools

    def _convert_messages_for_anthropic(self, messages: List[Dict[str, Any]]) -> tuple:
        """Convert messages to Anthropic format, extracting system prompt"""
        system_prompt = ""
        converted_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = content
            elif role == "user":
                converted_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                if "tool_calls" in msg and msg["tool_calls"]:
                    # Convert tool calls to Anthropic format
                    content_blocks = []
                    if content:
                        content_blocks.append({"type": "text", "text": content})
                    for tc in msg["tool_calls"]:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
                        })
                    converted_messages.append({"role": "assistant", "content": content_blocks})
                else:
                    converted_messages.append({"role": "assistant", "content": content})
            elif role == "tool":
                # Find the corresponding assistant message with tool_use
                converted_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": content
                    }]
                })

        return system_prompt, converted_messages

    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        _retry_count: int = 0
    ) -> Iterator[StreamChunk]:
        client = self._get_client()
        if not client:
            raise RuntimeError("ANTHROPIC_API_KEY not set. Use /setapikey anthropic <your-key>")

        system_prompt, converted_messages = self._convert_messages_for_anthropic(messages)

        kwargs = {
            "model": model,
            "messages": converted_messages,
            "max_tokens": 8192,
            "stream": True
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if tools:
            anthropic_tools = self._convert_tools_to_anthropic_format(tools)
            if anthropic_tools:
                kwargs["tools"] = anthropic_tools

        try:
            current_tool_calls: Dict[str, Dict[str, Any]] = {}
            current_tool_id = None

            with client.messages.stream(**kwargs) as stream:
                for event in stream:
                    if hasattr(event, 'type'):
                        if event.type == 'content_block_start':
                            if hasattr(event, 'content_block'):
                                block = event.content_block
                                if hasattr(block, 'type') and block.type == 'tool_use':
                                    current_tool_id = block.id
                                    current_tool_calls[current_tool_id] = {
                                        "id": block.id,
                                        "name": block.name,
                                        "arguments": ""
                                    }

                        elif event.type == 'content_block_delta':
                            if hasattr(event, 'delta'):
                                delta = event.delta
                                if hasattr(delta, 'type'):
                                    if delta.type == 'text_delta' and hasattr(delta, 'text'):
                                        yield StreamChunk(content=delta.text)
                                    elif delta.type == 'input_json_delta' and hasattr(delta, 'partial_json'):
                                        if current_tool_id and current_tool_id in current_tool_calls:
                                            current_tool_calls[current_tool_id]["arguments"] += delta.partial_json

                        elif event.type == 'message_stop':
                            if current_tool_calls:
                                tool_calls = [
                                    ToolCall(
                                        id=tc["id"],
                                        name=tc["name"],
                                        arguments=tc["arguments"]
                                    )
                                    for tc in current_tool_calls.values()
                                    if tc["name"]
                                ]
                                if tool_calls:
                                    yield StreamChunk(tool_calls=tool_calls, finish_reason="tool_use")
                            yield StreamChunk(finish_reason="stop")

        except Exception as e:
            error_str = str(e)
            log_api_error(
                provider="anthropic",
                model=model,
                error=error_str,
                request_context={"message_count": len(messages), "has_tools": bool(tools)}
            )
            # Try key rotation and retry
            if _retry_count < 3 and (is_rate_limit_error(error_str) or is_credit_error(error_str) or is_auth_error(error_str)):
                rotated, new_key = api_key_manager.report_error(self.PROVIDER, error_str)
                if rotated and new_key:
                    log_debug(f"Anthropic: Rotated to new API key, retrying...")
                    self._client = None
                    self._current_api_key = None
                    yield from self.stream_chat(messages, model, tools, _retry_count + 1)
                    return
            raise


# ═══════════════════════════════════════════════════════════════════════════════
# OpenAI Client
# ═══════════════════════════════════════════════════════════════════════════════

class OpenAIClient(BaseAIClient):
    """OpenAI API client with automatic key rotation"""

    PROVIDER = "openai"

    def __init__(self):
        self._client = None
        self._current_api_key = None

    @property
    def api_key(self) -> Optional[str]:
        """Get API key from key manager (supports rotation)"""
        key = api_key_manager.get_key(self.PROVIDER)
        if key:
            return key
        return os.environ.get("OPENAI_API_KEY")

    def _get_client(self):
        current_key = self.api_key
        # Recreate client if key changed
        if current_key != self._current_api_key:
            self._client = None
            self._current_api_key = current_key
        if self._client is None and current_key:
            from openai import OpenAI
            self._client = OpenAI(api_key=current_key)
        return self._client

    def is_available(self) -> bool:
        return api_key_manager.has_available_key(self.PROVIDER) or bool(os.environ.get("OPENAI_API_KEY"))

    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        _retry_count: int = 0
    ) -> Iterator[StreamChunk]:
        client = self._get_client()
        if not client:
            raise RuntimeError("OPENAI_API_KEY not set. Use /setapikey openai <your-key>")

        # Check if model supports tools (o1 models don't)
        model_config = None
        for key, config in AVAILABLE_MODELS.items():
            if config.id == model:
                model_config = config
                break

        supports_tools = model_config.supports_tools if model_config else True

        kwargs = {
            "messages": messages,
            "model": model,
            "stream": True
        }

        if tools and supports_tools:
            kwargs["tools"] = tools

        try:
            stream = client.chat.completions.create(**kwargs)
        except Exception as e:
            error_str = str(e)
            log_api_error(
                provider="openai",
                model=model,
                error=error_str,
                request_context={"message_count": len(messages), "has_tools": bool(tools)}
            )
            # Try key rotation and retry
            if _retry_count < 3 and (is_rate_limit_error(error_str) or is_credit_error(error_str) or is_auth_error(error_str)):
                rotated, new_key = api_key_manager.report_error(self.PROVIDER, error_str)
                if rotated and new_key:
                    log_debug(f"OpenAI: Rotated to new API key, retrying...")
                    self._client = None
                    self._current_api_key = None
                    yield from self.stream_chat(messages, model, tools, _retry_count + 1)
                    return
            raise

        current_tool_calls: Dict[int, Dict[str, str]] = {}

        for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta

            if delta.content:
                yield StreamChunk(content=delta.content)

            if hasattr(delta, 'tool_calls') and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in current_tool_calls:
                        current_tool_calls[idx] = {
                            "id": tc.id or f"call_{idx}",
                            "name": "",
                            "arguments": ""
                        }
                    if tc.function:
                        if tc.function.name:
                            current_tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            current_tool_calls[idx]["arguments"] += tc.function.arguments

            if choice.finish_reason:
                if current_tool_calls:
                    tool_calls = [
                        ToolCall(
                            id=tc["id"],
                            name=tc["name"],
                            arguments=tc["arguments"]
                        )
                        for tc in current_tool_calls.values()
                        if tc["name"]
                    ]
                    if tool_calls:
                        yield StreamChunk(tool_calls=tool_calls, finish_reason=choice.finish_reason)
                else:
                    yield StreamChunk(finish_reason=choice.finish_reason)


# ═══════════════════════════════════════════════════════════════════════════════
# Ollama Client
# ═══════════════════════════════════════════════════════════════════════════════

class OllamaClient(BaseAIClient):
    """Ollama API client for local LLM inference"""

    def __init__(self):
        self._http_client = None

    @property
    def base_url(self) -> str:
        """Get base URL from environment (dynamic)"""
        return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    def _get_client(self):
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=120.0)
        return self._http_client

    def is_available(self) -> bool:
        """Check if Ollama is running"""
        try:
            client = self._get_client()
            response = client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    def _convert_tools_to_ollama_format(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI-style tools to Ollama format"""
        ollama_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "parameters": func.get("parameters", {"type": "object", "properties": {}})
                    }
                })
        return ollama_tools

    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Iterator[StreamChunk]:
        client = self._get_client()

        # Convert messages (remove tool-specific fields if model doesn't support tools)
        converted_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "tool":
                # Convert tool results to user messages
                converted_messages.append({
                    "role": "user",
                    "content": f"Tool result: {content}"
                })
            elif role == "assistant" and "tool_calls" in msg:
                # Skip tool call messages, include only text content
                if content:
                    converted_messages.append({"role": "assistant", "content": content})
            else:
                converted_messages.append({"role": role, "content": content})

        payload = {
            "model": model,
            "messages": converted_messages,
            "stream": True
        }

        # Check if model supports tools
        model_config = None
        for key, config in AVAILABLE_MODELS.items():
            if config.id == model:
                model_config = config
                break

        if tools and model_config and model_config.supports_tools:
            payload["tools"] = self._convert_tools_to_ollama_format(tools)

        try:
            with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload
            ) as response:
                response.raise_for_status()

                current_tool_calls: Dict[int, Dict[str, str]] = {}

                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)

                            # Handle message content
                            if "message" in data:
                                msg = data["message"]
                                if "content" in msg and msg["content"]:
                                    yield StreamChunk(content=msg["content"])

                                # Handle tool calls
                                if "tool_calls" in msg:
                                    for i, tc in enumerate(msg["tool_calls"]):
                                        current_tool_calls[i] = {
                                            "id": f"ollama_call_{i}",
                                            "name": tc.get("function", {}).get("name", ""),
                                            "arguments": json.dumps(tc.get("function", {}).get("arguments", {}))
                                        }

                            # Check if done
                            if data.get("done", False):
                                if current_tool_calls:
                                    tool_calls = [
                                        ToolCall(
                                            id=tc["id"],
                                            name=tc["name"],
                                            arguments=tc["arguments"]
                                        )
                                        for tc in current_tool_calls.values()
                                        if tc["name"]
                                    ]
                                    if tool_calls:
                                        yield StreamChunk(tool_calls=tool_calls, finish_reason="tool_calls")
                                yield StreamChunk(finish_reason="stop")

                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            log_api_error(
                provider="ollama",
                model=model,
                error=str(e),
                request_context={"message_count": len(messages), "base_url": self.base_url}
            )
            raise

    def list_local_models(self) -> List[str]:
        """List locally available Ollama models"""
        try:
            client = self._get_client()
            response = client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
        except Exception:
            pass
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Google Gemini Client
# ═══════════════════════════════════════════════════════════════════════════════

class GeminiClient(BaseAIClient):
    """Google Gemini API client with streaming support"""

    PROVIDER = "google"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self):
        self._client = None
        self._current_api_key = None

    @property
    def api_key(self) -> Optional[str]:
        """Get API key from key manager (supports rotation)"""
        key = api_key_manager.get_key(self.PROVIDER)
        if key:
            return key
        return os.environ.get("GOOGLE_API_KEY")

    def _get_client(self):
        current_key = self.api_key
        if current_key != self._current_api_key:
            self._client = None
            self._current_api_key = current_key
        if self._client is None and current_key:
            self._client = httpx.Client(timeout=120.0)
        return self._client

    def is_available(self) -> bool:
        return api_key_manager.has_available_key(self.PROVIDER) or bool(os.environ.get("GOOGLE_API_KEY"))

    def _convert_messages_to_gemini_format(
        self,
        messages: List[Dict[str, Any]]
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """Convert OpenAI-style messages to Gemini format"""
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_instruction = content
                continue

            # Map roles
            gemini_role = "user" if role == "user" else "model"

            # Handle tool results
            if role == "tool":
                # Tool results go as user messages with function response
                tool_call_id = msg.get("tool_call_id", "")
                contents.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.get("name", tool_call_id),
                            "response": {"result": content}
                        }
                    }]
                })
                continue

            # Handle assistant messages with tool calls
            if role == "assistant" and msg.get("tool_calls"):
                parts = []
                if content:
                    parts.append({"text": content})
                for tc in msg.get("tool_calls", []):
                    func = tc.get("function", {})
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}
                    parts.append({
                        "functionCall": {
                            "name": func.get("name", ""),
                            "args": args
                        }
                    })
                contents.append({"role": "model", "parts": parts})
                continue

            # Regular message
            if content:
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}]
                })

        return system_instruction, contents

    def _convert_tools_to_gemini_format(
        self,
        tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert OpenAI-style tools to Gemini format"""
        gemini_tools = []

        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                gemini_func = {
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                }

                # Convert parameters
                params = func.get("parameters", {})
                if params:
                    gemini_func["parameters"] = {
                        "type": params.get("type", "object"),
                        "properties": params.get("properties", {}),
                        "required": params.get("required", [])
                    }

                gemini_tools.append(gemini_func)

        return [{"functionDeclarations": gemini_tools}] if gemini_tools else []

    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        _retry_count: int = 0
    ) -> Iterator[StreamChunk]:
        client = self._get_client()
        api_key = self.api_key

        if not client or not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set. Use /setapikey google <your-key>")

        # Convert messages
        system_instruction, contents = self._convert_messages_to_gemini_format(messages)

        # Build request payload
        payload = {"contents": contents}

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        # Add tools if provided
        if tools:
            gemini_tools = self._convert_tools_to_gemini_format(tools)
            if gemini_tools:
                payload["tools"] = gemini_tools

        # Generation config
        payload["generationConfig"] = {
            "temperature": 0.7,
            "maxOutputTokens": 8192,
        }

        # Streaming endpoint
        url = f"{self.BASE_URL}/models/{model}:streamGenerateContent?alt=sse&key={api_key}"

        try:
            with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    error_text = response.read().decode()
                    log_api_error(
                        provider="google",
                        model=model,
                        error=error_text,
                        request_context={"status_code": response.status_code}
                    )

                    # Try key rotation
                    if _retry_count < 3 and (is_rate_limit_error(error_text) or is_auth_error(error_text)):
                        rotated, new_key = api_key_manager.report_error(self.PROVIDER, error_text)
                        if rotated and new_key:
                            log_debug("Gemini: Rotated to new API key, retrying...")
                            self._client = None
                            self._current_api_key = None
                            yield from self.stream_chat(messages, model, tools, _retry_count + 1)
                            return

                    raise RuntimeError(f"Gemini API error: {error_text}")

                current_tool_calls = {}

                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    try:
                        data = json.loads(line[6:])  # Remove "data: " prefix

                        candidates = data.get("candidates", [])
                        if not candidates:
                            continue

                        candidate = candidates[0]
                        content = candidate.get("content", {})
                        parts = content.get("parts", [])

                        for part in parts:
                            # Text content
                            if "text" in part:
                                yield StreamChunk(content=part["text"])

                            # Function call
                            if "functionCall" in part:
                                fc = part["functionCall"]
                                idx = len(current_tool_calls)
                                current_tool_calls[idx] = {
                                    "id": f"gemini_call_{idx}",
                                    "name": fc.get("name", ""),
                                    "arguments": json.dumps(fc.get("args", {}))
                                }

                        # Check finish reason
                        finish_reason = candidate.get("finishReason", "")
                        if finish_reason:
                            if current_tool_calls:
                                tool_calls = [
                                    ToolCall(
                                        id=tc["id"],
                                        name=tc["name"],
                                        arguments=tc["arguments"]
                                    )
                                    for tc in current_tool_calls.values()
                                    if tc["name"]
                                ]
                                if tool_calls:
                                    yield StreamChunk(tool_calls=tool_calls, finish_reason="tool_calls")

                            if finish_reason == "STOP":
                                yield StreamChunk(finish_reason="stop")

                    except json.JSONDecodeError:
                        continue

        except httpx.HTTPStatusError as e:
            error_str = str(e)
            log_api_error(
                provider="google",
                model=model,
                error=error_str,
                request_context={"message_count": len(messages)}
            )
            raise
        except Exception as e:
            log_api_error(
                provider="google",
                model=model,
                error=str(e),
                request_context={"message_count": len(messages)}
            )
            raise


# ═══════════════════════════════════════════════════════════════════════════════
# Client Manager
# ═══════════════════════════════════════════════════════════════════════════════

class ClientManager:
    """Manages AI clients based on the selected model"""

    def __init__(self):
        self._clients: Dict[ModelProvider, BaseAIClient] = {
            ModelProvider.GROQ: GroqClient(),
            ModelProvider.OPENROUTER: OpenRouterClient(),
            ModelProvider.ANTHROPIC: AnthropicClient(),
            ModelProvider.OPENAI: OpenAIClient(),
            ModelProvider.OLLAMA: OllamaClient(),
            ModelProvider.GOOGLE: GeminiClient(),
        }

    def get_client(self, model_key: str) -> BaseAIClient:
        """Get the appropriate client for the given model"""
        if model_key not in AVAILABLE_MODELS:
            raise ValueError(f"Unknown model: {model_key}")

        config = AVAILABLE_MODELS[model_key]
        client = self._clients[config.provider]

        if not client.is_available():
            provider_name = config.provider.value.lower()
            raise RuntimeError(
                f"{provider_name.upper()}_API_KEY not set. Use /setapikey {provider_name} <your-key>"
            )

        return client

    def get_model_id(self, model_key: str) -> str:
        """Get the model ID for the given model key"""
        if model_key not in AVAILABLE_MODELS:
            raise ValueError(f"Unknown model: {model_key}")
        return AVAILABLE_MODELS[model_key].id

    def generate_title(self, first_message: str) -> str:
        """Generate a title for a conversation using the utility model"""
        try:
            groq_client = self._clients[ModelProvider.GROQ]
            if not groq_client.is_available():
                return "Untitled Conversation"

            client = groq_client._get_client()
            prompt = TITLE_GENERATION_PROMPT.format(message=first_message[:500])

            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=UTILITY_MODEL,
                max_tokens=50,
                temperature=0.7
            )

            title = response.choices[0].message.content.strip()
            # Clean up the title
            title = title.strip('"\'').strip()
            # Limit length
            if len(title) > 50:
                title = title[:47] + "..."

            return title if title else "Untitled Conversation"

        except Exception as e:
            from .logger import log_error
            log_error("Failed to generate title", e, {"message": first_message[:100]})
            return "Untitled Conversation"

    def get_available_providers(self) -> Dict[ModelProvider, bool]:
        """Get a dict of providers and their availability status"""
        return {
            provider: client.is_available()
            for provider, client in self._clients.items()
        }

    def get_ollama_models(self) -> List[str]:
        """Get list of locally available Ollama models"""
        ollama_client = self._clients.get(ModelProvider.OLLAMA)
        if ollama_client and isinstance(ollama_client, OllamaClient):
            return ollama_client.list_local_models()
        return []

    def add_custom_ollama_model(self, model_id: str, name: str = None) -> str:
        """Add a custom Ollama model to available models"""
        key = f"ollama-{model_id.replace(':', '-').replace('/', '-')}"
        if key not in AVAILABLE_MODELS:
            AVAILABLE_MODELS[key] = ModelConfig(
                id=model_id,
                name=name or f"{model_id} (Ollama)",
                provider=ModelProvider.OLLAMA,
                description=f"Custom Ollama model: {model_id}",
                supports_tools=False
            )
        return key
