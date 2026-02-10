# CLI Comparison

Head-to-head comparison of Claude Code, Gemini CLI, and OpenAI Codex CLI. What each is good at, what each is bad at, and how ActionOS-CLI should route tasks.

## The bottom line

No single CLI wins at everything. The developers getting the best results in 2026 use two or three strategically:

| | Claude Code | Gemini CLI | Codex CLI |
|---|---|---|---|
| **One-liner** | The quality expert | The free researcher | The fast executor |
| **Best at** | Clean code on first try, multi-file edits, debugging | Research, large codebase comprehension, free tier | Speed, token efficiency, sandbox safety, hard agentic tasks |
| **Worst at** | Cost, usage limits, TOS restrictions | Code reliability (40-50% error rate), model regressions | UX polish, code quality, verbose explanation |

## Benchmarks (February 2026)

| Benchmark | Claude Code | Gemini CLI | Codex CLI |
|-----------|------------|------------|-----------|
| **SWE-bench Verified** | **80.9%** (Opus 4.5) | 78% (Gemini 3 Flash) | 80.0% (GPT-5.2) |
| **SWE-bench Pro** | 45.89% (Opus 4.5) | 43.30% (Gemini 3 Pro) | **57%** (GPT-5.3-Codex) |
| **Terminal-Bench 2.0** | 65.4% (Opus 4.6) | N/A | **77.3%** (GPT-5.3-Codex) |
| **Aider Polyglot** | **89.4%** (Opus 4.5) | 82.2% (Gemini 2.5 Pro) | 88% (GPT-5) |

**Reading the benchmarks:**
- SWE-bench Verified = standard bug-fix tasks. Claude and Codex tied at the top.
- SWE-bench Pro = harder multi-file tasks (~107 lines, ~4.1 files). **Codex leads by 11 points.** This is the most meaningful gap.
- Terminal-Bench 2.0 = real terminal tasks. **Codex leads by 12 points.**
- Aider Polyglot = code editing across 6 languages. **Claude leads.** Best at clean, correct edits.

## Built-in tools

| Tool | Claude Code | Gemini CLI | Codex CLI |
|------|------------|------------|-----------|
| Read files | `Read` (dedicated) | Shell | Shell |
| Write files | `Write` (dedicated) | Shell | Shell |
| Edit files | `Edit` (exact string replace) | Shell | `ApplyPatch` (experimental) |
| Search files | `Glob` (dedicated) | Shell | Shell |
| Search content | `Grep` (ripgrep-based) | Shell | Shell |
| Run commands | `Bash` | Shell | Shell |
| Web search | `WebSearch` (built-in) | Google Search grounding | Web search (cached index by default) |
| Web fetch | `WebFetch` (built-in) | Built-in | Via shell |
| Sub-agents | `Task` (built-in) | None | None |
| Notebooks | `NotebookEdit` | None | None |
| MCP servers | Full (HTTP, SSE, Stdio) | Full (STDIO, HTTP) | Full (STDIO, HTTP) |

Claude Code has the richest tool set. Gemini and Codex route most file operations through shell commands.

## Agentic capabilities

This is the most important section for ActionOS-CLI. How each CLI works as an autonomous agent — not just what models they have, but how they think, plan, execute, recover, and manage context.

### Agent loop

| | Claude Code | Codex CLI | Gemini CLI |
|---|---|---|---|
| **Loop type** | Think → Tool Use → Observe → repeat | ReAct inner loop (shell-first) | ReAct loop |
| **Planning** | `TodoWrite` — structured task lists with status tracking, injected as system reminders after each tool call | Implicit in reasoning outputs, no built-in task list | Implicit in reasoning, no built-in task list |
| **Self-correction** | Observes errors, updates plan, retries with different approach | Observes shell output, retries | Observes output, retries. `/introspect` for debugging decisions |
| **Sub-agents** | **Native** — `dispatch_agent` spawns sub-agents with independent context windows. Swarm architecture for parallel execution. | None native — external via Agents SDK. Can run as MCP server for orchestration. | None native — community proposals exist (PR #4883). External orchestration via scripts. |
| **Tool chain limit** | Unlimited — loop runs until model says `end_turn` | Unlimited — inner loop runs until model says `done` | Unlimited within 1M token window |
| **Mid-turn steering** | No | **Yes** — submit messages while Codex is working to redirect in real time | No |

**Why this matters for ActionOS-CLI:** Claude Code's `TodoWrite` and sub-agent system mean it can decompose complex tasks autonomously — crucial for multi-step Telegram requests. Codex's mid-turn steering could enable "cancel and redirect" UX. Gemini's lack of sub-agents means it's better for single-focus tasks.

### Context and memory

| | Claude Code | Codex CLI | Gemini CLI |
|---|---|---|---|
| **Context window** | 200K tokens (1M beta) | ~200K tokens | **1M tokens** |
| **Max output** | 128K tokens (Opus 4.6) | Not disclosed | 64K tokens |
| **Compaction** | Auto at ~75% usage, manual `/compact`. Strips old thinking blocks. | Auto (known stability issues — compaction loops where context drops to ~5%). | Auto + **deliberate goal-directed** (specify what to preserve). Manual `/compress`. |
| **Session resume** | `--resume <session_id>` | `codex resume --last` or `codex resume <id>` | `/chat save` and `/chat resume` |
| **Cross-session memory** | **Automatic Session Memory** — extracts structured summaries, saves to disk, injects into future sessions. + `CLAUDE.md` for project instructions. | `AGENTS.md` for project instructions. Thread archiving. No automatic memory extraction. | `GEMINI.md` for project instructions. User-level memory. No automatic extraction. |
| **Session forking** | No | **Yes** — `/fork` branches from any point in the transcript | No (but has "Rewind" to navigate history) |

**Why this matters for ActionOS-CLI:** Claude Code's automatic session memory means the agent gets smarter over time without us building anything. Gemini's 1M context means fewer compaction cycles for long tasks. Codex's forking could enable "try both approaches" patterns. All three support session resume — critical for our `--resume` based conversation continuity.

### Permission and safety model

| | Claude Code | Codex CLI | Gemini CLI |
|---|---|---|---|
| **Default behavior** | Prompts user for risky actions (file writes, shell, new network domains) | Depends on policy: `suggest` (confirm writes), `auto-edit`, `full-auto` | Depends on mode: `default` (confirm each), `auto_edit`, `yolo`, `plan` (read-only) |
| **Full autonomy** | `--dangerously-skip-permissions` | `--full-auto` (within sandbox) or `--yolo` (no sandbox) | `yolo` mode (but high-priority deny rules still fire) |
| **Tool restrictions** | `--allowedTools` and `--disallowedTools` flags | Approval policies (suggest/auto-edit/full-auto) | Policy engine with per-command allowlists |
| **OS sandbox** | Bubblewrap (Linux), Seatbelt (macOS). Network proxy with domain allowlists. | **Seatbelt (macOS), Landlock+seccomp (Linux).** Dedicated `codex-linux-sandbox` binary. Docker fallback. | Docker, Podman, or Seatbelt. Default was "no sandbox" until security fix in v0.1.14. |
| **Cloud isolation** | No | **Yes — Cloud Codex** runs in fully isolated containers with internet disabled | No |
| **Static analysis** | Pre-execution analysis flags risky commands (84% fewer permission prompts) | No | No |
| **Smart approvals** | Auto-allow for safely sandboxable commands | Auto prefix-rule suggestions on escalation | "Always Allow" persistence per tool |

**Why this matters for ActionOS-CLI:** Our two-pass approval model (pass 1 read-only, approve, pass 2 escalated) maps cleanest to Claude Code's `--allowedTools`. Codex's approval policies work differently — we'd need to translate. Gemini's policy engine is the most configurable but adds complexity.

### Extensibility

| | Claude Code | Codex CLI | Gemini CLI |
|---|---|---|---|
| **MCP servers** | Mature. `mcp__<server>__<action>` naming. | Mature. STDIO + HTTP. Allowlisting for security. | Mature. FastMCP integration. Auto-prefixes conflicting names. |
| **Hooks / callbacks** | **Rich** — `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, `Stop`, `SessionStart`, `SubagentStop`, `Notification` | Limited — event streams for clients, no user-defined middleware | **Rich** — pre-tool-*selection* (before model chooses), pre/post execution. Per-hook toggles. |
| **Custom sub-agents** | `.claude/agents/` markdown files or inline JSON. Background concurrent execution. | External via Agents SDK typed handoffs | None native, external via ADK |
| **Plugins** | Bundles (sub-agents + hooks + MCP + skills + commands) as distributable units | Agent Skills (SKILL.md with progressive disclosure) | Extensions (MCP + GEMINI.md + commands + playbooks) via catalog |
| **Runtime tool creation** | Via MCP + beta "Tool Search Tool" for on-demand discovery | Via MCP + Skills | Via MCP + **skill-creator skill** (generates new skills during a session) |

**Why this matters for ActionOS-CLI:** Claude Code's hooks are the most useful for our architecture — `PreToolUse` could feed into our approval gate, `PostToolUse` into our audit log. Gemini's pre-tool-*selection* hooks are unique and could enable smart tool filtering. Codex has the weakest hook system.

### Multi-step task handling

| | Claude Code | Codex CLI | Gemini CLI |
|---|---|---|---|
| **Task decomposition** | **TodoWrite** — structured JSON task lists with IDs, status, priorities. Current state injected after each tool call. | Implicit in reasoning outputs. No structured system. | Implicit in reasoning. Agent skills provide pre-defined workflows. |
| **Failure recovery** | Updates TODO, adjusts plan, spawns sub-agents for alternative approaches. Task files survive session crashes. | Observes errors, retries. Thread rollback drops last N turns to recover from bad paths. | Observes errors, retries. "Rewind" navigates back to try alternatives. |
| **Swarm / decomposition** | **Orchestrator pattern** — main session delegates to specialized sub-agents with independent context. Solves "context rot" (degradation from accumulated errors/logs). | Single agent loop. 7-hour max sessions with auto-compaction. | Single agent loop. 1M context reduces need for decomposition. |
| **Max complexity** | Highest — swarm architecture pushes past single-context limits | Medium — limited by compaction stability (known stalling issues) | Medium — large context compensates but no sub-agent delegation |

**Why this matters for ActionOS-CLI:** For complex Telegram requests ("refactor my auth system"), Claude Code can autonomously decompose into sub-tasks and delegate. Codex and Gemini will attempt it in one pass. This is Claude's strongest differentiator as an agent.

### Unique agentic features (what each can do that others can't)

**Claude Code:**
- Native sub-agent spawning with swarm architecture — no other CLI has built-in multi-agent orchestration
- `TodoWrite` as a first-class planning tool — persistent task tracking injected into context
- Automatic Session Memory — learns across sessions without user intervention
- Pre-execution static analysis — 84% fewer permission prompts
- Plugin system for distributable agent bundles

**Codex CLI:**
- Cross-surface harness — same agent loop powers CLI, web app, IDE extension, macOS app via JSON-RPC
- Thread forking — git-like branching for conversations
- Mid-turn steering — redirect the agent while it's working
- Cloud Codex — fully air-gapped execution (internet disabled during task)
- Built in Rust — lowest overhead, fastest startup

**Gemini CLI:**
- 1M token context window — reads entire codebases in one session
- Deliberate context compaction — specify what to preserve during summarization
- Pre-tool-*selection* hooks — filter available tools before the model even chooses
- Skill-creator skill — agent extends its own capabilities at runtime
- Generous free tier — 1,000 req/day with full 1M context

## Models available

### Claude Code
| Model | Strengths | Context |
|-------|-----------|---------|
| Opus 4.6 | Most powerful reasoning, deep analysis | 200K (1M beta) |
| Opus 4.5 | Flagship, best SWE-bench Verified | 200K (1M beta) |
| Sonnet 4.5 (default) | Balanced, handles ~90% of tasks | 200K (1M beta) |
| Haiku 4.5 | Fast and cheap for simple tasks | 200K |

### Gemini CLI
| Model | Strengths | Context |
|-------|-----------|---------|
| Gemini 3 Flash | Best coding in the Gemini family | 1M |
| Gemini 3 Pro | Stronger reasoning, worse at coding than Flash | 1M |
| Gemini 2.5 Pro | Older but stable | 1M |
| Gemini 2.5 Flash | Fast but weak for complex coding | 1M |

### Codex CLI
| Model | Strengths | Context |
|-------|-----------|---------|
| GPT-5.3-Codex | Frontier coding + reasoning, SWE-bench Pro #1 | Not disclosed |
| GPT-5.2-Codex | Strong repo-scale reasoning | Not disclosed |
| GPT-5 | General frontier model | 128K+ |
| GPT-4.1 | Light option for simple tasks | 128K |
| codex-mini-latest | Cheapest ($1.50/M input) | Not disclosed |

## Cost

| | Claude Code | Gemini CLI | Codex CLI |
|---|---|---|---|
| **Free tier** | None | **1,000 req/day, 1M context** | Limited promo only |
| **Entry sub** | $20/mo (Pro) | Free | $20/mo (ChatGPT Plus) |
| **Heavy use** | $100-200/mo (Max) | Usage-based | $200/mo (ChatGPT Pro) |
| **Cheap API model** | ~$3/$15 per M tokens (Sonnet) | **$0.50/$3** per M (Flash) | $1.50/$6 per M (codex-mini) |
| **Best API model** | $15/$75 per M tokens (Opus) | ~$2/$8 per M (3 Pro) | Varies |
| **Token efficiency** | Uses ~4x more tokens per task | Moderate | **3-4x fewer tokens than Claude** |
| **Usage limits at $20/mo** | Restrictive (hit in ~30 min) | Generous | More generous than Claude |

**Effective cost per task:** Gemini is cheapest (free). Codex is next (fewer tokens + lower prices). Claude is most expensive but produces highest quality, potentially saving time on review/debugging.

Real-world test: same complex task cost $4.80 with Claude (260K in, 69K out) vs $7.06 with Gemini (432K in, 56K out) — Claude was cheaper despite higher per-token prices because it needed fewer attempts.

## Auth and TOS for automation

| | Claude Code | Gemini CLI | Codex CLI |
|---|---|---|---|
| **Auth options** | OAuth (subscription), API key | OAuth, API key, **service account** | ChatGPT login, API key |
| **Automation allowed?** | **API key only** | **Yes — explicitly encouraged** | **Yes — first-class feature** |
| **Anti-automation TOS?** | Yes (consumer terms) | No | No |
| **Headless auth for bots** | API key required | Service accounts (designed for CI) | `codex login --device-auth` |
| **Third-party wrapping** | Blocked + enforced (Jan 2026) | No restrictions | Actively partnering with third parties |
| **Open source** | Source-available (not OSS) | **Apache 2.0** | **Apache 2.0** |

**For ActionOS-CLI:** Gemini and Codex have zero TOS concerns for our use case. Claude requires API key auth for compliant automation.

## Strengths and weaknesses (honest)

### Claude Code

**Strengths:**
- Highest first-attempt code quality of the three
- Best multi-file coordination and refactoring
- Best debugging and bug-fixing reasoning
- Most polished terminal UX and tool set
- Strong at non-coding tasks (research, writing, analysis)
- Auto-compaction enables long sessions

**Weaknesses:**
- Most expensive, most restrictive usage limits
- TOS prohibits subscription-based automation (API key required)
- Uses ~4x more tokens than Codex for equivalent tasks
- Context loss in very long sessions despite compaction
- Sometimes starts editing when you ask conceptual questions
- Not open source

### Gemini CLI

**Strengths:**
- Free tier is genuinely usable (1,000 req/day)
- 1M token context window — real and available for free
- Google Search grounding for real-time research
- Multimodal (text, image, audio, video)
- Service accounts for clean bot auth
- Apache 2.0 open source

**Weaknesses:**
- Highest error rate of the three (40-50% in independent tests)
- Gemini 3 Pro has quality regressions — worse than 2.5 Pro for some tasks
- Context degrades past ~200K tokens despite 1M window
- Reports of destroying codebases, wiping git history
- Model availability issues on paid plans
- Privacy: free tier uses your data for training

### Codex CLI

**Strengths:**
- Token efficient (3-4x fewer tokens than Claude)
- Fastest output speed
- OS-level sandboxing (Seatbelt/Landlock) — most secure execution
- `codex exec` designed for scripted automation
- Leads on hardest benchmarks (SWE-bench Pro 57%, Terminal-Bench 77.3%)
- Apache 2.0 open source

**Weaknesses:**
- Lower code quality than Claude (needs more review)
- Primitive UX — poor error communication
- Quality regressions with newer models (GPT-5-Codex transition)
- Web search uses cached index by default (stale results)
- Requires government ID for account verification
- Terse output — less educational than Claude's explanations

## Best CLI by task type

This is the routing table ActionOS-CLI should use:

| Task | Primary CLI | Why | Fallback |
|------|------------|-----|----------|
| **Bug fixing** | Claude Code | Highest first-attempt success, best debugging | Codex |
| **New features** | Claude Code | Best multi-file coordination | Codex |
| **Large refactors** | Claude Code | Best edit quality (Aider #1) | Gemini (context) |
| **Code review** | Codex CLI | Fast, cheap, good at spotting issues | Claude |
| **Quick scripts** | Codex CLI | Fastest, cheapest, most token-efficient | Gemini (free) |
| **Research** | Gemini CLI | Google Search grounding, free, multimodal | Claude |
| **Codebase comprehension** | Gemini CLI | 1M context reads entire repos | Claude (quality) |
| **Writing / prose** | Claude Code | Strongest prose quality | Gemini |
| **Data analysis** | Claude Code | Best reasoning + tool use | Gemini (large data) |
| **Security-sensitive** | Codex CLI | Only real OS-level sandbox | Claude |
| **Prototyping / exploration** | Gemini CLI | Free tier, fast iteration | Codex |
| **Complex agentic tasks** | Codex CLI | SWE-bench Pro #1, Terminal-Bench #1 | Claude |

## Speed comparison

| | Claude Code | Gemini CLI | Codex CLI |
|---|---|---|---|
| **Simple queries** | Medium | Fast (Flash) | Fastest |
| **Complex tasks** | Fast (generates most volume) | Slow (Pro), fragmented attempts | Medium (reasoning overhead) |
| **Volume** | ~1,200 lines in 5 min | Varies | ~200 lines in 10 min |
| **Latency** | Medium | Low (Flash), High (Pro) | Low |

## CLI flags comparison (for ActionOS-CLI runner)

| Feature | Claude Code | Gemini CLI | Codex CLI |
|---------|------------|------------|-----------|
| **Non-interactive** | `--print` | `-p` / headless mode | `codex exec` |
| **JSON output** | `--output-format json` | `--output-format json` | JSON via exec mode |
| **Resume session** | `--resume <id>` | TBD | TBD |
| **System prompt** | `--append-system-prompt` | TBD | `--instructions` / `-i` |
| **Tool allowlist** | `--allowedTools` | TBD | Approval policies |
| **Budget cap** | `--max-budget-usd` | N/A (free tier) | Token limits |
| **Turn limit** | `--max-turns` | TBD | TBD |
| **Model select** | `--model` | `--model` | `--model` |
| **Sandbox** | N/A | N/A | `--sandbox read-only\|workspace-write\|full-access` |

(TBD = needs verification against actual CLI help output during implementation)

## Implications for ActionOS-CLI

### Runner priority (updated)

1. **Gemini CLI** — default for research, exploration, and free-tier tasks. Zero TOS risk. Service account auth.
2. **Codex CLI** — default for quick scripts, code review, security-sensitive work. Zero TOS risk. `codex exec`.
3. **Claude Code** — default for quality-critical coding (bug fixes, features, refactors). **Requires API key for compliant automation.** Highest quality, highest cost.

### Smart routing

The orchestrator should pick the CLI based on task type, not just user preference. The routing table above becomes a config-driven decision:

```toml
[routing]
# Task type -> preferred CLI
bug_fix = "claude"
new_feature = "claude"
refactor = "claude"
code_review = "codex"
quick_script = "codex"
research = "gemini"
codebase_search = "gemini"
writing = "claude"
default = "gemini"  # cheapest fallback
```

The user can override per-message with a prefix (e.g., `/claude`, `/gemini`, `/codex`) or let the orchestrator auto-route.

### Auth strategy (updated)

| CLI | Auth method | TOS status |
|-----|------------|------------|
| Gemini CLI | Service account or OAuth | Clean — explicitly allowed |
| Codex CLI | API key or device auth | Clean — explicitly allowed |
| Claude Code | **API key** (`ANTHROPIC_API_KEY`) | Clean — explicitly allowed |

All three use their officially sanctioned automation auth. No gray areas.
