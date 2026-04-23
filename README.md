# Telegram YTM Queue

Telegram group -> backend -> local worker or browser extension -> YouTube Music queue controller.

## What is now real

### Real browser execution (Phase 3)
- MV3 Chrome extension polls the backend only when a `music.youtube.com` tab exists
- Content script opens YouTube Music search results, ranks visible result rows, opens the action menu, and clicks:
  - `Play next` for `/next`
  - `Add to queue` for `/queue` or `/add`
- Extension reports success/failure and current now-playing state back to the backend

### Real search path (Phase 2)
- `ytmusicapi` is supported and installed in the project venv
- If `YTMUSIC_HEADERS_PATH` points to a valid auth headers file, backend search uses live YouTube Music search
- If auth is missing or invalid, backend falls back safely to the static provider

## Project status

### Phase 1
- Telegram webhook intake with `/next`, `/queue`, `/add`, `/nowplaying`, `/skip`
- SQLite persistence
- Local worker polling + job execution
- Search provider abstraction with deterministic mock provider and optional `ytmusicapi`
- Browser controller abstraction with a mock controller and Playwright-ready interface

### Phase 2
- Inline disambiguation flow via callback payloads
- Dedupe window
- Pending jobs + reconnect-safe worker polling
- `now playing` state tracking and `skip`

### Phase 3
- MV3 Chrome extension scaffold upgraded into the real browser execution path
- Extension sync endpoints for queue execution results and now-playing state
- Content script has real DOM automation for search result targeting and action menu clicks

## Quick start

```bash
cd /home/fate/.openclaw/workspace/projects/telegram-ytm-queue
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev,ytmusic]
uvicorn app.main:app --reload --port 8015
```

Run tests:

```bash
source .venv/bin/activate
pytest
```

## Real YouTube Music search setup

1. Open YouTube Music in Brave or another Chromium browser and sign in.
2. Export your request headers/cookies using `ytmusicapi`'s auth export flow.
   Typical output is a JSON file like `browser.json`.
3. Set:

```bash
export YTMUSIC_HEADERS_PATH=/absolute/path/to/browser.json
```

4. Restart the backend.

Health check will show the active provider:

```bash
curl http://127.0.0.1:8015/healthz
```

If auth is good, `search_provider` will be `ytmusicapi`.
Otherwise it falls back to `static`.

## Real browser execution setup

1. Keep a `music.youtube.com` tab open in Brave or another Chromium browser.
2. Load the unpacked extension from `extension/`. In Brave, open `brave://extensions`, enable **Developer mode**, then **Load unpacked**.
3. Start the backend on port `8015`.
4. Send `/next <song>` or `/queue <song>` in Telegram.

The extension will:
- sync the current now playing state to the backend
- poll for ready jobs
- execute them in the active YT Music tab
- report the result back

## Commands

- `/next <song>` → search and Play next
- `/queue <song>` → search and Add to queue
- `/add <song>` → alias for queue
- `/nowplaying` → returns the latest synced playback state
- `/skip` → queues a browser-extension skip action against the active YT Music tab

## Env

- `APP_DB_PATH` default: `./data/app.db`
- `BOT_TOKEN` optional for Telegram send-back integration
- `TELEGRAM_ALLOWED_CHAT_IDS` comma-separated allowlist
- `YTMUSIC_BROWSER_MODE` one of `mock`, `playwright`, `extension`
- `YTMUSIC_HEADERS_PATH` path to `ytmusicapi` auth headers JSON
- `DEDUP_WINDOW_SECONDS` default `120`

## Layout

- `app/` backend + domain logic
- `worker/` local worker entrypoint
- `extension/` MV3 extension
- `tests/` unit + API coverage
- `docs/` architecture and extension notes

## Notes

- The extension path is now the preferred real execution path.
- The Playwright controller remains a secondary option if you want a pure local-worker browser lane later.
- `skip` now uses the same extension job/report path as queue actions when invoked from Telegram.
