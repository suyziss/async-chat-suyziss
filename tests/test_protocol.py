import json
import pytest

from chat.protocol import ChatMessage, create_message, encode_message, decode_message


def test_create_message():
    message = create_message("message", "Alex", "Привет")
    assert message.type == "message"
    assert message.nickname == "Alex"
    assert message.text == "Привет"


def test_encode_message():
    message = create_message("message", "Alex", "Привет")
    data = json.loads(encode_message(message))
    assert data["nickname"] == "Alex"
    assert data["text"] == "Привет"


def test_decode_message():
    raw = json.dumps({
        "type": "message",
        "nickname": "Alex",
        "text": "Hello",
        "timestamp": 123.0,
    })
    message = decode_message(raw)
    assert message.nickname == "Alex"
    assert message.text == "Hello"
    assert message.timestamp == 123.0


def test_unicode_message():
    message = create_message("message", "Тест", "Привет 👋")
    decoded = decode_message(encode_message(message))
    assert decoded.text == "Привет 👋"


def test_invalid_json():
    with pytest.raises(ValueError):
        decode_message("{invalid json")


def test_non_object_json():
    with pytest.raises(ValueError):
        decode_message("[]")


def test_missing_fields():
    with pytest.raises(ValueError):
        decode_message('{"type":"message"}')


def test_invalid_type():
    raw = json.dumps({
        "type": "unknown",
        "nickname": "Alex",
        "text": "Hello",
        "timestamp": 123.0,
    })
    with pytest.raises(ValueError):
        decode_message(raw)


def test_invalid_nickname():
    with pytest.raises(ValueError):
        create_message("message", "A" * 33, "Hello")


def test_invalid_message_type():
    with pytest.raises(ValueError):
        create_message("unknown", "Alex", "Hello")
