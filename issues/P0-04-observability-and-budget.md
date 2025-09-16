# P0: Observability and token budget controls

Labels: priority/P0, area/ops, area/observability

Summary:
- Add lightweight run summaries and token/budget controls to keep pipeline stable and costs predictable.

Current achievements:
- End-to-end scripts and metrics exist but lack consolidated run logs.

Tasks:
- After each run, append JSONL/CSV with counts (regions processed, artifacts produced), error rates, avg sim of top-1, and elapsed times.
- Track token usage during LLM analysis; add soft/hard budget thresholds and graceful stop with summary.
- Minimal Prometheus-friendly log line or export if feasible later (optional).

Acceptance criteria:
- A single file in `eval/` or `Logs/` grows per run with the summary; budgets enforced.

