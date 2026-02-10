"""Long-polling loop for the Telegram bot.

Polls getUpdates with a long timeout, dispatches to handler.
Runs indefinitely until cancelled.
"""

from __future__ import annotations

import asyncio
import logging

from src.bot.handler import MessageHandler
from src.bot.telegram import TelegramAPI

logger = logging.getLogger(__name__)


async def run_polling(api: TelegramAPI, handler: MessageHandler, poll_interval: float = 1.0) -> None:
    """Run the long-polling loop. Blocks until cancelled."""
    offset: int | None = None
    logger.info("Polling loop started")

    while True:
        try:
            updates = await api.get_updates(offset=offset, timeout=25)

            for update in updates:
                update_id = update.get("update_id", 0)
                try:
                    await handler.handle_update(update)
                except Exception:
                    logger.exception("Error handling update %s", update_id)

                # Move offset past this update so we don't re-process it
                offset = update_id + 1

        except asyncio.CancelledError:
            logger.info("Polling loop cancelled")
            raise
        except Exception:
            logger.exception("Polling error, retrying in %.1fs", poll_interval)
            await asyncio.sleep(poll_interval)
