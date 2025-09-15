# GroundedDINO/SAM Visual Extraction — Status (2025-09-15)

This document summarizes the current status of the visual pipeline (CV + GroundedDINO/SAM), GCS configuration, notebook automation, issues encountered, and the immediate next steps.

## What’s Done
- CV segmentation and LLM analysis in repo (all Playbook pages + 3 frames) with facts and ingestion.
- GCS bucket `gs://pik-artifacts-dev` provisioned: UBLA, PAP enforced, logging to `gs://pik-artifacts-logs`, versioning on, minimal lifecycle, CORS uploaded.
- Artifacts uploaded:
  - `cv_regions/`, `cv_frames/`
  - `grounded_regions/` (pilot: page-42, page-45; then ready for 4–11 + 3 frames)
  - `embeddings/openai_embeddings.ndjson`
  - `visual_review/visual_review.html` (can be rebuilt inline)
- Visual review generator supports inline PNG embedding (`--inline`) to remove dependency on public file serving.
- Colab notebook `notebooks/Grounded_DINO_SAM2_Detection.ipynb`:
  - Reads SA key from Colab Keys (`userdata.get('GCS_SA_JSON')` or `secretName`); if absent, prompts for manual JSON upload and mounts via gcsfuse `--key-file`.
  - Installs Torch cu121 + Segment-Anything; clones GroundedDINO from source and injects into `sys.path` (reliable import).
  - Auto-downloads GroundedDINO config and weights with size checks and fallbacks; renders PDF→PNG; runs detection (DINO→SAM); rsync to `grounded_regions/`.

## Current Complexities / Issues
- GroundedDINO wheels sometimes fail to build in Colab. Fixed with source install + explicit sys.path.
- Model weights download may intermittently fail or produce 0-byte file (network rate limiting). Added robust fetch (curl with retries then wget; we can add GCS-hosted mirror if needed).
- Config file not found (GroundingDINO_SwinT_OGC.py): added dual strategy (download then fallback to package config).
- GPU vs CPU: when GPU not selected or Torch not CUDA-enabled, SAM prints “custom C++ ops missing; CPU mode”. Notebook now clearly expects GPU runtime; can be forced to CUDA in model init; user must pick GPU.
- Colab Keys vs Secrets folder: unified logic — prefer Keys first, otherwise prompt and mount with uploaded SA.
- Web PNG visibility: some environments block file URLs; visual review now supports inline base64.

## How to Run (Colab Pro+)
1) Set runtime: Python 3 + GPU (L4/T4/A100), latest runtime. Restart runtime.
2) Add SA key to Colab Keys (Tools → Secrets): name `GCS_SA_JSON` (or `secretName`).
3) Open and Run All: `notebooks/Grounded_DINO_SAM2_Detection.ipynb`.
   - If key not found in Keys, notebook prompts to upload JSON and mounts gcsfuse with it.
   - Notebook downloads weights/configs, renders Playbook pages, runs GroundedDINO→SAM on pages 4–11 and 3 frames, and uploads regions to GCS.

## After Detection (automated locally)
- Sync grounded regions and run LLM analysis and ingestion:
  - `gsutil -m rsync -r gs://pik-artifacts-dev/grounded_regions out/visual/grounded_regions`
  - `./.venv/bin/python scripts/analyze_detected_regions.py --detected-dir out/visual/grounded_regions --all --outdir out/visual/grounded_regions --chat-model gpt-4o`
  - `./.venv/bin/python scripts/fill_region_facts.py --roots out/visual/grounded_regions`
  - `./.venv/bin/python scripts/ingest_visual_artifacts.py --source-json \
     "$HOME/GCS/pik_result_bucket/Qdrant_Destination/playbooks/PIK - Expert Guide - Platform IT Architecture - Playbook - v11.pdf.json" \
     --regions-dir out/visual/grounded_regions --out out/openai_embeddings.ndjson`
  - Recompute metrics/Q&A; rebuild visual review inline: `./.venv/bin/python scripts/generate_visual_review.py --inline`

## Metrics Snapshot (latest local)
- Baseline (text + CV + small grounded pilot): recall@1≈0.80, recall@3≈0.83, recall@5≈0.87; MRR≈0.83 (30 queries). Expect improvement as grounded coverage expands.

## Next Steps
- Run GroundedDINO→SAM on pages 4–11 + 3 frames in Colab; confirm regions in GCS.
- Pull and analyze → facts → ingest → metrics; publish updated inline visual review to GCS.
- If downloads remain flaky, add GCS mirrors for GroundedDINO weights and config.
- Optional: switch SAM to ViT‑L for lighter memory footprint, enable xformers for speed.

