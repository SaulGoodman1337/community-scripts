#!/usr/bin/env bash
_CS_DEFAULT_URL="https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main"
_cs_boot="${COMMUNITY_SCRIPTS_CORE_DIR:-$(dirname "${BASH_SOURCE[0]}")/../../core}/core/build.func"
source "$_cs_boot" 2>/dev/null || source <(curl -fsSL "${COMMUNITY_SCRIPTS_CORE_URL:-https://raw.githubusercontent.com/community-scripts/core/main}/core/build.func")
# Copyright (c) 2026
# License: MIT
# Source: https://github.com/philippoo66/optolink-splitter

APP="Optolink-Splitter"
var_tags="${var_tags:-home-automation;heating;serial;mqtt}"
var_cpu="${var_cpu:-1}"
var_ram="${var_ram:-512}"
var_disk="${var_disk:-4}"
var_os="${var_os:-debian}"
var_version="${var_version:-13}"
var_arm64="${var_arm64:-yes}"
var_unprivileged="${var_unprivileged:-0}"
var_nesting="${var_nesting:-1}"

header_info "$APP"
variables
color
catch_errors

function update_script() {
  header_info
  check_container_storage
  check_container_resources

  if [[ ! -d /opt/optolink/.git || ! -f /opt/optolink/settings_ini.py ]]; then
    msg_error "No ${APP} installation found!"
    exit 1
  fi

  msg_info "Updating base system"
  $STD apt-get update
  $STD apt-get upgrade -y
  msg_ok "Updated base system"

  msg_info "Updating Optolink-Splitter source"
  $STD runuser -u optolink -- git -C /opt/optolink fetch --prune origin main
  $STD runuser -u optolink -- git -C /opt/optolink reset --hard origin/main
  msg_ok "Updated Optolink-Splitter source"

  msg_info "Updating Python dependencies"
  $STD runuser -u optolink -- /opt/optolink/venv/bin/pip install --upgrade pip setuptools wheel pyserial paho-mqtt
  msg_ok "Updated Python dependencies"

  msg_info "Refreshing VScotHO1 profile helper"
  $STD curl -fsSL \
    https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/tools/optolink-apply-vscotho1-profile.sh \
    -o /usr/local/bin/optolink-apply-vscotho1-profile
  chmod 755 /usr/local/bin/optolink-apply-vscotho1-profile
  $STD curl -fsSL \
    https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/config/optolink-splitter/vcontrol-mapping.md \
    -o /root/optolink-vcontrol-mapping.md
  msg_ok "Refreshed VScotHO1 profile helper"

  chown -R optolink:optolink /opt/optolink
  systemctl daemon-reload

  msg_info "Restarting Optolink-Splitter"
  if [[ -e /dev/ttyUSB0 ]]; then
    if systemctl restart optolink-splitter.service && sleep 2 && systemctl is-active --quiet optolink-splitter.service; then
      msg_ok "Optolink-Splitter is running"
    else
      msg_warn "Optolink-Splitter did not stay active; check configuration and serial device"
      journalctl -u optolink-splitter.service -n 20 --no-pager || true
    fi
  else
    systemctl stop optolink-splitter.service 2>/dev/null || true
    msg_warn "No /dev/ttyUSB0 detected; service remains stopped until the Optolink adapter is available"
  fi

  msg_ok "Updated successfully!"
  exit
}

start
build_container
description

msg_ok "Completed successfully!\n"
echo -e "${CREATING}${GN}${APP} setup has been successfully initialized!${CL}"
echo -e "${INFO}${YW}Configuration:${CL} ${GN}/opt/optolink/settings_ini.py${CL}"
echo -e "${INFO}${YW}Poll list:${CL} ${GN}/opt/optolink/poll_list.py${CL}"
echo -e "${INFO}${YW}TCP endpoint (when enabled):${CL} ${BGN}${IP}:65234${CL}"
echo -e "${INFO}${YW}Service status:${CL} ${GN}systemctl status optolink-splitter${CL}"
echo -e "${INFO}${YW}Serial devices:${CL} ${GN}optolink-ports${CL}"
echo -e "${INFO}${YW}VScotHO1 profile:${CL} ${GN}optolink-apply-vscotho1-profile${CL}"
echo -e "${INFO}${YW}Inside the container, run '${GN}update${YW}' to update Optolink-Splitter.${CL}"
