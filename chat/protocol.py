import json
import time
from dataclasses import dataclass
from typing import Literal

MessageType = Literal["join", "message", "leave", "system", "error"]


@dataclass
class ChatMessage:
    type: MessageType
    nickname: str
    text: str
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "nickname": self.nickname,
            "text": self.text,
            "timestamp": self.timestamp,
        }


def create_message(
    message_type: MessageType,
    nickname: str = "",
    text: str = "",
) -> ChatMessage:
    if message_type not in {"join", "message", "leave", "system", "error"}:
        raise ValueError("Invalid message type")

    if not isinstance(nickname, str) or not isinstance(text, str):
        raise ValueError("Nickname and text must be strings")

    if any(ord(char) < 32 and char not in "\t" for char in nickname + text):
        raise ValueError("Control characters are not allowed")

    if len(nickname) > 32:
        raise ValueError("Nickname is too long")

    if len(text) > 4000:
        raise ValueError("Message is too long")

    return ChatMessage(
        type=message_type,
        nickname=nickname,
        text=text,
        timestamp=time.time(),
    )


def encode_message(message: ChatMessage) -> str:
    return json.dumps(message.to_dict(), ensure_ascii=False)


def decode_message(raw: str) -> ChatMessage:
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Message must be a JSON object")

        required = {"type", "nickname", "text", "timestamp"}
        if not required.issubset(data):
            raise ValueError("Missing required fields")

        if data["type"] not in {"join", "message", "leave", "system", "error"}:
            raise ValueError("Invalid message type")

        if not isinstance(data["nickname"], str):
            raise ValueError("Nickname must be a string")

        if not isinstance(data["text"], str):
            raise ValueError("Text must be a string")

        if not isinstance(data["timestamp"], (int, float)):
            raise ValueError("Timestamp must be numeric")

        return ChatMessage(
            type=data["type"],
            nickname=data["nickname"],
            text=data["text"],
            timestamp=float(data["timestamp"]),
        )
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        raise ValueError(f"Invalid message: {exc}") from exc
