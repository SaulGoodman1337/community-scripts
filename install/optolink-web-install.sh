#!/usr/bin/env bash

# Copyright (c) 2026
# License: MIT

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

BASE_URL="https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/apps/optolink-web"
msg_info "Installing Optolink-Web"
install -d -o optolinkweb -g optolinkweb /opt/optolink-web /opt/optolink-web/templates /opt/optolink-web/static
curl -fsSL "$BASE_URL/app.py" -o /opt/optolink-web/app.py
curl -fsSL "$BASE_URL/datapoints.json" -o /opt/optolink-web/datapoints.json
curl -fsSL "$BASE_URL/requirements.txt" -o /opt/optolink-web/requirements.txt
curl -fsSL "$BASE_URL/templates/index.html" -o /opt/optolink-web/templates/index.html
curl -fsSL "$BASE_URL/static/app.js" -o /opt/optolink-web/static/app.js
curl -fsSL "$BASE_URL/static/style.css" -o /opt/optolink-web/static/style.css
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
\${EDITOR:-editor} /etc/optolink-web.env
systemctl restart optolink-web.service
systemctl --no-pager --full status optolink-web.service
EOF_HELPER
chmod 755 /usr/local/bin/optolink-web-config
msg_ok "Created configuration helper"

motd_ssh
customize
cleanup_lxc
