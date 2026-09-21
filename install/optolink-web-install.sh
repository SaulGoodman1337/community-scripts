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
$STD apt-get install -y ca-certificates curl python3 python3-venv
msg_ok "Installed dependencies"

msg_info "Creating service account"
if ! id optolinkweb >/dev/null 2>&1; then
  useradd --system --home-dir /opt/optolink-web --shell /usr/sbin/nologin optolinkweb
fi
msg_ok "Created service account"

msg_info "Installing Optolink-Web"
install -d -o optolinkweb -g optolinkweb /opt/optolink-web /opt/optolink-web/templates /opt/optolink-web/static
cs_repo_fetch apps/optolink-web/app.py /opt/optolink-web/app.py
cs_repo_fetch apps/optolink-web/datapoints.json /opt/optolink-web/datapoints.json
cs_repo_fetch apps/optolink-web/requirements.txt /opt/optolink-web/requirements.txt
cs_repo_fetch apps/optolink-web/templates/index.html /opt/optolink-web/templates/index.html
cs_repo_fetch apps/optolink-web/static/app.js /opt/optolink-web/static/app.js
cs_repo_fetch apps/optolink-web/static/style.css /opt/optolink-web/static/style.css
python3 -m venv /opt/optolink-web/venv
/opt/optolink-web/venv/bin/pip install --upgrade pip setuptools wheel
/opt/optolink-web/venv/bin/pip install -r /opt/optolink-web/requirements.txt
/opt/optolink-web/venv/bin/python -m py_compile /opt/optolink-web/app.py
chown -R optolinkweb:optolinkweb /opt/optolink-web
msg_ok "Installed Optolink-Web"

msg_info "Creating configuration"
cat <<'EOF_ENV' >/etc/optolink-web.env
# Existing Optolink-Splitter endpoint
OPTOLINK_HOST=192.168.1.10
OPTOLINK_PORT=65234
OPTOLINK_TCP_TIMEOUT=3.0

# Optional MQTT connection. Leave MQTT_HOST empty to run TCP-only.
MQTT_HOST=
MQTT_PORT=1883
MQTT_USER=
MQTT_PASSWORD=
MQTT_TOPIC=openv

# Safety gate for web writes. Keep false until reads have been verified.
ALLOW_WRITES=false
EOF_ENV
chmod 600 /etc/optolink-web.env
msg_ok "Created configuration"

msg_info "Creating systemd service"
cat <<'EOF_SERVICE' >/etc/systemd/system/optolink-web.service
[Unit]
Description=Optolink Web UI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=optolinkweb
Group=optolinkweb
WorkingDirectory=/opt/optolink-web
EnvironmentFile=/etc/optolink-web.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/optolink-web/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadOnlyPaths=/opt/optolink-web

[Install]
WantedBy=multi-user.target
EOF_SERVICE

systemctl daemon-reload
systemctl enable --now optolink-web.service
sleep 2
if systemctl is-active --quiet optolink-web.service; then
  msg_ok "Optolink-Web is running"
else
  msg_error "Optolink-Web did not start"
  journalctl -u optolink-web.service -n 30 --no-pager || true
  exit 1
fi

cat <<'EOF_HELPER' >/usr/local/bin/optolink-web-config
#!/usr/bin/env bash
set -e
${EDITOR:-editor} /etc/optolink-web.env
systemctl restart optolink-web.service
systemctl --no-pager --full status optolink-web.service
EOF_HELPER
chmod 755 /usr/local/bin/optolink-web-config
msg_ok "Created configuration helper"

motd_ssh
customize
cleanup_lxc
install_private_update ct/optolink-web.sh
