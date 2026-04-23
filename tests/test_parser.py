from app.models import Intent
from app.parser import parse_message


def test_parse_next_command():
    parsed = parse_message('/next blinding lights weeknd')
    assert parsed.intent == Intent.PLAY_NEXT
    assert parsed.query == 'blinding lights weeknd'


def test_parse_unknown_text():
    parsed = parse_message('hello team')
    assert parsed.intent == Intent.UNKNOWN
