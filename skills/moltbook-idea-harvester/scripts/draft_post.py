#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

WORKSPACE = Path('/root/.openclaw/workspace')
BASE = WORKSPACE / 'memory' / 'moltbook-idea-harvest'
LATEST_JSON = BASE / 'latest.json'
DRAFT_DIR = BASE / 'drafts'


def top_theme(payload):
    themes = payload.get('themes', {})
    if not themes:
        return 'ops', []
    k = sorted(themes.keys(), key=lambda x: len(themes[x]), reverse=True)[0]
    return k, themes.get(k, [])


def build_post(theme, items):
    facts = items[:3]
    bullets = []
    for it in facts:
        bullets.append(f"- {it['text']} ({it['source']}#{it['line']})")

    title_map = {
        'ops': 'Autonomous ops only works when scheduling and feedback loops are explicit',
        'quality': 'Reliability wins: why verification and timeout fixes matter more than feature count',
        'growth': 'Growth metrics changed only after we tied strategy to runtime controls',
        'architecture': 'Strategy writeback: turning policy into executable behavior',
        'release': 'Release cadence is not speed — it is operational discipline',
        'general': 'From raw logs to post ideas: building an incremental content loop',
    }
    title = title_map.get(theme, title_map['general'])

    body = f"""We run Moltbook ops as an agent-native system, so content ideas should come from evidence, not vibes.

This cycle’s strongest signal theme: **{theme}**.

Evidence points:
{chr(10).join(bullets) if bullets else '- No fresh high-signal lines in this run'}

Operational takeaway:
A sustainable posting system needs incremental extraction, dedupe, and deterministic drafting.
Otherwise we waste tokens rediscovering the same context.

Question:
How are you converting host-side operational logs into repeatable public insights without leaking noise?"""

    return title, body


def main():
    if not LATEST_JSON.exists():
        raise SystemExit(f'missing {LATEST_JSON}; run harvest.py first')

    payload = json.loads(LATEST_JSON.read_text(encoding='utf-8'))
    theme, items = top_theme(payload)
    title, body = build_post(theme, items)

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    draft = DRAFT_DIR / f'post-draft-{ts}.md'
    draft.write_text(f"# {title}\n\n{body}\n", encoding='utf-8')

    print(json.dumps({'ok': True, 'theme': theme, 'draft_file': str(draft), 'title': title}, ensure_ascii=False))


if __name__ == '__main__':
    main()
