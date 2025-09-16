# P1: Minimal FastAPI service — /search and /answer

Labels: priority/P1, area/api, area/rag

Summary:
- Provide a lightweight service to consume the index: search and answer with citations. Qdrant as primary backend, NDJSON as fallback.

Current achievements:
- CLI `retrieval_search.py` and `rag_answer.py` cover the core logic.

Tasks:
- Create `api/app.py` with `/search` and `/answer` endpoints; wire to Qdrant or NDJSON fallback.
- Add request parameters: `k`, `prefer_visual`, `type_weights`, tag boosts.
- Return structured JSON with sources (file/page/id/region) and scores.

Acceptance criteria:
- Uvicorn-run service returns correct results locally; simple auth optional.

