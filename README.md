# AsyncChat

Многопользовательский терминальный чат на Python 3.11+.

## Возможности

- asyncio и WebSocket-сервер.
- TUI на Textual и Rich.
- Pydantic-валидация JSON-протокола.
- Проверка уникальности ников.
- История последних 200 сообщений в памяти.
- Уведомления о входе и выходе.
- Автоматическое переподключение.
- Ctrl+Q — выход, Ctrl+R — переподключение.

## Установка

```bash
python -m pip install -r requirements.txt
```

## Запуск сервера

```bash
python -m chat.server --host 127.0.0.1 --port 8765
```

Для подключений из локальной сети:

```bash
python -m chat.server --host 0.0.0.0 --port 8765
```

## Запуск клиентов

```bash
python -m chat.client --host 127.0.0.1 --port 8765 --nick alice
```

```bash
python -m chat.client --host 127.0.0.1 --port 8765 --nick bob
```

Для других устройств замените 127.0.0.1 на LAN-IP сервера.

## Переменные окружения

```bash
export CHAT_HOST=127.0.0.1
export CHAT_PORT=8765
export CHAT_NICK=alice
```

## Тесты

```bash
python -m pytest -v
```

## Протокол

Каждое сообщение содержит поля type, user, text и ts.
Допустимые типы: join, message, leave, system и error.

История хранится в оперативной памяти и теряется при остановке сервера.
Сообщения во время отключения не гарантируют повторную доставку.

Для публичного развёртывания настройте TLS/WSS и защиту доступа.
