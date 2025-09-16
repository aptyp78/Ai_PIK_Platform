# P0: Expand eval set and tune type/tag weights

Labels: priority/P0, area/eval, area/retrieval

Summary:
- Grow the annotated query set and calibrate retrieval weights to raise recall@1/MRR on a representative workload.

Current achievements:
- eval/queries.jsonl exists, along with eval_metrics.py and retrieval_search.py supporting type/tag weights and prefer-visual.
- Recent metrics (docs/STATUS_GROUNDED_SAM_2025-09-16.md) show solid baseline.

Tasks:
- Add 30–40 new queries to `eval/queries.jsonl` with accurate `positive_ids`.
- Define default tag weights via `TAG_WEIGHTS` env (e.g., Canvas, Assessment, Diagram, Pillar, Layer) and commit recommended values.
- Run `scripts/eval_metrics.py` regularly and write a snapshot line to `eval/review.md` or CSV.
- Iterate `type`/`tag` weights to improve recall@1 without harming overall nDCG.

Acceptance criteria:
- 60+ total queries with positives; reproducible metrics snapshots stored.
- +10–15% relative recall@1 improvement over baseline.

