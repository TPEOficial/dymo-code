"""
Multi-Agent System for Dymo Code
Allows multiple AI agents to work in parallel on different tasks
"""

import os
import sys
import uuid
import threading
import queue
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.live import Live
from rich.table import Table
from rich.box import ROUNDED

from .config import COLORS

# ═══════════════════════════════════════════════════════════════════════════════
# Agent Types and Status
# ═══════════════════════════════════════════════════════════════════════════════

class AgentStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AgentType(Enum):
    GENERAL = "general"           # General purpose agent
    CODER = "coder"               # Code generation agent
    REVIEWER = "reviewer"         # Code review agent
    RESEARCHER = "researcher"     # Research/web search agent
    FILE_OP = "file_op"           # File operations agent
    SHELL = "shell"               # Shell command execution agent

@dataclass
class AgentTask:
    """Represents a task assigned to an agent"""
    id: str
    task_type: AgentType
    description: str
    prompt: str
    status: AgentStatus = AgentStatus.QUEUED
    progress: int = 0
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    parent_task_id: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.task_type.value,
            "description": self.description,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

# ═══════════════════════════════════════════════════════════════════════════════
# Agent Worker
# ═══════════════════════════════════════════════════════════════════════════════

class AgentWorker:
    """
    Individual agent worker that executes tasks.
    Each worker runs in its own thread and can process tasks independently.
    """

    def __init__(self, worker_id: str, agent_type: AgentType, llm_client, tools: Dict):
        self.worker_id = worker_id
        self.agent_type = agent_type
        self.llm_client = llm_client
        self.tools = tools
        self.current_task: Optional[AgentTask] = None
        self.is_busy = False
        self.stop_flag = threading.Event()

    def execute_task(self, task: AgentTask, on_progress: Callable = None) -> AgentTask:
        """Execute a task and return the updated task with results"""
        self.current_task = task
        self.is_busy = True
        task.status = AgentStatus.RUNNING
        task.started_at = datetime.now()

        try:
            # Build messages for the LLM
            system_prompt = self._get_system_prompt()
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task.prompt}
            ]

            # Execute with the LLM
            response = self.llm_client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                tools=list(self.tools.values()) if self.tools else None,
                stream=True
            )

            result_text = ""
            for chunk in response:
                if self.stop_flag.is_set():
                    task.status = AgentStatus.CANCELLED
                    break

                choice = chunk.choices[0]
                if choice.delta.content:
                    result_text += choice.delta.content

                # Update progress based on content length (rough estimate)
                if on_progress:
                    estimated_progress = min(90, len(result_text) // 10)
                    task.progress = estimated_progress
                    on_progress(task)

            if task.status != AgentStatus.CANCELLED:
                task.result = result_text
                task.status = AgentStatus.COMPLETED
                task.progress = 100

        except Exception as e:
            task.status = AgentStatus.FAILED
            task.error = str(e)

        finally:
            task.completed_at = datetime.now()
            self.is_busy = False
            self.current_task = None

        return task

    def _get_system_prompt(self) -> str:
        """Get the appropriate system prompt based on agent type"""
        prompts = {
            AgentType.GENERAL: """Eres un asistente de IA general. Ayuda al usuario con cualquier tarea.
Sé conciso y directo en tus respuestas.""",

            AgentType.CODER: """Eres un experto en programación. Tu trabajo es escribir código limpio,
eficiente y bien documentado. Siempre explica brevemente tu código.
Usa las herramientas disponibles para crear archivos cuando sea necesario.""",

            AgentType.REVIEWER: """Eres un revisor de código experto. Analiza el código en busca de:
- Bugs y errores potenciales
- Problemas de seguridad
- Mejoras de rendimiento
- Mejores prácticas
Proporciona feedback constructivo y específico.""",

            AgentType.RESEARCHER: """Eres un investigador. Tu trabajo es buscar información,
analizar datos y proporcionar resúmenes claros y concisos.
Cita fuentes cuando sea posible.""",

            AgentType.FILE_OP: """Eres un especialista en operaciones de archivos.
Tu trabajo es crear, modificar, mover y organizar archivos y carpetas.
Siempre confirma las operaciones realizadas.""",

            AgentType.SHELL: """Eres un experto en línea de comandos.
Tu trabajo es ejecutar comandos de shell de forma segura.
Siempre explica qué hace cada comando antes de ejecutarlo.
NUNCA ejecutes comandos destructivos sin confirmación."""
        }
        return prompts.get(self.agent_type, prompts[AgentType.GENERAL])

    def cancel(self):
        """Cancel the current task"""
        self.stop_flag.set()

# ═══════════════════════════════════════════════════════════════════════════════
# Agent Manager
# ═══════════════════════════════════════════════════════════════════════════════

class AgentManager:
    """
    Manages multiple agent workers and task distribution.
    Allows running multiple tasks in parallel.
    """

    def __init__(self, llm_client, tools: Dict, max_workers: int = 4):
        self.llm_client = llm_client
        self.tools = tools
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        self.tasks: Dict[str, AgentTask] = {}
        self.task_futures: Dict[str, Future] = {}
        self.workers: Dict[str, AgentWorker] = {}

        self.console = Console(force_terminal=True)
        self.lock = threading.Lock()

        # Callbacks
        self.on_task_update: Optional[Callable[[AgentTask], None]] = None
        self.on_task_complete: Optional[Callable[[AgentTask], None]] = None

    def create_task(
        self,
        description: str,
        prompt: str,
        task_type: AgentType = AgentType.GENERAL,
        parent_task_id: str = None
    ) -> AgentTask:
        """Create a new task"""
        task_id = str(uuid.uuid4())[:8]
        task = AgentTask(
            id=task_id,
            task_type=task_type,
            description=description,
            prompt=prompt,
            parent_task_id=parent_task_id
        )

        with self.lock:
            self.tasks[task_id] = task

            if parent_task_id and parent_task_id in self.tasks:
                self.tasks[parent_task_id].subtasks.append(task_id)

        return task

    def submit_task(self, task: AgentTask, run_async: bool = True) -> Optional[str]:
        """
        Submit a task for execution.
        If run_async=True, runs in background and returns task ID.
        If run_async=False, blocks until completion and returns result.
        """
        worker_id = str(uuid.uuid4())[:8]
        worker = AgentWorker(
            worker_id=worker_id,
            agent_type=task.task_type,
            llm_client=self.llm_client,
            tools=self.tools
        )

        with self.lock:
            self.workers[worker_id] = worker

        def execute_and_cleanup():
            try:
                result = worker.execute_task(task, on_progress=self._handle_progress)

                if self.on_task_complete:
                    self.on_task_complete(result)

                return result
            finally:
                with self.lock:
                    if worker_id in self.workers:
                        del self.workers[worker_id]

        if run_async:
            future = self.executor.submit(execute_and_cleanup)
            with self.lock:
                self.task_futures[task.id] = future
            return task.id
        else:
            return execute_and_cleanup()

    def _handle_progress(self, task: AgentTask):
        """Handle task progress updates"""
        with self.lock:
            self.tasks[task.id] = task

        if self.on_task_update:
            self.on_task_update(task)

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Get a task by ID"""
        with self.lock:
            return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[AgentTask]:
        """Get all tasks"""
        with self.lock:
            return list(self.tasks.values())

    def get_running_tasks(self) -> List[AgentTask]:
        """Get all currently running tasks"""
        with self.lock:
            return [t for t in self.tasks.values() if t.status == AgentStatus.RUNNING]

    def get_queued_tasks(self) -> List[AgentTask]:
        """Get all queued tasks"""
        with self.lock:
            return [t for t in self.tasks.values() if t.status == AgentStatus.QUEUED]

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a specific task"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status in [AgentStatus.QUEUED, AgentStatus.RUNNING]:
                    task.status = AgentStatus.CANCELLED

                    # Cancel the worker if running
                    for worker in self.workers.values():
                        if worker.current_task and worker.current_task.id == task_id:
                            worker.cancel()
                            break

                    # Cancel future if exists
                    if task_id in self.task_futures:
                        self.task_futures[task_id].cancel()

                    return True
        return False

    def cancel_all_tasks(self):
        """Cancel all running and queued tasks"""
        with self.lock:
            for task in self.tasks.values():
                if task.status in [AgentStatus.QUEUED, AgentStatus.RUNNING]:
                    task.status = AgentStatus.CANCELLED

            for worker in self.workers.values():
                worker.cancel()

            for future in self.task_futures.values():
                future.cancel()

    def wait_for_task(self, task_id: str, timeout: float = None) -> Optional[AgentTask]:
        """Wait for a specific task to complete"""
        with self.lock:
            future = self.task_futures.get(task_id)

        if future:
            try:
                future.result(timeout=timeout)
            except Exception:
                pass

        return self.get_task(task_id)

    def wait_for_all(self, timeout: float = None):
        """Wait for all tasks to complete"""
        with self.lock:
            futures = list(self.task_futures.values())

        for future in futures:
            try: future.result(timeout=timeout)
            except Exception: pass

    def shutdown(self):
        """Shutdown the agent manager"""
        self.cancel_all_tasks()
        self.executor.shutdown(wait=False)

    # ═══════════════════════════════════════════════════════════════════════════
    # Display Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def display_status(self):
        """Display current status of all agents and tasks"""
        tasks = self.get_all_tasks()

        if not tasks:
            self.console.print(f"\n[{COLORS['muted']}]No hay tareas en el sistema.[/]\n")
            return

        table = Table(
            title="Estado de Agentes",
            box=ROUNDED,
            title_style=f"bold {COLORS['primary']}",
            header_style=f"bold {COLORS['secondary']}"
        )
        table.add_column("ID", style=f"{COLORS['accent']}", width=10)
        table.add_column("Tipo", style=f"{COLORS['muted']}", width=12)
        table.add_column("Descripción", style="white", ratio=2)
        table.add_column("Estado", width=14)
        table.add_column("Progreso", width=12)

        for task in sorted(tasks, key=lambda t: t.created_at, reverse=True)[:10]:
            status_display = {
                AgentStatus.QUEUED: f"[{COLORS['muted']}]◯ En cola[/]",
                AgentStatus.RUNNING: f"[{COLORS['warning']}]⟳ Ejecutando[/]",
                AgentStatus.COMPLETED: f"[{COLORS['success']}]✓ Completado[/]",
                AgentStatus.FAILED: f"[{COLORS['error']}]✗ Error[/]",
                AgentStatus.CANCELLED: f"[{COLORS['muted']}]⊘ Cancelado[/]"
            }.get(task.status, str(task.status))

            progress_bar = f"[{COLORS['primary']}]{'█' * (task.progress // 10)}{'░' * (10 - task.progress // 10)}[/]"

            table.add_row(
                task.id,
                task.task_type.value,
                task.description[:40] + ("..." if len(task.description) > 40 else ""),
                status_display,
                progress_bar
            )

        self.console.print()
        self.console.print(table)

        # Show active workers
        with self.lock:
            active = len([w for w in self.workers.values() if w.is_busy])
            self.console.print(
                f"\n[{COLORS['muted']}]Trabajadores activos: {active}/{self.max_workers}[/]\n"
            )

    def display_task_result(self, task_id: str):
        """Display the result of a specific task"""
        task = self.get_task(task_id)
        if not task:
            self.console.print(f"\n[{COLORS['error']}]Tarea no encontrada: {task_id}[/]\n")
            return

        status_color = {
            AgentStatus.COMPLETED: COLORS['success'],
            AgentStatus.FAILED: COLORS['error'],
            AgentStatus.CANCELLED: COLORS['muted']
        }.get(task.status, COLORS['muted'])

        header = Text()
        header.append(f"Tarea {task.id} ", style=f"bold {COLORS['accent']}")
        header.append(f"({task.status.value})", style=f"{status_color}")

        content = task.result if task.result else task.error if task.error else "Sin resultado"

        self.console.print()
        self.console.print(Panel(
            content,
            title=header,
            title_align="left",
            border_style=status_color,
            box=ROUNDED,
            padding=(1, 2)
        ))
        self.console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

# Will be initialized when the agent starts
agent_manager: Optional[AgentManager] = None


def init_agent_manager(llm_client, tools: Dict, max_workers: int = 4) -> AgentManager:
    """Initialize the global agent manager"""
    global agent_manager
    agent_manager = AgentManager(llm_client, tools, max_workers)
    return agent_manager


def get_agent_manager() -> Optional[AgentManager]:
    """Get the global agent manager"""
    return agent_manager