#!/usr/bin/env bash
set -euo pipefail

# Periodic progress reporter. Writes a line every 5 minutes with key counters.
# Usage:
#   nohup bash scripts/progress_report.sh > Logs/progress.log 2>&1 & echo $! > tmp/progress.pid

interval=${1:-300}

grounded_root="out/visual/grounded_regions"
pages_root="out/visual/playbook"

snap() {
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  # grounded regions progress (sum over all units)
  gr_tot=$(find "$grounded_root" -name 'region-*.json' 2>/dev/null | wc -l | awk '{print $1}')
  gr_done=$(find "$grounded_root" -name 'region-*.struct.json' -size +0c 2>/dev/null | wc -l | awk '{print $1}')
  # page-level artifacts (per-page struct.json under playbook)
  pg_done=$(find "$pages_root" -maxdepth 1 -name '*.struct.json' 2>/dev/null | wc -l | awk '{print $1}')
  # index size
  idx_lines=$(wc -l out/openai_embeddings.ndjson 2>/dev/null | awk '{print $1}')
  # last metrics from log (if any)
  last_rec1=$(rg -n "^recall@1:" -n Logs/batch_cv_run.log 2>/dev/null | tail -n 1 | awk '{print $2}')
  last_mrr=$(rg -n "^MRR:" Logs/batch_cv_run.log 2>/dev/null | tail -n 1 | awk '{print $2}')
  echo "$ts grounded=$gr_done/$gr_tot pages_struct=$pg_done index_lines=$idx_lines recall@1=${last_rec1:-NA} MRR=${last_mrr:-NA}"
}

while true; do
  snap
  sleep "$interval"
done
