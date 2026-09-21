#!/usr/bin/env bash

# Copyright (c) 2026
# License: MIT
# Source: https://github.com/dongdongbh/Mindwtr

CS_REPO="${COMMUNITY_SCRIPTS_REPO:-SaulGoodman1337/community-scripts}"
CS_REF="${COMMUNITY_SCRIPTS_REF:-main}"

cs_repo_fetch() {
  local rel="${1:?repo-relative path}"
  local dest="${2:?destination}"
  if [[ -n "${COMMUNITY_SCRIPTS_ROOT:-}" && -f "${COMMUNITY_SCRIPTS_ROOT}/$rel" ]]; then
    cp "${COMMUNITY_SCRIPTS_ROOT}/$rel" "$dest"
    return 0
  fi
  if [[ -z "${COMMUNITY_SCRIPTS_GITHUB_TOKEN:-}" ]]; then
    echo "Missing COMMUNITY_SCRIPTS_GITHUB_TOKEN for private repository access." >&2
    return 1
  fi
  curl -fsSL \
    -H "Authorization: Bearer $COMMUNITY_SCRIPTS_GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.raw+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/$CS_REPO/contents/$rel?ref=$CS_REF" \
    -o "$dest"
}

install_private_update() {
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

source /dev/stdin <<<"$FUNCTIONS_FILE_PATH"
color
verb_ip6
catch_errors
setting_up_container
network_check
update_os

msg_info "Installing dependencies"
$STD apt-get install -y \
  ca-certificates \
  curl \
  openssl
msg_ok "Installed dependencies"

msg_info "Installing Docker"
setup_docker
msg_ok "Installed Docker"

# Apply the standard community-scripts container customization before starting
# the application. This keeps console autologin and /usr/bin/update available
# even when the application itself fails to start.
motd_ssh
customize

msg_info "Preparing Mindwtr"
install -d -o 1000 -g 1000 -m 0750 /opt/mindwtr/data

MINDWTR_IP="$(hostname -I | awk '{print $1}')"
if [[ -z "$MINDWTR_IP" ]]; then
  msg_error "Unable to determine container IPv4 address"
  exit 1
fi

MINDWTR_TOKEN="$(openssl rand -hex 32)"
MINDWTR_WEB_URL="http://${MINDWTR_IP}:5173"
MINDWTR_CLOUD_URL="http://${MINDWTR_IP}:8787"

cat <<EOF >/opt/mindwtr/.env
MINDWTR_CLOUD_AUTH_TOKENS=${MINDWTR_TOKEN}
MINDWTR_CLOUD_CORS_ORIGIN=${MINDWTR_WEB_URL}
MINDWTR_DEFAULT_CLOUD_URL=${MINDWTR_CLOUD_URL}
EOF
chmod 600 /opt/mindwtr/.env

cat <<'EOF' >/opt/mindwtr/compose.yaml
services:
  mindwtr-cloud:
    image: ghcr.io/dongdongbh/mindwtr-cloud:latest
    container_name: mindwtr-cloud
    hostname: mindwtr-cloud
    restart: unless-stopped
    ports:
      - "8787:8787"
    environment:
      MINDWTR_CLOUD_AUTH_TOKENS: ${MINDWTR_CLOUD_AUTH_TOKENS}
      MINDWTR_CLOUD_CORS_ORIGIN: ${MINDWTR_CLOUD_CORS_ORIGIN}
    volumes:
      - ./data:/app/cloud_data
    healthcheck:
      test:
        - CMD-SHELL
        - >-
          code=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8787/ready);
          [ "$$code" = 200 ] || { [ "$$code" = 404 ] && curl -fsS http://localhost:8787/health >/dev/null; }
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s

  mindwtr-app:
    image: ghcr.io/dongdongbh/mindwtr-app:latest
    container_name: mindwtr-app
    hostname: mindwtr-app
    restart: unless-stopped
    ports:
      - "5173:5173"
    environment:
      MINDWTR_DEFAULT_CLOUD_URL: ${MINDWTR_DEFAULT_CLOUD_URL}
    depends_on:
      mindwtr-cloud:
        condition: service_healthy
EOF

cat <<EOF >/root/mindwtr.creds
Mindwtr Web/PWA: ${MINDWTR_WEB_URL}
Mindwtr Cloud/Sync API: ${MINDWTR_CLOUD_URL}
Sync token: ${MINDWTR_TOKEN}
EOF
chmod 600 /root/mindwtr.creds

msg_ok "Prepared Mindwtr"

msg_info "Pulling Mindwtr images"
cd /opt/mindwtr
$STD docker compose pull
msg_ok "Pulled Mindwtr images"

msg_info "Starting Mindwtr"
$STD docker compose up -d
msg_ok "Started Mindwtr"

msg_info "Checking Mindwtr Cloud"
for i in {1..60}; do
  if curl -fsS http://127.0.0.1:8787/health >/dev/null 2>&1; then
    msg_ok "Mindwtr Cloud is healthy"
    break
  fi

  sleep 2

  if [[ "$i" -eq 60 ]]; then
    msg_error "Mindwtr Cloud did not become healthy"
    docker compose logs --tail=100 mindwtr-cloud
    exit 150
  fi
done

cleanup_lxc
install_private_update ct/mindwtr.sh
