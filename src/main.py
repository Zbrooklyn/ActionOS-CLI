"""ActionOS-CLI entry point.

Loads config, starts the Telegram polling loop, handles graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from src.bot.handler import MessageHandler
from src.bot.polling import run_polling
from src.bot.telegram import TelegramAPI
from src.config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("actionos")


async def async_main() -> None:
    config = load_config()

    api = TelegramAPI(config.telegram.bot_token)

    # Verify bot token works
    try:
        me = await api.get_me()
        logger.info("Bot connected: @%s (%s)", me.get("username"), me.get("first_name"))
    except Exception:
        logger.exception("Failed to connect to Telegram. Check your bot_token.")
        await api.close()
        sys.exit(1)

    handler = MessageHandler(api, config.telegram.owner_id)

    # Graceful shutdown on SIGTERM/SIGINT
    loop = asyncio.get_running_loop()
    polling_task = asyncio.create_task(
        run_polling(api, handler, config.telegram.poll_interval)
    )

    def shutdown(sig: signal.Signals) -> None:
        logger.info("Received %s, shutting down...", sig.name)
        polling_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown, sig)

    try:
        await polling_task
    except asyncio.CancelledError:
        pass
    finally:
        await api.close()
        logger.info("Shutdown complete.")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
