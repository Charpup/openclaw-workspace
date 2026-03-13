#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def score_text(text: str):
    score = 0
    reasons = []

    words = re.findall(r"\b\w+\b", text)
    wc = len(words)

    # Length (target 160-380)
    if 160 <= wc <= 380:
        score += 20; reasons.append('length:good')
    elif 120 <= wc <= 500:
        score += 10; reasons.append('length:acceptable')
    else:
        reasons.append('length:weak')

    # Evidence (numbers, arrows, %, version tags)
    if re.search(r"\b\d+\b", text):
        score += 10; reasons.append('evidence:numbers')
    if re.search(r"(->|→|\b\d+%\b|v\d+\.\d+)", text):
        score += 10; reasons.append('evidence:change_markers')

    # Structure markers
    markers = 0
    if re.search(r"\bwhat changed\b|\bimplemented loop\b|\btakeaway\b", text, re.I): markers += 1
    if re.search(r"\bquestion\b|\?", text, re.I): markers += 1
    if re.search(r"\n- ", text): markers += 1
    score += markers * 10
    reasons.append(f'structure:{markers}')

    # Token-noise penalty
    if re.search(r"REDACTED|moltbook_sk_|ntn_", text):
        score -= 25; reasons.append('safety:leak_like')

    # Generic fluff penalty (simple heuristic)
    fluff_hits = len(re.findall(r"\b(amazing|awesome|revolutionary|incredible)\b", text, re.I))
    if fluff_hits:
        score -= min(10, fluff_hits * 3)
        reasons.append(f'quality:fluff_{fluff_hits}')

    score = max(0, min(100, score))
    return score, reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--draft-file', required=True)
    ap.add_argument('--threshold', type=int, default=70)
    args = ap.parse_args()

    p = Path(args.draft_file)
    text = p.read_text(encoding='utf-8', errors='ignore')

    score, reasons = score_text(text)
    passed = score >= args.threshold

    print(json.dumps({
        'ok': True,
        'draft_file': str(p),
        'score': score,
        'threshold': args.threshold,
        'passed': passed,
        'reasons': reasons,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
