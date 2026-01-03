"""
Prompt Enhancement System for Dymo Code
Improves user prompts before sending to the main AI for better understanding.
"""

import json
from typing import Optional, Tuple
from dataclasses import dataclass

from .storage import user_config
from .logger import log_debug, log_error


# Enhancement prompt template
ENHANCEMENT_PROMPT = """You are a prompt optimizer. Your task is to improve the user's prompt for an AI coding assistant.

RULES:
1. Keep the original intent intact
2. Add clarity where the prompt is ambiguous
3. Structure multi-part tasks clearly
4. Specify implicit requirements explicitly
5. Keep it concise - don't add unnecessary verbosity
6. If the prompt is already clear, return it as-is
7. DO NOT add information the user didn't request
8. DO NOT change the scope of the task

USER PROMPT:
{user_prompt}

CONTEXT (if any):
{context}

Return ONLY the improved prompt, nothing else. If no improvement needed, return the original."""


@dataclass
class EnhancementResult:
    """Result of prompt enhancement"""
    original: str
    enhanced: str
    was_enhanced: bool


class PromptEnhancer:
    """
    Enhances user prompts using a lightweight AI model.
    This helps the main AI understand complex or ambiguous requests better.
    """

    def __init__(self):
        self._enabled: Optional[bool] = None

    @property
    def enabled(self) -> bool:
        """Check if prompt enhancement is enabled"""
        if self._enabled is None:
            self._enabled = user_config.get("prompt_enhancement", True)
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """Set prompt enhancement enabled state"""
        self._enabled = value
        user_config.set("prompt_enhancement", value)

    def toggle(self) -> bool:
        """Toggle prompt enhancement on/off"""
        self.enabled = not self.enabled
        return self.enabled

    def should_enhance(self, prompt: str) -> bool:
        """
        Determine if a prompt should be enhanced.
        Skip enhancement for simple/short prompts or commands.
        """
        if not self.enabled:
            return False

        # Skip commands
        if prompt.startswith("/"):
            return False

        # Skip very short prompts (likely simple questions)
        if len(prompt) < 30:
            return False

        # Skip if prompt is already very structured (has bullet points, numbers)
        if any(prompt.strip().startswith(x) for x in ["1.", "2.", "-", "*", "•"]):
            return False

        # Enhance complex prompts
        indicators = [
            "revisa", "arregla", "agrega", "implementa", "crea",
            "check", "fix", "add", "implement", "create",
            "faltan", "missing", "compare", "sync",
            "no funciona", "doesn't work", "error",
        ]

        prompt_lower = prompt.lower()
        return any(ind in prompt_lower for ind in indicators)

    def enhance(self, prompt: str, context: str = "") -> EnhancementResult:
        """
        Enhance a user prompt using AI.

        Args:
            prompt: The original user prompt
            context: Optional context (e.g., referenced files, previous messages)

        Returns:
            EnhancementResult with original and enhanced prompts
        """
        if not self.should_enhance(prompt):
            return EnhancementResult(
                original=prompt,
                enhanced=prompt,
                was_enhanced=False
            )

        try:
            enhanced = self._call_enhancer(prompt, context)

            # Validate enhancement
            if enhanced and enhanced.strip() and enhanced != prompt:
                log_debug(f"Prompt enhanced: {len(prompt)} -> {len(enhanced)} chars")
                return EnhancementResult(
                    original=prompt,
                    enhanced=enhanced,
                    was_enhanced=True
                )
        except Exception as e:
            log_error("Prompt enhancement failed", e)

        # Return original if enhancement failed
        return EnhancementResult(
            original=prompt,
            enhanced=prompt,
            was_enhanced=False
        )

    def _call_enhancer(self, prompt: str, context: str) -> Optional[str]:
        """Call the AI to enhance the prompt"""
        from .clients import ClientManager

        try:
            client_manager = ClientManager()

            # Use a fast, cheap model for enhancement
            # Try Groq first (fast), then fallback to others
            enhancement_models = ["groq-llama-scout", "groq-llama-instant", "gpt-oss"]

            for model_key in enhancement_models:
                try:
                    client = client_manager.get_client(model_key)
                    model_id = client_manager.get_model_id(model_key)

                    # Build the enhancement request
                    messages = [
                        {
                            "role": "system",
                            "content": "You are a prompt optimizer. Improve prompts for clarity without changing their intent. Be concise."
                        },
                        {
                            "role": "user",
                            "content": ENHANCEMENT_PROMPT.format(
                                user_prompt=prompt,
                                context=context[:500] if context else "None"
                            )
                        }
                    ]

                    # Get response (non-streaming for speed)
                    response = ""
                    for chunk in client.stream_chat(messages=messages, model=model_id, tools=None):
                        if chunk.content:
                            response += chunk.content

                    return response.strip()

                except Exception as e:
                    log_debug(f"Enhancement model {model_key} failed: {e}")
                    continue

            return None

        except Exception as e:
            log_error("Enhancement client error", e)
            return None


# Global instance
prompt_enhancer = PromptEnhancer()


def enhance_prompt(prompt: str, context: str = "") -> Tuple[str, bool]:
    """
    Convenience function to enhance a prompt.

    Returns:
        Tuple of (enhanced_prompt, was_enhanced)
    """
    result = prompt_enhancer.enhance(prompt, context)
    return result.enhanced, result.was_enhanced
