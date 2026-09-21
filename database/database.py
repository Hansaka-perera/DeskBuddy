from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
from typing import Optional, List, Dict


class Database:
    def __init__(self, path: str = "database/memory.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT
            );
            INSERT OR IGNORE INTO users (id, name) VALUES (1, 'User');

            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                memory_key TEXT NOT NULL,
                memory_value TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(category, memory_key)
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS alarms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'reminder',
                enabled INTEGER NOT NULL DEFAULT 1,
                last_fired_date TEXT
            );
            """)

    def remember(self, category: str, key: str, value: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("""
                INSERT INTO memories(category, memory_key, memory_value)
                VALUES (?, ?, ?)
                ON CONFLICT(category, memory_key)
                DO UPDATE SET memory_value=excluded.memory_value, updated_at=CURRENT_TIMESTAMP
            """, (category, key, value))

    def get_memory(self, category: Optional[str] = None) -> List[Dict]:
        query = "SELECT category, memory_key, memory_value FROM memories"
        args = []
        if category:
            query += " WHERE category = ?"
            args.append(category)
        query += " ORDER BY updated_at DESC"
        with self._lock, self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        return [dict(r) for r in rows]

    def add_message(self, role: str, content: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("INSERT INTO conversations(role, content) VALUES (?, ?)", (role, content))

    def recent_messages(self, limit: int = 12) -> List[Dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM conversations ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def clear_memories(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM memories")

    def clear_conversations(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM conversations")

    def add_alarm(self, alarm_time: str, alarm_type: str = "reminder") -> int:
        with self._lock, self._connect() as conn:
            return conn.execute("INSERT INTO alarms(time, type) VALUES (?, ?)", (alarm_time, alarm_type)).lastrowid

    def due_alarms(self, current_time: str) -> List[Dict]:
        today = __import__("datetime").date.today().isoformat()
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM alarms WHERE enabled=1 AND time=? AND (last_fired_date IS NULL OR last_fired_date != ?)", (current_time, today)).fetchall()
        return [dict(row) for row in rows]

    def mark_alarm_fired(self, alarm_id: int) -> None:
        today = __import__("datetime").date.today().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE alarms SET last_fired_date=? WHERE id=?", (today, alarm_id))
