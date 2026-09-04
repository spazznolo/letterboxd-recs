#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

USERNAME="${1:-spazznolo}"
TOP_N="${2:-100}"
BRANCH="${3:-main}"
SIMILAR_USERS="${4:-100}"
NEW_USERS="${5:-20}"
BLOG_REPO="${BLOG_REPO:-/Users/jspagnolo/Documents/GitHub/spazznolo.github.io}"
BLOG_BRANCH="${BLOG_BRANCH:-master}"
BLOG_ASSET="${BLOG_REPO}/assets/data/letterboxd-recs-feed.txt"
LOCK_FILE="${REPO_ROOT}/.weekly_publish.lock"

if [[ -f "$LOCK_FILE" ]]; then
  EXISTING_PID="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ -n "$EXISTING_PID" ]] && kill -0 "$EXISTING_PID" 2>/dev/null; then
    echo "[weekly_publish] Existing run detected (pid=$EXISTING_PID); exiting"
    exit 0
  fi
  rm -f "$LOCK_FILE"
fi

echo "$$" > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

if [[ ! -d "$BLOG_REPO/.git" ]]; then
  echo "[weekly_publish] Blog repo not found: $BLOG_REPO"
  exit 1
fi

echo "[weekly_publish] Syncing blog origin/$BLOG_BRANCH"
/usr/bin/git -C "$BLOG_REPO" pull --ff-only origin "$BLOG_BRANCH"

echo "[weekly_publish] Syncing origin/$BRANCH"
/usr/bin/git -C "$REPO_ROOT" pull --ff-only origin "$BRANCH"

echo "[weekly_publish] Running weekly pipeline for $USERNAME (top_n=$TOP_N similar_users=$SIMILAR_USERS new_users=$NEW_USERS)"
/usr/bin/caffeinate -i .venv/bin/letterboxd-recs weekly \
  --username "$USERNAME" \
  --top-n "$TOP_N" \
  --similar-users "$SIMILAR_USERS" \
  --new-users "$NEW_USERS" \
  --out "$BLOG_ASSET"

# Reassert the repo root before git commands in case the long-running pipeline
# leaves the shell in an invalid working directory state under launchd.
cd "$REPO_ROOT"

if [[ ! -f "$BLOG_ASSET" ]]; then
  echo "[weekly_publish] Blog recommendation page not found after weekly run"
  exit 1
fi

if /usr/bin/git -C "$BLOG_REPO" diff --quiet -- assets/data/letterboxd-recs.html; then
  echo "[weekly_publish] No blog recommendation changes to publish"
else
  /usr/bin/git -C "$BLOG_REPO" add assets/data/letterboxd-recs-feed.txt
  /usr/bin/git -C "$BLOG_REPO" commit -m "Update Letterboxd recommendations ($(date +%Y-%m-%d))"
  /usr/bin/git -C "$BLOG_REPO" push origin "$BLOG_BRANCH"
  echo "[weekly_publish] Published Letterboxd recommendations to blog origin/$BLOG_BRANCH"
fi
