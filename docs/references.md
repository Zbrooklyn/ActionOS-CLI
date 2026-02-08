# References

Patterns stolen from OpenClaw, LiteClaw, and existing Telegram+Claude bots. What to adopt, what to skip, and what changes our architecture.

## OpenClaw Core Templates

Source: [openclaw/openclaw](https://github.com/openclaw/openclaw) — `docs/reference/templates/`

OpenClaw's core innovation is a **file-based prompt workspace**: agent behavior lives in markdown files that get injected into the system prompt at session start. Not hardcoded, not in a database — just files in `~/.openclaw/workspace/`.

### The 8 template files

| File | Purpose | Injected into prompt? |
|------|---------|----------------------|
| **SOUL.md** | Agent personality, values, behavioral boundaries ("who you are") | Yes — gets special treatment in prompt builder |
| **AGENTS.md** | Operational manual — session startup protocol, memory rules, safety guardrails | Yes — primary system instructions |
| **IDENTITY.md** | Self-description card: name, creature type, vibe, emoji, avatar | Yes |
| **USER.md** | Evolving profile of the human (name, timezone, preferences, context) | Yes |
| **TOOLS.md** | Environment-specific config (SSH hosts, device names, camera locations) | Yes |
| **BOOTSTRAP.md** | First-run onboarding conversation — then deletes itself | Only if present |
| **BOOT.md** | Startup checklist (what to do on every launch) | Yes |
| **HEARTBEAT.md** | Periodic task definitions (YAML frontmatter + task list) | Config for heartbeat system |

### Key patterns worth stealing

**1. File-based prompt workspace**
Instead of hardcoding agent behavior, use editable markdown files. They're versionable (git), human-readable, and the agent itself can update them.

**ActionOS-CLI adoption:** Done. Created `workspace/` directory with:
- `SOUL.md` — agent personality, values, behavioral rules
- `USER.md` — evolving human profile (name, timezone, preferences)
- `MEMORY.md` — curated long-term memory (decisions, learnings, facts)
- `BOOT.md` — startup checklist (merged from OpenClaw's AGENTS.md)
- `BOOTSTRAP.md` — first-run onboarding (bootstrap-then-delete)

These are read and concatenated into `--append-system-prompt` on every invocation. See [Workspace](workspace.md).

**2. Two-tiered memory**
- `memory/YYYY-MM-DD.md` — raw daily conversation logs
- `MEMORY.md` — curated wisdom distilled from daily logs

The agent periodically reviews daily logs and updates MEMORY.md with significant learnings. This prevents unbounded context growth while preserving important information.

**3. Bootstrap-then-delete onboarding**
BOOTSTRAP.md guides first-run setup through natural conversation ("Hey, I just came online. Who am I?"), populates IDENTITY.md and USER.md, then deletes itself. Elegant way to handle first-time setup.

**4. Lazy skill loading**
52+ skills but only one is loaded per invocation. The agent sees a list of names + descriptions, picks the relevant one, then reads its SKILL.md. Keeps prompt size manageable.

**ActionOS-CLI adoption:** We already do this — skill descriptions in the system prompt, full manifest loaded on demand.

**5. Prompt mode tiers**
- **full** — all workspace files (main agent)
- **minimal** — AGENTS.md + TOOLS.md only (subagents)
- **none** — single identity line only

Subagents get less context = lower cost + security isolation.

**6. SOUL.md gets special treatment**
The prompt builder specifically checks for SOUL.md's existence and triggers additional persona guidance when found. It's the only file checked by name.

### Patterns we skip

- **Dev-mode personality swapping** (`.dev.md` variants) — fun but unnecessary for v1
- **Group chat behavior rules** — we're single-user
- **Cross-session messaging** — we have one agent, not a fleet

---

## LiteClaw

Source: [Pr0fe5s0r/LiteClaw](https://github.com/Pr0fe5s0r/LiteClaw) — `src/liteclaw/`

LiteClaw is a lightweight OpenClaw clone in Python + Node.js. ~20 source files. Uses OpenAI-format function calling with a streaming tool-call accumulation loop.

### Architecture

```
[User] <--WhatsApp/Telegram/Slack--> [bridge/index.js :3040]
                                           |
                                      HTTP POST
                                           |
                                     [main.py FastAPI :8009]
                                           |
                                     [agent.py LiteClawAgent]
                                      /    |    \
                              [tools.py] [memory.py] [subagent.py]
                                           |
                                      [db.py SQLite]

Background daemons:
  [heartbeat.py] — periodic tasks from HEARTBEAT.md
  [subconscious.py] — autonomous self-reflection
  [scheduler.py] — cron jobs via APScheduler
```

### Key patterns worth stealing

**1. Typing indicator loop**
An asyncio task sends Telegram "typing" action every 4 seconds while the agent thinks. Telegram's typing indicator expires after ~5 seconds, so this provides continuous feedback.

**ActionOS-CLI adoption:** Direct copy. Send `typing` every 4-5s while Claude CLI subprocess is running.

**2. Consecutive failure halt**
After 3 consecutive tool failures, inject a `[SYSTEM HALT]` message forcing the LLM to stop and reflect before retrying. Prevents infinite retry loops.

**ActionOS-CLI adoption:** If we detect Claude making the same failing tool call repeatedly (from `stream-json` events or from result text), inject a "stop and reconsider" message on resume.

**3. Layered system prompt**
Static identity (AGENT.md) + dynamic memories (SOUL, PERSONALITY, LEARNING) rebuilt on every message. Memory updates are immediately reflected.

**ActionOS-CLI adoption:** Our `--append-system-prompt` already supports this. Add workspace file reading.

**4. Four-tier memory system**
- **SOUL.md** — facts about the user
- **PERSONALITY.md** — agent's own evolving persona
- **SUBCONSCIOUS.md** — innovation ideas, error patterns
- **LEARNING.md** — best practices, workflow optimizations

All are plain markdown files the agent can read and update.

**5. Message deduplication (two layers)**
- In-memory set (capped at 1000) for webhook dedup
- Before DB insert, check if last message is identical (same role, content)

**6. Command blocklist**
Regex patterns blocking `rm -rf /`, `kill python`, self-termination commands. Essential if the bot executes shell commands.

**7. Fresh session per cron job**
Each cron execution creates a unique session ID (`cron_{job_id}_{uuid}`). Prevents context pollution between scheduled runs.

**ActionOS-CLI adoption:** Already in our design (cron jobs get dedicated threads).

**8. Platform-agnostic backend**
Python backend never knows about WhatsApp/Telegram specifics. The Node.js bridge handles platform translation. If you add Discord later, only the bridge changes.

**ActionOS-CLI adoption:** Not needed for v1 (Telegram only), but keep the ingress layer clean so this is possible later.

### Patterns we skip

- **Subconscious/innovation loop** — autonomous self-reflection every 30-60 min is cool but out of scope
- **Vision agent** — desktop control via screenshots, not relevant for Telegram
- **Selenium WhatsApp client** — legacy approach, we use Telegram API directly

---

## Telegram + Claude Bot Implementations

### 1. TSGram MCP (`areweai/tsgram-mcp`)

**Verdict: AVOID as a starting point.**

Despite the name, the AI bot calls **OpenRouter API** (not Claude Code). It's an API-key proxy, not a CLI integration. The only Claude Code component is a fragile **named pipe hack** that injects Telegram messages into a running Claude process's stdin via `mkfifo`.

**What to steal:**
- Secret redaction regex patterns (filter API keys, tokens, DB URLs before sending to Telegram)
- That's it

**What to avoid:**
- OpenRouter API key requirement (violates our "no API key" principle)
- Named pipe IPC (fragile, platform-specific)
- Docker-heavy deployment (7 compose files for a chat relay)
- No real conversation memory (one system + one user message per request)

### 2. claude-telegram-bot (`linuz90/claude-telegram-bot`)

**Verdict: BEST reference implementation. ~3,300 lines of TypeScript.**

Uses the **official Claude Agent SDK** (`@anthropic-ai/claude-agent-sdk`) with `query()` for streaming events. CLI auth by default. No API key needed.

**Core invocation:**
```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

const instance = query({
  prompt: userMessage,
  options: {
    cwd: workingDir,
    permissionMode: "bypassPermissions",
    allowDangerouslySkipPermissions: true,
    resume: sessionId || undefined,
    systemPrompt: safetyPrompt,
    abortController: abortController,
  },
});

for await (const event of instance) {
  // Process: assistant messages, tool_use, thinking, result
}
```

**What to steal:**

| Pattern | Description |
|---------|-------------|
| Agent SDK `query()` with streaming | Typed events, no subprocess hacking, native resume |
| `permissionMode: "bypassPermissions"` + own safety layer | Bypass SDK prompts, add your own tool interception |
| Tool interception in streaming loop | Inspect every `tool_use` block BEFORE execution |
| AbortController for cancellation | Clean `/cancel` implementation |
| Session resume via `resume` option | Store session ID, pass on next call |
| Crash retry (fresh session on exit code error) | Automatic recovery |
| `ask_user` MCP tool | File-based IPC for inline keyboard questions |
| Sequentialized message processing | Prevent race conditions per chat |

**What to avoid:**
- `allowDangerouslySkipPermissions: true` without documenting the risk
- Hardcoded Italian strings in session flow

### 3. claude-code-telegram (`RichardAtCT/claude-code-telegram`)

**Verdict: Good patterns, over-engineered. ~4-6K lines of Python.**

Uses Python `claude-code-sdk` with CLI subprocess fallback. Most sophisticated session management of the three.

**What to steal:**

| Pattern | Description |
|---------|-------------|
| SDK-to-subprocess fallback | Try SDK first, fall back to `claude -p --output-format stream-json` |
| `_build_command()` for CLI invocation | Exact subprocess flags reference |
| Auto-resume by user+directory | Find most recent session without explicit ID |
| Session expiry + LRU eviction | Automatic cleanup of old sessions |

**What to avoid:**
- Abstract `SessionStorage` base class, facade pattern, dependency injection — enterprise patterns for a chat relay
- `ANTHROPIC_API_KEY` as a first-class option
- Feature flags for everything
- SQLite session persistence (SDK manages history internally)

---

## Architectural Decision: Subprocess Only (No Agent SDK)

### Why not the Agent SDK?

The Claude Agent SDK (`claude-code-sdk`) requires `permissionMode: "bypassPermissions"` for non-interactive use. This:
- Disables Claude Code's built-in permission system entirely
- Shifts the safety boundary from Claude Code (hardened, maintained by Anthropic) to our code (new, less tested)
- Requires `allowDangerouslySkipPermissions: true` — the flag name is a warning

With our subprocess approach using `--allowedTools "Read,Glob,Grep"`:
- Claude **literally cannot** use Write, Edit, or Bash. The CLI enforces it.
- Even if our orchestrator has a bug, Claude can't escape the tool restriction.
- The safety boundary is in Claude Code itself, not in our code.

Additionally, the Agent SDK docs state: "Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products." While we're a personal tool (not a product), using the raw CLI binary is the cleanest path — we are Claude Code, not a wrapper pretending to be.

### Decision

**Subprocess only.** `claude --print --output-format json --resume`. Two-pass approval for tool escalation. The runner is built as a clean abstraction so adding Gemini CLI and Codex CLI later is a new module, not a rewrite.

See [Policy](policy.md) for the full auth and TOS analysis.

---

## Skills Ecosystem Reference

### OpenClaw skills structure

Source: [openclaw/skills](https://github.com/openclaw/skills)

Each skill is a directory with at minimum a `SKILL.md`:

```yaml
# Frontmatter
name: skill-identifier
description: brief summary
metadata:
  openclaw:
    emoji: [emoji]
    requires:
      anyBins: [dependencies]
```

Body contains: parameter tables, quick start examples, tool-specific subsections, advanced patterns, rules/constraints, and a "learnings" section with dated insights.

### LiteClaw skills structure

Skills are single markdown files in `skills/` that get injected into the agent prompt. Much simpler than OpenClaw — no manifest, no code, just prompt text.

### Our approach (comparison)

| Feature | OpenClaw | LiteClaw | ActionOS-CLI |
|---------|----------|----------|--------------|
| **Format** | Directory with SKILL.md | Single markdown file | Directory with manifest.json + run.py |
| **Execution** | Built-in tools + shell | LLM decides + shell | Orchestrator subprocess (no shell for Claude) |
| **Discovery** | Lazy load (read one at a time) | All loaded into prompt | Descriptions in prompt, full manifest on demand |
| **Permissions** | Minimal (sandbox option) | None (runs as agent) | Tiered (read/write/execute/system) + approval |
| **Install** | ClawHub marketplace | Manual copy | Agent proposes + user approves |
| **Self-extending** | Yes (community marketplace) | No | Yes (agent proposes, human approves) |

---

## Full repo links

### OpenClaw
- Core: https://github.com/openclaw/openclaw
- Templates: https://github.com/openclaw/openclaw/tree/main/docs/reference/templates
- Skills: https://github.com/openclaw/skills
- Docs: https://docs.openclaw.ai/reference/templates/SOUL

### LiteClaw
- Source: https://github.com/Pr0fe5s0r/LiteClaw/tree/main/src/liteclaw

### Telegram + Claude bots
- TSGram MCP: https://github.com/areweai/tsgram-mcp — **avoid** (uses OpenRouter, not Claude Code)
- claude-telegram-bot: https://github.com/linuz90/claude-telegram-bot — **best reference** (~3.3K lines, Agent SDK)
- claude-code-telegram: https://github.com/RichardAtCT/claude-code-telegram — **good patterns, over-engineered** (~4-6K lines, Python SDK + CLI fallback)

### Other mentioned repos
- ccswarm: https://github.com/nwiizo/ccswarm — Claude Code orchestration + git worktree isolation
- claude-flow: https://github.com/ruvnet/claude-flow — Multi-agent swarm platform
- awesome-agent-skills: https://github.com/kodustech/awesome-agent-skills — Skill packaging patterns
