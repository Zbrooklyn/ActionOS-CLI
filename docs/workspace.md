# Workspace Templates

File-based prompt workspace for agent personality, user context, and long-term memory. Inspired by [OpenClaw's template system](references.md#openclaw-core-templates).

## Overview

The `workspace/` directory contains markdown files that are read by the orchestrator and injected into Claude's system prompt via `--append-system-prompt` on every invocation. Instead of hardcoding agent behavior, these files are editable, versionable (git), and human-readable.

```
workspace/
  SOUL.md          # Agent personality, values, behavioral rules
  USER.md          # Evolving profile of the human
  MEMORY.md        # Curated long-term memory
  BOOT.md          # Startup checklist (read every session)
  BOOTSTRAP.md     # First-run onboarding (used once, then deleted)
  memory/          # Raw daily conversation logs
    YYYY-MM-DD.md  # Auto-generated daily log
```

## File descriptions

### SOUL.md

**Who the agent is.** Personality, behavioral boundaries, values. This file defines the agent's character and is the most important workspace file.

- Read on every invocation.
- The orchestrator checks for SOUL.md's existence specifically — if missing, the agent runs without personality constraints.
- Only the human edits this file. The agent cannot modify its own SOUL.

**OpenClaw parallel:** SOUL.md + IDENTITY.md (we merge these — no need for a separate identity card in a single-agent system).

### USER.md

**Who the human is.** Name, timezone, preferences, current projects, context. This accumulates over time as the agent learns about the user.

- Read on every invocation.
- The agent may suggest updates (e.g., "Should I add Python 3.12 to your preferences?"), but only writes happen through an approved skill or manual edit.
- Template fields start as "(not yet set)" — populated during onboarding or over time.

**OpenClaw parallel:** USER.md (same concept, same purpose).

### MEMORY.md

**What the agent remembers.** Curated, distilled knowledge from past conversations. Key decisions, learnings, stable facts.

- Read on every invocation.
- Structured in sections: Decisions, Learnings, Facts.
- Kept concise — this goes into the system prompt, so every line costs tokens.

**OpenClaw parallel:** MEMORY.md (curated layer of two-tiered memory).

### BOOT.md

**What to do on startup.** A checklist the agent sees at the beginning of every session. Reminds it of available tools, constraints, how skills work, and to check MEMORY.md/USER.md for context.

- Read on every invocation (unless BOOTSTRAP.md exists — see below).
- Keep this short. It runs every time.

**OpenClaw parallel:** BOOT.md (same concept).

### BOOTSTRAP.md

**First-run onboarding.** Guides the human through initial setup via natural conversation. Asks for name, timezone, preferences, and current projects.

- Exists only until first-run completes.
- When the orchestrator detects BOOTSTRAP.md, it injects this INSTEAD of BOOT.md.
- After the first successful conversation, the orchestrator writes answers to USER.md and deletes BOOTSTRAP.md.
- Subsequent sessions use BOOT.md.

**OpenClaw parallel:** BOOTSTRAP.md (same bootstrap-then-delete pattern).

### memory/ (daily logs)

**Raw conversation logs.** Auto-generated daily markdown files.

- Created automatically by the orchestrator after each conversation.
- Format: `YYYY-MM-DD.md` with timestamped entries.
- These are NOT injected into the system prompt (they'd be too large).
- Periodically review and promote important items to MEMORY.md.
- Old logs can be archived or deleted without affecting agent behavior.

**OpenClaw parallel:** `memory/YYYY-MM-DD.md` (raw layer of two-tiered memory).

## How workspace files enter the system prompt

The orchestrator builds the `--append-system-prompt` value by reading workspace files in order:

```
1. SOUL.md content       (if exists)
2. USER.md content       (if exists)
3. MEMORY.md content     (if exists)
4. BOOT.md content       (or BOOTSTRAP.md if first run)
5. Skill descriptions    (from loaded skill manifests)
6. Orchestrator instructions (skill_call format, constraints)
```

This is concatenated into a single string and passed as `--append-system-prompt`. Claude's built-in system prompt is preserved (we never use `--system-prompt`).

**Token budget:** Workspace files should be kept concise. A rough target:

| File | Target size | Notes |
|------|-------------|-------|
| SOUL.md | < 500 words | Personality doesn't need to be a novel |
| USER.md | < 300 words | Key facts only, not a biography |
| MEMORY.md | < 500 words | Curate aggressively, promote only what matters |
| BOOT.md | < 200 words | Short checklist |
| Skill descriptions | ~50 words each | Name + one-line description per skill |

Total system prompt overhead target: **< 2000 tokens** from workspace files.

## Files we chose NOT to create

From OpenClaw's 8 templates, we adopted 5 and skipped 3:

| OpenClaw file | Our decision | Reason |
|---------------|--------------|--------|
| SOUL.md | Adopted | Core personality file |
| AGENTS.md | Merged into BOOT.md | We have one agent, not a fleet. Operational instructions fit in BOOT.md. |
| IDENTITY.md | Merged into SOUL.md | Single-agent system doesn't need a separate identity card. |
| USER.md | Adopted | Essential for personalization |
| TOOLS.md | Merged into config.toml | Environment config (SSH hosts, paths) belongs in config, not in a prompt file. |
| BOOTSTRAP.md | Adopted | Elegant onboarding pattern |
| BOOT.md | Adopted | Startup checklist |
| HEARTBEAT.md | Replaced by cron_jobs table | We use SQLite cron scheduling, not a markdown-based heartbeat config. |

## Editing workspace files

- **Manually:** Edit the files directly. Changes take effect on the next invocation.
- **Via Telegram:** Tell the agent to update USER.md or MEMORY.md. If the `notes` skill is approved, it can write to these files.
- **Via the agent:** The agent can suggest changes, but the orchestrator will only write if the operation goes through the approval flow (write-tier skill or two-pass approval).
- **Via git:** The workspace directory is part of the repo. Version control your agent's personality.
