# P0: Index all Unstructured JSON across PIK sources (full methodology)

Labels: priority/P0, area/index, area/retrieval

Summary:
- Build a clean text embeddings index from ALL available Unstructured JSON, not just IT Playbook, to cover the full PIK methodology (PIK 5‑0, canvases, frameworks).

Current achievements:
- `rebuild_index.py` for explicit file lists; partial coverage via Qdrant_Destination `playbooks/` and `frames/`.

Tasks:
- Add `scripts/rebuild_index_all.py` to recursively scan `pik_source_bucket/{playbooks,frames,vlm_unstructured,raw_json}` and `pik_result_bucket/Qdrant_Destination/{playbooks,frames}`.
- Rebuild index and refresh `suggested_topk`; re‑label positives for management‑level questions.
- Document the one‑liner in README/docs.

Acceptance criteria:
- Index contains content across methodology beyond IT; improved coverage on management questions; clean NDJSON built reproducibly.
