# Policy

Authentication, licensing, and terms-of-service decisions for ActionOS-CLI.

## Auth strategy: compliant automation for all three CLIs

After researching each provider's TOS and enforcement history, ActionOS-CLI uses each CLI's **officially sanctioned automation auth method**. No gray areas.

| CLI | Auth method | TOS status | How |
|-----|------------|------------|-----|
| Gemini CLI | Service account or Google OAuth | **Explicitly allowed** — Google recommends service accounts for "non-interactive environments, CI/CD pipelines" | `GOOGLE_APPLICATION_CREDENTIALS` or OAuth |
| Codex CLI | API key or device auth | **Explicitly allowed** — `codex exec` is a first-class automation feature with official SDK | `CODEX_API_KEY` or `codex login --device-auth` |
| Claude Code | **API key** | **Explicitly allowed** — Consumer Terms carve out API key access from automation prohibition | `ANTHROPIC_API_KEY` |

### Why API key for Claude (not subscription auth)

Anthropic's Consumer Terms (Section 3, Item 7) prohibit automated access "through a bot, script, or otherwise" **except via API key**. They enforced this in January 2026 — blocking OpenCode, Roo Code, Cline, Kilo, and other tools that wrapped subscription auth in third-party harnesses.

Using `claude --print` with subscription auth is a gray area. Using `claude --print` with `ANTHROPIC_API_KEY` is unambiguously compliant. Since we're building automation, we use the compliant path.

**Trade-off:** API key means per-token billing instead of flat-rate subscription. But Claude is our quality runner, not our volume runner. Gemini (free tier) handles volume. Claude handles quality-critical tasks where the cost is justified.

### Why Gemini and Codex have no gray area

- **Gemini CLI:** Google provides service account auth explicitly for "non-interactive environments, CI/CD pipelines." They ship a GitHub Action. They promote automation use cases. No anti-automation clause in the TOS.
- **Codex CLI:** OpenAI ships `codex exec` as a dedicated non-interactive subcommand. They provide an SDK for programmatic control. They're actively partnering with third-party tools for OAuth access. No anti-automation clause.

## What we do

- Spawn the official CLI binary as a subprocess
- Authenticate using each provider's recommended automation method
- Pipe in prompts, capture structured output
- Never touch OAuth tokens, session cookies, or internal auth flows

## What we don't do

- Store or pass subscription OAuth tokens
- Spoof client identity headers
- Extract or reuse internal auth tokens
- Route traffic through third-party proxies (OpenRouter, etc.)
- Pretend to be a different client than what we are
- Offer this as a hosted service to others

## Cost implications

| CLI | Cost model | Expected role |
|-----|-----------|---------------|
| Gemini CLI | Free tier: 1,000 req/day | Default runner — research, exploration, prototyping |
| Codex CLI | $1.50-6/M tokens (codex-mini) or ChatGPT Plus subscription | Quick scripts, code review, security-sensitive tasks |
| Claude Code | $3-75/M tokens depending on model | Quality-critical coding — bug fixes, features, refactors |

Smart routing (see [CLI Comparison](cli-comparison.md)) keeps costs down by using the cheapest CLI that's good enough for each task type. Claude is only invoked when quality matters most.

## OpenClaw precedent

OpenClaw (formerly Clawdbot) experienced:
- Account bans for tools that **spoofed Claude Code's client identity**
- 400+ malicious packages in their skill marketplace
- 42,665 publicly exposed instances leaking API keys and conversation histories
- Prompt injection attacks via email forwarding

**How we're different:**

| OpenClaw risk | Our mitigation |
|---------------|----------------|
| Spoofed Claude Code headers | We use API key auth, not subscription spoofing |
| Subscription auth wrapping | API key = explicitly compliant |
| Public skill marketplace | No marketplace, all skills local + approved |
| Exposed instances | Single-user, local-only, no public endpoints |
| Unrestricted shell | Default tools are read-only, approval-gated |
| No audit trail | Everything logged to SQLite |

## For anyone forking this project

If you fork ActionOS-CLI:
- **Personal use** with API keys: fully compliant. No gray area.
- **Offering as a service**: still use API key auth. Consider each provider's commercial use terms.
- **Never** share credentials, spoof client identity, or extract internal auth tokens.

The runner interface is designed to make auth-method switching a config change. See [Architecture](architecture.md) for the runner abstraction.
