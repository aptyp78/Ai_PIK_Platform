# P1: CLIP/OpenCLIP hybrid retrieval for images

Labels: priority/P1, area/retrieval, area/vision

Summary:
- Add image embeddings (page/region PNG) and blend with text similarity to improve image-heavy queries.

Current achievements:
- NDJSON index and cosine search exist; visual region previews are stored in meta.

Tasks:
- Implement `scripts/embed_images.py` to compute CLIP/OpenCLIP vectors and append to NDJSON (separate `vector_image` or separate records with `type=ImageVec`).
- Extend `scripts/retrieval_search.py` to blend scores (weighted sum) and flag `--with-images`.
- Update `scripts/eval_metrics.py` to evaluate blended ranking and compare deltas.

Acceptance criteria:
- Measurable recall@1/MRR uplift on queries tied to visual semantics.

