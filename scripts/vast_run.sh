#!/usr/bin/env bash
set -euo pipefail

# Run a command on the remote vast-4090 host inside the repo, with Conda + .env loaded.
# Usage:
#   scripts/vast_run.sh "python scripts/render_pages.py --pdf \"$PDF_PATH\" --pages 42 45 --outdir \"$OUT_PAGES\" --dpi 150"
#
# Notes:
# - Quotes are required around the remote command if it includes spaces or shell expansion.
# - The script expects an SSH alias `vast-4090` to be configured locally (~/.ssh/config).
# - On the remote, the repo is at /root/AiPIK, Conda base is /opt/conda, and `.env` is loaded if present.

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"<remote command>\"" >&2
  exit 1
fi

alias_name=${VAST_ALIAS:-vast-4090}
remote_cmd=$1

ssh -o BatchMode=yes "$alias_name" bash -lc "'
set -euo pipefail
cd /root/AiPIK
if [ -f /opt/conda/etc/profile.d/conda.sh ]; then
  source /opt/conda/etc/profile.d/conda.sh
  conda activate base || true
fi
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi
# Ensure writable TMPDIR for OCR on remote
mkdir -p /tmp/tess_tmp
export TMPDIR=/tmp/tess_tmp
echo "[vast-4090] Running: $remote_cmd"
eval "$remote_cmd"
'"
