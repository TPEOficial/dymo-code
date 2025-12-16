"""
Message Queue Manager for Dymo Code
Allows users to queue messages while the agent is processing
"""

import threading, queue
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED

from .config import COLORS

# ═══════════════════════════════════════════════════════════════════════════════
# Queue Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class QueuedMessage:
    """A message waiting in the queue"""
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    position: int = 0

# ═══════════════════════════════════════════════════════════════════════════════
# Message Queue Manager
# ═══════════════════════════════════════════════════════════════════════════════

class MessageQueueManager:
    """Manages a queue of messages for the agent"""

    def __init__(self, console: Console):
        self.console = console
        self.message_queue: queue.Queue[QueuedMessage] = queue.Queue()
        self.is_processing = False
        self.lock = threading.Lock()
        self._message_counter = 0

    def add_message(self, content: str) -> int:
        """Add a message to the queue and return its position"""
        with self.lock:
            self._message_counter += 1
            position = self._message_counter
            msg = QueuedMessage(content=content, position=position)
            self.message_queue.put(msg)

            # Show queue notification
            queue_size = self.message_queue.qsize()
            self._show_queue_notification(content, queue_size)

            return position

    def get_next_message(self) -> Optional[QueuedMessage]:
        """Get the next message from the queue"""
        try:
            return self.message_queue.get_nowait()
        except queue.Empty:
            return None

    def has_pending_messages(self) -> bool:
        """Check if there are pending messages"""
        return not self.message_queue.empty()

    def get_queue_size(self) -> int:
        """Get the current queue size"""
        return self.message_queue.qsize()

    def set_processing(self, is_processing: bool):
        """Set the processing state"""
        with self.lock:
            self.is_processing = is_processing

    def is_agent_processing(self) -> bool:
        """Check if the agent is currently processing"""
        return self.is_processing

    def clear_queue(self):
        """Clear all pending messages"""
        with self.lock:
            while not self.message_queue.empty():
                try:
                    self.message_queue.get_nowait()
                except queue.Empty:
                    break
            self._message_counter = 0

    def _show_queue_notification(self, content: str, queue_size: int):
        """Show a notification that a message was queued"""
        preview = content[:50] + "..." if len(content) > 50 else content

        notification = Text()
        notification.append("📥 ", style=f"{COLORS['warning']}")
        notification.append("Message queued", style=f"bold {COLORS['warning']}")
        notification.append(f" (#{queue_size} in queue)", style=f"{COLORS['muted']}")
        notification.append("\n")
        notification.append(f'"{preview}"', style=f"italic {COLORS['muted']}")

        self.console.print(
            Panel(
                notification,
                border_style=f"{COLORS['warning']}",
                box=ROUNDED,
                padding=(0, 1)
            )
        )

    def show_queue_status(self):
        """Display current queue status"""
        size = self.get_queue_size()

        if size == 0:
            self.console.print(
                f"\n[{COLORS['muted']}]No messages in queue.[/]\n"
            )
        else:
            status = Text()
            status.append("📋 ", style=f"{COLORS['secondary']}")
            status.append(f"{size} message{'s' if size > 1 else ''}", style=f"bold {COLORS['secondary']}")
            status.append(" waiting in queue", style=f"{COLORS['muted']}")

            self.console.print(
                Panel(
                    status,
                    border_style=f"{COLORS['secondary']}",
                    box=ROUNDED,
                    padding=(0, 1)
                )
            )

    def show_processing_next(self, msg: QueuedMessage):
        """Show notification that we're processing the next queued message"""
        preview = msg.content[:60] + "..." if len(msg.content) > 60 else msg.content

        notification = Text()
        notification.append("▶ ", style=f"{COLORS['success']}")
        notification.append("Processing queued message", style=f"bold {COLORS['success']}")
        notification.append("\n")
        notification.append(f'"{preview}"', style=f"italic white")

        self.console.print()
        self.console.print(
            Panel(
                notification,
                border_style=f"{COLORS['success']}",
                box=ROUNDED,
                padding=(0, 1)
            )
        )
