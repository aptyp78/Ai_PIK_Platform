# P0: Notebook — disable control gate and fix Torch/SAM/SAM2/GroundedDINO install

Labels: priority/P0, area/visual, area/pipeline

Summary:
- Remove gating (“Control and Parameters”) to run full volume; fix dependency pins and multi-mirror model fetch to make the Colab notebook robust.

Current achievements:
- `scripts/patch_notebook.py` injects control cell and normalizes some installs; strict JSON response enabled in region analysis.

Tasks:
- Change control cell: `START_RUN=True` and `require_start()` no-op; or remove gate calls from heavy cells.
- Normalize install cell: Torch 2.5.1 + cu124, optional xformers, numpy<2.1, typing_extensions>=4.14, filelock>=3.15; HF Hub + GCS + curl mirrors for SAM2.
- CI sanity: add a lint/parse check that the `.ipynb` remains valid JSON (no conflict markers).

Acceptance criteria:
- Notebook runs end-to-end without manual toggles; model weights properly fetched with fallback; no import errors on Torch/SAM2/GroundedDINO.
