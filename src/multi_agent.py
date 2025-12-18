"""
Multi-Agent System for Dymo Code
Enables parallel task execution with multiple AI agents
"""

import threading
import time
import uuid
import queue
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future, as_completed

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID

from .config import COLORS, AVAILABLE_MODELS, DEFAULT_MODEL, get_system_prompt


# ═══════════════════════════════════════════════════════════════════════════════
# Task Status
# ═══════════════════════════════════════════════════════════════════════════════

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Task
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AgentTask:
    """Represents a task to be executed by an agent"""
    id: str
    description: str
    prompt: str
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    error: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model: str = DEFAULT_MODEL
    agent_id: Optional[str] = None
    parent_task_id: Optional[str] = None  # For subtasks
    progress: float = 0.0
    depends_on: List[str] = field(default_factory=list)  # Task IDs this depends on
    order: int = 0  # Execution order for sequential tasks

    @property
    def duration(self) -> float:
        """Get task duration in seconds"""
        if not self.started_at:
            return 0
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()

    @property
    def status_icon(self) -> str:
        """Get status icon"""
        icons = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.RUNNING: "🔄",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.CANCELLED: "🚫",
        }
        return icons.get(self.status, "❓")


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Worker
# ═══════════════════════════════════════════════════════════════════════════════

class AgentWorker:
    """
    A fast, lightweight worker for parallel task execution.
    Optimized for speed with minimal overhead.
    """

    # Shared client manager for all workers (avoid recreation)
    _shared_client_manager = None
    _client_cache = {}
    _cache_lock = threading.Lock()

    def __init__(self, worker_id: str, model_key: str = DEFAULT_MODEL):
        self.worker_id = worker_id
        self.model_key = model_key
        self.is_busy = False
        self.current_task: Optional[AgentTask] = None
        self._lock = threading.Lock()

    @classmethod
    def _get_shared_client(cls, model_key: str):
        """Get or create a shared client (cached for speed)"""
        with cls._cache_lock:
            if cls._shared_client_manager is None:
                from .clients import ClientManager
                cls._shared_client_manager = ClientManager()

            cache_key = model_key
            if cache_key not in cls._client_cache:
                cls._client_cache[cache_key] = {
                    "client": cls._shared_client_manager.get_client(model_key),
                    "model_id": cls._shared_client_manager.get_model_id(model_key)
                }
            return cls._client_cache[cache_key]

    def execute_task(self, task: AgentTask, progress_callback: Callable = None) -> str:
        """Execute a task and return the result - FAST version"""
        from .tools import get_all_tool_definitions, execute_tool

        with self._lock:
            self.is_busy = True
            self.current_task = task

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task.agent_id = self.worker_id

        try:
            # Use cached client (much faster)
            cached = self._get_shared_client(self.model_key)
            client = cached["client"]
            model_id = cached["model_id"]

            # Minimal system prompt for speed
            system_prompt = f"Task: {task.description}\nExecute efficiently. Be concise. CWD: {self._get_cwd()}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task.prompt}
            ]

            # Get tools (exclude multi-agent tools)
            all_tools = get_all_tool_definitions()
            tools = [t for t in all_tools if t.get("function", {}).get("name") not in ("spawn_agents", "check_agent_tasks")]

            # Fast execution - max 5 rounds, quick timeout
            max_rounds = 5
            full_response = ""

            for round_num in range(max_rounds):
                if progress_callback:
                    progress_callback(task.id, (round_num + 1) / max_rounds)

                response_text = ""
                tool_calls = []

                try:
                    for chunk in client.stream_chat(messages=messages, model=model_id, tools=tools):
                        if chunk.content:
                            response_text += chunk.content
                        if chunk.tool_calls:
                            tool_calls.extend(chunk.tool_calls)
                except Exception as e:
                    task.error = str(e)
                    task.status = TaskStatus.FAILED
                    return f"Error: {str(e)}"

                if tool_calls:
                    messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments}} for tc in tool_calls]
                    })

                    # Execute tools
                    for tc in tool_calls:
                        try:
                            # Parse arguments - can be string JSON or dict
                            if isinstance(tc.arguments, dict):
                                args = tc.arguments
                            elif isinstance(tc.arguments, str):
                                import json
                                try:
                                    args = json.loads(tc.arguments) if tc.arguments.strip() else {}
                                except json.JSONDecodeError:
                                    args = {}
                            else:
                                args = {}

                            result = execute_tool(tc.name, args)
                            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)[:3000]})
                        except Exception as e:
                            messages.append({"role": "tool", "tool_call_id": tc.id, "content": f"Error: {e}"})
                else:
                    full_response = response_text
                    break

            task.result = full_response
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.progress = 1.0
            return full_response

        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            return f"Task failed: {e}"
        finally:
            with self._lock:
                self.is_busy = False
                self.current_task = None

    def _get_cwd(self) -> str:
        import os
        return os.getcwd()


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Pool
# ═══════════════════════════════════════════════════════════════════════════════

class AgentPool:
    """
    Fast pool of agent workers for parallel task execution.
    Pre-initialized executor for minimal latency.
    """

    MAX_WORKERS = 5

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console(force_terminal=True)
        self.tasks: Dict[str, AgentTask] = {}
        self.workers: Dict[str, AgentWorker] = {}
        # Pre-initialize executor for speed
        self.executor = ThreadPoolExecutor(max_workers=self.MAX_WORKERS)
        self.futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._task_callbacks: Dict[str, Callable] = {}

    def _get_colors(self) -> Dict[str, str]:
        """Get theme colors"""
        try:
            from .themes import theme_manager
            return theme_manager.colors
        except ImportError:
            return {
                "primary": "#7C3AED",
                "secondary": "#06B6D4",
                "success": "#10B981",
                "warning": "#F59E0B",
                "error": "#EF4444",
                "muted": "#6B7280",
            }

    def create_task(
        self,
        description: str,
        prompt: str,
        model: str = DEFAULT_MODEL,
        parent_task_id: str = None
    ) -> AgentTask:
        """Create a new task"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        task = AgentTask(
            id=task_id,
            description=description,
            prompt=prompt,
            model=model,
            parent_task_id=parent_task_id
        )

        with self._lock:
            self.tasks[task_id] = task

        return task

    def submit_task(self, task: AgentTask, callback: Callable = None) -> str:
        """Submit a task for execution - fast path"""
        # Create worker
        worker_id = f"worker_{uuid.uuid4().hex[:6]}"
        worker = AgentWorker(worker_id, task.model)

        with self._lock:
            self.workers[worker_id] = worker
            if callback:
                self._task_callbacks[task.id] = callback

        def progress_update(task_id: str, progress: float):
            with self._lock:
                if task_id in self.tasks:
                    self.tasks[task_id].progress = progress

        def execute_and_cleanup():
            try:
                result = worker.execute_task(task, progress_update)
                # Call callback if set
                with self._lock:
                    if task.id in self._task_callbacks:
                        try:
                            self._task_callbacks[task.id](task, result)
                        except Exception:
                            pass
                return result
            finally:
                with self._lock:
                    if worker_id in self.workers:
                        del self.workers[worker_id]

        future = self.executor.submit(execute_and_cleanup)

        with self._lock:
            self.futures[task.id] = future

        return task.id

    def submit_tasks_parallel(
        self,
        tasks: List[AgentTask],
        callback: Callable = None
    ) -> List[str]:
        """Submit multiple tasks to run in parallel"""
        task_ids = []
        for task in tasks:
            task_id = self.submit_task(task, callback)
            task_ids.append(task_id)
        return task_ids

    def submit_tasks_sequential(
        self,
        tasks: List[AgentTask],
        callback: Callable = None,
        pass_context: bool = True
    ) -> List[str]:
        """
        Submit tasks to run sequentially (one after another).
        Each task waits for the previous to complete.
        If pass_context=True, previous task results are added to the next task's context.
        """
        task_ids = []
        previous_results = []

        for i, task in enumerate(tasks):
            task.order = i

            # Add context from previous tasks if enabled
            if pass_context and previous_results:
                context = "\n\n=== Context from previous tasks ===\n"
                for prev_desc, prev_result in previous_results:
                    context += f"\n[{prev_desc}]:\n{prev_result[:2000]}\n"
                context += "\n=== End of context ===\n\n"
                task.prompt = context + task.prompt

            # Submit and wait for completion
            task_id = self.submit_task(task, callback)
            task_ids.append(task_id)

            # Wait for this task to complete before moving to next
            result = self.get_task_result(task_id, timeout=120)

            # Store result for context passing
            if task.status == TaskStatus.COMPLETED:
                previous_results.append((task.description, task.result))
            elif task.status == TaskStatus.FAILED:
                # If a task fails, we can still continue or stop
                previous_results.append((task.description, f"FAILED: {task.error}"))

        return task_ids

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Get a task by ID"""
        with self._lock:
            return self.tasks.get(task_id)

    def get_task_result(self, task_id: str, timeout: float = None) -> Optional[str]:
        """Wait for a task to complete and return result"""
        with self._lock:
            future = self.futures.get(task_id)
            task = self.tasks.get(task_id)

        if not future or not task:
            return None

        try:
            future.result(timeout=timeout)
            return task.result
        except Exception as e:
            return f"Error: {str(e)}"

    def wait_all(self, task_ids: List[str], timeout: float = None) -> Dict[str, str]:
        """Wait for multiple tasks and return results"""
        results = {}

        for task_id in task_ids:
            result = self.get_task_result(task_id, timeout)
            results[task_id] = result or ""

        return results

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        with self._lock:
            future = self.futures.get(task_id)
            task = self.tasks.get(task_id)

        if future and task:
            cancelled = future.cancel()
            if cancelled or task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                return True
        return False

    def get_active_tasks(self) -> List[AgentTask]:
        """Get all active (pending or running) tasks"""
        with self._lock:
            return [
                t for t in self.tasks.values()
                if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
            ]

    def get_all_tasks(self) -> List[AgentTask]:
        """Get all tasks"""
        with self._lock:
            return list(self.tasks.values())

    def clear_completed(self):
        """Clear completed tasks from history"""
        with self._lock:
            to_remove = [
                tid for tid, t in self.tasks.items()
                if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ]
            for tid in to_remove:
                del self.tasks[tid]
                if tid in self.futures:
                    del self.futures[tid]
                if tid in self._task_callbacks:
                    del self._task_callbacks[tid]

    def shutdown(self):
        """Shutdown the pool"""
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None

    # ═══════════════════════════════════════════════════════════════════════════
    # Display Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def show_tasks(self):
        """Display all tasks in a table"""
        colors = self._get_colors()
        tasks = self.get_all_tasks()

        if not tasks:
            self.console.print(f"\n[{colors['muted']}]No tasks in queue.[/]\n")
            return

        table = Table(
            title="Agent Tasks",
            box=ROUNDED,
            title_style=f"bold {colors['secondary']}",
            header_style=f"bold {colors['muted']}"
        )

        table.add_column("ID", style=colors['accent'], width=12)
        table.add_column("Status", width=10)
        table.add_column("Description", style="white", max_width=40)
        table.add_column("Progress", width=10)
        table.add_column("Duration", style=colors['muted'], width=10)

        for task in sorted(tasks, key=lambda t: t.created_at, reverse=True):
            # Status with icon
            status_style = {
                TaskStatus.PENDING: colors['muted'],
                TaskStatus.RUNNING: colors['warning'],
                TaskStatus.COMPLETED: colors['success'],
                TaskStatus.FAILED: colors['error'],
                TaskStatus.CANCELLED: colors['muted'],
            }.get(task.status, "white")

            status_text = f"[{status_style}]{task.status_icon} {task.status.value}[/]"

            # Progress bar
            if task.status == TaskStatus.RUNNING:
                filled = int(task.progress * 10)
                progress = "█" * filled + "░" * (10 - filled)
            elif task.status == TaskStatus.COMPLETED:
                progress = "██████████"
            else:
                progress = "░░░░░░░░░░"

            # Duration
            duration = f"{task.duration:.1f}s" if task.duration > 0 else "-"

            table.add_row(
                task.id,
                status_text,
                task.description[:40],
                progress,
                duration
            )

        self.console.print()
        self.console.print(table)
        self.console.print()

    def show_task_result(self, task_id: str):
        """Show detailed result of a task"""
        colors = self._get_colors()
        task = self.get_task(task_id)

        if not task:
            self.console.print(f"[{colors['error']}]Task not found: {task_id}[/]")
            return

        # Build panel content
        content = Text()
        content.append(f"Status: ", style=colors['muted'])
        content.append(f"{task.status_icon} {task.status.value}\n", style=colors['secondary'])

        content.append(f"Description: ", style=colors['muted'])
        content.append(f"{task.description}\n\n", style="white")

        if task.result:
            content.append("Result:\n", style=f"bold {colors['success']}")
            content.append(task.result[:2000], style="white")
            if len(task.result) > 2000:
                content.append("\n... [truncated]", style=colors['muted'])

        if task.error:
            content.append("\nError:\n", style=f"bold {colors['error']}")
            content.append(task.error, style=colors['error'])

        panel = Panel(
            content,
            title=f"[bold {colors['primary']}]Task: {task_id}[/]",
            border_style=colors['border'] if 'border' in colors else colors['muted'],
            box=ROUNDED
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Definitions for Multi-Agent
# ═══════════════════════════════════════════════════════════════════════════════

MULTI_AGENT_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "spawn_agents",
            "description": """Spawn AI agents to work on tasks. Automatically detects if tasks should run in parallel or sequentially.

IMPORTANT - Dependency Detection:
- If tasks have dependencies (one needs the result of another), they run SEQUENTIALLY
- If tasks are independent, they run in PARALLEL for speed
- Keywords that indicate dependencies: "document", "review", "based on", "after", "using the", "from the"

Examples:
- PARALLEL: "Create a Python script" + "Create a README" (independent)
- SEQUENTIAL: "Create a project" + "Document the project" (second needs first)

Set sequential=true to force sequential execution when one task depends on another's output.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "description": "List of tasks to execute",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {
                                    "type": "string",
                                    "description": "Short description of what this agent should do"
                                },
                                "prompt": {
                                    "type": "string",
                                    "description": "Detailed instructions for the agent"
                                },
                                "depends_on_previous": {
                                    "type": "boolean",
                                    "description": "Set to true if this task depends on the previous task's result",
                                    "default": False
                                }
                            },
                            "required": ["description", "prompt"]
                        }
                    },
                    "sequential": {
                        "type": "boolean",
                        "description": "Force sequential execution (one task after another). Use when tasks have dependencies. Default: auto-detect",
                        "default": False
                    },
                    "wait_for_results": {
                        "type": "boolean",
                        "description": "Whether to wait for all agents to complete (default: true)",
                        "default": True
                    }
                },
                "required": ["tasks"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_agent_tasks",
            "description": "Check the status of running agent tasks",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of task IDs to check (optional, checks all if empty)"
                    }
                }
            }
        }
    }
]


# ═══════════════════════════════════════════════════════════════════════════════
# Dependency Detection (AI-powered, language-agnostic)
# ═══════════════════════════════════════════════════════════════════════════════

DEPENDENCY_CHECK_PROMPT = """Analyze these tasks and determine if they have dependencies (one task needs the result of another).

Tasks:
{tasks}

Rules:
- If Task 2+ needs files/code/output created by Task 1, they are DEPENDENT
- If Task 2+ documents, reviews, tests, or modifies what Task 1 creates, they are DEPENDENT
- If tasks work on completely separate things, they are INDEPENDENT

Reply with ONLY one word: DEPENDENT or INDEPENDENT"""


def detect_dependencies(tasks_data: List[Dict]) -> bool:
    """
    Detect if tasks have dependencies using AI analysis.
    Works with any language. Returns True if tasks should run sequentially.
    """
    if len(tasks_data) < 2:
        return False

    # Check explicit dependency flags first (fast path)
    for task in tasks_data[1:]:
        if task.get("depends_on_previous", False):
            return True

    # Use AI to analyze dependencies (language-agnostic)
    try:
        from .config import UTILITY_MODEL

        # Format tasks for analysis
        tasks_text = ""
        for i, task in enumerate(tasks_data, 1):
            desc = task.get("description", "")
            prompt = task.get("prompt", "")[:200]  # Limit prompt length
            tasks_text += f"Task {i}: {desc}\n  Details: {prompt}\n\n"

        analysis_prompt = DEPENDENCY_CHECK_PROMPT.format(tasks=tasks_text)

        # Use cached client for speed
        cached = AgentWorker._get_shared_client(UTILITY_MODEL)
        client = cached["client"]
        model_id = cached["model_id"]

        # Quick, non-streaming call for speed
        response_text = ""
        for chunk in client.stream_chat(
            messages=[{"role": "user", "content": analysis_prompt}],
            model=model_id,
            tools=None
        ):
            if chunk.content:
                response_text += chunk.content

        # Parse response
        response_lower = response_text.strip().lower()

        if "dependent" in response_lower and "independent" not in response_lower:
            return True
        elif "independent" in response_lower:
            return False
        else:
            # If unclear, assume dependent to be safe
            return "depend" in response_lower

    except Exception as e:
        # If AI check fails, fall back to simple heuristic
        from .logger import log_debug
        log_debug(f"AI dependency check failed, using fallback: {e}")
        return _fallback_dependency_check(tasks_data)


def _fallback_dependency_check(tasks_data: List[Dict]) -> bool:
    """
    Simple fallback dependency detection (keyword-based).
    Used when AI check fails.
    """
    # Common dependency indicators (multi-language)
    dependency_indicators = [
        "document", "review", "test", "deploy", "publish", "validate", "check",
        "both", "all", "ambos", "todos", "両方", "所有", "alle", "tous", "tutti",
        "after", "based on", "using", "from the",
    ]

    for task in tasks_data[1:]:
        combined = (task.get("description", "") + " " + task.get("prompt", "")).lower()
        if any(ind in combined for ind in dependency_indicators):
            return True

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

agent_pool = AgentPool()


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Execution
# ═══════════════════════════════════════════════════════════════════════════════

def execute_multi_agent_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Execute a multi-agent tool"""
    from .ui import console, display_info
    from rich.spinner import Spinner
    from rich.live import Live

    if tool_name == "spawn_agents":
        tasks_data = arguments.get("tasks", [])
        wait = arguments.get("wait_for_results", True)
        force_sequential = arguments.get("sequential", False)

        if not tasks_data:
            return "Error: No tasks provided"

        if len(tasks_data) > agent_pool.MAX_WORKERS:
            return f"Error: Maximum {agent_pool.MAX_WORKERS} parallel tasks allowed"

        # Detect if tasks have dependencies (using AI)
        if force_sequential:
            has_dependencies = True
        else:
            console.print()
            console.print(f"[dim]Analyzing task dependencies...[/]", end=" ")
            has_dependencies = detect_dependencies(tasks_data)
            console.print(f"[dim]{'Sequential' if has_dependencies else 'Parallel'}[/]")

        # Create tasks
        tasks = []
        for i, task_data in enumerate(tasks_data):
            task = agent_pool.create_task(
                description=task_data.get("description", "Unnamed task"),
                prompt=task_data.get("prompt", "")
            )
            task.order = i
            tasks.append(task)

        # Choose execution mode based on dependencies
        if has_dependencies:
            # Sequential execution - notify user
            console.print()
            console.print(f"[bold yellow]Dependencies detected - running {len(tasks)} tasks sequentially[/]")
            console.print(f"[dim]Each task will wait for the previous to complete and receive its context[/]")
            console.print()

            # Run sequentially with context passing
            task_ids = agent_pool.submit_tasks_sequential(tasks, pass_context=True)

            # Format results
            output = ["=== Sequential Agent Results ==="]
            output.append(f"(Tasks ran in order due to dependencies)\n")

            for i, task_id in enumerate(task_ids):
                task = agent_pool.get_task(task_id)
                if task:
                    output.append(f"\n--- [{i+1}/{len(tasks)}] {task.description} ---")
                    output.append(f"Status: {task.status.value}")
                    output.append(f"Duration: {task.duration:.1f}s")
                    if task.result:
                        output.append(f"Result:\n{task.result[:3000]}")
                    if task.error:
                        output.append(f"Error: {task.error}")
                    output.append("")

            return "\n".join(output)
        else:
            # Parallel execution
            console.print()
            console.print(f"[bold green]No dependencies - running {len(tasks)} tasks in parallel[/]")
            console.print()

            task_ids = agent_pool.submit_tasks_parallel(tasks)

            if wait:
                # Wait for all to complete
                results = agent_pool.wait_all(task_ids, timeout=120)  # 2 min timeout max

                # Format results
                output = ["=== Parallel Agent Results ==="]
                output.append(f"({len(tasks)} tasks ran simultaneously)\n")

                for task_id in task_ids:
                    task = agent_pool.get_task(task_id)
                    if task:
                        output.append(f"\n--- {task.description} ---")
                        output.append(f"Status: {task.status.value}")
                        output.append(f"Duration: {task.duration:.1f}s")
                        if task.result:
                            output.append(f"Result:\n{task.result[:3000]}")
                        if task.error:
                            output.append(f"Error: {task.error}")
                        output.append("")

                return "\n".join(output)
            else:
                # Return task IDs for later checking
                return f"Started {len(task_ids)} agents in parallel. Task IDs: {', '.join(task_ids)}\nUse check_agent_tasks to monitor progress."

    elif tool_name == "check_agent_tasks":
        task_ids = arguments.get("task_ids", [])

        if task_ids:
            tasks = [agent_pool.get_task(tid) for tid in task_ids if agent_pool.get_task(tid)]
        else:
            tasks = agent_pool.get_all_tasks()

        if not tasks:
            return "No tasks found."

        output = ["=== Agent Tasks Status ===\n"]

        for task in tasks:
            output.append(f"{task.status_icon} [{task.id}] {task.description}")
            output.append(f"   Status: {task.status.value}")
            if task.status == TaskStatus.RUNNING:
                output.append(f"   Progress: {task.progress*100:.0f}%")
            if task.status == TaskStatus.COMPLETED:
                preview = task.result[:200] + "..." if len(task.result) > 200 else task.result
                output.append(f"   Result preview: {preview}")
            if task.error:
                output.append(f"   Error: {task.error}")
            output.append("")

        return "\n".join(output)

    return f"Unknown multi-agent tool: {tool_name}"
