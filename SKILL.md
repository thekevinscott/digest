---
name: digest
description: Extract insights from transcripts into actionable artifact files.
---

# /digest

Process raw transcript logs and extract insights directly into artifact files.

## Output Files

All in `notes/digest/`:

| File | What to extract |
|------|-----------------|
| `opportunities.md` | Optimization ideas - "could improve", friction points, repeated manual work, better approaches mentioned |
| `loose-ends.md` | Open items - TODOs not done, questions unanswered, "need to" without resolution |
| `research-backlog.md` | Future directions - "interesting", "worth exploring", novel techniques |
| `blog-grist.md` | Significant work completed, problems solved, patterns discovered |
| `things-learned.md` | Preferences, environment facts, workflow learnings |

## Entry Format

Append only the entry block - no file headers, titles, or descriptions:

```
---
### 2026-01-07

## project-name

- Item from this session
- Another item
```

Do not add `# File Title` or description text. Files are append-only logs.

## Instructions

### 1. Find unprocessed transcripts

```bash
uv run --project ~/.claude/skills/digest digest --list
```

If output is "Nothing new to process", stop here.

Use `--path <dir>` to specify a different base directory (defaults to cwd):

```bash
uv run --project ~/.claude/skills/digest digest --path /other/project --list
```

### 2. Extract and analyze

For each session with new content:

```bash
uv run --project ~/.claude/skills/digest digest --extract <session_id>
```

This outputs cleaned message text (user/assistant only, no metadata).

**What to look for**:

**Opportunities** (`opportunities.md`):
- "could improve", "should optimize", "better way"
- Friction, repeated steps, workarounds
- Failed approaches that revealed a gap

**Loose ends** (`loose-ends.md`):
- TODOs not completed in the session
- Questions raised but not answered
- "Need to" / "should" without resolution

**Research backlog** (`research-backlog.md`):
- "Interesting", "worth exploring"
- Techniques mentioned but not tried
- Links/references saved for later

**Blog grist** (`blog-grist.md`):
- Significant work completed
- Problems solved in interesting ways
- Patterns or insights that emerged

**Memories** (`things-learned.md`):
- User preferences ("I prefer...", "don't like...")
- Environment facts (paths, configs, tools)
- Workflow patterns to remember

### 3. Mark processed

After extracting insights from a session:

```bash
uv run --project ~/.claude/skills/digest digest --mark <session_id>
```

### 4. Report

Brief summary:
- Sessions processed: N (X new lines)
- Items added: Y opportunities, Z loose ends, etc.

Keep it short. The artifacts speak for themselves.
