# Config

Configuration file schema for ActionOS-CLI. Single TOML file at `config/default.toml`.

## File location and permissions

```
config/default.toml     # Main config (chmod 600 — contains bot token)
config/example.toml     # Example config checked into git (no secrets)
```

The config file should be `chmod 600` (owner read/write only) because it contains the Telegram bot token.

## Full schema

```toml
# ActionOS-CLI configuration

[telegram]
# Bot token from BotFather (required)
bot_token = "123456:ABC-DEF..."

# Your Telegram user ID (required). Only this user can interact with the bot.
# Get it by messaging @userinfobot on Telegram.
owner_id = 123456789

# Polling interval in seconds
poll_interval = 1.0

[claude]
# Path to Claude CLI binary. Defaults to "claude" (found via PATH).
cli_path = "claude"

# Default model. Omit to use whatever Claude CLI is configured for.
# model = "sonnet"

# Default max turns per invocation
max_turns = 5

# Default max budget per invocation (USD)
max_budget_usd = 0.50

# Default allowed tools (read-only set)
default_allowed_tools = ["Read", "Glob", "Grep"]

# Escalated tools (available after approval)
escalated_allowed_tools = ["Read", "Write", "Edit", "Glob", "Grep"]

# Build mode tools (available after approval for dev tasks)
build_allowed_tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]

# Subprocess timeout in seconds
timeout_seconds = 120

[store]
# Path to SQLite database file
db_path = "data/actionos.db"

[skills]
# Path to builtin skills directory
builtin_path = "skills/builtin"

# Path to custom (user-approved) skills directory
custom_path = "skills/custom"

# Skill execution timeout in seconds
skill_timeout_seconds = 30

# Max consecutive failures before auto-disabling a skill
max_failures = 3

[sandbox]
# Docker image for sandboxed skill execution
image = "actionos-sandbox"

# Resource limits
memory = "256m"
cpus = "0.5"

[jobs]
# Max jobs per minute globally (rate limiting)
max_per_minute = 10

# Min interval between jobs in same thread (seconds)
thread_cooldown = 2.0

# Max retry attempts for transient failures
max_retries = 2

# Retry backoff intervals (seconds)
retry_backoff = [5, 15]

[approvals]
# Approval timeout in minutes
timeout_minutes = 10

[alerts]
# Alert if a single job costs more than this (USD)
job_cost_threshold = 0.50

# Alert if daily total exceeds this (USD)
daily_cost_threshold = 5.00

[dashboard]
# Web dashboard port (0 = disabled)
port = 8080

# Bind address
host = "127.0.0.1"
```

## Environment variable overrides

For deployment scenarios where you don't want secrets in a file:

```bash
ACTIONOS_TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
ACTIONOS_TELEGRAM_OWNER_ID=123456789
```

Environment variables take precedence over the config file. Only `bot_token` and `owner_id` have env var overrides — everything else must be in the config file.

**Note:** We prefer the config file over environment variables for most settings because environment variables leak to subprocesses (including Claude CLI and skill executors). The bot token should ideally not be in env vars.

## Config loading order

1. Load `config/default.toml`.
2. Override with environment variables (if set).
3. Validate required fields (`telegram.bot_token`, `telegram.owner_id`).
4. Apply defaults for missing optional fields.
5. If config file doesn't exist, print setup instructions and exit.

## Example config (checked into git)

`config/example.toml` ships with the repo as a template:

```toml
# Copy this file to config/default.toml and fill in your values.
# chmod 600 config/default.toml

[telegram]
bot_token = "YOUR_BOT_TOKEN_HERE"
owner_id = 0  # Your Telegram user ID

[claude]
max_turns = 5
max_budget_usd = 0.50
timeout_seconds = 120

[store]
db_path = "data/actionos.db"
```

## Gitignore

The following should be in `.gitignore`:

```
config/default.toml    # Contains bot token
data/                  # Database and user data
skills/custom/         # User-approved skills (not shared)
```
