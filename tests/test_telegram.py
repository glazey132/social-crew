import pytest

from tools.telegram import TelegramClient


def test_parse_callback_accepts_valid_inputs():
    client = TelegramClient(bot_token="", chat_id="")
    decision, clip_id = client.parse_callback("approve clip_123")
    assert decision == "approve"
    assert clip_id == "clip_123"


def test_parse_callback_rejects_invalid_inputs():
    client = TelegramClient(bot_token="", chat_id="")
    with pytest.raises(ValueError):
        client.parse_callback("not-valid")

