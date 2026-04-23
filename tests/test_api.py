from pathlib import Path
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app, db, settings, service, search_provider, browser
from app.db import Database
from app.search import StaticSearchProvider
from app.service import QueueService
from app.browser import MockBrowserController


def setup_app(tmp_path: Path):
    settings.cache_clear()
    db.cache_clear()
    service.cache_clear()
    search_provider.cache_clear()
    browser.cache_clear()
    app.dependency_overrides = {}
    import os
    os.environ['APP_DB_PATH'] = str(tmp_path / 'app.db')
    os.environ['TELEGRAM_ALLOWED_CHAT_IDS'] = '42'
    settings.cache_clear(); db.cache_clear(); service.cache_clear(); search_provider.cache_clear(); browser.cache_clear()
    return TestClient(app)


def test_webhook_preserves_telegram_sender(tmp_path):
    client = setup_app(tmp_path)
    resp = client.post('/telegram/webhook', json={'message': {'message_id': 11, 'text': '/next yellow coldplay', 'from': {'id': 9, 'username': 'tushar'}, 'chat': {'id': 42, 'type': 'group'}}})
    assert resp.status_code == 200
    request_id = resp.json()['request_id']
    job = client.get('/api/worker/jobs/next').json()['job']
    assert job['id'] == request_id
    assert job['user_id'] == 9
    assert job['username'] == 'tushar'


def test_webhook_queue_and_confirm(tmp_path):
    client = setup_app(tmp_path)
    resp = client.post('/telegram/webhook', json={'message': {'message_id': 1, 'text': '/queue perfect', 'from': {'id': 9, 'username': 'tushar'}, 'chat': {'id': 42, 'type': 'group'}}})
    assert resp.status_code == 200
    body = resp.json()
    assert body['ok'] is True
    assert body['request_id'] is not None
    assert body['candidates'] is not None
    confirm = client.post('/api/queue/confirm', json={'request_id': body['request_id'], 'video_id': body['candidates'][0]['video_id']})
    assert confirm.status_code == 200
    assert confirm.json()['ok'] is True


def test_nowplaying_and_skip(tmp_path):
    client = setup_app(tmp_path)
    resp = client.post('/telegram/webhook', json={'message': {'message_id': 1, 'text': '/next yellow coldplay', 'from': {'id': 9, 'username': 'tushar'}, 'chat': {'id': 42, 'type': 'group'}}})
    request_id = resp.json()['request_id']
    client.get('/api/worker/jobs/next')
    client.post(f'/api/worker/jobs/{request_id}/complete')
    skip = client.post('/telegram/webhook', json={'message': {'message_id': 2, 'text': '/skip', 'from': {'id': 9, 'username': 'tushar'}, 'chat': {'id': 42, 'type': 'group'}}})
    assert skip.status_code == 200
    np = client.post('/telegram/webhook', json={'message': {'message_id': 3, 'text': '/nowplaying', 'from': {'id': 9, 'username': 'tushar'}, 'chat': {'id': 42, 'type': 'group'}}})
    assert np.status_code == 200
    assert 'Now playing:' in np.json()['message']


def test_unknown_song_uses_query_candidate_for_extension(tmp_path):
    client = setup_app(tmp_path)
    resp = client.post('/telegram/webhook', json={'message': {'message_id': 1, 'text': '/queue obscure song from group', 'from': {'id': 10, 'username': 'friend'}, 'chat': {'id': 42, 'type': 'group'}}})
    assert resp.status_code == 200
    body = resp.json()
    assert body['ok'] is True
    assert body['candidates'][0]['title'] == 'obscure song from group'
    assert body['candidates'][0]['video_id'].startswith('query-')
    job = client.get('/api/worker/jobs/next').json()['job']
    assert job['query'] == 'obscure song from group'
    assert job['candidate']['title'] == 'obscure song from group'


def test_extension_report_updates_state(tmp_path):
    client = setup_app(tmp_path)
    resp = client.post('/telegram/webhook', json={'message': {'message_id': 1, 'text': '/next husn anuv jain', 'from': {'id': 9, 'username': 'tushar'}, 'chat': {'id': 42, 'type': 'group'}}})
    assert resp.status_code == 200
    job = client.get('/api/worker/jobs/next').json()['job']
    assert job['candidate']['title']
    report = client.post(f"/api/worker/jobs/{job['id']}/report", json={'ok': True, 'detail': 'Play next: Husn', 'worker_id': 'extension', 'now_playing': 'Husn — Anuv Jain', 'action': 'play_next'})
    assert report.status_code == 200
    now_playing = client.get('/api/queue/now-playing')
    assert now_playing.json()['now_playing'] == 'Husn — Anuv Jain'


def test_skip_creates_extension_job_and_report_updates_state(tmp_path):
    client = setup_app(tmp_path)
    resp = client.post('/telegram/webhook', json={'message': {'message_id': 4, 'text': '/skip', 'from': {'id': 9, 'username': 'tushar'}, 'chat': {'id': 42, 'type': 'group'}}})
    assert resp.status_code == 200
    body = resp.json()
    assert body['ok'] is True
    assert body['request_id'] is not None
    assert 'Skip queued' in body['message']

    job = client.get('/api/worker/jobs/next').json()['job']
    assert job['id'] == body['request_id']
    assert job['intent'] == 'skip'
    assert job.get('candidate') is None

    report = client.post(f"/api/worker/jobs/{job['id']}/report", json={'ok': True, 'detail': 'Skipped to: Yellow — Coldplay', 'worker_id': 'extension', 'now_playing': 'Yellow — Coldplay', 'action': 'skip'})
    assert report.status_code == 200
    assert report.json()['ok'] is True
    assert client.get('/api/queue/now-playing').json()['now_playing'] == 'Yellow — Coldplay'


def test_local_worker_complete_handles_skip_job(tmp_path):
    client = setup_app(tmp_path)
    resp = client.post('/telegram/webhook', json={'message': {'message_id': 5, 'text': '/skip', 'from': {'id': 9, 'username': 'tushar'}, 'chat': {'id': 42, 'type': 'group'}}})
    request_id = resp.json()['request_id']
    client.get('/api/worker/jobs/next')

    complete = client.post(f'/api/worker/jobs/{request_id}/complete')
    assert complete.status_code == 200
    assert complete.json()['ok'] is True
    assert 'Skipped' in complete.json()['message']
