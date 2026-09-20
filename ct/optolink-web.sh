#!/usr/bin/env bash
_CS_DEFAULT_URL="https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main"
_cs_boot="${COMMUNITY_SCRIPTS_CORE_DIR:-$(dirname "${BASH_SOURCE[0]}")/../../core}/core/build.func"
source "$_cs_boot" 2>/dev/null || source <(curl -fsSL "${COMMUNITY_SCRIPTS_CORE_URL:-https://raw.githubusercontent.com/community-scripts/core/main}/core/build.func")
# Copyright (c) 2026
# License: MIT

APP="Optolink-Web"
var_tags="${var_tags:-home-automation;heating;web;mqtt}"
var_cpu="${var_cpu:-1}"
var_ram="${var_ram:-512}"
var_disk="${var_disk:-4}"
var_os="${var_os:-debian}"
var_version="${var_version:-13}"
var_arm64="${var_arm64:-yes}"
var_unprivileged="${var_unprivileged:-1}"
var_nesting="${var_nesting:-0}"

header_info "$APP"
variables
color
catch_errors

function update_script() {
  header_info
  check_container_storage
  check_container_resources

  if [[ ! -f /opt/optolink-web/app.py || ! -f /etc/optolink-web.env ]]; then
    msg_error "No ${APP} installation found!"
    exit 1
  fi

  msg_info "Updating base system"
  $STD apt-get update
  $STD apt-get upgrade -y
  msg_ok "Updated base system"

  BASE_URL="https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/apps/optolink-web"
  msg_info "Updating Optolink-Web application"
  $STD curl -fsSL "$BASE_URL/app.py" -o /opt/optolink-web/app.py
  $STD curl -fsSL "$BASE_URL/datapoints.json" -o /opt/optolink-web/datapoints.json
  $STD curl -fsSL "$BASE_URL/requirements.txt" -o /opt/optolink-web/requirements.txt
  $STD curl -fsSL "$BASE_URL/templates/index.html" -o /opt/optolink-web/templates/index.html
  $STD curl -fsSL "$BASE_URL/static/app.js" -o /opt/optolink-web/static/app.js
  $STD curl -fsSL "$BASE_URL/static/style.css" -o /opt/optolink-web/static/style.css
  /opt/optolink-web/venv/bin/python -m py_compile /opt/optolink-web/app.py
  chown -R optolinkweb:optolinkweb /opt/optolink-web
  msg_ok "Updated Optolink-Web application"

  msg_info "Updating Python dependencies"
  $STD /opt/optolink-web/venv/bin/pip install --upgrade pip setuptools wheel
  $STD /opt/optolink-web/venv/bin/pip install -r /opt/optolink-web/requirements.txt
  msg_ok "Updated Python dependencies"

  systemctl restart optolink-web.service
  sleep 2
  if systemctl is-active --quiet optolink-web.service; then
    msg_ok "Optolink-Web is running"
  else
    msg_error "Optolink-Web did not start"
    journalctl -u optolink-web.service -n 30 --no-pager || true
    exit 1
  fi

  msg_ok "Updated successfully!"
  exit
}

start
build_container
description

msg_ok "Completed successfully!\n"
echo -e "${CREATING}${GN}${APP} has been successfully initialized!${CL}"
echo -e "${INFO}${YW}Web UI:${CL} ${BGN}http://${IP}:8080${CL}"
echo -e "${INFO}${YW}Configuration:${CL} ${GN}/etc/optolink-web.env${CL}"
echo -e "${INFO}${YW}Service:${CL} ${GN}systemctl status optolink-web${CL}"
echo -e "${INFO}${YW}After configuring the splitter/MQTT endpoints:${CL} ${GN}systemctl restart optolink-web${CL}"
echo -e "${INFO}${YW}Inside the container, run '${GN}update${YW}' to update Optolink-Web.${CL}"
