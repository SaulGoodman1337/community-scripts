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
  $STD cs_repo_fetch tools/optolink-apply-vscotho1-profile.sh /usr/local/bin/optolink-apply-vscotho1-profile
  chmod 755 /usr/local/bin/optolink-apply-vscotho1-profile
  $STD cs_repo_fetch config/optolink-splitter/vcontrol-mapping.md /root/optolink-vcontrol-mapping.md
  msg_ok "Refreshed VScotHO1 profile helper"

  chown -R optolink:optolink /opt/optolink
  systemctl daemon-reload

  msg_info "Restarting Optolink-Splitter"
  if [[ -c /dev/ttyUSB0 ]]; then
    if systemctl restart optolink-splitter.service && sleep 2 && systemctl is-active --quiet optolink-splitter.service; then
      msg_ok "Optolink-Splitter is running"
    else
      msg_warn "Optolink-Splitter did not stay active; check configuration and serial device"
      journalctl -u optolink-splitter.service -n 20 --no-pager || true
    fi
  else
    systemctl stop optolink-splitter.service 2>/dev/null || true
    msg_warn "No real character device found at /dev/ttyUSB0; service remains stopped until the Optolink adapter is available"
  fi

  configure_private_update ct/optolink-splitter.sh

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
