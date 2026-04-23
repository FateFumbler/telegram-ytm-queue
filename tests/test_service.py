from pathlib import Path

from app.db import Database
from app.models import Intent, RequestStatus
from app.search import StaticSearchProvider
from app.service import QueueService


def make_service(tmp_path: Path) -> QueueService:
    return QueueService(Database(tmp_path / 'app.db'), StaticSearchProvider())


def test_high_confidence_request_goes_ready(tmp_path):
    svc = make_service(tmp_path)
    res = svc.create_song_request(chat_id=1, user_id=2, username='tushar', message_id=10, intent=Intent.PLAY_NEXT, query='yellow coldplay', dedupe_window_seconds=120)
    assert 'Queued request' in res.text
    assert res.request_id is not None


def test_ambiguous_request_needs_confirmation(tmp_path):
    svc = make_service(tmp_path)
    res = svc.create_song_request(chat_id=1, user_id=2, username='tushar', message_id=10, intent=Intent.ADD_TO_QUEUE, query='perfect', dedupe_window_seconds=120)
    assert 'Multiple matches' in res.text
    assert len(res.candidates or []) >= 2


def test_duplicate_detection(tmp_path):
    svc = make_service(tmp_path)
    first = svc.create_song_request(chat_id=1, user_id=2, username='tushar', message_id=10, intent=Intent.ADD_TO_QUEUE, query='husn anuv jain', dedupe_window_seconds=120)
    second = svc.create_song_request(chat_id=1, user_id=2, username='tushar', message_id=11, intent=Intent.ADD_TO_QUEUE, query='husn anuv jain', dedupe_window_seconds=120)
    assert first.request_id is not None
    assert 'Already queued recently' in second.text
