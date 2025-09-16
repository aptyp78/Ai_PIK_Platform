# P0: Stabilize GroundedDINO/SAM2 visual→facts→index loop

Labels: priority/P0, area/visual, area/pipeline

Summary:
- Make the visual extraction pipeline reliable end-to-end: SAM2 init via env-based model paths with fallback to SAM v1, mirrored weights in GCS, idempotent processing, and artifact manifests for traceability.

Current achievements:
- scripts/analyze_detected_regions.py supports `--skip-existing` (saves tokens/time).
- scripts/pull_grounded_ingest_eval.sh runs end-to-end (sync → analyze → ingest → review → metrics).
- docs/STATUS_GROUNDED_SAM_2025-09-16.md: successful fallback to SAM v1; artifacts ingested; metrics snapshot recorded.

Tasks:
- Add env-based model paths to detection/pipeline scripts: `$MODEL_DIR/{groundingdino,sam,sam2}` with clear validation.
- Implement graceful fallback: try SAM2 → fallback to SAM v1 if init fails; log reason.
- Mirror model weights to GCS (`gs://pik-artifacts-dev/models/...`) and update Colab to fetch from GCS.
- Add per-unit manifest JSON (hashes, timestamps, counts) alongside regions; verify in `pull_grounded_ingest_eval.sh`.
- Ensure idempotency: checksums + `--skip-existing` for all analyzer steps.
- Update `eval/visual_review.html` generation to include manifest link.

Acceptance criteria:
- One-command run completes without manual fixes; SAM2 used when available, otherwise v1 fallback.
- No duplicate re-processing on repeated runs (idempotent).
- Manifest JSON present for each processed unit; visual review regenerated.
- Metrics snapshot appended to eval logs after run.

