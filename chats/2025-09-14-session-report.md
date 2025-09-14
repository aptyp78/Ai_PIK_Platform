# Session Report — 2025-09-14

## Summary
We prepared and validated a retrieval stack for the “Platform IT Architecture” Playbook and key frames, rebuilt a clean embeddings index, generated 30 Russian queries with metrics and full Q/A, and documented the target multimodal RAG technology stack. Next, we proceed to semantic visual extraction for selected Playbook pages, then the 3 frames.

## Decisions
- Vision model: use OpenAI GPT‑4o for visual captioning and structural extraction (confirmed).
- Keep Sonar only for chat/completions (no embeddings).
- Postpone spaCy tagger until after visual extraction; add simple tag boosts if needed.
- No Qdrant ingestion yet; stay local until visual artifacts are integrated.

## Data & Mounts
- Remote: rclone `gcs-pik` (GCS) mounted via macFUSE.
- Buckets: `~/GCS/pik_source_bucket`, `~/GCS/pik_result_bucket`.
- Sources in result bucket:
  - Playbook JSON: `~/GCS/pik_result_bucket/Qdrant_Destination/playbooks/PIK - Expert Guide - Platform IT Architecture - Playbook - v11.pdf.json`
  - Frames (PDF JSON):
    - Canvas Table View: `.../frames/PIK - Platform IT Architecture Canvas - Table View - v01.pdf.json`
    - Canvases poster: `.../frames/PIK - Platform IT Architecture Canvases - v01.pdf.json`
    - Assessment/Scoring: `.../frames/PIK - Expert Guide - Platform IT Architecture - Assessment - v01.pdf.json`

## Index & Evaluation
- Chunking: ~1400 chars with ~180 overlap; filter PageBreak; include Image OCR only if ≥180 chars.
- Embeddings: OpenAI `text-embedding-3-large` (3072d).
- Current index: 32 chunks → `out/openai_embeddings.ndjson`.
- Queries: 30 RU questions in `eval/queries.jsonl` (+ `eval/queries.txt`).
- Metrics (autolabeled): recall@1=1.000, recall@3=1.000, recall@5=1.000; nDCG@3=0.992; MRR=1.000.
- Q/A: `eval/qa.md`, `eval/qa.jsonl` (RAG with top‑3, gpt‑4o‑mini generator for now).
- Review report: `eval/review.md`, `eval/review.csv` (flags: miss@1, low_sim, image_top1).

## Code & Docs
- Scripts: build index/search/eval/Q&A in `scripts/` (rebuild_index, rag_answer, build_qa, eval_metrics, report_queries, etc.).
- Tech stack (full design incl. visual): `docs/TECH_STACK.md`.
- Repo hygiene: `.gitignore` excludes secrets/env/out/venv.

## Visual Extraction Scope (Playbook)
Printed page numbers identified as key: 5, 6, 7, 8, 10, 11, 17, 18, 20, 21, 22, 23, 24, 26, 27, 29, 30, 33, 34, 41, 42, 43, 45, 46, 47, 49.

## Next Steps (high level)
1) Visual extraction on selected Playbook pages using GPT‑4o:
   - Produce per‑page: caption.txt, struct.json, facts.txt under `out/visual/pages/`.
2) Integrate VisualCaption/VisualFact into index; recalc metrics; update Q/A.
3) Repeat visual extraction for 3 frames (Canvas Table, Canvases, Assessment).
4) Optional: simple tag boosts; later spaCy tagging if needed.

---

Owner: aso • Workspace: AiPIK • Date: 2025‑09‑14

