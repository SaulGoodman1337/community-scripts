#!/usr/bin/env bash
set -euo pipefail

CONF="/etc/community-scripts-private.conf"
TOKEN_FILE="/etc/community-scripts-github-token"

if [[ ! -r "$CONF" ]]; then
  echo "Missing $CONF" >&2
  exit 2
fi

# shellcheck disable=SC1090
source "$CONF"

: "${COMMUNITY_SCRIPTS_TARGET:?COMMUNITY_SCRIPTS_TARGET is missing in $CONF}"
REPO="${COMMUNITY_SCRIPTS_REPO:-SaulGoodman1337/community-scripts}"
REF="${COMMUNITY_SCRIPTS_REF:-main}"

save_token() {
  local token
  printf 'GitHub token: ' >/dev/tty
  read -rs token </dev/tty
  printf '\n' >/dev/tty
  if [[ -z "$token" ]]; then
    echo "A GitHub token is required." >&2
    exit 2
  fi
  umask 077
  printf '%s\n' "$token" >"$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
  chown root:root "$TOKEN_FILE"
  unset token
  echo "GitHub token saved in $TOKEN_FILE (root-only)."
}

case "${1:-}" in
  --save-token)
    save_token
    exit 0
    ;;
  --forget-token|--clear-token)
    rm -f "$TOKEN_FILE"
    echo "Saved GitHub token removed."
    exit 0
    ;;
esac

TOKEN="${COMMUNITY_SCRIPTS_GITHUB_TOKEN:-}"
if [[ -z "$TOKEN" && -r "$TOKEN_FILE" ]]; then
  IFS= read -r TOKEN <"$TOKEN_FILE" || true
fi

if [[ -z "$TOKEN" ]]; then
  printf 'GitHub token: ' >/dev/tty
  read -rs TOKEN </dev/tty
  printf '\n' >/dev/tty
fi

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
