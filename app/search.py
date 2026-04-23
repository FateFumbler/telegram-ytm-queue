from __future__ import annotations

from typing import Protocol
import hashlib

from app.models import SongCandidate


class SearchProvider(Protocol):
    def search(self, query: str) -> list[SongCandidate]: ...
    def resolve(self, video_id: str, query: str = "") -> SongCandidate | None: ...
    def source_name(self) -> str: ...


CATALOG = [
    SongCandidate(video_id="vid-1", title="Blinding Lights", artist="The Weeknd", duration="3:20", album="After Hours", score=0.98),
    SongCandidate(video_id="vid-2", title="Yellow", artist="Coldplay", duration="4:26", album="Parachutes", score=0.97),
    SongCandidate(video_id="vid-3", title="Husn", artist="Anuv Jain", duration="3:38", album="Husn", score=0.96),
    SongCandidate(video_id="vid-4", title="Perfect", artist="Ed Sheeran", duration="4:21", album="Divide", score=0.93),
    SongCandidate(video_id="vid-5", title="Perfect", artist="One Direction", duration="3:52", album="Made in the A.M.", score=0.89),
]


class StaticSearchProvider:
    def search(self, query: str) -> list[SongCandidate]:
        q = query.lower().strip()
        scored: list[SongCandidate] = []
        for candidate in CATALOG:
            hay = f"{candidate.title} {candidate.artist} {candidate.album}".lower()
            score = 0.5
            if q in hay:
                score += 0.4
            for token in q.split():
                if token in hay:
                    score += 0.05
            scored.append(SongCandidate(**{**candidate.to_dict(), "score": min(score, 0.99)}))
        ranked = sorted(scored, key=lambda item: item.score, reverse=True)[:5]
        if q and (not ranked or ranked[0].score < 0.9):
            digest = hashlib.sha1(q.encode("utf-8")).hexdigest()[:12]
            return [
                SongCandidate(
                    video_id=f"query-{digest}",
                    title=query.strip(),
                    artist="YouTube Music search",
                    duration="",
                    album="",
                    score=0.99,
                )
            ]
        return ranked

    def resolve(self, video_id: str, query: str = "") -> SongCandidate | None:
        for candidate in self.search(query or video_id):
            if candidate.video_id == video_id:
                return candidate
        for candidate in CATALOG:
            if candidate.video_id == video_id:
                return candidate
        return None

    def source_name(self) -> str:
        return "static"


class YTMusicSearchProvider:
    def __init__(self, headers_path: str) -> None:
        try:
            from ytmusicapi import YTMusic
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("ytmusicapi is not installed") from exc
        self.client = YTMusic(headers_path)
        self.headers_path = headers_path

    def _normalize(self, item: dict, base_score: float = 0.8) -> SongCandidate:
        artists = item.get("artists") or []
        artist_text = ", ".join(a.get("name", "") for a in artists if a.get("name"))
        album = item.get("album", {}) or {}
        duration = item.get("duration") or item.get("duration_seconds") or ""
        score = float(item.get("score") or base_score)
        return SongCandidate(
            video_id=item.get("videoId") or item.get("browseId") or "",
            title=item.get("title") or "Unknown title",
            artist=artist_text or item.get("artist") or "Unknown artist",
            duration=str(duration),
            album=album.get("name", "") if isinstance(album, dict) else str(album),
            score=score,
        )

    def search(self, query: str) -> list[SongCandidate]:
        results = self.client.search(query, filter="songs", limit=5)
        normalized = [self._normalize(item, base_score=max(0.65, 0.95 - idx * 0.07)) for idx, item in enumerate(results)]
        return [item for item in normalized if item.video_id]

    def resolve(self, video_id: str, query: str = "") -> SongCandidate | None:
        if query:
            for item in self.search(query):
                if item.video_id == video_id:
                    return item
        search_term = query or video_id
        for item in self.search(search_term):
            if item.video_id == video_id:
                return item
        return None

    def source_name(self) -> str:
        return "ytmusicapi"


def build_search_provider(headers_path: str | None) -> SearchProvider:
    if headers_path:
        try:
            return YTMusicSearchProvider(headers_path)
        except Exception:
            pass
    return StaticSearchProvider()
