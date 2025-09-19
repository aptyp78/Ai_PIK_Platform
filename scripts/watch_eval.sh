#!/usr/bin/env bash
set -euo pipefail

REGIONS_DIR=${1:-out/visual/grounded_regions}
INTERVAL=${INTERVAL:-10}

mkdir -p eval
echo "[watch] updating visual review and progress every ${INTERVAL}s (Ctrl-C to stop)"
while true; do
  python3 scripts/generate_visual_review.py --regions-detect "$REGIONS_DIR" --out eval/visual_review.html --inline --auto-refresh 5 || true
  python3 scripts/progress_dashboard.py --playbooks /root/data/playbooks --frames /root/data/frames --pages-dir out/page_images --regions-dir "$REGIONS_DIR" --index out/openai_embeddings.ndjson --out eval/progress.html --auto-refresh 5 || true
  sleep "$INTERVAL"
done

