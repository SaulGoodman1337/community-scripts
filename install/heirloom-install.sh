#!/usr/bin/env bash

# Copyright (c) 2026
# License: MIT
# Source: https://heirloom-app.com/ | https://github.com/Jyok1m/heirloom

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
$STD apt-get install -y   ca-certificates   curl   openssl
msg_ok "Installed dependencies"

msg_info "Installing Docker"
setup_docker
msg_ok "Installed Docker"

motd_ssh
customize

msg_info "Preparing Heirloom"
install -d -m 0750 /opt/heirloom

HEIRLOOM_IP="$(hostname -I | awk '{print $1}')"
if [[ -z "$HEIRLOOM_IP" ]]; then
  msg_error "Unable to determine container IPv4 address"
  exit 1
fi

POSTGRES_PASSWORD="$(openssl rand -hex 32)"
AUTH_JWT_SECRET="$(openssl rand -hex 32)"
HEIRLOOM_URL="http://${HEIRLOOM_IP}:8081"

curl -fsSL   https://raw.githubusercontent.com/Jyok1m/heirloom/main/docker-compose.prod.yml   -o /opt/heirloom/docker-compose.yml

sed -i 's/127\.0\.0\.1:8081:80/8081:80/g' /opt/heirloom/docker-compose.yml

if ! grep -q '8081:80' /opt/heirloom/docker-compose.yml; then
  msg_error "Unable to expose the Heirloom frontend on port 8081"
  exit 1
fi

cat <<EOF_ENV >/opt/heirloom/.env
BACKEND_PORT=3000
BACKEND_URL=http://127.0.0.1:3000
FRONTEND_PORT=8081
FRONTEND_URL=${HEIRLOOM_URL}

POSTGRES_USER=heirloom
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=heirloom
DATABASE_URL=postgresql://heirloom:${POSTGRES_PASSWORD}@db:5432/heirloom

MEDIA_ROOT=./data/media
MAX_UPLOAD_MB=100

AI_PROVIDER=openai
AI_MODEL=gpt-5-mini
AI_API_KEY=
AI_BASE_URL=
AI_REASONING_EFFORT=low

AUTH_JWT_SECRET=${AUTH_JWT_SECRET}
PUBLIC_URL=${HEIRLOOM_URL}
EOF_ENV
chmod 600 /opt/heirloom/.env

cat <<EOF_CREDS >/root/heirloom.creds
Heirloom URL: ${HEIRLOOM_URL}
Configuration: /opt/heirloom/.env
PostgreSQL user: heirloom
PostgreSQL password: ${POSTGRES_PASSWORD}
EOF_CREDS
chmod 600 /root/heirloom.creds
msg_ok "Prepared Heirloom"

msg_info "Pulling Heirloom images"
cd /opt/heirloom
$STD docker compose pull db migrate api app
msg_ok "Pulled Heirloom images"

msg_info "Applying database migrations"
$STD docker compose run --rm migrate
msg_ok "Applied database migrations"

msg_info "Starting Heirloom"
$STD docker compose up -d api app
msg_ok "Started Heirloom"

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

cleanup_lxc
install_private_update ct/heirloom.sh
