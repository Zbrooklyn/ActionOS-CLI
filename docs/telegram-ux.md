# Telegram UX

How the bot behaves in Telegram — commands, message formats, approval buttons, and error states.

## Bot setup

- Created via BotFather.
- Uses **long polling** (`getUpdates`), not webhooks. No public IP needed.
- Single-user: only responds to your Telegram user ID (configured in `config/default.toml`).
- All other messages are silently ignored (no "unauthorized" reply — don't reveal the bot exists to strangers).

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message + status check (CLI auth, DB, skills count) |
| `/status` | Current job queue: running, queued, needs_approval, recent completed |
| `/skills` | List enabled skills with tier and description |
| `/jobs` | Recent jobs: last 10 with status, duration, cost |
| `/cancel` | Cancel the currently running job (sends SIGTERM to CLI process) |
| `/clear` | Start a new Claude session (drops session, next message creates fresh one) |
| `/dev` | Toggle dev mode — expanded tools (Write, Edit, Bash) for skill building |
| `/mode` | Show current mode (normal or dev) |
| `/help` | List available commands |

## Message handling

### Incoming message (you -> bot)

1. Any non-command text message becomes a prompt for Claude.
2. Photos/documents: acknowledged with "File received, but file processing is not yet supported." (future: OCR, file analysis).
3. Voice messages: same — acknowledged, not processed yet.
4. Edits to previous messages: ignored (no re-processing).

### Outgoing message (bot -> you)

Three message types, each visually distinct:

#### 1. Claude response

Plain text. No prefix, no decoration. Just Claude's reply as-is.

If the response exceeds 4096 characters (Telegram's limit):
- Split at paragraph boundaries.
- Send as multiple messages with a small delay (500ms) to preserve order.
- If it contains code blocks, never split mid-block.

#### 2. System message

Prefixed with a label to distinguish from Claude output:

```
[System] Job queued. Position: 1
[System] Job started. Resuming session.
[System] Job completed in 3.2s ($0.002, 1.2k tokens)
[System] Job failed: Claude CLI returned an error. Check /status for details.
[System] Job timed out after 120s.
[System] Session lost. Starting fresh.
```

#### 3. Approval request

**For tool escalation (two-pass approval):**

When Claude needs write/execute tools beyond the default read-only set:

```
Approval needed

Claude analyzed the task and wants to proceed with:
"Edit main.py line 42 to fix the null check, then run tests."

This requires: Write, Edit, Bash
Current permissions: Read-only

[Approve] [Deny]
```

Approving triggers pass 2: `--resume` with escalated `--allowedTools`.

**For skill execution (write+ tier):**

```
Approval needed

Claude wants to use skill: notes (tier: write)
Action: Create note "meeting-notes" in data/notes/

[Approve] [Deny]
```

**For new skill proposals:**

```
New skill proposed

Name: github-issues
Tier: read
Permissions: network (yes), filesystem (no), shell (no)
Description: Search and read GitHub issues for a repository.
Risk: low

[Approve] [Sandbox Only] [Reject] [View Code]
```

## Inline keyboard buttons

All approval buttons use Telegram's `InlineKeyboardMarkup` with callback data:

| Button | Callback data | Action |
|--------|--------------|--------|
| Approve | `approve:<approval_id>` | Approve and execute (escalate tools or run skill) |
| Deny | `deny:<approval_id>` | Reject, resume Claude with "Denied. Suggest alternative." |
| Sandbox | `sandbox:<approval_id>` | Approve but force sandbox execution |
| View Code | `viewcode:<approval_id>` | Send skill source as a message |
| Sandbox Only | `sandboxonly:<approval_id>` | Approve skill but force `sandbox: true` |
| Reject | `reject:<approval_id>` | Reject skill proposal |

### Button behavior

- Buttons are **one-use**: after tapping, the message is edited to show the result and buttons are removed.
- Example after approval:
  ```
  Approval needed

  Claude analyzed the task and wants to proceed with:
  "Edit main.py line 42 to fix the null check."

  Approved at 14:32. Executing with escalated permissions.
  ```
- If no response within 10 minutes, the approval times out and the job is marked `TIMED_OUT`.

## Typing indicator

- When a job is `RUNNING`, the bot sends a "typing" action to Telegram every 5 seconds.
- This gives you visual feedback that something is happening.

## Error messages

| Scenario | Message |
|----------|---------|
| CLI not found | `[System] Claude CLI is not installed or not in PATH. Run "npm install -g @anthropic-ai/claude-code" on the server.` |
| Auth expired | `[System] Claude CLI auth expired. Run "claude login" on the server.` |
| Rate limited | `[System] Rate limit reached. Job queued, will retry in {N}s.` |
| Job failed | `[System] Job failed: {error_message}. Use /jobs to see details.` |
| Timeout | `[System] Job timed out after {N}s. Try breaking the task into smaller steps.` |
| Budget exceeded | `[System] Job hit budget limit (${budget}). Use /jobs to see details.` |
| Turn limit hit | `[System] Job hit turn limit ({N} turns). Task may need to be broken down.` |
| Session corrupted | `[System] Previous session was lost. Starting fresh.` |
| Unknown error | `[System] Unexpected error. Logged for debugging. Job ID: {id}` |

## Thread model

- Each Telegram chat (private chat with the bot) is one thread.
- If you use Telegram's "Topics" feature in a group, each topic is a separate thread.
- Each thread gets its own Claude CLI session (stored as `session_id` from CLI response).
- `/clear` resets the session for the current thread only (sets `session_id` to NULL, next message creates a fresh session).

## Cron output

Cron jobs send output to dedicated threads, not your main conversation:

```
[Cron: daily-summary] Here's your summary for today...
```

```
[Reminder] Meeting with Alex in 15 minutes.
```

These are clearly labeled and never pretend to be Claude responses to your messages.

If a cron job fails:

```
[Cron: daily-backup] Job failed: timeout after 120s. Check /jobs for details.
```

## Message ordering

Telegram does not guarantee message order in all cases. Our approach:
- We process messages in the order received by our polling loop.
- If two messages arrive for the same thread while a job is running, the second is queued (not dropped).
- We never reorder or deduplicate based on Telegram's message ID — only based on our own dedup window (same content within 5s).
