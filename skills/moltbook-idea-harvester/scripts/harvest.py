#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path('/root/.openclaw/workspace')
ROOTS = [WORKSPACE / 'memory', WORKSPACE / 'projects', WORKSPACE / '01_active']
EXCLUDE = {'.git', 'node_modules', 'dist', 'build', '__pycache__', '.venv'}
EXTS = {'.md', '.txt', '.log', '.json', '.yaml', '.yml'}
MAX_FILE = 300_000
MAX_SNIPPETS = 800

OUT_DIR = WORKSPACE / 'memory' / 'moltbook-idea-harvest'
STATE = OUT_DIR / 'state.json'
LATEST_MD = OUT_DIR / 'latest.md'
LATEST_JSON = OUT_DIR / 'latest.json'

KEYWORDS = {
    'release': ['release', 'tag', 'version', 'published'],
    'ops': ['cron', 'schedule', 'automation', 'ops', 'runtime'],
    'quality': ['bug', 'fix', 'verify', 'timeout', 'stable'],
    'growth': ['karma', 'followers', 'engagement', 'comments', 'posts', 'okr'],
    'architecture': ['strategy', 'writeback', 'pipeline', 'loop', 'profile'],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def sh(s: str):
    return hashlib.sha1(s.encode('utf-8', errors='ignore')).hexdigest()


def load_state():
    if not STATE.exists():
        return {'updated_at': None, 'processed_files': {}, 'seen_snippets': {}}
    try:
        return json.loads(STATE.read_text(encoding='utf-8'))
    except Exception:
        return {'updated_at': None, 'processed_files': {}, 'seen_snippets': {}}


def save_state(st):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding='utf-8')


def fp(path: Path):
    st = path.stat()
    return sh(f"{path}:{st.st_mtime_ns}:{st.st_size}")


def iter_files():
    for root in ROOTS:
        if not root.exists():
            continue
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in EXCLUDE]
            for fn in files:
                p = Path(d) / fn
                if p.suffix.lower() in EXTS:
                    try:
                        if p.stat().st_size <= MAX_FILE:
                            yield p
                    except Exception:
                        pass


def keep(line: str):
    t = line.strip()
    if len(t) < 20 or len(t) > 260:
        return False
    if t.startswith('#'):
        return False
    if re.search(r'(✅|❌|⚠️|\bfix\b|\bokr\b|\bcron\b|\bstrategy\b|\brelease\b)', t, re.I):
        return True
    if t.startswith('- ') or t.startswith('* '):
        return True
    return ':' in t and len(t.split(':', 1)[0]) < 40


def theme(t: str):
    low = t.lower()
    for k, arr in KEYWORDS.items():
        if any(x in low for x in arr):
            return k
    return 'general'


def main():
    st = load_state()
    processed = st.get('processed_files', {})
    seen = st.get('seen_snippets', {})

    scanned = changed = 0
    snippets = []

    for p in iter_files():
        scanned += 1
        pkey = str(p)
        fpr = fp(p)
        if processed.get(pkey) == fpr:
            continue
        changed += 1
        try:
            lines = p.read_text(encoding='utf-8', errors='ignore').splitlines()
        except Exception:
            processed[pkey] = fpr
            continue

        rel = str(p.relative_to(WORKSPACE))
        for i, line in enumerate(lines, start=1):
            if not keep(line):
                continue
            txt = re.sub(r'\s+', ' ', line.strip())
            h = sh(f'{rel}:{i}:{txt}')
            if h in seen:
                continue
            seen[h] = now()
            snippets.append({'source': rel, 'line': i, 'text': txt, 'theme': theme(txt)})
            if len(snippets) >= MAX_SNIPPETS:
                break

        processed[pkey] = fpr
        if len(snippets) >= MAX_SNIPPETS:
            break

    st['updated_at'] = now()
    st['processed_files'] = processed
    st['seen_snippets'] = seen
    save_state(st)

    by = {}
    for s in snippets:
        by.setdefault(s['theme'], []).append(s)

    payload = {
        'generated_at': now(),
        'stats': {'files_scanned': scanned, 'files_changed': changed, 'new_snippets': len(snippets)},
        'themes': {k: v[:20] for k, v in sorted(by.items(), key=lambda kv: len(kv[1]), reverse=True)}
    }

    lines = [
        f"# Moltbook Idea Harvest ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
        '',
        f"- Files scanned: **{scanned}**",
        f"- Changed files processed: **{changed}**",
        f"- New snippets extracted: **{len(snippets)}**",
        '',
        '## Top themes'
    ]
    for k, arr in sorted(by.items(), key=lambda kv: len(kv[1]), reverse=True):
        lines.append(f"\n### {k} ({len(arr)})")
        for s in arr[:12]:
            lines.append(f"- `{s['source']}#{s['line']}` — {s['text']}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    LATEST_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(json.dumps({
        'ok': True,
        'state_file': str(STATE),
        'latest_md': str(LATEST_MD),
        'latest_json': str(LATEST_JSON),
        'files_scanned': scanned,
        'files_changed': changed,
        'new_snippets': len(snippets),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
