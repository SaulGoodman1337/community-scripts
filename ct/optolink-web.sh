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

  msg_info "Updating Optolink-Web application"
  cs_repo_fetch apps/optolink-web/app.py /opt/optolink-web/app.py
  cs_repo_fetch apps/optolink-web/datapoints.json /opt/optolink-web/datapoints.json
  cs_repo_fetch apps/optolink-web/requirements.txt /opt/optolink-web/requirements.txt
  cs_repo_fetch apps/optolink-web/templates/index.html /opt/optolink-web/templates/index.html
  cs_repo_fetch apps/optolink-web/static/app.js /opt/optolink-web/static/app.js
  cs_repo_fetch apps/optolink-web/static/style.css /opt/optolink-web/static/style.css
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

  configure_private_update ct/optolink-web.sh

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
