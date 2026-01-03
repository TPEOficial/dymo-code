"""
Prompt Suggestions System for Dymo Code
Generates contextual prompt suggestions based on conversation history
"""

import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class PromptSuggestion:
    """Represents a suggested prompt"""
    text: str
    category: str  # "continue", "clarify", "action", "explore"
    confidence: float  # 0.0 to 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# Context Patterns and Suggestions
# ═══════════════════════════════════════════════════════════════════════════════

# Patterns that suggest follow-up actions
CONTEXT_PATTERNS = {
    # After file creation/modification
    r"(created|wrote|updated|modified)\s+(file|archivo)": [
        "Run the tests to verify",
        "Show me the file content",
        "Add error handling",
        "Create tests for this",
    ],
    # After error or failure
    r"(error|failed|exception|traceback|falló)": [
        "Fix the error",
        "Show me more details",
        "Try a different approach",
        "Search for solutions online",
    ],
    # After listing files
    r"(found|listed|files|archivos)\s*:?\s*\n": [
        "Read the main file",
        "Show the project structure",
        "Search for a specific pattern",
    ],
    # After code explanation
    r"(this|the)\s+(code|function|class)\s+(does|is|handles)": [
        "Can you improve it?",
        "Add documentation",
        "Show me an example usage",
        "What are the edge cases?",
    ],
    # After successful operation
    r"(successfully|done|completed|completado|listo)": [
        "What's next?",
        "Run the application",
        "Commit the changes",
        "Show me a summary",
    ],
    # After search/grep results
    r"(matches|results|encontr)": [
        "Show the first result",
        "Filter by type",
        "Replace all occurrences",
    ],
    # After installation
    r"(installed|npm|pip|cargo)\s+(install|add)": [
        "Show the dependencies",
        "Run the build",
        "Test the installation",
    ],
    # Questions from AI
    r"\?\s*$": [
        "Yes",
        "No",
        "Show me more options",
        "Let me think about it",
    ],
    # After showing code
    r"```[\w]*\n[\s\S]*```": [
        "Run this code",
        "Explain this code",
        "Modify this to...",
        "Save this to a file",
    ],
    # After git operations
    r"(commit|push|pull|merge|branch)": [
        "Show git status",
        "Create a new branch",
        "Push the changes",
        "Show the diff",
    ],
    # Empty or new conversation
    r"^$": [
        "What files are in this project?",
        "Explain this codebase",
        "Help me with...",
        "Search for...",
    ],
}

# Action-based suggestions (when last message was an action)
ACTION_FOLLOWUPS = {
    "create_file": ["Run the code", "Add tests", "Show the file"],
    "read_file": ["Modify this file", "Find similar patterns", "Explain this code"],
    "run_command": ["Check the output", "Fix any errors", "Run again"],
    "delete_path": ["Verify deletion", "Restore if needed", "Continue with next step"],
    "grep_search": ["Show full context", "Replace matches", "Narrow the search"],
    "glob_search": ["Read the files", "Filter results", "Search contents"],
    "web_search": ["Get more details", "Visit the first result", "Search for alternatives"],
}

# Generic suggestions for different conversation states
GENERIC_SUGGESTIONS = {
    "start": [
        "Show me the project structure",
        "What can you help me with?",
        "Read the README",
        "List the main files",
    ],
    "mid_conversation": [
        "Continue",
        "Show me more",
        "What else?",
        "Summarize so far",
    ],
    "after_error": [
        "Try again",
        "Show the full error",
        "Search for a fix",
        "Use a different approach",
    ],
    "after_success": [
        "Great, what's next?",
        "Run the tests",
        "Commit changes",
        "Show summary",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
# Suggestion Generator
# ═══════════════════════════════════════════════════════════════════════════════

class PromptSuggestionGenerator:
    """Generates contextual prompt suggestions based on conversation history"""

    def __init__(self):
        self._enabled = True
        self._last_suggestions: List[PromptSuggestion] = []
        self._suggestion_index = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    def toggle(self) -> bool:
        """Toggle suggestions on/off. Returns new state."""
        self._enabled = not self._enabled
        return self._enabled

    def get_suggestion(self, messages: List[Dict[str, Any]], last_tool: Optional[str] = None) -> Optional[str]:
        """
        Get the best prompt suggestion based on conversation context.

        Args:
            messages: List of conversation messages
            last_tool: Name of the last tool that was executed (if any)

        Returns:
            Suggested prompt string or None
        """
        if not self._enabled:
            return None

        suggestions = self._generate_suggestions(messages, last_tool)
        self._last_suggestions = suggestions
        self._suggestion_index = 0

        if suggestions:
            return suggestions[0].text
        return None

    def get_next_suggestion(self) -> Optional[str]:
        """Get the next suggestion in the rotation"""
        if not self._last_suggestions:
            return None

        self._suggestion_index = (self._suggestion_index + 1) % len(self._last_suggestions)
        return self._last_suggestions[self._suggestion_index].text

    def get_all_suggestions(self) -> List[str]:
        """Get all current suggestions"""
        return [s.text for s in self._last_suggestions]

    def _generate_suggestions(
        self,
        messages: List[Dict[str, Any]],
        last_tool: Optional[str] = None
    ) -> List[PromptSuggestion]:
        """Generate a list of suggestions based on context"""
        suggestions = []

        # Get the last assistant message
        last_assistant_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                last_assistant_msg = msg.get("content", "")
                break

        # No messages yet - show start suggestions
        if not last_assistant_msg or len(messages) <= 1:
            for text in GENERIC_SUGGESTIONS["start"]:
                suggestions.append(PromptSuggestion(
                    text=text,
                    category="start",
                    confidence=0.7
                ))
            return suggestions[:4]

        # Check for tool-based suggestions first (highest priority)
        if last_tool and last_tool in ACTION_FOLLOWUPS:
            for text in ACTION_FOLLOWUPS[last_tool]:
                suggestions.append(PromptSuggestion(
                    text=text,
                    category="action",
                    confidence=0.9
                ))

        # Check context patterns
        for pattern, pattern_suggestions in CONTEXT_PATTERNS.items():
            if re.search(pattern, last_assistant_msg, re.IGNORECASE | re.MULTILINE):
                for text in pattern_suggestions:
                    # Avoid duplicates
                    if not any(s.text == text for s in suggestions):
                        suggestions.append(PromptSuggestion(
                            text=text,
                            category="context",
                            confidence=0.8
                        ))

        # If still no suggestions, use generic mid-conversation ones
        if not suggestions:
            # Detect conversation state
            if any(word in last_assistant_msg.lower() for word in ["error", "failed", "exception"]):
                state = "after_error"
            elif any(word in last_assistant_msg.lower() for word in ["success", "done", "created", "completed"]):
                state = "after_success"
            else:
                state = "mid_conversation"

            for text in GENERIC_SUGGESTIONS[state]:
                suggestions.append(PromptSuggestion(
                    text=text,
                    category="generic",
                    confidence=0.5
                ))

        # Sort by confidence and limit
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        return suggestions[:6]

    def add_custom_pattern(self, pattern: str, suggestions: List[str]):
        """Add a custom context pattern with suggestions"""
        CONTEXT_PATTERNS[pattern] = suggestions


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton Instance
# ═══════════════════════════════════════════════════════════════════════════════

prompt_suggester = PromptSuggestionGenerator()


# ═══════════════════════════════════════════════════════════════════════════════
# Settings Management
# ═══════════════════════════════════════════════════════════════════════════════

def load_suggestion_settings():
    """Load suggestion settings from user config"""
    try:
        from .storage import user_config
        enabled = user_config.get("prompt_suggestions_enabled", True)
        prompt_suggester.enabled = enabled
    except Exception:
        pass  # Use default (enabled)


def save_suggestion_settings():
    """Save suggestion settings to user config"""
    try:
        from .storage import user_config
        user_config.set("prompt_suggestions_enabled", prompt_suggester.enabled)
    except Exception:
        pass


# Load settings on import
load_suggestion_settings()
