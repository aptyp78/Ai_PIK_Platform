# Colab Notebook Automation — Latest/Stable Links, CI Stamping, and Hardening (2025‑09‑16)

This report captures the work to make the Colab notebook easy to launch, versioned, and reliable, with clear CI flows and conflict safety.

## Outcomes
- Stable Colab launch links in README:
  - Latest: `blob/colab-latest`
  - Stable: `blob/colab-stable`
- CI “stamp” workflow updates the notebook header and `NOTEBOOK_VERSION`, refreshes links, and advances `colab-latest`.
- Manual “promote to stable” workflow moves `colab-stable` to any ref (defaults to `main`).
- Notebook quality gates: start toggle, compatibility pins, per‑cell logger, and JSON/merge‑conflict validation in CI.

## Branching Model
- `main`: development/default branch.
- `colab-latest`: always points to current `main` after successful stamp. Readme’s “Latest” badge opens this ref in Colab.
- `colab-stable`: manually promoted when a revision is considered release‑ready. Readme’s “Stable” link opens this ref.

## CI Workflows
- `update-colab-latest.yml` (push + manual)
  - Steps:
    - Validate `notebooks/Grounded_DINO_SAM2_Detection.ipynb` (no conflict markers; valid JSON)
    - Stamp header and `NOTEBOOK_VERSION` via `scripts/patch_notebook.py`
    - Rebase on `origin/main`, commit stamped changes (if any), push to `main`
    - Advance `colab-latest` to `HEAD`
  - Hardening: full history checkout (`fetch-depth: 0`), safe.directory set, concurrency guard.
- `promote-colab-stable.yml` (manual)
  - Input `ref` (default `main`); moves `colab-stable` to the target SHA.

## Notebook Hardening
- Run control:
  - Top cell adds `START_RUN` and `require_start()`; heavy cells guarded.
- Compatibility fixes cell:
  - Pins: `typing_extensions>=4.14,<5`, `filelock>=3.15`, `numpy<2.1,>=1.24`, `gcsfs==2025.3.0`, `fsspec==2025.3.0`.
  - Optional removal of `xformers` (coupled to Torch version).
  - Version reporting via `importlib.metadata`.
- Install cell:
  - Torch cu124 stack pinned to 2.5.1/0.20.1/2.5.1.
  - Avoid IPython upgrades (Colab expects 7.34.0); ensure `jedi`.
  - Final compatibility pins after third‑party requirements.
- Logging:
  - Per‑cell JSONL logger writes to `LOG_DIR/cells.jsonl`; final cell uploads to GCS.
- GCS throughput:
  - Suggest `python3-crcmod` install to speed up `gsutil rsync`.

## Conflict/JSON Safety
- `scripts/patch_notebook.py` refuses to run if conflict markers (<<<<<<<, =======, >>>>>>>) are present or JSON is invalid; prints actionable hints and exits with code 2.
- CI validates the notebook before stamping and fails early with a clear message.

## Usage
- Launch (Latest): https://colab.research.google.com/github/aptyp78/PIKAi/blob/colab-latest/notebooks/Grounded_DINO_SAM2_Detection.ipynb
- Launch (Stable): https://colab.research.google.com/github/aptyp78/PIKAi/blob/colab-stable/notebooks/Grounded_DINO_SAM2_Detection.ipynb
- Promote to stable: Actions → “Promote notebook to colab-stable” → Run (ref: `main` or tag).
- Typical run order in Colab:
  1) Run Control: set `START_RUN=True`.
  2) Auth + gcsfuse.
  3) Compatibility Fixes → Restart runtime.
  4) Install Torch + SAM/SAM2 + GroundedDINO.
  5) Render → Detect → Upload Regions; optionally upload `cells.jsonl` to GCS.

## Troubleshooting
- Pip resolver warnings: acceptable; ensure pins remain post‑restart.
- Slow `gsutil rsync`: install `python3-crcmod`.
- Logger upload: ensure at least one cell executed after enabling the logger so `cells.jsonl` exists.
- CI stamp fails:
  - If message mentions conflict markers or invalid JSON: resolve merge conflicts in the notebook (use the version from `colab-latest`), then re‑run.
  - If push fails (non‑fast‑forward): rerun; CI rebases on `origin/main` before committing.

## Next Steps
- Optional: add tags for stable notebook releases (e.g., `notebook-YYYYMMDD`) and link them in release notes.
- Optional: add a smoke test job (import + versions) to catch dependency drift automatically.

