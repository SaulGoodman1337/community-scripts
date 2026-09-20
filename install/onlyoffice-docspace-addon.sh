#!/usr/bin/env bash
set -Eeuo pipefail

# Install ONLYOFFICE DocSpace Community next to an existing native
# ONLYOFFICE Docs Community installation in the same Debian LXC.
# Intended for the Proxmox VE community-scripts ONLYOFFICE LXC.

DOCSPACE_PORT="${DOCSPACE_PORT:-8080}"
DOCS_PUBLIC_URL="${DOCS_PUBLIC_URL:-}"
DOCSPACE_SKIP_HARDWARE_CHECK="${DOCSPACE_SKIP_HARDWARE_CHECK:-false}"
DOCSPACE_INSTALL_FLUENTBIT="${DOCSPACE_INSTALL_FLUENTBIT:-false}"
ONLYOFFICE_LOCAL_JSON="/etc/onlyoffice/documentserver/local.json"
INSTALLER_URL="https://download.onlyoffice.com/docspace/docspace-install.sh"
LOG_FILE="/var/log/onlyoffice-docspace-addon.log"
BACKUP_DIR="/root/onlyoffice-docspace-preinstall-$(date +%Y%m%d-%H%M%S)"

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { printf '%b[INFO]%b %s\n' "$BLUE" "$NC" "$*"; }
ok() { printf '%b[ OK ]%b %s\n' "$GREEN" "$NC" "$*"; }
warn() { printf '%b[WARN]%b %s\n' "$YELLOW" "$NC" "$*"; }
die() { printf '%b[FAIL]%b %s\n' "$RED" "$NC" "$*" >&2; exit 1; }

POLICY_FILE="/usr/sbin/policy-rc.d"
POLICY_ORIG="/usr/sbin/policy-rc.d.onlyoffice-docspace-orig"
POLICY_ACTIVE=false

install_openresty_policy() {
  if [[ -e "$POLICY_ORIG" ]]; then
    die "Found stale $POLICY_ORIG. Restore/remove it manually before continuing."
  fi
  if [[ -e "$POLICY_FILE" ]]; then
    mv "$POLICY_FILE" "$POLICY_ORIG"
  fi
  cat >"$POLICY_FILE" <<'POLICY'
#!/bin/sh
svc="$(basename "$1" .service)"
if [ "$svc" = "openresty" ]; then
  # The stock OpenResty package initially tries port 80. ONLYOFFICE Docs already
  # owns that port. DocSpace will write its configured port before restarting
  # OpenResty itself later in the package configuration.
  exit 101
fi
if [ -x /usr/sbin/policy-rc.d.onlyoffice-docspace-orig ]; then
  exec /usr/sbin/policy-rc.d.onlyoffice-docspace-orig "$@"
fi
exit 0
POLICY
  chmod 755 "$POLICY_FILE"
  POLICY_ACTIVE=true
}

restore_openresty_policy() {
  if [[ "$POLICY_ACTIVE" == "true" ]]; then
    rm -f "$POLICY_FILE"
    if [[ -e "$POLICY_ORIG" ]]; then
      mv "$POLICY_ORIG" "$POLICY_FILE"
    fi
    POLICY_ACTIVE=false
  fi
}

on_error() {
  local rc=$?
  restore_openresty_policy || true
  printf '\n%b[FAIL]%b Installation stopped with exit code %s.\n' "$RED" "$NC" "$rc" >&2
  printf 'Log: %s\n' "$LOG_FILE" >&2
  printf 'Pre-install backup: %s\n' "$BACKUP_DIR" >&2
  exit "$rc"
}
trap on_error ERR

[[ $EUID -eq 0 ]] || die "Run this installer as root inside the ONLYOFFICE LXC."
[[ -f /etc/debian_version ]] || die "This add-on currently supports Debian-based native ONLYOFFICE LXC installations only."

ARCH="$(dpkg --print-architecture 2>/dev/null || true)"
[[ "$ARCH" == "amd64" ]] || die "DocSpace DEB packages currently require amd64. Detected: ${ARCH:-unknown}."

DOCSPACE_DPKG_STATUS="$(dpkg-query -W -f='${Status}' docspace 2>/dev/null || true)"
DOCSPACE_PARTIAL=false
if [[ "$DOCSPACE_DPKG_STATUS" == "install ok installed" ]]; then
  die "DocSpace is already installed. This script is intentionally install-only and will not perform an in-place update."
elif [[ -n "$DOCSPACE_DPKG_STATUS" ]]; then
  DOCSPACE_PARTIAL=true
  warn "Detected a partially installed DocSpace package state: $DOCSPACE_DPKG_STATUS"
  warn "The installer will try to repair and finish the interrupted installation."
fi

if ! dpkg-query -W -f='${Status}' onlyoffice-documentserver 2>/dev/null | grep -q 'install ok installed'; then
  die "No native onlyoffice-documentserver package found. This script is for the Proxmox community-scripts ONLYOFFICE LXC."
fi

[[ -f "$ONLYOFFICE_LOCAL_JSON" ]] || die "Missing $ONLYOFFICE_LOCAL_JSON."

case "$DOCSPACE_PORT" in
  ''|*[!0-9]*) die "DOCSPACE_PORT must be numeric." ;;
esac
(( DOCSPACE_PORT >= 1024 && DOCSPACE_PORT <= 65535 )) || die "DOCSPACE_PORT must be between 1024 and 65535."

if ! command -v ss >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq iproute2
fi
if ss -H -ltn | awk '{print $4}' | grep -qE ":${DOCSPACE_PORT}$"; then
  die "TCP port $DOCSPACE_PORT is already in use. Set another port, e.g. DOCSPACE_PORT=8180."
fi

# DocSpace/OpenSearch requires this kernel-wide setting. In an unprivileged LXC
# it normally has to be changed on the Proxmox host, not inside the container.
VM_MAX_MAP_COUNT="$(cat /proc/sys/vm/max_map_count 2>/dev/null || echo 0)"
if [[ "$VM_MAX_MAP_COUNT" =~ ^[0-9]+$ ]] && (( VM_MAX_MAP_COUNT < 262144 )); then
  cat >&2 <<MSG
${RED}[FAIL]${NC} vm.max_map_count is $VM_MAX_MAP_COUNT; OpenSearch requires at least 262144.
Set this on the Proxmox HOST, then run this installer again:

  echo 'vm.max_map_count=262144' > /etc/sysctl.d/99-opensearch.conf
  sysctl --system

This setting is kernel-wide and normally cannot be raised from an unprivileged LXC.
MSG
  exit 1
fi

# Basic visibility into resources. The official installer performs its own
# hardware check unless DOCSPACE_SKIP_HARDWARE_CHECK=true is explicitly set.
CPU_COUNT="$(nproc 2>/dev/null || echo '?')"
MEM_MB="$(awk '/MemTotal:/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo '?')"
FREE_GB="$(df -Pk / | awk 'NR==2 {printf "%d", $4/1024/1024}')"
info "Detected resources: ${CPU_COUNT} vCPU, ~${MEM_MB} MiB RAM, ~${FREE_GB} GiB free on /."
warn "Current ONLYOFFICE guidance for DocSpace is substantially higher than a normal Docs-only LXC. Resize the LXC before installation if necessary."

command -v python3 >/dev/null 2>&1 || die "python3 is required to read the existing ONLYOFFICE JWT configuration."

JWT_SECRET="$(python3 - "$ONLYOFFICE_LOCAL_JSON" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    d=json.load(f)
try:
    print(d['services']['CoAuthoring']['secret']['inbox']['string'])
except Exception:
    pass
PY
)"
[[ -n "$JWT_SECRET" ]] || die "Could not read services.CoAuthoring.secret.inbox.string from local.json."

JWT_HEADER="$(python3 - "$ONLYOFFICE_LOCAL_JSON" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    d=json.load(f)
header = (
    d.get('services', {}).get('CoAuthoring', {}).get('token', {}).get('inbox', {}).get('header')
    or 'AuthorizationJwt'
)
print(header)
PY
)"

PRIMARY_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[[ -n "$PRIMARY_IP" ]] || die "Could not determine the LXC IP address. Set DOCS_PUBLIC_URL explicitly and ensure networking is configured."

if [[ -z "$DOCS_PUBLIC_URL" ]]; then
  DOCS_PUBLIC_URL="http://${PRIMARY_IP}/"
  warn "DOCS_PUBLIC_URL was not set; using $DOCS_PUBLIC_URL for the initial installation."
  warn "When you enable HTTPS through VyOS HAProxy, change the Document Service URL in DocSpace to the HTTPS Docs hostname."
fi

case "$DOCS_PUBLIC_URL" in
  http://*|https://*) ;;
  *) die "DOCS_PUBLIC_URL must start with http:// or https://" ;;
esac

# Keep the URL canonical for ONLYOFFICE configuration.
[[ "$DOCS_PUBLIC_URL" == */ ]] || DOCS_PUBLIC_URL="${DOCS_PUBLIC_URL}/"

mkdir -p "$BACKUP_DIR"
cp -a "$ONLYOFFICE_LOCAL_JSON" "$BACKUP_DIR/local.json"
[[ -d /etc/nginx ]] && cp -a /etc/nginx "$BACKUP_DIR/nginx"
dpkg --get-selections > "$BACKUP_DIR/dpkg-selections.txt"
debconf-get-selections > "$BACKUP_DIR/debconf-selections.txt" 2>/dev/null || true

info "Preseeding DocSpace: port=$DOCSPACE_PORT, Docs URL=$DOCS_PUBLIC_URL, JWT header=$JWT_HEADER"
printf '%s\n' \
  "docspace docspace/port string $DOCSPACE_PORT" \
  "docspace docspace/ds-url string $DOCS_PUBLIC_URL" \
  "docspace docspace/jwt-header string $JWT_HEADER" \
  "docspace docspace/jwt-secret string $JWT_SECRET" \
  | debconf-set-selections

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
INSTALLER="$TMP_DIR/docspace-install.sh"

info "Downloading the official ONLYOFFICE DocSpace Community installer."
curl -fsSL "$INSTALLER_URL" -o "$INSTALLER"
chmod 700 "$INSTALLER"

SKIP_HC_ARG="false"
case "${DOCSPACE_SKIP_HARDWARE_CHECK,,}" in
  1|true|yes|y) SKIP_HC_ARG="true" ;;
esac

FLUENTBIT_ARG="false"
case "${DOCSPACE_INSTALL_FLUENTBIT,,}" in
  1|true|yes|y) FLUENTBIT_ARG="true" ;;
esac

info "Installing DocSpace Community using native DEB packages. Existing ONLYOFFICE Docs will be reused."
info "Installation log: $LOG_FILE"

# OpenResty's Debian package starts its stock nginx config during dpkg configure.
# That stock config listens on :80, which conflicts with the existing ONLYOFFICE
# Docs nginx. Temporarily deny only that automatic service start; DocSpace later
# writes the requested port and restarts OpenResty directly.
install_openresty_policy

set +e
if [[ "$DOCSPACE_PARTIAL" == "true" ]]; then
  info "Repairing the interrupted package configuration."
  DEBIAN_FRONTEND=noninteractive apt-get -f install -y 2>&1 | tee "$LOG_FILE"
  rc=${PIPESTATUS[0]}
  if (( rc == 0 )); then
    DEBIAN_FRONTEND=noninteractive dpkg --configure -a 2>&1 | tee -a "$LOG_FILE"
    rc=${PIPESTATUS[0]}
  fi
else
  # Do not let the upstream installer create a swapfile inside an LXC. Configure
  # LXC swap from Proxmox instead. Hardware checks stay enabled by default.
  APP_PORT="$DOCSPACE_PORT" \
    bash "$INSTALLER" package \
      --installationtype community \
      --skiphardwarecheck "$SKIP_HC_ARG" \
      --makeswap false \
      --installfluentbit "$FLUENTBIT_ARG" \
      2>&1 | tee "$LOG_FILE"
  rc=${PIPESTATUS[0]}
fi
set -e
restore_openresty_policy
(( rc == 0 )) || exit "$rc"

# Re-apply the external Document Server settings explicitly in case a package
# upgrade or debconf default changed during installation.
printf '%s\n' \
  "docspace docspace/port string $DOCSPACE_PORT" \
  "docspace docspace/ds-url string $DOCS_PUBLIC_URL" \
  "docspace docspace/jwt-header string $JWT_HEADER" \
  "docspace docspace/jwt-secret string $JWT_SECRET" \
  | debconf-set-selections
DEBIAN_FRONTEND=noninteractive dpkg-reconfigure docspace >>"$LOG_FILE" 2>&1

sleep 2

if curl -fsS --max-time 10 "http://127.0.0.1/healthcheck" 2>/dev/null | grep -qi 'true'; then
  ok "Existing ONLYOFFICE Docs healthcheck is OK."
else
  warn "ONLYOFFICE Docs healthcheck did not return 'true'. Check: systemctl status onlyoffice-documentserver nginx"
fi

if ss -H -ltn | awk '{print $4}' | grep -qE ":${DOCSPACE_PORT}$"; then
  ok "DocSpace is listening on TCP port $DOCSPACE_PORT."
else
  warn "DocSpace is not listening on TCP port $DOCSPACE_PORT yet. Inspect systemctl --failed and $LOG_FILE."
fi

cat <<MSG

${GREEN}Installation finished.${NC}

DocSpace setup wizard:
  http://${PRIMARY_IP}:${DOCSPACE_PORT}/

Existing ONLYOFFICE Docs:
  http://${PRIMARY_IP}/

For VyOS HAProxy, the intended split is:
  office.<your-domain>  -> ${PRIMARY_IP}:${DOCSPACE_PORT}
  docs.<your-domain>    -> ${PRIMARY_IP}:80

The Document Server URL currently configured in DocSpace is:
  ${DOCS_PUBLIC_URL}

If your final frontend is HTTPS, both DocSpace and Docs should be exposed through
HTTPS hostnames to avoid mixed-content problems in browsers.

Backup made before installation:
  ${BACKUP_DIR}

Log:
  ${LOG_FILE}
MSG
