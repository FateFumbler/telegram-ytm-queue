from __future__ import annotations

from functools import lru_cache
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.browser import MockBrowserController
from app.config import get_settings, Settings
from app.db import Database
from app.models import Intent
from app.parser import parse_message
from app.search import SearchProvider, build_search_provider
from app.service import QueueService


app = FastAPI(title="Telegram YTM Queue")


class ConfirmPayload(BaseModel):
    request_id: int
    video_id: str


class ExecutionReport(BaseModel):
    ok: bool
    detail: str
    worker_id: str = "extension"
    now_playing: str | None = None
    action: str | None = None


class PlaybackStatePayload(BaseModel):
    now_playing: str
    source: str = "extension"


class TelegramUser(BaseModel):
    id: int
    username: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str = "group"


class TelegramMessage(BaseModel):
    message_id: int
    text: str | None = None
    from_: TelegramUser | None = Field(default=None, alias="from")
    chat: TelegramChat

    model_config = {"populate_by_name": True, "protected_namespaces": ()}


class TelegramUpdate(BaseModel):
    message: TelegramMessage | None = None
    callback_query: dict | None = None


@lru_cache
def settings() -> Settings:
    return get_settings()


@lru_cache
def db() -> Database:
    return Database(settings().db_path)


@lru_cache
def search_provider() -> SearchProvider:
    return build_search_provider(settings().ytmusic_headers_path)


@lru_cache
def service() -> QueueService:
    return QueueService(db(), search_provider())


@lru_cache
def browser() -> MockBrowserController:
    return MockBrowserController()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "search_provider": search_provider().source_name()}


@app.post("/telegram/webhook")
def telegram_webhook(update: TelegramUpdate) -> dict:
    cfg = settings()
    svc = service()
    if update.callback_query:
        data = update.callback_query.get("data", "")
        if data.startswith("confirm:"):
            _, req_id, video_id = data.split(":", 2)
            res = svc.confirm_request(int(req_id), video_id)
            return {"ok": True, "message": res.text, "request_id": res.request_id}
        return {"ok": False, "message": "Unknown callback"}

    if not update.message:
        return {"ok": True, "message": "ignored"}

    chat_id = update.message.chat.id
    if cfg.allowed_chat_ids and chat_id not in cfg.allowed_chat_ids:
        raise HTTPException(status_code=403, detail="chat not allowed")

    parsed = parse_message(update.message.text or "")
    user = update.message.from_ or TelegramUser(id=0, username="unknown")

    if parsed.intent in {Intent.PLAY_NEXT, Intent.ADD_TO_QUEUE}:
        res = svc.create_song_request(
            chat_id=chat_id,
            user_id=user.id,
            username=user.username or "unknown",
            message_id=update.message.message_id,
            intent=parsed.intent,
            query=parsed.query,
            dedupe_window_seconds=cfg.dedupe_window_seconds,
        )
        payload = [c.to_dict() for c in res.candidates] if res.candidates else None
        return {"ok": True, "message": res.text, "request_id": res.request_id, "candidates": payload}

    if parsed.intent == Intent.NOW_PLAYING:
        return {"ok": True, "message": svc.now_playing().text}

    if parsed.intent == Intent.SKIP:
        res = svc.create_control_request(chat_id=chat_id, user_id=user.id, username=user.username or "unknown", message_id=update.message.message_id, intent=Intent.SKIP)
        return {"ok": True, "message": res.text, "request_id": res.request_id}

    if parsed.intent == Intent.HELP:
        return {"ok": True, "message": "Use /next, /queue, /add, /nowplaying, /skip"}

    return {"ok": True, "message": "Ignored. Use /next <song> or /queue <song>."}


@app.get('/api/worker/jobs/next')
def next_job() -> dict:
    row = service().next_job()
    return {"job": row}


@app.post('/api/worker/jobs/{request_id}/complete')
def complete_job(request_id: int) -> dict:
    row = db().get_request(request_id)
    if not row:
        raise HTTPException(status_code=404, detail='request not found')
    candidate = service().resolve_candidate(row)
    if row.get('intent') != Intent.SKIP.value and not candidate:
        raise HTTPException(status_code=400, detail='candidate not resolvable')
    res = service().execute_job(request_id, browser(), candidate)
    return {"ok": True, "message": res.text}


@app.post('/api/worker/jobs/{request_id}/report')
def report_job(request_id: int, payload: ExecutionReport) -> dict:
    res = service().mark_execution_result(
        request_id=request_id,
        ok=payload.ok,
        detail=payload.detail,
        worker_id=payload.worker_id,
        now_playing=payload.now_playing,
        action=payload.action,
    )
    return {"ok": payload.ok, "message": res.text}


@app.post('/api/extension/state')
def extension_state(payload: PlaybackStatePayload) -> dict:
    db().set_now_playing(payload.now_playing)
    db().add_action(request_id=None, worker_id=payload.source, action='state_update', status='ok', detail=payload.now_playing)
    return {"ok": True}


@app.get('/api/queue/now-playing')
def api_now_playing() -> dict:
    return {"now_playing": db().get_now_playing()}


@app.post('/api/queue/confirm')
def api_confirm(payload: ConfirmPayload) -> dict:
    res = service().confirm_request(payload.request_id, payload.video_id)
    return {"ok": True, "message": res.text}
