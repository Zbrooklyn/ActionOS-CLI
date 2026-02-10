# Workspace Templates

File-based prompt workspace for agent personality, user context, and long-term memory. Matches [OpenClaw's template naming](references.md#openclaw-core-templates) for interoperability.

## Overview

The `workspace/` directory contains markdown files that are read by the orchestrator and injected into Claude's system prompt via `--append-system-prompt` on every invocation. Instead of hardcoding agent behavior, these files are editable, versionable (git), and human-readable.

```
workspace/
  SOUL.md            # Core personality and values
  SOUL.dev.md        # Dev mode personality (builder mindset)
  IDENTITY.md        # Agent identity card (name, role, platform)
  IDENTITY.dev.md    # Dev mode identity (expanded role)
  AGENTS.md          # Operations manual (memory, safety, skills, output)
  AGENTS.dev.md      # Dev mode operations (skill building, git workflow)
  USER.md            # Evolving profile of the human
  MEMORY.md          # Curated long-term memory
  TOOLS.md           # Environment-specific infrastructure notes
  BOOT.md            # Startup checklist + mode switching
  BOOTSTRAP.md       # First-run onboarding (used once, then deleted)
  HEARTBEAT.md       # Cron/heartbeat task configuration
  memory/            # Raw daily conversation logs
    YYYY-MM-DD.md    # Auto-generated daily log
```

## Modes

The workspace supports two modes:

| Mode | Trigger | Workspace files loaded | Tools |
|------|---------|----------------------|-------|
| **normal** | Default | SOUL + IDENTITY + AGENTS + USER + MEMORY + TOOLS + BOOT | Read, Glob, Grep |
| **dev** | `/dev` command | SOUL.dev + IDENTITY.dev + AGENTS.dev + USER + MEMORY + TOOLS + BOOT | Read, Glob, Grep, Write, Edit, Bash (after approval) |

In dev mode, the agent can build and propose skills, modify project files, run tests, and commit to git — all with the human's approval via the two-pass flow.

The orchestrator swaps `.dev.md` variants for their base files when dev mode is active. Files without `.dev` variants (USER, MEMORY, TOOLS, BOOT, HEARTBEAT) are shared across modes.

## File descriptions

### SOUL.md / SOUL.dev.md

**Who the agent is.** Core personality, values, behavioral boundaries.

- Read on every invocation. Dev mode loads SOUL.dev.md instead.
- The orchestrator checks for SOUL.md's existence specifically — if missing, the agent runs without personality constraints.
- Only the human edits this file. The agent cannot modify its own SOUL.
- SOUL.dev.md adds: builder mindset, quality-consciousness, permission to create skills.

**OpenClaw parallel:** SOUL.md (same file, same name, same purpose).

### IDENTITY.md / IDENTITY.dev.md

**Agent identity card.** Name, role, platform, relationship to the human.

- Read on every invocation. Dev mode loads IDENTITY.dev.md instead.
- Lightweight metadata. Keeps identity separate from personality (SOUL) and operations (AGENTS).
- IDENTITY.dev.md changes role to "Personal AI assistant + skill builder".

**OpenClaw parallel:** IDENTITY.md (same file, same name, same purpose).

### AGENTS.md / AGENTS.dev.md

**Operations manual.** Memory management, safety boundaries, skill usage, output formatting rules.

- Read on every invocation. Dev mode loads AGENTS.dev.md instead.
- This is the "how to operate" document — the most content-heavy workspace file.
- AGENTS.dev.md adds: skill building workflow (propose → build → test → register → iterate), git workflow, expanded tool table.

**OpenClaw parallel:** AGENTS.md (same file, same name, same purpose).

**LiteClaw parallel:** AGENT.md (behavioral instructions, autonomy features).

### USER.md

**Who the human is.** Name, timezone, preferences, output formatting, current projects.

- Read on every invocation (same in both modes).
- The agent may suggest updates, but only writes through an approved skill or manual edit.
- Template fields start as "(not yet set)" — populated during onboarding or over time.
- Includes output formatting preferences (Telegram-specific: char limits, no tables, etc.).

**OpenClaw parallel:** USER.md (same file, same name, same purpose).

### MEMORY.md

**What the agent remembers.** Curated, distilled knowledge from past conversations.

- Read on every invocation (same in both modes).
- Structured in sections: Decisions, Learnings, Facts, Patterns.
- The Patterns section stores meta-knowledge: what works, what doesn't, workflow optimizations.
- Kept concise — this goes into the system prompt, so every line costs tokens.

**OpenClaw parallel:** MEMORY.md (curated layer of two-tiered memory).

**LiteClaw parallel:** LEARNING.md + SUBCONSCIOUS.md (we combine both into MEMORY.md's Patterns section).

### TOOLS.md

**What the human's environment looks like.** Machines, project paths, services, infrastructure notes.

- Read on every invocation (same in both modes).
- Distinct from skills (which define *how* to do things) — TOOLS.md describes *what exists*.
- Distinct from config.toml (which the agent cannot read) — TOOLS.md is agent-accessible context.
- Template ships with empty sections. Populated during onboarding or manually.

**OpenClaw parallel:** TOOLS.md (same file, same name, same purpose).

### BOOT.md

**Startup checklist.** What to check on session start, current mode, constraints.

- Read on every invocation (unless BOOTSTRAP.md exists).
- Lean checklist — detailed operations are in AGENTS.md.
- Contains mode indicator (normal vs dev) so the agent knows its current capabilities.

**OpenClaw parallel:** BOOT.md (same file, same name, same purpose).

### BOOTSTRAP.md

**First-run onboarding.** Guides the human through initial setup via natural conversation.

- Exists only until first-run completes.
- When detected, injected INSTEAD of BOOT.md.
- After the first conversation, the orchestrator writes answers to USER.md and deletes BOOTSTRAP.md.

**OpenClaw parallel:** BOOTSTRAP.md (same file, same name, same purpose).

### HEARTBEAT.md

**Cron/heartbeat configuration.** What the agent should check periodically.

- Read by the orchestrator to configure the `cron_jobs` table.
- Contains schedule, checklist of tasks, and output thread config.
- Delete this file to disable all heartbeat runs.
- Each heartbeat creates a fresh session (no `--resume`) to prevent context pollution.

**OpenClaw parallel:** HEARTBEAT.md (same file, same name. We back it with SQLite cron_jobs for robustness, but the file is the config interface).

### memory/ (daily logs)

**Raw conversation logs.** Auto-generated daily markdown files.

- Created automatically by the orchestrator after each conversation.
- Format: `YYYY-MM-DD.md` with timestamped entries.
- NOT injected into the system prompt (too large).
- Periodically review and promote important items to MEMORY.md.

**OpenClaw parallel:** `memory/YYYY-MM-DD.md` (same directory, same purpose).

## How workspace files enter the system prompt

### Normal mode assembly order

```
1. workspace/SOUL.md         (personality)
2. workspace/IDENTITY.md     (identity card)
3. workspace/USER.md         (human profile)
4. workspace/MEMORY.md       (curated memory)
5. workspace/TOOLS.md        (environment notes)
6. workspace/AGENTS.md       (operations manual)
7. workspace/BOOT.md         (startup checklist — or BOOTSTRAP.md if first run)
8. Mode-specific instructions (default/research)
9. Skill descriptions        (from loaded skill manifests)
10. Orchestrator instructions (skill_call format, constraints)
```

### Dev mode assembly order

```
1. workspace/SOUL.dev.md     (dev personality)
2. workspace/IDENTITY.dev.md (dev identity)
3. workspace/USER.md         (human profile — shared)
4. workspace/MEMORY.md       (curated memory — shared)
5. workspace/TOOLS.md        (environment notes — shared)
6. workspace/AGENTS.dev.md   (dev operations manual)
7. workspace/BOOT.md         (startup checklist — shared)
8. Mode-specific instructions (build mode)
9. Skill descriptions        (from loaded skill manifests)
10. Orchestrator instructions (skill_call format, constraints)
```

All workspace files are optional. If missing, the agent runs with mode instructions only.

**Token budget:** Workspace files should be kept concise. A rough target:

| File | Target size | Notes |
|------|-------------|-------|
| SOUL.md | < 300 words | Personality, not a novel |
| IDENTITY.md | < 100 words | Lightweight identity card |
| AGENTS.md | < 500 words | Operations manual — the longest file |
| USER.md | < 300 words | Key facts only |
| MEMORY.md | < 500 words | Curate aggressively |
| TOOLS.md | < 200 words | Infrastructure notes, not an inventory |
| BOOT.md | < 200 words | Short startup checklist |
| Skill descriptions | ~50 words each | Name + one-line description per skill |

Total system prompt overhead target: **< 2500 tokens** from workspace files.

## OpenClaw / LiteClaw mapping

Full 1:1 mapping with OpenClaw naming. All files are interchangeable.

| Our file | OpenClaw file | LiteClaw source | Notes |
|----------|--------------|-----------------|-------|
| SOUL.md | SOUL.md | PERSONALITY.md | Same name, same purpose |
| SOUL.dev.md | SOUL.dev.md | (none) | Dev mode personality |
| IDENTITY.md | IDENTITY.md | (none) | Same name, same purpose |
| IDENTITY.dev.md | IDENTITY.dev.md | (none) | Dev mode identity |
| AGENTS.md | AGENTS.md | AGENT.md | Same name, same purpose |
| AGENTS.dev.md | AGENTS.dev.md | (none) | Dev mode operations |
| USER.md | USER.md | SOUL.md (user facts) | Same name |
| MEMORY.md | MEMORY.md | LEARNING.md + SUBCONSCIOUS.md | Same name, broader scope |
| TOOLS.md | TOOLS.md | (none) | Same name, same purpose |
| BOOT.md | BOOT.md | (none) | Same name, same purpose |
| BOOTSTRAP.md | BOOTSTRAP.md | (none) | Same name, same purpose |
| HEARTBEAT.md | HEARTBEAT.md | HEARTBEAT.md | Same name, backed by SQLite |
| memory/*.md | memory/*.md | (none) | Same directory structure |

### LiteClaw files we absorbed

| LiteClaw file | Where it went | Reason |
|---------------|---------------|--------|
| PERSONALITY.md | SOUL.md | Our SOUL.md covers character and behavioral evolution |
| SUBCONSCIOUS.md | MEMORY.md (Patterns section) | Innovation ideas and error patterns fit under curated memory |
| LEARNING.md | MEMORY.md (Patterns section) | Best practices and workflow optimizations are long-term memory |

## Editing workspace files

- **Manually:** Edit the files directly. Changes take effect on the next invocation.
- **Via Telegram:** Tell the agent to update USER.md or MEMORY.md. If the `notes` skill is approved, it can write to these files.
- **Via dev mode:** In dev mode, the agent can directly propose edits to workspace files (with approval).
- **Via git:** The workspace directory is part of the repo. Version control your agent's personality.
