# BOOT

Startup checklist. Read on every invocation.

<!-- Short checklist the agent sees at session start. Tells it what tools
     are available and what to check first. Keep this lean — detailed
     operations are in AGENTS.md. -->

## On session start

1. You have access to read-only tools by default: `Read`, `Glob`, `Grep`.
2. If you need write or execute tools, describe what you want to do. The human will approve or deny via Telegram.
3. Check MEMORY.md for relevant context before asking questions the human has already answered.
4. Check USER.md for the human's preferences and current projects.
5. Check TOOLS.md for environment details (machines, paths, services).

## Mode

Current mode: **normal**

- **normal** — read-only tools, full workspace loaded (SOUL + IDENTITY + USER + MEMORY + TOOLS + AGENTS + BOOT).
- **dev** — expanded tools after approval, dev workspace loaded (SOUL.dev + IDENTITY.dev + AGENTS.dev + USER + MEMORY + TOOLS + BOOT). You can build and propose skills with write/execute access.

Mode is set by the orchestrator based on the `/dev` command or per-job config.

## Constraints

- Max turns per invocation: set by orchestrator (default 5).
- Max budget per invocation: set by orchestrator (default $0.50).
- If you hit a turn or budget limit, summarize where you are so the human can continue in the next message.
