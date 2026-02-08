# ActionOS-CLI

**OpenClaw Lite — a personal AI assistant on Telegram, powered by Claude CLI.**

No API keys for Claude. No spoofing. No marketplace. Just a clean loop:
Telegram message in, Claude CLI subprocess, structured reply out.

---

## What this is

A lightweight, always-on Telegram assistant that routes your messages through Claude CLI's native auth (your existing subscription). It borrows the good parts of OpenClaw's architecture — gateway, job orchestration, modular skills — without the sprawl, the public skill marketplace, or the unrestricted shell access.

Think of it as 5 parts:

| # | Part | Role |
|---|------|------|
| 1 | **Telegram Ingress** | Receives messages and approval buttons |
| 2 | **State Store (SQLite)** | Threads, messages, jobs, tool calls, approvals, skills |
| 3 | **Orchestrator / Worker** | Turns messages into jobs, dedupes, retries, rate-limits |
| 4 | **Claude CLI Runner** | Subprocess wrapper — `claude --print --output-format json --resume` |
| 5 | **Skills Layer** | Allowlisted tools, no auto-install, approval-gated |

## Core principles

- **No Claude API key.** All inference goes through `claude` CLI using your existing OAuth login. Zero token billing, zero key management.
- **No spoofing.** Every reply is either genuinely from a Claude CLI run or clearly labeled as a system message. No cached replies pretending to be live inference. No hidden prompts. Full audit trail.
- **No auto-install.** Skills are proposed by the agent, reviewed by you, activated only with your explicit approval.
- **No unrestricted shell.** Default tools are read-only. Write/execute requires approval. Risky operations run sandboxed.
- **Telegram is the only UI.** A minimal web dashboard comes later for jobs/logs/approvals, but Telegram is the primary interface.

## How it works

```
You (Telegram)
  |
  v
Telegram Bot (polling, no public IP needed)
  |
  v
Orchestrator (job queue + dedup + rate limit + approval gate)
  |
  v
claude --print --output-format json --resume <session_id>
  |  (first message omits --resume; session_id captured from response)
  v
Parse JSON response --> store in SQLite --> reply to Telegram
  |
  v (if skill_call detected)
Orchestrator executes skill --> feeds result back via --resume
```

Each Telegram thread maps to a Claude CLI session. The `session_id` comes from Claude CLI's JSON response on first invocation; subsequent messages use `--resume` for continuity. Claude is the brain (decides what to do), the orchestrator is the hands (executes skills, manages approvals).

## Folder structure

```
actionos-cli/
  src/
    bot/              # Telegram bot (polling, message handling)
    orchestrator/     # Job queue, worker loop, dedup, locks
    runner/           # Claude CLI subprocess wrapper
    skills/           # Skill loader, manifest parser, execution
    store/            # SQLite schema, migrations, queries
    dashboard/        # (later) Minimal web UI for jobs/approvals
  skills/
    builtin/          # Safe defaults: notes, reminders, file-search
    custom/           # User-approved skills land here
  config/
    default.toml      # Bot token, allowed tools, limits, paths
  docs/               # Design documentation (you are here)
  tests/
  README.md
```

## Documentation

| Doc | What it covers |
|-----|----------------|
| [Architecture](docs/architecture.md) | System diagram, component breakdown, data flow |
| [CLI Contract](docs/cli-contract.md) | Claude CLI flags, invocation patterns, JSON response parsing |
| [Skills Manifest](docs/skills-manifest.md) | Skill format, orchestrator-as-executor model, approval flow |
| [Telegram UX](docs/telegram-ux.md) | Commands, buttons, message formats, two-pass approval UX |
| [Schema](docs/schema.md) | SQLite tables, relationships, migration strategy |
| [Security](docs/security.md) | Hard rules, threat model, what we refuse to do |
| [Config](docs/config.md) | TOML config schema, defaults, environment overrides |
| [Build Phases](docs/build-phases.md) | Implementation order, milestones, definition of done |
| [References](docs/references.md) | OpenClaw, LiteClaw, and Telegram+Claude bot analysis |

## Build order (summary)

1. Telegram bot — receive + send messages (polling)
2. SQLite schema — threads, messages, jobs, tool_calls, approvals
3. Claude CLI wrapper — single-shot first, then session continuity
4. Approval gate — risky action approval flow via Telegram buttons
5. Job runner — dedup, locks, retry, rate-limit
6. Safe tools v1 — notes, reminders, file search
7. Skills folder — manifest loader, propose/approve/activate cycle
8. Web dashboard — jobs + logs + approvals (read-only)

## License

MIT
