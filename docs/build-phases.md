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
- Subprocess wrapper: spawn `claude --print --output-format json --session-id <id>`.
- Pipe user message as input, capture JSON output.
- Parse response, extract `result` field.
- Store assistant message in `messages` table.
- Send Claude's reply to Telegram.
- Error handling: CLI not found, auth expired, timeout, invalid JSON.

**Definition of done:**
- You send a message, Claude responds through the bot.
- Conversation has continuity (session ID preserves context).
- `/clear` starts a fresh session.
- CLI errors produce clear system messages in Telegram.

**This is the "it works" milestone.** From here on, you have a usable personal assistant.

---

## Phase 4: Approval Gate

**Goal:** Risky actions require your explicit approval before execution.

**Build:**
- `approvals` table.
- Detect tool calls in Claude's JSON output that exceed read tier.
- Generate approval request message with inline keyboard buttons.
- Handle button callbacks: approve, deny, sandbox.
- On approval: re-invoke Claude with escalated `--allowedTools`.
- On denial: inform Claude, suggest alternative approach.
- Timeout: auto-expire approvals after 10 minutes.

**Definition of done:**
- When Claude wants to write a file, you see an approval button in Telegram.
- Approving lets the action proceed. Denying blocks it gracefully.
- The approval and decision are logged in the database.
- Expired approvals are handled (job marked timed_out, you're notified).

---

## Phase 5: Job Runner (Orchestration)

**Goal:** Robust job lifecycle — queue, dedup, retry, rate-limit, concurrency control.

**Build:**
- Worker loop that polls `jobs` table for `queued` status.
- One job at a time per thread, parallel across threads.
- Duplicate detection (same message within 5s window).
- Retry logic (transient failures, max 2 retries, backoff).
- Rate limiting (max N jobs/minute, configurable).
- `/cancel` command kills the running subprocess.
- `/jobs` command shows recent job history with status, duration, cost.

**Definition of done:**
- Rapid-fire messages don't create duplicate jobs.
- A failed job retries automatically, then gives up gracefully.
- You can cancel a long-running job from Telegram.
- `/jobs` shows a useful history.

---

## Phase 6: Safe Tools v1

**Goal:** First set of actually useful skills — notes, reminders, file search.

**Build:**
- Skill loader: scan `skills/builtin/` for `manifest.json` files.
- Skill executor: validate inputs, run `run.py`, capture output.
- `tool_calls` table for audit logging.
- Implement builtin skills:
  - `notes`: CRUD for text notes in `data/notes/`.
  - `reminders`: store with natural-language time parsing, simple cron check.
  - `file-search`: glob + grep over a specified directory.
- System prompt includes available skill descriptions.

**Definition of done:**
- "Save a note about the meeting today" creates a file in `data/notes/`.
- "Remind me to call Alex tomorrow at 9am" stores a reminder that fires.
- "Find files about authentication in ~/project" returns results.
- Every skill invocation is logged in `tool_calls`.

---

## Phase 7: Skills Folder (Custom Skills)

**Goal:** The agent can propose new skills, you can approve them, and they become available.

**Build:**
- Skill proposal detection in Claude's output.
- Proposal message with approval buttons in Telegram.
- "View Code" button sends full source.
- On approval: write skill to `skills/custom/`, register in `skills` table.
- `skills` table tracks status (active, disabled, draft, rejected).
- `/skills` command lists all skills with status.
- Docker sandbox for skills that require it.

**Definition of done:**
- Claude proposes a skill ("I need a tool to check weather").
- You review the code, approve it.
- Next conversation, Claude can use the new skill.
- Sandboxed skills run in Docker with resource limits.

---

## Phase 8: Web Dashboard (Read-Only)

**Goal:** Minimal web UI to view jobs, logs, approvals, and skills. No actions — just visibility.

**Build:**
- Simple HTTP server (Flask/FastAPI or even static HTML + SQLite REST).
- Pages:
  - Jobs: table with status, duration, cost, prompt preview.
  - Logs: tool calls for a selected job.
  - Approvals: pending + history.
  - Skills: list with status toggles.
- No authentication beyond running on localhost (or basic auth if exposed).
- No actions (no approve/deny from dashboard — that stays in Telegram).

**Definition of done:**
- Open `localhost:8080` and see your job history.
- Click a job to see its tool calls.
- See pending approvals (but approve them in Telegram).
- See skill registry with enable/disable status.

---

## Future phases (not planned in detail)

| Phase | Description |
|-------|-------------|
| Cron jobs | Scheduled recurring prompts (daily summary, backups, etc.) |
| Swarm mode | Multi-agent for complex tasks (research + implement + review) |
| Voice messages | Telegram voice -> transcription -> Claude |
| File handling | Photos/documents sent to bot -> processed by Claude |
| Multi-user | Support multiple authorized Telegram users (separate threads/permissions) |
| Mobile dashboard | PWA version of the web dashboard |

---

## Language choice

**Python** for the initial build. Reasons:

- `python-telegram-bot` is mature and well-documented.
- `subprocess` module handles Claude CLI spawning cleanly.
- SQLite support is built into the standard library.
- Skill executors are Python by default (trivial to run).
- Fast to prototype, easy to read, easy to hand off.

If performance becomes an issue (unlikely for single-user), specific components can be rewritten. But Python is the right call for "get it working and keep it simple."
