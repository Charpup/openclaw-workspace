#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
import requests

WORKSPACE = Path('/root/.openclaw/workspace')
BASE = WORKSPACE / 'memory' / 'moltbook-idea-harvest'
DRAFT_DIR = BASE / 'drafts'


def run_json(cmd):
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out.strip())


def latest_draft():
    files = sorted(DRAFT_DIR.glob('post-draft-*.md'))
    return files[-1] if files else None


def extract_title_and_content(path: Path):
    txt = path.read_text(encoding='utf-8', errors='ignore')
    lines = txt.splitlines()
    title = 'Untitled'
    body = txt
    if lines and lines[0].startswith('# '):
        title = lines[0][2:].strip()
        body = '\n'.join(lines[2:]).strip() if len(lines) > 2 else ''
    return title, body


def reachable(url: str):
    try:
        r = requests.get(url, timeout=15)
        return r.status_code < 400, r.status_code
    except Exception:
        return False, None


def load_api_key():
    env = Path('/root/.openclaw/skills/moltbook-automation/.env')
    if env.exists():
        for line in env.read_text(encoding='utf-8', errors='ignore').splitlines():
            if line.startswith('MOLTBOOK_API_KEY='):
                return line.split('=', 1)[1].strip()
    return os.environ.get('MOLTBOOK_API_KEY')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--threshold', type=int, default=72)
    ap.add_argument('--submolt', default='openclaw')
    args = ap.parse_args()

    # 1) refresh harvest + draft
    run_json(['python3', str(WORKSPACE / 'skills/moltbook-idea-harvester/scripts/harvest.py')])
    run_json(['python3', str(WORKSPACE / 'skills/moltbook-idea-harvester/scripts/draft_post.py')])

    draft = latest_draft()
    if not draft:
        print(json.dumps({'ok': False, 'error': 'no_draft'}))
        return

    # 2) gate scoring
    gate = run_json(['python3', str(WORKSPACE / 'skills/moltbook-idea-harvester/scripts/review_gate.py'), '--draft-file', str(draft), '--threshold', str(args.threshold)])
    if not gate.get('passed'):
        print(json.dumps({'ok': True, 'published': False, 'gate': gate, 'draft_file': str(draft)}))
        return

    # 3) publish via challenge solver skill
    api_key = load_api_key()
    if not api_key:
        print(json.dumps({'ok': False, 'error': 'missing_api_key'}))
        return

    title, _ = extract_title_and_content(draft)
    post = run_json([
        'python3', str(WORKSPACE / 'skills/moltbook-challenge-solver/scripts/post_and_verify.py'),
        '--api-key', api_key,
        '--submolt', args.submolt,
        '--title', title,
        '--content-file', str(draft),
    ])

    url = post.get('post_url')
    ok, code = reachable(url) if url else (False, None)
    post['url_reachable'] = ok
    post['url_status'] = code

    # fallback URL hints
    if not ok and post.get('post_id'):
        pid = post['post_id']
        cands = [
            f'https://www.moltbook.com/post/{pid}',
            f'https://www.moltbook.com/p/{pid}',
            f'https://www.moltbook.com/posts/{pid}',
        ]
        for c in cands:
            o, sc = reachable(c)
            if o:
                post['post_url'] = c
                post['url_reachable'] = True
                post['url_status'] = sc
                break

    print(json.dumps({
        'ok': True,
        'published': True,
        'gate': gate,
        'draft_file': str(draft),
        'post': post,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
