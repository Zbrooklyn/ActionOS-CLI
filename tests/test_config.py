"""Tests for the config loader."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from src.config import load_config


def test_load_from_toml() -> None:
    content = b"""
[telegram]
bot_token = "test-token-123"
owner_id = 42
poll_interval = 2.0

[claude]
max_turns = 10
max_budget_usd = 1.00

[store]
db_path = "test.db"
"""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    try:
        cfg = load_config(path)
        assert cfg.telegram.bot_token == "test-token-123"
        assert cfg.telegram.owner_id == 42
        assert cfg.telegram.poll_interval == 2.0
        assert cfg.claude.max_turns == 10
        assert cfg.claude.max_budget_usd == 1.00
        assert cfg.store.db_path == "test.db"
    finally:
        path.unlink()


def test_env_var_override(monkeypatch) -> None:
    content = b"""
[telegram]
bot_token = "file-token"
owner_id = 1
"""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    try:
        monkeypatch.setenv("ACTIONOS_TELEGRAM_BOT_TOKEN", "env-token")
        monkeypatch.setenv("ACTIONOS_TELEGRAM_OWNER_ID", "99")
        cfg = load_config(path)
        assert cfg.telegram.bot_token == "env-token"
        assert cfg.telegram.owner_id == 99
    finally:
        path.unlink()


def test_defaults() -> None:
    content = b"""
[telegram]
bot_token = "test-token"
owner_id = 1
"""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    try:
        cfg = load_config(path)
        assert cfg.claude.cli_path == "claude"
        assert cfg.claude.max_turns == 5
        assert cfg.claude.max_budget_usd == 0.50
        assert cfg.claude.timeout_seconds == 120
        assert cfg.claude.default_allowed_tools == ["Read", "Glob", "Grep"]
        assert cfg.store.db_path == "data/actionos.db"
        assert cfg.workspace.path == "workspace"
        assert cfg.workspace.enabled is True
    finally:
        path.unlink()
