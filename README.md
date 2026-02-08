# ActionOS-CLI

**OpenClaw Lite — a personal AI assistant on Telegram, powered by official AI CLIs.**

No spoofing. No marketplace. Compliant auth for all three CLIs.
Telegram message in, smart CLI routing, structured reply out.

---

## What this is

A lightweight, always-on Telegram assistant that routes your messages through official AI CLI tools (Claude Code, Gemini CLI, ChatGPT Codex CLI) using each provider's officially sanctioned automation auth — no spoofing, no gray areas. It borrows the good parts of OpenClaw's architecture — gateway, job orchestration, modular skills — without the sprawl, the public skill marketplace, or the unrestricted shell access. Smart routing picks the best CLI for each task type.

Think of it as 5 parts:

| # | Part | Role |
|---|------|------|
| 1 | **Telegram Ingress** | Receives messages and approval buttons |
| 2 | **State Store (SQLite)** | Threads, messages, jobs, tool calls, approvals, skills |
| 3 | **Orchestrator / Worker** | Turns messages into jobs, dedupes, retries, rate-limits |
| 4 | **CLI Runner** | Subprocess wrapper — Claude first, Gemini + Codex later |
| 5 | **Skills Layer** | Allowlisted tools, no auto-install, approval-gated |

## Core principles

- **Compliant auth for every CLI.** Gemini: service accounts (Google recommends for CI). Codex: API key + `codex exec` (first-class automation). Claude: API key (explicitly carved out from automation ban). Zero gray areas. See [Policy](docs/policy.md).
- **Smart routing.** The orchestrator picks the best CLI for each task — Claude for quality-critical coding, Codex for speed and security, Gemini for research and free-tier volume. See [CLI Comparison](docs/cli-comparison.md).
- **No spoofing.** Every reply is genuinely from a CLI run or clearly labeled as a system message. No cached replies pretending to be live inference. No hidden prompts. No bypassed permission systems. Full audit trail.
- **No auto-install.** Skills are proposed by the agent, reviewed by you, activated only with your explicit approval.
- **No unrestricted shell.** Default tools are read-only. Write/execute requires approval. Risky operations run sandboxed.
- **Telegram + Dashboard.** Telegram is the primary interface. A full dashboard (Kanban, analytics, approvals) comes later.

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
  workspace/
    SOUL.md           # Core personality and values
    SOUL.dev.md       # Dev mode personality (builder mindset)
    IDENTITY.md       # Agent identity card (name, role, platform)
    IDENTITY.dev.md   # Dev mode identity (expanded role)
    AGENTS.md         # Operations manual (memory, safety, output)
    AGENTS.dev.md     # Dev mode operations (skill building, git)
    USER.md           # Evolving profile of the human
    MEMORY.md         # Curated long-term memory
    TOOLS.md          # Environment notes (machines, paths, services)
    BOOT.md           # Startup checklist + mode switching
    BOOTSTRAP.md      # First-run onboarding (used once, then deleted)
    HEARTBEAT.md      # Cron/heartbeat task configuration
    memory/           # Raw daily conversation logs
  skills/
    builtin/          # Safe defaults: notes, reminders, file-search
    custom/           # User-approved skills land here
  config/
    default.toml      # Bot token, allowed tools, limits, paths
  docs/               # Design documentation
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
| [CLI Comparison](docs/cli-comparison.md) | Claude vs Gemini vs Codex: benchmarks, strengths, routing table |
| [Workspace](docs/workspace.md) | Prompt templates (SOUL, USER, MEMORY, BOOT), OpenClaw patterns |
| [Config](docs/config.md) | TOML config schema, defaults, environment overrides |
| [Build Phases](docs/build-phases.md) | Implementation order, milestones, definition of done |
| [References](docs/references.md) | OpenClaw, LiteClaw, and Telegram+Claude bot analysis |
| [Policy](docs/policy.md) | Auth decisions, TOS awareness, OpenClaw precedent |

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
