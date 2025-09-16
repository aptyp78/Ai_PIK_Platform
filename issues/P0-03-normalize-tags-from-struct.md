# P0: Normalize tags from struct.json into meta.tags

Labels: priority/P0, area/normalization, area/retrieval

Summary:
- Convert `*.struct.json` content (Canvas/Assessment/Diagram, Pillar, Layer, etc.) into controlled `meta.tags` during ingestion to enable robust tag boosts and filters.

Current achievements:
- Ingestor writes `meta.tags` but currently leaves it empty; TECH_STACK defines normalization rules and target tags.

Tasks:
- Implement tag extraction in `scripts/ingest_visual_artifacts.py` reading alongside facts/struct.
- Define mapping and normalization (case-insensitive, canonical forms), e.g., `pillar=Security` → `Pillar` tag.
- Update `scripts/retrieval_search.py` and `scripts/eval_metrics.py` to use tags for boosts consistently.
- Document tag glossary in `docs/TECH_STACK.md` or a new `docs/TAGS.md`.

Acceptance criteria:
- `meta.tags` populated for VisualCaption/VisualFact items; visible impact on boosted categories.
- Tag boosts reproducibly improve relevant queries (esp. Pillar/Layer questions).

