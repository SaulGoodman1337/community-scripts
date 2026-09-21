#!/usr/bin/env bash
set -euo pipefail

CONFIG="/etc/smb-scan-proxy.env"
SMB_CONF="/etc/samba/smb.conf"
BACKEND_AUTH="/etc/smb-scan-proxy.backend"

if [[ ! -f "$CONFIG" ]]; then
  echo "Missing $CONFIG" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$CONFIG"
set +a

ENABLED="${ENABLED:-false}"
PRINTER_IP="${PRINTER_IP:-}"
FRONTEND_SHARE="${FRONTEND_SHARE:-scan}"
FRONTEND_USER="${FRONTEND_USER:-scanner}"
FRONTEND_PASSWORD="${FRONTEND_PASSWORD:-}"
BACKEND_HOST="${BACKEND_HOST:-}"
BACKEND_SHARE="${BACKEND_SHARE:-}"
BACKEND_SUBDIR="${BACKEND_SUBDIR:-}"
BACKEND_DOMAIN="${BACKEND_DOMAIN:-WORKGROUP}"
BACKEND_USER="${BACKEND_USER:-}"
BACKEND_PASSWORD="${BACKEND_PASSWORD:-}"

case "$FRONTEND_SHARE" in
  (*[!A-Za-z0-9._-]*|'')
    echo "FRONTEND_SHARE may only contain letters, numbers, dot, underscore and dash" >&2
    exit 1
    ;;
esac

case "$FRONTEND_USER" in
  (*[!A-Za-z0-9._-]*|'')
    echo "FRONTEND_USER contains unsupported characters" >&2
    exit 1
    ;;
esac

if [[ -z "$FRONTEND_PASSWORD" ]]; then
  echo "FRONTEND_PASSWORD must not be empty" >&2
  exit 1
fi

if [[ -n "$PRINTER_IP" ]]; then
  python3 - "$PRINTER_IP" <<'PY'
import ipaddress
import sys
ipaddress.ip_address(sys.argv[1])
PY
fi

if [[ "$ENABLED" == "true" && -z "$PRINTER_IP" ]]; then
  echo "ENABLED=true requires PRINTER_IP" >&2
  exit 1
fi

if ! id scanproxy >/dev/null 2>&1; then
  useradd --system --home-dir /srv/smb-scan-proxy --shell /usr/sbin/nologin scanproxy
fi

if ! id "$FRONTEND_USER" >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$FRONTEND_USER"
fi

install -d -o scanproxy -g scanproxy -m 0770 /srv/smb-scan-proxy/inbox
install -d -o scanproxy -g scanproxy -m 0770 /var/lib/smb-scan-proxy/queue

printf '%s\n%s\n' "$FRONTEND_PASSWORD" "$FRONTEND_PASSWORD" | smbpasswd -s -a "$FRONTEND_USER" >/dev/null

ALLOW_HOSTS="127.0.0.1"
if [[ "$ENABLED" == "true" ]]; then
  ALLOW_HOSTS="$ALLOW_HOSTS $PRINTER_IP"
fi

cat >"$SMB_CONF" <<EOF
[global]
   workgroup = WORKGROUP
   server string = SMB Scan Proxy
   server role = standalone server
   security = user
   map to guest = Never

   # Legacy protocol is exposed only on this isolated frontend.
   server min protocol = NT1
   server max protocol = NT1
   ntlm auth = ntlmv1-permitted
   lanman auth = no

   # This process may also act as a modern SMB client via smbclient.
   client min protocol = SMB2_02
   client max protocol = SMB3

   smb ports = 445 139
   interfaces = lo eth0
   bind interfaces only = yes
   hosts allow = $ALLOW_HOSTS
   hosts deny = 0.0.0.0/0

   load printers = no
   printing = bsd
   disable spoolss = yes
   unix extensions = no
   log file = /var/log/samba/log.%m
   max log size = 1000

[$FRONTEND_SHARE]
   path = /srv/smb-scan-proxy/inbox
   browseable = yes
   read only = no
   guest ok = no
   valid users = $FRONTEND_USER
   force user = scanproxy
   force group = scanproxy
   create mask = 0660
   force create mode = 0660
   directory mask = 0770
   force directory mode = 0770
EOF

testparm -s "$SMB_CONF" >/dev/null

if [[ -n "$BACKEND_HOST" && -n "$BACKEND_SHARE" && -n "$BACKEND_USER" && -n "$BACKEND_PASSWORD" ]]; then
  cat >"$BACKEND_AUTH" <<EOF
username = $BACKEND_USER
password = $BACKEND_PASSWORD
domain = $BACKEND_DOMAIN
EOF
  chown root:scanproxy "$BACKEND_AUTH"
  chmod 640 "$BACKEND_AUTH"
else
  rm -f "$BACKEND_AUTH"
fi

systemctl daemon-reload
systemctl disable --now nmbd.service >/dev/null 2>&1 || true

if [[ "$ENABLED" == "true" ]]; then
  systemctl enable smbd.service smb-scan-proxy-worker.service >/dev/null
  systemctl restart smbd.service
  systemctl restart smb-scan-proxy-worker.service
  echo "SMB scan proxy enabled."
  echo "Frontend: \\\\$HOSTNAME\\$FRONTEND_SHARE (allowed client: $PRINTER_IP)"
else
  systemctl disable --now smbd.service smb-scan-proxy-worker.service >/dev/null 2>&1 || true
  echo "SMB scan proxy remains disabled. Set ENABLED=true and PRINTER_IP in $CONFIG."
fi
