#!/bin/bash
# Strong closed-loop orchestrator
# strategy -> apply -> gated content publish -> feedback

set -euo pipefail

WORKSPACE="/root/.openclaw/workspace"
THRESHOLD_FALLBACK="70"

# 1) Recompute strategy and auto-apply runtime params
AUTO_APPLY=1 bash "$WORKSPACE/scripts/moltbook-compound-mechanism.sh"

# 2) Run gated publish pipeline (strategy-driven threshold/budget)
python3 "$WORKSPACE/skills/moltbook-idea-harvester/scripts/gate_and_publish.py" --threshold "$THRESHOLD_FALLBACK" --use-strategy
