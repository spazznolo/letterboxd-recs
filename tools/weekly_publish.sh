#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

USERNAME="${1:-spazznolo}"
TOP_N="${2:-100}"
BRANCH="${3:-main}"
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

echo "[weekly_publish] Running weekly pipeline for $USERNAME (top_n=$TOP_N)"
/usr/bin/caffeinate -i .venv/bin/letterboxd-recs weekly --username "$USERNAME" --top-n "$TOP_N"

# Reassert the repo root before git commands in case the long-running pipeline
# leaves the shell in an invalid working directory state under launchd.
cd "$REPO_ROOT"

if [[ ! -f docs/index.html ]]; then
  echo "[weekly_publish] docs/index.html not found after weekly run"
  exit 1
fi

if /usr/bin/git -C "$REPO_ROOT" diff --quiet -- docs/index.html; then
  echo "[weekly_publish] No docs/index.html changes to publish"
  exit 0
fi

/usr/bin/git -C "$REPO_ROOT" add docs/index.html
/usr/bin/git -C "$REPO_ROOT" commit -m "Update recommendations page ($(date +%Y-%m-%d))"
/usr/bin/git -C "$REPO_ROOT" push origin "$BRANCH"

echo "[weekly_publish] Published docs/index.html to origin/$BRANCH"
