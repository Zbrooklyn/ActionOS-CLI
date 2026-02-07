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
|  (Job Queue)     |  Prevents overlapping runs. Manages retries.
+--------+---------+
         |
         v
+------------------+
|  Claude CLI      |  Spawns `claude` subprocess per job.
|  Runner          |  Parses JSON output. Enforces turn limits.
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
|  (Allowlist)     |  Approval-gated. No auto-install.
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
                         +--> BLOCKED (needs approval)
                         +--> TIMED_OUT
```

**Rules:**
- One job runs at a time per thread (no overlapping Claude sessions on the same conversation).
- Cross-thread parallelism is allowed (multiple threads can have running jobs simultaneously).
- Duplicate detection: if the same message arrives twice within 5 seconds, ignore the second.
- Retry: on transient CLI failures, retry up to 2 times with backoff (5s, 15s).
- Rate limit: max N jobs per minute globally (configurable, default 10).
- Timeout: kill the CLI subprocess after T seconds (configurable, default 120s).

### 3. Claude CLI Runner

**Responsibility:** Spawn `claude` as a subprocess, feed it a prompt, collect structured output.

This is the only component that touches Claude. It does not interpret the response — it just captures it and hands it to the state store.

**Invocation pattern:**
```bash
claude --print \
       --output-format json \
       --session-id <thread_id> \
       --max-turns <N> \
       --system-prompt <orchestrator_instructions> \
       --allowedTools <tool_list>
```

**Input:** Job record (prompt, thread ID, tool permissions, turn limit).
**Output:** Parsed JSON (assistant message, tool calls, cost metadata).

See [CLI Contract](cli-contract.md) for full details.

### 4. State Store (SQLite)

**Responsibility:** Persist everything. Single source of truth.

One SQLite file. No external database. Migrations handled by versioned SQL scripts.

**Tables:**
- `threads` — maps Telegram chats to Claude sessions
- `messages` — full conversation history
- `jobs` — job queue with status tracking
- `tool_calls` — what tools were invoked, args, results (audit log)
- `approvals` — pending/approved/rejected actions
- `skills` — registered skills with status and permissions
- `cron_jobs` — scheduled recurring tasks

See [Schema](schema.md) for full DDL.

### 5. Skills Layer

**Responsibility:** Provide modular tools the agent can use, with explicit permission boundaries.

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

## Data flow: message to reply

Step-by-step for a normal message:

1. You send a message in Telegram.
2. Bot polling loop picks it up, creates a `message` record, creates a `job` record with status `QUEUED`.
3. Orchestrator picks up the job, checks for duplicates, checks rate limit.
4. Orchestrator sets job status to `RUNNING`, invokes Claude CLI Runner.
5. Runner spawns `claude --print --output-format json --session-id <thread> ...` with your message as stdin.
6. Claude CLI processes the prompt, possibly makes tool calls (captured in JSON output).
7. Runner parses JSON response, writes `message` (assistant reply) + `tool_calls` records.
8. Orchestrator sets job status to `COMPLETED`.
9. Bot sends the assistant reply to Telegram.

## Data flow: approval-required action

1. Claude's response includes a tool call flagged as `write` or `execute` tier.
2. Runner detects the tool call requires approval.
3. Job status set to `BLOCKED`. An `approval` record is created.
4. Bot sends you an approval message with inline buttons: `Approve | Deny | Sandbox`.
5. You tap `Approve`.
6. Bot updates the `approval` record, creates a new job to execute the approved action.
7. Runner re-invokes Claude CLI with the approved tool available.
8. Normal flow resumes.

## Concurrency model

- **Single-threaded orchestrator** with an async event loop (no thread pool, no multiprocessing).
- One Claude CLI subprocess at a time per thread; multiple threads can run in parallel.
- SQLite with WAL mode for safe concurrent reads during writes.
- File-level locking for the skills folder during install/activate.

## What's deliberately excluded

- **No message broker** (Redis, RabbitMQ). SQLite job queue is sufficient for single-user.
- **No container orchestration** (Kubernetes, Docker Compose for runtime). Docker is only used as a sandbox for risky skills.
- **No WebSocket / real-time streaming**. Telegram messages are fire-and-forget. Streaming can come later.
- **No multi-user support**. This is a personal assistant. One Telegram user, one Claude login.
