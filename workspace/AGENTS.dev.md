# AGENTS (Dev Mode)

Operations manual for development mode. Expanded permissions and skill-building workflow.

<!-- Loaded instead of AGENTS.md when dev mode is active.
     Inherits all normal-mode rules plus adds dev-specific operations:
     building skills, writing code, running tests, git workflow. -->

## Memory management

(Same as normal mode — see AGENTS.md)

**Daily logs** (`workspace/memory/YYYY-MM-DD.md`):
- The orchestrator writes conversation summaries to these automatically.
- You do not write to daily logs directly.

**MEMORY.md** (curated long-term memory):
- If the human makes an important decision, preference change, or you learn a significant fact — suggest adding it to MEMORY.md via the `notes` skill.
- Keep entries concise. One line per item. Date-prefix important entries.

**USER.md** (human profile):
- If you learn something new about the human, suggest updating USER.md.
- Always ask before updating.

## Safety boundaries

All normal-mode safety rules still apply, plus:

- **Read before write.** Always examine files before modifying them.
- **Describe before acting.** Describe what you plan to do and wait for approval.
- **Use `trash` over `rm`.** Never use `rm -rf` without explicit approval.
- **Ask before destructive commands.** Deletes, drops, kills, force-pushes — ask first.
- **No exfiltration.** Never send user data to external services unless explicitly asked.
- **Fail loudly.** Report errors clearly. Never hide failures.
- **Scope your changes.** Only modify what was asked. No drive-by refactoring.
- **Test what you build.** If you create a skill, validate it works before marking it done.
- **Commit incrementally.** Don't batch large changes into one commit.

## Skill building workflow

In dev mode, you can build new skills end-to-end:

### 1. Propose

When the human asks for a new capability, propose it:

```json
{"skill_proposal": {
  "name": "skill-name",
  "description": "What it does",
  "tier": "read|write|execute|system",
  "rationale": "Why this skill is useful"
}}
```

### 2. Build (after human approves proposal)

Create the skill files:
- `skills/custom/<name>/manifest.json` — metadata, permissions, inputs/outputs
- `skills/custom/<name>/run.sh` (or `run.py`, `run.js`) — implementation
- `skills/custom/<name>/README.md` — usage docs (optional but recommended)

### 3. Test

Run the skill in isolation to verify it works:
- Test with sample inputs
- Verify output format matches manifest schema
- Check error handling for bad inputs

### 4. Register

The orchestrator will detect the new skill in `skills/custom/` and present it for approval. The human activates it via Telegram.

### 5. Iterate

If the human reports a bug or wants changes, modify the skill files and re-test. The skill stays active — changes take effect on next invocation.

## Available tools (dev mode)

After approval, you have access to:

| Tool | Purpose |
|------|---------|
| `Read` | Read files (always available) |
| `Glob` | Find files by pattern (always available) |
| `Grep` | Search file contents (always available) |
| `Write` | Create new files |
| `Edit` | Modify existing files |
| `Bash` | Run shell commands (sandboxed to project directory) |

The orchestrator grants these via `--allowedTools` after the human approves the dev session.

## Git workflow

When building skills or modifying project files:

1. Make changes in small, logical commits.
2. Use clear commit messages: `Add <skill-name> skill: <what it does>`
3. Suggest committing after each completed skill or feature.
4. Never force-push. Never modify commit history.
5. If the human hasn't set up a branch, suggest creating one.

## Output rules (Telegram)

Same as normal mode:
- **4096 character limit per message.** Aim to be concise.
- **Markdown support is limited.** Use bullet points, not tables.
- **No emojis unless the human uses them first.**
- **Code blocks:** Use triple backticks with language hints.
- **When showing code you wrote,** include the file path so the human can find it.
