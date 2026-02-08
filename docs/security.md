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
| **Runaway execution** | Claude enters an infinite tool-call loop or burns budget | Resource exhaustion, cost |
| **Data leakage** | Sensitive data in notes/files sent to Claude, then to a third party | Privacy violation |
| **Skill escape** | A skill accesses files/network outside its declared permissions | Lateral movement |

## Hard rules (non-negotiable)

### 1. No auto-install of skills

Skills proposed by the agent are **never** activated without explicit user approval via Telegram buttons. There is no `--auto-approve` flag. There is no "trust this author" bypass. Every new skill goes through the approval flow.

### 2. No unrestricted shell access by default

Claude CLI's `Bash` tool is **not** in the default `--allowedTools` list. Shell access is only available when:
- The job is explicitly an approved "build mode" task, AND
- The user has approved it via the two-pass approval flow for this specific invocation.

### 3. No Claude API key in the system

All inference goes through `claude` CLI with its native OAuth. No API key is stored, configured, or passed. If the CLI's auth expires, the system stops and tells you to re-login. It does not attempt to authenticate on your behalf.

### 4. Single user only

The bot responds **only** to the configured Telegram user ID. All other messages are silently dropped — no error message, no acknowledgment. The bot does not reveal its existence to unauthorized users.

### 5. Everything is logged

Every job, tool call, approval decision, and error is written to SQLite. Logs are never silently dropped. If a write fails, the job fails.

### 6. Default tools are read-only

The default `--allowedTools` for any job is: `Read, Glob, Grep`. Write and execute tools are added only through the two-pass approval flow. Each approval is scoped to a single job — permissions are never sticky.

### 7. Timeouts and budgets are enforced

Every Claude CLI subprocess has:
- A hard timeout (default: 120s, configurable). Process is killed if exceeded.
- A `--max-turns` limit (default: 5). Prevents infinite agent loops.
- A `--max-budget-usd` limit (default: $0.50). Prevents runaway cost.

There is no "unlimited" mode for any of these.

### 8. No spoofing

- Every Telegram message is labeled: Claude response, system message, or approval request.
- Cached or templated responses are never disguised as live Claude output.
- If a skill fails, the failure is reported honestly — never a fake success.
- The audit log cannot be retroactively edited.

### 9. System prompt is append-only

We use `--append-system-prompt`, never `--system-prompt`. This preserves Claude CLI's built-in safety behaviors and tool-use instructions. The orchestrator cannot strip Claude's defaults — only add to them.

### 10. Claude cannot execute skills directly

Custom skills are run by the orchestrator, not by Claude CLI. Claude can only request a skill via a structured JSON block in its response. The orchestrator validates, checks permissions, and executes. This prevents Claude from being tricked into running arbitrary code via prompt injection.

## Permission model

### Tool tiers

| Tier | Default state | Approval | Revocation |
|------|--------------|----------|------------|
| read | Allowed | None needed | Can be removed from allowlist |
| write | Blocked | One-time per skill | Remove from skills table |
| execute | Blocked | Per invocation | Automatic after job completes |
| system | Blocked | Per invocation + sandbox | Automatic after job completes |

### Two-pass escalation flow

```
User message arrives
  |
  v
Orchestrator assigns default tools (read-only: Read, Glob, Grep)
  |
  v
Pass 1: Claude responds with read-only tools
  |-- No escalation needed --> reply directly
  |-- Skill call (read tier) --> orchestrator executes, feeds result back
  |-- Skill call (write+ tier) --> approval request, then execute if approved
  |-- Needs write/execute tools --> describes what it wants to do
       |
       v
    Orchestrator detects escalation request
       |
       v
    Approval request sent to Telegram
       |
       v
    User approves --> Pass 2: --resume with escalated --allowedTools
    User denies --> inform Claude via --resume: "Denied. Suggest alternative."
```

**Why two passes?** Claude CLI executes built-in tools during its agent loop. There's no mid-execution interception with `--print` mode. By restricting tools on pass 1, Claude can only describe what it wants. Pass 2 gives it the tools to act — only after you approve.

### De-escalation

After a job completes, any escalated permissions are revoked. The next job in the same thread starts with default (read-only) permissions again. There is no "remember my approval for this thread" — each job is a clean slate.

## Skill security

### Before approval

- Skill code is shown to the user in full (via "View Code" button).
- Manifest is validated: required fields present, tier matches declared permissions.
- `system`-tier skills with `sandbox: false` are rejected automatically.
- Skill names are validated: lowercase, hyphens only, no path traversal characters.

### During execution

- Skills are executed by the orchestrator as a subprocess, never in the orchestrator's own process.
- Sandboxed skills run in Docker with:
  - Memory limit (256MB default)
  - CPU limit (0.5 cores default)
  - No network (unless `permissions.network: true`)
  - Read-only filesystem (unless `permissions.filesystem` includes `"write"`)
  - No access to host filesystem outside declared paths
  - No access to config files, database, or bot token
- Non-sandboxed skills are still restricted to declared `permissions.paths` via working directory isolation.
- Skill execution has its own timeout (default: 30s, separate from the CLI timeout).

### After execution

- Output is captured and logged in `tool_calls` table.
- If the skill produced unexpected output (e.g., tried to write outside its paths), it's flagged in the audit log.
- Skills that fail repeatedly (3+ consecutive failures) are auto-disabled with a notification.
- Skill output is fed back to Claude as a user message — Claude does not see raw stderr or internal errors.

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
- Claude CLI's session data (`~/.claude/`) is not accessible to skills.

## Graceful shutdown and recovery

- On SIGTERM/SIGINT: orchestrator sends SIGTERM to any running Claude CLI subprocess, waits for completion, marks interrupted jobs as `failed` with "interrupted by shutdown".
- On restart: orchestrator scans for jobs in `running` status, marks them as `failed` with "interrupted by restart". These are not automatically retried (user must re-request).
- Approval timeouts are checked on startup — any expired pending approvals are marked `timed_out`.

## What we explicitly do NOT do

| Practice | Why not |
|----------|---------|
| Public skill marketplace | Supply chain attacks. Every skill is local and user-approved. |
| Auto-update skills from remote sources | Same reason. Updates are manual. |
| Run as root | Unnecessary privilege. Run as a regular user. |
| Store conversation history remotely | Privacy. Everything stays in local SQLite. |
| Allow Claude to modify its own system prompt | Prompt injection vector. System prompts are set by the orchestrator only (via `--append-system-prompt`). |
| Allow Claude to approve its own actions | Defeats the purpose. Only the human approves. |
| Trust Claude's self-assessment of risk | The tier system is based on manifest declarations, not on what Claude says is safe. |
| Use `--system-prompt` (replace mode) | Strips Claude's built-in safety behaviors. Always use `--append-system-prompt`. |
| Let Claude call skills directly | Prevents prompt injection from triggering skill execution. Orchestrator is the only executor. |
