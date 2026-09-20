#!/usr/bin/env bash

# Copyright (c) 2026
# License: MIT
# Source: https://github.com/philippoo66/optolink-splitter

source /dev/stdin <<<"$FUNCTIONS_FILE_PATH"
color
verb_ip6
catch_errors
setting_up_container
network_check
update_os

msg_info "Installing dependencies"
$STD apt-get install -y \
  ca-certificates \
  git \
  python3 \
  python3-venv
msg_ok "Installed dependencies"

msg_info "Creating Optolink service account"
if ! id optolink >/dev/null 2>&1; then
  useradd --system --home-dir /opt/optolink --shell /usr/sbin/nologin optolink
fi
usermod -aG dialout optolink
msg_ok "Created Optolink service account"

msg_info "Installing Optolink-Splitter"
git clone --depth=1 https://github.com/philippoo66/optolink-splitter.git /opt/optolink
chown -R optolink:optolink /opt/optolink
runuser -u optolink -- python3 -m venv /opt/optolink/venv
runuser -u optolink -- /opt/optolink/venv/bin/pip install --upgrade pip setuptools wheel
runuser -u optolink -- /opt/optolink/venv/bin/pip install pyserial paho-mqtt
msg_ok "Installed Optolink-Splitter"

msg_info "Preparing configuration"
cp /opt/optolink/settings_ini.py.example /opt/optolink/settings_ini.py
cp /opt/optolink/poll_list.py.example /opt/optolink/poll_list.py

sed -i \
  -e "s|^port_vitoconnect = .*|port_vitoconnect = None             # Optional second serial adapter, e.g. '/dev/ttyUSB1'|" \
  -e 's|^mqtt_broker = .*|mqtt_broker = None                     # Set to "host:1883" to enable MQTT|' \
  /opt/optolink/settings_ini.py

chown optolink:optolink /opt/optolink/settings_ini.py /opt/optolink/poll_list.py
chmod 640 /opt/optolink/settings_ini.py /opt/optolink/poll_list.py
msg_ok "Prepared configuration"

msg_info "Creating systemd service"
cat <<'EOF_SERVICE' >/etc/systemd/system/optolink-splitter.service
[Unit]
Description=Optolink Switch/Splitter
Documentation=https://github.com/philippoo66/optolink-splitter
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=optolink
Group=optolink
SupplementaryGroups=dialout
WorkingDirectory=/opt/optolink
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/optolink/venv/bin/python /opt/optolink/optolinkvs2_switch.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF_SERVICE

cat <<'EOF_PORTS' >/usr/local/bin/optolink-ports
#!/usr/bin/env bash
set -e
printf '%s\n' 'Serial devices visible inside this LXC:'
ls -l /dev/serial/by-id 2>/dev/null || true
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
printf '\npyserial detection:\n'
exec /opt/optolink/venv/bin/python /opt/optolink/list_ports.py
EOF_PORTS
chmod 755 /usr/local/bin/optolink-ports

systemctl daemon-reload
systemctl enable optolink-splitter.service
msg_ok "Created systemd service"

msg_info "Checking serial adapter"
if [[ -e /dev/ttyUSB0 ]]; then
  systemctl start optolink-splitter.service
  sleep 2
  if systemctl is-active --quiet optolink-splitter.service; then
    msg_ok "Optolink-Splitter is running"
  else
    msg_warn "Service was started but did not stay active; configure settings_ini.py and poll_list.py"
    journalctl -u optolink-splitter.service -n 20 --no-pager || true
  fi
else
  msg_warn "No /dev/ttyUSB0 detected. The service is enabled but was not started."
  msg_warn "Connect/pass through the Optolink USB adapter, then run: systemctl start optolink-splitter"
fi

motd_ssh
customize
cleanup_lxc
