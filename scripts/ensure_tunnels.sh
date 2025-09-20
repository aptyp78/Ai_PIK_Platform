#!/usr/bin/env bash
set -euo pipefail

# Ensure local HTTP servers are running and expose them via cloudflared tunnels.
# Writes discovered endpoints to out/portal/endpoints.json

mkdir -p Logs out/portal tmp

# Start local servers if missing
if ! ss -ltnp 2>/dev/null | rg -q ":8000\b"; then
  nohup python3 -m http.server 8000 -d out/portal >> Logs/http_portal.log 2>&1 & echo $! > Logs/http_portal.pid || true
fi
if ! ss -ltnp 2>/dev/null | rg -q ":8001\b"; then
  nohup python3 -m http.server 8001 -d eval >> Logs/http_eval2.log 2>&1 & echo $! > Logs/http_eval2.pid || true
fi

# cloudflared binary
CF_BIN="cloudflared"
if command -v "$CF_BIN" >/dev/null 2>&1; then
  :
elif [ -x tmp/cloudflared ]; then
  CF_BIN="tmp/cloudflared"
else
  URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
  curl -fsSL "$URL" -o tmp/cloudflared
  chmod +x tmp/cloudflared
  CF_BIN="tmp/cloudflared"
fi

start_tunnel() {
  local port="$1"; local name="cf_${port}"; local log="Logs/${name}.log"; local pidf="Logs/${name}.pid"
  if [ -f "$pidf" ] && ps -p "$(cat "$pidf" 2>/dev/null)" >/dev/null 2>&1; then
    : # already running
  else
    nohup "$CF_BIN" tunnel --no-autoupdate --url "http://127.0.0.1:${port}" > "$log" 2>&1 & echo $! > "$pidf"
    sleep 0.5
  fi
  # wait for URL
  local url=""
  for i in $(seq 1 40); do
    if grep -qE "https://[a-zA-Z0-9.-]*trycloudflare.com" "$log"; then
      url=$(grep -oE "https://[a-zA-Z0-9.-]*trycloudflare.com" "$log" | head -n1)
      break
    fi
    sleep 0.25
  done
  echo "$url"
}

PORTAL_URL=$(start_tunnel 8000)
EVAL_URL=$(start_tunnel 8001)

HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
LOCAL_URL="http://127.0.0.1:8000/landing/index.html"
INTERNAL_URL="http://${HOST_IP:-127.0.0.1}:8000/landing/index.html"

cat > out/portal/endpoints.json << JSON
{
  "portal_local": "${LOCAL_URL}",
  "portal_internal": "${INTERNAL_URL}",
  "portal_public": "${PORTAL_URL}",
  "eval_public": "${EVAL_URL}",
  "eval_progress": "${EVAL_URL%/}/progress.html",
  "eval_visual_review": "${EVAL_URL%/}/visual_review.html"
}
JSON

echo "Portal local:     ${LOCAL_URL}"
echo "Portal internal:  ${INTERNAL_URL}"
echo "Portal public:    ${PORTAL_URL}"
echo "Eval progress:    ${EVAL_URL%/}/progress.html"
echo "Eval visual:      ${EVAL_URL%/}/visual_review.html"
