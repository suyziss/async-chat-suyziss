"""Конфигурация AsyncChat."""

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChatConfig:
    """Настройки подключения."""

    host: str = "127.0.0.1"
    port: int = 8765
    nickname: str = "guest"

    @classmethod
    def from_env(cls) -> "ChatConfig":
        """Читает настройки из переменных окружения."""
        host = os.getenv("CHAT_HOST", "127.0.0.1")
        port = int(os.getenv("CHAT_PORT", "8765"))
        nickname = os.getenv("CHAT_NICK", "guest")

        if not host.strip():
            raise ValueError("Адрес сервера не может быть пустым")

        validate_port(port)
        validate_nickname(nickname)

        return cls(host=host, port=port, nickname=nickname)


def validate_port(port: int) -> None:
    """Проверяет диапазон TCP-порта."""
    if not 1 <= port <= 65535:
        raise ValueError("Порт должен быть от 1 до 65535")


def validate_nickname(nickname: str) -> None:
    """Проверяет допустимые символы ника."""
    if not re.fullmatch(r"[A-Za-zА-Яа-яЁё0-9_-]{1,32}", nickname):
        raise ValueError(
            "Ник: 1–32 символа, буквы, цифры, _ или -"
        )
