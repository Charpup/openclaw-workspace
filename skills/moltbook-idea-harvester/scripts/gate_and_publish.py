#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
import requests

WORKSPACE = Path('/root/.openclaw/workspace')
BASE = WORKSPACE / 'memory' / 'moltbook-idea-harvest'
DRAFT_DIR = BASE / 'drafts'
STRATEGY_FILE = WORKSPACE / 'config' / 'moltbook-strategy.json'
FEEDBACK_DIR = WORKSPACE / 'memory' / 'moltbook-loop-feedback'
PUBLISH_STATE = FEEDBACK_DIR / 'publish-state.json'
LATEST_FEEDBACK = FEEDBACK_DIR / 'latest.json'


def run_json(cmd):
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out.strip())


def latest_draft():
    files = sorted(DRAFT_DIR.glob('post-draft-*.md'))
    return files[-1] if files else None


def extract_title(path: Path):
    txt = path.read_text(encoding='utf-8', errors='ignore')
    lines = txt.splitlines()
    if lines and lines[0].startswith('# '):
        return lines[0][2:].strip()
    return 'Untitled'


def reachable(url: str):
    try:
        r = requests.get(url, timeout=15)
        return r.status_code < 400, r.status_code
    except Exception:
        return False, None


def fetch_post_receipt(api_key: str, post_id: str):
    api = 'https://www.moltbook.com/api/v1'
    h = {'Authorization': f'Bearer {api_key}'}
    r = requests.get(f'{api}/posts/{post_id}', headers=h, timeout=20)
    p = r.json().get('post', {})
    return {
        'post_id': post_id,
        'title': p.get('title'),
        'verification_status': p.get('verification_status'),
        'is_spam': p.get('is_spam'),
        'created_at': p.get('created_at'),
        'author': (p.get('author') or {}).get('name'),
    }


def load_api_key():
    env = Path('/root/.openclaw/skills/moltbook-automation/.env')
    if env.exists():
        for line in env.read_text(encoding='utf-8', errors='ignore').splitlines():
            if line.startswith('MOLTBOOK_API_KEY='):
                return line.split('=', 1)[1].strip()
    return os.environ.get('MOLTBOOK_API_KEY')


def load_strategy_controls(default_threshold: int, default_submolt: str):
    controls = {
        'threshold': default_threshold,
        'daily_publish_budget': 1,
        'publish_mode': 'gated-auto',
        'submolt': default_submolt,
        'strategy': 'unknown',
    }
    if not STRATEGY_FILE.exists():
        return controls
    try:
        data = json.loads(STRATEGY_FILE.read_text(encoding='utf-8'))
        cp = data.get('content_policy', {})
        controls['threshold'] = int(cp.get('review_gate_threshold', controls['threshold']))
        controls['daily_publish_budget'] = int(cp.get('daily_publish_budget', controls['daily_publish_budget']))
        controls['publish_mode'] = cp.get('publish_mode', controls['publish_mode'])
        controls['submolt'] = cp.get('target_submolt', controls['submolt'])
        controls['strategy'] = data.get('strategy', controls['strategy'])
        return controls
    except Exception:
        return controls


def load_publish_state():
    if not PUBLISH_STATE.exists():
        return {'date': None, 'count': 0}
    try:
        return json.loads(PUBLISH_STATE.read_text(encoding='utf-8'))
    except Exception:
        return {'date': None, 'count': 0}


def save_publish_state(state):
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    PUBLISH_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def within_budget(budget: int):
    today = datetime.now().strftime('%Y-%m-%d')
    st = load_publish_state()
    if st.get('date') != today:
        st = {'date': today, 'count': 0}
    return st['count'] < budget, st


def increment_publish_count(state):
    state['count'] = int(state.get('count', 0)) + 1
    save_publish_state(state)


def write_feedback(payload):
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    payload['ts'] = datetime.utcnow().isoformat() + 'Z'
    LATEST_FEEDBACK.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--threshold', type=int, default=72)
    ap.add_argument('--submolt', default='openclaw')
    ap.add_argument('--use-strategy', action='store_true', default=True)
    args = ap.parse_args()

    controls = load_strategy_controls(args.threshold, args.submolt) if args.use_strategy else {
        'threshold': args.threshold, 'daily_publish_budget': 1, 'publish_mode': 'gated-auto', 'submolt': args.submolt, 'strategy': 'manual'
    }

    # 1) refresh harvest + draft
    harvest = run_json(['python3', str(WORKSPACE / 'skills/moltbook-idea-harvester/scripts/harvest.py')])
    run_json(['python3', str(WORKSPACE / 'skills/moltbook-idea-harvester/scripts/draft_post.py')])

    draft = latest_draft()
    if not draft:
        out = {'ok': False, 'error': 'no_draft', 'controls': controls}
        write_feedback(out)
        print(json.dumps(out, ensure_ascii=False))
        return

    # 2) budget gate first
    allowed, state = within_budget(int(controls['daily_publish_budget']))
    if not allowed:
        out = {
            'ok': True,
            'published': False,
            'reason': 'daily_publish_budget_reached',
            'controls': controls,
            'budget_state': state,
            'draft_file': str(draft),
            'harvest': harvest,
        }
        write_feedback(out)
        print(json.dumps(out, ensure_ascii=False))
        return

    # 3) review gate scoring
    threshold = int(controls['threshold'])
    gate = run_json([
        'python3', str(WORKSPACE / 'skills/moltbook-idea-harvester/scripts/review_gate.py'),
        '--draft-file', str(draft),
        '--threshold', str(threshold),
    ])
    if not gate.get('passed'):
        out = {
            'ok': True,
            'published': False,
            'reason': 'gate_failed',
            'gate': gate,
            'controls': controls,
            'budget_state': state,
            'draft_file': str(draft),
            'harvest': harvest,
        }
        write_feedback(out)
        print(json.dumps(out, ensure_ascii=False))
        return

    # 4) publish via challenge solver skill
    api_key = load_api_key()
    if not api_key:
        out = {'ok': False, 'error': 'missing_api_key', 'controls': controls}
        write_feedback(out)
        print(json.dumps(out, ensure_ascii=False))
        return

    post = run_json([
        'python3', str(WORKSPACE / 'skills/moltbook-challenge-solver/scripts/post_and_verify.py'),
        '--api-key', api_key,
        '--submolt', controls['submolt'],
        '--title', extract_title(draft),
        '--content-file', str(draft),
    ])

    url = post.get('post_url')
    ok, code = reachable(url) if url else (False, None)
    post['url_reachable_from_runner'] = ok
    post['url_status_from_runner'] = code

    if not ok and post.get('post_id'):
        pid = post['post_id']
        for c in [
            f'https://www.moltbook.com/post/{pid}',
            f'https://www.moltbook.com/p/{pid}',
            f'https://www.moltbook.com/posts/{pid}',
        ]:
            o, sc = reachable(c)
            if o:
                post['post_url'] = c
                post['url_reachable_from_runner'] = True
                post['url_status_from_runner'] = sc
                break

    receipt = None
    if post.get('post_id'):
        try:
            receipt = fetch_post_receipt(api_key, post['post_id'])
        except Exception:
            receipt = {'post_id': post.get('post_id'), 'error': 'receipt_fetch_failed'}

    verified = (post.get('verification_status') == 'verified')
    if verified:
        increment_publish_count(state)

    out = {
        'ok': True,
        'published': verified,
        'gate': gate,
        'controls': controls,
        'budget_state': state,
        'draft_file': str(draft),
        'harvest': harvest,
        'post': post,
        'acceptance_receipt': receipt,
        'note': 'URL may be geo-blocked for human regions; use acceptance_receipt as canonical proof.',
    }
    write_feedback(out)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
