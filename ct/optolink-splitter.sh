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
  local update_dir="/usr/local/lib/community-scripts"
  local update_file="$update_dir/private-update.sh"
  local tmp_update

  install -d -m 0755 "$update_dir"

  # Do not overwrite the currently running /usr/bin/update script in place.
  # Bash may still be reading that inode and can resume at a shifted byte
  # offset after the child updater returns. Fetch to a new inode and replace
  # atomically instead.
  tmp_update="$(mktemp "$update_dir/.private-update.sh.XXXXXX")"
  if ! cs_repo_fetch tools/private-update.sh "$tmp_update"; then
    rm -f "$tmp_update"
    return 1
  fi
  chmod 755 "$tmp_update"
  chown root:root "$tmp_update"
  mv -f "$tmp_update" "$update_file"

  cat >/etc/community-scripts-private.conf <<EOF_PRIVATE_UPDATE
COMMUNITY_SCRIPTS_REPO=$CS_REPO
COMMUNITY_SCRIPTS_REF=$CS_REF
COMMUNITY_SCRIPTS_TARGET=$target
EOF_PRIVATE_UPDATE
  chmod 600 /etc/community-scripts-private.conf
  ln -sf "$update_file" /usr/bin/update
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

  msg_info "Refreshing VDensHO1 Home Assistant profile"
  cs_repo_fetch tools/optolink-apply-vdensho1-ha-profile.sh /usr/local/bin/optolink-apply-vdensho1-ha-profile
  chmod 755 /usr/local/bin/optolink-apply-vdensho1-ha-profile

  # Keep the previous VScotHO1 helper as an explicit rollback option.
  cs_repo_fetch tools/optolink-apply-vscotho1-profile.sh /usr/local/bin/optolink-apply-vscotho1-profile
  chmod 755 /usr/local/bin/optolink-apply-vscotho1-profile

  cs_repo_fetch tools/optolink-party-test.sh /usr/local/bin/optolink-party-test
  chmod 755 /usr/local/bin/optolink-party-test
  ln -sf /usr/local/bin/optolink-party-test /usr/bin/optolink-party-test

  cs_repo_fetch tools/optolink-debug.py /usr/local/bin/optolink-debug
  chmod 755 /usr/local/bin/optolink-debug
  ln -sf /usr/local/bin/optolink-debug /usr/bin/optolink-debug

  cs_repo_fetch tools/optolink-party-emulator.py /usr/local/bin/optolink-party-emulator
  chmod 755 /usr/local/bin/optolink-party-emulator
  chown root:root /usr/local/bin/optolink-party-emulator

  cs_repo_fetch config/optolink-splitter/optolink-party-emulator.service /etc/systemd/system/optolink-party-emulator.service
  chmod 644 /etc/systemd/system/optolink-party-emulator.service
  chown root:root /etc/systemd/system/optolink-party-emulator.service
  systemctl daemon-reload
  systemctl enable optolink-party-emulator.service

  cs_repo_fetch config/optolink-splitter/vcontrol-mapping.md /root/optolink-vcontrol-mapping.md
  chown -R optolink:optolink /opt/optolink
  msg_ok "Refreshed profile helpers"

  msg_info "Activating VDensHO1/20C2 Home Assistant profile"
  if /usr/local/bin/optolink-apply-vdensho1-ha-profile; then
    msg_ok "VDensHO1/20C2 Home Assistant profile is active"
  else
    msg_error "Could not activate VDensHO1 Home Assistant profile; rollback was attempted"
    exit 1
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
echo -e "${INFO}${YW}Home Assistant poll list:${CL} ${GN}/opt/optolink/homeassistant_poll_list.py${CL}"
echo -e "${INFO}${YW}TCP endpoint (when enabled):${CL} ${BGN}${IP}:65234${CL}"
echo -e "${INFO}${YW}Service status:${CL} ${GN}systemctl status optolink-splitter${CL}"
echo -e "${INFO}${YW}Party emulation:${CL} ${GN}systemctl status optolink-party-emulator${CL}"
echo -e "${INFO}${YW}Serial devices:${CL} ${GN}optolink-ports${CL}"
echo -e "${INFO}${YW}VDensHO1 HA profile:${CL} ${GN}optolink-apply-vdensho1-ha-profile${CL}"
echo -e "${INFO}${YW}Legacy rollback profile:${CL} ${GN}optolink-apply-vscotho1-profile${CL}"
echo -e "${INFO}${YW}Inside the container, run '${GN}update${YW}' to update Optolink-Splitter.${CL}"
