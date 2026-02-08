# Architecture

## System overview

ActionOS-CLI is 5 components connected in a pipeline. Each component has one job and a clean interface to the next.

```
+------------------+
|  Telegram Bot    |  Polling loop. Receives messages, sends replies + buttons.
|  (Ingress)       |  No webhook, no public IP.
+--------+---------+
         |
         v
+------------------+
|  Orchestrator    |  Converts messages to jobs. Deduplicates. Rate-limits.
|  (Job Queue)     |  Prevents overlapping runs. Manages retries + approvals.
+--------+---------+
         |
         v
+------------------+
|  Claude CLI      |  Spawns `claude` subprocess per job.
|  Runner          |  Parses JSON output. Enforces turn + budget limits.
+--------+---------+
         |
         v
+------------------+
|  State Store     |  SQLite. Threads, messages, jobs, tool calls,
|  (SQLite)        |  approvals, skills, cron. Single file, no server.
+--------+---------+
         |
         v
+------------------+
|  Skills Layer    |  Builtin + custom tools. Manifest-driven.
|  (Allowlist)     |  Executed by orchestrator, NOT by Claude directly.
+------------------+
```

## Component breakdown

### 1. Telegram Bot (Ingress)

**Responsibility:** Translate between Telegram's API and the orchestrator's job interface.

- Uses long-polling (`getUpdates`), not webhooks. No public IP required.
- Each Telegram chat maps to a "thread" in the state store.
- Incoming messages become job requests.
- Outgoing messages are either Claude responses or system messages (job status, approval requests).
- Inline keyboard buttons for approvals: `Approve`, `Deny`, `Sandbox`.
- Handles message chunking (Telegram's 4096 char limit per message).

**Does not:** Parse intent, decide what to do, call Claude directly.

### 2. Orchestrator (Job Queue + Worker)

**Responsibility:** Manage the lifecycle of jobs from creation to completion.

A "job" is **one Claude CLI invocation**. Everything more complex (pipelines, scheduled tasks, multi-step workflows) is built on top of jobs, not inside them.

**Job lifecycle:**
```
CREATED --> QUEUED --> RUNNING --> COMPLETED
                         |
                         +--> FAILED (retryable)
                         +--> NEEDS_APPROVAL (two-pass)
                         +--> TIMED_OUT
                         +--> CANCELLED
```

**Rules:**
- One job runs at a time per thread (no overlapping Claude sessions on the same conversation).
- Cross-thread parallelism is allowed (multiple threads can have running jobs simultaneously).
- Duplicate detection: if the same message arrives twice within 5 seconds, ignore the second.
- Retry: on transient CLI failures, retry up to 2 times with backoff (5s, 15s).
- Rate limit: max N jobs per minute globally (configurable, default 10).
- Timeout: kill the CLI subprocess after T seconds (configurable, default 120s).
- Budget: `--max-budget-usd` caps each invocation (configurable, default $0.50).

### Workspace (Prompt Templates)

**Responsibility:** Define agent personality, user context, and long-term memory via editable markdown files.

The `workspace/` directory contains files read by the orchestrator and injected into `--append-system-prompt` on every invocation:

| File | Purpose | Injected? |
|------|---------|-----------|
| `SOUL.md` | Agent personality, values, behavioral rules | Yes — always |
| `USER.md` | Evolving profile of the human (name, timezone, preferences) | Yes — always |
| `MEMORY.md` | Curated long-term memory (decisions, learnings, facts) | Yes — always |
| `BOOT.md` | Startup checklist (available tools, constraints, skill format) | Yes — every session |
| `BOOTSTRAP.md` | First-run onboarding (used once, then deleted) | Yes — replaces BOOT.md on first run |
| `memory/*.md` | Raw daily conversation logs | No — too large, for review only |

The orchestrator builds the system prompt by concatenating: SOUL.md + USER.md + MEMORY.md + BOOT.md + skill descriptions + orchestrator instructions. This is passed as `--append-system-prompt`, preserving Claude's built-in capabilities.

Inspired by [OpenClaw's template system](references.md#openclaw-core-templates). See [Workspace](workspace.md) for full details.

### 3. CLI Runner (multi-CLI ready)

**Responsibility:** Spawn an AI CLI as a subprocess, feed it a prompt, collect structured output.

This is the only component that touches AI models. It does not interpret the response — it just captures it and hands it to the orchestrator.

The runner is an abstraction with one implementation per CLI:

| Runner | CLI | Auth | Status |
|--------|-----|------|--------|
| `ClaudeRunner` | `claude --print --output-format json` | `claude login` (OAuth) | v1 |
| `GeminiRunner` | `gemini` CLI | `gemini auth login` (Google OAuth) | Future |
| `CodexRunner` | `codex` CLI | `codex auth` (OpenAI OAuth) | Future |

All runners implement the same interface: accept a job record, return structured output (result text, session ID, cost, usage). The orchestrator doesn't know or care which CLI it's talking to.

**First message in a thread (new session):**
```bash
echo "<prompt>" | claude --print \
       --output-format json \
       --max-turns 5 \
       --max-budget-usd 0.50 \
       --append-system-prompt "<orchestrator_instructions>" \
       --allowedTools "Read,Glob,Grep"
```

**Subsequent messages (resume existing session):**
```bash
echo "<prompt>" | claude --print \
       --output-format json \
       --resume <session_id> \
       --max-turns 5 \
       --max-budget-usd 0.50 \
       --append-system-prompt "<orchestrator_instructions>" \
       --allowedTools "Read,Glob,Grep"
```

**Key:** The `session_id` comes from Claude CLI's JSON response on the first invocation. We store it in the `threads` table and use `--resume` for all subsequent messages.

**Input:** Job record (prompt, session ID if resuming, tool permissions, turn limit, budget).
**Output:** Parsed JSON (assistant message, session ID, cost, usage, subtype).

See [CLI Contract](cli-contract.md) for full details.

### 4. State Store (SQLite)

**Responsibility:** Persist everything. Single source of truth.

One SQLite file. No external database. Migrations handled by versioned SQL scripts.

**Tables:**
- `threads` — maps Telegram chats to Claude session IDs (from CLI response)
- `messages` — full conversation history
- `jobs` — job queue with status tracking
- `tool_calls` — what tools were invoked, args, results (audit log)
- `approvals` — pending/approved/rejected actions
- `skills` — registered skills with status and permissions
- `cron_jobs` — scheduled recurring tasks

See [Schema](schema.md) for full DDL.

### 5. Skills Layer

**Responsibility:** Provide modular tools the agent can use, with explicit permission boundaries.

**Critical design decision: Claude does not execute skills directly.** Claude CLI's built-in tools (Read, Write, Bash, etc.) are controlled via `--allowedTools`. Our custom skills are a separate layer — the orchestrator executes them.

The flow:
1. Claude's response includes a structured `skill_call` JSON block (e.g., `{"skill_call": {"name": "notes", "inputs": {"action": "create", "title": "meeting"}}}`).
2. The orchestrator detects the skill call, validates inputs against the manifest.
3. The orchestrator executes the skill (subprocess or Docker sandbox).
4. The result is fed back to Claude via `--resume` as the next user message.

This means Claude is the **brain** (decides what to do) and the orchestrator is the **hands** (does it). Claude never has direct access to skill executors.

Each skill is a folder:
```
skills/builtin/notes/
  manifest.json    # name, description, inputs, permissions, risk
  run.py           # executor
```

**Skill tiers:**
| Tier | Risk | Examples | Approval |
|------|------|----------|----------|
| **read** | Low | File search, notes lookup, web fetch | Auto-approved |
| **write** | Medium | Create/edit files, save notes | One-time approval per skill |
| **execute** | High | Run scripts, shell commands | Per-invocation approval |
| **system** | Critical | Install packages, modify config | Per-invocation + sandbox |

See [Skills Manifest](skills-manifest.md) for the full spec.

## Data flow: normal message

Step-by-step for a read-only request (e.g., "What's in my notes?"):

1. You send a message in Telegram.
2. Bot polling loop picks it up, creates a `message` record, creates a `job` record with status `QUEUED`.
3. Orchestrator picks up the job, checks for duplicates, checks rate limit.
4. Orchestrator sets job status to `RUNNING`, invokes Claude CLI Runner.
5. Runner spawns `claude --print --output-format json --resume <session_id> ...` with your message as stdin.
6. Claude CLI processes the prompt using read-only tools. Returns JSON.
7. Runner parses JSON response, writes `message` (assistant reply) record. Stores `session_id` if new.
8. Orchestrator sets job status to `COMPLETED`.
9. Bot sends the assistant reply to Telegram.

## Data flow: skill invocation

Step-by-step when Claude wants to use a custom skill (e.g., "Save a note about the meeting"):

1. Steps 1-6 same as above. Claude's `result` text includes a `skill_call` JSON block.
2. Orchestrator detects the `skill_call` in the response.
3. Orchestrator checks skill tier:
   - **Read tier:** Auto-approved. Proceed.
   - **Write tier:** Check if this skill has been approved before. If not, request approval.
   - **Execute/system tier:** Always request approval.
4. If approval needed: create `approval` record, send approval buttons to Telegram. Job status = `NEEDS_APPROVAL`. Wait.
5. User taps `Approve` (or `Deny`/`Sandbox`).
6. Orchestrator validates inputs against skill manifest.
7. Orchestrator executes `run.py` (subprocess or Docker if sandboxed).
8. Orchestrator captures skill output.
9. Orchestrator creates a new job: `--resume <session_id>` with the skill output as the prompt: `"[Skill result for notes] Note created: data/notes/meeting.md"`.
10. Claude receives the result, generates a final reply.
11. Bot sends Claude's reply to Telegram.

## Data flow: two-pass approval (risky built-in tools)

When Claude needs tools beyond read-only (e.g., "Fix the bug in main.py"):

1. **Pass 1 (read-only):** Orchestrator invokes Claude with `--allowedTools "Read,Glob,Grep"`.
2. Claude analyzes the situation using read-only tools. Its response describes what it wants to do: "I need to edit main.py line 42 to fix the null check."
3. Orchestrator detects the intent (Claude asked to write/execute but only had read tools).
4. Orchestrator creates an `approval` record, sends approval request to Telegram.
5. You tap `Approve`.
6. **Pass 2 (escalated):** Orchestrator creates a new job with `--resume <session_id>` and `--allowedTools "Read,Write,Edit,Glob,Grep"`. Prompt: "Approved. Proceed."
7. Claude executes the edit with the now-available tools.
8. Normal completion flow.

**Why two passes?** Claude CLI executes tools during its agent loop. There's no way to intercept a tool call mid-execution with `--print` mode. By restricting tools on pass 1, Claude can only describe what it wants. Pass 2 gives it the tools to act.

## Data flow: cron job

Scheduled tasks run without a user message triggering them:

1. Orchestrator's timer fires based on `cron_jobs.next_run_at`.
2. Orchestrator creates a job linked to a designated **system thread** (one per cron job, created on cron setup).
3. Runner invokes Claude CLI with the cron job's prompt and tool permissions.
4. On completion, bot sends the result to the cron job's thread in Telegram.
5. Messages are clearly labeled: `[Cron: daily-summary] ...`

Each cron job has its own Telegram thread so output doesn't pollute your main conversation.

## Concurrency model

- **Single-threaded orchestrator** with an async event loop (no thread pool, no multiprocessing).
- One Claude CLI subprocess at a time per thread; multiple threads can run in parallel.
- SQLite with WAL mode for safe concurrent reads during writes.
- File-level locking for the skills folder during install/activate.

## What's deliberately excluded

- **No message broker** (Redis, RabbitMQ). SQLite job queue is sufficient for single-user.
- **No container orchestration** (Kubernetes, Docker Compose for runtime). Docker is only used as a sandbox for risky skills.
- **No WebSocket / real-time streaming** in v1. Telegram messages are fire-and-forget. `stream-json` mode can come later.
- **No multi-user support**. This is a personal assistant. One Telegram user, one Claude login.
- **No MCP in v1**. Skills are plain subprocess executors. MCP integration can be added later for richer tool protocols.
