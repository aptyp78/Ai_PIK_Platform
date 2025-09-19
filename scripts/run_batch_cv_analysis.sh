#!/usr/bin/env bash
set -euo pipefail

# Batch analyzer/ingester for CV regions over playbooks and frames.
# Defaults to OpenAI chat model gpt-5-mini and emits progress after each chunk.
#
# Usage:
#   export OPENAI_API_KEY="$(cat Secrets/OpenAi\ API.key)"
#   export GOOGLE_APPLICATION_CREDENTIALS="$PWD/Secrets/pik-ai-unstructured-2e64c607c270-colab-grounded.json" # optional, for publish
#   bash scripts/run_batch_cv_analysis.sh [CHAT_MODEL] [CHUNK_SIZE]
#

CHAT_MODEL=${1:-gpt-5-mini}
CHUNK=${2:-8}

# Pick up keys from Secrets/* if env not set
if [[ -z "${OPENAI_API_KEY:-}" && -f "Secrets/OpenAi API.key" ]]; then
  export OPENAI_API_KEY="$(cat 'Secrets/OpenAi API.key')"
fi

# Avoid Mac sandbox /tmp issues
export TMPDIR="${TMPDIR:-$PWD/tmp}"
mkdir -p "$TMPDIR"

echo "[deprecated] CV pipeline has been removed. Use grounded_sam_pipeline.py or scripts/generate_visual_review.py with --regions-detect=out/visual/grounded_regions."
exit 1

analyze_dir_pages() {
  local base="$1"
  local label="$2"
  if [[ ! -d "$base" ]]; then
    echo "[skip] $label: directory not found: $base"
    return 0
  fi
  # Portable list of numeric page dirs (avoid mapfile for macOS bash 3.2)
  local PAGES_STR
  PAGES_STR=$(ls -1 "$base" | awk '/^[0-9]+$/ {print $0}' | sort -n | tr '\n' ' ')
  # shellcheck disable=SC2206
  local PAGES=( $PAGES_STR )
  local N=${#PAGES[@]}
  if (( N == 0 )); then
    echo "[warn] $label: no numeric subdirs, nothing to analyze"
    return 0
  fi
  local i=0
  while (( i < N )); do
    local from=$i
    local to=$(( i + CHUNK - 1 ))
    if (( to >= N )); then to=$(( N - 1 )); fi
    local slice=("${PAGES[@]:from:to-from+1}")
    echo "[analyze:$label] pages: ${slice[*]}"
    python3 scripts/analyze_detected_regions.py \
      --detected-dir "$base" \
      --pages ${slice[*]} \
      --outdir "$base" \
      --chat-model "$CHAT_MODEL" \
      --skip-existing || true
    # brief pacing to smooth bursts
    sleep 1
    i=$(( to + 1 ))
  done
}

ingest_frames() {
  local index="out/openai_embeddings.ndjson"
  local count=0
  for d in out/visual/cv_frames/*; do
    [[ -d "$d/regions" ]] || continue
    local name
    name="$(basename "$d")"
    local sj=""
    if [[ -f "data/results/frames/$name.png.json" ]]; then
      sj="data/results/frames/$name.png.json"
    elif [[ -f "data/results/frames/$name.pdf.json" ]]; then
      sj="data/results/frames/$name.pdf.json"
    else
      echo "[warn] frames ingest: source json not found for $name" >&2
      continue
    fi
    echo "[ingest:frame] $name"
    python3 scripts/ingest_visual_artifacts.py \
      --source-json "$sj" \
      --regions-dir "$d" \
      --out "$index" \
      --model text-embedding-3-large \
      --batch 64 >/dev/null || true
    count=$((count+1))
  done
  echo "[ingest:frames] appended from $count frame sets"
}

ingest_playbook_dir() {
  local name="$1"; shift
  local rd="out/visual/cv_regions/$name"
  local sj="data/results/playbooks/$name.pdf.json"
  local index="out/openai_embeddings.ndjson"
  if [[ -d "$rd" && -f "$sj" ]]; then
    echo "[ingest:playbook] $name"
    python3 scripts/ingest_visual_artifacts.py \
      --source-json "$sj" \
      --regions-dir "$rd" \
      --out "$index" \
      --model text-embedding-3-large \
      --batch 64 || true
  else
    echo "[skip] ingest $name: regions or source json missing"
  fi
}

# 1) Analyze frames (already CV-segmented)
for f in out/visual/cv_frames/*; do
  [[ -d "$f/regions" ]] || continue
  # frames are per-file regions without numeric unit subdirs; analysis already done earlier, so we skip here to save tokens
  :
done

# 2) Analyze playbooks (two dirs)
analyze_dir_pages "out/visual/cv_regions/2023-06 - fastbreakOne - Expert Guide - Ecosystem Strategy  - English" "fastbreakOne"
analyze_dir_pages "out/visual/cv_regions/PIK 5-0 - Introduction - English" "PIK 5-0"

# 3) Rebuild text index FIRST, then ingest visuals (append)
python3 scripts/rebuild_index_all.py --roots data/results/playbooks data/results/frames --out out/openai_embeddings.ndjson --model text-embedding-3-large --max-chars 1400 --overlap 180
ingest_frames
ingest_playbook_dir "2023-06 - fastbreakOne - Expert Guide - Ecosystem Strategy  - English"
ingest_playbook_dir "PIK 5-0 - Introduction - English"

# 4) Recompute metrics/overview
python3 scripts/generate_visual_review.py --inline || true
python3 scripts/eval_metrics.py --index out/openai_embeddings.ndjson --eval eval/queries.jsonl --prefer-visual --model text-embedding-3-large

# 5) Optional publish to GCS
if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
  gsutil -m cp out/openai_embeddings.ndjson gs://pik-artifacts-dev/embeddings/openai_embeddings.ndjson || true
  echo "[publish] gs://pik-artifacts-dev/embeddings/openai_embeddings.ndjson"
fi

echo "[done] batch CV analysis + ingest complete"
