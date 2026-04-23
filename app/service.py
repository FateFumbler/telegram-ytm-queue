from __future__ import annotations

from dataclasses import dataclass

from app.browser import BrowserController
from app.db import Database
from app.models import Intent, RequestStatus, SongCandidate
from app.search import SearchProvider


@dataclass(slots=True)
class ServiceResponse:
    text: str
    request_id: int | None = None
    candidates: list[SongCandidate] | None = None


class QueueService:
    def __init__(self, db: Database, search_provider: SearchProvider) -> None:
        self.db = db
        self.search_provider = search_provider

    def create_song_request(self, *, chat_id: int, user_id: int, username: str, message_id: int, intent: Intent, query: str, dedupe_window_seconds: int) -> ServiceResponse:
        normalized_query = query.strip().lower()
        duplicate = self.db.find_recent_duplicate(chat_id=chat_id, query=normalized_query, seconds=dedupe_window_seconds)
        if duplicate:
            req_id = self.db.create_request(chat_id=chat_id, user_id=user_id, username=username, intent=intent.value, query=normalized_query, status=RequestStatus.DUPLICATE.value, message_id=message_id, worker_note=f"duplicate_of:{duplicate['id']}")
            return ServiceResponse(text=f"Already queued recently as request #{duplicate['id']}", request_id=req_id)

        candidates = self.search_provider.search(query)
        if not candidates:
            req_id = self.db.create_request(chat_id=chat_id, user_id=user_id, username=username, intent=intent.value, query=normalized_query, status=RequestStatus.FAILED.value, message_id=message_id, worker_note='no_results')
            return ServiceResponse(text=f"No results found for: {query}", request_id=req_id)

        top = candidates[0]
        confidence_gap = top.score - (candidates[1].score if len(candidates) > 1 else 0.0)
        high_confidence = top.score >= 0.9 and confidence_gap >= 0.03
        if high_confidence:
            req_id = self.db.create_request(chat_id=chat_id, user_id=user_id, username=username, intent=intent.value, query=normalized_query, status=RequestStatus.READY.value, message_id=message_id, selected_video_id=top.video_id, selected_payload=[top])
            return ServiceResponse(text=f"Queued request for {top.title} — {top.artist}", request_id=req_id, candidates=[top])

        req_id = self.db.create_request(chat_id=chat_id, user_id=user_id, username=username, intent=intent.value, query=normalized_query, status=RequestStatus.PENDING_CONFIRMATION.value, message_id=message_id, selected_payload=candidates[:3])
        return ServiceResponse(text="Multiple matches found. Confirm one of the top 3.", request_id=req_id, candidates=candidates[:3])

    def create_control_request(self, *, chat_id: int, user_id: int, username: str, message_id: int, intent: Intent) -> ServiceResponse:
        req_id = self.db.create_request(chat_id=chat_id, user_id=user_id, username=username, intent=intent.value, query=intent.value, status=RequestStatus.READY.value, message_id=message_id)
        if intent == Intent.SKIP:
            return ServiceResponse(text="Skip queued for the YouTube Music tab", request_id=req_id)
        return ServiceResponse(text=f"{intent.value} queued", request_id=req_id)

    def confirm_request(self, request_id: int, video_id: str) -> ServiceResponse:
        row = self.db.get_request(request_id)
        if not row:
            return ServiceResponse(text="Request not found")
        for candidate in self.db.pending_candidates(request_id):
            if candidate.video_id == video_id:
                self.db.update_request(request_id, status=RequestStatus.READY.value, selected_video_id=video_id, selected_payload=self.db.serialize_candidates([candidate]))
                return ServiceResponse(text=f"Confirmed {candidate.title} — {candidate.artist}", request_id=request_id, candidates=[candidate])
        return ServiceResponse(text="Candidate not found for confirmation", request_id=request_id)

    def next_job(self) -> dict | None:
        row = self.db.next_ready_request()
        if not row:
            return None
        self.db.update_request(row['id'], status=RequestStatus.QUEUED.value)
        fresh = self.db.get_request(row['id'])
        if not fresh:
            return None
        candidate = self.resolve_candidate(fresh)
        if candidate:
            fresh['candidate'] = candidate.to_dict()
        return fresh

    def resolve_candidate(self, row: dict) -> SongCandidate | None:
        if row.get('selected_payload'):
            candidates = self.db.pending_candidates(int(row['id']))
            if row.get('selected_video_id'):
                for candidate in candidates:
                    if candidate.video_id == row['selected_video_id']:
                        return candidate
            if len(candidates) == 1:
                return candidates[0]
        if row.get('selected_video_id'):
            return self.search_provider.resolve(row['selected_video_id'], row.get('query', ''))
        return None

    def execute_job(self, request_id: int, browser: BrowserController, chosen_candidate: SongCandidate) -> ServiceResponse:
        row = self.db.get_request(request_id)
        if not row:
            return ServiceResponse(text="Request missing", request_id=request_id)
        self.db.update_request(request_id, status=RequestStatus.EXECUTING.value)
        intent = row['intent']
        if intent == Intent.SKIP.value:
            result = browser.skip()
            detail = f"Skipped. Now playing: {result.detail}"
            self.mark_execution_result(request_id=request_id, ok=result.ok, detail=detail, worker_id='local-worker', now_playing=result.detail if result.ok else None, action=intent)
            return ServiceResponse(text=detail, request_id=request_id)
        if intent == Intent.PLAY_NEXT.value:
            result = browser.play_next(chosen_candidate)
        else:
            result = browser.add_to_queue(chosen_candidate)
        self.mark_execution_result(request_id=request_id, ok=result.ok, detail=result.detail, worker_id='local-worker', now_playing=(f"{chosen_candidate.title} — {chosen_candidate.artist}" if result.ok and intent == Intent.PLAY_NEXT.value else None), action=intent)
        return ServiceResponse(text=result.detail, request_id=request_id)

    def mark_execution_result(self, *, request_id: int, ok: bool, detail: str, worker_id: str, now_playing: str | None = None, action: str | None = None) -> ServiceResponse:
        row = self.db.get_request(request_id)
        if not row:
            return ServiceResponse(text='Request missing', request_id=request_id)
        final_status = RequestStatus.DONE.value if ok else RequestStatus.FAILED.value
        self.db.update_request(request_id, status=final_status, worker_note=detail)
        self.db.add_action(request_id=request_id, worker_id=worker_id, action=action or row['intent'], status='ok' if ok else 'failed', detail=detail)
        if now_playing:
            self.db.set_now_playing(now_playing)
        return ServiceResponse(text=detail, request_id=request_id)

    def skip(self, browser: BrowserController) -> ServiceResponse:
        result = browser.skip()
        self.db.set_now_playing(result.detail)
        self.db.add_action(request_id=None, worker_id='local', action='skip', status='ok' if result.ok else 'failed', detail=result.detail)
        return ServiceResponse(text=f"Skipped. Now playing: {result.detail}")

    def now_playing(self, browser: BrowserController | None = None) -> ServiceResponse:
        current = browser.now_playing() if browser else self.db.get_now_playing()
        if browser:
            self.db.set_now_playing(current)
        return ServiceResponse(text=f"Now playing: {current}")
