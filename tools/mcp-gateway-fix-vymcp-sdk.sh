#!/usr/bin/env bash
set -Eeuo pipefail

CTID="${CTID:-118}"

if [[ $EUID -ne 0 ]] || ! command -v pct >/dev/null 2>&1; then
  echo "Run this script as root on a Proxmox VE node." >&2
  exit 1
fi

pct config "$CTID" >/dev/null 2>&1 || {
  echo "CT $CTID does not exist." >&2
  exit 1
}

pct status "$CTID" | grep -q 'status: running' || {
  echo "CT $CTID is not running." >&2
  exit 1
}

echo "==> Stopping VyMCP tunnel"
pct exec "$CTID" -- systemctl stop mcp-vymcp-tunnel.service || true

echo "==> Pinning MCP Python SDK to v1"
pct exec "$CTID" -- bash -c '
set -Eeuo pipefail
/opt/vymcp-venv/bin/pip install --upgrade "mcp>=1.2,<2"
'

echo "==> Verifying imports"
pct exec "$CTID" -- bash -c '
set -Eeuo pipefail
/opt/vymcp-venv/bin/python - <<PY
from mcp.server.fastmcp import FastMCP
import importlib.metadata
import vymcp
print("mcp=" + importlib.metadata.version("mcp"))
print("vymcp=" + importlib.metadata.version("vymcp"))
print("FastMCP import OK")
PY
'

echo "==> Testing VyManager token"
pct exec "$CTID" -- bash -c '
set -Eeuo pipefail
set -a
source /etc/mcp-gateway/vymcp.env
set +a

status="$(curl -sS -o /tmp/vymcp-sites.json -w "%{http_code}"   --connect-timeout 5   -H "Authorization: Bearer ${VYMANAGER_API_TOKEN}"   "${VYMANAGER_BASE_URL}/session/sites")"

if [[ "$status" != "200" ]]; then
  echo "VyManager token test failed: HTTP $status" >&2
  cat /tmp/vymcp-sites.json >&2 || true
  rm -f /tmp/vymcp-sites.json
  exit 1
fi

count="$(python3 - <<PY
import json
with open("/tmp/vymcp-sites.json","r",encoding="utf-8") as f:
    data=json.load(f)
print(len(data) if isinstance(data,list) else "unknown")
PY
)"
rm -f /tmp/vymcp-sites.json
echo "VyManager token OK; visible sites: $count"
'

echo "==> Starting VyMCP tunnel"
pct exec "$CTID" -- systemctl restart mcp-vymcp-tunnel.service

echo "==> Waiting for readiness"
ready=0
for _ in $(seq 1 20); do
  if pct exec "$CTID" -- curl -fsS http://127.0.0.1:19081/readyz >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done

if (( ready == 1 )); then
  echo "VyMCP tunnel: ready"
  pct exec "$CTID" -- systemctl --no-pager --full status mcp-vymcp-tunnel.service | sed -n '1,14p'
  exit 0
fi

echo "VyMCP tunnel did not become ready." >&2
pct exec "$CTID" -- journalctl -u mcp-vymcp-tunnel.service -n 80 --no-pager -o cat >&2 || true
exit 1
