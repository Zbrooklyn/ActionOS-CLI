# Skills Manifest

How skills are defined, proposed, approved, and executed.

## What a skill is

A skill is a modular tool the agent can invoke. It has a manifest (what it does, what it needs), an executor (the code), and a permission tier.

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
| `description` | string | One sentence. Shown to the agent so it knows when to use this skill. |
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

When Claude determines it needs a capability it doesn't have, it can propose a new skill.

### Proposal format

Claude generates and returns (as part of its response):

```json
{
  "skill_proposal": {
    "manifest": { ... },
    "code": "# Python code for run.py\n...",
    "example": "Example invocation and expected output",
    "rationale": "Why this skill is needed"
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
   - **Sandbox Only**: Skill is written but `sandbox: true` forced.
   - **Reject**: Skill is discarded. Reason optionally noted.
   - **View Code**: Full source sent as a Telegram message for review.
4. If approved, the skill is available on the next invocation.

### What the agent cannot do

- Activate a skill without approval. Ever.
- Modify an existing skill's manifest or code. (Propose a new version instead.)
- Propose a skill with `tier: "system"` that has `sandbox: false`.
- Access paths outside the skill's declared `permissions.paths`.

## Skill execution

When the orchestrator invokes a skill:

1. Load `manifest.json`, validate inputs against schema.
2. Check tier approval (auto, one-time, or per-invocation).
3. If `sandbox: true`, run inside Docker container with limited resources.
4. Execute `run.py` (or `run.js`) with inputs as JSON on stdin.
5. Capture stdout as the skill's output.
6. Log everything to `tool_calls` table (skill name, inputs, output, duration, success/fail).

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
4. Pass the skill descriptions to Claude via the system prompt so it knows what's available.

On each Claude CLI invocation, the system prompt includes:

```
Available tools:
- notes: Create, read, update, and search personal notes.
- reminders: Set reminders with natural language times.
- file-search: Search files by name or content.
- web-fetch: Fetch a URL and return content.

If you need a tool that isn't listed, you may propose a new skill.
```
