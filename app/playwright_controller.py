from __future__ import annotations

from app.browser import BrowserResult
from app.models import SongCandidate


class PlaywrightBrowserController:
    """Production hook point for a persistent Playwright profile tied to music.youtube.com.

    This is intentionally lightweight in repo state: it keeps the interface stable so the
    local worker can swap from mock -> real browser automation without changing the backend.
    """

    def __init__(self, profile_dir: str = "./playwright-profile") -> None:
        self.profile_dir = profile_dir

    def play_next(self, candidate: SongCandidate) -> BrowserResult:
        return BrowserResult(ok=False, action="play_next", detail=f"Playwright controller not wired yet for {candidate.title}")

    def add_to_queue(self, candidate: SongCandidate) -> BrowserResult:
        return BrowserResult(ok=False, action="add_to_queue", detail=f"Playwright controller not wired yet for {candidate.title}")

    def skip(self) -> BrowserResult:
        return BrowserResult(ok=False, action="skip", detail="Playwright controller not wired yet")

    def now_playing(self) -> str:
        return "Unknown (Playwright controller not wired yet)"
