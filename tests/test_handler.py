"""Tests for the Telegram message handler."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from src.bot.handler import MessageHandler


def make_update(user_id: int, chat_id: int, text: str, update_id: int = 1) -> dict:
    """Create a fake Telegram update."""
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "from": {"id": user_id, "first_name": "Test"},
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        },
    }


def test_echo_from_owner() -> None:
    api = AsyncMock()
    handler = MessageHandler(api, owner_id=123)

    update = make_update(user_id=123, chat_id=123, text="hello world")
    asyncio.run(handler.handle_update(update))

    api.send_message.assert_called_once_with(123, "hello world")


def test_ignore_non_owner() -> None:
    api = AsyncMock()
    handler = MessageHandler(api, owner_id=123)

    update = make_update(user_id=999, chat_id=999, text="hello")
    asyncio.run(handler.handle_update(update))

    api.send_message.assert_not_called()


def test_start_command() -> None:
    api = AsyncMock()
    handler = MessageHandler(api, owner_id=123)

    update = make_update(user_id=123, chat_id=123, text="/start")
    asyncio.run(handler.handle_update(update))

    api.send_message.assert_called_once()
    msg = api.send_message.call_args[0][1]
    assert "ActionOS-CLI is running" in msg


def test_help_command() -> None:
    api = AsyncMock()
    handler = MessageHandler(api, owner_id=123)

    update = make_update(user_id=123, chat_id=123, text="/help")
    asyncio.run(handler.handle_update(update))

    api.send_message.assert_called_once()
    msg = api.send_message.call_args[0][1]
    assert "/start" in msg
    assert "/help" in msg
    assert "/clear" in msg
    assert "/status" in msg


def test_clear_command() -> None:
    api = AsyncMock()
    handler = MessageHandler(api, owner_id=123)

    update = make_update(user_id=123, chat_id=123, text="/clear")
    asyncio.run(handler.handle_update(update))

    api.send_message.assert_called_once()
    msg = api.send_message.call_args[0][1]
    assert "Session cleared" in msg


def test_status_command() -> None:
    api = AsyncMock()
    handler = MessageHandler(api, owner_id=123)

    update = make_update(user_id=123, chat_id=123, text="/status")
    asyncio.run(handler.handle_update(update))

    api.send_message.assert_called_once()
    msg = api.send_message.call_args[0][1]
    assert "echo mode" in msg


def test_unknown_command() -> None:
    api = AsyncMock()
    handler = MessageHandler(api, owner_id=123)

    update = make_update(user_id=123, chat_id=123, text="/unknown")
    asyncio.run(handler.handle_update(update))

    api.send_message.assert_called_once()
    msg = api.send_message.call_args[0][1]
    assert "Unknown command" in msg


def test_command_with_bot_suffix() -> None:
    api = AsyncMock()
    handler = MessageHandler(api, owner_id=123)

    update = make_update(user_id=123, chat_id=123, text="/start@MyBot")
    asyncio.run(handler.handle_update(update))

    api.send_message.assert_called_once()
    msg = api.send_message.call_args[0][1]
    assert "ActionOS-CLI is running" in msg


def test_empty_update_ignored() -> None:
    api = AsyncMock()
    handler = MessageHandler(api, owner_id=123)

    asyncio.run(handler.handle_update({"update_id": 1}))
    api.send_message.assert_not_called()
