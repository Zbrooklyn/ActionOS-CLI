# Security

Hard rules, threat model, and boundaries for ActionOS-CLI.

## Threat model

ActionOS-CLI runs on your machine (or VPS), talks to Telegram, and executes Claude CLI. The threats we design against:

| Threat | Vector | Impact |
|--------|--------|--------|
| **Prompt injection** | Malicious content in fetched URLs, files, or user-forwarded messages tricks Claude into executing unintended actions | Data exfiltration, unauthorized commands |
| **Skill supply chain** | A proposed skill contains malicious code | Arbitrary code execution |
| **Telegram impersonation** | Someone sends messages pretending to be you | Unauthorized agent actions |
| **Session hijacking** | Telegram bot token leaked | Full control of the bot |
| **Runaway execution** | Claude enters an infinite tool-call loop | Resource exhaustion, cost |
| **Data leakage** | Sensitive data in notes/files sent to Claude, then to a third party | Privacy violation |

## Hard rules (non-negotiable)

### 1. No auto-install of skills

Skills proposed by the agent are **never** activated without explicit user approval via Telegram buttons. There is no `--auto-approve` flag. There is no "trust this author" bypass. Every new skill goes through the approval flow.

### 2. No unrestricted shell access by default

Claude CLI's `Bash` tool is **not** in the default `--allowedTools` list. Shell access is only available when:
- The job is explicitly a "build mode" task, AND
- The user has approved it for this specific invocation.

### 3. No Claude API key in the system

All inference goes through `claude` CLI with its native OAuth. No API key is stored, configured, or passed. If the CLI's auth expires, the system stops and tells you to re-login. It does not attempt to authenticate on your behalf.

### 4. Single user only

The bot responds **only** to the configured Telegram user ID. All other messages are silently dropped — no error message, no acknowledgment. The bot does not reveal its existence to unauthorized users.

### 5. Everything is logged

Every job, tool call, approval decision, and error is written to SQLite. Logs are never silently dropped. If a write fails, the job fails.

### 6. Default tools are read-only

The default `--allowedTools` for any job is: `Read, Glob, Grep`. Write and execute tools are added only through the approval gate or explicit job configuration.

### 7. Timeouts are enforced

Every Claude CLI subprocess has a hard timeout (default: 120s). `--max-turns` is always set (default: 5). There is no "unlimited" mode.

### 8. No spoofing

- Every Telegram message is labeled: Claude response, system message, or approval request.
- Cached or templated responses are never disguised as live Claude output.
- If a skill fails, the failure is reported honestly — never a fake success.
- The audit log cannot be retroactively edited.

## Permission model

### Tool tiers

| Tier | Default state | Approval | Revocation |
|------|--------------|----------|------------|
| read | Allowed | None needed | Can be removed from allowlist |
| write | Blocked | One-time per skill | Remove from skills table |
| execute | Blocked | Per invocation | Automatic after job completes |
| system | Blocked | Per invocation + sandbox | Automatic after job completes |

### Escalation flow

```
User message arrives
  |
  v
Orchestrator assigns default tools (read-only)
  |
  v
Claude responds
  |-- No tool calls needed --> reply directly
  |-- Read-tier tool call --> execute, reply
  |-- Write/execute/system tool call --> BLOCK job, request approval
       |
       v
    User approves --> new job with escalated tools
    User denies --> inform Claude, suggest alternative
```

### De-escalation

After a job completes, any escalated permissions are revoked. The next job in the same thread starts with default (read-only) permissions again. There is no "remember my approval for this thread" — each job is a clean slate.

## Skill security

### Before approval

- Skill code is shown to the user in full (via "View Code" button).
- Manifest is validated: required fields present, tier matches declared permissions.
- `system`-tier skills with `sandbox: false` are rejected automatically.

### During execution

- Skills run in a subprocess, not in the orchestrator's process.
- Sandboxed skills run in Docker with:
  - Memory limit (256MB default)
  - CPU limit (0.5 cores default)
  - No network (unless `permissions.network: true`)
  - Read-only filesystem (unless `permissions.filesystem` includes `"write"`)
  - No access to host filesystem outside declared paths
- Non-sandboxed skills are still restricted to declared `permissions.paths`.

### After execution

- Output is captured and logged.
- If the skill produced unexpected output (e.g., tried to write outside its paths), it's flagged in the audit log.
- Skills that fail repeatedly (3+ consecutive failures) are auto-disabled with a notification.

## Telegram security

### Bot token

- Stored in `config/default.toml`, not in environment variables (avoids leaking via `env` in subprocesses).
- The config file should be `chmod 600` (owner read/write only).
- If the token is compromised: revoke via BotFather, generate new token, update config.

### Message validation

- Every incoming update is checked: `message.from.id` must match configured user ID.
- Callback queries (button presses) are also validated against user ID.
- No group chat support in v1 (prevents confusion about who's authorized).

### Rate limiting (inbound)

- Max 1 job per 2 seconds per thread (prevents accidental spam).
- Max 10 jobs per minute globally (prevents runaway if something goes wrong).

## File system boundaries

The orchestrator process runs with the permissions of the user who starts it. To limit blast radius:

- Working directory for Claude CLI is set to a dedicated project folder, not `~/` or `/`.
- Skills can only access paths declared in their manifest.
- The SQLite database file is outside the skills working directory.
- No skill can read the config file (which contains the bot token).

## What we explicitly do NOT do

| Practice | Why not |
|----------|---------|
| Public skill marketplace | Supply chain attacks. Every skill is local and user-approved. |
| Auto-update skills from remote sources | Same reason. Updates are manual. |
| Run as root | Unnecessary privilege. Run as a regular user. |
| Store conversation history remotely | Privacy. Everything stays in local SQLite. |
| Allow Claude to modify its own system prompt | Prompt injection vector. System prompts are set by the orchestrator only. |
| Allow Claude to approve its own actions | Defeats the purpose. Only the human approves. |
| Trust Claude's self-assessment of risk | The tier system is based on manifest declarations, not on what Claude says is safe. |
