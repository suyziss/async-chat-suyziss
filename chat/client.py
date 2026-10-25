"""Textual TUI-клиент AsyncChat."""

import argparse
import asyncio
import logging
import os
import time
from datetime import datetime
from typing import ClassVar

import websockets
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, RichLog, Static
from websockets.exceptions import ConnectionClosed, WebSocketException

from chat.config import validate_nickname, validate_port
from chat.protocol import ChatMessage, decode_message, encode_message


logger = logging.getLogger("chat.client")


class ChatApp(App[None]):
    """Терминальный интерфейс чата."""

    TITLE = "AsyncChat"
    CSS = """
    Screen {
        layout: vertical;
    }
    #status {
        height: 1;
        padding: 0 1;
        background: #17212b;
        color: #00e5ff;
    }
    #history {
        height: 1fr;
        border: round #334155;
        padding: 0 1;
    }
    #composer {
        dock: bottom;
        height: 3;
        margin: 0 1;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("ctrl+q", "quit", "Выход"),
        ("ctrl+r", "reconnect", "Переподключение"),
    ]

    def __init__(self, host: str, port: int, nickname: str) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.nickname = nickname
        self.connected = False
        self.online = 0
        self.socket = None
        self.connection_task: asyncio.Task[None] | None = None
        self.reconnect_requested = asyncio.Event()
        self.shutdown_requested = False

    def compose(self) -> ComposeResult:
        """Создаёт элементы интерфейса."""
        yield Header()
        yield Static("○ Отключён", id="status")
        yield RichLog(id="history", wrap=True, markup=True)
        yield Input(placeholder="Сообщение… Enter — отправить", id="composer")
        yield Footer()

    async def on_mount(self) -> None:
        """Запускает подключение."""
        self.connection_task = asyncio.create_task(self.connection_loop())

    def show_status(self) -> None:
        """Обновляет индикатор соединения."""
        state = "● Подключён" if self.connected else "○ Отключён"
        self.query_one("#status", Static).update(
            f"{state} | {self.nickname} | Онлайн: {self.online}"
        )

    def add_line(self, message: ChatMessage) -> None:
        """Выводит сообщение в историю."""
        log = self.query_one("#history", RichLog)
        stamp = datetime.fromtimestamp(message.timestamp).strftime("%H:%M:%S")

        if message.type == "system":
            if message.text.endswith("вошёл в чат"):
                self.online += 1
            elif message.text.endswith("вышел из чата"):
                self.online = max(0, self.online - 1)
            self.show_status()
            log.write(f"[yellow][{stamp}] * {message.text}[/yellow]")
        elif message.type == "error":
            log.write(f"[bold red][{stamp}] Ошибка: {message.text}[/bold red]")
        elif message.nickname == self.nickname:
            log.write(f"[bold cyan][{stamp}] Вы: {message.text}[/bold cyan]")
        else:
            log.write(
                f"[bold green][{stamp}] {message.nickname}: {message.text}[/bold green]"
            )

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Отправляет сообщение по Enter."""
        text = event.value.strip()
        event.input.value = ""

        if not text:
            return

        if not self.connected or self.socket is None:
            self.add_line(ChatMessage(
                type="error", nickname="client",
                text="Нет соединения. Ожидайте переподключения.",
                timestamp=time.time(),
            ))
            return

        message = ChatMessage(
            type="message", nickname=self.nickname, text=text, timestamp=time.time()
        )

        try:
            await self.socket.send(encode_message(message))
        except (ConnectionClosed, OSError, WebSocketException):
            self.connected = False
            self.show_status()

    async def action_reconnect(self) -> None:
        """Принудительно переподключается."""
        self.reconnect_requested.set()
        if self.socket is not None:
            await self.socket.close()

    async def connection_loop(self) -> None:
        """Подключается с автоматическим повтором."""
        delay = 1.0

        while not self.shutdown_requested:
            try:
                self.show_status()

                async with websockets.connect(
                    f"ws://{self.host}:{self.port}",
                    open_timeout=10,
                    close_timeout=3,
                    max_size=16384,
                ) as socket:
                    self.socket = socket
                    await socket.send(encode_message(ChatMessage(
                        type="join", nickname=self.nickname, text="", timestamp=time.time()
                    )))

                    self.connected = True
                    self.reconnect_requested.clear()
                    self.show_status()
                    delay = 1.0

                    async for raw in socket:
                        try:
                            message = decode_message(raw)
                        except ValueError:
                            continue

                        self.add_line(message)

                        if message.type == "error" and (
                            "занят" in message.text.lower()
                            or "недопустимый ник" in message.text.lower()
                        ):
                            self.shutdown_requested = True
                            self.exit()
                            return

            except asyncio.CancelledError:
                raise
            except (ConnectionRefusedError, OSError, WebSocketException) as exc:
                self.add_line(ChatMessage(
                    type="error", nickname="client",
                    text=f"Соединение недоступно: {type(exc).__name__}",
                    timestamp=time.time(),
                ))
            except Exception:
                logger.exception("Ошибка клиента")
            finally:
                self.connected = False
                self.socket = None
                self.show_status()

            if self.shutdown_requested:
                break

            self.add_line(ChatMessage(
                type="system", nickname="client",
                text=f"Переподключение через {delay:.0f} с…",
                timestamp=time.time(),
            ))

            try:
                await asyncio.wait_for(
                    self.reconnect_requested.wait(), timeout=delay
                )
            except asyncio.TimeoutError:
                pass

            self.reconnect_requested.clear()
            delay = min(delay * 2, 30.0)

    async def on_unmount(self) -> None:
        """Закрывает соединение при выходе."""
        self.shutdown_requested = True

        if self.socket is not None:
            try:
                await self.socket.send(encode_message(ChatMessage(
                    type="leave", nickname=self.nickname, text="", timestamp=time.time()
                )))
                await self.socket.close()
            except Exception:
                pass

        if self.connection_task is not None:
            self.connection_task.cancel()
            try:
                await self.connection_task
            except asyncio.CancelledError:
                pass


def main() -> None:
    """Запускает TUI-клиент."""
    parser = argparse.ArgumentParser(description="AsyncChat client")
    parser.add_argument("--host", default=os.getenv("CHAT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("CHAT_PORT", "8765")))
    parser.add_argument("--nick", default=os.getenv("CHAT_NICK", "guest"))
    args = parser.parse_args()

    validate_port(args.port)
    validate_nickname(args.nick)

    logging.basicConfig(level=logging.INFO)
    ChatApp(args.host, args.port, args.nick).run()


if __name__ == "__main__":
    main()
