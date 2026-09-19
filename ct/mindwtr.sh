#!/usr/bin/env bash
_CS_DEFAULT_URL="https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main"
_cs_boot="${COMMUNITY_SCRIPTS_CORE_DIR:-$(dirname "${BASH_SOURCE[0]}")/../../core}/core/build.func"
source "$_cs_boot" 2>/dev/null || source <(curl -fsSL "${COMMUNITY_SCRIPTS_CORE_URL:-https://raw.githubusercontent.com/community-scripts/core/main}/core/build.func")
# Copyright (c) 2026
# License: MIT
# Source: https://github.com/dongdongbh/Mindwtr

APP="Mindwtr"
var_tags="${var_tags:-productivity;docker}"
var_cpu="${var_cpu:-2}"
var_ram="${var_ram:-2048}"
var_disk="${var_disk:-8}"
var_os="${var_os:-debian}"
var_version="${var_version:-13}"
var_arm64="${var_arm64:-yes}"
var_unprivileged="${var_unprivileged:-1}"
var_nesting="${var_nesting:-1}"

header_info "$APP"
variables
color
catch_errors

function update_script() {
  header_info
  check_container_storage
  check_container_resources

  if [[ ! -f /opt/mindwtr/compose.yaml || ! -f /opt/mindwtr/.env ]]; then
    msg_error "No ${APP} installation found!"
    exit 1
  fi

  msg_info "Updating base system"
  $STD apt-get update
  $STD apt-get upgrade -y
  msg_ok "Updated base system"

  msg_info "Updating Docker"
  setup_docker
  msg_ok "Updated Docker"

  msg_info "Pulling latest Mindwtr images"
  cd /opt/mindwtr
  $STD docker compose pull
  msg_ok "Pulled latest Mindwtr images"

  msg_info "Updating Mindwtr"
  $STD docker compose up -d --remove-orphans
  msg_ok "Updated Mindwtr"

  msg_info "Checking Mindwtr Cloud"
  for i in {1..30}; do
    if curl -fsS http://127.0.0.1:8787/health >/dev/null 2>&1; then
      msg_ok "Mindwtr Cloud is healthy"
      break
    fi
    sleep 2
    if [[ "$i" -eq 30 ]]; then
      msg_error "Mindwtr Cloud did not become healthy"
      docker compose logs --tail=100 mindwtr-cloud
      exit 150
    fi
  done

  msg_info "Removing unused Docker images"
  $STD docker image prune -f
  msg_ok "Removed unused Docker images"

  msg_ok "Updated successfully!"
  exit
}

start
build_container
description

msg_ok "Completed successfully!\n"
echo -e "${CREATING}${GN}${APP} setup has been successfully initialized!${CL}"
echo -e "${INFO}${YW}Access the web app using the following URL:${CL}"
echo -e "${GATEWAY}${BGN}http://${IP}:5173${CL}"
echo -e "${INFO}${YW}Cloud/Sync API:${CL}"
echo -e "${GATEWAY}${BGN}http://${IP}:8787${CL}"
echo -e "${INFO}${YW}Inside the container, run '${GN}update${YW}' to update Mindwtr.${CL}"
