#!/usr/bin/env bash

# Copyright (c) 2026
# License: MIT
# Source: https://heirloom-app.com/ | https://github.com/Jyok1m/heirloom

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
