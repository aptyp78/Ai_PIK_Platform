# P1: Qdrant push/search integration

Labels: priority/P1, area/index, area/api

Summary:
- Move from NDJSON-only to Qdrant for production-grade retrieval with filters and metadata.

Current achievements:
- NDJSON index and metadata schema are stable; Qdrant chosen in TECH_STACK.

Tasks:
- Implement `scripts/qdrant_push.py` to create/update collection and upsert vectors + metadata (config via `$QDRANT_URL`, `$QDRANT_API_KEY`, `$QDRANT_COLLECTION`).
- Implement `scripts/qdrant_search.py` with parity of type/tag weights and basic filters.
- Document migration steps and parity checks.

Acceptance criteria:
- Collection populated; CLI search returns results matching NDJSON ranking within tolerance.

