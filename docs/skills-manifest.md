# Skills Manifest

How skills are defined, proposed, approved, and executed.

## What a skill is

A skill is a modular tool that the **orchestrator** (not Claude CLI) can execute on Claude's behalf. Claude is the brain — it decides when a skill should be used. The orchestrator is the hands — it actually runs the skill code.

Each skill lives in its own folder:

```
skills/
  builtin/
    notes/
      manifest.json
      run.py
    reminders/
      manifest.json
      run.py
    file-search/
      manifest.json
      run.py
  custom/
    my-script/
      manifest.json
      run.py
      README.md
```

## How Claude invokes skills (orchestrator-as-executor model)

Claude CLI has its own built-in tools (Read, Write, Edit, Bash, etc.) controlled via `--allowedTools`. Our custom skills are **separate** — Claude cannot call them directly.

### The flow

1. The orchestrator includes skill descriptions in `--append-system-prompt`:
   ```
   Available custom skills:
   - notes: Create, read, update, and search personal notes.
   - reminders: Set reminders with natural language times.

   To use a skill, include this JSON block in your response:
   {"skill_call": {"name": "<skill_name>", "inputs": {<inputs>}}}
   ```

2. Claude decides to use a skill and includes the JSON block in its text response:
   ```
   I'll save that as a note for you.
   {"skill_call": {"name": "notes", "inputs": {"action": "create", "title": "meeting", "content": "Discussed Q3 roadmap..."}}}
   ```

3. The orchestrator parses the `skill_call` from Claude's response.

4. The orchestrator validates inputs against the skill's manifest schema.

5. The orchestrator checks permissions (tier-based approval).

6. The orchestrator executes `run.py` as a subprocess (or in Docker if sandboxed).

7. The orchestrator feeds the result back to Claude via `--resume`:
   ```
   [Skill result: notes] Note created successfully: data/notes/meeting.md
   ```

8. Claude generates a final user-facing reply incorporating the result.

### Why not let Claude call skills directly?

- **No Bash needed.** If Claude called skills via Bash, we'd need Bash in `--allowedTools` for every job. That's the unrestricted shell access we're trying to avoid.
- **No spoofing.** The orchestrator controls what runs. Claude can't trick the system into executing a skill that doesn't exist or bypassing approval.
- **Clean audit trail.** Every skill execution goes through the orchestrator's logging, not buried inside Claude's internal tool loop.
- **Approval is possible.** Since the orchestrator intercepts before execution, it can pause for approval without mid-execution process hacks.

## Manifest schema

```json
{
  "name": "notes",
  "version": "1.0.0",
  "description": "Create, read, update, and search personal notes.",
  "author": "builtin",
  "tier": "write",
  "inputs": {
    "action": {
      "type": "string",
      "enum": ["create", "read", "update", "search", "list"],
      "required": true
    },
    "title": {
      "type": "string",
      "required": false
    },
    "content": {
      "type": "string",
      "required": false
    },
    "query": {
      "type": "string",
      "required": false
    }
  },
  "outputs": {
    "type": "string",
    "description": "The result of the note operation."
  },
  "permissions": {
    "filesystem": ["read", "write"],
    "network": false,
    "shell": false,
    "paths": ["data/notes/"]
  },
  "risk": "low",
  "sandbox": false,
  "enabled": true
}
```

### Field definitions

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique skill identifier. Lowercase, hyphens only. |
| `version` | string | Semver. |
| `description` | string | One sentence. Included in Claude's system prompt so it knows when to use this skill. |
| `author` | string | `"builtin"` or your name/handle. |
| `tier` | enum | `"read"`, `"write"`, `"execute"`, `"system"`. Determines approval requirements. |
| `inputs` | object | JSON Schema for the skill's parameters. |
| `outputs` | object | JSON Schema for the skill's return value. |
| `permissions.filesystem` | array | `["read"]`, `["read", "write"]`, or `[]`. |
| `permissions.network` | bool | Can this skill make HTTP requests? |
| `permissions.shell` | bool | Can this skill spawn subprocesses? |
| `permissions.paths` | array | Allowed filesystem paths (relative to project root). |
| `risk` | enum | `"low"`, `"medium"`, `"high"`, `"critical"`. Informational. |
| `sandbox` | bool | Must this skill run in a Docker container? |
| `enabled` | bool | Is this skill currently active? |

## Permission tiers

| Tier | Approval | What it can do | Examples |
|------|----------|----------------|----------|
| **read** | Auto-approved | Read files, search, fetch URLs | file-search, web-lookup |
| **write** | One-time approval | Create/edit files in allowed paths | notes, reminders, bookmarks |
| **execute** | Per-invocation | Run scripts, shell commands | run-test, deploy-check |
| **system** | Per-invocation + sandbox | Install packages, modify config | package-install, cron-edit |

## Builtin skills (v1)

These ship with ActionOS-CLI and are pre-approved:

| Skill | Tier | Description |
|-------|------|-------------|
| `notes` | write | Create/read/update/search personal notes (stored in `data/notes/`) |
| `reminders` | write | Set reminders with natural language times (stored in `data/reminders/`) |
| `file-search` | read | Search files by name or content in a specified directory |
| `web-fetch` | read | Fetch a URL and return content as text/markdown |
| `summarize` | read | Summarize a block of text or a URL |

## How the agent proposes a new skill

When Claude determines it needs a capability it doesn't have, it can propose a new skill by including a `skill_proposal` JSON block in its response.

### Proposal format

```json
{
  "skill_proposal": {
    "manifest": {
      "name": "github-issues",
      "version": "1.0.0",
      "description": "Search and read GitHub issues for a repository.",
      "tier": "read",
      "inputs": { "repo": {"type": "string", "required": true}, "query": {"type": "string", "required": false} },
      "outputs": { "type": "string" },
      "permissions": { "filesystem": [], "network": true, "shell": false, "paths": [] },
      "risk": "low",
      "sandbox": false
    },
    "code": "#!/usr/bin/env python3\nimport sys, json, urllib.request\n...",
    "example": "Input: {\"repo\": \"user/repo\", \"query\": \"bug\"}\nOutput: \"Found 3 issues matching 'bug'...\"",
    "rationale": "User frequently asks about GitHub issues. A dedicated skill avoids web scraping each time."
  }
}
```

### Approval flow

1. Orchestrator detects `skill_proposal` in Claude's response.
2. A human-readable summary is sent to Telegram:
   ```
   New skill proposed: "github-issues"
   Tier: read
   Permissions: network (yes), filesystem (no), shell (no)
   Description: Search and read GitHub issues for a repository.
   Risk: low

   [Approve] [Sandbox Only] [Reject] [View Code]
   ```
3. You tap a button:
   - **Approve**: Skill is written to `skills/custom/`, `enabled: true`.
   - **Sandbox Only**: Skill is written but `sandbox: true` forced regardless of manifest.
   - **Reject**: Skill is discarded. Reason optionally noted.
   - **View Code**: Full source sent as a Telegram message for review before deciding.
4. If approved, the skill description is added to the system prompt on the next invocation.

### What the agent cannot do

- Activate a skill without approval. Ever.
- Modify an existing skill's manifest or code. (Propose a new version instead.)
- Propose a skill with `tier: "system"` that has `sandbox: false`.
- Access paths outside the skill's declared `permissions.paths`.
- Execute a skill directly — only the orchestrator can run skill code.

## Skill execution

When the orchestrator invokes a skill:

1. Load `manifest.json`, validate inputs against schema.
2. Check tier approval (auto, one-time, or per-invocation).
3. If `sandbox: true`, run inside Docker container with limited resources.
4. Execute `run.py` (or `run.js`) with inputs as JSON on stdin.
5. Capture stdout as the skill's output. Capture stderr for error logging.
6. Log everything to `tool_calls` table (skill name, inputs, output, duration, success/fail).
7. Feed output back to Claude via `--resume` as the next message.

### Sandbox execution

For sandboxed skills:

```bash
docker run --rm \
  --memory=256m \
  --cpus=0.5 \
  --network=none \       # unless permissions.network is true
  --read-only \          # unless permissions.filesystem includes "write"
  -v /path/to/skill:/skill:ro \
  -v /path/to/allowed:/data \
  actionos-sandbox \
  python /skill/run.py
```

The sandbox image (`actionos-sandbox`) is a minimal Python/Node image with no tools pre-installed.

## Skill discovery

The orchestrator reads skills at startup:

1. Scan `skills/builtin/` and `skills/custom/` for folders with `manifest.json`.
2. Validate each manifest.
3. Build a tool registry: `{ name -> manifest + executor path }`.
4. On each Claude CLI invocation, include skill descriptions in `--append-system-prompt`.

The system prompt includes:

```
Available custom skills:
- notes: Create, read, update, and search personal notes. Inputs: action (create|read|update|search|list), title?, content?, query?
- reminders: Set reminders with natural language times. Inputs: action (set|list|cancel), text?, time?
- file-search: Search files by name or content. Inputs: directory, pattern?, content_query?

To use a skill, include a JSON block in your response:
{"skill_call": {"name": "<skill_name>", "inputs": {<inputs matching the skill's schema>}}}

If you need a tool that isn't listed, you may propose a new skill.
```

## Future: MCP integration

In a later version, skills could be registered as MCP (Model Context Protocol) tool servers. Claude CLI natively supports MCP via `--mcp-config`. This would let Claude call skills as first-class tools rather than via JSON blocks in text.

Pros: cleaner integration, Claude can use skills in its internal tool loop.
Cons: each skill must implement the MCP protocol, more complexity.

Decision deferred to after v1 is stable.
