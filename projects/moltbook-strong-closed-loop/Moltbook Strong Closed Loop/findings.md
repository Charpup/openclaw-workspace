# Findings — Moltbook Strong Closed Loop

## Target Architecture
Single strategy profile drives both:
1) Operations loop (metrics/engage cadence/timeouts)
2) Content loop (harvest->draft->gate->publish)

And both loops write feedback back for next strategy cycle.

## Current Gaps
- Strategy profile does not currently control gate threshold/publish budget.
- Content pipeline can run independently from strategy engine.
- Publish outcomes are not persisted as control feedback for strategy.

## Scope (locked)
- In scope:
  - Extend strategy profile with content-control fields
  - Make gate/publish read strategy profile
  - Add daily publish budget enforcement + feedback writeback
  - Add orchestrator and cron runtime wiring
- Out of scope:
  - New social platforms
  - Major prompt architecture redesign
  - Non-Moltbook workflows

## TDD/SDD acceptance
- Tests for strategy-driven threshold/budget resolution
- Tests for budget enforcement and feedback file write
- Dry-run + one forced run verification
