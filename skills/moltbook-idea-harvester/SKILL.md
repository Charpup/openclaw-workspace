---
name: moltbook-idea-harvester
description: Harvest post ideas from host-wide memory/journal/log files incrementally with dedupe, then generate ready-to-publish Moltbook draft posts. Use when running Moltbook content operations, planning daily posts, or reducing token cost for post ideation.
---

# Moltbook Idea Harvester

Extract high-signal inspiration from host files and produce structured post drafts.

## Scripts

- `scripts/harvest.py`
  - Incrementally scan host-wide roots (workspace + agent workspaces such as `/root/workspace-*`).
  - Skip unchanged files via file fingerprint index.
  - Dedupe extracted snippets via snippet hash index.
  - Apply sensitive-data redaction before persistence.
  - Honor ignore rules from `config/moltbook-harvestignore.txt`.
  - Output:
    - `memory/moltbook-idea-harvest/latest.md`
    - `memory/moltbook-idea-harvest/latest.json`
    - `memory/moltbook-idea-harvest/state.json`

- `scripts/draft_post.py`
  - Read latest harvest output.
  - Select top themes and build one concise English post draft (Moltbook-style).
  - Output draft markdown to `memory/moltbook-idea-harvest/drafts/`.

- `scripts/review_gate.py`
  - Score draft quality and decide pass/fail by threshold.

- `scripts/gate_and_publish.py`
  - Run harvest + draft + review gate.
  - If score >= threshold, publish through `moltbook-challenge-solver` and verify.
  - Validate public post URL reachability before returning link.

## Runbook

### 1) Harvest ideas

```bash
python skills/moltbook-idea-harvester/scripts/harvest.py
```

### 2) Generate post draft

```bash
python skills/moltbook-idea-harvester/scripts/draft_post.py
```

### 3) Gated auto-publish (closed loop)

```bash
python skills/moltbook-idea-harvester/scripts/gate_and_publish.py --threshold 72
```

This executes:
- harvest -> draft -> score gate -> conditional publish+verify
- returns a verified link only when gate passes and URL is reachable

## Safety / Scope

- Read-only scan of workspace text files.
- Exclude vendor/generated dirs (`.git`, `node_modules`, `dist`, `build`, `.venv`, `__pycache__`).
- No destructive edits.
- Incremental mode by default for low token and low compute cost.

## References

- `references/format-guide.md` for post style + quality checklist.
