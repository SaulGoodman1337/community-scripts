#!/usr/bin/env bash
_CS_DEFAULT_URL="https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main"
_cs_boot="${COMMUNITY_SCRIPTS_CORE_DIR:-$(dirname "${BASH_SOURCE[0]}")/../../core}/core/build.func"
source "$_cs_boot" 2>/dev/null || source <(curl -fsSL "${COMMUNITY_SCRIPTS_CORE_URL:-https://raw.githubusercontent.com/community-scripts/core/main}/core/build.func")
# Copyright (c) 2026
# License: MIT
# Inspired by https://github.com/Andreetje/smb1-proxy

APP="SMB-Scan-Proxy"
var_tags="${var_tags:-samba;scanner;proxy;legacy}"
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

  if [[ ! -f /etc/smb-scan-proxy.env || ! -f /opt/smb-scan-proxy/worker.py ]]; then
    msg_error "No ${APP} installation found!"
    exit 1
  fi

  msg_info "Updating base system"
  $STD apt-get update
  $STD apt-get upgrade -y
  msg_ok "Updated base system"

  BASE_URL="https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main"
  msg_info "Updating SMB scan proxy"
  $STD curl -fsSL "$BASE_URL/apps/smb-scan-proxy/worker.py" -o /opt/smb-scan-proxy/worker.py
  $STD curl -fsSL "$BASE_URL/tools/smb-scan-proxy-apply.sh" -o /usr/local/sbin/smb-scan-proxy-apply
  chmod 755 /opt/smb-scan-proxy/worker.py /usr/local/sbin/smb-scan-proxy-apply
  python3 -m py_compile /opt/smb-scan-proxy/worker.py
  msg_ok "Updated SMB scan proxy"

  msg_info "Re-applying configuration"
  /usr/local/sbin/smb-scan-proxy-apply
  msg_ok "Re-applied configuration"

  msg_ok "Updated successfully!"
  exit
}

start
build_container
description

msg_ok "Completed successfully!\n"
echo -e "${CREATING}${GN}${APP} has been successfully initialized!${CL}"
echo -e "${INFO}${YW}Configuration:${CL} ${GN}/etc/smb-scan-proxy.env${CL}"
echo -e "${INFO}${YW}Generated frontend credentials:${CL} ${GN}/root/smb-scan-proxy.creds${CL}"
echo -e "${INFO}${YW}Configure and enable:${CL} ${GN}smb-scan-proxy-config${CL}"
echo -e "${INFO}${YW}Status:${CL} ${GN}smb-scan-proxy-status${CL}"
echo -e "${INFO}${YW}The legacy SMB listener remains disabled until ENABLED=true and PRINTER_IP are configured.${CL}"
