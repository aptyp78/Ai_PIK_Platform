# P2: Graph layer build and exports

Labels: priority/P2, area/graph, area/retrieval

Summary:
- Build a knowledge graph from `*.struct.json` and expose exports + optional graph-aware retrieval filters.

Current achievements:
- Graph plan defined in TECH_STACK; struct JSON already produced for regions.

Tasks:
- Implement `scripts/build_graph.py` (NetworkX) and export GEXF + `graph/summary.md`.
- Add `scripts/graph_filter_search.py` to restrict retrieval by graph-derived filters (e.g., components under a pillar/layer).

Acceptance criteria:
- Graph built and browsable; optional pre-filter improves precision on pillar/layer queries.

