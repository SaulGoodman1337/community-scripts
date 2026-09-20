#!/usr/bin/env bash
set -Eeuo pipefail

ACTION="${1:-install}"
CONF="/etc/default/docspace-lean"
ENFORCER="/usr/local/sbin/docspace-lean-enforce"
SERVICE="/etc/systemd/system/docspace-lean-enforce.service"
PATH_UNIT="/etc/systemd/system/docspace-lean-enforce.path"

LEAN_OPENSEARCH_HEAP="${DOCSPACE_LEAN_OPENSEARCH_HEAP:-512m}"
LEAN_IDENTITY_HEAP="${DOCSPACE_LEAN_IDENTITY_HEAP:-}"
LEAN_PERSIST="${DOCSPACE_LEAN_PERSIST:-true}"

info() { printf '[INFO] %s\n' "$*"; }
ok()   { printf '[ OK ] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
die()  { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

is_true() {
  case "${1,,}" in
    1|true|yes|y) return 0 ;;
    *) return 1 ;;
  esac
}

validate_heap() {
  [[ "$1" =~ ^[0-9]+[mMgG]$ ]] || die "Heap value must look like 512m, 1g, 2g, ..."
}

[[ $EUID -eq 0 ]] || die "Run as root inside the DocSpace LXC."

case "$ACTION" in
  install|apply|status|remove) ;;
  *) die "Usage: $0 [install|apply|status|remove]" ;;
esac

if [[ "$ACTION" == "remove" ]]; then
  systemctl disable --now docspace-lean-enforce.path >/dev/null 2>&1 || true
  rm -f "$PATH_UNIT" "$SERVICE" "$ENFORCER" "$CONF"
  rm -rf     /etc/systemd/system/docspace-identity-authorization.service.d/lean-memory.conf     /etc/systemd/system/docspace-identity-api.service.d/lean-memory.conf
  systemctl daemon-reload
  ok "Removed persistent DocSpace lean-mode enforcement."
  warn "Services disabled by lean mode are not automatically re-enabled."
  warn "OpenSearch/JVM heap values are not automatically restored."
  exit 0
fi

if [[ "$ACTION" == "status" ]]; then
  echo "Configuration:"
  if [[ -r "$CONF" ]]; then
    cat "$CONF"
  else
    echo "  not installed"
  fi
  echo
  echo "Lean services:"
  for svc in docspace-ai-worker docspace-mcp docspace-telegram; do
    printf '  %-28s enabled=%-8s active=%s\n'       "$svc"       "$(systemctl is-enabled "$svc.service" 2>/dev/null || echo missing)"       "$(systemctl is-active "$svc.service" 2>/dev/null || echo inactive)"
  done
  echo
  echo "OpenSearch heap:"
  grep -E '^[[:space:]]*-Xm[sx]' /etc/opensearch/jvm.options 2>/dev/null || true
  echo
  echo "Persistence watcher:"
  systemctl is-enabled docspace-lean-enforce.path 2>/dev/null || true
  systemctl is-active docspace-lean-enforce.path 2>/dev/null || true
  exit 0
fi

if [[ "$ACTION" == "apply" ]]; then
  [[ -x "$ENFORCER" ]] || die "$ENFORCER is not installed."
  exec "$ENFORCER"
fi

validate_heap "$LEAN_OPENSEARCH_HEAP"
if [[ -n "$LEAN_IDENTITY_HEAP" ]]; then
  validate_heap "$LEAN_IDENTITY_HEAP"
fi

cat >"$CONF" <<EOF
LEAN_OPENSEARCH_HEAP=$LEAN_OPENSEARCH_HEAP
LEAN_IDENTITY_HEAP=$LEAN_IDENTITY_HEAP
EOF
chmod 600 "$CONF"

cat >"$ENFORCER" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

CONF="/etc/default/docspace-lean"
[[ -r "$CONF" ]] || exit 0
# shellcheck disable=SC1090
source "$CONF"

# A systemd.path event can fire while dpkg is still updating package state.
# Wait until package-management processes are gone before touching services.
for _ in $(seq 1 150); do
  if ! pgrep -x dpkg >/dev/null 2>&1      && ! pgrep -x apt >/dev/null 2>&1      && ! pgrep -x apt-get >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if [[ -f /etc/opensearch/jvm.options && -n "${LEAN_OPENSEARCH_HEAP:-}" ]]; then
  heap_changed="$(python3 - /etc/opensearch/jvm.options "$LEAN_OPENSEARCH_HEAP" <<'PY'
import re
import sys

path, heap = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as fh:
    before = fh.read()

after, n1 = re.subn(r"(?m)^-Xms\S+\s*$", f"-Xms{heap}", before, count=1)
after, n2 = re.subn(r"(?m)^-Xmx\S+\s*$", f"-Xmx{heap}", after, count=1)
if not n1:
    after += f"\n-Xms{heap}\n"
if not n2:
    after += f"-Xmx{heap}\n"

if after != before:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(after)
    print("yes")
else:
    print("no")
PY
)"

  if [[ "$heap_changed" == "yes" ]] && systemctl is-active --quiet opensearch; then
    systemctl restart opensearch
  fi
fi

# Conservative lean profile: these are integration/background services without
# a normal browser-facing OpenResty upstream. Keep docspace-ai and backup
# services running because disabling them can turn normal UI probes into 502s.
for svc in docspace-ai-worker docspace-mcp docspace-telegram; do
  if systemctl cat "$svc.service" >/dev/null 2>&1; then
    systemctl disable --now "$svc.service" >/dev/null 2>&1 || true
  fi
done

if [[ -n "${LEAN_IDENTITY_HEAP:-}" ]]; then
  changed=false
  for svc in docspace-identity-authorization docspace-identity-api; do
    dir="/etc/systemd/system/${svc}.service.d"
    file="${dir}/lean-memory.conf"
    mkdir -p "$dir"
    wanted="[Service]
Environment=\"JAVA_TOOL_OPTIONS=-Xms128m -Xmx${LEAN_IDENTITY_HEAP}\""
    current="$(cat "$file" 2>/dev/null || true)"
    if [[ "$current" != "$wanted" ]]; then
      printf '%s\n' "$wanted" >"$file"
      changed=true
    fi
  done

  if [[ "$changed" == "true" ]]; then
    systemctl daemon-reload
    systemctl restart docspace-identity-authorization docspace-identity-api
  fi
fi
EOF
chmod 755 "$ENFORCER"

cat >"$SERVICE" <<EOF
[Unit]
Description=Reapply DocSpace lean-mode settings
After=local-fs.target

[Service]
Type=oneshot
ExecStart=$ENFORCER
TimeoutStartSec=5min
EOF

cat >"$PATH_UNIT" <<EOF
[Unit]
Description=Watch dpkg state and reapply DocSpace lean mode

[Path]
PathChanged=/var/lib/dpkg/status
Unit=docspace-lean-enforce.service

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

if is_true "$LEAN_PERSIST"; then
  systemctl enable --now docspace-lean-enforce.path >/dev/null
  info "Persistent dpkg watcher enabled."
else
  systemctl disable --now docspace-lean-enforce.path >/dev/null 2>&1 || true
  info "Persistent dpkg watcher disabled by DOCSPACE_LEAN_PERSIST=$LEAN_PERSIST."
fi

"$ENFORCER"

ok "DocSpace lean mode installed."
echo "OpenSearch heap: $LEAN_OPENSEARCH_HEAP"
echo "Disabled services: docspace-ai-worker docspace-mcp docspace-telegram"
if [[ -n "$LEAN_IDENTITY_HEAP" ]]; then
  echo "Identity JVM max heap: $LEAN_IDENTITY_HEAP"
else
  echo "Identity JVM heap: unchanged"
fi
