# GroundedDINO/SAM Visual Extraction — Status (2025-09-16)

This update reflects the results from the Colab notebook run and subsequent local processing (sync → analyze → ingest → evaluate).

## What’s New
- Pulled grounded regions from GCS for pages 4–11 and three frames:
  - `PIK - Expert Guide - Platform IT Architecture - Assessment - v01/regions/region-1.*`
  - `PIK - Platform IT Architecture Canvases - v01/regions/region-{1,2}.*`
  - `PIK - Platform IT Architecture Canvas - Table View - v01/regions/region-{1,2}.*`
  - `page-{4..11}/regions/region-1.*`
- Ran LLM analysis for each detected region to produce:
  - `region-*.caption.txt`, `region-*.struct.json`, `region-*.facts.jsonl`
- Ingested all visual artifacts into the embeddings index and regenerated the inline visual review.
- Added a small improvement and utility:
  - `scripts/analyze_detected_regions.py`: new `--skip-existing` flag to avoid re-processing regions that already have `struct.json` (saves tokens/time).
  - `scripts/pull_grounded_ingest_eval.sh`: end-to-end helper (sync → analyze → facts → ingest → review → metrics).

## Notebook Results Snapshot
- Colab environment had CUDA available (`Torch 2.5.1+cu124`).
- SAM2 init failed, gracefully fell back to SAM v1 (ViT‑H). Artifacts were uploaded to `gs://pik-artifacts-dev/grounded_regions` and synced locally.

## Local Artifacts
- Grounded regions: `out/visual/grounded_regions/<unit>/regions/region-*.{png,json,caption.txt,struct.json,facts.jsonl}`
- Visual review (inline PNGs): `eval/visual_review.html`
- Embeddings index: `out/openai_embeddings.ndjson` (appended with new visual captions/facts)

## Link
- Signed URL (7d): https://storage.googleapis.com/pik-artifacts-dev/visual_review/visual_review-20250916-070434.html?x-goog-signature=64db5b96831a56dbccf72a8ed8b53a3a647269d09f049b1e6103014965ec96480f4208053de60b4bbe5f7e4a2a517b8bd841384e3d1a8d923951bf6c94e5ce42f79510318073c1d6473f808868e4366e954a7ec8821e921caa7897308bc919cc38fa21e5909bf931d7436f5c07085fb0d3bc3b0ad59bab5b2f4db31a783ec59ef39e3b0e921d85937c117a19b003d7780de24d99b4e7933517dc24dfb512696ff348f4dde3786101dab7cca829db23cff82ac08d92cb10c4b7d2e443272c8cef192381a1f4c3b078e4b6c3d8741d77e8bebd2c1e49b848216d642f9b8d21e637a7f7a443c9035b935e06c7b330cee9d0c1130da692a94eb54f0a2ff96f1fcc90&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=service%40pik-ai-unstructured.iam.gserviceaccount.com%2F20250916%2Feurope-west3%2Fstorage%2Fgoog4_request&x-goog-date=20250916T050509Z&x-goog-expires=604800&x-goog-signedheaders=host

## Metrics (eval/queries.jsonl)
- Prefer-visual weights enabled.
- Current run:
  - recall@1: 0.667
  - recall@3: 0.700
  - recall@5: 0.767
  - MRR: 0.720 (30 annotated queries)
- Note: metrics will shift with index composition as we add visual items; consider tuning type/tag weights in `scripts/eval_metrics.py` or refining `positive_ids`.

## How to Reproduce
```
# End-to-end refresh (uses $OPENAI_API_KEY):
./scripts/pull_grounded_ingest_eval.sh \
  GCS_BUCKET=pik-artifacts-dev \
  SOURCE_JSON="$HOME/GCS/pik_result_bucket/Qdrant_Destination/playbooks/PIK - Expert Guide - Platform IT Architecture - Playbook - v11.pdf.json"
```

## Next Steps
- Optionally re-run the Colab notebook with SAM2 once config issue is resolved, then resync and analyze new regions.
- Calibrate `type`/`tag` weights for retrieval (e.g., upweight `Canvas`, `Assessment` facts slightly).
- Expand `eval/queries.jsonl` and update `positive_ids` to reflect new visual facts.
- If model download flakiness persists, mirror GroundedDINO/SAM weights in GCS and point the notebook to those.
