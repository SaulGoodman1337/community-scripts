#!/usr/bin/env bash
_CS_DEFAULT_URL="https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main"
_cs_boot="${COMMUNITY_SCRIPTS_CORE_DIR:-$(dirname "${BASH_SOURCE[0]}")/../../core}/core/build.func"
source "$_cs_boot" 2>/dev/null || source <(curl -fsSL "${COMMUNITY_SCRIPTS_CORE_URL:-https://raw.githubusercontent.com/community-scripts/core/main}/core/build.func")
# Copyright (c) 2026
# License: MIT
# Source: https://heirloom-app.com/ | https://github.com/Jyok1m/heirloom

APP="Heirloom"
var_tags="${var_tags:-genealogy;family-tree;docker}"
var_cpu="${var_cpu:-2}"
var_ram="${var_ram:-4096}"
var_disk="${var_disk:-12}"
var_os="${var_os:-debian}"
var_version="${var_version:-13}"
var_arm64="${var_arm64:-no}"
var_unprivileged="${var_unprivileged:-1}"
var_nesting="${var_nesting:-1}"

header_info "$APP"
variables
color
catch_errors

function refresh_compose() {
  local tmp_file="/opt/heirloom/docker-compose.yml.new"

  curl -fsSL     https://raw.githubusercontent.com/Jyok1m/heirloom/main/docker-compose.prod.yml     -o "$tmp_file"

  sed -i 's/127\.0\.0\.1:8081:80/8081:80/g' "$tmp_file"

  if ! grep -q '8081:80' "$tmp_file"; then
    rm -f "$tmp_file"
    msg_error "Unable to expose the Heirloom frontend on port 8081"
    exit 1
  fi

  mv "$tmp_file" /opt/heirloom/docker-compose.yml
}

function update_script() {
  header_info
  check_container_storage
  check_container_resources

  if [[ ! -f /opt/heirloom/docker-compose.yml || ! -f /opt/heirloom/.env ]]; then
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

  msg_info "Refreshing Heirloom compose file"
  cp /opt/heirloom/docker-compose.yml /opt/heirloom/docker-compose.yml.bak
  refresh_compose
  msg_ok "Refreshed Heirloom compose file"

  msg_info "Pulling Heirloom images"
  cd /opt/heirloom
  $STD docker compose pull db migrate api app
  msg_ok "Pulled Heirloom images"

  msg_info "Applying database migrations"
  $STD docker compose run --rm migrate
  msg_ok "Applied database migrations"

  msg_info "Updating Heirloom"
  $STD docker compose up -d api app
  msg_ok "Updated Heirloom"

  msg_info "Checking Heirloom"
  for i in {1..60}; do
    if curl -fsS http://127.0.0.1:8081/ >/dev/null 2>&1; then
      msg_ok "Heirloom is reachable"
      break
    fi
    sleep 2
    if [[ "$i" -eq 60 ]]; then
      msg_error "Heirloom did not become reachable"
      docker compose ps
      docker compose logs --tail=100 api app
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
echo -e "${INFO}${YW}Access Heirloom using the following URL:${CL}"
echo -e "${GATEWAY}${BGN}http://${IP}:8081${CL}"
echo -e "${INFO}${YW}Configuration is stored in ${GN}/opt/heirloom/.env${CL}"
echo -e "${INFO}${YW}Inside the container, run '${GN}update${YW}' to update Heirloom.${CL}"
