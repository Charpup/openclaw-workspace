#!/bin/bash
# moltbook-compound-mechanism.sh - Dynamic OKR strategy profile generator
# Usage:
#   bash scripts/moltbook-compound-mechanism.sh           # generate profile only
#   AUTO_APPLY=1 bash scripts/moltbook-compound-mechanism.sh  # generate + apply writeback

set -euo pipefail

WORKSPACE="/root/.openclaw/workspace"
STRATEGY_FILE="$WORKSPACE/config/moltbook-strategy.json"
WEBHOOK_URL="${MOLTBOOK_WEBHOOK_URL:-}"
API_BASE="${MOLTBOOK_API_BASE:-https://www.moltbook.com/api/v1}"
API_KEY="${MOLTBOOK_API_KEY:-}"
AUTHOR_NAME="${MOLTBOOK_AUTHOR_NAME:-Charpup_V2}"

mkdir -p "$WORKSPACE/config" "$WORKSPACE/logs"

: "${API_KEY:?MOLTBOOK_API_KEY is required}"
: "${WEBHOOK_URL:?MOLTBOOK_WEBHOOK_URL is required}"

# ---------- Fetch metrics (with fallback) ----------
ACCOUNT_INFO=$(curl -s "$API_BASE/agents/me" -H "Authorization: Bearer $API_KEY")
KARMA=$(echo "$ACCOUNT_INFO" | jq -r '.agent.karma // empty')
FOLLOWERS=$(echo "$ACCOUNT_INFO" | jq -r '.agent.follower_count // empty')

if [ -z "$KARMA" ] || [ -z "$FOLLOWERS" ]; then
  FALLBACK=$(curl -s "$API_BASE/posts?author=$AUTHOR_NAME&sort=new&limit=1" -H "Authorization: Bearer $API_KEY")
  KARMA=$(echo "$FALLBACK" | jq -r '.posts[0].author.karma // 0')
  FOLLOWERS=$(echo "$FALLBACK" | jq -r '.posts[0].author.followerCount // 0')
fi

KARMA=${KARMA:-0}
FOLLOWERS=${FOLLOWERS:-0}

KARMA_TARGET=120
FOLLOWERS_TARGET=18
KARMA_PROGRESS=$(( KARMA * 100 / KARMA_TARGET ))
FOLLOWERS_PROGRESS=$(( FOLLOWERS * 100 / FOLLOWERS_TARGET ))

# ---------- Strategy tier matrix ----------
if [ "$KARMA" -lt 100 ]; then
  STRATEGY="aggressive"
  DAILY_COMMENTS=24
  WEEKLY_POSTS=5
  AUTO_ENGAGE_EVERY="3h"
  OPS_MVP_EVERY="4h"
  HIGH_VALUE_THRESHOLD=450
  SUGGESTION_LIMIT=7
  FOCUS="volume + consistency"
  ENGAGEMENT_MODE="breadth-first"
  LANGUAGE_STYLE="concise_en_data_dense"
  CONTENT_QUALITY_GATE="short_data_backed"
  POST_MIN_WORDS=120
  POST_MAX_WORDS=220
  CTA_STYLE="direct_follow_prompt"
  REVIEW_GATE_THRESHOLD=65
  DAILY_PUBLISH_BUDGET=2
  PUBLISH_MODE="gated-auto"
  TARGET_SUBMOLT="openclaw"
elif [ "$KARMA" -lt 150 ]; then
  STRATEGY="quality"
  DAILY_COMMENTS=15
  WEEKLY_POSTS=3
  AUTO_ENGAGE_EVERY="4h"
  OPS_MVP_EVERY="4h"
  HIGH_VALUE_THRESHOLD=600
  SUGGESTION_LIMIT=5
  FOCUS="deep engagement"
  ENGAGEMENT_MODE="mixed"
  LANGUAGE_STYLE="structured_technical_en"
  CONTENT_QUALITY_GATE="claim_evidence_question"
  POST_MIN_WORDS=180
  POST_MAX_WORDS=320
  CTA_STYLE="discussion_question"
  REVIEW_GATE_THRESHOLD=70
  DAILY_PUBLISH_BUDGET=1
  PUBLISH_MODE="gated-auto"
  TARGET_SUBMOLT="openclaw"
else
  STRATEGY="authority"
  DAILY_COMMENTS=9
  WEEKLY_POSTS=2
  AUTO_ENGAGE_EVERY="6h"
  OPS_MVP_EVERY="6h"
  HIGH_VALUE_THRESHOLD=800
  SUGGESTION_LIMIT=4
  FOCUS="thought leadership"
  ENGAGEMENT_MODE="depth-first"
  LANGUAGE_STYLE="framework_thought_leadership_en"
  CONTENT_QUALITY_GATE="benchmark_framework_reproducible"
  POST_MIN_WORDS=260
  POST_MAX_WORDS=450
  CTA_STYLE="invite_critique"
  REVIEW_GATE_THRESHOLD=78
  DAILY_PUBLISH_BUDGET=1
  PUBLISH_MODE="gated-auto"
  TARGET_SUBMOLT="openclaw"
fi

UPDATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# ---------- Persist full strategy profile ----------
cat > "$STRATEGY_FILE" <<EOF
{
  "updated": "$UPDATED_AT",
  "metrics": {
    "karma": $KARMA,
    "followers": $FOLLOWERS,
    "karma_target": $KARMA_TARGET,
    "followers_target": $FOLLOWERS_TARGET,
    "karma_progress": $KARMA_PROGRESS,
    "followers_progress": $FOLLOWERS_PROGRESS
  },
  "strategy": "$STRATEGY",
  "execution": {
    "daily_comments": $DAILY_COMMENTS,
    "weekly_posts": $WEEKLY_POSTS,
    "auto_engage_every": "$AUTO_ENGAGE_EVERY",
    "ops_mvp_every": "$OPS_MVP_EVERY",
    "high_value_threshold": $HIGH_VALUE_THRESHOLD,
    "suggestion_limit": $SUGGESTION_LIMIT
  },
  "content_policy": {
    "quality_gate": "$CONTENT_QUALITY_GATE",
    "language_style": "$LANGUAGE_STYLE",
    "post_words": { "min": $POST_MIN_WORDS, "max": $POST_MAX_WORDS },
    "cta_style": "$CTA_STYLE",
    "review_gate_threshold": $REVIEW_GATE_THRESHOLD,
    "daily_publish_budget": $DAILY_PUBLISH_BUDGET,
    "publish_mode": "$PUBLISH_MODE",
    "target_submolt": "$TARGET_SUBMOLT"
  },
  "engagement_policy": {
    "mode": "$ENGAGEMENT_MODE",
    "focus": "$FOCUS"
  }
}
EOF

# ---------- Report ----------
curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "{
    \"username\": \"Galatea Strategy Engine 🎯\",
    \"embeds\": [{
      \"title\": \"🔄 Compound Strategy Updated\",
      \"description\": \"Dynamic OKR strategy profile generated\",
      \"color\": 15158332,
      \"fields\": [
        {\"name\": \"📊 Current Status\", \"value\": \"Karma: $KARMA/$KARMA_TARGET ($KARMA_PROGRESS%)\\nFollowers: $FOLLOWERS/$FOLLOWERS_TARGET ($FOLLOWERS_PROGRESS%)\", \"inline\": true},
        {\"name\": \"🎯 Strategy\", \"value\": \"$STRATEGY\", \"inline\": true},
        {\"name\": \"📋 Execution Params\", \"value\": \"Comments: $DAILY_COMMENTS/day\\nPosts: $WEEKLY_POSTS/week\\nAuto-engage: $AUTO_ENGAGE_EVERY\", \"inline\": false},
        {\"name\": \"🧭 Policy\", \"value\": \"$ENGAGEMENT_MODE · $LANGUAGE_STYLE\", \"inline\": false},
        {\"name\": \"🧪 Content Control\", \"value\": \"Gate: $REVIEW_GATE_THRESHOLD\\nBudget: $DAILY_PUBLISH_BUDGET/day\\nMode: $PUBLISH_MODE\", \"inline\": false}
      ],
      \"timestamp\": \"$UPDATED_AT\"
    }]
  }" >/dev/null

# ---------- Optional auto-apply ----------
if [ "${AUTO_APPLY:-0}" = "1" ]; then
  bash "$WORKSPACE/scripts/strategy-apply.sh" --apply || true
fi

echo "[$(date)] Strategy updated: $STRATEGY (Karma: $KARMA, Followers: $FOLLOWERS)" >> "$WORKSPACE/logs/compound.log"
echo "Strategy profile written: $STRATEGY_FILE"