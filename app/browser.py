from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models import SongCandidate


@dataclass(slots=True)
class BrowserResult:
    ok: bool
    action: str
    detail: str


class BrowserController(Protocol):
    def play_next(self, candidate: SongCandidate) -> BrowserResult: ...
    def add_to_queue(self, candidate: SongCandidate) -> BrowserResult: ...
    def skip(self) -> BrowserResult: ...
    def now_playing(self) -> str: ...


class MockBrowserController:
    def __init__(self) -> None:
        self.current = "Nothing playing"
        self.queue: list[str] = []

    def play_next(self, candidate: SongCandidate) -> BrowserResult:
        self.queue.insert(0, f"{candidate.title} — {candidate.artist}")
        return BrowserResult(ok=True, action="play_next", detail=self.queue[0])

    def add_to_queue(self, candidate: SongCandidate) -> BrowserResult:
        item = f"{candidate.title} — {candidate.artist}"
        self.queue.append(item)
        return BrowserResult(ok=True, action="add_to_queue", detail=item)

    def skip(self) -> BrowserResult:
        self.current = self.queue.pop(0) if self.queue else "Nothing playing"
        return BrowserResult(ok=True, action="skip", detail=self.current)

    def now_playing(self) -> str:
        return self.current
