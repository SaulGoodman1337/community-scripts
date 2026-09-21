#!/usr/bin/env bash

# Copyright (c) 2026
# License: MIT

CS_REPO="${COMMUNITY_SCRIPTS_REPO:-SaulGoodman1337/community-scripts}"
CS_REF="${COMMUNITY_SCRIPTS_REF:-main}"

cs_repo_fetch() {
  local rel="${1:?repo-relative path}"
  local dest="${2:?destination}"
  if [[ -n "${COMMUNITY_SCRIPTS_ROOT:-}" && -f "${COMMUNITY_SCRIPTS_ROOT}/$rel" ]]; then
    cp "${COMMUNITY_SCRIPTS_ROOT}/$rel" "$dest"
    return 0
  fi
  if [[ -z "${COMMUNITY_SCRIPTS_GITHUB_TOKEN:-}" ]]; then
    echo "Missing COMMUNITY_SCRIPTS_GITHUB_TOKEN for private repository access." >&2
    return 1
  fi
  curl -fsSL \
    -H "Authorization: Bearer $COMMUNITY_SCRIPTS_GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.raw+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/$CS_REPO/contents/$rel?ref=$CS_REF" \
    -o "$dest"
}

install_private_update() {
  local target="${1:?ct script path}"
  install -d -m 0755 /usr/local/lib/community-scripts
  cs_repo_fetch tools/private-update.sh /usr/local/lib/community-scripts/private-update.sh
  chmod 755 /usr/local/lib/community-scripts/private-update.sh
  cat >/etc/community-scripts-private.conf <<EOF_PRIVATE_UPDATE
COMMUNITY_SCRIPTS_REPO=$CS_REPO
COMMUNITY_SCRIPTS_REF=$CS_REF
COMMUNITY_SCRIPTS_TARGET=$target
EOF_PRIVATE_UPDATE
  chmod 600 /etc/community-scripts-private.conf
  ln -sf /usr/local/lib/community-scripts/private-update.sh /usr/bin/update
}

source /dev/stdin <<<"$FUNCTIONS_FILE_PATH"
color
verb_ip6
catch_errors
setting_up_container
network_check
update_os

msg_info "Installing dependencies"
$STD apt-get install -y   ca-certificates   curl   openssl   python3   samba   smbclient
msg_ok "Installed dependencies"

msg_info "Creating service account and directories"
if ! id scanproxy >/dev/null 2>&1; then
  useradd --system --home-dir /srv/smb-scan-proxy --shell /usr/sbin/nologin scanproxy
fi
install -d -o scanproxy -g scanproxy -m 0770 /srv/smb-scan-proxy/inbox
install -d -o scanproxy -g scanproxy -m 0770 /var/lib/smb-scan-proxy/queue
install -d -m 0755 /opt/smb-scan-proxy
msg_ok "Created service account and directories"

msg_info "Installing SMB scan proxy"
cs_repo_fetch apps/smb-scan-proxy/worker.py /opt/smb-scan-proxy/worker.py
cs_repo_fetch tools/smb-scan-proxy-apply.sh /usr/local/sbin/smb-scan-proxy-apply
chmod 755 /opt/smb-scan-proxy/worker.py /usr/local/sbin/smb-scan-proxy-apply
python3 -m py_compile /opt/smb-scan-proxy/worker.py
msg_ok "Installed SMB scan proxy"

FRONTEND_PASSWORD="$(openssl rand -hex 12)"

msg_info "Creating configuration"
cat >/etc/smb-scan-proxy.env <<EOF
# Keep disabled until PRINTER_IP and backend settings have been reviewed.
ENABLED=false

# Only this printer/scanner IP is allowed to reach the legacy SMB frontend.
PRINTER_IP=

# Legacy frontend presented to the printer.
FRONTEND_SHARE=scan
FRONTEND_USER=scanner
FRONTEND_PASSWORD=$FRONTEND_PASSWORD
FRONTEND_MIN_PROTOCOL=SMB2_02
FRONTEND_MAX_PROTOCOL=SMB2_02

# Modern backend Samba/NAS target.
BACKEND_HOST=
BACKEND_SHARE=
BACKEND_SUBDIR=
BACKEND_DOMAIN=WORKGROUP
BACKEND_USER=
BACKEND_PASSWORD=
BACKEND_PROTOCOL=SMB3

# Worker tuning.
INBOX_DIR=/srv/smb-scan-proxy/inbox
QUEUE_DIR=/var/lib/smb-scan-proxy/queue
POLL_SECONDS=2
STABLE_SECONDS=4
UPLOAD_RETRY_SECONDS=15
EOF
chmod 600 /etc/smb-scan-proxy.env

cat >/root/smb-scan-proxy.creds <<EOF
Frontend SMB credentials generated during installation
=====================================================
Share:    \\LXC-IP\scan
Username: scanner
Password: $FRONTEND_PASSWORD

Configure /etc/smb-scan-proxy.env, then run:
  smb-scan-proxy-config
EOF
chmod 600 /root/smb-scan-proxy.creds
msg_ok "Created configuration"

msg_info "Creating systemd service"
cat >/etc/systemd/system/smb-scan-proxy-worker.service <<'EOF_SERVICE'
[Unit]
Description=SMB Scan Proxy upload worker
After=network-online.target smbd.service
Wants=network-online.target

[Service]
Type=simple
User=scanproxy
Group=scanproxy
EnvironmentFile=/etc/smb-scan-proxy.env
ExecStart=/usr/bin/python3 /opt/smb-scan-proxy/worker.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/srv/smb-scan-proxy /var/lib/smb-scan-proxy
ReadOnlyPaths=-/etc/smb-scan-proxy.backend

[Install]
WantedBy=multi-user.target
EOF_SERVICE
systemctl daemon-reload
msg_ok "Created systemd service"

cat >/usr/local/bin/smb-scan-proxy-config <<'EOF_CONFIG'
#!/usr/bin/env bash
set -e
${EDITOR:-editor} /etc/smb-scan-proxy.env
exec /usr/local/sbin/smb-scan-proxy-apply
EOF_CONFIG
chmod 755 /usr/local/bin/smb-scan-proxy-config

cat >/usr/local/bin/smb-scan-proxy-status <<'EOF_STATUS'
#!/usr/bin/env bash
set -e
echo "== config =="
grep -E '^(ENABLED|PRINTER_IP|FRONTEND_SHARE|FRONTEND_USER|FRONTEND_MIN_PROTOCOL|FRONTEND_MAX_PROTOCOL|BACKEND_HOST|BACKEND_SHARE|BACKEND_SUBDIR|BACKEND_PROTOCOL)=' /etc/smb-scan-proxy.env || true
echo
echo "== services =="
systemctl --no-pager --full status smbd.service smb-scan-proxy-worker.service || true
echo
echo "== queue =="
find /var/lib/smb-scan-proxy/queue -maxdepth 1 -type f -printf '%f\n' 2>/dev/null || true
EOF_STATUS
chmod 755 /usr/local/bin/smb-scan-proxy-status

ln -sf /usr/local/sbin/smb-scan-proxy-apply /usr/bin/smb-scan-proxy-apply
ln -sf /usr/local/bin/smb-scan-proxy-config /usr/bin/smb-scan-proxy-config
ln -sf /usr/local/bin/smb-scan-proxy-status /usr/bin/smb-scan-proxy-status

msg_info "Applying safe initial configuration"
/usr/local/sbin/smb-scan-proxy-apply
msg_ok "Safe initial configuration applied"

motd_ssh
customize
cleanup_lxc
install_private_update ct/smb-scan-proxy.sh
