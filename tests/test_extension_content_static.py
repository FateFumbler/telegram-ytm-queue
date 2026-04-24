from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT_JS = ROOT / "extension" / "content.js"


def test_content_script_uses_non_navigating_queue_api_for_queue_jobs():
    source = CONTENT_JS.read_text()

    assert "/youtubei/v1/search" in source
    assert "/youtubei/v1/music/get_queue" in source
    assert "queueInsertPosition: 'INSERT_AFTER_CURRENT_VIDEO'" in source
    assert "location.href = url" not in source


def test_content_script_verifies_up_next_insertion_before_success():
    source = CONTENT_JS.read_text()

    assert "verifyQueueInsertion" in source
    assert "ytmusic-player-queue-item" in source
    assert "throw new Error('Could not verify queue insertion" in source


def test_content_script_inserts_returned_queue_items_into_live_store():
    source = CONTENT_JS.read_text()

    assert "queueDatas" in source
    assert "queueData.content" in source
    assert "type: 'ADD_ITEMS'" in source
    assert "selectedItemIndex" in source
    assert "shouldAssignIds: true" in source
