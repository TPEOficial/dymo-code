"""
Persistent Memory System for Dymo Code
Stores user data, preferences, and context across sessions using SQLite
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path

from .storage import get_data_directory, get_db_path, ensure_directories

# ═══════════════════════════════════════════════════════════════════════════════
# Database Configuration
# ═══════════════════════════════════════════════════════════════════════════════

def get_database_path() -> Path:
    """Get the database path using the storage system"""
    return get_db_path()


def ensure_data_dir():
    """Ensure the data directory exists"""
    ensure_directories()


# ═══════════════════════════════════════════════════════════════════════════════
# Memory Manager Class
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryManager:
    """
    Manages persistent memory storage for the AI agent.
    Stores user profile, preferences, facts, and context.
    """

    def __init__(self):
        ensure_data_dir()
        db_path = get_database_path()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_database()

    def _init_database(self):
        """Initialize database tables"""
        cursor = self.conn.cursor()

        # User profile table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Facts/knowledge table - things the agent learns about the user
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                confidence REAL DEFAULT 1.0,
                source TEXT DEFAULT 'user',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Notes/reminders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,
                priority INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Projects table - track user's projects
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                path TEXT,
                description TEXT,
                tech_stack TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        self.conn.commit()

    # ═══════════════════════════════════════════════════════════════════════════
    # User Profile Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def set_profile(self, key: str, value: str, category: str = "general") -> bool:
        """Set a user profile value"""
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO user_profile (key, value, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=?, category=?, updated_at=?
        """, (key, value, category, now, now, value, category, now))
        self.conn.commit()
        return True

    def get_profile(self, key: str) -> Optional[str]:
        """Get a user profile value"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM user_profile WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None

    def get_all_profile(self) -> Dict[str, str]:
        """Get all user profile data"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value, category FROM user_profile")
        return {row["key"]: {"value": row["value"], "category": row["category"]} for row in cursor.fetchall()}

    def delete_profile(self, key: str) -> bool:
        """Delete a profile value"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM user_profile WHERE key = ?", (key,))
        self.conn.commit()
        return cursor.rowcount > 0

    # ═══════════════════════════════════════════════════════════════════════════
    # Facts Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def add_fact(self, fact: str, category: str = "general", confidence: float = 1.0, source: str = "user") -> int:
        """Add a fact about the user"""
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO facts (fact, category, confidence, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fact, category, confidence, source, now, now))
        self.conn.commit()
        return cursor.lastrowid

    def get_facts(self, category: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get facts, optionally filtered by category"""
        cursor = self.conn.cursor()
        if category:
            cursor.execute(
                "SELECT * FROM facts WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
                (category, limit)
            )
        else:
            cursor.execute("SELECT * FROM facts ORDER BY updated_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def search_facts(self, query: str) -> List[Dict]:
        """Search facts by content"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM facts WHERE fact LIKE ? ORDER BY confidence DESC, updated_at DESC",
            (f"%{query}%",)
        )
        return [dict(row) for row in cursor.fetchall()]

    def delete_fact(self, fact_id: int) -> bool:
        """Delete a fact"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    # ═══════════════════════════════════════════════════════════════════════════
    # Preferences Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def set_preference(self, key: str, value: str, description: str = None) -> bool:
        """Set a preference"""
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO preferences (key, value, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=?, description=?, updated_at=?
        """, (key, value, description, now, now, value, description, now))
        self.conn.commit()
        return True

    def get_preference(self, key: str, default: str = None) -> Optional[str]:
        """Get a preference value"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

    def get_all_preferences(self) -> Dict[str, Dict]:
        """Get all preferences"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value, description FROM preferences")
        return {row["key"]: {"value": row["value"], "description": row["description"]} for row in cursor.fetchall()}

    def delete_preference(self, key: str) -> bool:
        """Delete a preference"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM preferences WHERE key = ?", (key,))
        self.conn.commit()
        return cursor.rowcount > 0

    # ═══════════════════════════════════════════════════════════════════════════
    # Notes Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def add_note(self, title: str, content: str, tags: List[str] = None, priority: int = 0) -> int:
        """Add a note"""
        now = datetime.now().isoformat()
        tags_str = json.dumps(tags) if tags else None
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO notes (title, content, tags, priority, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, content, tags_str, priority, now, now))
        self.conn.commit()
        return cursor.lastrowid

    def get_notes(self, limit: int = 20) -> List[Dict]:
        """Get all notes"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM notes ORDER BY priority DESC, updated_at DESC LIMIT ?", (limit,))
        notes = []
        for row in cursor.fetchall():
            note = dict(row)
            if note["tags"]:
                note["tags"] = json.loads(note["tags"])
            notes.append(note)
        return notes

    def search_notes(self, query: str) -> List[Dict]:
        """Search notes"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM notes
            WHERE title LIKE ? OR content LIKE ?
            ORDER BY priority DESC, updated_at DESC
        """, (f"%{query}%", f"%{query}%"))
        notes = []
        for row in cursor.fetchall():
            note = dict(row)
            if note["tags"]:
                note["tags"] = json.loads(note["tags"])
            notes.append(note)
        return notes

    def update_note(self, note_id: int, title: str = None, content: str = None,
                    tags: List[str] = None, priority: int = None) -> bool:
        """Update a note"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        existing = cursor.fetchone()
        if not existing:
            return False

        now = datetime.now().isoformat()
        new_title = title if title is not None else existing["title"]
        new_content = content if content is not None else existing["content"]
        new_tags = json.dumps(tags) if tags is not None else existing["tags"]
        new_priority = priority if priority is not None else existing["priority"]

        cursor.execute("""
            UPDATE notes SET title=?, content=?, tags=?, priority=?, updated_at=?
            WHERE id=?
        """, (new_title, new_content, new_tags, new_priority, now, note_id))
        self.conn.commit()
        return True

    def delete_note(self, note_id: int) -> bool:
        """Delete a note"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    # ═══════════════════════════════════════════════════════════════════════════
    # Projects Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def add_project(self, name: str, path: str = None, description: str = None,
                    tech_stack: List[str] = None) -> int:
        """Add a project"""
        now = datetime.now().isoformat()
        tech_str = json.dumps(tech_stack) if tech_stack else None
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO projects (name, path, description, tech_stack, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET path=?, description=?, tech_stack=?, updated_at=?
        """, (name, path, description, tech_str, now, now, path, description, tech_str, now))
        self.conn.commit()
        return cursor.lastrowid

    def get_projects(self) -> List[Dict]:
        """Get all projects"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY updated_at DESC")
        projects = []
        for row in cursor.fetchall():
            project = dict(row)
            if project["tech_stack"]:
                project["tech_stack"] = json.loads(project["tech_stack"])
            projects.append(project)
        return projects

    def get_project(self, name: str) -> Optional[Dict]:
        """Get a specific project"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            project = dict(row)
            if project["tech_stack"]:
                project["tech_stack"] = json.loads(project["tech_stack"])
            return project
        return None

    def delete_project(self, name: str) -> bool:
        """Delete a project"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM projects WHERE name = ?", (name,))
        self.conn.commit()
        return cursor.rowcount > 0

    # ═══════════════════════════════════════════════════════════════════════════
    # Context Generation for AI
    # ═══════════════════════════════════════════════════════════════════════════

    def get_context_for_ai(self) -> str:
        """
        Generate a context string for the AI with relevant user information.
        This should be included in the system prompt.
        """
        context_parts = []

        # User profile
        profile = self.get_all_profile()
        if profile:
            context_parts.append("## User Information")
            for key, data in profile.items():
                context_parts.append(f"- {key}: {data['value']}")

        # Recent facts
        facts = self.get_facts(limit=10)
        if facts:
            context_parts.append("\n## Known Facts About User")
            for fact in facts:
                context_parts.append(f"- {fact['fact']}")

        # Preferences
        prefs = self.get_all_preferences()
        if prefs:
            context_parts.append("\n## User Preferences")
            for key, data in prefs.items():
                desc = f" ({data['description']})" if data['description'] else ""
                context_parts.append(f"- {key}: {data['value']}{desc}")

        # Current projects
        projects = self.get_projects()
        if projects:
            context_parts.append("\n## User's Projects")
            for proj in projects[:5]:  # Limit to 5 most recent
                tech = ", ".join(proj["tech_stack"]) if proj.get("tech_stack") else "N/A"
                context_parts.append(f"- {proj['name']}: {proj.get('description', 'No description')} (Tech: {tech})")

        if context_parts:
            return "\n".join(context_parts)
        return ""

    def close(self):
        """Close the database connection"""
        self.conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance
# ═══════════════════════════════════════════════════════════════════════════════

memory = MemoryManager()
