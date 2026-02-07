# CLI Contract

How ActionOS-CLI invokes Claude CLI, what it sends, and what it expects back.

## Core principle

Claude CLI is a **black box subprocess**. We spawn it, pipe input, capture output, and parse JSON. We never patch, fork, or monkey-patch the CLI binary. If Claude CLI changes its output format, we update our parser — we don't work around it.

## Invocation

### Basic single-shot

```bash
echo "<prompt>" | claude --print \
  --output-format json \
  --session-id <session_id> \
  --max-turns 1
```

### Threaded conversation (session continuity)

```bash
echo "<prompt>" | claude --print \
  --output-format json \
  --session-id <thread_id>
```

The `--session-id` maps 1:1 with a Telegram thread. Claude CLI manages its own conversation history internally. We don't replay messages — the CLI remembers.

### With tool restrictions

```bash
echo "<prompt>" | claude --print \
  --output-format json \
  --session-id <thread_id> \
  --max-turns 5 \
  --allowedTools "Read,Glob,Grep"
```

Only the listed tools are available to Claude for this invocation. This is how we enforce skill tiers: read-tier jobs get read-only tools, write-tier jobs get more.

### With system prompt (orchestrator instructions)

```bash
echo "<prompt>" | claude --print \
  --output-format json \
  --session-id <thread_id> \
  --system-prompt "You are a personal assistant. Respond concisely. If a task requires file writes or shell commands, describe what you would do but do not execute. The user will approve actions separately."
```

The system prompt is how the orchestrator controls Claude's behavior per job type.

## Flags reference

| Flag | Required | Purpose |
|------|----------|---------|
| `--print` | Yes | Non-interactive mode, output to stdout |
| `--output-format json` | Yes | Structured JSON response |
| `--session-id <id>` | Yes | Conversation continuity per thread |
| `--max-turns <n>` | Recommended | Cap agent loop iterations (default: 5) |
| `--allowedTools <list>` | Recommended | Restrict available tools |
| `--system-prompt <text>` | Optional | Per-invocation orchestrator instructions |
| `--model <id>` | Optional | Override model (default: whatever CLI is configured for) |

## Expected JSON output

Claude CLI with `--output-format json` returns a JSON object. The fields we parse:

```json
{
  "type": "result",
  "session_id": "thread_abc123",
  "result": "The assistant's final text reply.",
  "cost_usd": 0.003,
  "duration_ms": 2450,
  "num_turns": 2,
  "is_error": false
}
```

### Fields we use

| Field | Type | How we use it |
|-------|------|---------------|
| `result` | string | Sent back to Telegram as the reply |
| `session_id` | string | Verified against our thread mapping |
| `cost_usd` | float | Logged per job for tracking |
| `duration_ms` | int | Logged per job, used for timeout tuning |
| `num_turns` | int | Logged, compared against `--max-turns` |
| `is_error` | bool | If true, job marked FAILED, error sent to user |

### Fields we may use later

| Field | Type | Future use |
|-------|------|------------|
| `tool_calls` | array | Audit log, skill usage tracking |
| `model` | string | Log which model was used |
| `token_usage` | object | Cost analysis |

## Error handling

### CLI process errors

| Scenario | Detection | Action |
|----------|-----------|--------|
| CLI not found | spawn fails, ENOENT | Job FAILED, alert user "Claude CLI not installed" |
| Auth expired | stderr contains auth error | Job FAILED, alert user "Run `claude login`" |
| Rate limited | exit code or stderr | Job retried with backoff (5s, 15s) |
| Timeout | process exceeds `timeout_ms` | SIGTERM, wait 5s, SIGKILL. Job TIMED_OUT |
| Invalid JSON | JSON.parse fails | Job FAILED, raw stdout logged for debugging |
| Non-zero exit | exit code != 0 | Job FAILED, stderr logged |

### Timeout strategy

```
1. Spawn subprocess with timer
2. If timer fires:
   a. Send SIGTERM
   b. Wait 5 seconds
   c. If still alive, send SIGKILL
   d. Mark job TIMED_OUT
   e. Send user: "Job timed out after {N}s. The task may have been too complex for a single run."
```

Default timeout: 120 seconds. Configurable per job type.

## System prompt templates

### Default (general assistant)

```
You are a personal assistant running inside ActionOS-CLI.
Respond concisely and directly.
Do not execute file writes or shell commands unless explicitly provided as allowed tools.
If you need to perform a risky action, describe it clearly so the user can approve it.
```

### Research mode

```
You are a research assistant running inside ActionOS-CLI.
Your job is to find information and summarize it.
You have access to: Read, Glob, Grep, WebSearch, WebFetch.
Do not modify any files. Report your findings concisely.
```

### Build mode (approved execution)

```
You are a development assistant running inside ActionOS-CLI.
The user has approved execution for this task.
You may use: Read, Write, Edit, Bash, Glob, Grep.
Make minimal changes. Do not refactor beyond what was asked.
Commit messages should be clear and concise.
```

## Session management

- **Session ID = thread ID** from the state store (UUID).
- Claude CLI persists session state internally (in `~/.claude/` or similar).
- We never delete CLI sessions ourselves — they expire naturally.
- If a session becomes corrupted (repeated errors), the orchestrator can start a fresh session by generating a new UUID and updating the thread mapping.

## Cost tracking

Every job logs `cost_usd` from the CLI output. The orchestrator can:

- Sum daily/weekly/monthly costs.
- Alert if a single job exceeds a threshold (configurable, default $0.50).
- Alert if daily total exceeds a threshold (configurable, default $5.00).

This is informational only — we don't block jobs based on cost (since there's no API billing, cost here reflects the CLI's internal estimate against your subscription).
