"""Message handler for the Telegram bot.

Processes incoming updates: validates user, handles commands, echoes messages.
Phase 1 is echo-only. Phase 3 will replace echo with Claude CLI invocation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.bot.telegram import TelegramAPI

logger = logging.getLogger(__name__)

# Commands that the bot handles
COMMANDS = {
    "/start": "Welcome message and status check",
    "/help": "List available commands",
    "/clear": "Start a new session (Phase 3)",
    "/status": "Show job queue status (Phase 2)",
}


class MessageHandler:
    """Handles incoming Telegram updates."""

    def __init__(self, api: TelegramAPI, owner_id: int) -> None:
        self._api = api
        self._owner_id = owner_id

    async def handle_update(self, update: dict) -> None:
        """Process a single update from Telegram."""
        message = update.get("message")
        if not message:
            return

        user = message.get("from", {})
        user_id = user.get("id")
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")

        if not chat_id:
            return

        # Single-user lockdown: silently ignore messages from other users
        if user_id != self._owner_id:
            logger.debug("Ignored message from user %s (not owner)", user_id)
            return

        # Handle commands
        if text.startswith("/"):
            await self._handle_command(chat_id, text)
        elif text:
            # Phase 1: echo. Phase 3 will route to Claude CLI.
            await self._handle_message(chat_id, text)

    async def _handle_command(self, chat_id: int, text: str) -> None:
        """Route a command to its handler."""
        command = text.split()[0].lower()

        # Strip @botname suffix (e.g. /start@MyBot)
        if "@" in command:
            command = command.split("@")[0]

        if command == "/start":
            await self._cmd_start(chat_id)
        elif command == "/help":
            await self._cmd_help(chat_id)
        elif command == "/clear":
            await self._cmd_clear(chat_id)
        elif command == "/status":
            await self._cmd_status(chat_id)
        else:
            await self._api.send_message(
                chat_id, f"[System] Unknown command: {command}. Use /help to see available commands."
            )

    async def _handle_message(self, chat_id: int, text: str) -> None:
        """Handle a regular text message. Phase 1: echo it back."""
        await self._api.send_message(chat_id, text)

    async def _cmd_start(self, chat_id: int) -> None:
        """Welcome message with basic status."""
        lines = [
            "ActionOS-CLI is running.",
            "",
            "Send me a message and I'll echo it back.",
            "Use /help to see available commands.",
            "",
            "Phase 1: Echo mode (Telegram integration verified).",
        ]
        await self._api.send_message(chat_id, "\n".join(lines))

    async def _cmd_help(self, chat_id: int) -> None:
        """List available commands."""
        lines = ["Available commands:", ""]
        for cmd, desc in COMMANDS.items():
            lines.append(f"{cmd} - {desc}")
        await self._api.send_message(chat_id, "\n".join(lines))

    async def _cmd_clear(self, chat_id: int) -> None:
        """Clear session. No-op in Phase 1."""
        await self._api.send_message(
            chat_id, "[System] Session cleared. (No active session in echo mode.)"
        )

    async def _cmd_status(self, chat_id: int) -> None:
        """Show status. Minimal in Phase 1."""
        await self._api.send_message(
            chat_id, "[System] Status: Running (echo mode). No jobs in queue."
        )
