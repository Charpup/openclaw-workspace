# Task Plan — Moltbook Strong Closed Loop

## SDD (Spec-first)
- Define strategy content-control contract:
  - `content_policy.review_gate_threshold`
  - `content_policy.daily_publish_budget`
  - `content_policy.publish_mode`
- Define feedback contract:
  - `memory/moltbook-loop-feedback/latest.json`
  - includes gate score, publish result, verification status, post_id, timestamp

## TDD (Red->Green)
1. Add tests for strategy config resolution in gate pipeline
2. Add tests for daily publish budget enforcement
3. Add tests for feedback record persistence

## Implementation
1. Upgrade `scripts/moltbook-compound-mechanism.sh`
2. Upgrade `skills/moltbook-idea-harvester/scripts/gate_and_publish.py`
3. Add orchestrator `scripts/moltbook-strong-loop.sh`
4. Wire cron to execute orchestrator

## Verification
- Unit tests pass
- One manual orchestrator run passes
- Cron job updated and enabled
