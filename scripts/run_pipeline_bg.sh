#!/usr/bin/env bash
set -euo pipefail

# Full pipeline runner in background with logging
# Usage: nohup bash scripts/run_pipeline_bg.sh >> Logs/pipeline.log 2>&1 & echo $! > Logs/pipeline.pid

mkdir -p Logs /tmp/tess_tmp
export TMPDIR=/tmp/tess_tmp

# Load .env if present
# Safe source .env
if [ -f .env ]; then
  while IFS= read -r line; do
    case "$line" in 
      \#*|'') continue ;;
      *'='*) export "$line" || true ;;
    esac
  done < .env
fi

# Pick up OpenAI key from Secrets if not set
if [ -z "${OPENAI_API_KEY:-}" ] && [ -f "Secrets/OpenAi API.key" ]; then
  export OPENAI_API_KEY="$(cat 'Secrets/OpenAi API.key')"
fi

CHAT_MODEL=${CHAT_MODEL:-gpt-5-mini}
EMB_MODEL=${EMB_MODEL:-text-embedding-3-large}
INDEX_PATH=${INDEX_PATH:-out/openai_embeddings.ndjson}
JSON_PATH=${JSON_PATH:-/root/data/playbook.json}

echo "[pipeline] start at $(date -u +%FT%TZ)"

echo "[1/6] prepare inputs (300 dpi)"
python3 scripts/prepare_inputs.py --playbooks /root/data/playbooks --frames /root/data/frames --out-root out/page_images --dpi 300 || true

echo "[2/6] detection (GroundedDINO+SAM)"
python3 scripts/batch_gdino_sam2.py \
  --pages-root out/page_images \
  --outdir out/visual/grounded_regions \
  --prompts diagram canvas table legend node arrow textbox \
  --grounding-model /root/models/groundingdino/groundingdino_swint_ogc.pth \
  --sam-model /root/models/sam/sam_vit_h_4b8939.pth || true

echo "[3/6] analysis (LLM)"
python3 scripts/analyze_detected_regions.py \
  --detected-dir out/visual/grounded_regions \
  --all \
  --outdir out/visual/grounded_regions \
  --profile auto \
  --synonyms config/semantic_synonyms.yaml \
  --weights config/visual_objects_weights.yaml \
  --tmpdir /tmp/tess_tmp \
  --chat-model "$CHAT_MODEL" \
  --skip-existing || true

echo "[4/6] ingest embeddings"
python3 scripts/ingest_visual_artifacts.py \
  --source-json "$JSON_PATH" \
  --regions-dir out/visual/grounded_regions \
  --out "$INDEX_PATH" \
  --model "$EMB_MODEL" || true

echo "[5/6] review + progress"
python3 scripts/generate_visual_review.py --regions-detect out/visual/grounded_regions --out eval/visual_review.html --inline --auto-refresh 5 || true
python3 scripts/progress_dashboard.py --playbooks /root/data/playbooks --frames /root/data/frames --pages-dir out/page_images --regions-dir out/visual/grounded_regions --index "$INDEX_PATH" --out eval/progress.html --auto-refresh 5 || true

echo "[6/6] metrics (optional)"
python3 scripts/eval_metrics.py --index "$INDEX_PATH" --eval eval/queries.jsonl --prefer-visual || true

echo "[pipeline] done at $(date -u +%FT%TZ)"
