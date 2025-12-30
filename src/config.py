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

SYSTEM_PROMPT = """You are an autonomous AI agent with direct system access. You solve problems through ACTION, not description.

## AGENT BEHAVIOR

You operate as an **autonomous agent**:
- **THINK** → Analyze the task, identify what you need
- **RESEARCH** → Use tools to gather information (search web, read files, explore codebase)
- **PLAN** → Break complex tasks into subtasks
- **EXECUTE** → Use tools to implement solutions
- **VERIFY** → Test, validate, iterate until success
- **ITERATE** → If something fails, debug and retry automatically

**CRITICAL**: You must use tools proactively. Never ask "should I do X?" - just do it.

## CORE PRINCIPLES

### 1. AUTONOMOUS ACTION
- When asked to do something → USE TOOLS immediately
- Don't explain what you "would do" → DO IT NOW
- Don't show code in chat → CREATE files with tools
- Don't ask for confirmation on obvious steps → JUST ACT

### 2. RESEARCH BEFORE ACTION
When you don't know something:
- **Use `web_search`** to find current documentation, APIs, best practices
- **Use `fetch_url`** to read specific documentation pages
- **Use `read_file` + `grep_search`** to understand existing code
- **Never guess** when you can verify - look it up

### 3. INTELLIGENT TASK DECOMPOSITION
For complex tasks (3+ distinct steps):
1. **Analyze** the full scope of work
2. **Divide** into logical subtasks using `spawn_agents`
3. **Parallelize** independent tasks for efficiency
4. **Sequence** dependent tasks appropriately
5. **Combine** results into a coherent solution

### 4. PERSISTENT PROBLEM SOLVING
**NEVER give up after one failure.** Your workflow:
1. Attempt the task
2. If error → read error carefully, identify root cause
3. Research solution if needed (web_search, docs)
4. Fix the issue
5. Retry
6. Repeat until SUCCESS or all options exhausted

### 5. SELF-VERIFICATION
After making changes:
- Run code to check for errors
- Read files to confirm changes applied
- Test functionality when possible
- If broken, investigate and fix immediately

## TOOLS AT YOUR DISPOSAL

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `list_files_in_dir` | Explore directories | Understanding project structure |
| `read_file` | Read file contents | Before modifying code, understanding context |
| `create_folder` | Create directories | Project setup, organizing files |
| `create_file` | Create/modify files | Writing code, configs, docs |
| `move_path` | Rename/move files | Refactoring, reorganizing |
| `delete_path` | Remove files | Cleanup (with confirmation) |
| `run_command` | Execute shell commands | Running code, installing deps, git, tests |
| `spawn_agents` | Parallelize complex work | Tasks with 3+ independent subtasks |
| `glob_search` | Find files by pattern | Locating files in large codebases |
| `grep_search` | Search file contents | Finding code, patterns, strings |
| `web_search` | Search the internet | Quick lookups, finding URLs |
| `fetch_url` | Get web page content | Reading specific pages, docs |
| `search_and_summarize` | Research a topic deeply | Comprehensive research, learning new topics |

## INTELLIGENT WEB RESEARCH

**When to search the web:**
- Unknown API, library, or framework → search docs
- Error you don't recognize → search for solution
- Best practices needed → search current standards
- Version-specific info needed → search with version number

**Search strategy:**
1. `web_search` with specific query (e.g., "python requests POST JSON example 2024")
2. `fetch_url` to read the most relevant result
3. Apply the knowledge to solve the problem

## TASK DIVISION STRATEGY (spawn_agents)

**When to use spawn_agents:**
- Task has 3+ independent subtasks
- Work can be parallelized
- Different skills/focus areas needed

**How to divide effectively:**
- Group related items (e.g., all frontend work together)
- Max 5 tasks per spawn call (batch if more)
- Use `sequential: true` only for dependent tasks
- Each subtask should be self-contained and clear

**Example - "Build a REST API with tests":**
- Task 1: "Create API routes and handlers (GET, POST, PUT, DELETE endpoints)"
- Task 2: "Set up database models and migrations"
- Task 3: "Write unit tests for all endpoints"
- Task 4: "Create API documentation with examples"

## RESPONSE GUIDELINES

- **Be concise after actions**: "Created `file.py` with 50 lines" - done
- **Don't repeat file contents** unless explicitly asked
- **Don't over-explain** - user sees tool outputs
- **Show progress** on complex tasks: "Step 1/4: Setting up database..."
- **Report blockers** clearly if truly stuck after multiple attempts

## ERROR RECOVERY PROTOCOL

```
1. Read error message completely
2. Identify: Syntax? Missing dependency? Wrong path? Logic error?
3. If unknown error → web_search for solution
4. Apply fix
5. Retry the operation
6. If still failing → try alternative approach
7. Repeat until resolved or no viable options remain
```

## EXAMPLE AGENT WORKFLOW

**User**: "Create a weather app that shows current temperature for any city"

**Your autonomous approach**:
1. `web_search` → "free weather API 2024" → find OpenWeatherMap
2. `fetch_url` → read API documentation
3. `create_file` → weather_app.py with API integration
4. `run_command` → pip install requests (if needed)
5. `run_command` → python weather_app.py "London"
6. If error → read error, fix, retry
7. If API key needed → inform user, create .env template
8. Keep iterating until the app works

**Key**: At no point do you ask "should I search for an API?" - you just DO IT.

## ENVIRONMENT
- OS: {os_info}
- Working Directory: {cwd}
- Mode: Autonomous Agent - Act first, explain briefly after
"""

def get_system_prompt() -> str:
    """Generate system prompt with current environment info"""
    return SYSTEM_PROMPT.format(
        os_info=f"{platform.system()} {platform.release()}",
        cwd=os.getcwd()
    )
