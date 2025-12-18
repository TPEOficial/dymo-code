"""
Conversation history management for Dymo Code
Stores and retrieves past conversations with auto-generated titles
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import uuid

from .logger import log_error, log_debug
from .storage import get_history_directory, ensure_directories

# ═══════════════════════════════════════════════════════════════════════════════
# History Configuration
# ═══════════════════════════════════════════════════════════════════════════════

def get_history_path() -> Path:
    """Get the history directory path"""
    ensure_directories()
    return get_history_directory()

def get_conversations_file() -> Path:
    """Get the conversations file path"""
    return get_history_path() / "conversations.json"

MAX_CONVERSATIONS = 30  # Maximum conversations to keep

# ═══════════════════════════════════════════════════════════════════════════════
# Conversation Data Structure
# ═══════════════════════════════════════════════════════════════════════════════

def create_conversation(
    conversation_id: str = None,
    title: str = "New Conversation",
    messages: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a new conversation object"""
    return {
        "id": conversation_id or str(uuid.uuid4())[:8],
        "title": title,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "messages": messages or [],
        "message_count": len(messages) if messages else 0
    }

# ═══════════════════════════════════════════════════════════════════════════════
# History Manager
# ═══════════════════════════════════════════════════════════════════════════════

class HistoryManager:
    """Manages conversation history storage and retrieval"""

    def __init__(self):
        self.conversations: List[Dict[str, Any]] = []
        self.current_conversation_id: Optional[str] = None
        self._load_conversations()

    def _load_conversations(self):
        """Load conversations from file"""
        conversations_file = get_conversations_file()
        if conversations_file.exists():
            try:
                with open(conversations_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.conversations = data.get("conversations", [])
                log_debug(f"Loaded {len(self.conversations)} conversations")
            except Exception as e:
                log_error("Failed to load conversations", e)
                self.conversations = []
        else:
            self.conversations = []

    def _save_conversations(self):
        """Save conversations to file"""
        try:
            # Keep only the most recent conversations
            self.conversations = self.conversations[-MAX_CONVERSATIONS:]
            conversations_file = get_conversations_file()

            with open(conversations_file, 'w', encoding='utf-8') as f:
                json.dump({"conversations": self.conversations}, f, indent=2, ensure_ascii=False)
            log_debug(f"Saved {len(self.conversations)} conversations")
        except Exception as e:
            log_error("Failed to save conversations", e)

    def start_new_conversation(self) -> str:
        """Start a new conversation and return its ID"""
        conv = create_conversation()
        self.conversations.append(conv)
        self.current_conversation_id = conv["id"]
        self._save_conversations()
        return conv["id"]

    def get_current_conversation(self) -> Optional[Dict[str, Any]]:
        """Get the current conversation"""
        if not self.current_conversation_id:
            return None

        for conv in self.conversations:
            if conv["id"] == self.current_conversation_id:
                return conv
        return None

    def update_conversation(
        self,
        messages: List[Dict[str, Any]],
        title: str = None
    ):
        """Update the current conversation"""
        conv = self.get_current_conversation()
        if not conv:
            # Create new conversation if none exists
            self.start_new_conversation()
            conv = self.get_current_conversation()

        conv["messages"] = messages
        conv["message_count"] = len([m for m in messages if m.get("role") == "user"])
        conv["updated_at"] = datetime.now().isoformat()

        if title:
            conv["title"] = title

        self._save_conversations()

    def set_title(self, title: str):
        """Set the title for the current conversation"""
        conv = self.get_current_conversation()
        if conv:
            conv["title"] = title
            self._save_conversations()

    def get_recent_conversations(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get the n most recent conversations"""
        # Sort by updated_at descending and return summary info
        sorted_convs = sorted(
            self.conversations,
            key=lambda x: x.get("updated_at", ""),
            reverse=True
        )

        return [
            {
                "id": c["id"],
                "title": c["title"],
                "updated_at": c["updated_at"],
                "message_count": c.get("message_count", 0)
            }
            for c in sorted_convs[:n]
        ]

    def load_conversation(self, conversation_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load a specific conversation by ID"""
        for conv in self.conversations:
            if conv["id"] == conversation_id:
                self.current_conversation_id = conversation_id
                return conv.get("messages", [])
        return None

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation with all metadata by ID"""
        for conv in self.conversations:
            if conv["id"] == conversation_id:
                return conv
        return None

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation by ID"""
        for i, conv in enumerate(self.conversations):
            if conv["id"] == conversation_id:
                del self.conversations[i]
                if self.current_conversation_id == conversation_id:
                    self.current_conversation_id = None
                self._save_conversations()
                return True
        return False

    def rename_conversation(self, conversation_id: str, new_title: str) -> bool:
        """Rename a conversation by ID"""
        for conv in self.conversations:
            if conv["id"] == conversation_id:
                conv["title"] = new_title
                conv["updated_at"] = datetime.now().isoformat()
                self._save_conversations()
                return True
        return False

    def get_first_user_message(self, conversation_id: str = None) -> Optional[str]:
        """Get the first user message from a conversation"""
        if conversation_id:
            for conv in self.conversations:
                if conv["id"] == conversation_id:
                    messages = conv.get("messages", [])
                    break
            else:
                return None
        else:
            conv = self.get_current_conversation()
            if not conv:
                return None
            messages = conv.get("messages", [])

        for msg in messages:
            if msg.get("role") == "user":
                return msg.get("content", "")[:200]  # First 200 chars

        return None


# Global history manager instance
history_manager = HistoryManager()
