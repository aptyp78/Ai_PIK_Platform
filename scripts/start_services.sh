#!/usr/bin/env bash
set -euo pipefail

mkdir -p Logs eval /tmp/tess_tmp
export TMPDIR=/tmp/tess_tmp

# Load .env
# Safe source .env (only lines with key=value, skip comments)
if [ -f .env ]; then
  while IFS= read -r line; do
    case "$line" in 
      \#*|'') continue ;;
      *'='*) export "$line" || true ;;
    esac
  done < .env
fi

# Start pipeline in background if not running
if [ -f Logs/pipeline.pid ] && ps -p "$(cat Logs/pipeline.pid)" >/dev/null 2>&1; then
  echo "pipeline already running (pid=$(cat Logs/pipeline.pid))"
else
  echo "starting pipeline in background"
  nohup bash scripts/run_pipeline_bg.sh >> Logs/pipeline.log 2>&1 & echo $! > Logs/pipeline.pid
fi

# Start eval watcher (review + progress) if not running
if [ -f Logs/watch_eval.pid ] && ps -p "$(cat Logs/watch_eval.pid)" >/dev/null 2>&1; then
  echo "watcher already running (pid=$(cat Logs/watch_eval.pid))"
else
  echo "starting watch_eval in background"
  nohup bash scripts/watch_eval.sh >> Logs/watch_eval.log 2>&1 & echo $! > Logs/watch_eval.pid
fi

# Optional: start HTTP server on port 8000 serving eval/
if [ -f Logs/http_eval.pid ] && ps -p "$(cat Logs/http_eval.pid)" >/dev/null 2>&1; then
  echo "http server already running (pid=$(cat Logs/http_eval.pid))"
else
  echo "starting http server on :8000 (serving eval/)"
  nohup python3 -m http.server 8000 -d eval >> Logs/http_eval.log 2>&1 & echo $! > Logs/http_eval.pid
fi

echo "services started. review: http://$(hostname -I 2>/dev/null | awk '{print $1}'):8000/visual_review.html"
