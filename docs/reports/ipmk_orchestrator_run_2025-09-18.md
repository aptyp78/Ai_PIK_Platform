# IPMK Orchestrator v3 Run Report — 2025-09-18

## Overview
- Executed `notebooks/IPMK_Orchestrator_v3.ipynb` headlessly via `jupyter nbconvert --execute` after preparing environment variables (`MODEL_DIR`, `GROUNDING_MODEL`, `SAM_MODEL`, `OPENAI_API_KEY`).
- Full pipeline completed: GCS sync → PDF rendering (300 dpi) → GroundedDINO+SAM2 detection → LLM analysis → embeddings ingest → visual review generation → metrics.
- Resulting notebook saved in-place with latest outputs (duration ≈ 25 minutes).

## Environment Preparation
- System packages installed: `google-cloud-sdk` (provides `gcloud`/`gsutil`), `tesseract-ocr` (plus language packs).
- Python packages installed: `pytesseract`, `supervision`, `yapf`; ensured existing dependencies (`groundingdino`, `sam2`, `torch`, `open_clip`) import cleanly.
- Authenticated to GCP using service account key `Secrets/pik-ai-unstructured-3c2e9f8c1a8d.json`; confirmed bucket access via `gsutil ls`.

## Code Adjustments
- Updated `scripts/grounded_sam_detect.py` to support the newer `groundingdino` API:
  - Gracefully fall back to the detections object returned by new releases, converting confidences back to logits.
  - Read images through OpenCV when required and disable PIL’s decompression bomb guard for high-resolution pages.
  - Skip (rather than abort on) pages without detections, logging a warning instead.
- No other source files modified.

## Pipeline Stage Outcomes
- **Sync**: `gsutil rsync` fetched 3 playbook PDFs and 55 frame assets into `/root/data/playbooks` and `/root/data/frames`.
- **Render**: `scripts/batch_render.py` produced 62 page PNGs for the main playbook plus additional assets under `out/page_images/` (300 dpi).
- **Detection**: `scripts/batch_gdino_sam2.py` processed every page image; output stored in `out/visual/grounded_regions/<page>/regions` with caption/struct/fact placeholders ready.
- **Analysis**: `scripts/analyze_detected_regions.py` generated captions, structural JSON, PNG crops, and triple facts for each detected region (see `out/visual/grounded_regions/page-*/regions/`).
- **Ingest**: `scripts/ingest_visual_artifacts.py` appended 1,111 records to `out/openai_embeddings.ndjson` (IDs continue from any prior contents).
- **Review/Eval**: 
  - HTML review written to `eval/visual_review.html` (images inlined, referencing grounded regions).
  - `scripts/eval_metrics.py` executed on `eval/queries.jsonl`; metrics all zero (no positive hits located, MRR 0.010 across 78 queries).

## Key Artifacts
- `out/visual/grounded_regions/` — per-page detection trees with captions/structs/facts.
- `out/openai_embeddings.ndjson` — updated embedding index (1,111 new items written this run).
- `eval/visual_review.html` — consolidated visual review for the processed playbook.
- `notebooks/IPMK_Orchestrator_v3.ipynb` — refreshed notebook containing execution logs and outputs.

## Observations & Recommendations
- Evaluation metrics remain at zero; likely causes include outdated `eval/queries.jsonl` annotations or new IDs not yet referenced. Review ground-truth mappings before next assessment cycle.
- Large-page warning mitigation (PIL decompression check) is now disabled globally; consider adding size-based safeguards if hostile inputs are a concern.
- If re-running soon, flip `IPMK_DO_*` flags as needed to avoid redundant reruns (e.g., skip sync/detect for incremental LLM passes).
- Validate that downstream consumers of `out/openai_embeddings.ndjson` account for the increased record count and metadata (tags, previews).
