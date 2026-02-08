"""Telegram Bot API client using httpx.

Handles polling, sending messages, and callback queries.
Thin wrapper — no framework, just the API calls we need.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.telegram.org/bot{token}"


class TelegramAPI:
    """Low-level Telegram Bot API client."""

    def __init__(self, token: str, timeout: float = 30.0) -> None:
        self._base = BASE_URL.format(token=token)
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(self, method: str, **params: Any) -> dict:
        """Call a Telegram Bot API method."""
        # Filter out None values
        data = {k: v for k, v in params.items() if v is not None}
        url = f"{self._base}/{method}"

        try:
            resp = await self._client.post(url, json=data)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("Telegram API error: %s %s — %s", method, e.response.status_code, e.response.text)
            raise
        except httpx.RequestError as e:
            logger.error("Telegram request error: %s — %s", method, e)
            raise

        result = resp.json()
        if not result.get("ok"):
            logger.error("Telegram API returned not ok: %s", result)
            raise RuntimeError(f"Telegram API error: {result.get('description', 'unknown')}")

        return result.get("result", {})

    async def get_me(self) -> dict:
        """Get bot info. Useful as a connectivity/auth check."""
        return await self._call("getMe")

    async def get_updates(self, offset: int | None = None, timeout: int = 25) -> list[dict]:
        """Long-poll for updates."""
        return await self._call("getUpdates", offset=offset, timeout=timeout)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        """Send a text message."""
        return await self._call(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    async def send_chat_action(self, chat_id: int, action: str = "typing") -> bool:
        """Send a chat action (e.g. 'typing' indicator)."""
        return await self._call("sendChatAction", chat_id=chat_id, action=action)
