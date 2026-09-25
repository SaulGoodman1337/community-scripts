#!/usr/bin/env bash
set -Eeuo pipefail

CTID="${CTID:-118}"
VYMANAGER_URL="${VYMANAGER_URL:-http://192.168.150.60:8000}"

ok()   { printf '  [OK]   %s\n' "$*"; }
warn() { printf '  [WARN] %s\n' "$*"; }
fail() { printf '  [FAIL] %s\n' "$*" >&2; FAILURES=$((FAILURES+1)); }

FAILURES=0

if [[ $EUID -ne 0 ]] || ! command -v pct >/dev/null 2>&1; then
  echo "Run this script as root on a Proxmox VE node." >&2
  exit 1
fi

echo "MCP gateway preflight - CT $CTID"
echo "================================"

if ! pct config "$CTID" >/dev/null 2>&1; then
  echo "CT $CTID does not exist." >&2
  exit 1
fi

if pct status "$CTID" | grep -q 'status: running'; then
  ok "container is running"
else
  fail "container is not running"
fi

if pct config "$CTID" | grep -Eq '^features:.*(^|,)nesting=1(,|$)|^features:.*nesting=1'; then
  ok "nesting=1"
else
  fail "nesting is not enabled"
fi

state="$(pct exec "$CTID" -- systemctl is-system-running 2>/dev/null || true)"
if [[ "$state" == "running" ]]; then
  ok "systemd state: running"
else
  warn "systemd state: ${state:-unknown}"
fi

failed_units="$(pct exec "$CTID" -- systemctl --failed --no-legend 2>/dev/null | sed '/^[[:space:]]*$/d' || true)"
if [[ -z "$failed_units" ]]; then
  ok "no failed systemd units"
else
  fail "failed systemd units detected"
  printf '%s\n' "$failed_units"
fi

for bin in   /opt/vymcp-venv/bin/vymcp   /usr/local/bin/run-proxmox-mcp   /usr/local/bin/tunnel-client; do
  if pct exec "$CTID" -- test -x "$bin"; then
    ok "$bin present"
  else
    fail "$bin missing or not executable"
  fi
done

tunnel_version="$(pct exec "$CTID" -- /usr/local/bin/tunnel-client --version 2>/dev/null || true)"
[[ -n "$tunnel_version" ]] && ok "tunnel-client: $tunnel_version" || fail "tunnel-client does not run"

node_version="$(pct exec "$CTID" -- node --version 2>/dev/null || true)"
[[ "$node_version" =~ ^v([2-9][0-9]|1[0-9][0-9])\. ]] && ok "Node.js: $node_version" || fail "Node.js 20+ required, found: ${node_version:-none}"

if pct exec "$CTID" -- test -r /usr/local/share/ca-certificates/proxmox-cluster-ca.crt; then
  ok "Proxmox cluster CA installed"
else
  fail "Proxmox cluster CA missing"
fi

if pct exec "$CTID" -- test -r /etc/mcp-gateway/proxmox-pve.env; then
  ok "Proxmox MCP environment present"
else
  fail "/etc/mcp-gateway/proxmox-pve.env missing"
fi

echo
echo "Proxmox API/TLS test"
echo "--------------------"
PVE_API_OK=0
if pct exec "$CTID" -- bash -c '
set -Eeuo pipefail
set -a
source /etc/mcp-gateway/proxmox-pve.env
set +a
curl -fsS --connect-timeout 5 \
  --cacert /usr/local/share/ca-certificates/proxmox-cluster-ca.crt \
  -H "Authorization: PVEAPIToken=${PROXMOX_USER}!${PROXMOX_TOKEN_NAME}=${PROXMOX_TOKEN_VALUE}" \
  "https://${PROXMOX_HOST}:${PROXMOX_PORT}/api2/json/version" \
  | jq -e ".data.version != null" >/dev/null
'; then
  ok "PVE token authenticates and TLS verification succeeds"
  PVE_API_OK=1
else
  fail "PVE API token/TLS test failed"
  echo
  echo "  Certificate presented by pveproxy:"
  pct exec "$CTID" -- bash -c '
    set -a
    source /etc/mcp-gateway/proxmox-pve.env
    set +a
    timeout 8 openssl s_client -connect "${PROXMOX_HOST}:${PROXMOX_PORT}" -servername "${PROXMOX_HOST}" </dev/null 2>/dev/null \
      | openssl x509 -noout -subject -issuer -ext subjectAltName 2>/dev/null
  ' | sed 's/^/    /' || true
  echo
  warn "The CA may be trusted while the configured PROXMOX_HOST is absent from the certificate SAN."
fi

echo
echo "Proxmox MCP read-only smoke test"
echo "--------------------------------"
if (( PVE_API_OK == 1 )); then
  mcp_failed=0
  for tool in proxmox_get_nodes proxmox_get_vms proxmox_whoami; do
    response="$(pct exec "$CTID" -- bash -c "
      set -Eeuo pipefail
      set -a
      source /etc/mcp-gateway/proxmox-pve.env
      set +a
      cd /opt/mcp-proxmox
      printf '%s\\n' '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"$tool\",\"arguments\":{}}}' \
        | timeout 15 node index.js 2>/dev/null
    " 2>/dev/null | grep -m1 '^{' || true)"
    if [[ -n "$response" ]] && jq -e '
      .result != null
      and (.result.isError != true)
      and ((.result.structuredContent.error? // null) == null)
    ' >/dev/null 2>&1 <<<"$response"; then
      ok "$tool"
    else
      fail "$tool returned an MCP error or no valid response"
      [[ -n "$response" ]] && jq -r '.result.content[0].text? // .error.message? // .' <<<"$response" 2>/dev/null | sed 's/^/         /' || true
      mcp_failed=1
    fi
  done
  if (( mcp_failed == 0 )); then
    ok "mcp-proxmox read-only smoke test passed"
  fi
else
  warn "Skipping MCP smoke test until PVE TLS/API connectivity is fixed"
fi

echo
echo "VyManager reachability"
echo "----------------------"
vy_host="$(python3 -c 'from urllib.parse import urlparse; import sys; u=urlparse(sys.argv[1]); print(u.hostname or "")' "$VYMANAGER_URL")"
vy_port="$(python3 -c 'from urllib.parse import urlparse; import sys; u=urlparse(sys.argv[1]); print(u.port or (443 if u.scheme=="https" else 80))' "$VYMANAGER_URL")"
if pct exec "$CTID" -- bash -c "timeout 4 bash -c '</dev/tcp/$vy_host/$vy_port'" >/dev/null 2>&1; then
  ok "TCP $vy_host:$vy_port reachable"
  vy_code="$(pct exec "$CTID" -- curl -sS -o /dev/null --connect-timeout 5 -w '%{http_code}' "$VYMANAGER_URL/docs" 2>/dev/null || true)"
  if [[ "$vy_code" =~ ^[1-5][0-9][0-9]$ && "$vy_code" != "000" ]]; then
    ok "VyManager HTTP endpoint responds at $VYMANAGER_URL/docs (HTTP $vy_code)"
  else
    fail "TCP is open, but no usable HTTP response from $VYMANAGER_URL/docs"
  fi
else
  fail "TCP $vy_host:$vy_port is not reachable from CT $CTID"
fi

echo
echo "npm audit (informational)"
echo "-------------------------"
audit_json="$(pct exec "$CTID" -- bash -c 'cd /opt/mcp-proxmox && npm audit --omit=dev --json 2>/dev/null' 2>/dev/null || true)"
if [[ -n "$audit_json" && "$audit_json" != \{* ]]; then
  audit_json="$(sed -n '/^{/,$p' <<<"$audit_json")"
fi
if [[ -n "$audit_json" ]] && jq -e '.metadata.vulnerabilities' >/dev/null 2>&1 <<<"$audit_json"; then
  critical="$(jq -r '.metadata.vulnerabilities.critical // 0' <<<"$audit_json")"
  high="$(jq -r '.metadata.vulnerabilities.high // 0' <<<"$audit_json")"
  moderate="$(jq -r '.metadata.vulnerabilities.moderate // 0' <<<"$audit_json")"
  low="$(jq -r '.metadata.vulnerabilities.low // 0' <<<"$audit_json")"
  if (( critical == 0 && high == 0 && moderate == 0 && low == 0 )); then
    ok "npm audit: no known vulnerabilities"
  else
    warn "npm audit: critical=$critical high=$high moderate=$moderate low=$low"
    jq -r '
      .vulnerabilities // {}
      | to_entries[]
      | "         - \(.key): severity=\(.value.severity), via=" +
        ((.value.via // []) | map(if type=="object" then (.title // .name // "advisory") else tostring end) | join("; "))
    ' <<<"$audit_json" 2>/dev/null || true
    warn "No automatic npm audit fix was applied."
  fi
else
  warn "npm audit result could not be parsed"
fi

echo
echo "Tunnel configuration"
echo "--------------------"
for envfile in /etc/mcp-gateway/vymcp.env /etc/mcp-gateway/proxmox-tunnel.env; do
  if pct exec "$CTID" -- test -r "$envfile"; then
    ok "$envfile configured"
  else
    warn "$envfile not configured yet (expected before tunnel IDs/API key are supplied)"
  fi
done

echo
if (( FAILURES == 0 )); then
  echo "PRECHECK RESULT: PASS"
  exit 0
else
  echo "PRECHECK RESULT: $FAILURES failure(s)"
  exit 1
fi
