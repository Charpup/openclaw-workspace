#!/usr/bin/env python3
"""
Incremental idea harvester for Moltbook content.

- Scans journal/memory-like files
- Extracts high-signal lines as inspiration candidates
- Stores processed-file index to avoid reprocessing unchanged files
- Stores dedupe index for extracted snippets
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

WORKSPACE = Path('/root/.openclaw/workspace')
DEFAULT_ROOTS = [
    WORKSPACE / 'memory',
    WORKSPACE / 'projects',
    WORKSPACE / '01_active',
]
EXCLUDE_DIRS = {'.git', 'node_modules', 'dist', 'build', '__pycache__', '.venv'}
TEXT_EXT = {'.md', '.txt', '.log', '.json', '.yaml', '.yml'}

STATE_DIR = WORKSPACE / 'memory' / 'moltbook-idea-harvest'
STATE_FILE = STATE_DIR / 'state.json'
LATEST_MD = STATE_DIR / 'latest.md'
LATEST_JSON = STATE_DIR / 'latest.json'

KEYWORDS = {
    'release': ['release', 'tag', 'version', 'v3.', 'v4.', 'published'],
    'ops': ['cron', 'schedule', 'automation', 'autonomous', 'ops', 'run'],
    'quality': ['bug', 'fix', 'failure', 'timeout', 'verify', 'stable', 'stability'],
    'growth': ['karma', 'followers', 'engagement', 'comments', 'posts', 'okr'],
    'architecture': ['strategy', 'writeback', 'pipeline', 'loop', 'profile', 'runtime'],
}

MAX_FILE_BYTES = 300_000
MAX_SNIPPETS = 120


@dataclass
class Snippet:
    source: str
    line_no: int
    text: str
    theme: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode('utf-8', errors='ignore')).hexdigest()


def file_fingerprint(path: Path) -> str:
    st = path.stat()
    key = f"{path}:{st.st_mtime_ns}:{st.st_size}"
    return hashlib.sha1(key.encode()).hexdigest()


def load_state() -> Dict:
    if not STATE_FILE.exists():
        return {
            'updated_at': None,
            'processed_files': {},   # path -> fingerprint
            'seen_snippets': {},     # snippet_hash -> first_seen_at
        }
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {
            'updated_at': None,
            'processed_files': {},
            'seen_snippets': {},
        }


def save_state(state: Dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def iter_files(roots: List[Path]):
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix.lower() in TEXT_EXT:
                    try:
                        if p.stat().st_size <= MAX_FILE_BYTES:
                            yield p
                    except Exception:
                        continue


def detect_theme(line: str) -> str:
    low = line.lower()
    for theme, kws in KEYWORDS.items():
        if any(k in low for k in kws):
            return theme
    return 'general'


def should_keep(line: str) -> bool:
    t = line.strip()
    if len(t) < 20 or len(t) > 260:
        return False
    if t.startswith('#') or t.startswith('|---'):
        return False
    if t.startswith('http'):
        return False
    # keep bullets, status lines, concise statements with signal
    if re.search(r'(✅|❌|⚠️|\bok\b|\berror\b|\bfail|\bfix|\brelease|\bokr|\bcron|\bstrategy)', t, re.I):
        return True
    if t.startswith('- ') or t.startswith('* '):
        return True
    if ':' in t and len(t.split(':', 1)[0]) < 40:
        return True
    return False


def extract_snippets(path: Path) -> List[Snippet]:
    out: List[Snippet] = []
    try:
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    except Exception:
        return out

    for i, line in enumerate(lines, start=1):
        if should_keep(line):
            txt = re.sub(r'\s+', ' ', line.strip())
            out.append(Snippet(
                source=str(path.relative_to(WORKSPACE)),
                line_no=i,
                text=txt,
                theme=detect_theme(txt),
            ))
    return out


def materialize_report(snippets: List[Snippet], scanned: int, changed: int) -> Tuple[Dict, str]:
    by_theme: Dict[str, List[Snippet]] = {}
    for s in snippets:
        by_theme.setdefault(s.theme, []).append(s)

    payload = {
        'generated_at': now_iso(),
        'stats': {
            'files_scanned': scanned,
            'files_changed': changed,
            'new_snippets': len(snippets),
        },
        'themes': {
            k: [
                {'source': s.source, 'line': s.line_no, 'text': s.text}
                for s in v[:20]
            ]
            for k, v in sorted(by_theme.items(), key=lambda kv: len(kv[1]), reverse=True)
        }
    }

    md = [
        f"# Moltbook Idea Harvest ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
        '',
        f"- Files scanned: **{scanned}**",
        f"- Changed files processed: **{changed}**",
        f"- New snippets extracted: **{len(snippets)}**",
        '',
        '## Top themes',
    ]

    for theme, items in sorted(by_theme.items(), key=lambda kv: len(kv[1]), reverse=True):
        md.append(f"\n### {theme} ({len(items)})")
        for s in items[:12]:
            md.append(f"- `{s.source}#{s.line_no}` — {s.text}")

    md.append('\n## Post-angle suggestions')
    suggestions = [
        '1) Strategy writeback changed real runtime knobs (not dashboard theater).',
        '2) Verification reliability engineering: from failed captcha to deterministic solver pipeline.',
        '3) Cron hardening retrospective: timeout tuning + dedupe + delivery formatting contracts.',
    ]
    md.extend([f"- {x}" for x in suggestions])

    return payload, '\n'.join(md) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', action='append', help='Custom root path, repeatable')
    ap.add_argument('--max-snippets', type=int, default=MAX_SNIPPETS)
    args = ap.parse_args()

    roots = [Path(r) for r in args.root] if args.root else DEFAULT_ROOTS
    state = load_state()

    processed = state.get('processed_files', {})
    seen = state.get('seen_snippets', {})

    scanned = 0
    changed = 0
    new_snippets: List[Snippet] = []

    for p in iter_files(roots):
        scanned += 1
        fp = file_fingerprint(p)
        pkey = str(p)
        if processed.get(pkey) == fp:
            continue
        changed += 1

        snippets = extract_snippets(p)
        for s in snippets:
            h = sha1_text(f"{s.source}:{s.line_no}:{s.text}")
            if h in seen:
                continue
            seen[h] = now_iso()
            new_snippets.append(s)
            if len(new_snippets) >= args.max_snippets:
                break

        processed[pkey] = fp
        if len(new_snippets) >= args.max_snippets:
            break

    state['updated_at'] = now_iso()
    state['processed_files'] = processed
    state['seen_snippets'] = seen
    save_state(state)

    payload, md = materialize_report(new_snippets, scanned, changed)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    LATEST_MD.write_text(md, encoding='utf-8')

    print(json.dumps({
        'ok': True,
        'state_file': str(STATE_FILE),
        'latest_md': str(LATEST_MD),
        'latest_json': str(LATEST_JSON),
        'files_scanned': scanned,
        'files_changed': changed,
        'new_snippets': len(new_snippets),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
