# P2: Prefect orchestration for the pipeline

Labels: priority/P2, area/orchestration, area/ops

Summary:
- Parameterize and orchestrate the pipeline with Prefect: sync → analyze → ingest → evaluate; keep shell runner for local use.

Current achievements:
- End-to-end shell script exists (`scripts/pull_grounded_ingest_eval.sh`).

Tasks:
- Create Prefect flow with tasks for each stage; pass env/config; add logging hooks.
- Add Makefile/CLI entry to run with parameters; document setup.

Acceptance criteria:
- Flow runs locally; parameters configurable; logs visible in Prefect UI when enabled.

