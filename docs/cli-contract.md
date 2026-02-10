# CLI Contract

How ActionOS-CLI invokes Claude CLI, what it sends, and what it expects back.

## Core principle

Claude CLI is a **black box subprocess**. We spawn it, pipe input, capture output, and parse JSON. We never patch, fork, or monkey-patch the CLI binary. If Claude CLI changes its output format, we update our parser — we don't work around it.

## Invocation

### First message in a thread (new session)

```bash
echo "<prompt>" | claude --print \
  --output-format json \
  --max-turns 5 \
  --max-budget-usd 0.50 \
  --append-system-prompt "<orchestrator_instructions>" \
  --allowedTools "Read,Glob,Grep"
```

This creates a new session. The `session_id` is returned in the JSON response — we store it for future use.

### Subsequent messages (resume session)

```bash
echo "<prompt>" | claude --print \
  --output-format json \
  --resume <session_id> \
  --max-turns 5 \
  --max-budget-usd 0.50 \
  --append-system-prompt "<orchestrator_instructions>" \
  --allowedTools "Read,Glob,Grep"
```

`--resume <session_id>` continues the existing conversation. Claude CLI manages its own conversation history internally. We don't replay messages — the CLI remembers.

### Continue most recent session (alternative)

```bash
echo "<prompt>" | claude --print \
  --output-format json \
  --continue \
  --max-turns 5
```

`--continue` resumes the most recent session without needing the session ID. Useful as a fallback, but we prefer explicit `--resume` for reliability.

### With escalated tools (after approval)

```bash
echo "Approved. Proceed with the file write." | claude --print \
  --output-format json \
  --resume <session_id> \
  --max-turns 10 \
  --max-budget-usd 1.00 \
  --append-system-prompt "<build_mode_instructions>" \
  --allowedTools "Read,Write,Edit,Glob,Grep"
```

After the user approves a risky action, we resume the same session with an expanded `--allowedTools` list and a higher budget/turn limit.

## Flags reference

| Flag | Required | Purpose |
|------|----------|---------|
| `--print` / `-p` | Yes | Non-interactive mode, output to stdout |
| `--output-format json` | Yes | Structured JSON response (also supports `stream-json`) |
| `--resume <session_id>` | For continuity | Resume an existing conversation by session UUID |
| `--continue` | Alternative | Resume most recent session (no ID needed) |
| `--max-turns <n>` | Recommended | Cap agent loop iterations (default: 5 for us) |
| `--max-budget-usd <n>` | Recommended | Hard spending cap per invocation |
| `--allowedTools <list>` | Recommended | Allowlist specific tools (comma or space separated) |
| `--disallowedTools <list>` | Optional | Blocklist specific tools (complement to allowedTools) |
| `--append-system-prompt <text>` | Yes | Add orchestrator instructions while preserving Claude's built-in prompt |
| `--append-system-prompt-file <path>` | Alternative | Read append prompt from file |
| `--model <id>` | Optional | Override model (alias like `sonnet` or full ID) |
| `--json-schema <schema>` | Optional | Force structured output matching a JSON schema |

### Important: `--append-system-prompt` vs `--system-prompt`

- **`--system-prompt`** replaces Claude's entire built-in system prompt. This strips Claude of knowing how to use its own tools (Read, Edit, Bash, etc.). **Do not use this.**
- **`--append-system-prompt`** adds to the default prompt, preserving all built-in capabilities. **Always use this.**

### Important: `--session-id` vs `--resume`

- **`--session-id <uuid>`** sets the UUID for a **new** session. It does not resume an existing one.
- **`--resume <session_id>`** continues an existing session. This is what we use for conversation continuity.

We use `--session-id` only once (optionally, to force a specific UUID on first message). After that, it's `--resume` for all subsequent messages.

## Expected JSON output

Claude CLI with `--output-format json` returns a JSON object. Actual shape:

```json
{
  "type": "result",
  "subtype": "success",
  "session_id": "abc123-def456-...",
  "uuid": "msg-uuid-here",
  "result": "The assistant's final text reply.",
  "total_cost_usd": 0.03988,
  "duration_ms": 3302,
  "duration_api_ms": 2918,
  "num_turns": 2,
  "is_error": false,
  "usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "cache_read_input_tokens": 890
  }
}
```

### Fields we use

| Field | Type | How we use it |
|-------|------|---------------|
| `result` | string | Sent back to Telegram as the reply |
| `session_id` | string | Stored in `threads` table for `--resume` on next message |
| `subtype` | string | `"success"`, `"error_max_turns"`, `"error_during_execution"`. Determines job status. |
| `total_cost_usd` | float | Logged per job for tracking |
| `duration_ms` | int | Total wall clock time. Logged per job. |
| `duration_api_ms` | int | Time spent in API calls only. Logged for analysis. |
| `num_turns` | int | Logged, compared against `--max-turns` |
| `is_error` | bool | If true, job marked FAILED, error sent to user |
| `uuid` | string | Unique message ID. Stored for dedup and audit. |
| `usage` | object | Token counts. Logged for cost analysis. |
| `usage.input_tokens` | int | Input tokens consumed |
| `usage.output_tokens` | int | Output tokens generated |
| `usage.cache_read_input_tokens` | int | Tokens served from prompt cache |

### Subtype handling

| Subtype | Meaning | Job status |
|---------|---------|------------|
| `success` | Completed normally | `completed` |
| `error_max_turns` | Hit `--max-turns` limit before finishing | `failed` (with note: "Hit turn limit") |
| `error_during_execution` | Error during tool use or generation | `failed` (log error details) |

## Error handling

### CLI process errors

| Scenario | Detection | Action |
|----------|-----------|--------|
| CLI not found | spawn fails, ENOENT | Job FAILED, alert user "Claude CLI not installed" |
| Auth expired | stderr contains auth error | Job FAILED, alert user "Run `claude login`" |
| Rate limited | exit code or stderr | Job retried with backoff (5s, 15s) |
| Timeout | process exceeds `timeout_ms` | SIGTERM, wait 5s, SIGKILL. Job TIMED_OUT |
| Budget exceeded | `subtype: "error_max_turns"` or cost check | Job FAILED, notify user |
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

## System prompt construction

The `--append-system-prompt` value is built by the orchestrator from multiple sources:

### Prompt assembly order (normal mode)

```
1. workspace/SOUL.md         (personality — if exists)
2. workspace/IDENTITY.md     (identity card — if exists)
3. workspace/USER.md         (human profile — if exists)
4. workspace/MEMORY.md       (curated long-term memory — if exists)
5. workspace/TOOLS.md        (environment notes — if exists)
6. workspace/AGENTS.md       (operations manual — if exists)
7. workspace/BOOT.md         (startup checklist — or BOOTSTRAP.md if first run)
8. Mode-specific instructions (see templates below)
9. Skill descriptions        (from loaded skill manifests)
10. Orchestrator instructions (skill_call format, constraints)
```

### Prompt assembly order (dev mode)

```
1-7: Same as normal, but SOUL.dev.md, IDENTITY.dev.md, AGENTS.dev.md
     are loaded instead of their base files.
8.   Build mode instructions
9-10: Same as normal.
```

All workspace files are optional. If missing, the agent runs with mode-specific instructions only. See [Workspace](workspace.md) for file details.

### Mode templates

These are appended AFTER workspace files.

**Default (general assistant):**

```
You have read-only access to files. If a task requires writing files, running commands,
or any action beyond reading — describe exactly what you would do and wait for approval.
Do not attempt to execute actions you don't have tools for.

Available custom skills:
{skill_descriptions}

To use a skill, include a JSON block in your response:
{"skill_call": {"name": "<skill_name>", "inputs": {<inputs>}}}

If you need a capability that isn't available, you may propose a new skill.
To propose, include a JSON block:
{"skill_proposal": {"name": "...", "description": "...", "tier": "...", "code": "...", "rationale": "..."}}
```

**Research mode:**

```
Your job is to find information and summarize it.
You have access to: Read, Glob, Grep, WebSearch, WebFetch.
Do not modify any files. Report your findings concisely.
```

**Build mode (after user approval):**

```
The user has approved execution for this task.
You may use: Read, Write, Edit, Bash, Glob, Grep.
Make minimal changes. Do not refactor beyond what was asked.
Commit messages should be clear and concise.
```

## Session management

- **First message:** Invoke Claude without `--resume`. Capture `session_id` from JSON response. Store in `threads` table.
- **Subsequent messages:** Use `--resume <session_id>`. Claude CLI handles context internally.
- **`/clear` command:** Generate a new session by dropping `--resume` on next invocation. Update `threads.session_id` with the new ID from the response.
- **Corrupted session:** If `--resume` fails (CLI returns error), fall back to a fresh session. Notify user: "Previous session was lost. Starting fresh."
- **Session storage:** Claude CLI stores sessions in `~/.claude/projects/`. We don't manage these files — the CLI handles expiry.

## Cost tracking

Every job logs `total_cost_usd` and `usage` from the CLI output. The orchestrator can:

- Sum daily/weekly/monthly costs.
- Alert if a single job exceeds a threshold (configurable, default $0.50).
- Alert if daily total exceeds a threshold (configurable, default $5.00).
- Use `--max-budget-usd` to hard-cap individual invocations.

This is informational — since there's no API billing, cost reflects the CLI's internal estimate against your subscription. The `--max-budget-usd` flag is still useful as a runaway prevention mechanism.

## Stream JSON mode (future)

For real-time feedback, `--output-format stream-json` emits events as they happen:

```json
{"type": "assistant", "message": {"content": [{"type": "text", "text": "Let me..."}]}}
{"type": "tool_use", "tool": "Read", "input": {"file_path": "/foo"}}
{"type": "tool_result", "output": "..."}
{"type": "result", "subtype": "success", "result": "...", "total_cost_usd": 0.02}
```

This would allow real-time "typing" in Telegram and mid-execution visibility. Not needed for v1, but the architecture should not preclude it.
