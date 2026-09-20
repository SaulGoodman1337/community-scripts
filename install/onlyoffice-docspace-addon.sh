#!/usr/bin/env bash
set -Eeuo pipefail

# Install ONLYOFFICE DocSpace Community next to an existing native
# ONLYOFFICE Docs Community installation in the same Debian LXC.
# Intended for the Proxmox VE community-scripts ONLYOFFICE LXC.

DOCSPACE_PORT="${DOCSPACE_PORT:-8088}"
DOCS_PUBLIC_URL="${DOCS_PUBLIC_URL:-}"
DOCSPACE_SKIP_HARDWARE_CHECK="${DOCSPACE_SKIP_HARDWARE_CHECK:-false}"
DOCSPACE_INSTALL_FLUENTBIT="${DOCSPACE_INSTALL_FLUENTBIT:-false}"
DOCSPACE_AUTO_ACTIVATE_USERS="${DOCSPACE_AUTO_ACTIVATE_USERS:-false}"
DOCSPACE_LEAN_MODE="${DOCSPACE_LEAN_MODE:-false}"
DOCSPACE_LEAN_PERSIST="${DOCSPACE_LEAN_PERSIST:-true}"
DOCSPACE_LEAN_IDENTITY_HEAP="${DOCSPACE_LEAN_IDENTITY_HEAP:-}"
DOCSPACE_OPENSEARCH_HEAP="${DOCSPACE_OPENSEARCH_HEAP:-}"
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

is_true() {
  case "${1,,}" in
    1|true|yes|y) return 0 ;;
    *) return 1 ;;
  esac
}

if [[ -z "$DOCSPACE_OPENSEARCH_HEAP" ]]; then
  if is_true "$DOCSPACE_LEAN_MODE"; then
    DOCSPACE_OPENSEARCH_HEAP="512m"
  else
    DOCSPACE_OPENSEARCH_HEAP="1g"
  fi
fi

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

# Ports used internally by DocSpace services. The external OpenResty listener
# must not reuse any of them.
DOCSPACE_RESERVED_PORTS=(5000 5001 5003 5004 5005 5006 5007 5009 5010 5011 5012 5013 5014 5015 5027 5032 5033 5034 5075 5099 5100 5124 5157 5158 8080 8081 8092 9090 9834 9899)
for p in "${DOCSPACE_RESERVED_PORTS[@]}"; do
  if (( DOCSPACE_PORT == p )); then
    die "DOCSPACE_PORT=$DOCSPACE_PORT is reserved by an internal DocSpace service. Use e.g. DOCSPACE_PORT=8088."
  fi
done

if ! command -v ss >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq iproute2
fi
if ss -H -ltn | awk '{print $4}' | grep -qE ":${DOCSPACE_PORT}$"; then
  die "TCP port $DOCSPACE_PORT is already in use. Set another non-reserved port, e.g. DOCSPACE_PORT=8188."
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
SWAP_MB="$(awk '/SwapTotal:/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo 0)"
FREE_GB="$(df -Pk / | awk 'NR==2 {printf "%d", $4/1024/1024}')"
info "Detected resources: ${CPU_COUNT} vCPU, ~${MEM_MB} MiB RAM, ~${SWAP_MB} MiB swap, ~${FREE_GB} GiB free on /."
warn "The combined Docs + DocSpace stack is substantially heavier than a Docs-only LXC."
if [[ "$MEM_MB" =~ ^[0-9]+$ ]] && (( MEM_MB < 8192 )); then
  warn "Less than 8 GiB RAM detected. The shared-LXC setup can hit the OOM killer during Java/OpenSearch startup."
fi
if [[ "$SWAP_MB" =~ ^[0-9]+$ ]] && (( SWAP_MB == 0 )); then
  warn "No swap detected. Configure Proxmox LXC swap (for example 4 GiB) to absorb startup memory spikes."
fi

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
  # The existing Document Server runs in the same LXC. Use loopback for the
  # package configuration; after DocSpace is configured, the browser-facing
  # URL is normalized to the same-origin /ds-vpath/ proxy.
  DOCS_PUBLIC_URL="http://127.0.0.1"
  info "DOCS_PUBLIC_URL was not set; using loopback $DOCS_PUBLIC_URL for the existing local Document Server."
fi

case "$DOCS_PUBLIC_URL" in
  http://*|https://*) ;;
  *) die "DOCS_PUBLIC_URL must start with http:// or https://" ;;
esac

# IMPORTANT: no trailing slash here. DocSpace injects this value into proxy_pass
# inside a regex location. nginx forbids a URI part (including a lone "/") in
# proxy_pass for regex locations.
while [[ "$DOCS_PUBLIC_URL" == */ ]]; do
  DOCS_PUBLIC_URL="${DOCS_PUBLIC_URL%/}"
done

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

# DocSpace sizes OpenSearch for a much larger/dedicated host. In this add-on
# OpenSearch shares the LXC with Docs and all DocSpace microservices, so use a
# conservative fixed heap by default. Override with DOCSPACE_OPENSEARCH_HEAP.
if [[ -f /etc/opensearch/jvm.options ]]; then
  case "$DOCSPACE_OPENSEARCH_HEAP" in
    *[!0-9mMgG]*|"") die "DOCSPACE_OPENSEARCH_HEAP must look like 512m, 1g, 2g, ..." ;;
  esac
  cp -a /etc/opensearch/jvm.options "$BACKUP_DIR/opensearch-jvm.options.postinstall"
  python3 - /etc/opensearch/jvm.options "$DOCSPACE_OPENSEARCH_HEAP" <<'PY'
import re
import sys

path, heap = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as fh:
    data = fh.read()

data, n1 = re.subn(r"(?m)^-Xms\S+\s*$", f"-Xms{heap}", data, count=1)
data, n2 = re.subn(r"(?m)^-Xmx\S+\s*$", f"-Xmx{heap}", data, count=1)

if not n1:
    data += f"\n-Xms{heap}\n"
if not n2:
    data += f"-Xmx{heap}\n"

with open(path, "w", encoding="utf-8") as fh:
    fh.write(data)
PY
  systemctl restart opensearch || warn "OpenSearch did not start after applying heap=$DOCSPACE_OPENSEARCH_HEAP."
fi

# The upstream package configurator stops all ds-*.service units before
# configuring DocSpace, but in the EXTERNAL_DOCS_SERVER path it does not start
# the already-installed local Document Server again. Restore the services here.
for svc in ds-docservice ds-converter ds-metrics; do
  if systemctl cat "$svc.service" >/dev/null 2>&1; then
    systemctl restart "$svc.service"
  fi
done

# Normalize the same-LXC topology. The browser reaches Docs through DocSpace's
# same-origin /ds-vpath/ proxy, while server-to-server traffic stays on loopback.
DOCSPACE_APPSETTINGS="/etc/onlyoffice/docspace/appsettings.community.json"
if [[ -f "$DOCSPACE_APPSETTINGS" ]]; then
  python3 - "$DOCSPACE_APPSETTINGS" "$DOCSPACE_PORT" <<'PY'
import json
import sys

path = sys.argv[1]
port = sys.argv[2]

with open(path, "r", encoding="utf-8") as fh:
    data = json.load(fh)

url = data.setdefault("files", {}).setdefault("docservice", {}).setdefault("url", {})
url["public"] = "/ds-vpath/"
url["internal"] = "http://127.0.0.1"
url["portal"] = f"http://127.0.0.1:{port}"

with open(path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
fi

if [[ -f /etc/openresty/conf.d/onlyoffice.conf ]]; then
  sed -i '/~\* \^\/ds-vpath\/ {/,/}/s#\(proxy_pass \).*;#\1http://127.0.0.1;#' \
    /etc/openresty/conf.d/onlyoffice.conf
fi

# DocSpace generates stream and callback URLs on 127.0.0.1 for this same-LXC
# topology. Document Server blocks private-address fetches by default, so allow
# private IPs for its outbound request filter.
python3 - "$ONLYOFFICE_LOCAL_JSON" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as fh:
    data = json.load(fh)

request_filter = (
    data.setdefault("services", {})
        .setdefault("CoAuthoring", {})
        .setdefault("request-filtering-agent", {})
)
request_filter["allowPrivateIPAddress"] = True

with open(path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY

# The Document Server is consumed only through DocSpace's same-origin
# /ds-vpath/ proxy in this topology. Restrict its nginx listener to loopback so
# TCP/80 is not exposed on the LXC network interface. Patch both the generated
# config and ONLYOFFICE templates so a later package reconfigure is less likely
# to restore a wildcard listener.
if [[ -e /etc/nginx/sites-enabled/default || -L /etc/nginx/sites-enabled/default ]]; then
  rm -f /etc/nginx/sites-enabled/default
  info "Disabled the Debian default nginx site."
fi

for conf in \
  /etc/nginx/conf.d/ds.conf \
  /etc/onlyoffice/documentserver/nginx/ds.conf \
  /etc/onlyoffice/documentserver/nginx/ds.conf.tmpl \
  /etc/onlyoffice/documentserver/nginx/ds-ssl.conf.tmpl
do
  [[ -f "$conf" ]] || continue
  sed -i -E \
    -e 's/listen[[:space:]]+0\.0\.0\.0:80;/listen 127.0.0.1:80;/g' \
    -e 's/listen[[:space:]]+\[::\]:80([[:space:]]+default_server)?;/listen [::1]:80\1;/g' \
    "$conf"
done

nginx -t >>"$LOG_FILE" 2>&1
systemctl restart nginx

/usr/local/openresty/nginx/sbin/nginx -t >>"$LOG_FILE" 2>&1
systemctl restart openresty
for svc in docspace-api docspace-files docspace-files-worker docspace-doceditor; do
  if systemctl cat "$svc.service" >/dev/null 2>&1; then
    systemctl restart "$svc.service"
  fi
done

if is_true "$DOCSPACE_LEAN_MODE"; then
  info "Installing conservative DocSpace lean mode."
  DOCSPACE_LEAN_OPENSEARCH_HEAP="$DOCSPACE_OPENSEARCH_HEAP" \
  DOCSPACE_LEAN_IDENTITY_HEAP="$DOCSPACE_LEAN_IDENTITY_HEAP" \
  DOCSPACE_LEAN_PERSIST="$DOCSPACE_LEAN_PERSIST" \
    bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/tools/docspace-lean-mode.sh)" -- install
fi

sleep 2

if curl -fsS --max-time 10 "http://127.0.0.1:8000/healthcheck" 2>/dev/null | grep -qi 'true'; then
  ok "ONLYOFFICE DocService healthcheck is OK."
else
  warn "DocService on 127.0.0.1:8000 did not return 'true'. Check ds-docservice."
fi

if curl -fsS --max-time 10 "http://127.0.0.1/healthcheck" 2>/dev/null | grep -qi 'true'; then
  ok "ONLYOFFICE Docs nginx healthcheck is OK."
else
  warn "ONLYOFFICE Docs on loopback port 80 did not return 'true'. Check nginx and ds-docservice."
fi

if ss -H -ltn | awk '{print $4}' | grep -qx '127.0.0.1:80'; then
  ok "ONLYOFFICE Docs is bound to loopback on TCP port 80."
else
  warn "Expected ONLYOFFICE Docs to listen on 127.0.0.1:80."
fi

if ss -H -ltn | awk '{print $4}' | grep -Eq '^(0\.0\.0\.0:80|\[::\]:80)$'; then
  warn "TCP port 80 still has a wildcard listener. Inspect nginx configuration before exposing the LXC."
fi

if curl -fsS --max-time 10 "http://127.0.0.1:$DOCSPACE_PORT/ds-vpath/healthcheck" 2>/dev/null | grep -qi 'true'; then
  ok "DocSpace /ds-vpath/ Document Server proxy is OK."
else
  warn "DocSpace /ds-vpath/ healthcheck failed. Check OpenResty and the Document Server routing."
fi

if ss -H -ltn | awk '{print $4}' | grep -qE ":${DOCSPACE_PORT}$"; then
  ok "DocSpace is listening on TCP port $DOCSPACE_PORT."
else
  warn "DocSpace is not listening on TCP port $DOCSPACE_PORT yet. Inspect systemctl --failed and $LOG_FILE."
fi

DOCS_VERSION="$(dpkg-query -W -f='${Version}' onlyoffice-documentserver 2>/dev/null || true)"
if [[ "$DOCS_VERSION" == 9.4.0-* ]]; then
  warn "ONLYOFFICE Docs $DOCS_VERSION is affected by the Analytics.js/ad-blocker editor issue."
  warn "If the editor stays as an empty skeleton, disable browser/ad-block filtering for this origin or upgrade Docs."
fi

AUTO_ACTIVATE_ARG="false"
case "${DOCSPACE_AUTO_ACTIVATE_USERS,,}" in
  1|true|yes|y) AUTO_ACTIVATE_ARG="true" ;;
esac

if [[ "$AUTO_ACTIVATE_ARG" == "true" ]]; then
  info "Installing automatic activation for active local DocSpace users."
  curl -fsSL \
    "https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/tools/docspace-auto-activate-users.sh" \
    | bash -s -- install
fi

if is_true "$DOCSPACE_LEAN_MODE"; then
  LEAN_SUMMARY="enabled (OpenSearch=$DOCSPACE_OPENSEARCH_HEAP; disabled: ai-worker, mcp, telegram)"
else
  LEAN_SUMMARY="disabled"
fi

cat <<MSG

${GREEN}Installation finished.${NC}

DocSpace setup wizard:
  http://${PRIMARY_IP}:${DOCSPACE_PORT}/

ONLYOFFICE Docs:
  loopback only: http://127.0.0.1:80/

For HAProxy/reverse proxy, expose only DocSpace:
  office.<your-domain>  -> ${PRIMARY_IP}:${DOCSPACE_PORT}

Document Server routing:
  Browser -> /ds-vpath/ -> 127.0.0.1:80
  DocSpace -> Docs      -> http://127.0.0.1
  Docs -> DocSpace      -> http://127.0.0.1:${DOCSPACE_PORT}

Lean mode:
  ${LEAN_SUMMARY}

The Document Server is intentionally not exposed on the LXC network interface.
When DocSpace is placed behind HTTPS, the editor remains same-origin through
/ds-vpath/, avoiding mixed-content problems.

Backup made before installation:
  ${BACKUP_DIR}

Log:
  ${LOG_FILE}
MSG
