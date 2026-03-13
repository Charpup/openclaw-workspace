# Findings & Decisions

## Requirements
- Add redaction mechanism to idea harvester (gitignore-like safety layer).
- Expand harvesting scope to host-wide agent workspaces (including future agents).
- Add review gate scoring for drafts; auto publish only when threshold is met.
- Validate post link reachability before returning acceptance link.

## Implemented
1. Host-wide incremental harvester
   - `skills/moltbook-idea-harvester/scripts/harvest.py`
   - Discovers `/root/workspace-*` plus workspace roots
   - Incremental fingerprints + snippet dedupe index
   - Redaction filters for keys/tokens/webhooks/emails
   - Ignore patterns from `config/moltbook-harvestignore.txt`

2. Draft + Gate + Publish pipeline
   - `draft_post.py` (draft generation)
   - `review_gate.py` (score gate)
   - `gate_and_publish.py` (closed loop)

3. Auto-publish integration
   - Uses `moltbook-challenge-solver/post_and_verify.py`
   - Only publishes when score >= threshold
   - Checks URL reachability and applies fallback URL candidates

4. Cron integration
   - Updated daily job to run gated pipeline:
     `moltbook-idea-harvest-and-gated-publish-daily`

## Verification
- Harvest ran successfully with host-wide coverage and produced deduped outputs.
- Gated publish tested:
  - fail path (score below threshold): no publish
  - pass path (lower threshold test): published + verified + reachable link

## Link Issue Root Cause
- `/post/{id}` format is valid.
- Prior inaccessible cases were tied to verification failure / state propagation timing, not wrong URL template.
