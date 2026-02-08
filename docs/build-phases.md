# Build Phases

Implementation order, milestones, and definition of done for each phase.

## Guiding principle

Each phase produces something you can actually use daily. No phase is "just infrastructure" — every phase ends with a working feature you interact with through Telegram.

**Priority order:** Telegram → Claude CLI → Dashboard → Other CLIs (Gemini, Codex)

Claude Code is the primary engine. It has the strongest agentic capabilities (sub-agents, TodoWrite planning, session memory, best code quality). Gemini and Codex come later as additional runners — the architecture supports them, but they're not blocking anything.

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
- Auth via `ANTHROPIC_API_KEY` (compliant automation — see [Policy](policy.md)).
- Capture `session_id` from JSON response, store in `threads` table.
- Use `--resume <session_id>` for subsequent messages in the same thread.
- Use `--append-system-prompt` (not `--system-prompt`) to preserve Claude's built-in capabilities.
- Load workspace files (SOUL.md, IDENTITY.md, AGENTS.md, USER.md, MEMORY.md, TOOLS.md, BOOT.md) and concatenate into `--append-system-prompt`.
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
- Dev mode (`/dev`) for building skills with Write/Edit/Bash tools.

**Definition of done:**
- Claude proposes a skill ("I need a tool to check weather").
- You review the code, approve it.
- On next invocation, Claude's system prompt includes the new skill.
- Sandboxed skills run in Docker with resource limits.

---

## Phase 8: Web Dashboard

**Goal:** Web UI to view jobs, logs, approvals, skills, and costs.

**Build:**
- Simple HTTP server (FastAPI).
- Pages:
  - Jobs: table with status, duration, cost, tokens, prompt preview.
  - Logs: tool calls for a selected job (both builtin and skill).
  - Approvals: pending + history.
  - Skills: list with status toggles.
  - Cost: daily/weekly summary.
- No authentication beyond running on localhost (or basic auth if exposed).
- Start read-only, add actions (approve/deny, skill management) later.

**Definition of done:**
- Open `localhost:8080` and see your job history.
- Click a job to see its tool calls and the full job chain.
- See cost summary for the past week.

---

## Phase 9: Gemini + Codex Integration

**Goal:** Route tasks to Claude, Gemini, or Codex based on task type or user choice.

This phase comes after the core product is working and stable. The runner abstraction from Phase 3 makes this a new module, not a rewrite.

**Build:**
- Gemini runner module (service account auth, `-p` flag, JSON output).
- Codex runner module (API key auth, `codex exec`, JSON output).
- Verify CLI flags against actual `--help` output for each CLI.
- Smart routing: auto-pick CLI based on task type (see [CLI Comparison](cli-comparison.md)).
- Per-message override: `/claude`, `/gemini`, `/codex` prefixes.
- Config: default CLI, routing table, per-CLI model selection.
- Cost tracking normalized across providers.
- Dashboard updated with per-CLI breakdown.

**Definition of done:**
- `/gemini what's the weather` routes to Gemini CLI.
- `/codex review this function` routes to Codex CLI.
- Default messages route to Claude (or per routing config).
- All three CLIs use compliant auth methods.

---

## Future phases (not planned in detail)

| Phase | Description |
|-------|-------------|
| Full Dashboard | Kanban board, conversation threads, cost analytics, WebSocket real-time updates |
| Cron jobs | Scheduled recurring prompts with dedicated output threads |
| Stream mode | `--output-format stream-json` for real-time Telegram feedback |
| MCP skills | Register skills as MCP servers for native CLI integration |
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
