# BOOT

Startup checklist. The orchestrator reads this on every launch.

<!-- This defines what the agent should do (or be aware of) at the start of
     every session. Injected into the system prompt alongside SOUL.md and
     USER.md. Keep it short — this runs on every invocation. -->

## On session start

1. You have access to read-only tools by default: `Read`, `Glob`, `Grep`.
2. If you need write or execute tools, describe what you want to do. The human will approve or deny via Telegram.
3. Check MEMORY.md for relevant context before asking questions the human has already answered.
4. Check USER.md for the human's preferences and current projects.

## Available skills

Skills are listed in your system prompt. To use one, output a `skill_call` JSON block. The orchestrator will execute it and feed the result back to you.

Do **not** try to execute skills yourself via Bash or other tools. The orchestrator is the only skill executor.

## Constraints

- Max turns per invocation: set by orchestrator (default 5)
- Max budget per invocation: set by orchestrator (default $0.50)
- If you hit a turn or budget limit, summarize where you are so the human can continue.
