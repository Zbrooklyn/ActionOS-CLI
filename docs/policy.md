# Policy

Authentication, licensing, and terms-of-service awareness for ActionOS-CLI.

## Auth decision: official CLI auth only

ActionOS-CLI uses each AI CLI's **native authentication** — the login you already have from your subscription. We never store, pass, or manage API keys.

| CLI | Auth method | How it works |
|-----|-------------|--------------|
| Claude Code | `claude login` (OAuth) | Pro/Max subscription, CLI handles auth internally |
| Gemini CLI | `gemini auth login` (Google OAuth) | Google AI subscription, CLI handles auth internally |
| ChatGPT Codex CLI | `codex auth` (OpenAI OAuth) | Plus/Pro subscription, CLI handles auth internally |

**What we do:**
- Spawn the official CLI binary as a subprocess
- The CLI handles its own authentication, API calls, and billing
- We pipe in prompts, capture structured output
- We never touch tokens, headers, or auth flows

**What we don't do:**
- Store or pass API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`)
- Spoof client identity headers
- Extract or reuse OAuth tokens
- Route traffic through third-party proxies (OpenRouter, etc.)
- Pretend to be a different client than what we are

## TOS awareness

We are aware of the policy landscape and have made deliberate choices.

### Anthropic (Claude)

Anthropic's Consumer Terms (Section 3, Item 7) prohibit automated access "through a bot, script, or otherwise" except via API key. At the same time, Claude Code's `--print` mode, `--output-format json`, and `--resume` flags are explicitly designed for scripting and non-interactive use — Anthropic's own CLI reference promotes these for "SRE bots, automated code reviews, and agent integrations."

The Agent SDK docs state: "Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products. Developers should use API key authentication instead."

**Our position:**
- ActionOS-CLI is a **personal tool**, not a product offered to third parties.
- We run the **official Claude Code binary** — we are not a third-party harness spoofing Claude Code's identity.
- We use `--print` mode exactly as documented by Anthropic for scripting use.
- We are not extracting OAuth tokens, forging headers, or circumventing rate limits.
- We acknowledge the gray area and accept the risk for personal use.
- If Anthropic tightens enforcement on CLI-based automation, we will adapt — the runner abstraction makes switching to API key auth a config change, not a rewrite.

**What we will never do:**
- Spoof Claude Code's client identity (this is what got OpenCode/others banned)
- Share subscription credentials with other users
- Offer this as a hosted service using subscription auth
- Extract or pass OAuth tokens outside the CLI's own process

### Google (Gemini) and OpenAI (Codex)

Same principle applies. We run the official CLI binary. We don't extract tokens or spoof identity. If either provider restricts CLI-based automation, we'll adapt.

## Why not API keys?

1. **Simplicity.** CLI auth means zero credential management. No key rotation, no billing dashboards, no per-token cost tracking. You log in once and it works.
2. **Existing subscriptions.** Users already pay for Pro/Max. An API key means paying again, per token, for the same model.
3. **CLI-first design.** By wrapping the official binary, we get all built-in tools, safety behaviors, and updates for free. API key + raw SDK means rebuilding the agent loop.
4. **Multi-CLI future.** The same subprocess pattern works for Claude, Gemini, and Codex. API key auth would require separate SDKs, separate billing, separate credential management for each provider.

## Fallback plan

If any CLI provider explicitly blocks automated subprocess usage:

1. The runner abstraction isolates the CLI invocation. Switching to API key auth is a single-module change.
2. The Agent SDK (Claude) / equivalent SDKs (Gemini, OpenAI) support API key auth for the same capabilities.
3. No other component (orchestrator, skills, Telegram bot, state store) needs to change.

This is documented as a known risk, not ignored. The architecture is designed so the fix is cheap.

## OpenClaw precedent

OpenClaw (formerly Clawdbot) experienced:
- Account bans for tools that **spoofed Claude Code's client identity** to route subscription traffic through third-party harnesses.
- 400+ malicious packages in their skill marketplace.
- 42,665 publicly exposed instances leaking API keys and conversation histories.
- Prompt injection attacks via email forwarding.

**How we're different:**
| OpenClaw risk | Our mitigation |
|---------------|----------------|
| Spoofed Claude Code headers | We run the real `claude` binary, no spoofing |
| Public skill marketplace | No marketplace, all skills local + approved |
| Exposed instances | Single-user, local-only, no public endpoints |
| OAuth token extraction | We never touch tokens, CLI handles auth |
| Unrestricted shell | Default tools are read-only, approval-gated |
| No audit trail | Everything logged to SQLite |

## For anyone forking this project

If you fork ActionOS-CLI:
- **Personal use** with your own CLI subscriptions: same gray area as us. Your risk to accept.
- **Offering as a service to others**: you should switch to API key auth. The runner abstraction makes this straightforward.
- **Never** share subscription credentials or extract OAuth tokens.
- **Never** spoof client identity headers.

The runner interface is designed to make auth-method switching a config change. See [Architecture](architecture.md) for the runner abstraction.
