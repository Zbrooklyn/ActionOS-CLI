"""Configuration loader for ActionOS-CLI.

Loads from config/default.toml, with env var overrides for secrets.
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path("config/default.toml")


@dataclass
class TelegramConfig:
    bot_token: str
    owner_id: int
    poll_interval: float = 1.0


@dataclass
class ClaudeConfig:
    cli_path: str = "claude"
    max_turns: int = 5
    max_budget_usd: float = 0.50
    timeout_seconds: int = 120
    default_allowed_tools: list[str] = field(
        default_factory=lambda: ["Read", "Glob", "Grep"]
    )


@dataclass
class StoreConfig:
    db_path: str = "data/actionos.db"


@dataclass
class WorkspaceConfig:
    path: str = "workspace"
    enabled: bool = True


@dataclass
class Config:
    telegram: TelegramConfig
    claude: ClaudeConfig
    store: StoreConfig
    workspace: WorkspaceConfig


def load_config(path: Path = CONFIG_PATH) -> Config:
    """Load configuration from TOML file with env var overrides."""
    raw: dict = {}

    if path.exists():
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    else:
        # Allow running with env vars only
        pass

    tg = raw.get("telegram", {})

    # Env var overrides for secrets
    bot_token = os.environ.get("ACTIONOS_TELEGRAM_BOT_TOKEN", tg.get("bot_token", ""))
    owner_id_str = os.environ.get(
        "ACTIONOS_TELEGRAM_OWNER_ID", str(tg.get("owner_id", 0))
    )

    try:
        owner_id = int(owner_id_str)
    except ValueError:
        print(f"Error: owner_id must be an integer, got '{owner_id_str}'")
        sys.exit(1)

    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        print(
            "Error: Telegram bot token not configured.\n"
            "Either:\n"
            "  1. Copy config/example.toml to config/default.toml and fill in your values\n"
            "  2. Set ACTIONOS_TELEGRAM_BOT_TOKEN environment variable\n"
        )
        sys.exit(1)

    if owner_id == 0:
        print(
            "Error: Telegram owner_id not configured.\n"
            "Message @userinfobot on Telegram to get your user ID.\n"
            "Set it in config/default.toml or ACTIONOS_TELEGRAM_OWNER_ID env var.\n"
        )
        sys.exit(1)

    cl = raw.get("claude", {})
    st = raw.get("store", {})
    ws = raw.get("workspace", {})

    return Config(
        telegram=TelegramConfig(
            bot_token=bot_token,
            owner_id=owner_id,
            poll_interval=tg.get("poll_interval", 1.0),
        ),
        claude=ClaudeConfig(
            cli_path=cl.get("cli_path", "claude"),
            max_turns=cl.get("max_turns", 5),
            max_budget_usd=cl.get("max_budget_usd", 0.50),
            timeout_seconds=cl.get("timeout_seconds", 120),
            default_allowed_tools=cl.get(
                "default_allowed_tools", ["Read", "Glob", "Grep"]
            ),
        ),
        store=StoreConfig(
            db_path=st.get("db_path", "data/actionos.db"),
        ),
        workspace=WorkspaceConfig(
            path=ws.get("path", "workspace"),
            enabled=ws.get("enabled", True),
        ),
    )
