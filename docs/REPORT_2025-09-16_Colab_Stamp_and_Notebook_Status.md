# Colab Notebook — CI Stamp, Links, and Current Status (2025-09-16)

This report summarizes the current state of the Colab notebook, CI stamping workflow, dependency compatibility, and usage links.

## Summary
- Introduced a stable Colab launch branch: `colab-latest`.
- Added CI workflow to stamp the notebook header and `NOTEBOOK_VERSION`, update README/docs links, and advance `colab-latest`.
- Inserted “Compatibility Fixes (pip pins)” cell and per‑cell execution logger with upload to GCS.
- Resolved merge conflicts by taking notebook from `colab-latest` and keeping `scripts/patch_notebook.py` from `main`.

## Links
- Colab (stable): https://colab.research.google.com/github/aptyp78/PIKAi/blob/colab-latest/notebooks/Grounded_DINO_SAM2_Detection.ipynb
- CI workflow: `.github/workflows/update-colab-latest.yml`
- CI status badge (README): shows the latest stamp on `main`.
- Visual review (signed, may expire): see `docs/STATUS_GROUNDED_SAM_2025-09-16.md` for the current link.

## Recent CI Run
- Job: “Stamp notebook and advance colab-latest”
- Trigger: push to `main`
- Result: Success
- Head SHA (main): see notebook header `NOTEBOOK_VERSION` for the stamped value.

## Notebook Controls & Safety
- Top cell: `START_RUN` toggle gates heavy steps via `require_start()`.
- Empty `PAGES` renders all pages (auto‑detect via `pdfinfo`).
- Logger: “Cell Execution Logger” writes per‑cell JSONL to `LOG_DIR/cells.jsonl`. Final cell uploads to GCS.

## Dependency Compatibility (Colab)
- Compatibility cell pins:
  - `typing_extensions>=4.14.0,<5`
  - `filelock>=3.15`
  - `numpy<2.1,>=1.24`
  - `gcsfs==2025.3.0`, `fsspec==2025.3.0`
- Torch stack (CUDA 12.4): `torch==2.5.1`, `torchvision==0.20.1`, `torchaudio==2.5.1`.
- `xformers` intentionally skipped (tight coupling to torch version).
- For gsutil speed: install `python3-crcmod` via apt in Auth cell.

## Usage (Quick)
1. Open Colab via the stable link above; set runtime to GPU.
2. In “Run Control and Parameters”, set `START_RUN=True`; leave `PAGES=[]` to process all pages if desired.
3. Run “Auth + gcsfuse setup”.
4. Run “Compatibility Fixes (pip pins)”, then Restart Runtime.
5. Run “Install Torch + SAM/SAM2 + GroundedDINO”.
6. Continue with render → detect → upload. Finally, upload `cells.jsonl` to GCS.

## Troubleshooting
- Pip resolver warnings: acceptable if pins remain in place after Restart.
- `gsutil rsync` slow: install `python3-crcmod`.
- Logger upload: ensure at least one cell executed after enabling the logger so `cells.jsonl` exists.
- CI JSON error: CI now validates for conflict markers/invalid JSON and fails early with a clear message.

## Next Steps
- Optionally add a `colab-stable` branch for tagged releases (README could display both “Latest” and “Stable” badges).
- Extend CI to run a lightweight smoke test (import + version checks) in a Colab‑like container for early detection of dependency drift.

