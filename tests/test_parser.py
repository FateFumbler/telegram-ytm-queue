from app.models import Intent
from app.parser import parse_message


def test_parse_next_command():
    parsed = parse_message('/next blinding lights weeknd')
    assert parsed.intent == Intent.PLAY_NEXT
    assert parsed.query == 'blinding lights weeknd'


def test_parse_unknown_text():
    parsed = parse_message('hello team')
    assert parsed.intent == Intent.UNKNOWN


def test_parse_play_phrase_as_play_next():
    parsed = parse_message('play solo by fred again')
    assert parsed.intent == Intent.PLAY_NEXT
    assert parsed.query == 'solo by fred again'


def test_queue_alias_still_plays_next():
    parsed = parse_message('/queue yellow coldplay')
    assert parsed.intent == Intent.PLAY_NEXT
    assert parsed.query == 'yellow coldplay'
