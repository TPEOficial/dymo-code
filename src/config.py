"""
Configuration and constants for Dymo Code
Multi-provider AI terminal assistant with support for:
- Groq, OpenRouter, Claude (Anthropic), OpenAI, Ollama, Google Gemini, Cerebras
"""

import os
import platform
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List

# ═══════════════════════════════════════════════════════════════════════════════
# Model Provider Configuration
# ═══════════════════════════════════════════════════════════════════════════════

class ModelProvider(Enum):
    GROQ = "groq"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    GOOGLE = "google"
    CEREBRAS = "cerebras"

@dataclass
class ModelConfig:
    id: str
    name: str
    provider: ModelProvider
    description: str
    supports_code_execution: bool = False
    supports_web_search: bool = False
    supports_tools: bool = True
    context_window: int = 128000
    max_output_tokens: Optional[int] = None

# ═══════════════════════════════════════════════════════════════════════════════
# Provider-specific Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ProviderConfig:
    """Configuration for an API provider"""
    name: str
    env_key: str
    base_url: Optional[str] = None
    requires_api_key: bool = True
    description: str = ""

PROVIDER_CONFIGS: Dict[ModelProvider, ProviderConfig] = {
    ModelProvider.GROQ: ProviderConfig(
        name="Groq",
        env_key="GROQ_API_KEY",
        description="Ultra-fast inference for open models"
    ),
    ModelProvider.OPENROUTER: ProviderConfig(
        name="OpenRouter",
        env_key="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        description="Access to 100+ models via single API"
    ),
    ModelProvider.ANTHROPIC: ProviderConfig(
        name="Anthropic",
        env_key="ANTHROPIC_API_KEY",
        description="Claude models - powerful reasoning & coding"
    ),
    ModelProvider.OPENAI: ProviderConfig(
        name="OpenAI",
        env_key="OPENAI_API_KEY",
        description="GPT-4o and o1 models"
    ),
    ModelProvider.OLLAMA: ProviderConfig(
        name="Ollama",
        env_key="OLLAMA_BASE_URL",
        base_url="http://localhost:11434",
        requires_api_key=False,
        description="Local LLM inference"
    ),
    ModelProvider.GOOGLE: ProviderConfig(
        name="Google",
        env_key="GOOGLE_API_KEY",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        description="Google's Gemini models - multimodal AI"
    ),
    ModelProvider.CEREBRAS: ProviderConfig(
        name="Cerebras",
        env_key="CEREBRAS_API_KEY",
        description="Ultra-fast inference - world's fastest AI chip"
    ),
}

# ═══════════════════════════════════════════════════════════════════════════════
# Available Models
# ═══════════════════════════════════════════════════════════════════════════════

AVAILABLE_MODELS: Dict[str, ModelConfig] = {
    # Groq Models
    "llama": ModelConfig(
        id="llama-3.3-70b-versatile",
        name="Llama 3.3 70B",
        provider=ModelProvider.GROQ,
        description="Fast and capable open-source model via Groq"
    ),
    "gpt-oss": ModelConfig(
        id="openai/gpt-oss-120b",
        name="GPT-OSS 120B",
        provider=ModelProvider.GROQ,
        description="Large GPT model with code execution & web search",
        supports_code_execution=True,
        supports_web_search=True
    ),
    "compound": ModelConfig(
        id="compound",
        name="Groq Compound",
        provider=ModelProvider.GROQ,
        description="Multi-tool agent with code exec, web search, browser",
        supports_code_execution=True,
        supports_web_search=True
    ),
    "compound-mini": ModelConfig(
        id="compound-mini",
        name="Groq Compound Mini",
        provider=ModelProvider.GROQ,
        description="Fast single-tool agent with code execution",
        supports_code_execution=True,
        supports_web_search=True
    ),

    # Anthropic Claude Models
    "claude-opus": ModelConfig(
        id="claude-opus-4-20250514",
        name="Claude Opus 4",
        provider=ModelProvider.ANTHROPIC,
        description="Most capable Claude model for complex tasks",
        supports_tools=True,
        context_window=200000,
        max_output_tokens=32000
    ),
    "claude-sonnet": ModelConfig(
        id="claude-sonnet-4-20250514",
        name="Claude Sonnet 4",
        provider=ModelProvider.ANTHROPIC,
        description="Balanced performance and speed",
        supports_tools=True,
        context_window=200000,
        max_output_tokens=16000
    ),
    "claude-haiku": ModelConfig(
        id="claude-3-5-haiku-20241022",
        name="Claude 3.5 Haiku",
        provider=ModelProvider.ANTHROPIC,
        description="Fast and affordable for simple tasks",
        supports_tools=True,
        context_window=200000,
        max_output_tokens=8192
    ),

    # OpenAI Models
    "gpt-4o": ModelConfig(
        id="gpt-4o",
        name="GPT-4o",
        provider=ModelProvider.OPENAI,
        description="Most capable GPT-4 model",
        supports_tools=True,
        context_window=128000,
        max_output_tokens=16384
    ),
    "gpt-4o-mini": ModelConfig(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        provider=ModelProvider.OPENAI,
        description="Fast and affordable GPT-4o variant",
        supports_tools=True,
        context_window=128000,
        max_output_tokens=16384
    ),
    "o1": ModelConfig(
        id="o1",
        name="OpenAI o1",
        provider=ModelProvider.OPENAI,
        description="Advanced reasoning model",
        supports_tools=False,
        context_window=200000,
        max_output_tokens=100000
    ),
    "o1-mini": ModelConfig(
        id="o1-mini",
        name="OpenAI o1-mini",
        provider=ModelProvider.OPENAI,
        description="Faster reasoning model",
        supports_tools=False,
        context_window=128000,
        max_output_tokens=65536
    ),

    # Ollama Local Models (common defaults)
    "ollama-llama3": ModelConfig(
        id="llama3.2",
        name="Llama 3.2 (Ollama)",
        provider=ModelProvider.OLLAMA,
        description="Local Llama 3.2 via Ollama",
        supports_tools=True,
        context_window=128000
    ),
    "ollama-codellama": ModelConfig(
        id="codellama",
        name="CodeLlama (Ollama)",
        provider=ModelProvider.OLLAMA,
        description="Specialized for code generation",
        supports_tools=False,
        context_window=16000
    ),
    "ollama-mistral": ModelConfig(
        id="mistral",
        name="Mistral (Ollama)",
        provider=ModelProvider.OLLAMA,
        description="Fast local inference",
        supports_tools=True,
        context_window=32000
    ),
    "ollama-qwen": ModelConfig(
        id="qwen2.5-coder",
        name="Qwen 2.5 Coder (Ollama)",
        provider=ModelProvider.OLLAMA,
        description="Excellent for coding tasks",
        supports_tools=True,
        context_window=128000
    ),

    # Google Gemini Models
    "gemini-flash": ModelConfig(
        id="gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        provider=ModelProvider.GOOGLE,
        description="Fast and efficient Gemini model",
        supports_tools=True,
        context_window=1000000,
        max_output_tokens=8192
    ),
    "gemini-pro": ModelConfig(
        id="gemini-1.5-pro",
        name="Gemini 1.5 Pro",
        provider=ModelProvider.GOOGLE,
        description="Advanced reasoning and long context",
        supports_tools=True,
        context_window=2000000,
        max_output_tokens=8192
    ),
    "gemini-flash-lite": ModelConfig(
        id="gemini-2.0-flash-lite",
        name="Gemini 2.0 Flash Lite",
        provider=ModelProvider.GOOGLE,
        description="Lightweight and fast for simple tasks",
        supports_tools=True,
        context_window=1000000,
        max_output_tokens=8192
    ),

    # Cerebras Models (Ultra-fast inference)
    "cerebras-llama": ModelConfig(
        id="llama-3.3-70b",
        name="Llama 3.3 70B (Cerebras)",
        provider=ModelProvider.CEREBRAS,
        description="Ultra-fast Llama 3.3 70B inference",
        supports_tools=True,
        context_window=128000,
        max_output_tokens=8192
    ),
    "cerebras-llama-scout": ModelConfig(
        id="llama-4-scout-17b-16e-instruct",
        name="Llama 4 Scout 17B (Cerebras)",
        provider=ModelProvider.CEREBRAS,
        description="Llama 4 Scout - efficient and fast",
        supports_tools=True,
        context_window=128000,
        max_output_tokens=8192
    ),
}

DEFAULT_MODEL = "gpt-oss"

# Small model for utility tasks (title generation, etc.)
UTILITY_MODEL = "llama-3.1-8b-instant"

# Title generation prompt
TITLE_GENERATION_PROMPT = """Generate a very short title (3-6 words max) for this conversation based on the user's first message.
Reply with ONLY the title, no quotes, no explanation, no punctuation at the end.

User's message: {message}

Title:"""

# ═══════════════════════════════════════════════════════════════════════════════
# Color Scheme (Dynamic Theme Support)
# ═══════════════════════════════════════════════════════════════════════════════

# Default colors (used if theme system not yet loaded)
_DEFAULT_COLORS = {
    "primary": "#7C3AED",      # Purple
    "secondary": "#06B6D4",    # Cyan
    "success": "#10B981",      # Green
    "warning": "#F59E0B",      # Amber
    "error": "#EF4444",        # Red
    "muted": "#6B7280",        # Gray
    "accent": "#EC4899",       # Pink
}

def get_colors():
    """Get current theme colors (dynamic)"""
    try:
        from .themes import theme_manager
        return theme_manager.colors
    except ImportError:
        return _DEFAULT_COLORS

# For backward compatibility - this is a proxy that gets current theme colors
class ColorsProxy(dict):
    """Proxy dict that always returns current theme colors"""
    def __getitem__(self, key):
        return get_colors().get(key, "#FFFFFF")

    def get(self, key, default=None):
        return get_colors().get(key, default)

    def __iter__(self):
        return iter(get_colors())

    def keys(self):
        return get_colors().keys()

    def values(self):
        return get_colors().values()

    def items(self):
        return get_colors().items()

COLORS = ColorsProxy()

# ═══════════════════════════════════════════════════════════════════════════════
# System Prompt
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are an expert AI coding assistant with direct access to the user's system through tools. Your primary mode of operation is ACTION, not description.

## CORE PRINCIPLES

### 1. ACT, DON'T JUST DESCRIBE
- When asked to do something → USE TOOLS to do it
- Don't explain what you "would do" → DO IT
- Don't show code in chat → CREATE files with tools
- The user can see results through tool outputs

### 2. SOLVE PROBLEMS COMPLETELY
When given a task:
1. **Understand** - Read relevant files if needed
2. **Plan** - Break down into steps (use spawn_agents for complex tasks)
3. **Execute** - Use tools to implement the solution
4. **Verify** - Run/test to confirm it works
5. **Iterate** - If something fails, FIX IT and try again

**NEVER give up after one failure.** Debug, fix, and retry.

### 3. VERIFY YOUR WORK
After making changes:
- Run the code to check for errors
- Read the file to confirm changes were applied
- Test the functionality if possible
- If something breaks, investigate and fix it

### 4. ITERATE UNTIL SUCCESS
- Error in code? → Read the error, fix it, run again
- File not created? → Check the path, try again
- Test failed? → Debug, modify, retest
- Keep iterating until the task is COMPLETE

## TOOLS AVAILABLE

| Tool | Purpose |
|------|---------|
| `list_files_in_dir` | Explore directory structure |
| `read_file` | Read file contents |
| `create_folder` | Create directories |
| `create_file` | Create or modify files |
| `move_path` | Rename or move files |
| `delete_path` | Remove files (with confirmation) |
| `run_command` | Execute shell commands (output streams in real-time) |
| `spawn_agents` | Divide complex tasks (max 5 subtasks) |
| `glob_search` | Find files by pattern |
| `grep_search` | Search file contents |
| `web_search` | Search the internet |
| `fetch_url` | Get web page content |

## TASK DIVISION (spawn_agents)

For complex tasks with 3+ steps:
- Use `spawn_agents` to parallelize work
- Maximum 5 tasks per call (batch if needed)
- Group related items (e.g., "Create all sorting algorithms")
- Use `sequential: true` for dependent tasks

**Example - "Create an algorithm repository":**
- Task 1: "Create sorting algorithm files (bubble, merge, quick, heap)"
- Task 2: "Create search algorithm files (binary, linear, jump)"
- Task 3: "Create graph algorithm files (dijkstra, BFS, DFS)"

## RESPONSE STYLE

- **Brief after actions**: "Created `file.py`" - done
- **Don't repeat file contents** unless asked
- **Don't over-explain** - the user sees tool results
- **Be direct**: Do what's asked, no more, no less

## ERROR HANDLING

When something fails:
1. Read the error message carefully
2. Identify the root cause
3. Fix the issue
4. Run again to verify
5. Repeat until resolved

**Example workflow:**
```
User: "Create a Python script that fetches weather data and run it"

Your approach:
1. create_file → weather.py with API code
2. run_command → python weather.py
3. If error → read error, fix code, run again
4. If missing module → run_command pip install X, then retry
5. Continue until it works or you've exhausted options
```

## ENVIRONMENT
- OS: {os_info}
- Working Directory: {cwd}
"""

def get_system_prompt() -> str:
    """Generate system prompt with current environment info"""
    return SYSTEM_PROMPT.format(
        os_info=f"{platform.system()} {platform.release()}",
        cwd=os.getcwd()
    )
