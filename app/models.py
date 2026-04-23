from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any


class Intent(str, Enum):
    PLAY_NEXT = "play_next"
    ADD_TO_QUEUE = "add_to_queue"
    NOW_PLAYING = "now_playing"
    SKIP = "skip"
    HELP = "help"
    UNKNOWN = "unknown"


class RequestStatus(str, Enum):
    PENDING_CONFIRMATION = "pending_confirmation"
    READY = "ready"
    QUEUED = "queued"
    EXECUTING = "executing"
    DONE = "done"
    FAILED = "failed"
    DUPLICATE = "duplicate"


@dataclass(slots=True)
class SongCandidate:
    video_id: str
    title: str
    artist: str
    duration: str = ""
    album: str = ""
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ParsedCommand:
    intent: Intent
    query: str = ""
    raw_text: str = ""


@dataclass(slots=True)
class QueueRequest:
    id: int
    chat_id: int
    user_id: int
    username: str
    intent: str
    query: str
    status: str
    message_id: int
    selected_video_id: str | None = None
    worker_note: str | None = None
