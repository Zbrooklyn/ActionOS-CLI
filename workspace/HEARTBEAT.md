# HEARTBEAT

Configuration for periodic autonomous tasks (cron jobs).

<!-- This file defines what the agent should check during heartbeat runs.
     The orchestrator reads this to configure the cron_jobs table.
     Keep it brief — each heartbeat is a separate CLI invocation with
     its own token cost.

     Empty sections = no heartbeat for that category.
     Delete this file entirely to disable all heartbeat runs. -->

## Schedule

- Interval: 60 minutes (configurable in config.toml)
- Enabled: false

<!-- Set enabled to true when you have tasks worth checking periodically.
     Each heartbeat creates a fresh session (no --resume) to prevent
     context pollution between runs. -->

## Checklist

<!-- What to check during each heartbeat. One task per line.
     Each task should be self-contained and completable in 1-2 turns.

     Examples:
     - Check if any new files appeared in ~/Downloads
     - Summarize unread notifications
     - Review today's daily log and promote important items to MEMORY.md
     - Check disk usage on homelab
-->

## Output

- Thread: heartbeat (dedicated Telegram thread for heartbeat output)
- Only report if something noteworthy was found. Silent heartbeats = no message.
