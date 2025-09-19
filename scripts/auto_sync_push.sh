#!/usr/bin/env bash
set -euo pipefail

# Periodically push local branches that are ahead of their upstream.
# If upstream is missing but origin/<branch> exists, set upstream automatically.

cd "${AIPIK_REPO:-$(dirname "$0")/..}"
interval="${AUTO_SYNC_INTERVAL:-20}"

mkdir -p Logs

while true; do
  git fetch --all --prune >/dev/null 2>&1 || true
  # Iterate all local branches
  while IFS= read -r br; do
    [ -n "$br" ] || continue
    # Ensure upstream if possible
    upstream="$(git rev-parse --abbrev-ref "$br@{upstream}" 2>/dev/null || true)"
    if [ -z "$upstream" ]; then
      if git show-ref --verify --quiet "refs/remotes/origin/$br"; then
        git branch --set-upstream-to "origin/$br" "$br" >/dev/null 2>&1 || true
        upstream="origin/$br"
        echo "$(date -Is) [$br] set upstream to origin/$br" | tee -a Logs/auto_sync.log
      fi
    fi
    if [ -n "$upstream" ]; then
      ahead=$(git rev-list --count "$upstream".."$br" 2>/dev/null || echo 0)
      if [ "${ahead:-0}" -gt 0 ]; then
        if git push origin "$br"; then
          echo "$(date -Is) [$br] pushed ($ahead commits)" | tee -a Logs/auto_sync.log
        else
          echo "$(date -Is) [$br] push failed" | tee -a Logs/auto_sync.log
        fi
      fi
    fi
  done < <(git for-each-ref --format='%(refname:short)' refs/heads)
  sleep "$interval"
done

