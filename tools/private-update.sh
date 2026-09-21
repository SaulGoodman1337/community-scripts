#!/usr/bin/env bash
set -euo pipefail

CONF="/etc/community-scripts-private.conf"
if [[ ! -r "$CONF" ]]; then
  echo "Missing $CONF" >&2
  exit 2
fi

# shellcheck disable=SC1090
source "$CONF"

: "${COMMUNITY_SCRIPTS_TARGET:?COMMUNITY_SCRIPTS_TARGET is missing in $CONF}"
REPO="${COMMUNITY_SCRIPTS_REPO:-SaulGoodman1337/community-scripts}"
REF="${COMMUNITY_SCRIPTS_REF:-main}"

printf 'GitHub token: ' >/dev/tty
read -rs TOKEN </dev/tty
printf '\n' >/dev/tty

if [[ -z "$TOKEN" ]]; then
  echo "A GitHub token is required." >&2
  exit 2
fi

bootstrap="$(mktemp)"
trap 'rm -f "$bootstrap"' EXIT

curl -fsSL \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github.raw+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/$REPO/contents/tools/private-run.sh?ref=$REF" \
  -o "$bootstrap"

COMMUNITY_SCRIPTS_GITHUB_TOKEN="$TOKEN" \
COMMUNITY_SCRIPTS_REPO="$REPO" \
COMMUNITY_SCRIPTS_REF="$REF" \
bash "$bootstrap" "$COMMUNITY_SCRIPTS_TARGET"
