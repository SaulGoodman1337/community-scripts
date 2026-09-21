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

  msg_info "Updating SMB scan proxy"
  cs_repo_fetch apps/smb-scan-proxy/worker.py /opt/smb-scan-proxy/worker.py
  cs_repo_fetch tools/smb-scan-proxy-apply.sh /usr/local/sbin/smb-scan-proxy-apply
  chmod 755 /opt/smb-scan-proxy/worker.py /usr/local/sbin/smb-scan-proxy-apply
  ln -sf /usr/local/sbin/smb-scan-proxy-apply /usr/bin/smb-scan-proxy-apply
  [[ -x /usr/local/bin/smb-scan-proxy-config ]] && ln -sf /usr/local/bin/smb-scan-proxy-config /usr/bin/smb-scan-proxy-config
  [[ -x /usr/local/bin/smb-scan-proxy-status ]] && ln -sf /usr/local/bin/smb-scan-proxy-status /usr/bin/smb-scan-proxy-status
  python3 -m py_compile /opt/smb-scan-proxy/worker.py
  msg_ok "Updated SMB scan proxy"

  msg_info "Re-applying configuration"
  /usr/local/sbin/smb-scan-proxy-apply
  msg_ok "Re-applied configuration"

  configure_private_update ct/smb-scan-proxy.sh

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
