# Contributing Guide

This project uses a lightweight, practical workflow focused on small, reviewable changes. If you’re unsure about anything, open a draft PR early.

## Branching & PRs
- Do not commit directly to `main`.
- Create a task branch off `main`:
  - `feature/<short-topic>` for new work
  - `fix/<short-topic>` for bugfixes
  - `docs/<short-topic>` for documentation
  - `chore/<short-topic>` for maintenance
- Keep changes small and focused; open a PR early and iterate.
- Rebase before push to keep history linear:
  - `git pull --rebase origin main`
  - `git push -u origin <branch>`
- Merge via PR after review; delete the branch after merge.

## Commit Messages
- Use clear, imperative messages (present tense):
  - Good: `feat: add bootstrap cell to load .env`
  - Good: `fix: escape JSON quotes in notebook cell`
  - Avoid: `fixes`, `fixed`, generic `update`
- Include scope when helpful: `notebooks: ...`, `scripts: ...`, `docs: ...`.

## Notebooks
- Avoid committing large outputs and transient artifacts.
- Prefer clearing outputs before commit:
  - Install once: `pip install nbstripout`
  - Enable in the repo: `nbstripout --install`
- If outputs are valuable for review (plots, tables), keep them but be mindful of size.
- Consider parameterizing notebooks via a first "bootstrap" cell that loads `.env` and creates output directories.

## Secrets & Local Files
- Do not commit secrets or private endpoints.
- Keep real values in `.env` (already gitignored). Commit only `.env.example`.
- Keep `docs/infra/remotes.yaml` local (already gitignored). Use `docs/infra/remotes.example.yaml` as a template.
- Large datasets and generated artifacts should live under `out/` (gitignored) or external storage.

## Code & Scripts
- Prefer small, composable scripts under `scripts/`.
- Python style: keep it readable and consistent; type hints appreciated.
- Handle errors and print concise diagnostics for CLI scripts.
- Add usage/help (`-h/--help`) where reasonable.

## Updating Machine Docs (optional)
- Snapshot current machine: `python3 scripts/system_probe.py`
- Regenerate docs (incl. Network): `python3 scripts/generate_machine_docs.py`

## Typical Workflow
1) `git switch -c feature/<topic>`
2) Make focused changes; run locally
3) `git add -p && git commit -m "..."`
4) `git pull --rebase origin main`
5) `git push -u origin feature/<topic>`
6) Open PR, iterate, merge, `git branch -d feature/<topic>`

