#!/usr/bin/env bash
set -euo pipefail

# Periodically fast-forward local branches to origin if workspace is clean.
# Defaults: sync main and machine-<hostname> every 30s.

cd "${AIPIK_REPO:-$(dirname "$0")/..}"
interval="${AUTO_SYNC_INTERVAL:-30}"
host_branch="machine-$(hostname)"

mkdir -p Logs

while true; do
  for br in main "$host_branch"; do
    # Ensure branch exists locally or track remote
    if git show-ref --verify --quiet "refs/heads/$br"; then
      :
    elif git show-ref --verify --quiet "refs/remotes/origin/$br"; then
      git branch --track "$br" "origin/$br" >/dev/null 2>&1 || true
    else
      continue
    fi

    # Skip if local changes present
    if ! git diff --quiet || ! git diff --cached --quiet; then
      echo "$(date -Is) [$br] local changes; skip pull" | tee -a Logs/auto_sync.log
      continue
    fi

    git fetch --all --prune >/dev/null 2>&1 || true
    remote_hash="$(git rev-parse --verify "origin/$br" 2>/dev/null || true)"
    local_hash="$(git rev-parse --verify "$br" 2>/dev/null || true)"
    if [ -n "$remote_hash" ] && [ "$remote_hash" != "$local_hash" ]; then
      git switch -q "$br" || git switch -q -t "origin/$br" || true
      if git merge --ff-only "origin/$br"; then
        echo "$(date -Is) [$br] fast-forwarded to $remote_hash" | tee -a Logs/auto_sync.log
      else
        echo "$(date -Is) [$br] cannot fast-forward; manual resolve needed" | tee -a Logs/auto_sync.log
      fi
    fi
  done
  sleep "$interval"
done

