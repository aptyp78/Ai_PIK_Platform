#!/usr/bin/env bash
set -euo pipefail

# Sync grounded regions from GCS, analyze with LLM, fill facts, ingest into embeddings,
# regenerate visual review, and print retrieval metrics.

GCS_BUCKET="${GCS_BUCKET:-pik-artifacts-dev}"
REGIONS_DIR="${REGIONS_DIR:-out/visual/grounded_regions}"
SOURCE_JSON="${SOURCE_JSON:-$HOME/GCS/pik_result_bucket/Qdrant_Destination/playbooks/PIK - Expert Guide - Platform IT Architecture - Playbook - v11.pdf.json}"
CHAT_MODEL="${CHAT_MODEL:-gpt-4o}"
EMBED_MODEL="${EMBED_MODEL:-text-embedding-3-large}"
INDEX_OUT="${INDEX_OUT:-out/openai_embeddings.ndjson}"

echo "[1/6] Syncing grounded regions from gs://${GCS_BUCKET}/grounded_regions -> ${REGIONS_DIR}"
gsutil -m rsync -r "gs://${GCS_BUCKET}/grounded_regions" "${REGIONS_DIR}"

echo "[2/6] Analyzing regions with ${CHAT_MODEL} (skip existing)"
"${VENV_PY:-.venv/bin/python}" scripts/analyze_detected_regions.py \
  --detected-dir "${REGIONS_DIR}" --all --outdir "${REGIONS_DIR}" \
  --chat-model "${CHAT_MODEL}" --skip-existing

echo "[2.1/6] Writing manifests for processed units"
"${VENV_PY:-.venv/bin/python}" scripts/write_region_manifest.py --regions-dir "${REGIONS_DIR}"

echo "[3/6] Ensuring facts exist for all regions (fallbacks if needed)"
"${VENV_PY:-.venv/bin/python}" scripts/fill_region_facts.py --roots "${REGIONS_DIR}"

echo "[4/6] Ingesting visual artifacts into ${INDEX_OUT} using ${EMBED_MODEL}"
"${VENV_PY:-.venv/bin/python}" scripts/ingest_visual_artifacts.py \
  --source-json "${SOURCE_JSON}" \
  --regions-dir "${REGIONS_DIR}" \
  --out "${INDEX_OUT}" \
  --model "${EMBED_MODEL}"

echo "[5/6] Regenerating inline visual review"
"${VENV_PY:-.venv/bin/python}" scripts/generate_visual_review.py --inline

echo "[6/6] Computing retrieval metrics (prefer visual)"
"${VENV_PY:-.venv/bin/python}" scripts/eval_metrics.py \
  --index "${INDEX_OUT}" --eval eval/queries.jsonl --prefer-visual

echo "Done. Visual review: eval/visual_review.html"

# Append a lightweight summary line for observability
mkdir -p Logs
printf '%s\n' "{\"timestamp\":\"$(date -u +%FT%TZ)\",\"regions_dir\":\"${REGIONS_DIR}\",\"index\":\"${INDEX_OUT}\",\"chat_model\":\"${CHAT_MODEL}\",\"embed_model\":\"${EMBED_MODEL}\"}" >> Logs/visual_runs.jsonl
