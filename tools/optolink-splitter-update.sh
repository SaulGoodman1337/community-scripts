#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/optolink"
CS_REPO="${COMMUNITY_SCRIPTS_REPO:-SaulGoodman1337/community-scripts}"
CS_REF="${COMMUNITY_SCRIPTS_REF:-main}"
ROOT="${COMMUNITY_SCRIPTS_ROOT:-}"

info() { printf '[INFO] %s\n' "$*" >&2; }
ok()   { printf '[ OK ] %s\n' "$*" >&2; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
die()  { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

repo_file() {
  local rel="${1:?repo-relative path}"
  [[ -n "$ROOT" && -f "$ROOT/$rel" ]] || die "Repository file unavailable: $rel"
  printf '%s\n' "$ROOT/$rel"
}

install_repo_file() {
  local rel="${1:?repo-relative path}"
  local dest="${2:?destination}"
  local mode="${3:-0644}"
  install -D -m "$mode" "$(repo_file "$rel")" "$dest"
}

info "Optolink-Splitter update"
printf 'Repository: %s\nRef:        %s\n' "$CS_REPO" "$CS_REF" >&2

[[ -d "$APP_DIR/.git" && -f "$APP_DIR/settings_ini.py" ]] ||
  die "No Optolink-Splitter installation found in $APP_DIR"

info "Updating base system"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get upgrade -y
ok "Base system updated"

info "Updating upstream Optolink-Splitter source"
runuser -u optolink -- git -C "$APP_DIR" fetch --prune origin main
runuser -u optolink -- git -C "$APP_DIR" reset --hard origin/main
ok "Upstream source updated"

info "Updating Python dependencies"
runuser -u optolink -- "$APP_DIR/venv/bin/pip" install --upgrade   pip setuptools wheel pyserial paho-mqtt
ok "Python dependencies updated"

info "Refreshing community-scripts Optolink helpers"
install_repo_file tools/optolink-apply-vdensho1-ha-profile.sh   /usr/local/bin/optolink-apply-vdensho1-ha-profile 0755
install_repo_file tools/optolink-apply-vscotho1-profile.sh   /usr/local/bin/optolink-apply-vscotho1-profile 0755
install_repo_file tools/optolink-party-test.sh   /usr/local/bin/optolink-party-test 0755
ln -sf /usr/local/bin/optolink-party-test /usr/bin/optolink-party-test

install_repo_file tools/optolink-debug.py   /usr/local/bin/optolink-debug 0755
ln -sf /usr/local/bin/optolink-debug /usr/bin/optolink-debug

install_repo_file tools/optolink-party-emulator.py   /usr/local/bin/optolink-party-emulator 0755

install_repo_file config/optolink-splitter/wb2a-single-session-logger.py   /usr/local/bin/wb2a-single-session-logger 0755
ln -sf /usr/local/bin/wb2a-single-session-logger /usr/bin/wb2a-single-session-logger

install_repo_file config/optolink-splitter/wb2a-rkr-cycle-logger.py   /usr/local/bin/wb2a-rkr-cycle-logger 0755
ln -sf /usr/local/bin/wb2a-rkr-cycle-logger /usr/bin/wb2a-rkr-cycle-logger

install_repo_file config/optolink-splitter/optolink-party-emulator.service   /etc/systemd/system/optolink-party-emulator.service 0644

install_repo_file config/optolink-splitter/vcontrol-mapping.md   /root/optolink-vcontrol-mapping.md 0644

systemctl daemon-reload
systemctl enable optolink-party-emulator.service >/dev/null 2>&1 || true
chown root:root   /usr/local/bin/optolink-apply-vdensho1-ha-profile   /usr/local/bin/optolink-apply-vscotho1-profile   /usr/local/bin/optolink-party-test   /usr/local/bin/optolink-debug   /usr/local/bin/optolink-party-emulator   /usr/local/bin/wb2a-single-session-logger   /usr/local/bin/wb2a-rkr-cycle-logger   /etc/systemd/system/optolink-party-emulator.service   /root/optolink-vcontrol-mapping.md
ok "Helpers refreshed"

info "Activating VDensHO1/20C2 Home Assistant profile"
if COMMUNITY_SCRIPTS_ROOT="$ROOT"    COMMUNITY_SCRIPTS_GITHUB_TOKEN="${COMMUNITY_SCRIPTS_GITHUB_TOKEN:-}"    COMMUNITY_SCRIPTS_REPO="$CS_REPO"    COMMUNITY_SCRIPTS_REF="$CS_REF"    /usr/local/bin/optolink-apply-vdensho1-ha-profile; then
  ok "VDensHO1/20C2 Home Assistant profile active"
else
  die "Could not activate VDensHO1/20C2 Home Assistant profile; helper attempted rollback"
fi

chown -R optolink:optolink "$APP_DIR"

info "Refreshing private update entrypoint"
install_repo_file tools/private-update.sh   /usr/local/lib/community-scripts/private-update.sh 0755

cat >/etc/community-scripts-private.conf <<EOF
COMMUNITY_SCRIPTS_REPO=$CS_REPO
COMMUNITY_SCRIPTS_REF=$CS_REF
COMMUNITY_SCRIPTS_TARGET=tools/optolink-splitter-update.sh
EOF
chmod 600 /etc/community-scripts-private.conf
ln -sf /usr/local/lib/community-scripts/private-update.sh /usr/bin/update
ok "Future 'update' runs use the dedicated Optolink updater"

printf '\nInstalled loggers:\n' >&2
printf '  /usr/local/bin/wb2a-single-session-logger\n' >&2
printf '  /usr/local/bin/wb2a-rkr-cycle-logger\n' >&2
printf 'Run RKR logger: wb2a-rkr-cycle-logger\n' >&2
ok "Optolink-Splitter update completed"
