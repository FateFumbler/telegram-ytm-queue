# Architecture

## Production-ish shape

- Telegram webhook server (FastAPI)
- SQLite persistence for requests/actions/state
- Local worker polling backend for jobs
- Search provider abstraction (`StaticSearchProvider` now, `ytmusicapi` later)
- Browser controller abstraction (`MockBrowserController` now, Playwright or extension later)
- Chrome extension bridge for browser-native queue control

## Request lifecycle

1. Telegram `/next some song`
2. Parse command
3. Search top candidates
4. If high confidence => mark ready
5. If ambiguous => save top 3, wait for confirmation
6. Worker claims ready job
7. Browser controller executes queue action
8. Backend records result

## Phase mapping

### Phase 1
Implemented in backend + worker with mock browser controller.

### Phase 2
Implemented with candidate confirmation, dedupe, skip, now playing, reconnect-safe pending queue.

### Phase 3
Extension scaffold added. Content script is the integration point to operate an active `music.youtube.com` tab.
