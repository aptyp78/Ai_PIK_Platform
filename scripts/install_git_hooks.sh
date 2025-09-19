#!/usr/bin/env bash
set -euo pipefail

# Install repo-provided git hooks into .git/hooks (symlinks).
repo_root=$(cd "$(dirname "$0")/.." && pwd)
hooks_src="$repo_root/scripts/git-hooks"
hooks_dst="$repo_root/.git/hooks"

if [ ! -d "$hooks_dst" ]; then
  echo ".git/hooks not found. Are you in a git repository?" >&2
  exit 1
fi

for hook in post-commit; do
  src="$hooks_src/$hook"
  dst="$hooks_dst/$hook"
  if [ -f "$src" ]; then
    ln -sf "$src" "$dst"
    chmod +x "$src" || true
    echo "Installed hook: $hook"
  fi
done

echo "Done."

