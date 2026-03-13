#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path('/root/.openclaw/workspace')
OUT_DIR = WORKSPACE / 'memory' / 'moltbook-idea-harvest'
STATE = OUT_DIR / 'state.json'
LATEST_MD = OUT_DIR / 'latest.md'
LATEST_JSON = OUT_DIR / 'latest.json'
HARVESTIGNORE = WORKSPACE / 'config' / 'moltbook-harvestignore.txt'

EXCLUDE_DIRS = {'.git', 'node_modules', 'dist', 'build', '__pycache__', '.venv'}
TEXT_EXT = {'.md', '.txt', '.log', '.json', '.yaml', '.yml'}
MAX_FILE = 350_000
MAX_SNIPPETS = 1000

KEYWORDS = {
    'release': ['release', 'tag', 'version', 'published'],
    'ops': ['cron', 'schedule', 'automation', 'ops', 'runtime', 'timeout'],
    'quality': ['bug', 'fix', 'verify', 'stable', 'failure', 'error'],
    'growth': ['karma', 'followers', 'engagement', 'comments', 'posts', 'okr'],
    'architecture': ['strategy', 'writeback', 'pipeline', 'loop', 'profile', 'gate'],
}

REDACTIONS = [
    (re.compile(r'moltbook_sk_[A-Za-z0-9_\-]{16,}'), 'moltbook_sk_***REDACTED***'),
    (re.compile(r'ntn_[A-Za-z0-9]{20,}'), 'ntn_***REDACTED***'),
    (re.compile(r'(ghp|github_pat)_[A-Za-z0-9_]{20,}'), 'github_***REDACTED***'),
    (re.compile(r'(?i)(authorization:\s*bearer\s+)[A-Za-z0-9_\-\.]+'), r'\1***REDACTED***'),
    (re.compile(r'(?i)(api[_-]?key\s*[:=]\s*)([A-Za-z0-9_\-]{10,})'), r'\1***REDACTED***'),
    (re.compile(r'https://discord\.com/api/webhooks/[A-Za-z0-9/_\-]+'), 'https://discord.com/api/webhooks/***REDACTED***'),
    (re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'), '***EMAIL***'),
]


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(s: str):
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


def file_fp(path: Path):
    st = path.stat()
    return sha(f'{path}:{st.st_mtime_ns}:{st.st_size}')


def discover_roots():
    roots = [
        Path('/root/.openclaw/workspace/memory'),
        Path('/root/.openclaw/workspace/projects'),
        Path('/root/.openclaw/workspace/01_active'),
        Path('/root/.openclaw/workspace-orchestra'),
    ]

    # Include all agent workspaces on host: /root/workspace-*
    for p in Path('/root').glob('workspace-*'):
        roots.append(p)

    # Include selected shared areas for future agents
    roots.extend([
        Path('/root/.openclaw/workspace/03_deliverables'),
        Path('/root/.openclaw/workspace/02_archive'),
    ])

    uniq = []
    seen = set()
    for r in roots:
        rs = str(r)
        if rs not in seen and r.exists():
            seen.add(rs)
            uniq.append(r)
    return uniq


def load_ignore_patterns():
    patterns = [
        '**/.git/**', '**/node_modules/**', '**/dist/**', '**/build/**', '**/.venv/**', '**/__pycache__/**',
        '**/*.png', '**/*.jpg', '**/*.jpeg', '**/*.gif', '**/*.webp', '**/*.pdf', '**/*.zip', '**/*.tar*',
    ]
    if HARVESTIGNORE.exists():
        for line in HARVESTIGNORE.read_text(encoding='utf-8', errors='ignore').splitlines():
            t = line.strip()
            if t and not t.startswith('#'):
                patterns.append(t)
    return patterns


def ignored(path: Path, patterns):
    s = str(path)
    return any(fnmatch.fnmatch(s, p) for p in patterns)


def iter_files(roots, patterns):
    for root in roots:
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in EXCLUDE_DIRS]
            for fn in files:
                p = Path(d) / fn
                if ignored(p, patterns):
                    continue
                if p.suffix.lower() not in TEXT_EXT:
                    continue
                try:
                    if p.stat().st_size <= MAX_FILE:
                        yield p
                except Exception:
                    pass


def redact(text: str):
    t = text
    for rx, repl in REDACTIONS:
        t = rx.sub(repl, t)
    return t


def keep(line: str):
    t = line.strip()
    if len(t) < 20 or len(t) > 320:
        return False
    if t.startswith('#'):
        return False
    if re.search(r'(✅|❌|⚠️|\bfix\b|\bokr\b|\bcron\b|\bstrategy\b|\brelease\b|\bverify\b)', t, re.I):
        return True
    if t.startswith('- ') or t.startswith('* '):
        return True
    return ':' in t and len(t.split(':', 1)[0]) < 40


def theme(text: str):
    low = text.lower()
    for k, kws in KEYWORDS.items():
        if any(x in low for x in kws):
            return k
    return 'general'


def materialize(snippets, scanned, changed, roots):
    by = {}
    for s in snippets:
        by.setdefault(s['theme'], []).append(s)

    payload = {
        'generated_at': now(),
        'stats': {'files_scanned': scanned, 'files_changed': changed, 'new_snippets': len(snippets)},
        'roots': [str(r) for r in roots],
        'themes': {k: v[:25] for k, v in sorted(by.items(), key=lambda kv: len(kv[1]), reverse=True)}
    }

    lines = [
        f"# Moltbook Idea Harvest ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
        '',
        f"- Files scanned: **{scanned}**",
        f"- Changed files processed: **{changed}**",
        f"- New snippets extracted: **{len(snippets)}**",
        f"- Roots: **{len(roots)}**",
        '',
        '## Top themes',
    ]

    for k, arr in sorted(by.items(), key=lambda kv: len(kv[1]), reverse=True):
        lines.append(f"\n### {k} ({len(arr)})")
        for s in arr[:12]:
            lines.append(f"- `{s['source']}#{s['line']}` — {s['text']}")

    lines.append('\n## Post-angle suggestions')
    lines.append('- Strategy writeback changed real runtime knobs (not dashboard theater).')
    lines.append('- Verification reliability engineering: challenge solver + fallback taxonomy.')
    lines.append('- Cron hardening: timeout tuning + dedupe + output-format contracts.')

    return payload, '\n'.join(lines) + '\n'


def main():
    roots = discover_roots()
    patterns = load_ignore_patterns()
    st = load_state()
    processed = st.get('processed_files', {})
    seen = st.get('seen_snippets', {})

    scanned = changed = 0
    snippets = []

    for p in iter_files(roots, patterns):
        scanned += 1
        pkey = str(p)
        fpr = file_fp(p)
        if processed.get(pkey) == fpr:
            continue

        changed += 1
        try:
            lines = p.read_text(encoding='utf-8', errors='ignore').splitlines()
        except Exception:
            processed[pkey] = fpr
            continue

        rel = str(p)
        for i, line in enumerate(lines, start=1):
            if not keep(line):
                continue
            txt = redact(re.sub(r'\s+', ' ', line.strip()))
            h = sha(f'{rel}:{i}:{txt}')
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

    payload, md = materialize(snippets, scanned, changed, roots)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    LATEST_MD.write_text(md, encoding='utf-8')

    print(json.dumps({
        'ok': True,
        'state_file': str(STATE),
        'latest_md': str(LATEST_MD),
        'latest_json': str(LATEST_JSON),
        'files_scanned': scanned,
        'files_changed': changed,
        'new_snippets': len(snippets),
        'roots': len(roots),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
