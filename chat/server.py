"""Асинхронный WebSocket-сервер AsyncChat."""

import argparse
import asyncio
import logging
import signal
import time
from dataclasses import dataclass, field

from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServerProtocol, serve

from chat.config import validate_nickname, validate_port
from chat.protocol import ChatMessage, decode_message, encode_message


logger = logging.getLogger("chat.server")
MAX_HISTORY = 200
MAX_MESSAGE_SIZE = 16384


@dataclass(eq=False)
class Client:
    """Подключённый пользователь."""

    websocket: WebSocketServerProtocol
    nickname: str


@dataclass
class ChatServer:
    """Управляет подключениями и сообщениями."""

    clients: dict[str, Client] = field(default_factory=dict)
    history: list[ChatMessage] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def record(self, message: ChatMessage) -> None:
        """Сохраняет ограниченную историю."""
        self.history.append(message)
        del self.history[:-MAX_HISTORY]

    async def send(self, websocket: WebSocketServerProtocol,
                   message: ChatMessage) -> bool:
        """Отправляет сообщение одному соединению."""
        try:
            await websocket.send(encode_message(message))
            return True
        except (ConnectionClosed, OSError):
            return False

    async def send_error(self, websocket: WebSocketServerProtocol,
                         text: str) -> None:
        """Отправляет сообщение об ошибке."""
        message = ChatMessage(
            type="error", nickname="server", text=text, timestamp=time.time()
        )
        await self.send(websocket, message)

    async def broadcast(self, message: ChatMessage) -> None:
        """Рассылает сообщение всем зарегистрированным пользователям."""
        async with self.lock:
            clients = list(self.clients.values())

        results = await asyncio.gather(
            *(self.send(client.websocket, message) for client in clients)
        )

        for client, success in zip(clients, results):
            if not success:
                logger.info("Соединение пользователя %s закрыто",
                            client.nickname)

    async def handler(self, websocket: WebSocketServerProtocol) -> None:
        """Обрабатывает одного клиента."""
        client: Client | None = None

        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=30)
            request = decode_message(raw)

            if request.type != "join":
                await self.send_error(websocket, "Первым пакетом должен быть join")
                await websocket.close(code=1008, reason="Join required")
                return

            try:
                validate_nickname(request.nickname)
            except ValueError:
                await self.send_error(websocket, "Недопустимый ник")
                await websocket.close(code=1008, reason="Invalid nickname")
                return

            async with self.lock:
                if request.nickname in self.clients:
                    await self.send_error(websocket, "Этот ник уже занят")
                    await websocket.close(code=1008, reason="Nickname in use")
                    return

                client = Client(websocket, request.nickname)
                self.clients[request.nickname] = client
                history = list(self.history)

            for old_message in history:
                if not await self.send(websocket, old_message):
                    return

            logger.info("%s подключился", client.nickname)

            joined = ChatMessage(
                type="system",
                nickname="server",
                text=f"{client.nickname} вошёл в чат",
                timestamp=time.time(),
            )
            self.record(joined)
            await self.broadcast(joined)

            async for raw in websocket:
                incoming = decode_message(raw)

                if incoming.type == "leave":
                    break

                if incoming.type != "message":
                    await self.send_error(
                        websocket, "Разрешены только message и leave"
                    )
                    continue

                text = incoming.text.strip()
                if not text:
                    continue

                message = ChatMessage(
                    type="message",
                    nickname=client.nickname,
                    text=text,
                    timestamp=time.time(),
                )
                self.record(message)
                await self.broadcast(message)

        except asyncio.TimeoutError:
            await websocket.close(code=1008, reason="Join timeout")
        except ValueError:
            logger.warning("Получено некорректное сообщение")
            await self.send_error(websocket, "Некорректный формат сообщения")
            await websocket.close(code=1008, reason="Invalid message")
        except ConnectionClosed:
            pass
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка соединения")
        finally:
            if client is not None:
                async with self.lock:
                    self.clients.pop(client.nickname, None)

                logger.info("%s отключился", client.nickname)

                left = ChatMessage(
                    type="system",
                    nickname="server",
                    text=f"{client.nickname} вышел из чата",
                    timestamp=time.time(),
                )
                self.record(left)
                await self.broadcast(left)


async def run_server(host: str, port: int) -> None:
    """Запускает сервер до остановки."""
    state = ChatServer()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass

    async with serve(
        state.handler,
        host,
        port,
        max_size=MAX_MESSAGE_SIZE,
        ping_interval=20,
        ping_timeout=20,
    ):
        logger.info("Сервер запущен на %s:%s", host, port)
        print(f"AsyncChat: {host}:{port}. Для остановки нажмите Ctrl+C.")
        try:
            await stop.wait()
        except asyncio.CancelledError:
            pass


def main() -> None:
    """Обрабатывает аргументы командной строки."""
    parser = argparse.ArgumentParser(description="AsyncChat server")
    parser.add_argument(
        "--host", default=os.getenv("CHAT_HOST", "127.0.0.1")
    )
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("CHAT_PORT", "8765"))
    )
    args = parser.parse_args()
    validate_port(args.port)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        asyncio.run(run_server(args.host, args.port))
    except KeyboardInterrupt:
        pass


import os


if __name__ == "__main__":
    main()
