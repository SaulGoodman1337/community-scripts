#!/usr/bin/env bash
set -Eeuo pipefail

# MCP Gateway LXC bootstrap for Proxmox VE 9.x
# - Creates an unprivileged Debian 13 LXC via community-scripts.org
# - Installs VyMCP, mcp-proxmox and OpenAI tunnel-client
# - Creates a privilege-separated, read-only Proxmox API token
# - Installs hardened systemd units for two outbound-only Secure MCP tunnels
#
# Run this script as root on a Proxmox VE node.
# Override defaults by exporting variables before running, e.g.:
#   CTID=160 RAM=3072 DISK=16 BRIDGE=vmbr0 ./create-mcp-gateway-lxc.sh
#   IPV4=192.168.150.40/22 IPV4_GW=192.168.150.1 ./create-mcp-gateway-lxc.sh

trap 'echo "ERROR: line $LINENO: $BASH_COMMAND" >&2' ERR
HOST_TMP=""
PVE_TOKEN_CREATED=0
INSTALL_SUCCESS=0
cleanup() {
  set +e
  [[ -n "${HOST_TMP:-}" && -d "$HOST_TMP" ]] && rm -rf "$HOST_TMP"
  if [[ "${PVE_TOKEN_CREATED:-0}" == "1" && "${INSTALL_SUCCESS:-0}" != "1" ]]; then
    echo "Install did not complete; revoking newly-created Proxmox API token $PVE_MCP_TOKEN_ID" >&2
    pveum user token remove "$PVE_MCP_USER" "$PVE_MCP_TOKEN_NAME" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

COMMUNITY_DEBIAN_URL="${COMMUNITY_DEBIAN_URL:-https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/debian.sh}"
HOSTNAME_CT="${HOSTNAME_CT:-mcp-gateway}"
CPU="${CPU:-2}"
RAM="${RAM:-2048}"
DISK="${DISK:-12}"
BRIDGE="${BRIDGE:-vmbr0}"
IPV4="${IPV4:-dhcp}"
IPV4_GW="${IPV4_GW:-}"
IPV6_METHOD="${IPV6_METHOD:-none}"
TIMEZONE="${TIMEZONE:-Europe/Berlin}"
ENABLE_GUEST_FIREWALL="${ENABLE_GUEST_FIREWALL:-0}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1" >&2
    exit 1
  }
}

for cmd in pct pvesh pvesm pveum curl python3 ip awk grep sed; do
  need_cmd "$cmd"
done

if [[ $EUID -ne 0 ]]; then
  echo "Run this script as root on the Proxmox VE host." >&2
  exit 1
fi

if ! pveversion >/dev/null 2>&1; then
  echo "This does not look like a Proxmox VE host." >&2
  exit 1
fi

HOST_TMP="$(mktemp -d)"
chmod 0700 "$HOST_TMP"

pick_storage() {
  local content="$1" preferred="$2"
  if pvesm status -content "$content" 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$preferred"; then
    printf '%s\n' "$preferred"
  else
    pvesm status -content "$content" 2>/dev/null | awk 'NR>1 {print $1; exit}'
  fi
}

CONTAINER_STORAGE="${CONTAINER_STORAGE:-$(pick_storage rootdir local-zfs)}"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-$(pick_storage vztmpl local)}"

[[ -n "$CONTAINER_STORAGE" ]] || { echo "No storage with content type rootdir found." >&2; exit 1; }
[[ -n "$TEMPLATE_STORAGE" ]] || { echo "No storage with content type vztmpl found." >&2; exit 1; }

CTID="${CTID:-$(pvesh get /cluster/nextid)}"
if pct status "$CTID" >/dev/null 2>&1; then
  echo "VMID $CTID already exists. Set CTID to a free ID." >&2
  exit 1
fi

PVE_NODE="$(hostname)"
PVE_FQDN="${PVE_FQDN:-$(hostname -f 2>/dev/null || hostname)}"
PVE_IP="${PVE_IP:-$(ip -4 -o addr show "$BRIDGE" scope global 2>/dev/null | awk 'NR==1 {split($4,a,"/"); print a[1]}' || true)}"
if [[ -z "$PVE_IP" ]]; then
  PVE_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi

PVE_MCP_USER="${PVE_MCP_USER:-mcp-gateway@pve}"
PVE_MCP_TOKEN_NAME="${PVE_MCP_TOKEN_NAME:-mcp-ro-${CTID}}"
PVE_MCP_TOKEN_ID="${PVE_MCP_USER}!${PVE_MCP_TOKEN_NAME}"

if pveum user token list "$PVE_MCP_USER" 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$PVE_MCP_TOKEN_NAME"; then
  echo "API token $PVE_MCP_TOKEN_ID already exists. Choose another PVE_MCP_TOKEN_NAME." >&2
  exit 1
fi

if [[ "$IPV4" != "dhcp" && -z "$IPV4_GW" ]]; then
  echo "IPV4 is static ($IPV4) but IPV4_GW is empty." >&2
  exit 1
fi

cat <<EOF

MCP gateway deployment
----------------------
CTID:              $CTID
Hostname:          $HOSTNAME_CT
CPU/RAM/Disk:      $CPU / ${RAM} MiB / ${DISK} GiB
Container storage: $CONTAINER_STORAGE
Template storage:  $TEMPLATE_STORAGE
Bridge:            $BRIDGE
IPv4:              $IPV4
IPv6 method:       $IPV6_METHOD
PVE API endpoint:  $PVE_FQDN:8006 ($PVE_IP)
PVE API identity:  $PVE_MCP_TOKEN_ID (PVEAuditor only)

EOF

read -r -p "Create this LXC and install the MCP gateway? [y/N] " answer
[[ "$answer" =~ ^[Yy]$ ]] || exit 0

echo "==> Creating Debian 13 LXC using Community Scripts"
COMMUNITY_ENV=(
  "PHS_SILENT=1"
  "var_ctid=$CTID"
  "var_hostname=$HOSTNAME_CT"
  "var_cpu=$CPU"
  "var_ram=$RAM"
  "var_disk=$DISK"
  "var_os=debian"
  "var_version=13"
  "var_unprivileged=1"
  "var_nesting=0"
  "var_keyctl=0"
  "var_fuse=0"
  "var_protection=yes"
  "var_brg=$BRIDGE"
  "var_net=$IPV4"
  "var_ipv6_method=$IPV6_METHOD"
  "var_timezone=$TIMEZONE"
  "var_tags=mcp"
  "var_container_storage=$CONTAINER_STORAGE"
  "var_template_storage=$TEMPLATE_STORAGE"
)
if [[ -n "$IPV4_GW" ]]; then
  COMMUNITY_ENV+=("var_gateway=$IPV4_GW")
fi

COMMUNITY_DEBIAN_SCRIPT="$HOST_TMP/community-debian.sh"
curl -fsSL "$COMMUNITY_DEBIAN_URL" -o "$COMMUNITY_DEBIAN_SCRIPT"
chmod 0700 "$COMMUNITY_DEBIAN_SCRIPT"
env "${COMMUNITY_ENV[@]}" bash "$COMMUNITY_DEBIAN_SCRIPT"

if ! pct config "$CTID" >/dev/null 2>&1; then
  echo "Community Scripts finished but CT $CTID was not created. Aborting." >&2
  exit 1
fi

pct set "$CTID" -onboot 1
pct start "$CTID" >/dev/null 2>&1 || true

for _ in $(seq 1 30); do
  if pct exec "$CTID" -- true >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
pct exec "$CTID" -- true >/dev/null

if [[ "$ENABLE_GUEST_FIREWALL" == "1" ]]; then
  NET0="$(pct config "$CTID" | sed -n 's/^net0: //p')"
  if [[ "$NET0" != *"firewall="* ]]; then
    pct set "$CTID" -net0 "${NET0},firewall=1"
  else
    NET0="$(printf '%s' "$NET0" | sed -E 's/(^|,)firewall=[01]/\1firewall=1/')"
    pct set "$CTID" -net0 "$NET0"
  fi
fi

echo "==> Installing base packages"
pct exec "$CTID" -- bash -lc '
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y dist-upgrade
apt-get install -y --no-install-recommends \
  ca-certificates curl git jq unzip xz-utils \
  python3 python3-venv python3-pip \
  nodejs npm build-essential openssl
node_major="$(node -p "process.versions.node.split(\".\")[0]")"
if (( node_major < 20 )); then
  echo "Node.js >=20 is required; Debian provided $(node --version)." >&2
  exit 1
fi
'

if [[ -f /etc/pve/pve-root-ca.pem ]]; then
  echo "==> Installing Proxmox cluster CA in the LXC"
  pct push "$CTID" /etc/pve/pve-root-ca.pem /usr/local/share/ca-certificates/proxmox-cluster-ca.crt
  pct exec "$CTID" -- chmod 0644 /usr/local/share/ca-certificates/proxmox-cluster-ca.crt
  pct exec "$CTID" -- update-ca-certificates >/dev/null
fi

if [[ -n "$PVE_IP" && -n "$PVE_FQDN" ]]; then
  pct exec "$CTID" -- bash -lc "grep -Fq ' $PVE_FQDN' /etc/hosts || echo '$PVE_IP $PVE_FQDN $PVE_NODE' >> /etc/hosts"
fi

echo "==> Installing VyMCP"
pct exec "$CTID" -- bash -lc '
set -Eeuo pipefail
rm -rf /opt/vymcp-venv
python3 -m venv /opt/vymcp-venv
/opt/vymcp-venv/bin/pip install --upgrade pip wheel
/opt/vymcp-venv/bin/pip install "git+https://github.com/Community-VyProjects/VyMCP.git"
test -x /opt/vymcp-venv/bin/vymcp
'

echo "==> Installing Proxmox MCP"
pct exec "$CTID" -- bash -lc '
set -Eeuo pipefail
rm -rf /opt/mcp-proxmox
git clone --depth 1 https://github.com/gilby125/mcp-proxmox.git /opt/mcp-proxmox
cd /opt/mcp-proxmox
if [[ -f package-lock.json ]]; then
  npm ci --omit=dev
else
  npm install --omit=dev
fi
node --check index.js
cat > /usr/local/bin/run-proxmox-mcp <<"EOF"
#!/usr/bin/env bash
set -Eeuo pipefail
cd /opt/mcp-proxmox
exec /usr/bin/node /opt/mcp-proxmox/index.js
EOF
chmod 0755 /usr/local/bin/run-proxmox-mcp
'

echo "==> Installing latest OpenAI Secure MCP tunnel-client"
pct exec "$CTID" -- bash -lc '
set -Eeuo pipefail
arch="$(dpkg --print-architecture)"
case "$arch" in
  amd64) platform="linux-amd64" ;;
  arm64) platform="linux-arm64" ;;
  *) echo "Unsupported architecture for tunnel-client release: $arch" >&2; exit 1 ;;
esac
release="$(curl -fsSL https://api.github.com/repos/openai/tunnel-client/releases/latest | python3 -c "import json,sys; print(json.load(sys.stdin)[\"tag_name\"])")"
archive="tunnel-client-${release}-${platform}.zip"
base="https://github.com/openai/tunnel-client/releases/download/${release}"
tmp="$(mktemp -d)"
trap "rm -rf \"$tmp\"" EXIT
cd "$tmp"
curl -fsSLO "$base/$archive"
curl -fsSLO "$base/SHA256SUMS.txt"
checksum_line="$(grep -F "$archive" SHA256SUMS.txt | head -n1 || true)"
[[ -n "$checksum_line" ]] || { echo "No checksum entry for $archive" >&2; exit 1; }
printf "%s\n" "$checksum_line" | sha256sum -c -
unzip -q "$archive" -d extracted
binary="$(find extracted -type f -name tunnel-client -print -quit)"
[[ -n "$binary" ]] || { echo "tunnel-client binary not found in $archive" >&2; exit 1; }
install -m 0755 "$binary" /usr/local/bin/tunnel-client
/usr/local/bin/tunnel-client --version
'

echo "==> Creating read-only Proxmox API identity"
if ! pveum user list | awk 'NR>1 {print $1}' | grep -Fxq "$PVE_MCP_USER"; then
  pveum user add "$PVE_MCP_USER" --comment "Read-only MCP gateway service account"
fi
# Token permissions can never exceed the backing user. Give both only PVEAuditor.
pveum acl modify / -user "$PVE_MCP_USER" -role PVEAuditor
TOKEN_JSON="$(pveum user token add "$PVE_MCP_USER" "$PVE_MCP_TOKEN_NAME" --privsep 1 --output-format json)"
PVE_TOKEN_CREATED=1
PVE_TOKEN_VALUE="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["value"])' <<<"$TOKEN_JSON")"
[[ -n "$PVE_TOKEN_VALUE" && "$PVE_TOKEN_VALUE" != "None" ]] || { echo "Could not parse API token secret." >&2; exit 1; }
pveum acl modify / -token "$PVE_MCP_TOKEN_ID" -role PVEAuditor

echo "==> Installing MCP gateway service account and configuration"
pct exec "$CTID" -- bash -lc '
set -Eeuo pipefail
if ! id mcp-gateway >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /var/lib/mcp-gateway --shell /usr/sbin/nologin mcp-gateway
fi
install -d -m 0750 -o root -g mcp-gateway /etc/mcp-gateway
install -d -m 0750 -o mcp-gateway -g mcp-gateway /var/lib/mcp-gateway
'

TMP_PVE_ENV="$HOST_TMP/proxmox-pve.env"
: > "$TMP_PVE_ENV"
chmod 0600 "$TMP_PVE_ENV"
cat > "$TMP_PVE_ENV" <<EOF
PROXMOX_HOST=$PVE_FQDN
PROXMOX_PORT=8006
PROXMOX_USER=$PVE_MCP_USER
PROXMOX_TOKEN_NAME=$PVE_MCP_TOKEN_NAME
PROXMOX_TOKEN_VALUE=$PVE_TOKEN_VALUE
PROXMOX_ALLOW_ELEVATED=false
PROXMOX_VERIFY_TLS=true
NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/proxmox-cluster-ca.crt
EOF
pct push "$CTID" "$TMP_PVE_ENV" /etc/mcp-gateway/proxmox-pve.env
pct exec "$CTID" -- chown root:mcp-gateway /etc/mcp-gateway/proxmox-pve.env
pct exec "$CTID" -- chmod 0640 /etc/mcp-gateway/proxmox-pve.env

echo "==> Installing hardened tunnel services and configure helper"
TMP_SETUP="$HOST_TMP/configure-mcp-gateway"
cat > "$TMP_SETUP" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

install -d -m 0750 -o root -g mcp-gateway /etc/mcp-gateway

read -r -s -p "OpenAI tunnel runtime API key (CONTROL_PLANE_API_KEY): " OPENAI_KEY
echo
[[ -n "$OPENAI_KEY" ]] || { echo "API key is required." >&2; exit 1; }

read -r -p "Tunnel ID for VyMCP (tunnel_...): " VYMCP_TUNNEL_ID
[[ "$VYMCP_TUNNEL_ID" == tunnel_* ]] || { echo "Invalid VyMCP tunnel ID." >&2; exit 1; }

read -r -p "Tunnel ID for Proxmox MCP (tunnel_...): " PROXMOX_TUNNEL_ID
[[ "$PROXMOX_TUNNEL_ID" == tunnel_* ]] || { echo "Invalid Proxmox tunnel ID." >&2; exit 1; }

read -r -p "VyManager base URL [http://192.168.150.60:8000]: " VYMANAGER_BASE_URL
VYMANAGER_BASE_URL="${VYMANAGER_BASE_URL:-http://192.168.150.60:8000}"
VYMANAGER_BASE_URL="${VYMANAGER_BASE_URL%/}"

read -r -s -p "VyManager API token (vym_...): " VYMANAGER_API_TOKEN
echo
[[ -n "$VYMANAGER_API_TOKEN" ]] || { echo "VyManager API token is required." >&2; exit 1; }

umask 0077
cat > /etc/mcp-gateway/vymcp.env <<ENV
CONTROL_PLANE_API_KEY=$OPENAI_KEY
CONTROL_PLANE_TUNNEL_ID=$VYMCP_TUNNEL_ID
MCP_COMMAND=/opt/vymcp-venv/bin/vymcp
VYMANAGER_BASE_URL=$VYMANAGER_BASE_URL
VYMANAGER_API_TOKEN=$VYMANAGER_API_TOKEN
VYMANAGER_ENABLE_WRITES=false
VYMANAGER_VERIFY_SSL=true
VYMANAGER_TIMEOUT=30
ENV

cat > /etc/mcp-gateway/proxmox-tunnel.env <<ENV
CONTROL_PLANE_API_KEY=$OPENAI_KEY
CONTROL_PLANE_TUNNEL_ID=$PROXMOX_TUNNEL_ID
MCP_COMMAND=/usr/local/bin/run-proxmox-mcp
ENV

chown root:mcp-gateway /etc/mcp-gateway/vymcp.env /etc/mcp-gateway/proxmox-tunnel.env
chmod 0640 /etc/mcp-gateway/vymcp.env /etc/mcp-gateway/proxmox-tunnel.env

systemctl daemon-reload
systemctl enable --now mcp-vymcp-tunnel.service mcp-proxmox-tunnel.service
sleep 2

echo
echo "Service state:"
systemctl --no-pager --full status mcp-vymcp-tunnel.service mcp-proxmox-tunnel.service || true

echo
echo "Local readiness:"
curl -fsS http://127.0.0.1:19081/readyz || true
echo
curl -fsS http://127.0.0.1:19082/readyz || true
echo
EOF
pct push "$CTID" "$TMP_SETUP" /usr/local/sbin/configure-mcp-gateway
pct exec "$CTID" -- chmod 0750 /usr/local/sbin/configure-mcp-gateway

TMP_STATUS="$HOST_TMP/mcp-gateway-status"
cat > "$TMP_STATUS" <<'EOF'
#!/usr/bin/env bash
set -u
systemctl --no-pager --full status mcp-vymcp-tunnel.service mcp-proxmox-tunnel.service || true
echo
printf 'VyMCP tunnel readiness:   '
curl -fsS http://127.0.0.1:19081/readyz 2>/dev/null || echo 'not ready'
echo
printf 'Proxmox tunnel readiness: '
curl -fsS http://127.0.0.1:19082/readyz 2>/dev/null || echo 'not ready'
echo
EOF
pct push "$CTID" "$TMP_STATUS" /usr/local/sbin/mcp-gateway-status
pct exec "$CTID" -- chmod 0755 /usr/local/sbin/mcp-gateway-status

TMP_VY_UNIT="$HOST_TMP/mcp-vymcp-tunnel.service"
cat > "$TMP_VY_UNIT" <<'EOF'
[Unit]
Description=OpenAI Secure MCP Tunnel - VyMCP
After=network-online.target
Wants=network-online.target
ConditionPathExists=/etc/mcp-gateway/vymcp.env

[Service]
Type=simple
User=mcp-gateway
Group=mcp-gateway
Environment=HOME=/var/lib/mcp-gateway
EnvironmentFile=/etc/mcp-gateway/vymcp.env
ExecStart=/usr/local/bin/tunnel-client run --health.listen-addr 127.0.0.1:19081
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
CapabilityBoundingSet=
ReadWritePaths=/var/lib/mcp-gateway

[Install]
WantedBy=multi-user.target
EOF
pct push "$CTID" "$TMP_VY_UNIT" /etc/systemd/system/mcp-vymcp-tunnel.service

TMP_PVE_UNIT="$HOST_TMP/mcp-proxmox-tunnel.service"
cat > "$TMP_PVE_UNIT" <<'EOF'
[Unit]
Description=OpenAI Secure MCP Tunnel - Proxmox MCP
After=network-online.target
Wants=network-online.target
ConditionPathExists=/etc/mcp-gateway/proxmox-tunnel.env
ConditionPathExists=/etc/mcp-gateway/proxmox-pve.env

[Service]
Type=simple
User=mcp-gateway
Group=mcp-gateway
Environment=HOME=/var/lib/mcp-gateway
EnvironmentFile=/etc/mcp-gateway/proxmox-pve.env
EnvironmentFile=/etc/mcp-gateway/proxmox-tunnel.env
ExecStart=/usr/local/bin/tunnel-client run --health.listen-addr 127.0.0.1:19082
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
CapabilityBoundingSet=
ReadWritePaths=/var/lib/mcp-gateway

[Install]
WantedBy=multi-user.target
EOF
pct push "$CTID" "$TMP_PVE_UNIT" /etc/systemd/system/mcp-proxmox-tunnel.service

pct exec "$CTID" -- systemctl daemon-reload

# Do not expose SSH by default; management remains available through pct exec.
pct exec "$CTID" -- bash -lc 'systemctl disable --now ssh.service ssh.socket 2>/dev/null || true'

CT_IP="$(pct exec "$CTID" -- hostname -I 2>/dev/null | awk '{print $1}')"

INSTALL_SUCCESS=1

cat <<EOF

====================================================================
MCP gateway LXC created successfully
====================================================================
CTID:      $CTID
Hostname:  $HOSTNAME_CT
IP:        ${CT_IP:-unknown}

Installed:
  - VyMCP:              /opt/vymcp-venv/bin/vymcp
  - Proxmox MCP:        /opt/mcp-proxmox
  - OpenAI tunnel:      /usr/local/bin/tunnel-client
  - PVE read-only token: $PVE_MCP_TOKEN_ID

Writes are OFF:
  - Proxmox MCP: PROXMOX_ALLOW_ELEVATED=false
  - VyMCP:       VYMANAGER_ENABLE_WRITES=false

Next steps:
  1. In OpenAI Platform create TWO Secure MCP tunnels:
       - one for VyMCP
       - one for Proxmox MCP
     Create a runtime API key with Tunnels Read + Use.

  2. Configure the gateway interactively:
       pct exec $CTID -- /usr/local/sbin/configure-mcp-gateway

  3. Check status:
       pct exec $CTID -- /usr/local/sbin/mcp-gateway-status

  4. In ChatGPT developer-mode app setup, attach each app to its tunnel ID.

Useful logs:
  pct exec $CTID -- journalctl -u mcp-vymcp-tunnel -f
  pct exec $CTID -- journalctl -u mcp-proxmox-tunnel -f

To revoke the Proxmox token immediately:
  pveum user token remove '$PVE_MCP_USER' '$PVE_MCP_TOKEN_NAME'
====================================================================
EOF
