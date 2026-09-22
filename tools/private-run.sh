#!/usr/bin/env bash
set -euo pipefail

REPO="${COMMUNITY_SCRIPTS_REPO:-SaulGoodman1337/community-scripts}"
REF="${COMMUNITY_SCRIPTS_REF:-main}"
TOKEN="${COMMUNITY_SCRIPTS_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}"
TARGET="${1:-}"

if [[ -z "$TOKEN" ]]; then
  printf 'GitHub token: ' >/dev/tty
  read -rs TOKEN </dev/tty
  printf '\n' >/dev/tty
fi

if [[ -z "$TOKEN" ]]; then
  echo "A GitHub token is required for the private repository." >&2
  exit 2
fi

if [[ -z "$TARGET" || "$TARGET" == /* || "$TARGET" == *".."* ]]; then
  echo "Usage: private-run.sh <repo-relative-script> [args ...]" >&2
  exit 2
fi
shift || true

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

archive="$tmp_dir/repo.tar.gz"
curl -fsSL \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/$REPO/tarball/$REF" \
  -o "$archive"

mkdir -p "$tmp_dir/repo"
tar -xzf "$archive" -C "$tmp_dir/repo" --strip-components=1

repo_root="$tmp_dir/repo"

# Existing Optolink-Splitter LXCs historically pointed their update target at
# ct/optolink-splitter.sh. Running that full CT entrypoint inside the container
# unnecessarily loads the community-scripts UI/spinner stack and can fail with
# a broken stdout pipe. Migrate those legacy update calls transparently to the
# dedicated in-container updater. Host-side csrun installs are unaffected.
if [[ "$TARGET" == "ct/optolink-splitter.sh" &&
      -d /opt/optolink/.git &&
      -f /etc/community-scripts-private.conf ]]; then
  TARGET="tools/optolink-splitter-update.sh"
fi

script="$repo_root/$TARGET"
if [[ ! -f "$script" ]]; then
  echo "Repository script not found: $TARGET" >&2
  exit 3
fi

export COMMUNITY_SCRIPTS_ROOT="$repo_root"
export COMMUNITY_SCRIPTS_GITHUB_TOKEN="$TOKEN"
export COMMUNITY_SCRIPTS_REPO="$REPO"
export COMMUNITY_SCRIPTS_REF="$REF"

bash "$script" "$@"
