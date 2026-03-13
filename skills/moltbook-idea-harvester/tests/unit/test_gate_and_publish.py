#!/usr/bin/env python3
"""Tests for strategy-driven gate_and_publish logic."""
import json
import os
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE / 'scripts'))

from importlib.machinery import SourceFileLoader
gp = SourceFileLoader('gate_and_publish', str(BASE / 'scripts' / 'gate_and_publish.py')).load_module()


def test_load_strategy_controls_fallback():
    with tempfile.TemporaryDirectory() as td:
        gp.STRATEGY_FILE = Path(td) / 'strategy.json'
        c = gp.load_strategy_controls(72, 'openclaw')
        assert c['threshold'] == 72
        assert c['submolt'] == 'openclaw'
        print('test_load_strategy_controls_fallback ok')


def test_load_strategy_controls_from_file():
    with tempfile.TemporaryDirectory() as td:
        gp.STRATEGY_FILE = Path(td) / 'strategy.json'
        gp.STRATEGY_FILE.write_text(json.dumps({
            'strategy': 'quality',
            'content_policy': {
                'review_gate_threshold': 68,
                'daily_publish_budget': 2,
                'publish_mode': 'gated-auto',
                'target_submolt': 'memory'
            }
        }))
        c = gp.load_strategy_controls(72, 'openclaw')
        assert c['threshold'] == 68
        assert c['daily_publish_budget'] == 2
        assert c['submolt'] == 'memory'
        print('test_load_strategy_controls_from_file ok')


def test_within_budget_logic():
    with tempfile.TemporaryDirectory() as td:
        gp.FEEDBACK_DIR = Path(td)
        gp.PUBLISH_STATE = gp.FEEDBACK_DIR / 'publish-state.json'
        allowed, st = gp.within_budget(1)
        assert allowed is True
        gp.increment_publish_count(st)
        allowed2, _ = gp.within_budget(1)
        assert allowed2 is False
        print('test_within_budget_logic ok')


def test_write_feedback_exists():
    with tempfile.TemporaryDirectory() as td:
        gp.FEEDBACK_DIR = Path(td)
        gp.LATEST_FEEDBACK = gp.FEEDBACK_DIR / 'latest.json'
        gp.write_feedback({'published': True})
        assert gp.LATEST_FEEDBACK.exists()
        data = json.loads(gp.LATEST_FEEDBACK.read_text())
        assert data['published'] is True
        assert 'ts' in data
        print('test_write_feedback_exists ok')


if __name__ == '__main__':
    test_load_strategy_controls_fallback()
    test_load_strategy_controls_from_file()
    test_within_budget_logic()
    test_write_feedback_exists()
    print('All tests passed')
