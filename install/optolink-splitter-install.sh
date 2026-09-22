#!/usr/bin/env bash

# Copyright (c) 2026
# License: MIT
# Source: https://github.com/philippoo66/optolink-splitter

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

cs_repo_fetch config/optolink-splitter/vdensho1-20c2-wb2a-homeassistant.py /opt/optolink/homeassistant_poll_list.py
python3 -m py_compile /opt/optolink/homeassistant_poll_list.py
rm -f /opt/optolink/poll_list.py

sed -i \
  -e "s|^port_vitoconnect = .*|port_vitoconnect = None             # Optional second serial adapter, e.g. '/dev/ttyUSB1'|" \
  -e 's|^mqtt_broker = .*|mqtt_broker = None                     # Set to "host:1883" to enable MQTT|' \
  -e 's|^mqtt_topic = .*|mqtt_topic = "openv"|' \
  -e 's|^mqtt_listen = .*|mqtt_listen = "openv/cmnd"|' \
  -e 's|^mqtt_respond = .*|mqtt_respond = "openv/resp"|' \
  -e 's|^mqtt_fstr = .*|mqtt_fstr = "{dpname}"|' \
  /opt/optolink/settings_ini.py

cs_repo_fetch tools/optolink-apply-vdensho1-ha-profile.sh /usr/local/bin/optolink-apply-vdensho1-ha-profile
chmod 755 /usr/local/bin/optolink-apply-vdensho1-ha-profile

# Keep the previous profile helper as an explicit rollback option.
cs_repo_fetch tools/optolink-apply-vscotho1-profile.sh /usr/local/bin/optolink-apply-vscotho1-profile
chmod 755 /usr/local/bin/optolink-apply-vscotho1-profile

cs_repo_fetch tools/optolink-party-emulator.py /usr/local/bin/optolink-party-emulator
chmod 755 /usr/local/bin/optolink-party-emulator
chown root:root /usr/local/bin/optolink-party-emulator

cs_repo_fetch config/optolink-splitter/wb2a-single-session-logger.py /usr/local/bin/wb2a-single-session-logger
chmod 755 /usr/local/bin/wb2a-single-session-logger
chown root:root /usr/local/bin/wb2a-single-session-logger
ln -sf /usr/local/bin/wb2a-single-session-logger /usr/bin/wb2a-single-session-logger

cs_repo_fetch config/optolink-splitter/optolink-party-emulator.service /etc/systemd/system/optolink-party-emulator.service
chmod 644 /etc/systemd/system/optolink-party-emulator.service
chown root:root /etc/systemd/system/optolink-party-emulator.service

cs_repo_fetch config/optolink-splitter/vcontrol-mapping.md /root/optolink-vcontrol-mapping.md

chown optolink:optolink /opt/optolink/settings_ini.py /opt/optolink/homeassistant_poll_list.py
chmod 640 /opt/optolink/settings_ini.py /opt/optolink/homeassistant_poll_list.py
msg_ok "Prepared VDensHO1/20C2 Home Assistant configuration"

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
# The Party emulator is enabled by the VDensHO1 profile helper once MQTT is
# configured. The fresh installation intentionally leaves it disabled because
# mqtt_broker defaults to None.
msg_ok "Created systemd service"

msg_info "Checking serial adapter"
if [[ -c /dev/ttyUSB0 ]]; then
  if ! runuser -u optolink -- test -r /dev/ttyUSB0 || ! runuser -u optolink -- test -w /dev/ttyUSB0; then
    msg_warn "/dev/ttyUSB0 is present but the optolink service user cannot read/write it"
    stat -c 'Device permissions: %A owner=%U group=%G uid=%u gid=%g' /dev/ttyUSB0 || true
    id optolink || true
    msg_warn "Fix the USB serial device permissions on the Proxmox host, then restart the container/service"
  fi

  systemctl start optolink-splitter.service
  sleep 2
  if systemctl is-active --quiet optolink-splitter.service; then
    msg_ok "Optolink-Splitter is running"
  else
    msg_warn "Service was started but did not stay active; check serial-device permissions and configuration"
    journalctl -u optolink-splitter.service -n 20 --no-pager || true
  fi
else
  msg_warn "No real character device found at /dev/ttyUSB0. The service is enabled but was not started."
  msg_warn "Connect/pass through the Optolink USB adapter, then run: systemctl start optolink-splitter"
fi

motd_ssh
customize
cleanup_lxc
install_private_update ct/optolink-splitter.sh
