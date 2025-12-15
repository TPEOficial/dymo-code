"""
Context Manager for Dymo Code
Handles conversation context to prevent exceeding token limits.
Uses a hybrid approach: System Prompt + Summary + Recent Messages
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .config import AVAILABLE_MODELS, UTILITY_MODEL, ModelProvider
from .logger import log_debug, log_error


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

# Approximate characters per token (conservative estimate)
CHARS_PER_TOKEN = 4

# How much of the context window to use before triggering compression (80%)
CONTEXT_USAGE_THRESHOLD = 0.80

# Minimum number of recent messages to always keep
MIN_RECENT_MESSAGES = 10

# Maximum number of recent messages to keep
MAX_RECENT_MESSAGES = 20


# ═══════════════════════════════════════════════════════════════════════════════
# Token Estimation
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a text.
    Uses a simple heuristic: ~4 characters per token.
    This is conservative to avoid hitting limits.
    """
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN + 1


def estimate_message_tokens(message: Dict[str, Any]) -> int:
    """Estimate tokens for a single message"""
    tokens = 0

    # Role overhead (~4 tokens)
    tokens += 4

    # Content
    content = message.get("content", "")
    if content:
        tokens += estimate_tokens(content)

    # Tool calls
    if "tool_calls" in message:
        for tc in message["tool_calls"]:
            tokens += 10  # Overhead for tool call structure
            if "function" in tc:
                tokens += estimate_tokens(tc["function"].get("name", ""))
                tokens += estimate_tokens(tc["function"].get("arguments", ""))

    return tokens


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    """Estimate total tokens for a list of messages"""
    return sum(estimate_message_tokens(msg) for msg in messages)


# ═══════════════════════════════════════════════════════════════════════════════
# Summarization
# ═══════════════════════════════════════════════════════════════════════════════

SUMMARY_PROMPT = """Summarize the following conversation concisely. Focus on:
1. Key topics discussed
2. Important decisions or conclusions
3. Any tasks completed or pending
4. User preferences or requirements mentioned

Keep the summary under 500 words. Write in a way that preserves context for continuing the conversation.

Conversation:
{conversation}

Summary:"""


def format_messages_for_summary(messages: List[Dict[str, Any]]) -> str:
    """Format messages into readable text for summarization"""
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")

        # Skip system messages and empty content
        if role == "SYSTEM" or not content:
            continue

        # Truncate very long messages
        if len(content) > 1000:
            content = content[:1000] + "..."

        # Handle tool messages
        if role == "TOOL":
            tool_id = msg.get("tool_call_id", "unknown")
            lines.append(f"[Tool Result ({tool_id})]: {content[:200]}...")
        else:
            lines.append(f"{role}: {content}")

    return "\n\n".join(lines)


def generate_summary(messages: List[Dict[str, Any]], client_manager) -> Optional[str]:
    """
    Generate a summary of the conversation using the utility model.
    Returns None if summarization fails.
    """
    try:
        # Check if Groq is available (for utility model)
        groq_client = client_manager._clients.get(ModelProvider.GROQ)
        if not groq_client or not groq_client.is_available():
            log_debug("Groq not available for summarization, skipping")
            return None

        client = groq_client._get_client()
        if not client:
            return None

        # Format conversation for summary
        conversation_text = format_messages_for_summary(messages)

        if not conversation_text:
            return None

        prompt = SUMMARY_PROMPT.format(conversation=conversation_text)

        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=UTILITY_MODEL,
            max_tokens=800,
            temperature=0.3
        )

        summary = response.choices[0].message.content.strip()
        log_debug(f"Generated summary: {len(summary)} chars")
        return summary

    except Exception as e:
        log_error("Failed to generate summary", e)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Context Manager
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ContextState:
    """Represents the current state of context management"""
    total_tokens: int
    max_tokens: int
    usage_percent: float
    needs_compression: bool
    message_count: int
    summary_active: bool


class ContextManager:
    """
    Manages conversation context to prevent exceeding token limits.

    Strategy:
    1. Monitor token usage
    2. When approaching limit, summarize older messages
    3. Keep: [System Prompt] + [Summary] + [Recent Messages]
    """

    def __init__(self):
        self._summary: Optional[str] = None
        self._summarized_count: int = 0  # Number of messages that were summarized

    def get_context_window(self, model_key: str) -> int:
        """Get the context window size for the current model"""
        if model_key in AVAILABLE_MODELS:
            return AVAILABLE_MODELS[model_key].context_window
        return 128000  # Default fallback

    def get_state(self, messages: List[Dict[str, Any]], model_key: str) -> ContextState:
        """Get the current context state"""
        total_tokens = estimate_messages_tokens(messages)
        max_tokens = self.get_context_window(model_key)
        usage_percent = total_tokens / max_tokens if max_tokens > 0 else 0

        return ContextState(
            total_tokens=total_tokens,
            max_tokens=max_tokens,
            usage_percent=usage_percent,
            needs_compression=usage_percent >= CONTEXT_USAGE_THRESHOLD,
            message_count=len(messages),
            summary_active=self._summary is not None
        )

    def compress_context(
        self,
        messages: List[Dict[str, Any]],
        model_key: str,
        client_manager
    ) -> List[Dict[str, Any]]:
        """
        Compress the conversation context if needed.

        Returns the compressed messages list.
        """
        state = self.get_state(messages, model_key)

        if not state.needs_compression:
            return messages

        log_debug(f"Context compression triggered: {state.usage_percent:.1%} used")

        # Separate system prompt from conversation
        system_msg = None
        conversation_msgs = []

        for msg in messages:
            if msg.get("role") == "system":
                system_msg = msg
            else:
                conversation_msgs.append(msg)

        # If we don't have enough messages to compress, just return
        if len(conversation_msgs) <= MIN_RECENT_MESSAGES:
            log_debug("Not enough messages to compress")
            return messages

        # Split into messages to summarize and messages to keep
        keep_count = min(MAX_RECENT_MESSAGES, len(conversation_msgs) // 2)
        keep_count = max(keep_count, MIN_RECENT_MESSAGES)

        messages_to_summarize = conversation_msgs[:-keep_count]
        messages_to_keep = conversation_msgs[-keep_count:]

        # Generate summary of older messages
        summary = generate_summary(messages_to_summarize, client_manager)

        if summary:
            self._summary = summary
            self._summarized_count = len(messages_to_summarize)

            # Build new messages list
            new_messages = []

            # Add system prompt
            if system_msg:
                new_messages.append(system_msg)

            # Add summary as a system-like context message
            summary_msg = {
                "role": "user",
                "content": f"[Previous conversation summary - {self._summarized_count} messages]\n\n{summary}\n\n[End of summary - Recent messages follow]"
            }
            new_messages.append(summary_msg)

            # Add assistant acknowledgment to maintain conversation flow
            new_messages.append({
                "role": "assistant",
                "content": "I understand. I have the context from our previous conversation. Let's continue."
            })

            # Add recent messages
            new_messages.extend(messages_to_keep)

            new_state = self.get_state(new_messages, model_key)
            log_debug(
                f"Context compressed: {state.total_tokens} -> {new_state.total_tokens} tokens, "
                f"{state.message_count} -> {new_state.message_count} messages"
            )

            return new_messages
        else:
            # Fallback: just truncate to recent messages (no summary)
            log_debug("Summarization failed, falling back to truncation")
            new_messages = []
            if system_msg:
                new_messages.append(system_msg)
            new_messages.extend(messages_to_keep)
            return new_messages

    def should_compress(self, messages: List[Dict[str, Any]], model_key: str) -> bool:
        """Check if context compression is needed"""
        state = self.get_state(messages, model_key)
        return state.needs_compression

    def reset(self):
        """Reset the context manager state"""
        self._summary = None
        self._summarized_count = 0

    @property
    def has_summary(self) -> bool:
        """Check if there's an active summary"""
        return self._summary is not None

    @property
    def summary(self) -> Optional[str]:
        """Get the current summary"""
        return self._summary


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

context_manager = ContextManager()
