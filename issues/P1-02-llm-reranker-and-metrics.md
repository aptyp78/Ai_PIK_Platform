# P1: LLM reranker and A/B metrics

Labels: priority/P1, area/retrieval, area/eval

Summary:
- Add optional reranking of top-30 candidates with a compact LLM scoring prompt (faithfulness + topicality) and integrate into metrics for A/B testing.

Current achievements:
- RAG answer flow exists (scripts/rag_answer.py) using OpenAI chat; can reuse client and style.

Tasks:
- Implement `rerank.py` module to score top-30 and return new order.
- Add `--rerank` to `scripts/retrieval_search.py` and `scripts/eval_metrics.py` with model/temperature flags.
- Evaluate latency/cost trade-offs and default it off.

Acceptance criteria:
- Rerank integrates cleanly; optional; shows ≥5% uplift on recall@1/MRR for targeted queries.

