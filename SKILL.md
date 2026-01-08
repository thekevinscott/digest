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

Each entry should be timestamped and separated by dashes:

```
---
### 2026-01-07

- Item from this session
- Another item

---
### 2026-01-06

- Earlier item
```

## Instructions

### 1. Find unprocessed transcripts

```bash
uv run --project ~/.claude/skills/digest digest --list
```

If output is "Nothing new to process", stop here.

### 2. Extract and analyze

For each session with new content:

```bash
uv run --project ~/.claude/skills/digest digest --extract <session_id>
```

This outputs cleaned message text (user/assistant only, no metadata).

**What to look for**:

**Opportunities** (append to `notes/digest/opportunities.md`):
- Explicit mentions: "could improve", "should optimize", "better way"
- Friction: repeated steps, workarounds, things that felt slow
- Failed approaches that revealed a gap
- Tag by project: add under `## <project>` section (create if needed)

**Loose ends** (append to `notes/digest/loose-ends.md`):
- TODOs mentioned but not completed in the session
- Questions raised but not answered
- "Need to" or "should" statements without resolution
- Things deferred explicitly ("will do later", "not now")
- Tag by project: add under `## <project>` section

**Research backlog** (append to `notes/digest/research-backlog.md`):
- "Interesting", "worth exploring", "might be cool"
- Techniques mentioned but not tried
- Links/references saved for later
- Just bullet points with optional tags

**Blog grist** (append to `notes/digest/blog-grist.md`):
- Significant work completed (features, fixes, new capabilities)
- Problems solved in interesting ways
- Patterns or insights that emerged
- Tag by project: add under `## <project>` section

**Memories** (append to `notes/digest/things-learned.md`):
- User preferences expressed ("I prefer...", "don't like...")
- Environment facts learned (paths, configs, tools)
- Workflow patterns to remember
- Add under appropriate section header

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
