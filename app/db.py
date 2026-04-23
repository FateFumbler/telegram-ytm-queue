from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.models import SongCandidate


SCHEMA = """
CREATE TABLE IF NOT EXISTS queue_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    intent TEXT NOT NULL,
    query TEXT NOT NULL,
    status TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    selected_video_id TEXT,
    selected_payload TEXT,
    worker_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS queue_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER,
    worker_id TEXT,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS playback_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    now_playing TEXT DEFAULT 'Nothing playing',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO playback_state(id, now_playing) VALUES (1, 'Nothing playing');
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def serialize_candidates(candidates: list[SongCandidate] | None) -> str | None:
        return json.dumps([c.to_dict() for c in candidates]) if candidates else None

    def create_request(self, *, chat_id: int, user_id: int, username: str, intent: str, query: str, status: str, message_id: int, selected_payload: list[SongCandidate] | None = None, selected_video_id: str | None = None, worker_note: str | None = None) -> int:
        payload = self.serialize_candidates(selected_payload)
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO queue_requests(chat_id, user_id, username, intent, query, status, message_id, selected_video_id, selected_payload, worker_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (chat_id, user_id, username, intent, query, status, message_id, selected_video_id, payload, worker_note),
            )
            return int(cur.lastrowid)

    def get_request(self, request_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM queue_requests WHERE id = ?", (request_id,)).fetchone()
        return dict(row) if row else None

    def update_request(self, request_id: int, **fields: Any) -> None:
        if not fields:
            return
        if 'selected_payload' in fields and isinstance(fields['selected_payload'], list):
            fields['selected_payload'] = self.serialize_candidates(fields['selected_payload'])
        columns = ", ".join(f"{k} = ?" for k in fields.keys()) + ", updated_at = CURRENT_TIMESTAMP"
        values = list(fields.values()) + [request_id]
        with self.connect() as conn:
            conn.execute(f"UPDATE queue_requests SET {columns} WHERE id = ?", values)

    def find_recent_duplicate(self, *, chat_id: int, query: str, seconds: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM queue_requests
                WHERE chat_id = ? AND query = ? AND created_at >= datetime('now', ?)
                AND status IN ('ready', 'queued', 'executing', 'done', 'pending_confirmation')
                ORDER BY id DESC LIMIT 1
                """,
                (chat_id, query, f'-{seconds} seconds'),
            ).fetchone()
        return dict(row) if row else None

    def next_ready_request(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM queue_requests
                WHERE status = 'ready'
                   OR (status = 'queued' AND updated_at <= datetime('now', '-20 seconds'))
                ORDER BY id ASC LIMIT 1
                """
            ).fetchone()
        return dict(row) if row else None

    def pending_candidates(self, request_id: int) -> list[SongCandidate]:
        row = self.get_request(request_id)
        if not row or not row.get('selected_payload'):
            return []
        return [SongCandidate(**item) for item in json.loads(row['selected_payload'])]

    def add_action(self, *, request_id: int | None, worker_id: str | None, action: str, status: str, detail: str = '') -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO queue_actions(request_id, worker_id, action, status, detail) VALUES (?, ?, ?, ?, ?)",
                (request_id, worker_id, action, status, detail),
            )

    def set_now_playing(self, text: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE playback_state SET now_playing = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (text,))

    def get_now_playing(self) -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT now_playing FROM playback_state WHERE id = 1").fetchone()
        return str(row['now_playing']) if row else 'Nothing playing'
