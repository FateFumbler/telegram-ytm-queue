from __future__ import annotations

from app.models import Intent, ParsedCommand

COMMAND_ALIASES = {
    "/next": Intent.PLAY_NEXT,
    "/play": Intent.PLAY_NEXT,
    "play": Intent.PLAY_NEXT,
    "/queue": Intent.PLAY_NEXT,
    "/add": Intent.PLAY_NEXT,
    "/nowplaying": Intent.NOW_PLAYING,
    "/np": Intent.NOW_PLAYING,
    "/skip": Intent.SKIP,
    "/help": Intent.HELP,
}


def parse_message(text: str) -> ParsedCommand:
    normalized = (text or "").strip()
    if not normalized:
        return ParsedCommand(intent=Intent.UNKNOWN, raw_text=text)
    parts = normalized.split(maxsplit=1)
    head = parts[0].lower()
    tail = parts[1].strip() if len(parts) > 1 else ""
    intent = COMMAND_ALIASES.get(head)
    if intent:
        return ParsedCommand(intent=intent, query=tail, raw_text=text)
    return ParsedCommand(intent=Intent.UNKNOWN, raw_text=text, query=normalized)
