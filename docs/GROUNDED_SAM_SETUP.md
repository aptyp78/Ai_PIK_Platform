# GroundedDINO + SAM/SAM‑2 Setup and Pipeline

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/aptyp78/PIKAi/blob/574ca3c/notebooks/Grounded_DINO_SAM2_Detection.ipynb)

This doc outlines how to set up GroundedDINO and Segment Anything (SAM/SAM‑2) locally and run the grounded region extraction pipeline.

## 1) Environment

- Python 3.9+ recommended (we use `.venv` here).
- GPU with CUDA is recommended for performance, but CPU works for small tests.
- Install core deps (PyPI):

```
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121  # choose CUDA/CPU build as needed
pip install groundingdino segment-anything
# For SAM‑2 (optional, latest):
pip install git+https://github.com/facebookresearch/segment-anything-2.git
```

If you encounter build issues, consult each project's README for exact versions.

## 2) Weights

Download weights into `~/models` (or a path you prefer):

- GroundingDINO: e.g. `groundingdino_swint_ogc.pth`
- SAM (ViT‑H/ViT‑L/ViT‑B): e.g. `sam_vit_h_4b8939.pth`
- SAM‑2 (optional): e.g. `sam2_hiera_large.pt`

Put them under: `~/models/{groundingdino, sam, sam2}/...`

## 3) Run the pipeline

We provide a detection script that uses GroundedDINO+SAM to generate regions and then the existing LLM analyzer to extract caption/struct/facts.

1. Render Playbook PDF pages if not yet rendered:

```
.venv/bin/python scripts/render_pages.py \
  --pdf \
  "$HOME/GCS/pik_source_bucket/playbooks/PIK - Expert Guide - Platform IT Architecture - Playbook - v11.pdf" \
  --pages 42 43 45 \
  --outdir "out/page_images/PIK - Expert Guide - Platform IT Architecture - Playbook - v11"
```

2. Detect regions using GroundedDINO + SAM (example prompts):

```
.venv/bin/python scripts/grounded_sam_detect.py \
  --images \
  "out/page_images/PIK - Expert Guide - Platform IT Architecture - Playbook - v11/page-42.png" \
  "out/page_images/PIK - Expert Guide - Platform IT Architecture - Playbook - v11/page-45.png" \
  --outdir out/visual/grounded_regions \
  --grounding-model "$HOME/models/groundingdino/groundingdino_swint_ogc.pth" \
  --sam-model "$HOME/models/sam/sam_vit_h_4b8939.pth" \
  --prompts diagram canvas table legend node arrow text box
```

This produces `out/visual/grounded_regions/<image_stem>/regions/region-*.json` (bbox + base64 crops).

3. Analyze each region with our LLM extractor to produce artifacts:

```
.venv/bin/python scripts/analyze_detected_regions.py \
  --detected-dir out/visual/grounded_regions \
  --all \
  --outdir out/visual/grounded_regions \
  --chat-model gpt-4o
```

4. Ingest facts into the embeddings index:

```
.venv/bin/python scripts/ingest_visual_artifacts.py \
  --source-json "$HOME/GCS/pik_result_bucket/Qdrant_Destination/playbooks/PIK - Expert Guide - Platform IT Architecture - Playbook - v11.pdf.json" \
  --regions-dir out/visual/grounded_regions \
  --out out/openai_embeddings.ndjson
```

5. Recompute metrics and regenerate Q/A as needed.

## Notes

- If packages aren’t installed, the detection script will explain what’s missing and exit gracefully.
- You can mix detectors: CV (`scripts/cv_segment.py`) or GroundedDINO+SAM. Prefer grounded results when available.
- The ingestion expects `region-*.facts.jsonl`; if empty, run `scripts/fill_region_facts.py` to create fallback facts from captions.
