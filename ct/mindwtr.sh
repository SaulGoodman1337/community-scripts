#!/usr/bin/env bash
_CS_DEFAULT_URL="https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main"
_cs_boot="${COMMUNITY_SCRIPTS_CORE_DIR:-$(dirname "${BASH_SOURCE[0]}")/../../core}/core/build.func"
source "$_cs_boot" 2>/dev/null || source <(curl -fsSL "${COMMUNITY_SCRIPTS_CORE_URL:-https://raw.githubusercontent.com/community-scripts/core/main}/core/build.func")

CS_REPO="${COMMUNITY_SCRIPTS_REPO:-SaulGoodman1337/community-scripts}"
CS_REF="${COMMUNITY_SCRIPTS_REF:-main}"

cs_repo_fetch() {
  local rel="${1:?repo-relative path}"
  local dest="${2:?destination}"

  if [[ -n "${COMMUNITY_SCRIPTS_ROOT:-}" && -f "${COMMUNITY_SCRIPTS_ROOT}/$rel" ]]; then
    cp "${COMMUNITY_SCRIPTS_ROOT}/$rel" "$dest"
    return 0
  fi

  if [[ -n "${COMMUNITY_SCRIPTS_GITHUB_TOKEN:-}" ]]; then
    curl -fsSL \
      -H "Authorization: Bearer $COMMUNITY_SCRIPTS_GITHUB_TOKEN" \
      -H "Accept: application/vnd.github.raw+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "https://api.github.com/repos/$CS_REPO/contents/$rel?ref=$CS_REF" \
      -o "$dest"
    return 0
  fi

  # Transitional fallback: this works only while the repository is public.
  curl -fsSL "https://raw.githubusercontent.com/$CS_REPO/$CS_REF/$rel" -o "$dest"
}

configure_private_update() {
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

  configure_private_update ct/mindwtr.sh

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
