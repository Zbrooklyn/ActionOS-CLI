# Schema

SQLite database design for ActionOS-CLI. Single file, no server.

## Database configuration

```sql
PRAGMA journal_mode = WAL;          -- Safe concurrent reads during writes
PRAGMA foreign_keys = ON;           -- Enforce referential integrity
PRAGMA busy_timeout = 5000;         -- Wait up to 5s on lock contention
```

## Tables

### threads

Maps Telegram chats to Claude CLI sessions.

```sql
CREATE TABLE threads (
    id              TEXT PRIMARY KEY,                    -- UUID (our internal ID)
    telegram_chat_id INTEGER NOT NULL UNIQUE,            -- Telegram chat/topic ID
    session_id      TEXT,                                -- Claude CLI session_id (from JSON response, NULL until first invocation)
    thread_type     TEXT NOT NULL DEFAULT 'user'
                    CHECK (thread_type IN ('user', 'cron')),  -- User conversation or cron output
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    metadata        TEXT                                 -- JSON blob for extensibility
);
```

**Notes:**
- `session_id` is **captured from Claude CLI's JSON response** after the first invocation. It's NULL until then.
- `session_id` changes when the user runs `/clear` (set back to NULL, next invocation creates a new session).
- `thread_type` distinguishes user conversations from cron output threads.
- `telegram_chat_id` is the unique key from Telegram's perspective.

### messages

Full conversation history. Every message — user, assistant, system — is stored.

```sql
CREATE TABLE messages (
    id              TEXT PRIMARY KEY,                    -- UUID
    thread_id       TEXT NOT NULL REFERENCES threads(id),
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    telegram_msg_id INTEGER,                             -- Telegram message ID (for editing)
    job_id          TEXT REFERENCES jobs(id),            -- Which job produced this message
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_messages_thread ON messages(thread_id, created_at);
```

### jobs

The core work unit. One job = one Claude CLI invocation.

```sql
CREATE TABLE jobs (
    id              TEXT PRIMARY KEY,                    -- UUID
    thread_id       TEXT NOT NULL REFERENCES threads(id),
    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'running', 'completed', 'failed',
                                      'needs_approval', 'timed_out', 'cancelled')),
    job_type        TEXT NOT NULL DEFAULT 'message'
                    CHECK (job_type IN ('message', 'approval_followup', 'skill_result', 'cron')),
    prompt          TEXT NOT NULL,                       -- The input sent to Claude
    result          TEXT,                                -- Claude's final response
    subtype         TEXT,                                -- From CLI: "success", "error_max_turns", "error_during_execution"
    error           TEXT,                                -- Error message if failed
    system_prompt   TEXT,                                -- Appended system prompt used for this job
    allowed_tools   TEXT,                                -- JSON array of tool names
    max_turns       INTEGER DEFAULT 5,
    budget_usd      REAL DEFAULT 0.50,                   -- --max-budget-usd value
    total_cost_usd  REAL,                                -- From CLI response
    duration_ms     INTEGER,                             -- Total wall clock time
    duration_api_ms INTEGER,                             -- API call time only
    num_turns       INTEGER,
    input_tokens    INTEGER,                             -- From usage object
    output_tokens   INTEGER,                             -- From usage object
    cache_read_tokens INTEGER,                           -- From usage object
    session_id      TEXT,                                -- Claude session used (for debugging)
    attempt         INTEGER NOT NULL DEFAULT 1,          -- Retry count
    parent_job_id   TEXT REFERENCES jobs(id),            -- Links approval_followup/skill_result to original job
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    started_at      TEXT,
    completed_at    TEXT
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_thread ON jobs(thread_id, created_at);
CREATE INDEX idx_jobs_parent ON jobs(parent_job_id);
```

**Notes:**
- `job_type` tracks why this job was created (user message, follow-up after approval, skill result feedback, or cron trigger).
- `parent_job_id` links follow-up jobs back to the original, for tracing the full chain.
- `total_cost_usd` (not `cost_usd`) matches Claude CLI's actual JSON field name.
- Token counts from `usage` object stored directly for analysis.

### tool_calls

Audit log of every tool invocation within a job. This is the debugging lifeline.

```sql
CREATE TABLE tool_calls (
    id              TEXT PRIMARY KEY,                    -- UUID
    job_id          TEXT NOT NULL REFERENCES jobs(id),
    tool_type       TEXT NOT NULL CHECK (tool_type IN ('builtin', 'skill')),  -- Claude's built-in tool or our custom skill
    tool_name       TEXT NOT NULL,                       -- e.g., "notes", "file-search", "Read", "Bash"
    inputs          TEXT,                                -- JSON: arguments passed to the tool
    output          TEXT,                                -- JSON: tool's response
    duration_ms     INTEGER,
    success         INTEGER NOT NULL DEFAULT 1,          -- 1 = success, 0 = failure
    error           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_tool_calls_job ON tool_calls(job_id);
CREATE INDEX idx_tool_calls_tool ON tool_calls(tool_name);
```

**Notes:**
- `tool_type` distinguishes Claude's built-in tools (from CLI JSON output) from our custom skills (executed by orchestrator).
- For built-in tools, data comes from parsing Claude's response. For skills, data comes from the orchestrator's execution.

### approvals

Tracks risky actions that need user sign-off.

```sql
CREATE TABLE approvals (
    id              TEXT PRIMARY KEY,                    -- UUID
    job_id          TEXT NOT NULL REFERENCES jobs(id),
    type            TEXT NOT NULL CHECK (type IN ('tool_escalation', 'skill_execution', 'skill_proposal')),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'denied', 'sandbox', 'timed_out')),
    description     TEXT NOT NULL,                       -- Human-readable: "Edit main.py line 42"
    details         TEXT,                                -- JSON: full context (requested tools, skill manifest, code)
    telegram_msg_id INTEGER,                             -- Message with approval buttons
    decided_at      TEXT,
    expires_at      TEXT,                                -- Auto-timeout (10 min default)
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_approvals_status ON approvals(status);
CREATE INDEX idx_approvals_job ON approvals(job_id);
```

**Notes:**
- `type` now has three values:
  - `tool_escalation`: Claude needs write/execute tools beyond the default read-only set (two-pass approval).
  - `skill_execution`: A write/execute/system skill needs per-invocation approval.
  - `skill_proposal`: Claude proposed a new skill that needs review.

### skills

Registry of installed skills.

```sql
CREATE TABLE skills (
    name            TEXT PRIMARY KEY,                    -- e.g., "notes", "github-issues"
    version         TEXT NOT NULL,
    description     TEXT NOT NULL,
    author          TEXT NOT NULL,                       -- "builtin" or user handle
    tier            TEXT NOT NULL CHECK (tier IN ('read', 'write', 'execute', 'system')),
    manifest        TEXT NOT NULL,                       -- Full manifest.json as text
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'disabled', 'draft', 'rejected')),
    sandbox         INTEGER NOT NULL DEFAULT 0,          -- Force sandbox execution
    path            TEXT NOT NULL,                       -- Filesystem path to skill folder
    approved_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### cron_jobs

Scheduled recurring tasks.

```sql
CREATE TABLE cron_jobs (
    id              TEXT PRIMARY KEY,                    -- UUID
    name            TEXT NOT NULL,                       -- Human-readable name
    thread_id       TEXT REFERENCES threads(id),         -- Dedicated thread for this cron's output
    schedule        TEXT NOT NULL,                       -- Cron expression: "0 9 * * *"
    prompt          TEXT NOT NULL,                       -- What to send to Claude
    system_prompt   TEXT,
    allowed_tools   TEXT,                                -- JSON array
    max_turns       INTEGER DEFAULT 5,
    budget_usd      REAL DEFAULT 0.50,
    enabled         INTEGER NOT NULL DEFAULT 1,
    last_run_at     TEXT,
    next_run_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_cron_enabled ON cron_jobs(enabled, next_run_at);
```

**Notes:**
- `thread_id` links to a dedicated Telegram thread for this cron job's output. Created when the cron job is set up.
- `budget_usd` and `max_turns` cap each cron invocation independently.

## Migrations

Migrations are versioned SQL files in `src/store/migrations/`:

```
src/store/migrations/
  001_initial.sql
  002_add_cron_jobs.sql
  ...
```

A `schema_version` table tracks which migrations have been applied:

```sql
CREATE TABLE schema_version (
    version         INTEGER PRIMARY KEY,
    applied_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

On startup, the store module:
1. Creates `schema_version` if it doesn't exist.
2. Reads current version.
3. Applies any unapplied migrations in order.

## Queries (common patterns)

### Get pending jobs for a thread
```sql
SELECT * FROM jobs
WHERE thread_id = ? AND status IN ('queued', 'needs_approval')
ORDER BY created_at ASC;
```

### Get recent jobs
```sql
SELECT * FROM jobs
ORDER BY created_at DESC
LIMIT 10;
```

### Get pending approvals
```sql
SELECT * FROM approvals
WHERE status = 'pending' AND (expires_at IS NULL OR expires_at > datetime('now'))
ORDER BY created_at ASC;
```

### Daily cost summary
```sql
SELECT date(completed_at) as day,
       SUM(total_cost_usd) as total_cost,
       SUM(input_tokens) as total_input,
       SUM(output_tokens) as total_output,
       COUNT(*) as job_count
FROM jobs
WHERE status = 'completed' AND completed_at >= date('now', '-7 days')
GROUP BY day
ORDER BY day DESC;
```

### Skill usage frequency
```sql
SELECT tool_name, COUNT(*) as uses, AVG(duration_ms) as avg_ms
FROM tool_calls
WHERE created_at >= date('now', '-30 days')
GROUP BY tool_name
ORDER BY uses DESC;
```

### Full job chain (original + follow-ups)
```sql
WITH RECURSIVE chain AS (
    SELECT * FROM jobs WHERE id = ?
    UNION ALL
    SELECT j.* FROM jobs j JOIN chain c ON j.parent_job_id = c.id
)
SELECT * FROM chain ORDER BY created_at ASC;
```
