# Workspace Templates

File-based prompt workspace for agent personality, user context, and long-term memory. Inspired by [OpenClaw's template system](references.md#openclaw-core-templates).

## Overview

The `workspace/` directory contains markdown files that are read by the orchestrator and injected into Claude's system prompt via `--append-system-prompt` on every invocation. Instead of hardcoding agent behavior, these files are editable, versionable (git), and human-readable.

```
workspace/
  SOUL.md          # Agent personality, values, behavioral rules
  USER.md          # Evolving profile of the human (+ output formatting prefs)
  MEMORY.md        # Curated long-term memory (decisions, learnings, facts, patterns)
  TOOLS.md         # Environment-specific infrastructure notes (machines, paths, services)
  BOOT.md          # Operations manual: tools, memory, safety, output rules
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

### TOOLS.md

**What the human's environment looks like.** Machines, project paths, services, infrastructure notes. Things the agent should know about the user's setup that aren't secrets.

- Read on every invocation.
- Distinct from skills (which define *how* to do things) — TOOLS.md describes *what exists*.
- Distinct from config.toml (which the agent cannot read) — TOOLS.md is agent-accessible context.
- Template ships with empty sections. Populated during onboarding or manually.

**OpenClaw parallel:** TOOLS.md (reversed our earlier decision to merge into config.toml — the agent needs to see this in the prompt, not in a config file it can't access).

**LiteClaw parallel:** No direct equivalent. LiteClaw stores environment info in SOUL.md, which mixes concerns.

### BOOT.md

**Operations manual.** Covers: startup checklist, skill invocation, memory management rules, safety boundaries, and Telegram output formatting. This is the most content-heavy workspace file.

- Read on every invocation (unless BOOTSTRAP.md exists — see below).
- Expanded from a simple checklist to a full operations manual, absorbing the role of OpenClaw's AGENTS.md.
- Contains: when/how to suggest memory updates, explicit safety rules ("read before write", "use trash over rm"), and Telegram-specific output constraints (4096 char limit, limited markdown).

**OpenClaw parallel:** BOOT.md + AGENTS.md (merged — single agent doesn't need separate files for "who are the agents" and "startup checklist").

**LiteClaw parallel:** AGENT.md (behavioral instructions, autonomy features, self-termination safeguard).

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
4. TOOLS.md content      (if exists)
5. BOOT.md content       (or BOOTSTRAP.md if first run)
6. Mode-specific instructions (default/research/build)
7. Skill descriptions    (from loaded skill manifests)
8. Orchestrator instructions (skill_call format, constraints)
```

This is concatenated into a single string and passed as `--append-system-prompt`. Claude's built-in system prompt is preserved (we never use `--system-prompt`).

**Token budget:** Workspace files should be kept concise. A rough target:

| File | Target size | Notes |
|------|-------------|-------|
| SOUL.md | < 500 words | Personality doesn't need to be a novel |
| USER.md | < 300 words | Key facts only, not a biography |
| MEMORY.md | < 500 words | Curate aggressively, promote only what matters |
| TOOLS.md | < 200 words | Infrastructure notes, not a full inventory |
| BOOT.md | < 500 words | Operations manual — the longest workspace file |
| Skill descriptions | ~50 words each | Name + one-line description per skill |

Total system prompt overhead target: **< 2500 tokens** from workspace files.

## OpenClaw / LiteClaw mapping

How our 6 workspace files relate to the template systems in OpenClaw (8 files) and LiteClaw (6 files):

| Our file | OpenClaw source | LiteClaw source | Notes |
|----------|----------------|-----------------|-------|
| SOUL.md | SOUL.md + IDENTITY.md | PERSONALITY.md | Merged identity card into personality (single agent) |
| USER.md | USER.md | SOUL.md (user facts) | LiteClaw confusingly stores user facts in SOUL.md |
| MEMORY.md | MEMORY.md | LEARNING.md + SUBCONSCIOUS.md | Combined learnings, patterns, and facts into one file |
| TOOLS.md | TOOLS.md | (none) | Environment-specific infrastructure notes |
| BOOT.md | BOOT.md + AGENTS.md | AGENT.md | Merged startup checklist + operations manual |
| BOOTSTRAP.md | BOOTSTRAP.md | (none) | First-run onboarding, then self-deletes |

### Files we chose NOT to create

| Source file | Decision | Reason |
|-------------|----------|--------|
| OpenClaw IDENTITY.md | Merged into SOUL.md | Single-agent system doesn't need a separate identity card |
| OpenClaw AGENTS.md | Merged into BOOT.md | One agent, not a fleet. Operations manual fits in BOOT.md |
| OpenClaw HEARTBEAT.md | Replaced by `cron_jobs` table | SQLite cron scheduling is more robust than markdown-based config |
| OpenClaw `.dev.md` variants | Skipped | Dev-mode personality swapping is unnecessary for a personal bot |
| LiteClaw PERSONALITY.md | Merged into SOUL.md | Our SOUL.md covers both character and behavioral evolution |
| LiteClaw SUBCONSCIOUS.md | Merged into MEMORY.md (Patterns section) | Innovation ideas and error patterns fit under curated memory |
| LiteClaw LEARNING.md | Merged into MEMORY.md (Patterns section) | Best practices and workflow optimizations are part of long-term memory |

## Editing workspace files

- **Manually:** Edit the files directly. Changes take effect on the next invocation.
- **Via Telegram:** Tell the agent to update USER.md or MEMORY.md. If the `notes` skill is approved, it can write to these files.
- **Via the agent:** The agent can suggest changes, but the orchestrator will only write if the operation goes through the approval flow (write-tier skill or two-pass approval).
- **Via git:** The workspace directory is part of the repo. Version control your agent's personality.
