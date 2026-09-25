#!/usr/bin/env bash
set -Eeuo pipefail

CTID="${CTID:-118}"
BRIDGE="${BRIDGE:-vmbr0}"

if [[ $EUID -ne 0 ]] || ! command -v pct >/dev/null 2>&1; then
  echo "Run this script as root on a Proxmox VE node." >&2
  exit 1
fi

for cmd in openssl timeout grep sed awk ip; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Missing required command: $cmd" >&2; exit 1; }
done

pct config "$CTID" >/dev/null 2>&1 || { echo "CT $CTID does not exist." >&2; exit 1; }
pct status "$CTID" | grep -q 'status: running' || { echo "CT $CTID is not running." >&2; exit 1; }

PVE_IP="${PVE_IP:-$(ip -4 -o addr show "$BRIDGE" scope global 2>/dev/null | awk 'NR==1 {split($4,a,"/"); print a[1}')}"
[[ -n "$PVE_IP" ]] || { echo "Could not determine PVE IPv4 address. Set PVE_IP=... explicitly." >&2; exit 1; }

CERT_DNS="$(
  timeout 5 openssl s_client -connect "127.0.0.1:8006" -servername "$(hostname -f 2>/dev/null || hostname)" </dev/null 2>/dev/null \
    | openssl x509 -noout -ext subjectAltName 2>/dev/null \
    | grep -o 'DNS:[^, ]*' \
    | head -n1 \
    | cut -d: -f2-
)"

[[ -n "$CERT_DNS" ]] || { echo "Could not determine a DNS SAN from the active pveproxy certificate." >&2; exit 1; }

ENVFILE="/etc/mcp-gateway/proxmox-pve.env"
pct exec "$CTID" -- test -f "$ENVFILE" || { echo "$ENVFILE missing in CT $CTID." >&2; exit 1; }

echo "Active pveproxy certificate DNS SAN: $CERT_DNS"
echo "PVE API IPv4: $PVE_IP"

pct exec "$CTID" -- sed -i "s|^PROXMOX_HOST=.*$|PROXMOX_HOST=$CERT_DNS|" "$ENVFILE"

pct exec "$CTID" -- bash -c "
  set -Eeuo pipefail
  grep -Fq ' $CERT_DNS' /etc/hosts || echo '$PVE_IP $CERT_DNS' >> /etc/hosts
"

echo
echo "Updated CT $CTID:"
pct exec "$CTID" -- grep '^PROXMOX_HOST=' "$ENVFILE"

echo
echo "TLS/API verification:"
pct exec "$CTID" -- bash -c '
  set -Eeuo pipefail
  set -a
  source /etc/mcp-gateway/proxmox-pve.env
  set +a
  curl -fsS --connect-timeout 5 \ \
    -H "Authorization: PVEAPIToken=${PROXMOX_USER}!${PROXMOX_TOKEN_NAME}=${PROXMOX_TOKEN_VALUE}" \
    "https://${PROXMOX_HOST}:${PROXMOX_PORT}/api2/json/version" \
    | jq .
'

echo
echo "PVE API host repair complete."
