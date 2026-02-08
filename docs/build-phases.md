# Build Phases

Implementation order, milestones, and definition of done for each phase.

## Guiding principle

Each phase produces something you can actually use daily. No phase is "just infrastructure" — every phase ends with a working feature you interact with through Telegram.

---

## Phase 1: Telegram Bot (Echo)

**Goal:** Bot receives your messages and echoes them back. Proves the Telegram integration works.

**Build:**
- BotFather setup, get token.
- Polling loop with `getUpdates`.
- User ID validation (single-user lockdown).
- Echo incoming messages back.
- Implement `/start` and `/help` commands.
- Config file (`config/default.toml`) with bot token and user ID.

**Definition of done:**
- You send a message, bot replies with the same text.
- Messages from other users are silently ignored.
- Bot runs indefinitely without crashing.

**Tech:** Python (`python-telegram-bot` library or raw `httpx` + polling loop).

---

## Phase 2: SQLite State Store

**Goal:** Persist threads, messages, and jobs. Bot writes to the database on every message.

**Build:**
- SQLite setup with WAL mode.
- Create `threads`, `messages`, `jobs` tables.
- Migration system (versioned SQL files).
- On incoming message: create thread (if new), store message, create job.
- `/status` command shows job counts from the database.

**Definition of done:**
- Messages are persisted across bot restarts.
- `/status` shows accurate counts.
- Database file is portable (copy it, query with any SQLite client).

---

## Phase 3: Claude CLI Runner

**Goal:** Messages go to Claude CLI and real responses come back.

**Build:**
- Subprocess wrapper: spawn `claude --print --output-format json` for first message (new session).
- Capture `session_id` from JSON response, store in `threads` table.
- Use `--resume <session_id>` for subsequent messages in the same thread.
- Use `--append-system-prompt` (not `--system-prompt`) to preserve Claude's built-in capabilities.
- Set `--max-turns 5` and `--max-budget-usd 0.50` as defaults.
- Set `--allowedTools "Read,Glob,Grep"` as the default read-only set.
- Parse response: extract `result`, `session_id`, `total_cost_usd`, `subtype`, `usage`.
- Store assistant message in `messages` table. Update `threads.session_id`.
- Send Claude's reply to Telegram.
- Error handling: CLI not found, auth expired, timeout, invalid JSON, session corruption.
- `/clear` sets `threads.session_id` to NULL (next message creates fresh session).

**Definition of done:**
- You send a message, Claude responds through the bot.
- Conversation has continuity (`--resume` preserves context).
- `/clear` starts a fresh session.
- CLI errors produce clear system messages in Telegram.
- `total_cost_usd` and token counts logged per job.

**This is the "it works" milestone.** From here on, you have a usable personal assistant.

---

## Phase 4: Approval Gate

**Goal:** Risky actions require your explicit approval before execution.

**Build:**
- `approvals` table.
- **Two-pass approval for built-in tools:**
  1. Pass 1 runs with read-only tools. Claude describes what it wants to do.
  2. Orchestrator detects escalation request (Claude's response text asks to write/execute).
  3. Approval request sent to Telegram with inline keyboard buttons.
  4. On approval: Pass 2 runs with `--resume <session_id>` and escalated `--allowedTools`.
  5. On denial: `--resume` with "Denied. Suggest alternative."
- Handle button callbacks: approve, deny.
- Timeout: auto-expire approvals after 10 minutes.
- `parent_job_id` links pass 2 job back to pass 1 for audit trail.

**Definition of done:**
- When Claude wants to write a file, you see an approval button in Telegram.
- Approving lets Claude proceed with the tools it needs. Denying blocks it gracefully.
- The approval and decision are logged in the database.
- Expired approvals are handled (job marked timed_out, you're notified).
- Permissions are revoked after the job completes (clean slate).

---

## Phase 5: Job Runner (Orchestration)

**Goal:** Robust job lifecycle — queue, dedup, retry, rate-limit, concurrency control.

**Build:**
- Worker loop that polls `jobs` table for `queued` status.
- One job at a time per thread, parallel across threads.
- Duplicate detection (same message content within 5s window).
- Retry logic (transient failures, max 2 retries, backoff).
- Rate limiting (max N jobs/minute, configurable).
- Graceful shutdown: on SIGTERM, kill subprocess, mark interrupted jobs as failed.
- Recovery on restart: scan for `running` jobs, mark as failed.
- `/cancel` command kills the running subprocess.
- `/jobs` command shows recent job history with status, duration, cost, tokens.

**Definition of done:**
- Rapid-fire messages don't create duplicate jobs.
- A failed job retries automatically, then gives up gracefully.
- You can cancel a long-running job from Telegram.
- `/jobs` shows a useful history.
- Restarting the bot doesn't leave zombie jobs in `running` state.

---

## Phase 6: Safe Skills v1

**Goal:** First set of actually useful custom skills — notes, reminders, file search.

**Build:**
- Skill loader: scan `skills/builtin/` for `manifest.json` files.
- Skill executor: validate inputs against manifest schema, run `run.py` as subprocess, capture output.
- `tool_calls` table for audit logging.
- Skill descriptions injected into `--append-system-prompt` so Claude knows what's available.
- Claude requests skills via `{"skill_call": {...}}` JSON blocks in its response text.
- Orchestrator detects skill calls, executes, feeds result back via `--resume`.
- Implement builtin skills:
  - `notes`: CRUD for text notes in `data/notes/`.
  - `reminders`: store with natural-language time parsing, simple cron check.
  - `file-search`: glob + grep over a specified directory.

**Definition of done:**
- "Save a note about the meeting today" creates a file in `data/notes/`.
- "Remind me to call Alex tomorrow at 9am" stores a reminder that fires.
- "Find files about authentication in ~/project" returns results.
- Every skill invocation is logged in `tool_calls` with `tool_type = 'skill'`.
- Claude gets the skill result and uses it in its response.

---

## Phase 7: Custom Skills (Self-Extending)

**Goal:** The agent can propose new skills, you can approve them, and they become available.

**Build:**
- Skill proposal detection: parse `{"skill_proposal": {...}}` from Claude's response.
- Proposal message with approval buttons in Telegram.
- "View Code" button sends full source as a Telegram message.
- On approval: write skill to `skills/custom/`, register in `skills` table.
- On "Sandbox Only": write skill with `sandbox: true` forced.
- `skills` table tracks status (active, disabled, draft, rejected).
- `/skills` command lists all skills with status.
- Docker sandbox for skills that require it.

**Definition of done:**
- Claude proposes a skill ("I need a tool to check weather").
- You review the code, approve it.
- On next invocation, Claude's system prompt includes the new skill.
- Sandboxed skills run in Docker with resource limits.

---

## Phase 8: Web Dashboard (Read-Only)

**Goal:** Minimal web UI to view jobs, logs, approvals, and skills. No actions — just visibility.

**Build:**
- Simple HTTP server (Flask/FastAPI or even static HTML + SQLite REST).
- Pages:
  - Jobs: table with status, duration, cost, tokens, prompt preview.
  - Logs: tool calls for a selected job (both builtin and skill).
  - Approvals: pending + history.
  - Skills: list with status toggles.
  - Cost: daily/weekly summary.
- No authentication beyond running on localhost (or basic auth if exposed).
- No actions (no approve/deny from dashboard — that stays in Telegram).

**Definition of done:**
- Open `localhost:8080` and see your job history.
- Click a job to see its tool calls and the full job chain (parent + follow-ups).
- See pending approvals (but approve them in Telegram).
- See skill registry with enable/disable status.
- See cost summary for the past week.

---

## Future phases (not planned in detail)

### Multi-CLI: Gemini + Codex integration

**Goal:** Route tasks to Claude, Gemini, or Codex based on user preference or task type.

The runner abstraction (Phase 3) is designed for this. Each CLI gets its own runner module:

| CLI | Binary | Auth | JSON output | Session resume |
|-----|--------|------|-------------|----------------|
| Claude Code | `claude --print --output-format json` | `claude login` | Yes | `--resume <id>` |
| Gemini CLI | `gemini` | `gemini auth login` | TBD (verify) | TBD |
| ChatGPT Codex CLI | `codex` | `codex auth` | TBD (verify) | TBD |

**Build:**
- New runner module per CLI (same interface: prompt in, structured result out).
- Config: default CLI per thread, or `/model claude` `/model gemini` commands.
- Session management per CLI (each has its own session format).
- Cost tracking normalized across providers.
- Skill system remains CLI-agnostic (orchestrator executes skills, not the CLI).

**Key principle:** Same auth model for all — official CLI login, no API keys, no spoofing. Each provider's CLI handles its own authentication. See [Policy](policy.md).

### Full Dashboard (OpenClaw / Asana / Trello style)

**Goal:** Upgrade from read-only dashboard (Phase 8) to a full project management interface.

**Build:**
- **Kanban board:** Jobs as cards across columns (queued / running / needs approval / completed / failed).
- **Conversation threads:** View full message history per thread, searchable.
- **Skill management:** Enable/disable skills, view proposals, approve from dashboard (not just Telegram).
- **Cost analytics:** Daily/weekly/monthly charts, per-CLI breakdown, token usage trends.
- **Approval management:** Approve/deny pending actions from dashboard with full context.
- **Cron management:** Create/edit/disable scheduled jobs with visual schedule editor.
- **Real-time updates:** WebSocket push for live job status, new messages, approval requests.
- **Mobile-responsive:** Works on phone browsers (or PWA).

**Tech:** React or Vue frontend, FastAPI backend serving the existing SQLite data. The backend is thin — it just queries SQLite and exposes WebSocket events.

**Inspiration:**
- OpenClaw's dashboard (conversation view + job status + skill registry)
- Asana/Trello (kanban boards, task cards, project views)
- Grafana (cost/usage analytics panels)

### Other future phases

| Phase | Description |
|-------|-------------|
| Cron jobs | Scheduled recurring prompts with dedicated output threads |
| Stream mode | `--output-format stream-json` for real-time Telegram feedback |
| MCP skills | Register skills as MCP servers for native CLI integration |
| Swarm mode | Multi-agent for complex tasks (research + implement + review) |
| Voice messages | Telegram voice -> transcription -> Claude |
| File handling | Photos/documents sent to bot -> processed by Claude |
| Multi-user | Support multiple authorized Telegram users (separate threads/permissions) |

---

## Language choice

**Python** for the initial build. Reasons:

- `python-telegram-bot` is mature and well-documented.
- `subprocess` module handles Claude CLI spawning cleanly.
- `sqlite3` is built into the standard library.
- Skill executors are Python by default (trivial to run).
- `asyncio` provides the event loop for concurrent thread handling.
- Fast to prototype, easy to read, easy to hand off.

If performance becomes an issue (unlikely for single-user), specific components can be rewritten. But Python is the right call for "get it working and keep it simple."
